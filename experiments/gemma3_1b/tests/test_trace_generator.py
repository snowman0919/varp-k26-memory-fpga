from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "generate_trace.py"
SPEC = importlib.util.spec_from_file_location("gemma_trace_generator", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeNode:
    def __init__(self, name: str):
        self.name = name


class TraceGeneratorTests(unittest.TestCase):
    def test_projection_classification_is_exact(self) -> None:
        self.assertEqual(
            MODULE.classify_node(
                FakeNode("/model/layers.7/self_attn/o_proj/MatMul")
            ),
            (7, "attention_projection", "o_proj"),
        )
        self.assertEqual(
            MODULE.classify_node(
                FakeNode("/model/layers.25/mlp/down_proj/MatMul")
            ),
            (25, "mlp_projection", "down_proj"),
        )
        self.assertEqual(
            MODULE.classify_node(FakeNode("/lm_head/MatMul")),
            (26, "lm_head", "lm_head"),
        )
        self.assertEqual(
            MODULE.classify_node(
                FakeNode("/model/layers.0/self_attn/Softmax")
            ),
            (0, "attention_non_projection", None),
        )

    def test_missing_model_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                FileNotFoundError,
                "refusing trace generation",
            ):
                MODULE.validate_model_dir(Path(directory))

    def test_model_resolution_requires_explicit_configuration(self) -> None:
        environment = dict(os.environ)
        environment.pop("GEMMA3_1B_ONNX_DIR", None)
        with mock.patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(
                RuntimeError,
                "No model will be downloaded",
            ):
                MODULE.resolve_model_dir(None)

    def test_token_rows_never_claim_functional_execution(self) -> None:
        projections = [{"node_name": "/lm_head/MatMul"}]
        rows = MODULE.make_token_rows([2, 818], ["<bos>", "The"], projections)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["functional_execution"] is False for row in rows))
        self.assertTrue(all(row["projection_jobs"] == 1 for row in rows))

    def test_canonical_json_is_order_stable(self) -> None:
        self.assertEqual(
            MODULE.canonical_json({"b": 2, "a": 1}),
            '{"a":1,"b":2}',
        )

    def test_small_graph_derived_scheduler_replay_is_exact_once(self) -> None:
        projections = []
        for index in range(8):
            projections.append(
                {
                    "node_name": (
                        f"/model/layers.{index}/mlp/gate_proj/MatMul"
                    ),
                    "operator_category": "mlp_projection",
                    "layer": index,
                    "projection_class": "gate_proj",
                    "K": 64,
                    "N": 16,
                    "external_data_offset": index * 4096,
                    "candidate_cluster": index % 4,
                    "candidate_channel": index % 4,
                    "candidate_bundle": index % 4,
                }
            )
        rows = MODULE.run_scheduler_trace(projections, 2)
        self.assertEqual(
            [row["scheduler"] for row in rows],
            ["S0", "S0-physical", "S1", "S2", "S3", "Oracle"],
        )
        self.assertTrue(all(row["jobs"] == 16 for row in rows))
        self.assertTrue(all(row["completed_jobs"] == 16 for row in rows))
        self.assertTrue(all(row["correctness"] for row in rows))
        self.assertTrue(all(not row["timed_out"] for row in rows))


if __name__ == "__main__":
    unittest.main()
