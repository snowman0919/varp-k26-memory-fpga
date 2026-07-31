# Gemma 3 1B model license notes

The Gemma model files are not part of this Git repository and must not be added
to release archives produced from it.

The pre-existing local model card at
`${GEMMA3_SOURCE_DIR}/README.md` declares the Hugging Face
license identifier `gemma`, identifies the base model as
`google/gemma-3-1b-pt`, and states that access requires review and acceptance of
Google's usage license. The inspected ONNX export directory does not contain a
standalone license text or an acquisition receipt. Consequently:

- the manifest records hashes and read-only paths but grants no redistribution
  permission;
- users must independently obtain the model from an authorized source and
  accept the applicable Gemma terms;
- model weights, ONNX external data, tokenizer files, and extracted substantial
  weight data must not be published merely because this evidence package refers
  to them;
- the repository contains only bounded hashes, graph metadata, and three small
  16x4 quantization/reference records for reproducibility review.

The local model card points to:

- Gemma documentation: <https://ai.google.dev/gemma/docs/core>
- Gemma terms: <https://ai.google.dev/gemma/terms>
- Hugging Face model identifier: `google/gemma-3-1b-pt`

This note is a provenance and release-control record, not legal advice.
