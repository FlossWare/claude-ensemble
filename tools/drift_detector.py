#!/usr/bin/env python3
"""
Model Drift Detection System

Detects statistical drift in model performance over time using:
1. Cumulative Sum (CUSUM) for detecting mean shifts
2. Page-Hinkley Test for abrupt changes
3. ADWIN (Adaptive Windowing) for concept drift
4. Kolmogorov-Smirnov test for distribution changes

Integrates with:
- workflow.executions: Performance metrics over time
- workflow.worker_results: Per-model quality tracking
- workflow.arbiter_decisions: Consensus quality tracking

Usage:
    python3 tools/drift_detector.py [--model opus] [--days 30] [--save-report]
    python3 tools/drift_detector.py --continuous --check-interval 3600

What it detects:
1. Performance degradation (quality score drift)
2. Confidence calibration drift
3. Cost efficiency changes
4. Task-specific model drift

Created: 2026-07-03
"""

import sys
import json
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from scipy import stats
from collections import deque, defaultdict
import psycopg2
import psycopg2.extras
import time

# Configuration
DB_CONFIG = {
    'host': 'aio-01',
    'port': 5433,
    'database': 'learning',
    'user': 'sfloess'
}

DRIFT_THRESHOLDS = {
    'cusum_threshold': 5.0,          # CUSUM threshold for change detection
    'page_hinkley_threshold': 10.0,  # Page-Hinkley threshold
    'page_hinkley_delta': 0.005,     # Minimum magnitude of change to detect
    'ks_test_alpha': 0.05,           # Significance level for KS test
    'min_samples': 30,               # Minimum samples for drift detection
    'quality_drop_threshold': 0.1,   # 10% quality drop triggers alert
    'cost_increase_threshold': 0.2   # 20% cost increase triggers alert
}

# Output paths
OUTPUT_DIR = Path.home() / '.claude' / 'learning' / 'drift_reports'
LATEST_REPORT = OUTPUT_DIR / 'latest_drift_report.json'
DRIFT_LOG = OUTPUT_DIR / 'drift_detection_log.jsonl'


class CUSUMDetector:
    """
    Cumulative Sum (CUSUM) drift detector
    Detects shifts in the mean of a time series
    """
    def __init__(self, threshold=5.0, drift_threshold=0.0):
        self.threshold = threshold
        self.drift_threshold = drift_threshold
        self.cumsum_pos = 0.0
        self.cumsum_neg = 0.0
        self.mean = None
        self.std = None
        self.values = []

    def update(self, value):
        """Update CUSUM with new value"""
        self.values.append(value)

        # Calculate baseline statistics
        if len(self.values) < 10:
            return False, 0.0

        if self.mean is None:
            self.mean = np.mean(self.values[:10])
            self.std = np.std(self.values[:10])
            if self.std == 0:
                self.std = 1.0

        # Standardized value
        z = (value - self.mean) / self.std

        # Update CUSUM
        self.cumsum_pos = max(0, self.cumsum_pos + z - self.drift_threshold)
        self.cumsum_neg = max(0, self.cumsum_neg - z - self.drift_threshold)

        # Check for drift
        drift_detected = (self.cumsum_pos > self.threshold or
                         self.cumsum_neg > self.threshold)

        drift_magnitude = max(self.cumsum_pos, self.cumsum_neg)

        return drift_detected, drift_magnitude

    def reset(self):
        """Reset detector after drift"""
        self.cumsum_pos = 0.0
        self.cumsum_neg = 0.0
        self.mean = np.mean(self.values[-10:]) if len(self.values) >= 10 else self.mean
        self.std = np.std(self.values[-10:]) if len(self.values) >= 10 else self.std


class PageHinkleyDetector:
    """
    Page-Hinkley test for abrupt changes
    More sensitive to sudden shifts than CUSUM
    """
    def __init__(self, threshold=10.0, delta=0.005):
        self.threshold = threshold
        self.delta = delta
        self.sum = 0.0
        self.min_sum = 0.0
        self.values = []

    def update(self, value):
        """Update Page-Hinkley test with new value"""
        self.values.append(value)

        if len(self.values) < 2:
            return False, 0.0

        # Update sum
        mean_t = np.mean(self.values)
        self.sum += value - mean_t - self.delta

        # Track minimum
        if self.sum < self.min_sum:
            self.min_sum = self.sum

        # Check for drift
        drift_magnitude = self.sum - self.min_sum
        drift_detected = drift_magnitude > self.threshold

        return drift_detected, drift_magnitude

    def reset(self):
        """Reset detector after drift"""
        self.sum = 0.0
        self.min_sum = 0.0


