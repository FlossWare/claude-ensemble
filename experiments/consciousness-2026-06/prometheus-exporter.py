#!/usr/bin/env python3
"""Prometheus Metrics Exporter"""
from collections import defaultdict

class PrometheusExporter:
    def __init__(self, port=9100):
        self.port = port
        self.metrics = {}

    def register_gauge(self, name, help_text, labels=None):
        """Register a gauge metric"""
        self.metrics[name] = {
            'type': 'gauge',
            'value': {},
            'help': help_text,
            'labels': labels or []
        }

    def register_counter(self, name, help_text, labels=None):
        """Register a counter metric"""
        self.metrics[name] = {
            'type': 'counter',
            'value': defaultdict(float),
            'help': help_text,
            'labels': labels or []
        }

    def register_histogram(self, name, help_text, labels=None, buckets=None):
        """Register a histogram metric"""
        if buckets is None:
            buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self.metrics[name] = {
            'type': 'histogram',
            'buckets': buckets,
            'values': defaultdict(list),
            'help': help_text,
            'labels': labels or []
        }

    def set_gauge(self, name, value, labels=None):
        """Set gauge value"""
        if name in self.metrics:
            label_key = self._label_key(labels or {})
            self.metrics[name]['value'][label_key] = value

    def inc_counter(self, name, labels=None, amount=1):
        """Increment counter"""
        if name in self.metrics:
            label_key = self._label_key(labels or {})
            self.metrics[name]['value'][label_key] += amount

    def observe_histogram(self, name, value, labels=None):
        """Record histogram observation"""
        if name in self.metrics:
            label_key = self._label_key(labels or {})
            self.metrics[name]['values'][label_key].append(value)

    def _label_key(self, labels_dict):
        """Convert labels dict to sorted tuple for consistent keys"""
        return tuple(sorted(labels_dict.items()))

    def _format_labels(self, label_key):
        """Format labels for Prometheus output"""
        if not label_key:
            return ""
        parts = [f'{k}="{v}"' for k, v in label_key]
        return '{' + ','.join(parts) + '}'

    def _compute_histogram_buckets(self, values, buckets):
        """Compute histogram bucket counts"""
        bucket_counts = {b: 0 for b in buckets}
        bucket_counts['+Inf'] = 0

        for value in values:
            for bucket in buckets:
                if value <= bucket:
                    bucket_counts[bucket] += 1
            bucket_counts['+Inf'] += 1

        total = sum(values)
        count = len(values)

        return bucket_counts, total, count

    def export_metrics(self):
        """Export in Prometheus format"""
        lines = []

        for name, metric in self.metrics.items():
            lines.append(f"# HELP {name} {metric['help']}")
            lines.append(f"# TYPE {name} {metric['type']}")

            if metric['type'] == 'gauge':
                for label_key, value in metric['value'].items():
                    labels_str = self._format_labels(label_key)
                    lines.append(f"{name}{labels_str} {value}")

            elif metric['type'] == 'counter':
                for label_key, value in metric['value'].items():
                    labels_str = self._format_labels(label_key)
                    lines.append(f"{name}{labels_str} {value}")

            elif metric['type'] == 'histogram':
                for label_key, values in metric['values'].items():
                    if not values:
                        continue

                    labels_str = self._format_labels(label_key)
                    bucket_counts, total, count = self._compute_histogram_buckets(
                        values, metric['buckets']
                    )

                    # Emit buckets
                    cumulative = 0
                    for bucket in sorted(metric['buckets']):
                        cumulative += bucket_counts[bucket]
                        bucket_label = f'{labels_str[:-1]},le="{bucket}"}}' if labels_str else f'{{le="{bucket}"}}'
                        lines.append(f"{name}_bucket{bucket_label} {cumulative}")

                    # +Inf bucket
                    inf_label = f'{labels_str[:-1]},le="+Inf"}}' if labels_str else '{le="+Inf"}'
                    lines.append(f"{name}_bucket{inf_label} {count}")

                    # _sum and _count
                    lines.append(f"{name}_sum{labels_str} {total}")
                    lines.append(f"{name}_count{labels_str} {count}")

        return '\n'.join(lines)

