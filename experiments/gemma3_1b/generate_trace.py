#!/usr/bin/env python3
"""Generate fail-closed Gemma 3 1B graph, token, and hybrid evidence.

The source model remains outside this repository.  This program reads ONNX
protobuf metadata without loading external tensors, except for three explicitly
bounded 16x4 representative tiles.  It never downloads or rewrites model files.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable

import onnx
import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "experiments/gemma3_1b"
MODEL_FILES = (
    "model.onnx",
    "model.onnx_data",
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "generation_config.json",
    "chat_template.jinja",
)
PROMPT = (
    "The K26 memory FPGA balances Gemma projection tiles with locality-aware "
    "work stealing. This deterministic prompt supplies a reproducible token "
    "ledger for graph-derived evaluation, not a generated model response."
)
PROJECTION_RE = re.compile(
    r"^/model/layers\.(?P<layer>\d+)/(?:self_attn/"
    r"(?P<attention>[qkvo]_proj)|mlp/(?P<mlp>gate_proj|up_proj|down_proj))"
    r"/MatMul$"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def tensor_shape(value: onnx.ValueInfoProto) -> list[str | int]:
    dims: list[str | int] = []
    for dim in value.type.tensor_type.shape.dim:
        if dim.dim_value:
            dims.append(int(dim.dim_value))
        elif dim.dim_param:
            dims.append(dim.dim_param)
        else:
            dims.append("?")
    return dims


def dtype_name(elem_type: int) -> str:
    return onnx.TensorProto.DataType.Name(elem_type).lower()


def external_fields(tensor: onnx.TensorProto) -> dict[str, str]:
    return {item.key: item.value for item in tensor.external_data}


def classify_node(
    node: onnx.NodeProto,
) -> tuple[int | None, str, str | None]:
    match = PROJECTION_RE.match(node.name)
    if match:
        projection = match.group("attention") or match.group("mlp")
        category = (
            "attention_projection"
            if match.group("attention")
            else "mlp_projection"
        )
        return int(match.group("layer")), category, projection
    if node.name == "/lm_head/MatMul":
        return 26, "lm_head", "lm_head"
    if "self_attn" in node.name:
        return _layer_from_name(node.name), "attention_non_projection", None
    if "/mlp/" in node.name:
        return _layer_from_name(node.name), "mlp_non_projection", None
    return _layer_from_name(node.name), "other", None


def _layer_from_name(name: str) -> int | None:
    match = re.search(r"/layers\.(\d+)/", name)
    return int(match.group(1)) if match else None


def inspect_graph(model_path: Path) -> tuple[onnx.ModelProto, list[dict[str, Any]], list[dict[str, Any]]]:
    # Path-based checking lets ONNX resolve external-data declarations while
    # avoiding materialization of the 5.21 GB tensor payload.
    onnx.checker.check_model(str(model_path), full_check=False)
    model = onnx.load_model(model_path, load_external_data=False)
    initializers = {tensor.name: tensor for tensor in model.graph.initializer}
    inventory: list[dict[str, Any]] = []
    projections: list[dict[str, Any]] = []
    projection_ordinal = 0

    for index, node in enumerate(model.graph.node):
        layer, category, projection = classify_node(node)
        tensor = initializers.get(node.input[1]) if len(node.input) > 1 else None
        is_projection = projection is not None and tensor is not None and len(tensor.dims) == 2
        k = int(tensor.dims[0]) if is_projection else ""
        n = int(tensor.dims[1]) if is_projection else ""
        fields = external_fields(tensor) if is_projection else {}
        source_weight_bytes = (
            int(fields.get("length", 0))
            if is_projection
            else ""
        )
        offset = int(fields.get("offset", 0)) if is_projection else ""
        row = {
            "node_index": index,
            "node_name": node.name,
            "domain": node.domain,
            "op_type": node.op_type,
            "layer": "" if layer is None else layer,
            "operator_category": category,
            "projection_class": projection or "",
            "K": k,
            "N": n,
            "dtype": dtype_name(tensor.data_type) if is_projection else "",
            "weight_initializer": tensor.name if is_projection else "",
            "source_weight_bytes": source_weight_bytes,
            "activation_bytes": int(k) * 4 if is_projection else "",
            "output_bytes": int(n) * 4 if is_projection else "",
            "reuse": "once_per_decode_token" if is_projection else "",
            "external_data_file": fields.get("location", "") if is_projection else "",
            "external_data_offset": offset,
            # In the model-level placement abstraction the ONNX external-data
            # byte offset is the immutable starting address. Physical DDR
            # placement remains a later mapping step.
            "estimated_memory_address": offset,
            "candidate_cluster": (
                (int(layer or 0) + projection_ordinal) % 4 if is_projection else ""
            ),
            "candidate_channel": (
                ((int(offset) // (1024 * 1024)) + projection_ordinal) % 4
                if is_projection
                else ""
            ),
            "candidate_bundle": (
                (int(layer or 0) + 2 * projection_ordinal) % 4
                if is_projection
                else ""
            ),
            "evidence_type": "graph-derived",
        }
        inventory.append(row)
        if is_projection:
            trace_row = dict(row)
            trace_row.update(
                {
                    "projection_id": projection_ordinal,
                    "modeled_int8_weight_bytes": int(k) * int(n),
                    "modeled_int8_activation_bytes": int(k),
                    "modeled_int32_output_bytes": int(n) * 4,
                    "quantization_state": (
                        "source_float32; accelerator cost uses explicit "
                        "modeled-int8 transform"
                    ),
                    "claim_boundary": (
                        "Node order, shape, dtype, initializer and external-data "
                        "offset are ONNX-derived; placement is deterministic modeled policy."
                    ),
                }
            )
            projections.append(trace_row)
            projection_ordinal += 1

    return model, inventory, projections


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def deterministic_tokens(tokenizer_path: Path, count: int = 32) -> tuple[list[int], list[str]]:
    try:
        from tokenizers import Tokenizer
    except ImportError as error:
        raise RuntimeError(
            "tokenizers is required; refusing to invent token IDs"
        ) from error
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    encoded = tokenizer.encode(PROMPT)
    if len(encoded.ids) < count:
        raise RuntimeError(
            f"prompt encoded to {len(encoded.ids)} tokens, fewer than required {count}"
        )
    return encoded.ids[:count], encoded.tokens[:count]


def make_token_rows(
    token_ids: list[int],
    token_pieces: list[str],
    projections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    order_hash = bytes_sha256(
        ("\n".join(str(row["node_name"]) for row in projections) + "\n").encode()
    )
    return [
        {
            "schema_version": "varp.gemma3.token-trace.v1",
            "token_index": index,
            "token_id": token_id,
            "token_piece": piece,
            "input_kind": "deterministic-token-input",
            "batch": 1,
            "projection_jobs": len(projections),
            "projection_order_sha256": order_hash,
            "evidence_type": "tokenizer-derived+graph-derived",
            "functional_execution": False,
            "claim_boundary": (
                "Token IDs are produced by the local tokenizer; projection order "
                "comes from ONNX. This JSONL is not generated text or an ORT timing trace."
            ),
        }
        for index, (token_id, piece) in enumerate(zip(token_ids, token_pieces))
    ]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(canonical_json(row) + "\n")


def make_tile_jobs(
    projections: list[dict[str, Any]],
    decode_tokens: int,
) -> list[Any]:
    sys.path.insert(0, str(ROOT / "src"))
    from varp.k26_scheduler_model import TileJob

    jobs = []
    for token in range(decode_tokens):
        for ordinal, row in enumerate(projections):
            job_id = token * len(projections) + ordinal
            layer = int(row["layer"])
            home = int(row["candidate_cluster"])
            jobs.append(
                TileJob(
                    job_id=job_id,
                    arrival_timestamp=job_id,
                    layer_id=min(layer, 25),
                    operation_type=str(row["operator_category"]),
                    activation_id=token,
                    weight_base=int(row["external_data_offset"]),
                    output_base=job_id * 4096,
                    k_start=0,
                    k_length=int(row["K"]),
                    n_start=0,
                    n_length=int(row["N"]),
                    preferred_channel=int(row["candidate_channel"]),
                    preferred_link_bundle=int(row["candidate_bundle"]),
                    reduction_owner=home,
                    priority=0,
                    stealable=True,
                    home_cluster=home,
                )
            )
    return jobs


def run_scheduler_trace(
    projections: list[dict[str, Any]],
    decode_tokens: int,
) -> list[dict[str, Any]]:
    sys.path.insert(0, str(ROOT / "src"))
    from varp.k26_scheduler_model import ModelConfig, run_model

    jobs = make_tile_jobs(projections, decode_tokens)
    total_int8_weight_bytes = sum(job.k_length * job.n_length for job in jobs)
    total_link_bytes = sum(
        job.k_length * job.n_length
        + job.k_length
        + job.n_length * 4
        + 32
        for job in jobs
    )
    rows: list[dict[str, Any]] = []
    for scheduler in ("S0", "S0-physical", "S1", "S2", "S3", "Oracle"):
        config = ModelConfig(
            scheduler=scheduler,
            clusters=4,
            channels=4,
            bundles=4,
            link_width_bits=128,
            queue_capacity=max(8192, len(jobs)),
            # A single real Gemma projection is intentionally represented by
            # one coarse job and can exceed the synthetic workload's default
            # 100k-cycle no-progress threshold.  An in-flight completion is
            # progress, not deadlock; retain a finite but safely larger bound.
            deadlock_no_progress_cycles=10_000_000_000,
        )
        result = run_model(
            jobs,
            config,
            seed=0,
            workload="gemma3_1b_projection_trace",
        )
        result["decode_tokens"] = decode_tokens
        result["model_clock_hz"] = 200_000_000
        result["modeled_total_int8_weight_bytes"] = total_int8_weight_bytes
        result["modeled_total_link_bytes"] = total_link_bytes
        result["modeled_projection_ms"] = (
            result["total_completion_cycles"] / 200_000_000 * 1000
        )
        result["claim_boundary"] = (
            "Graph-derived projection order/shapes replayed as one coarse INT8 "
            "job per projection. Timing is analytical-model, not RTL/DRAMsim3/ORT."
        )
        rows.append(result)
    return rows


def read_host_measurement(root: Path) -> dict[str, float]:
    benchmark = root / "inputs/y700/logs/y700_full_graph_profile/benchmark_y700_ort_android.csv"
    shares = root / "inputs/y700/paper_assets/tables/y700_full_graph_operator_share.csv"
    with benchmark.open(encoding="utf-8", newline="") as stream:
        full = next(
            row
            for row in csv.DictReader(stream)
            if row["kind"] == "full_gemma_onnx_decode_step"
            and row["status"] == "completed"
        )
    projection_ms = 0.0
    with shares.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["group"] in {
                "lm_head_projection",
                "mlp_projection",
                "attention_projection_or_matmul",
                "other_matmul",
            }:
                projection_ms += float(row["mean_duration_ms"])
    model_run_ms = 404.948
    return {
        "wallclock_mean_ms": float(full["mean_ms"]),
        "wallclock_p50_ms": float(full["p50_ms"]),
        "wallclock_p95_ms": float(full["p95_ms"]),
        "model_run_mean_ms": model_run_ms,
        "projection_mean_ms": projection_ms,
        "non_projection_mean_ms": model_run_ms - projection_ms,
    }


def build_hybrid_rows(
    scheduler_rows: list[dict[str, Any]],
    host: dict[str, float],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in scheduler_rows:
        tokens = int(result["decode_tokens"])
        modeled_projection = float(result["modeled_projection_ms"])
        host_fallback = host["non_projection_mean_ms"] * tokens
        rows.append(
            {
                "schema_version": "varp.gemma3.hybrid.v1",
                "scenario": f"batch1_decode{tokens}",
                "batch": 1,
                "decode_tokens": tokens,
                "scheduler": result["scheduler"],
                "projection_jobs": result["jobs"],
                "projection_cycles": result["total_completion_cycles"],
                "projection_ms": f"{modeled_projection:.9f}",
                "host_non_projection_fallback_ms": f"{host_fallback:.9f}",
                "hybrid_total_ms": f"{modeled_projection + host_fallback:.9f}",
                "p95_projection_job_cycles": result["p95_tile_latency_cycles"],
                "p99_projection_job_cycles": result["p99_tile_latency_cycles"],
                "cluster_utilization": f"{result['cluster_utilization_mean']:.9f}",
                "remote_weight_bytes": result["remote_weight_bytes"],
                "modeled_total_int8_weight_bytes": (
                    result["modeled_total_int8_weight_bytes"]
                ),
                "link_traffic_bytes": result["modeled_total_link_bytes"],
                "steal_overhead_traffic_bytes": (
                    result["remote_weight_bytes"]
                    + result["activation_retransmission_bytes"]
                    + result["partial_sum_traffic_bytes"]
                ),
                "exact_once": result["correctness"],
                "projection_evidence_type": "hybrid-modeled",
                "host_fallback_evidence_type": (
                    "host-measured" if tokens == 1 else "host-measured-linear-extrapolation"
                ),
                "functional_reference_status": (
                    "pre-existing-y700-ort-cpu-completed; "
                    "not rerun for deterministic token ledger"
                ),
                "claim_boundary": (
                    "Hybrid total combines coarse analytical projection replay "
                    "with measured Y700 non-projection fallback. It is not an "
                    "end-to-end hardware measurement or predicted product latency."
                ),
            }
        )
    return rows


def token_breakdown(projections: list[dict[str, Any]], host: dict[str, float]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in projections:
        grouped.setdefault(str(row["operator_category"]), []).append(row)
    host_group_ms = {
        "attention_projection": 23.97533333333333,
        "mlp_projection": 124.10666666666667,
        "lm_head": 52.074333333333335,
    }
    rows = []
    for category in ("attention_projection", "mlp_projection", "lm_head"):
        group = grouped[category]
        rows.append(
            {
                "operator_category": category,
                "graph_nodes_per_token": len(group),
                "source_float32_weight_bytes": sum(
                    int(row["source_weight_bytes"]) for row in group
                ),
                "modeled_int8_weight_bytes": sum(
                    int(row["modeled_int8_weight_bytes"]) for row in group
                ),
                "host_measured_mean_ms": f"{host_group_ms[category]:.9f}",
                "graph_evidence_type": "graph-derived",
                "timing_evidence_type": "host-measured",
                "claim_boundary": (
                    "Weight bytes are static graph initializer bytes; host duration "
                    "is a separate Y700 CPU-EP profile and is not memory-only time."
                ),
            }
        )
    return rows


def memory_budget_rows(
    model_dir: Path,
    projections: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    external_bytes = (model_dir / "model.onnx_data").stat().st_size
    projection_float = sum(int(row["source_weight_bytes"]) for row in projections)
    projection_int8 = sum(int(row["modeled_int8_weight_bytes"]) for row in projections)
    kv_per_token = (
        int(config["num_hidden_layers"])
        * 2
        * int(config["num_key_value_heads"])
        * int(config["head_dim"])
        * 4
    )
    capacity = 8 * 1024**3
    rows = []
    for context in (1, 32, 512, 32768):
        kv_bytes = kv_per_token * context
        rows.append(
            {
                "context_tokens": context,
                "external_data_bytes": external_bytes,
                "source_float32_projection_bytes": projection_float,
                "modeled_int8_projection_bytes": projection_int8,
                "float32_kv_cache_bytes": kv_bytes,
                "modeled_resident_bytes": projection_int8 + kv_bytes,
                "memory_capacity_bytes": capacity,
                "fits_8gib_modeled_partition": projection_int8 + kv_bytes <= capacity,
                "evidence_type": "graph-derived+capacity-arithmetic",
                "claim_boundary": (
                    "This is capacity arithmetic, not placement, bandwidth, "
                    "MIG closure, or runtime peak-memory evidence."
                ),
            }
        )
    return rows


def extract_representative_tiles(
    model_dir: Path,
    projections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    import numpy as np

    targets = ("o_proj", "gate_proj", "lm_head")
    selected = []
    for target in targets:
        selected.append(
            next(row for row in projections if row["projection_class"] == target)
        )
    data_path = model_dir / "model.onnx_data"
    records = []
    for row in selected:
        n = int(row["N"])
        base = int(row["external_data_offset"])
        raw_rows = []
        with data_path.open("rb") as stream:
            for k_index in range(16):
                stream.seek(base + k_index * n * 4)
                payload = stream.read(4 * 4)
                if len(payload) != 16:
                    raise RuntimeError("bounded tile read ended early")
                raw_rows.append(payload)
        raw = b"".join(raw_rows)
        weights = np.frombuffer(raw, dtype="<f4").reshape(16, 4)
        max_abs = float(np.max(np.abs(weights)))
        scale = max_abs / 127.0 if max_abs else 1.0
        quantized = np.clip(np.rint(weights / scale), -127, 127).astype(np.int8)
        activation = np.array(
            [((index * 17 + 3) % 255) - 127 for index in range(16)],
            dtype=np.int8,
        )
        reference = activation.astype(np.int32) @ quantized.astype(np.int32)
        records.append(
            {
                "projection_class": row["projection_class"],
                "source_initializer": row["weight_initializer"],
                "source_external_offset": base,
                "source_row_stride_bytes": n * 4,
                "source_tile_shape": [16, 4],
                "source_dtype": "float32-little-endian",
                "source_tile_sha256": bytes_sha256(raw),
                "quantization_rule": (
                    "per-tile symmetric INT8; scale=max(abs(x))/127; "
                    "zero_point=0; numpy.rint; clip[-127,127]"
                ),
                "scale": format(scale, ".17g"),
                "zero_point": 0,
                "quantized_tile_sha256": bytes_sha256(quantized.tobytes(order="C")),
                "quantized_weights_int8_k_by_n": quantized.astype(int).tolist(),
                "activation_int8": activation.astype(int).tolist(),
                "software_reference_int32": reference.astype(int).tolist(),
                "evidence_type": (
                    "actual-weight-bounded-extract+software-reference+rtl-fixture"
                ),
                "claim_boundary": (
                    "The bounded INT8 values are injected by "
                    "GemmaWeightTileRtlParitySpec; this does not validate "
                    "full-model quantization or end-to-end model execution."
                ),
            }
        )
    return records


def model_manifest(
    model_dir: Path,
    model: onnx.ModelProto,
    config: dict[str, Any],
    files: list[dict[str, Any]],
    projections: list[dict[str, Any]],
) -> dict[str, Any]:
    initializer_types = sorted(
        {dtype_name(tensor.data_type) for tensor in model.graph.initializer}
    )
    external_locations = sorted(
        {
            external_fields(tensor).get("location", "")
            for tensor in model.graph.initializer
            if tensor.data_location == onnx.TensorProto.EXTERNAL
        }
        - {""}
    )
    return {
        "schema_version": "varp.gemma3.model-manifest.v1",
        "status": "available-local-external-artifact",
        "model_family": "Gemma 3",
        "variant": "1B",
        "artifact_path": str(model_dir),
        "artifact_policy": "read-only; not copied into Git",
        "provenance": (
            "pre-existing local artifact; original acquisition transaction "
            "and exporter revision are not present"
        ),
        "files": files,
        "onnx": {
            "ir_version": model.ir_version,
            "opsets": [
                {"domain": item.domain or "ai.onnx", "version": item.version}
                for item in model.opset_import
            ],
            "graph_nodes": len(model.graph.node),
            "onnx_checker": "passed-full_check_false",
            "initializers": len(model.graph.initializer),
            "initializer_dtypes": initializer_types,
            "external_data_locations": external_locations,
            "inputs": [
                {
                    "name": value.name,
                    "dtype": dtype_name(value.type.tensor_type.elem_type),
                    "shape": tensor_shape(value),
                }
                for value in model.graph.input
            ],
            "outputs": [
                {
                    "name": value.name,
                    "dtype": dtype_name(value.type.tensor_type.elem_type),
                    "shape": tensor_shape(value),
                }
                for value in model.graph.output
            ],
        },
        "architecture": {
            "model_type": config["model_type"],
            "hidden_size": config["hidden_size"],
            "intermediate_size": config["intermediate_size"],
            "layers": config["num_hidden_layers"],
            "attention_heads": config["num_attention_heads"],
            "key_value_heads": config["num_key_value_heads"],
            "head_dim": config["head_dim"],
            "vocabulary": config["vocab_size"],
            "max_position_embeddings": config["max_position_embeddings"],
            "config_dtype": config["dtype"],
        },
        "quantization": {
            "artifact_state": "unquantized-float32",
            "graph_initializer_dtypes": list(initializer_types),
            "accelerator_cost_transform": (
                "explicit modeled INT8; source graph remains float32"
            ),
        },
        "projection_nodes": len(projections),
        "license": {
            "identifier_from_local_model_card": "gemma",
            "gated_access_notice": True,
            "redistribution_approved_by_this_manifest": False,
            "notes": "models/LICENSE_NOTES.md",
        },
        "claim_boundary": (
            "Graph structure and local file hashes are directly inspected. "
            "Artifact acquisition provenance and exporter identity remain unresolved."
        ),
    }


def validate_model_dir(model_dir: Path) -> None:
    missing = [name for name in MODEL_FILES if not (model_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(
            "Gemma artifact incomplete; refusing trace generation. Missing: "
            + ", ".join(missing)
        )


def generate(model_dir: Path, output: Path) -> dict[str, Any]:
    model_dir = model_dir.resolve()
    validate_model_dir(model_dir)
    output.mkdir(parents=True, exist_ok=True)
    model, inventory, projections = inspect_graph(model_dir / "model.onnx")
    if len(projections) != 183:
        raise RuntimeError(
            f"expected 183 dense projection nodes, found {len(projections)}; "
            "refusing to silently accept a different graph"
        )
    config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    files = [
        {
            "name": name,
            "path": str(model_dir / name),
            "size_bytes": (model_dir / name).stat().st_size,
            "sha256": sha256(model_dir / name),
        }
        for name in MODEL_FILES
    ]

    models_dir = ROOT / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    manifest = model_manifest(model_dir, model, config, files, projections)
    (models_dir / "gemma3_1b_manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    (models_dir / "gemma3_1b_files.sha256").write_text(
        "".join(f"{item['sha256']}  {item['path']}\n" for item in files),
        encoding="utf-8",
    )

    graph_path = output / "graph_inventory.csv"
    projection_path = output / "projection_trace.csv"
    token_path = output / "token_trace.jsonl"
    tile_path = output / "representative_weight_tiles.json"
    tile_csv_path = output / "representative_weight_tiles_int8.csv"
    write_csv(graph_path, inventory)
    write_csv(projection_path, projections)
    token_ids, token_pieces = deterministic_tokens(model_dir / "tokenizer.json")
    token_rows = make_token_rows(token_ids, token_pieces, projections)
    write_jsonl(token_path, token_rows)
    tile_records = extract_representative_tiles(model_dir, projections)
    tile_path.write_text(
        json.dumps(tile_records, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tile_csv_rows = []
    for tile in tile_records:
        for k_index, weights in enumerate(
            tile["quantized_weights_int8_k_by_n"]
        ):
            tile_csv_rows.append(
                {
                    "projection_class": tile["projection_class"],
                    "k_index": k_index,
                    "activation_int8": tile["activation_int8"][k_index],
                    **{
                        f"weight_n{n_index}_int8": value
                        for n_index, value in enumerate(weights)
                    },
                    **{
                        f"reference_n{n_index}_int32": tile[
                            "software_reference_int32"
                        ][n_index]
                        for n_index in range(4)
                    },
                    "quantized_tile_sha256": tile["quantized_tile_sha256"],
                }
            )
    write_csv(tile_csv_path, tile_csv_rows)

    scheduler_rows = (
        run_scheduler_trace(projections, 1)
        + run_scheduler_trace(projections, 32)
    )
    scheduler_path = output / "scheduler_replay.csv"
    write_csv(scheduler_path, scheduler_rows)
    host = read_host_measurement(ROOT)
    results_dir = ROOT / "results/model_level"
    hybrid_path = results_dir / "gemma3_1b_hybrid.csv"
    breakdown_path = results_dir / "gemma3_1b_token_breakdown.csv"
    memory_path = results_dir / "gemma3_1b_memory_budget.csv"
    write_csv(hybrid_path, build_hybrid_rows(scheduler_rows, host))
    write_csv(breakdown_path, token_breakdown(projections, host))
    write_csv(memory_path, memory_budget_rows(model_dir, projections, config))

    artifacts = {}
    for path in (
        graph_path,
        projection_path,
        token_path,
        tile_path,
        tile_csv_path,
        scheduler_path,
        hybrid_path,
        breakdown_path,
        memory_path,
        models_dir / "gemma3_1b_manifest.yaml",
        models_dir / "gemma3_1b_files.sha256",
    ):
        artifacts[path.relative_to(ROOT).as_posix()] = {
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        }
    trace_manifest = {
        "schema_version": "varp.gemma3.trace-manifest.v1",
        "status": "complete-with-explicit-hybrid-boundary",
        "model_onnx_sha256": next(
            item["sha256"] for item in files if item["name"] == "model.onnx"
        ),
        "model_external_data_sha256": next(
            item["sha256"] for item in files if item["name"] == "model.onnx_data"
        ),
        "graph_nodes": len(inventory),
        "projection_nodes_per_token": len(projections),
        "token_records": len(token_rows),
        "scheduler_replays": len(scheduler_rows),
        "schedulers": ["S0", "S0-physical", "S1", "S2", "S3", "Oracle"],
        "scheduler_variants_not_run": {},
        "repetition_scope": (
            "One deterministic graph/token ledger. Seed and process repetitions "
            "would be byte-identical because this replay has no stochastic input."
        ),
        "decode_token_counts": [1, 32],
        "functional_reference": {
            "status": "pre-existing-host-measurement",
            "platform": "Lenovo Y700 / ONNX Runtime Android CPU EP",
            "batch": 1,
            "sequence_length": 1,
            "artificial_past_length": 1,
            "measured_runs": 3,
            "wallclock_mean_ms": host["wallclock_mean_ms"],
            "source": (
                "inputs/y700/logs/y700_full_graph_profile/"
                "benchmark_y700_ort_android.csv"
            ),
            "boundary": (
                "Not rerun locally and not executed with token_trace.jsonl input."
            ),
        },
        "artifacts": artifacts,
        "claim_boundary": (
            "Graph and tokenizer outputs are directly derived from the hashed "
            "local artifact. Scheduler and hybrid timing are analytical. "
            "Representative tiles have software references and a bounded RTL "
            "fixture; this is not full-model RTL inference."
        ),
    }
    trace_manifest_path = output / "trace_manifest.json"
    trace_manifest_path.write_text(
        json.dumps(trace_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return trace_manifest


def resolve_model_dir(argument: Path | None) -> Path:
    if argument is not None:
        return argument
    value = os.environ.get("GEMMA3_1B_ONNX_DIR")
    if value:
        return Path(value)
    raise RuntimeError(
        "Gemma model path not configured. Set GEMMA3_1B_ONNX_DIR or pass "
        "--model-dir. No model will be downloaded automatically."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        manifest = generate(resolve_model_dir(args.model_dir), args.output)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
