"""Tests for GA learning artifact construction and provenance."""
import unittest

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


if __name__ == "__main__":
    unittest.main()