class ADWINDetector:
    """
    Adaptive Windowing (ADWIN) for concept drift
    Automatically adjusts window size based on detected changes
    """
    def __init__(self, delta=0.002):
        self.delta = delta
        self.window = deque(maxlen=1000)
        self.total = 0.0
        self.variance = 0.0
        self.width = 0

    def update(self, value):
        """Update ADWIN with new value"""
        self.window.append(value)
        self.width = len(self.window)

        if self.width < 2:
            return False, 0.0

        # Calculate statistics
        self.total = sum(self.window)
        mean = self.total / self.width
        self.variance = sum((x - mean) ** 2 for x in self.window) / self.width

        # Check for drift using sliding window approach
        # Split window and compare distributions
        drift_detected = False
        drift_magnitude = 0.0

        if self.width >= 10:
            # Compare recent vs older data
            split_point = self.width // 2
            recent = list(self.window)[split_point:]
            older = list(self.window)[:split_point]

            if len(recent) > 0 and len(older) > 0:
                mean_recent = np.mean(recent)
                mean_older = np.mean(older)

                # Calculate epsilon cut (change threshold)
                m = 1.0 / len(recent) + 1.0 / len(older)
                epsilon_cut = np.sqrt(2 * m * self.variance * np.log(2.0 / self.delta))

                drift_magnitude = abs(mean_recent - mean_older)
                drift_detected = drift_magnitude > epsilon_cut

        return drift_detected, drift_magnitude

    def reset(self):
        """Reset detector after drift"""
        # Keep only recent window
        if len(self.window) > 10:
            self.window = deque(list(self.window)[-10:], maxlen=1000)