if __name__ == '__main__':
    exporter = PrometheusExporter()

    # Consciousness metrics (existing)
    exporter.register_gauge('consciousness_phi', 'IIT Phi value')
    exporter.set_gauge('consciousness_phi', 4.2)

    # Workflow completion metrics
    exporter.register_counter(
        'workflow_completions_total',
        'Total number of workflow executions partitioned by workflow name and outcome (success, failed, error)',
        labels=['workflow', 'outcome']
    )

    exporter.register_histogram(
        'workflow_duration_seconds',
        'Wall-clock duration of workflow executions in seconds. Default buckets: 1, 5, 15, 30, 60, 120, 300, 600, 1800',
        labels=['workflow'],
        buckets=[1, 5, 15, 30, 60, 120, 300, 600, 1800]
    )

    # Worker output metrics
    exporter.register_counter(
        'worker_outputs_total',
        'Total number of worker outputs produced, partitioned by parent workflow, model, and outcome (success, failed, error)',
        labels=['workflow', 'model', 'outcome']
    )

    exporter.register_histogram(
        'worker_quality_score',
        'Distribution of worker output quality scores (0.0 to 1.0). Default buckets: 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0',
        labels=['workflow', 'model'],
        buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    )

    exporter.register_counter(
        'worker_tokens_total',
        'Total tokens consumed by workers, partitioned by model and direction (input, output)',
        labels=['model', 'direction']
    )

    exporter.register_counter(
        'worker_cost_usd_total',
        'Cumulative cost in USD incurred by worker inference calls, partitioned by model',
        labels=['model']
    )

    # Arbiter decision metrics
    exporter.register_counter(
        'arbiter_decisions_total',
        'Total arbiter decisions partitioned by workflow, arbiter model, and verdict (accept, accept_with_reservations, reject)',
        labels=['workflow', 'arbiter_model', 'verdict']
    )

    exporter.register_counter(
        'arbiter_consensus_model_selections_total',
        'Number of times each worker model was selected as the winning output by an arbiter in consensus decisions',
        labels=['workflow', 'selected_model']
    )

    exporter.register_histogram(
        'arbiter_consensus_iterations',
        'Number of consensus refinement iterations required before reaching confidence threshold',
        labels=['workflow', 'task_type'],
        buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    )

    # Model dominance tracking (anti-feedback-loop safeguard)
    exporter.register_gauge(
        'model_dominance_ratio',
        'Current usage fraction per model over the last 100 requests. Alert threshold is 0.70 (anti-feedback-loop safeguard)',
        labels=['model']
    )

    # Database query metrics
    exporter.register_histogram(
        'query_similarity_search_seconds',
        'Latency of pgvector similarity searches in seconds, partitioned by target table and whether filters were applied. Default buckets: 0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5',
        labels=['table', 'filter'],
        buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5]
    )

    exporter.register_counter(
        'storage_rows_inserted_total',
        'Total rows inserted into PostgreSQL partitioned by schema and table (e.g. learning.experiences, monitoring.execution_summary, costs.entries)',
        labels=['schema', 'table']
    )

    # Thompson Sampling bandit metrics
    exporter.register_gauge(
        'strategy_bandit_reward',
        'Current average reward from the Thompson Sampling bandit for each routing strategy',
        labels=['strategy']
    )

    # Fleet orchestration metrics
    exporter.register_gauge(
        'fleet_slot_utilization_ratio',
        'Current fraction of in-flight slots occupied per fleet host (0.0 to 1.0)',
        labels=['host']
    )

    exporter.register_counter(
        'fleet_routing_decisions_total',
        'Fleet routing decisions by source node, target node, model, and routing reason (load_balance/model_unavailable/cost_optimization)',
        labels=['source_node', 'target_node', 'model', 'reason']
    )

    # Example usage
    exporter.inc_counter('workflow_completions_total', {'workflow': 'code-review', 'outcome': 'success'})
    exporter.observe_histogram('workflow_duration_seconds', 45.3, {'workflow': 'code-review'})
    exporter.inc_counter('worker_outputs_total', {'workflow': 'code-review', 'model': 'sonnet', 'outcome': 'success'})
    exporter.observe_histogram('worker_quality_score', 0.85, {'workflow': 'code-review', 'model': 'sonnet'})
    exporter.inc_counter('worker_tokens_total', {'model': 'sonnet', 'direction': 'input'}, amount=1250)
    exporter.inc_counter('worker_tokens_total', {'model': 'sonnet', 'direction': 'output'}, amount=340)
    exporter.inc_counter('worker_cost_usd_total', {'model': 'sonnet'}, amount=0.0085)
    exporter.inc_counter('arbiter_decisions_total', {'workflow': 'code-review', 'arbiter_model': 'opus', 'verdict': 'accept'})
    exporter.inc_counter('arbiter_consensus_model_selections_total', {'workflow': 'code-review', 'selected_model': 'sonnet'})
    exporter.set_gauge('model_dominance_ratio', 0.42, {'model': 'sonnet'})
    exporter.observe_histogram('query_similarity_search_seconds', 0.00044, {'table': 'experiences', 'filter': 'true'})
    exporter.inc_counter('storage_rows_inserted_total', {'schema': 'learning', 'table': 'experiences'})
    exporter.set_gauge('strategy_bandit_reward', 0.78, {'strategy': 'grep_parallel'})
    exporter.set_gauge('fleet_slot_utilization_ratio', 0.68, {'host': 'server-02'})
    exporter.inc_counter('fleet_routing_decisions_total', {
        'source_node': 'laptop-01',
        'target_node': 'server-02',
        'model': 'sonnet',
        'reason': 'load_balance'
    })
    exporter.observe_histogram('arbiter_consensus_iterations', 3, {'workflow': 'code-review', 'task_type': 'consensus'})

    print(f"✅ Prometheus Exporter with Workflow Storage Metrics:\n{exporter.export_metrics()}")
