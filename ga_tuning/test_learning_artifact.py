"""Tests for GA learning artifact construction and provenance."""
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from ga_tuning.extract_and_apply_parameters import ParameterExtractor
from ga_tuning.learning_artifact import build_ga_learning_artifact


class GATuningLearningArtifactTests(unittest.TestCase):
    def test_nested_ga_output_preserves_candidates_and_blocks_knowledge_promotion(self):
        artifact = build_ga_learning_artifact(
            {
                "timestamp": "20261008_160000",
                "population_size": 50,
                "generations": 25,
                "total_evaluations": 1250,
            },
            {
                "compression": [
                    {"parameters": {"compression_level": 4.0, "target_reduction": 0.4}, "fitness": 0.91},
                    {"parameters": {"compression_level": 3.0, "target_reduction": 0.35}, "fitness": 0.82},
                ],
                "thompson": [],
            },
            {"compression": {"compression_level": 3.0}, "thompson": {"alpha_prior": 2.0}},
            best_parameters_source="ga_best_parameters_20261008_160000.json",
            summary_source="ga_summary_20261008_160000.json",
        )
        data = artifact.to_dict()
        self.assertEqual(data["artifact_type"], "ga.tuning.result")
        self.assertEqual(data["payload"]["run_id"], "ga-20261008_160000")
        self.assertEqual(data["payload"]["selected_parameters"]["compression"]["compression_level"], 4.0)
        self.assertEqual(len(data["payload"]["candidate_population"]["candidates"]["compression"]), 2)
        self.assertEqual(data["payload"]["fallback_parameters"]["thompson"]["alpha_prior"], 2.0)
        self.assertFalse(data["payload"]["knowledge_promotion"]["eligible"])
        self.assertIsNone(data["payload"]["evidence"]["confidence"])

    def test_empty_and_partial_results_are_valid_and_do_not_invent_systems(self):
        artifact = build_ga_learning_artifact(
            {"timestamp": "20261008_160000"},
            {"caching": [], "matrix": [{"parameters": {"task_weight": 0.2}, "fitness": 0.5}]},
            {"compression": {"compression_level": 3.0}},
            best_parameters_source="best.json",
            summary_source="summary.json",
        )
        payload = artifact.to_dict()["payload"]
        self.assertEqual(payload["evaluation_scope"]["systems_evaluated"], ["matrix"])
        self.assertEqual(payload["selected_parameters"], {"matrix": {"task_weight": 0.2}})
        self.assertIn("compression", payload["fallback_parameters"])


    def test_parameter_extractor_reads_current_nested_ga_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            best = root / "ga_best_parameters_20261008_160000.json"
            best.write_text(json.dumps({
                "compression": [{"parameters": {"compression_level": 4.5, "target_reduction": 0.42}, "fitness": 0.9}],
                "thompson": [],
            }), encoding="utf-8")
            extractor = ParameterExtractor(root, root / "settings.json", root / "evolution.md")
            params = extractor.extract_parameters(best)
            self.assertEqual(params["compression"]["compression_level"], 4.5)
            self.assertEqual(params["compression"]["target_reduction"], 0.42)
            self.assertNotIn("thompson", params)


    def test_partial_candidate_preserves_unreported_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            best = root / "ga_best_parameters_20261008_160000.json"
            best.write_text(json.dumps({
                "compression": [{"parameters": {"compression_level": 4.5}, "fitness": 0.9}],
            }), encoding="utf-8")
            settings = root / "settings.json"
            settings.write_text(json.dumps({
                "env": {
                    "GA_COMPRESSION_LEVEL": "2.0",
                    "GA_COMPRESSION_TARGET": "0.61",
                }
            }), encoding="utf-8")
            extractor = ParameterExtractor(root, settings, root / "evolution.md")
            params = extractor.extract_parameters(best)
            self.assertEqual(params, {"compression": {"compression_level": 4.5}})

            extractor.update_settings_json(params, run_id="ga-20261008_160000")
            updated = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(updated["env"]["GA_COMPRESSION_LEVEL"], "4.5")
            self.assertEqual(updated["env"]["GA_COMPRESSION_TARGET"], "0.61")
            self.assertEqual(updated["env"]["GA_TUNING_RUN_ID"], "ga-20261008_160000")

    def test_memory_ack_failure_leaves_settings_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            timestamp = "20261008_160000"
            best = root / f"ga_best_parameters_{timestamp}.json"
            best.write_text(json.dumps({
                "compression": [{"parameters": {"compression_level": 4.5}, "fitness": 0.9}],
            }), encoding="utf-8")
            (root / f"ga_fitness_history_{timestamp}.json").write_text("[]", encoding="utf-8")
            (root / f"ga_summary_{timestamp}.json").write_text(json.dumps({
                "timestamp": timestamp,
                "population_size": 10,
                "generations": 2,
                "total_evaluations": 20,
            }), encoding="utf-8")
            settings = root / "settings.json"
            original = {"env": {"GA_COMPRESSION_LEVEL": "2.0", "GA_COMPRESSION_TARGET": "0.61"}}
            settings.write_text(json.dumps(original), encoding="utf-8")
            tracking = root / "evolution.md"
            extractor = ParameterExtractor(root, settings, tracking)

            with patch(
                "ga_tuning.extract_and_apply_parameters.LearningClient"
            ) as client_class:
                client_class.return_value.record_artifact.return_value = {
                    "ok": False, "memory": False, "error": "Memory unavailable"
                }
                with self.assertRaisesRegex(RuntimeError, "settings.json was not changed"):
                    extractor.run()

            self.assertEqual(json.loads(settings.read_text(encoding="utf-8")), original)
            self.assertFalse(tracking.exists())

    def test_repeated_successful_run_is_idempotent_after_settings_apply(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            timestamp = "20261008_160000"
            best = root / f"ga_best_parameters_{timestamp}.json"
            best.write_text(json.dumps({
                "compression": [{"parameters": {"compression_level": 4.5}, "fitness": 0.9}],
            }), encoding="utf-8")
            (root / f"ga_fitness_history_{timestamp}.json").write_text("[]", encoding="utf-8")
            (root / f"ga_summary_{timestamp}.json").write_text(json.dumps({
                "timestamp": timestamp,
                "population_size": 10,
                "generations": 2,
                "total_evaluations": 20,
            }), encoding="utf-8")
            settings = root / "settings.json"
            settings.write_text(json.dumps({
                "env": {"GA_COMPRESSION_LEVEL": "2.0", "GA_COMPRESSION_TARGET": "0.61"}
            }), encoding="utf-8")
            tracking = root / "evolution.md"
            extractor = ParameterExtractor(root, settings, tracking)

            with patch(
                "ga_tuning.extract_and_apply_parameters.LearningClient"
            ) as client_class:
                client_class.return_value.record_artifact.return_value = {
                    "ok": True, "memory": True, "artifact_status": "stored"
                }
                extractor.run()
                first_settings = json.loads(settings.read_text(encoding="utf-8"))
                extractor.run()
                second_settings = json.loads(settings.read_text(encoding="utf-8"))

            self.assertEqual(first_settings, second_settings)
            client_class.return_value.record_artifact.assert_called_once()
            log = tracking.read_text(encoding="utf-8")
            self.assertEqual(log.count('"run_id": "ga-20261008_160000"'), 1)

    def test_unscored_candidate_is_not_applied_or_recorded_as_selected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            best = root / "ga_best_parameters_20261008_160000.json"
            best.write_text(json.dumps({
                "compression": [
                    {"parameters": {"compression_level": 1.0}, "fitness": None},
                    {"parameters": {"compression_level": 4.5}, "fitness": 0.9},
                ],
            }), encoding="utf-8")
            extractor = ParameterExtractor(root, root / "settings.json", root / "evolution.md")
            params = extractor.extract_parameters(best)
            self.assertEqual(params, {"compression": {"compression_level": 4.5}})

            artifact = build_ga_learning_artifact(
                {"timestamp": "20261008_160000"},
                json.loads(best.read_text(encoding="utf-8")),
                {},
                best_parameters_source=best.name,
                summary_source="ga_summary_20261008_160000.json",
            )
            payload = artifact.to_dict()["payload"]
            self.assertEqual(payload["selected_parameters"]["compression"]["compression_level"], 4.5)
            self.assertEqual(payload["objectives"]["compression"], 0.9)


    def test_non_finite_candidate_parameters_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            best = root / "ga_best_parameters_20261008_160000.json"
            best.write_text(json.dumps({
                "compression": [{
                    "parameters": {"compression_level": float("nan")},
                    "fitness": 0.9,
                }],
            }), encoding="utf-8")
            extractor = ParameterExtractor(root, root / "settings.json", root / "evolution.md")
            with self.assertRaisesRegex(ValueError, "finite"):
                extractor.extract_parameters(best)

            with self.assertRaisesRegex(ValueError, "finite"):
                build_ga_learning_artifact(
                    {"timestamp": "20261008_160000"},
                    json.loads(best.read_text(encoding="utf-8")),
                    {},
                    best_parameters_source=best.name,
                    summary_source="ga_summary_20261008_160000.json",
                )

    def test_missing_or_malformed_summary_timestamp_is_rejected(self):
        for summary in ({}, {"timestamp": "not-a-ga-timestamp"}):
            with self.subTest(summary=summary):
                with self.assertRaisesRegex(ValueError, "timestamp"):
                    build_ga_learning_artifact(
                        summary,
                        {"compression": [{"parameters": {"compression_level": 4.0}, "fitness": 0.9}]},
                        {},
                        best_parameters_source="best.json",
                        summary_source="summary.json",
                    )


if __name__ == "__main__":
    unittest.main()
