"""
WORKER 4: Auto-Tuner
====================

Generates recommended configuration settings based on analyzer output.

Reads correlation report and produces:
1. Recommended config file (YAML format)
2. Config history (audit trail)
3. A/B test framework for validating changes

Enables dynamic configuration tuning per workflow type without manual intervention.

Author: Gemini
"""

import json
import yaml
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List


@dataclass
class ConfigChange:
    """Record of a configuration change."""
    timestamp: str
    workflow_type: str
    setting: str  # "compression_enabled", "compression_level", "cache_strategy", etc
    old_value: str
    new_value: str
    confidence: float
    reason: str


class ConfigTuner:
    """
    Auto-tunes configuration settings based on performance analysis.

    Reads CorrelationReport from analyzer and generates recommended config
    changes with confidence scores and rollback capabilities.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the tuner.

        Args:
            config_dir: Directory for config files. Defaults to ~/.claude/metrics
        """
        if config_dir is None:
            config_dir = Path.home() / ".claude" / "metrics"

        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def generate_config(
        self,
        analysis_report: Dict,
        current_config: Optional[Dict] = None
    ) -> Dict:
        """
        Generate recommended configuration from analysis report.

        Args:
            analysis_report: Output from PerformanceAnalyzer
            current_config: Current configuration (for comparison)

        Returns:
            Recommended configuration dictionary
        """
        if current_config is None:
            current_config = self._get_default_config()

        recommended_config = self._build_recommended_config(
            analysis_report, current_config
        )

        return recommended_config

    def _get_default_config(self) -> Dict:
        """Get default configuration."""
        return {
            "compression": {
                "default": {
                    "enabled": True,
                    "method": "hierarchical_summarizer",
                    "target_reduction": 0.35,
                    "quality_threshold": 0.10,
                },
                "by_workflow": {},
            },
            "cache": {
                "default": {
                    "enabled": True,
                    "prefer_cache_hit": True,
                    "ttl_seconds": 3600,
                },
                "by_workflow": {},
            },
        }

    def _build_recommended_config(self, analysis: Dict, current: Dict) -> Dict:
        """Build recommended config from analysis."""
        config = self._get_default_config()

        # Update default settings based on overall analysis
        if analysis.get("latency_impact"):
            latency_avg = analysis["latency_impact"].get("compression_avg_ms", 0)
            if latency_avg < 50:
                config["compression"]["default"]["target_reduction"] = 0.40
            elif latency_avg > 100:
                config["compression"]["default"]["target_reduction"] = 0.25

        # Apply per-workflow recommendations
        for workflow, comp_stats in analysis.get("compression_analysis", {}).items():
            recommendation = comp_stats.get("recommendation")
            confidence = comp_stats.get("confidence", 0)

            if confidence < 0.75:
                continue  # Only apply confident recommendations

            workflow_config = {
                "enabled": recommendation != "none",
            }

            if recommendation == "aggressive_compression":
                workflow_config.update({
                    "method": "hierarchical_summarizer",
                    "target_reduction": 0.50,
                    "quality_threshold": 0.12,
                })
            elif recommendation == "moderate_compression":
                workflow_config.update({
                    "method": "hierarchical_summarizer",
                    "target_reduction": 0.35,
                    "quality_threshold": 0.10,
                })
            elif recommendation == "light_compression":
                workflow_config.update({
                    "method": "hierarchical_summarizer",
                    "target_reduction": 0.20,
                    "quality_threshold": 0.08,
                })
            elif recommendation == "none":
                workflow_config["enabled"] = False

            if workflow_config.get("enabled"):
                config["compression"]["by_workflow"][workflow] = workflow_config

        # Apply per-workflow cache recommendations
        for workflow, cache_stats in analysis.get("cache_analysis", {}).items():
            recommendation = cache_stats.get("recommendation")
            confidence = cache_stats.get("confidence", 0)

            if confidence < 0.75:
                continue

            workflow_cache = {"enabled": recommendation != "none"}

            if recommendation == "aggressive_caching":
                workflow_cache.update({
                    "prefer_cache_hit": True,
                    "ttl_seconds": 7200,
                })
            elif recommendation == "prefer_cache_hit":
                workflow_cache.update({
                    "prefer_cache_hit": True,
                    "ttl_seconds": 3600,
                })
            elif recommendation == "light_caching":
                workflow_cache.update({
                    "prefer_cache_hit": False,
                    "ttl_seconds": 1800,
                })

            if workflow_cache.get("enabled"):
                config["cache"]["by_workflow"][workflow] = workflow_cache

        return config

    def save_config(self, config: Dict, filename: str = "recommended_config.yaml") -> Path:
        """
        Save recommended configuration to file.

        Args:
            config: Configuration dictionary
            filename: Output filename

        Returns:
            Path to saved config file
        """
        config_file = self.config_dir / filename
        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        return config_file

    def load_config(self, filename: str = "recommended_config.yaml") -> Dict:
        """Load configuration from file."""
        config_file = self.config_dir / filename
        if not config_file.exists():
            return self._get_default_config()

        with open(config_file, "r") as f:
            return yaml.safe_load(f)

    def compare_configs(self, old_config: Dict, new_config: Dict) -> List[ConfigChange]:
        """
        Compare two configurations and identify changes.

        Args:
            old_config: Current/old configuration
            new_config: Proposed/new configuration

        Returns:
            List of ConfigChange objects
        """
        changes = []

        # Compare compression settings
        old_compression = old_config.get("compression", {}).get("by_workflow", {})
        new_compression = new_config.get("compression", {}).get("by_workflow", {})

        for workflow in set(list(old_compression.keys()) + list(new_compression.keys())):
            old_wf = old_compression.get(workflow, {})
            new_wf = new_compression.get(workflow, {})

            for key in set(list(old_wf.keys()) + list(new_wf.keys())):
                old_val = old_wf.get(key, "default")
                new_val = new_wf.get(key, "default")

                if old_val != new_val:
                    changes.append(ConfigChange(
                        timestamp=datetime.utcnow().isoformat() + "Z",
                        workflow_type=workflow,
                        setting=f"compression.{key}",
                        old_value=str(old_val),
                        new_value=str(new_val),
                        confidence=0.0,  # Will be filled by caller
                        reason=f"Updated based on performance analysis"
                    ))

        # Compare cache settings
        old_cache = old_config.get("cache", {}).get("by_workflow", {})
        new_cache = new_config.get("cache", {}).get("by_workflow", {})

        for workflow in set(list(old_cache.keys()) + list(new_cache.keys())):
            old_wf = old_cache.get(workflow, {})
            new_wf = new_cache.get(workflow, {})

            for key in set(list(old_wf.keys()) + list(new_wf.keys())):
                old_val = old_wf.get(key, "default")
                new_val = new_wf.get(key, "default")

                if old_val != new_val:
                    changes.append(ConfigChange(
                        timestamp=datetime.utcnow().isoformat() + "Z",
                        workflow_type=workflow,
                        setting=f"cache.{key}",
                        old_value=str(old_val),
                        new_value=str(new_val),
                        confidence=0.0,
                        reason=f"Updated based on performance analysis"
                    ))

        return changes

    def apply_config(
        self,
        new_config: Dict,
        current_config: Optional[Dict] = None,
        min_confidence: float = 0.85
    ) -> Dict:
        """
        Apply configuration changes with confidence threshold.

        Args:
            new_config: Recommended configuration
            current_config: Current configuration (auto-loaded if not provided)
            min_confidence: Only apply changes with confidence >= this threshold

        Returns:
            Updated configuration
        """
        if current_config is None:
            current_config = self.load_config("current_config.yaml")

        # In Phase 1, we don't apply automatically - just prepare for Phase 2
        # Phase 2 will implement actual config updates with validation
        return current_config

    def save_config_history(self, changes: List[ConfigChange]) -> Path:
        """Save configuration change history."""
        history_file = self.config_dir / "config_history.jsonl"

        with open(history_file, "a") as f:
            for change in changes:
                change_dict = {
                    "timestamp": change.timestamp,
                    "workflow_type": change.workflow_type,
                    "setting": change.setting,
                    "old_value": change.old_value,
                    "new_value": change.new_value,
                    "confidence": change.confidence,
                    "reason": change.reason,
                }
                f.write(json.dumps(change_dict) + "\n")

        return history_file

    def generate_ab_test_plan(
        self,
        new_config: Dict,
        changes: List[ConfigChange]
    ) -> Dict:
        """
        Generate an A/B test plan for validating config changes.

        Args:
            new_config: Proposed configuration
            changes: List of changes

        Returns:
            A/B test plan dictionary
        """
        plan = {
            "test_id": f"config_test_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "start_time": datetime.utcnow().isoformat() + "Z",
            "duration_hours": 24,
            "variants": {
                "control": {
                    "description": "Current production config",
                    "percent_traffic": 50,
                },
                "variant": {
                    "description": "Proposed new config",
                    "percent_traffic": 50,
                    "changes": [
                        {
                            "workflow": c.workflow_type,
                            "setting": c.setting,
                            "old_value": c.old_value,
                            "new_value": c.new_value,
                            "confidence": c.confidence,
                        }
                        for c in changes
                    ],
                },
            },
            "success_criteria": {
                "cost_reduction_percent": 5,
                "quality_impact_threshold": 0.05,
                "latency_increase_percent": 10,
            },
            "rollback_conditions": [
                "Quality drops below threshold",
                "Latency increases > 10%",
                "Cost savings < 5%",
            ],
        }

        return plan


