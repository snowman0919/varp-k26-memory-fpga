"""Dependency-aware Gemma projection-to-TileJob mapping.

The public projection CSV contains ONNX-derived layer, projection class, K/N,
and weight-offset facts, but its original cluster/channel/bundle placement is a
modeled policy. This module keeps those categories explicit and adds a
conservative transformer-stage dependency graph plus autoregressive token
barriers. It does not claim functional Gemma execution.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

from varp.k26_scheduler_model import TileJob


PLACEMENTS = (
    "source_rule",
    "round_robin",
    "size_aware",
    "channel_affinity",
)


@dataclass(frozen=True)
class PlacementSummary:
    placement: str
    tile_count_per_token: int
    cluster_tile_counts: tuple[int, int, int, int]
    cluster_mac_counts: tuple[int, int, int, int]


def _projection_key(row: dict[str, Any]) -> tuple[int, str]:
    return int(row["layer"]), str(row["projection_class"])


def projection_dependencies(
    projections: list[dict[str, Any]],
) -> dict[int, tuple[int, ...]]:
    """Build a conservative projection-stage DAG for one transformer token."""

    by_key = {
        _projection_key(row): ordinal
        for ordinal, row in enumerate(projections)
    }
    layer_ids = sorted(
        {
            int(row["layer"])
            for row in projections
            if str(row["projection_class"]) != "lm_head"
        }
    )
    if not layer_ids:
        raise ValueError("projection inventory has no transformer layers")
    final_layer = max(layer_ids)
    dependencies: dict[int, tuple[int, ...]] = {}

    def require(layer: int, *classes: str) -> tuple[int, ...]:
        missing = [name for name in classes if (layer, name) not in by_key]
        if missing:
            raise ValueError(
                f"layer {layer} missing projection classes: {missing}"
            )
        return tuple(by_key[(layer, name)] for name in classes)

    for ordinal, row in enumerate(projections):
        layer, projection = _projection_key(row)
        if projection in {"q_proj", "k_proj", "v_proj"}:
            dependencies[ordinal] = (
                require(layer - 1, "down_proj") if layer > 0 else ()
            )
        elif projection == "o_proj":
            dependencies[ordinal] = require(
                layer, "q_proj", "k_proj", "v_proj"
            )
        elif projection in {"gate_proj", "up_proj"}:
            dependencies[ordinal] = require(layer, "o_proj")
        elif projection == "down_proj":
            dependencies[ordinal] = require(
                layer, "gate_proj", "up_proj"
            )
        elif projection == "lm_head":
            dependencies[ordinal] = require(final_layer, "down_proj")
        else:
            raise ValueError(f"unsupported projection class: {projection}")
    return dependencies


def _tile_plan(
    projections: list[dict[str, Any]],
    *,
    n_tile: int,
    placement: str,
) -> tuple[list[dict[str, int]], PlacementSummary]:
    if placement not in PLACEMENTS:
        raise ValueError(f"unknown placement: {placement}")
    if n_tile < 1:
        raise ValueError("n_tile must be positive")

    plan: list[dict[str, int]] = []
    cluster_load = [0, 0, 0, 0]
    cluster_tiles = [0, 0, 0, 0]
    global_tile = 0
    for projection_ordinal, row in enumerate(projections):
        k_length = int(row["K"])
        n_total = int(row["N"])
        for n_start in range(0, n_total, n_tile):
            n_length = min(n_tile, n_total - n_start)
            work = k_length * n_length
            if placement == "source_rule":
                home = int(row["candidate_cluster"]) % 4
                bundle = int(row["candidate_bundle"]) % 4
            elif placement == "round_robin":
                home = global_tile % 4
                bundle = home
            elif placement == "size_aware":
                home = min(range(4), key=lambda index: (cluster_load[index], index))
                bundle = home
            else:
                home = int(row["candidate_channel"]) % 4
                bundle = home
            channel = int(row["candidate_channel"]) % 4
            plan.append(
                {
                    "projection_ordinal": projection_ordinal,
                    "n_start": n_start,
                    "n_length": n_length,
                    "home": home,
                    "channel": channel,
                    "bundle": bundle,
                    "work": work,
                }
            )
            cluster_load[home] += work
            cluster_tiles[home] += 1
            global_tile += 1

    return plan, PlacementSummary(
        placement=placement,
        tile_count_per_token=len(plan),
        cluster_tile_counts=tuple(cluster_tiles),
        cluster_mac_counts=tuple(cluster_load),
    )


def make_dependency_aware_tile_jobs(
    projections: Iterable[dict[str, Any]],
    *,
    decode_tokens: int,
    placement: str,
    n_tile: int = 1024,
) -> tuple[list[TileJob], PlacementSummary]:
    """Map projection shapes to N-axis tiles with stage and token barriers.

    `decode_tokens` names the analytical autoregressive sequence length. The
    token barrier is structural; token values and model outputs are not
    functionally executed by this model.
    """

    rows = list(projections)
    if decode_tokens < 1:
        raise ValueError("decode_tokens must be positive")
    dependencies = projection_dependencies(rows)
    plan, summary = _tile_plan(rows, n_tile=n_tile, placement=placement)
    plan_by_projection: dict[int, list[dict[str, int]]] = {}
    for tile in plan:
        plan_by_projection.setdefault(tile["projection_ordinal"], []).append(tile)

    jobs: list[TileJob] = []
    previous_token_final_ids: tuple[int, ...] = ()
    for token in range(decode_tokens):
        projection_job_ids: dict[int, tuple[int, ...]] = {}
        for projection_ordinal, row in enumerate(rows):
            upstream_projection_ids = dependencies[projection_ordinal]
            upstream_job_ids = tuple(
                job_id
                for upstream in upstream_projection_ids
                for job_id in projection_job_ids[upstream]
            )
            if not upstream_projection_ids:
                upstream_job_ids = previous_token_final_ids

            current_ids: list[int] = []
            for tile in plan_by_projection[projection_ordinal]:
                job_id = len(jobs)
                current_ids.append(job_id)
                layer = int(row["layer"])
                home = tile["home"]
                jobs.append(
                    TileJob(
                        job_id=job_id,
                        arrival_timestamp=token,
                        layer_id=min(layer, 25),
                        operation_type=str(row["projection_class"]),
                        activation_id=token * 32 + min(layer, 31),
                        weight_base=(
                            int(row["external_data_offset"])
                            + tile["n_start"]
                        ),
                        output_base=job_id * 4096,
                        k_start=0,
                        k_length=int(row["K"]),
                        n_start=tile["n_start"],
                        n_length=tile["n_length"],
                        preferred_channel=tile["channel"],
                        preferred_link_bundle=tile["bundle"],
                        reduction_owner=home,
                        priority=0,
                        stealable=True,
                        home_cluster=home,
                        dependency_ids=upstream_job_ids,
                    )
                )
            projection_job_ids[projection_ordinal] = tuple(current_ids)
        previous_token_final_ids = projection_job_ids[len(rows) - 1]

    expected = summary.tile_count_per_token * decode_tokens
    if len(jobs) != expected:
        raise AssertionError(f"generated {len(jobs)} jobs, expected {expected}")
    return jobs, summary