class DriftDetectionSystem:
    """
    Comprehensive drift detection system integrating multiple detectors
    """
    def __init__(self, db_config=None):
        self.db_config = db_config or DB_CONFIG
        self.conn = None

        # Detectors per model
        self.detectors = defaultdict(lambda: {
            'quality_cusum': CUSUMDetector(threshold=DRIFT_THRESHOLDS['cusum_threshold']),
            'quality_ph': PageHinkleyDetector(
                threshold=DRIFT_THRESHOLDS['page_hinkley_threshold'],
                delta=DRIFT_THRESHOLDS['page_hinkley_delta']
            ),
            'quality_adwin': ADWINDetector(),
            'confidence_cusum': CUSUMDetector(threshold=DRIFT_THRESHOLDS['cusum_threshold']),
            'cost_cusum': CUSUMDetector(threshold=DRIFT_THRESHOLDS['cusum_threshold'])
        })

        # Drift events log
        self.drift_events = []

    def connect(self):
        """Connect to PostgreSQL"""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(**self.db_config)

    def close(self):
        """Close database connection"""
        if self.conn and not self.conn.closed:
            self.conn.close()

    def fetch_model_timeseries(self, model=None, days=30, min_samples=None):
        """
        Fetch time-series data for model performance

        Returns: List of (timestamp, quality, confidence, cost) tuples
        """
        self.connect()
        min_samples = min_samples or DRIFT_THRESHOLDS['min_samples']

        query = """
            SELECT
                DATE_TRUNC('hour', created_at) as time_bucket,
                model,
                AVG(quality_score) as avg_quality,
                AVG(confidence) as avg_confidence,
                AVG(cost_usd) as avg_cost,
                COUNT(*) as sample_count
            FROM workflow.worker_results
            WHERE created_at > NOW() - INTERVAL '%s days'
                AND quality_score IS NOT NULL
                AND confidence IS NOT NULL
        """

        params = [days]

        if model:
            query += " AND model = %s"
            params.append(model)

        query += """
            GROUP BY DATE_TRUNC('hour', created_at), model
            HAVING COUNT(*) >= %s
            ORDER BY time_bucket ASC
        """
        params.append(min_samples)

        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()

        # Group by model
        timeseries_by_model = defaultdict(list)
        for row in results:
            timeseries_by_model[row['model']].append({
                'timestamp': row['time_bucket'],
                'quality': float(row['avg_quality']),
                'confidence': float(row['avg_confidence']),
                'cost': float(row['avg_cost']),
                'samples': int(row['sample_count'])
            })

        return timeseries_by_model

    def detect_drift(self, timeseries_data, model_name):
        """
        Run drift detection on time-series data

        Returns: {
            'drift_detected': bool,
            'drift_type': str,
            'drift_magnitude': float,
            'affected_metrics': list,
            'details': dict
        }
        """
        if len(timeseries_data) < DRIFT_THRESHOLDS['min_samples']:
            return {
                'drift_detected': False,
                'reason': f'Insufficient samples ({len(timeseries_data)} < {DRIFT_THRESHOLDS["min_samples"]})'
            }

        detectors = self.detectors[model_name]
        drift_signals = []

        # Extract metrics
        qualities = [d['quality'] for d in timeseries_data]
        confidences = [d['confidence'] for d in timeseries_data]
        costs = [d['cost'] for d in timeseries_data]

        # Quality drift detection
        for i, quality in enumerate(qualities):
            cusum_drift, cusum_mag = detectors['quality_cusum'].update(quality)
            ph_drift, ph_mag = detectors['quality_ph'].update(quality)
            adwin_drift, adwin_mag = detectors['quality_adwin'].update(quality)

            if cusum_drift:
                drift_signals.append({
                    'detector': 'CUSUM',
                    'metric': 'quality',
                    'index': i,
                    'magnitude': cusum_mag,
                    'value': quality
                })
                detectors['quality_cusum'].reset()

            if ph_drift:
                drift_signals.append({
                    'detector': 'Page-Hinkley',
                    'metric': 'quality',
                    'index': i,
                    'magnitude': ph_mag,
                    'value': quality
                })
                detectors['quality_ph'].reset()

            if adwin_drift:
                drift_signals.append({
                    'detector': 'ADWIN',
                    'metric': 'quality',
                    'index': i,
                    'magnitude': adwin_mag,
                    'value': quality
                })
                detectors['quality_adwin'].reset()

        # Confidence drift detection
        for i, confidence in enumerate(confidences):
            cusum_drift, cusum_mag = detectors['confidence_cusum'].update(confidence)
            if cusum_drift:
                drift_signals.append({
                    'detector': 'CUSUM',
                    'metric': 'confidence',
                    'index': i,
                    'magnitude': cusum_mag,
                    'value': confidence
                })
                detectors['confidence_cusum'].reset()

        # Cost drift detection
        for i, cost in enumerate(costs):
            cusum_drift, cusum_mag = detectors['cost_cusum'].update(cost)
            if cusum_drift:
                drift_signals.append({
                    'detector': 'CUSUM',
                    'metric': 'cost',
                    'index': i,
                    'magnitude': cusum_mag,
                    'value': cost
                })
                detectors['cost_cusum'].reset()

        # Distribution change detection (KS test)
        distribution_changes = self._detect_distribution_drift(qualities, confidences, costs)

        # Aggregate results
        drift_detected = len(drift_signals) > 0 or distribution_changes['drift_detected']

        if drift_detected:
            # Determine drift type
            quality_drifts = [s for s in drift_signals if s['metric'] == 'quality']
            confidence_drifts = [s for s in drift_signals if s['metric'] == 'confidence']
            cost_drifts = [s for s in drift_signals if s['metric'] == 'cost']

            if quality_drifts:
                drift_type = 'performance_degradation'
            elif confidence_drifts:
                drift_type = 'confidence_miscalibration'
            elif cost_drifts:
                drift_type = 'cost_efficiency_change'
            else:
                drift_type = 'distribution_shift'

            affected_metrics = list(set(s['metric'] for s in drift_signals))

            return {
                'drift_detected': True,
                'drift_type': drift_type,
                'affected_metrics': affected_metrics,
                'signal_count': len(drift_signals),
                'drift_signals': drift_signals,
                'distribution_changes': distribution_changes,
                'severity': self._calculate_severity(drift_signals, distribution_changes)
            }
        else:
            return {
                'drift_detected': False,
                'reason': 'No significant drift detected'
            }

    def _detect_distribution_drift(self, qualities, confidences, costs):
        """
        Detect distribution changes using Kolmogorov-Smirnov test
        Compares recent vs historical distributions
        """
        results = {
            'drift_detected': False,
            'quality_ks': None,
            'confidence_ks': None,
            'cost_ks': None
        }

        if len(qualities) < 20:
            return results

        # Split into historical (first 60%) and recent (last 40%)
        split_point = int(len(qualities) * 0.6)

        # Quality distribution
        hist_quality = qualities[:split_point]
        recent_quality = qualities[split_point:]
        ks_stat_q, p_value_q = stats.ks_2samp(hist_quality, recent_quality)
        results['quality_ks'] = {
            'statistic': float(ks_stat_q),
            'p_value': float(p_value_q),
            'drift': p_value_q < DRIFT_THRESHOLDS['ks_test_alpha']
        }

        # Confidence distribution
        hist_conf = confidences[:split_point]
        recent_conf = confidences[split_point:]
        ks_stat_c, p_value_c = stats.ks_2samp(hist_conf, recent_conf)
        results['confidence_ks'] = {
            'statistic': float(ks_stat_c),
            'p_value': float(p_value_c),
            'drift': p_value_c < DRIFT_THRESHOLDS['ks_test_alpha']
        }

        # Cost distribution
        hist_cost = costs[:split_point]
        recent_cost = costs[split_point:]
        ks_stat_cost, p_value_cost = stats.ks_2samp(hist_cost, recent_cost)
        results['cost_ks'] = {
            'statistic': float(ks_stat_cost),
            'p_value': float(p_value_cost),
            'drift': p_value_cost < DRIFT_THRESHOLDS['ks_test_alpha']
        }

        results['drift_detected'] = (
            results['quality_ks']['drift'] or
            results['confidence_ks']['drift'] or
            results['cost_ks']['drift']
        )

        return results

    def _calculate_severity(self, drift_signals, distribution_changes):
        """
        Calculate drift severity (low, medium, high, critical)

        Factors:
        - Number of detectors agreeing
        - Magnitude of drift
        - Multiple metrics affected
        - Statistical significance
        """
        severity_score = 0

        # Signal count (max 3 points)
        severity_score += min(len(drift_signals) / 3, 3)

        # Multiple detectors on same metric (2 points)
        metrics = [s['metric'] for s in drift_signals]
        if len(set(metrics)) < len(metrics):
            severity_score += 2

        # High magnitude drift (3 points)
        max_magnitude = max([s['magnitude'] for s in drift_signals], default=0)
        if max_magnitude > DRIFT_THRESHOLDS['cusum_threshold'] * 2:
            severity_score += 3

        # Distribution shift (2 points)
        if distribution_changes.get('drift_detected'):
            severity_score += 2

        # Quality impact (4 points for quality drift)
        quality_signals = [s for s in drift_signals if s['metric'] == 'quality']
        if quality_signals:
            severity_score += 4

        # Classify severity
        if severity_score >= 10:
            return 'CRITICAL'
        elif severity_score >= 7:
            return 'HIGH'
        elif severity_score >= 4:
            return 'MEDIUM'
        else:
            return 'LOW'

    def analyze_all_models(self, days=30):
        """
        Analyze drift for all models with sufficient data

        Returns: {
            model_name: drift_analysis
        }
        """
        timeseries_by_model = self.fetch_model_timeseries(days=days)

        results = {}
        for model_name, timeseries in timeseries_by_model.items():
            print(f"\n=== Analyzing {model_name} ({len(timeseries)} time buckets) ===")

            drift_analysis = self.detect_drift(timeseries, model_name)
            drift_analysis['model'] = model_name
            drift_analysis['sample_count'] = len(timeseries)
            drift_analysis['time_range'] = {
                'start': timeseries[0]['timestamp'].isoformat() if timeseries else None,
                'end': timeseries[-1]['timestamp'].isoformat() if timeseries else None
            }

            results[model_name] = drift_analysis

            # Print summary
            if drift_analysis.get('drift_detected'):
                severity = drift_analysis.get('severity', 'UNKNOWN')
                drift_type = drift_analysis.get('drift_type', 'unknown')
                affected = drift_analysis.get('affected_metrics', [])

                print(f"  ⚠ DRIFT DETECTED: {drift_type}")
                print(f"  Severity: {severity}")
                print(f"  Affected metrics: {', '.join(affected)}")
                print(f"  Signal count: {drift_analysis.get('signal_count', 0)}")
            else:
                print(f"  ✓ No significant drift")

        return results

    def generate_report(self, results, output_path=None):
        """
        Generate comprehensive drift detection report
        """
        output_path = output_path or LATEST_REPORT

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        report = {
            'timestamp': datetime.now().isoformat(),
            'models_analyzed': len(results),
            'drift_detected': any(r.get('drift_detected') for r in results.values()),
            'models': results,
            'summary': {
                'total_models': len(results),
                'models_with_drift': sum(1 for r in results.values() if r.get('drift_detected')),
                'severity_breakdown': self._summarize_severity(results)
            }
        }

        # Save report
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\n✓ Report saved to: {output_path}")

        # Append to log
        self._append_to_log(report)

        return report

    def _summarize_severity(self, results):
        """Summarize severity distribution"""
        severity_counts = defaultdict(int)
        for result in results.values():
            if result.get('drift_detected'):
                severity = result.get('severity', 'UNKNOWN')
                severity_counts[severity] += 1
        return dict(severity_counts)

    def _append_to_log(self, report):
        """Append report summary to drift log (JSONL)"""
        DRIFT_LOG.parent.mkdir(parents=True, exist_ok=True)

        log_entry = {
            'timestamp': report['timestamp'],
            'drift_detected': report['drift_detected'],
            'models_with_drift': report['summary']['models_with_drift'],
            'severity_breakdown': report['summary']['severity_breakdown']
        }

        with open(DRIFT_LOG, 'a') as f:
            f.write(json.dumps(log_entry, default=str) + '\n')

    def continuous_monitoring(self, check_interval=3600, days=7):
        """
        Continuous drift monitoring (for production deployment)

        Args:
            check_interval: Seconds between checks (default 1 hour)
            days: Days of historical data to analyze
        """
        print(f"Starting continuous drift monitoring (check every {check_interval}s)")
        print(f"Analyzing last {days} days of data")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                print(f"\n{'='*60}")
                print(f"Drift Check: {datetime.now().isoformat()}")
                print(f"{'='*60}")

                results = self.analyze_all_models(days=days)
                report = self.generate_report(results)

                # Alert on critical drift
                critical_models = [
                    model for model, result in results.items()
                    if result.get('severity') == 'CRITICAL'
                ]

                if critical_models:
                    print(f"\n🚨 CRITICAL DRIFT ALERT: {', '.join(critical_models)}")
                    print("Immediate investigation recommended!")

                print(f"\nNext check in {check_interval}s...")
                time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\n\nStopping continuous monitoring...")
        finally:
            self.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Model Drift Detection System')
    parser.add_argument('--model', type=str, help='Specific model to analyze')
    parser.add_argument('--days', type=int, default=30, help='Days of historical data')
    parser.add_argument('--save-report', action='store_true', help='Save detailed report')
    parser.add_argument('--continuous', action='store_true', help='Continuous monitoring mode')
    parser.add_argument('--check-interval', type=int, default=3600,
                       help='Seconds between checks (continuous mode)')

    args = parser.parse_args()

    detector = DriftDetectionSystem()

    try:
        if args.continuous:
            detector.continuous_monitoring(
                check_interval=args.check_interval,
                days=args.days
            )
        else:
            print("=" * 60)
            print("MODEL DRIFT DETECTION SYSTEM")
            print("=" * 60)

            if args.model:
                print(f"Analyzing model: {args.model}")
                timeseries = detector.fetch_model_timeseries(
                    model=args.model,
                    days=args.days
                )
                if args.model not in timeseries:
                    print(f"No data found for model: {args.model}")
                    return 1

                result = detector.detect_drift(timeseries[args.model], args.model)
                results = {args.model: result}
            else:
                print(f"Analyzing all models (last {args.days} days)")
                results = detector.analyze_all_models(days=args.days)

            if args.save_report:
                detector.generate_report(results)
            else:
                # Print summary
                print("\n" + "=" * 60)
                print("DRIFT DETECTION SUMMARY")
                print("=" * 60)

                drift_count = sum(1 for r in results.values() if r.get('drift_detected'))
                print(f"Models analyzed: {len(results)}")
                print(f"Models with drift: {drift_count}")

                if drift_count > 0:
                    print("\nDrift details:")
                    for model, result in results.items():
                        if result.get('drift_detected'):
                            print(f"\n  {model}:")
                            print(f"    Type: {result.get('drift_type')}")
                            print(f"    Severity: {result.get('severity')}")
                            print(f"    Affected: {', '.join(result.get('affected_metrics', []))}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        detector.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