def main():
    """Demo the tuner."""
    print("Config Tuner Demo")
    print("=" * 70)

    tuner = ConfigTuner()

    # Demo: Create a sample analysis report
    sample_analysis = {
        "compression_analysis": {
            "code_review": {
                "avg_reduction_percent": 38.2,
                "quality_impact": 0.08,
                "recommendation": "light_compression",
                "confidence": 0.91,
            },
            "release_notes": {
                "avg_reduction_percent": 48.1,
                "quality_impact": 0.04,
                "recommendation": "aggressive_compression",
                "confidence": 0.87,
            },
            "security_review": {
                "avg_reduction_percent": 22.3,
                "quality_impact": 0.15,
                "recommendation": "none",
                "confidence": 0.94,
            },
        },
        "cache_analysis": {
            "deployment": {
                "cache_hit_rate": 0.72,
                "avg_tokens_saved_per_hit": 8400,
                "recommendation": "aggressive_caching",
                "confidence": 0.89,
            },
        },
        "latency_impact": {
            "compression_avg_ms": 42,
        },
    }

    # Generate recommended config
    print("\nGenerating recommended configuration...")
    recommended = tuner.generate_config(sample_analysis)
    print(f"✓ Generated config with {len(recommended['compression']['by_workflow'])} "
          f"compression rules and {len(recommended['cache']['by_workflow'])} cache rules")

    # Save config
    config_path = tuner.save_config(recommended)
    print(f"✓ Saved to {config_path}")

    # Show sample of recommended settings
    print("\nRecommended Settings Preview:")
    print("-" * 70)
    for workflow, settings in recommended.get("compression", {}).get("by_workflow", {}).items():
        print(f"  {workflow}: compression_enabled={settings.get('enabled')}, "
              f"target_reduction={settings.get('target_reduction', 'default')}")


if __name__ == "__main__":
    main()
