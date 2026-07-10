#!/usr/bin/env python3
"""Prometheus Metrics Exporter"""

class PrometheusExporter:
    def __init__(self, port=9100):
        self.port = port
        self.metrics = {}
    
    def register_gauge(self, name, help_text):
        """Register a gauge metric"""
        self.metrics[name] = {'type': 'gauge', 'value': 0, 'help': help_text}
    
    def set_gauge(self, name, value):
        """Set gauge value"""
        if name in self.metrics:
            self.metrics[name]['value'] = value
    
    def export_metrics(self):
        """Export in Prometheus format"""
        lines = []
        for name, metric in self.metrics.items():
            lines.append(f"# HELP {name} {metric['help']}")
            lines.append(f"# TYPE {name} {metric['type']}")
            lines.append(f"{name} {metric['value']}")
        return '\n'.join(lines)

if __name__ == '__main__':
    exporter = PrometheusExporter()
    exporter.register_gauge('consciousness_phi', 'IIT Phi value')
    exporter.set_gauge('consciousness_phi', 4.2)
    print(f"✅ Prometheus Exporter:\n{exporter.export_metrics()}")
