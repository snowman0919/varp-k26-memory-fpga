# Gemma 3 1B acquisition and local verification

The trace generator is deliberately fail-closed. It does not download a model,
extract the two local ZIP files, copy weights into Git, or modify the source
artifact.

## Authorized acquisition

1. Review and accept the applicable Gemma terms at an authorized Google,
   Kaggle, or Hugging Face distribution point.
2. Obtain or export a Gemma 3 1B ONNX artifact with external data through your
   own authenticated process.
3. Keep the artifact outside this repository.
4. Set `GEMMA3_1B_ONNX_DIR` to the directory containing all files listed below.
5. Run the generator; it validates completeness and records new SHA-256 values.

Required local files:

```text
model.onnx
model.onnx_data
config.json
tokenizer.json
tokenizer_config.json
special_tokens_map.json
generation_config.json
chat_template.jinja
```

Command used for this evidence snapshot:

```bash
python3 experiments/gemma3_1b/generate_trace.py \
  --model-dir ${GEMMA3_1B_ONNX_DIR}
```

On another machine:

```bash
export GEMMA3_1B_ONNX_DIR=/authorized/read-only/path/gemma3-1B-onnx
python3 experiments/gemma3_1b/generate_trace.py
```

If the path or any required file is absent, the command exits with status 2 and
prints `BLOCKED`. It never substitutes synthetic graph rows or guessed token
IDs. Different hashes mean a different artifact and require a new evidence
review; they are not silently accepted as equivalent.

## Provenance limitation

The inspected artifact existed before this work. Its original acquisition
transaction, exporter command/revision, and accepted-license receipt are not
available in the workspace. The graph itself, configuration, tokenizer, file
sizes, and hashes are directly inspectable; the missing acquisition chain
remains an explicit provenance blocker for public redistribution.
