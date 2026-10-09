#!/usr/bin/env python3
"""
Extract GA-optimized parameters and apply to settings.json
Tracks parameter evolution over time for analysis.
"""

import json
import math
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ga_tuning.learning_artifact import build_ga_learning_artifact, scored_candidates
from learning.learning_client import LearningClient
from learning.portable_artifacts import LearningArtifact

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

    def extract_parameters(self, best_params_file: Path, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract parameters from a parsed GA result snapshot (or load one for standalone use)."""
        if data is None:
            with open(best_params_file, encoding="utf-8") as f:
                data = json.load(f)

        params = {}

        def best_candidate(system):
            # Share the exact scored-candidate selection rule with artifact creation.
            candidates = scored_candidates(data.get(system))
            if not candidates:
                return None
            candidate, _ = candidates[0]
            nested = candidate.get('parameters')
            return nested if isinstance(nested, dict) else candidate

        def available_values(system, names):
            candidate = best_candidate(system)
            if candidate is None:
                return None
            # Do not substitute hard-coded defaults for missing GA values. The
            # existing settings remain the fallback and are captured in the artifact.
            values = {}
            for name in names:
                if name not in candidate:
                    continue
                raw_value = candidate[name]
                if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                    raise ValueError(f"GA parameter {system}.{name} must be numeric")
                value = float(raw_value)
                if not math.isfinite(value):
                    raise ValueError(f"GA parameter {system}.{name} must be finite")
                values[name] = value
            return values or None

        # 1. Compression parameters
        comp = available_values('compression', ('compression_level', 'target_reduction'))
        if comp is not None:
            params['compression'] = comp

        # 2. Thompson Router parameters
        thompson = available_values('thompson', ('alpha_prior', 'beta_prior', 'cost_weight'))
        if thompson is not None:
            params['thompson'] = thompson

        # 3. Caching parameters
        caching = available_values('caching', ('ttl_seconds', 'cache_threshold'))
        if caching is not None:
            params['caching'] = caching

        # 4. Capability Matrix parameters
        matrix = available_values('matrix', ('domain_weight', 'complexity_weight', 'task_weight'))
        if matrix is not None:
            params['matrix'] = matrix

        # 5. Dashboard/Learning parameters
        dashboard = available_values('dashboard', ('learning_rate', 'exploration_decay', 'alert_threshold'))
        if dashboard is not None:
            params['dashboard'] = dashboard

        return params

    def update_settings_json(self, params: Dict[str, Any], run_id: str = None) -> None:
        """Update settings.json with new parameters"""
        with open(self.settings_json) as f:
            settings = json.load(f)

        # Update env vars with all parameters
        if 'env' not in settings:
            settings['env'] = {}
        if run_id:
            settings['env']['GA_TUNING_RUN_ID'] = run_id

        # Compression
        if 'compression' in params:
            if 'compression_level' in params['compression']:
                settings['env']['GA_COMPRESSION_LEVEL'] = str(params['compression']['compression_level'])
            if 'target_reduction' in params['compression']:
                settings['env']['GA_COMPRESSION_TARGET'] = str(params['compression']['target_reduction'])

        # Thompson Router
        if 'thompson' in params:
            if 'alpha_prior' in params['thompson']:
                settings['env']['GA_THOMPSON_ALPHA'] = str(params['thompson']['alpha_prior'])
            if 'beta_prior' in params['thompson']:
                settings['env']['GA_THOMPSON_BETA'] = str(params['thompson']['beta_prior'])
            if 'cost_weight' in params['thompson']:
                settings['env']['GA_THOMPSON_COST_WEIGHT'] = str(params['thompson']['cost_weight'])

        # Caching
        if 'caching' in params:
            if 'ttl_seconds' in params['caching']:
                settings['env']['GA_TUNING_CACHE_TTL'] = str(params['caching']['ttl_seconds'])
            if 'cache_threshold' in params['caching']:
                settings['env']['GA_TUNING_CACHE_THRESHOLD'] = str(params['caching']['cache_threshold'])

        # Matrix
        if 'matrix' in params:
            if 'domain_weight' in params['matrix']:
                settings['env']['GA_MATRIX_DOMAIN_WEIGHT'] = str(params['matrix']['domain_weight'])
            if 'complexity_weight' in params['matrix']:
                settings['env']['GA_MATRIX_COMPLEXITY_WEIGHT'] = str(params['matrix']['complexity_weight'])
            if 'task_weight' in params['matrix']:
                settings['env']['GA_MATRIX_TASK_WEIGHT'] = str(params['matrix']['task_weight'])

        # Dashboard
        if 'dashboard' in params:
            if 'learning_rate' in params['dashboard']:
                settings['env']['GA_DASHBOARD_LEARNING_RATE'] = str(params['dashboard']['learning_rate'])
            if 'exploration_decay' in params['dashboard']:
                settings['env']['GA_DASHBOARD_EXPLORATION_DECAY'] = str(params['dashboard']['exploration_decay'])
            if 'alert_threshold' in params['dashboard']:
                settings['env']['GA_DASHBOARD_ALERT_THRESHOLD'] = str(params['dashboard']['alert_threshold'])

        # Replace atomically so interruption cannot leave truncated JSON.
        original_mode = self.settings_json.stat().st_mode & 0o777
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.settings_json.parent,
                prefix=f".{self.settings_json.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(settings, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_path, original_mode)
            os.replace(temp_path, self.settings_json)
            temp_path = None
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass

    def log_parameter_evolution(self, params: Dict[str, Any], timestamp: str, run_id: str = None) -> None:
        """Log parameter changes once per GA run, including after a partial retry."""
        if run_id and self.tracking_log.exists():
            marker = json.dumps(run_id)
            if f'"run_id": {marker}' in self.tracking_log.read_text(encoding="utf-8"):
                return

        # Initialize log file if needed
        if not self.tracking_log.exists():
            self.tracking_log.write_text("# GA Parameter Evolution Log\n\n")

        # Append new entry
        entry = {
            'timestamp': timestamp,
            'run_id': run_id,
            'parameters': params
        }

        with open(self.tracking_log, 'a') as f:
            f.write(f"## {timestamp}\n\n")
            f.write("```json\n")
            f.write(json.dumps(entry, indent=2))
            f.write("\n```\n\n")

    def run(self) -> None:
        """Extract, acknowledge, apply, and log one immutable GA result snapshot."""
        try:
            best_params_file, _ = self.get_latest_results()
            timestamp = datetime.utcnow().isoformat()

            # Read the optimizer result exactly once. Parameter application and
            # artifact provenance must describe this same immutable in-memory snapshot.
            best_by_system = json.loads(best_params_file.read_text(encoding="utf-8"))
            params = self.extract_parameters(best_params_file, data=best_by_system)
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
            artifact = build_ga_learning_artifact(
                summary,
                best_by_system,
                fallback_parameters,
                best_parameters_source=best_params_file.name,
                summary_source=summary_file.name,
            )

            run_id = artifact.payload["run_id"]
            pending_artifact = self.results_dir / f".{run_id}.learning-artifact.json"
            # The artifact's run identity intentionally excludes mutable fallbacks.
            # Persist the first submitted payload and reuse it until application and
            # logging complete, so a retry cannot reconstruct different content.
            if pending_artifact.exists():
                artifact = LearningArtifact.from_json(
                    pending_artifact.read_text(encoding="utf-8")
                )
                if artifact.payload.get("run_id") != run_id:
                    raise RuntimeError(f"Pending GA artifact does not match run ID {run_id}")
            else:
                temp_path = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="w",
                        encoding="utf-8",
                        dir=self.results_dir,
                        prefix=f".{run_id}.",
                        suffix=".tmp",
                        delete=False,
                    ) as handle:
                        temp_path = Path(handle.name)
                        handle.write(artifact.to_json() + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temp_path, pending_artifact)
                    temp_path = None
                finally:
                    if temp_path is not None:
                        try:
                            temp_path.unlink()
                        except FileNotFoundError:
                            pass

            if current_settings.get("env", {}).get("GA_TUNING_RUN_ID") == run_id:
                # The acknowledgement and settings update already completed. Repair
                # a missing evolution log, then discard the retry snapshot.
                self.log_parameter_evolution(params, timestamp, run_id=run_id)
                pending_artifact.unlink(missing_ok=True)
                print(f"GA run {run_id} was already applied; skipping duplicate ingestion.")
                return

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

            print("Extracted GA parameters:")
            print(json.dumps(params, indent=2))

            # Update settings.json only after the Learning service confirms Memory.
            self.update_settings_json(params, run_id=run_id)
            print(f"\n✓ Updated {self.settings_json}")

            self.log_parameter_evolution(params, timestamp, run_id=run_id)
            pending_artifact.unlink(missing_ok=True)
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
