# Gemma 3 1B graph-derived evidence

This directory is generated from the hashed, read-only Gemma 3 1B ONNX
artifact recorded in `models/gemma3_1b_manifest.yaml`.

## Evidence layers

- `graph_inventory.csv`: all 7,837 ONNX nodes in execution order. Projection
  shape, initializer, dtype, external-data offset, and byte count are directly
  graph-derived.
- `projection_trace.csv`: the 183 dense projection nodes executed per decode
  token: 26 layers × (q, k, v, o, gate, up, down) plus `lm_head`.
- `token_trace.jsonl`: 32 deterministic tokenizer-derived input IDs linked to
  the projection-order hash. It is not generated text or an ORT timing trace.
- `scheduler_replay.csv`: the same projection ledger replayed for S0,
  S0-physical, S1–S3, and the offline Oracle list scheduler at decode lengths
  1 and 32. Each projection is one coarse analytical INT8 job. The Oracle row
  also carries a resource-load lower bound; its list-schedule completion time
  is not mislabeled as a mathematical optimum.
- `representative_weight_tiles.json`: bounded 16×4 reads from actual
  float32 external-data offsets for attention output, MLP gate, and `lm_head`,
  with deterministic symmetric INT8 quantization, explicit weight values, and
  software references. `representative_weight_tiles_int8.csv` is the exact
  fixture consumed by the RTL parity test.
- `trace_manifest.json`: hashes, counts, functional-reference provenance, and
  the claim boundary.

Model-level outputs are under `results/model_level/`.

## Reproduce

```bash
export GEMMA3_1B_ONNX_DIR=/authorized/read-only/path/gemma3-1B-onnx
python3 experiments/gemma3_1b/generate_trace.py
```

The committed snapshot was generated with:

```bash
python3 experiments/gemma3_1b/generate_trace.py \
  --model-dir ${GEMMA3_1B_ONNX_DIR}
```

Tests:

```bash
python3 -m pytest -q \
  experiments/gemma3_1b/tests/test_trace_generator.py
sbt -batch "testOnly varp.GemmaWeightTileRtlParitySpec"
```

## Interpretation boundary

The ONNX graph, tokenizer output, file hashes, and bounded weight bytes are
directly observed. Placement and scheduler replay are analytical. The hybrid
total combines those analytical projection cycles with the pre-existing Y700
CPU-EP non-projection measurement; it is neither a board measurement nor a
product-latency prediction. The three bounded 16×4 tiles are injected into the
actual `ComputeCluster`/`DecodeMatVecInt8` path and compared with their INT32
software references. That bounded parity result is not full-model RTL
inference or validation of the model-wide quantization policy.
