#!/usr/bin/env python3
"""
Extract GA-optimized parameters and apply to settings.json
Tracks parameter evolution over time for analysis.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ga_tuning.learning_artifact import build_ga_learning_artifact
from learning.learning_client import LearningClient

class ParameterExtractor:
    def __init__(self, results_dir: Path, settings_json: Path, tracking_log: Path):
        self.results_dir = Path(results_dir)
        self.settings_json = Path(settings_json)
        self.tracking_log = Path(tracking_log)
        self.tracking_log.parent.mkdir(parents=True, exist_ok=True)

    def get_latest_results(self) -> Tuple[Path, Path]:
        """Get latest GA results files"""
        best_params_files = sorted(
            self.results_dir.glob("ga_best_parameters_*.json"),
            reverse=True
        )
        fitness_files = sorted(
            self.results_dir.glob("ga_fitness_history_*.json"),
            reverse=True
        )

        if not best_params_files or not fitness_files:
            raise FileNotFoundError("No GA results found")

        return best_params_files[0], fitness_files[0]

    def extract_parameters(self, best_params_file: Path) -> Dict[str, Any]:
        """Extract parameters for all 5 tools from GA results"""
        with open(best_params_file) as f:
            data = json.load(f)

        params = {}

        def best_candidate(system):
            candidates = data.get(system)
            if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
                return None
            candidate = candidates[0]
            nested = candidate.get('parameters')
            return nested if isinstance(nested, dict) else candidate

        # 1. Compression parameters
        comp = best_candidate('compression')
        if comp is not None:
            params['compression'] = {
                'compression_level': float(comp.get('compression_level', 3)),
                'target_reduction': float(comp.get('target_reduction', 0.35))
            }

        # 2. Thompson Router parameters
        thompson = best_candidate('thompson')
        if thompson is not None:
            params['thompson'] = {
                'alpha_prior': float(thompson.get('alpha_prior', 2.0)),
                'beta_prior': float(thompson.get('beta_prior', 1.0)),
                'cost_weight': float(thompson.get('cost_weight', 0.25))
            }

        # 3. Caching parameters
        caching = best_candidate('caching')
        if caching is not None:
            params['caching'] = {
                'ttl_seconds': float(caching.get('ttl_seconds', 246.87)),
                'cache_threshold': float(caching.get('cache_threshold', 0.44))
            }

        # 4. Capability Matrix parameters
        matrix = best_candidate('matrix')
        if matrix is not None:
            params['matrix'] = {
                'domain_weight': float(matrix.get('domain_weight', 0.3)),
                'complexity_weight': float(matrix.get('complexity_weight', 0.4)),
                'task_weight': float(matrix.get('task_weight', 0.3))
            }

        # 5. Dashboard/Learning parameters
        dashboard = best_candidate('dashboard')
        if dashboard is not None:
            params['dashboard'] = {
                'learning_rate': float(dashboard.get('learning_rate', 0.05)),
                'exploration_decay': float(dashboard.get('exploration_decay', 0.95)),
                'alert_threshold': float(dashboard.get('alert_threshold', 0.7))
            }

        return params

    def update_settings_json(self, params: Dict[str, Any]) -> None:
        """Update settings.json with new parameters"""
        with open(self.settings_json) as f:
            settings = json.load(f)

        # Update env vars with all parameters
        if 'env' not in settings:
            settings['env'] = {}

        # Compression
        if 'compression' in params:
            settings['env']['GA_COMPRESSION_LEVEL'] = str(params['compression']['compression_level'])
            settings['env']['GA_COMPRESSION_TARGET'] = str(params['compression']['target_reduction'])

        # Thompson Router
        if 'thompson' in params:
            settings['env']['GA_THOMPSON_ALPHA'] = str(params['thompson']['alpha_prior'])
            settings['env']['GA_THOMPSON_BETA'] = str(params['thompson']['beta_prior'])
            settings['env']['GA_THOMPSON_COST_WEIGHT'] = str(params['thompson']['cost_weight'])

        # Caching
        if 'caching' in params:
            settings['env']['GA_TUNING_CACHE_TTL'] = str(params['caching']['ttl_seconds'])
            settings['env']['GA_TUNING_CACHE_THRESHOLD'] = str(params['caching']['cache_threshold'])

        # Matrix
        if 'matrix' in params:
            settings['env']['GA_MATRIX_DOMAIN_WEIGHT'] = str(params['matrix']['domain_weight'])
            settings['env']['GA_MATRIX_COMPLEXITY_WEIGHT'] = str(params['matrix']['complexity_weight'])
            settings['env']['GA_MATRIX_TASK_WEIGHT'] = str(params['matrix']['task_weight'])

        # Dashboard
        if 'dashboard' in params:
            settings['env']['GA_DASHBOARD_LEARNING_RATE'] = str(params['dashboard']['learning_rate'])
            settings['env']['GA_DASHBOARD_EXPLORATION_DECAY'] = str(params['dashboard']['exploration_decay'])
            settings['env']['GA_DASHBOARD_ALERT_THRESHOLD'] = str(params['dashboard']['alert_threshold'])

        # Write back
        with open(self.settings_json, 'w') as f:
            json.dump(settings, f, indent=2)

    def log_parameter_evolution(self, params: Dict[str, Any], timestamp: str) -> None:
        """Log parameter changes over time for tracking evolution"""

        # Initialize log file if needed
        if not self.tracking_log.exists():
            self.tracking_log.write_text("# GA Parameter Evolution Log\n\n")

        # Append new entry
        entry = {
            'timestamp': timestamp,
            'parameters': params
        }

        with open(self.tracking_log, 'a') as f:
            f.write(f"## {timestamp}\n\n")
            f.write("```json\n")
            f.write(json.dumps(params, indent=2))
            f.write("\n```\n\n")

    def run(self) -> None:
        """Extract, update, and log parameters"""
        try:
            # Get latest results
            best_params_file, _ = self.get_latest_results()
            timestamp = datetime.utcnow().isoformat()

            # Extract parameters and preserve the current values as explicit fallbacks.
            params = self.extract_parameters(best_params_file)
            with self.settings_json.open(encoding="utf-8") as handle:
                current_settings = json.load(handle)
            fallback_parameters = {
                key: value for key, value in current_settings.get("env", {}).items()
                if key.startswith("GA_")
            }
            summary_file = best_params_file.with_name(
                best_params_file.name.replace("ga_best_parameters_", "ga_summary_", 1)
            )
            if not summary_file.is_file():
                raise FileNotFoundError(f"GA summary not found for run: {best_params_file.name}")
            with summary_file.open(encoding="utf-8") as handle:
                summary = json.load(handle)
            best_by_system = json.loads(best_params_file.read_text(encoding="utf-8"))
            artifact = build_ga_learning_artifact(
                summary,
                best_by_system,
                fallback_parameters,
                best_parameters_source=best_params_file.name,
                summary_source=summary_file.name,
            )

            print("Created GA learning artifact:")
            print(artifact.to_json())

            # Canonical Learning service must acknowledge Memory persistence before
            # this run is allowed to alter settings.json.
            learning = LearningClient()
            response = learning.record_artifact(artifact.to_dict())
            if not response.get("ok") or not response.get("memory"):
                raise RuntimeError(
                    "Learning service did not durably acknowledge the GA artifact; "
                    "settings.json was not changed: " + str(response.get("error", response))
                )

            print(f"Extracted GA parameters:")
            print(json.dumps(params, indent=2))

            # Update settings.json only after the Learning service confirms Memory.
            self.update_settings_json(params)
            print(f"\n✓ Updated {self.settings_json}")

            # Log evolution
            self.log_parameter_evolution(params, timestamp)
            print(f"✓ Logged parameter evolution to {self.tracking_log}")

        except Exception as e:
            print(f"✗ Error: {e}")
            raise


if __name__ == '__main__':
    import sys

    rh_tools_root = Path(os.environ.get('RH_TOOLS_ROOT',
                         Path.home() / 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills'))

    results_dir = rh_tools_root / 'ga_tuning' / 'results'
    settings_json = rh_tools_root / 'settings.json'
    tracking_log = rh_tools_root / 'ga_tuning' / 'parameter_evolution.md'

    extractor = ParameterExtractor(results_dir, settings_json, tracking_log)
    extractor.run()
