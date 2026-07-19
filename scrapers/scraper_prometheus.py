#!/usr/bin/env python3
"""Prometheus documentation scraper.

Covers:
  - Prometheus concepts, configuration, PromQL
  - Alertmanager setup and configuration
  - Best practices and instrumentation
  - Client libraries, exporters, guides
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class PrometheusScraper(BaseScraper):
    """Scrape Prometheus documentation, guides, and best practices."""

    SOURCES = {
        "introduction": {
            "pages": {
                "https://prometheus.io/docs/introduction/overview/": "Prometheus Overview",
                "https://prometheus.io/docs/introduction/first_steps/": "Prometheus First Steps",
                "https://prometheus.io/docs/introduction/comparison/": "Prometheus Comparison",
                "https://prometheus.io/docs/introduction/faq/": "Prometheus FAQ",
                "https://prometheus.io/docs/introduction/glossary/": "Prometheus Glossary",
                "https://prometheus.io/docs/introduction/media/": "Prometheus Media Resources",
                "https://prometheus.io/docs/introduction/roadmap/": "Prometheus Roadmap",
                "https://prometheus.io/docs/introduction/design-doc/": "Prometheus Design Document",
                "https://prometheus.io/docs/introduction/stability/": "Prometheus Stability Guarantees",
                "https://prometheus.io/docs/introduction/release-cycle/": "Prometheus Release Cycle",
            },
        },
        "concepts": {
            "pages": {
                "https://prometheus.io/docs/concepts/data_model/": "Prometheus Data Model",
                "https://prometheus.io/docs/concepts/metric_types/": "Prometheus Metric Types",
                "https://prometheus.io/docs/concepts/jobs_instances/": "Prometheus Jobs and Instances",
                "https://prometheus.io/docs/concepts/remote_write_spec/": "Prometheus Remote Write Spec",
                "https://prometheus.io/docs/concepts/remote_read_spec/": "Prometheus Remote Read Spec",
                "https://prometheus.io/docs/concepts/exemplars/": "Prometheus Exemplars",
                "https://prometheus.io/docs/concepts/native_histograms/": "Prometheus Native Histograms",
                "https://prometheus.io/docs/concepts/text_parsing/": "Prometheus Text Parsing",
            },
        },
        "prometheus": {
            "pages": {
                # Configuration
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/": "Prometheus Configuration",
                "https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/": "Prometheus Recording Rules",
                "https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/": "Prometheus Alerting Rules",
                "https://prometheus.io/docs/prometheus/latest/configuration/template_examples/": "Prometheus Template Examples",
                "https://prometheus.io/docs/prometheus/latest/configuration/template_reference/": "Prometheus Template Reference",
                "https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/": "Prometheus Unit Testing Rules",
                # PromQL
                "https://prometheus.io/docs/prometheus/latest/querying/basics/": "PromQL Basics",
                "https://prometheus.io/docs/prometheus/latest/querying/operators/": "PromQL Operators",
                "https://prometheus.io/docs/prometheus/latest/querying/functions/": "PromQL Functions",
                "https://prometheus.io/docs/prometheus/latest/querying/examples/": "PromQL Examples",
                "https://prometheus.io/docs/prometheus/latest/querying/api/": "Prometheus HTTP API",
                # Core
                "https://prometheus.io/docs/prometheus/latest/storage/": "Prometheus Storage",
                "https://prometheus.io/docs/prometheus/latest/federation/": "Prometheus Federation",
                "https://prometheus.io/docs/prometheus/latest/migration/": "Prometheus Migration",
                "https://prometheus.io/docs/prometheus/latest/management_api/": "Prometheus Management API",
                "https://prometheus.io/docs/prometheus/latest/getting_started/": "Prometheus Getting Started",
                "https://prometheus.io/docs/prometheus/latest/installation/": "Prometheus Installation",
                "https://prometheus.io/docs/prometheus/latest/feature_flags/": "Prometheus Feature Flags",
                "https://prometheus.io/docs/prometheus/latest/disabled_features/": "Prometheus Disabled Features",
                # Service discovery
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config": "Prometheus Scrape Config",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#static_config": "Prometheus Static Config",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#file_sd_config": "Prometheus File SD Config",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#kubernetes_sd_config": "Prometheus Kubernetes SD",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#ec2_sd_config": "Prometheus EC2 SD",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#consul_sd_config": "Prometheus Consul SD",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#dns_sd_config": "Prometheus DNS SD",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#azure_sd_config": "Prometheus Azure SD",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#gce_sd_config": "Prometheus GCE SD",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#openstack_sd_config": "Prometheus OpenStack SD",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#marathon_sd_config": "Prometheus Marathon SD",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#dockerswarm_sd_config": "Prometheus Docker Swarm SD",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#docker_sd_config": "Prometheus Docker SD",
                "https://prometheus.io/docs/prometheus/latest/querying/pending/": "PromQL Pending Features",
                "https://prometheus.io/docs/prometheus/latest/querying/scope/": "PromQL Scope",
            },
        },
        "alerting": {
            "pages": {
                "https://prometheus.io/docs/alerting/latest/overview/": "Alertmanager Overview",
                "https://prometheus.io/docs/alerting/latest/alertmanager/": "Alertmanager",
                "https://prometheus.io/docs/alerting/latest/configuration/": "Alertmanager Configuration",
                "https://prometheus.io/docs/alerting/latest/clients/": "Alertmanager Clients",
                "https://prometheus.io/docs/alerting/latest/notification_examples/": "Alertmanager Notification Examples",
                "https://prometheus.io/docs/alerting/latest/notifications/": "Alertmanager Notifications",
                "https://prometheus.io/docs/alerting/latest/management_api/": "Alertmanager Management API",
                "https://prometheus.io/docs/alerting/latest/https/": "Alertmanager HTTPS Configuration",
                "https://prometheus.io/docs/alerting/latest/compatibility/": "Alertmanager Compatibility",
                "https://prometheus.io/docs/alerting/latest/alertmanager/#high-availability": "Alertmanager High Availability",
                "https://prometheus.io/docs/alerting/latest/alertmanager/#silences": "Alertmanager Silences",
                "https://prometheus.io/docs/alerting/latest/alertmanager/#inhibition": "Alertmanager Inhibition",
                "https://prometheus.io/docs/alerting/latest/alertmanager/#routing-tree": "Alertmanager Routing Tree",
            },
        },
        "best-practices": {
            "pages": {
                "https://prometheus.io/docs/practices/naming/": "Prometheus Naming Conventions",
                "https://prometheus.io/docs/practices/consoles/": "Prometheus Consoles",
                "https://prometheus.io/docs/practices/instrumentation/": "Prometheus Instrumentation",
                "https://prometheus.io/docs/practices/histograms/": "Prometheus Histograms",
                "https://prometheus.io/docs/practices/alerting/": "Prometheus Alerting Best Practices",
                "https://prometheus.io/docs/practices/rules/": "Prometheus Recording Rules Best Practices",
                "https://prometheus.io/docs/practices/pushing/": "Prometheus When to Use Pushgateway",
                "https://prometheus.io/docs/practices/remote_write/": "Prometheus Remote Write Tuning",
                "https://prometheus.io/docs/practices/storage/": "Prometheus Storage Best Practices",
                "https://prometheus.io/docs/practices/security/": "Prometheus Security Best Practices",
            },
        },
        "instrumenting": {
            "pages": {
                "https://prometheus.io/docs/instrumenting/clientlibs/": "Prometheus Client Libraries",
                "https://prometheus.io/docs/instrumenting/writing_clientlibs/": "Writing Client Libraries",
                "https://prometheus.io/docs/instrumenting/pushing/": "Prometheus Pushgateway",
                "https://prometheus.io/docs/instrumenting/exporters/": "Prometheus Exporters",
                "https://prometheus.io/docs/instrumenting/writing_exporters/": "Writing Exporters",
                "https://prometheus.io/docs/instrumenting/exposition_formats/": "Prometheus Exposition Formats",
                "https://prometheus.io/docs/instrumenting/format_types/": "Prometheus Format Types",
                "https://prometheus.io/docs/instrumenting/naming/": "Prometheus Metric Naming",
                "https://prometheus.io/docs/instrumenting/labels/": "Prometheus Labels",
                "https://prometheus.io/docs/instrumenting/writing_metrics/": "Prometheus Writing Metrics",
            },
        },
        "guides": {
            "pages": {
                "https://prometheus.io/docs/guides/basic-auth/": "Prometheus Basic Auth",
                "https://prometheus.io/docs/guides/cadvisor/": "Prometheus cAdvisor",
                "https://prometheus.io/docs/guides/dockerswarm/": "Prometheus Docker Swarm",
                "https://prometheus.io/docs/guides/file-sd/": "Prometheus File Service Discovery",
                "https://prometheus.io/docs/guides/go-application/": "Prometheus Go Application",
                "https://prometheus.io/docs/guides/multi-target-exporter/": "Prometheus Multi-Target Exporter",
                "https://prometheus.io/docs/guides/node-exporter/": "Prometheus Node Exporter",
                "https://prometheus.io/docs/guides/query-log/": "Prometheus Query Log",
                "https://prometheus.io/docs/guides/tls-encryption/": "Prometheus TLS Encryption",
                "https://prometheus.io/docs/guides/instrumenting-a-go-application/": "Prometheus Instrumenting Go",
                "https://prometheus.io/docs/guides/whats-a-metric/": "Prometheus What Is a Metric",
                "https://prometheus.io/docs/guides/understanding-metric-types/": "Prometheus Understanding Metric Types",
                "https://prometheus.io/docs/guides/use-labels/": "Prometheus Using Labels",
                "https://prometheus.io/docs/guides/grafana/": "Prometheus with Grafana",
                "https://prometheus.io/docs/guides/alerting-based-on-metrics/": "Prometheus Alerting Based on Metrics",
                "https://prometheus.io/docs/guides/multi-cluster-monitoring/": "Prometheus Multi-Cluster Monitoring",
                "https://prometheus.io/docs/guides/recording-rules/": "Prometheus Recording Rules Guide",
                "https://prometheus.io/docs/guides/relabel-configs/": "Prometheus Relabel Configs Guide",
                "https://prometheus.io/docs/guides/kubernetes-monitoring/": "Prometheus Kubernetes Monitoring",
                "https://prometheus.io/docs/guides/docker-monitoring/": "Prometheus Docker Monitoring",
            },
        },
        "operating": {
            "pages": {
                "https://prometheus.io/docs/operating/configuration/": "Prometheus Operating Configuration",
                "https://prometheus.io/docs/operating/security/": "Prometheus Security Model",
                "https://prometheus.io/docs/operating/integrations/": "Prometheus Integrations",
                "https://prometheus.io/docs/operating/performance/": "Prometheus Performance Tuning",
                "https://prometheus.io/docs/operating/observability/": "Prometheus Self-Monitoring",
                "https://prometheus.io/docs/operating/backwards-compatibility/": "Prometheus Backwards Compatibility",
                "https://prometheus.io/docs/prometheus/latest/command-line/promtool/": "Promtool CLI Reference",
                "https://prometheus.io/docs/prometheus/latest/command-line/prometheus/": "Prometheus CLI Reference",
                "https://prometheus.io/docs/prometheus/latest/configuration/https/": "Prometheus HTTPS Configuration",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#relabel_config": "Prometheus Relabel Config",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#metric_relabel_configs": "Prometheus Metric Relabel Configs",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#remote_write": "Prometheus Remote Write Config",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#remote_read": "Prometheus Remote Read Config",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#alertmanager_config": "Prometheus Alertmanager Config",
                "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#tls_config": "Prometheus TLS Config",
            },
        },
        "ecosystem": {
            "pages": {
                "https://prometheus.io/docs/instrumenting/exporters/#databases": "Prometheus Database Exporters",
                "https://prometheus.io/docs/instrumenting/exporters/#hardware-related": "Prometheus Hardware Exporters",
                "https://prometheus.io/docs/instrumenting/exporters/#messaging-systems": "Prometheus Messaging Exporters",
                "https://prometheus.io/docs/instrumenting/exporters/#storage": "Prometheus Storage Exporters",
                "https://prometheus.io/docs/instrumenting/exporters/#http": "Prometheus HTTP Exporters",
                "https://prometheus.io/docs/instrumenting/exporters/#apis": "Prometheus API Exporters",
                "https://prometheus.io/docs/instrumenting/exporters/#logging": "Prometheus Logging Exporters",
                "https://prometheus.io/docs/instrumenting/exporters/#other-monitoring-systems": "Prometheus Monitoring System Exporters",
                "https://prometheus.io/docs/instrumenting/exporters/#miscellaneous": "Prometheus Miscellaneous Exporters",
                "https://prometheus.io/docs/instrumenting/exporters/#software-exposing-prometheus-metrics": "Prometheus Native Metric Software",
                "https://prometheus.io/docs/instrumenting/exporters/#other-third-party-utilities": "Prometheus Third-Party Utilities",
                "https://prometheus.io/docs/visualization/grafana/": "Prometheus Grafana Visualization",
                "https://prometheus.io/docs/visualization/browser/": "Prometheus Expression Browser",
                "https://prometheus.io/docs/visualization/consoles/": "Prometheus Console Templates",
                "https://prometheus.io/docs/visualization/template_examples/": "Prometheus Visualization Template Examples",
                "https://prometheus.io/docs/visualization/promsql/": "Prometheus PromSQL Visualization",
            },
        },
        "client-libraries": {
            "pages": {
                "https://prometheus.io/docs/instrumenting/clientlibs/#go": "Prometheus Go Client",
                "https://prometheus.io/docs/instrumenting/clientlibs/#java": "Prometheus Java Client",
                "https://prometheus.io/docs/instrumenting/clientlibs/#python": "Prometheus Python Client",
                "https://prometheus.io/docs/instrumenting/clientlibs/#ruby": "Prometheus Ruby Client",
                "https://prometheus.io/docs/instrumenting/clientlibs/#rust": "Prometheus Rust Client",
                "https://prometheus.io/docs/instrumenting/clientlibs/#c": "Prometheus C Client",
                "https://prometheus.io/docs/instrumenting/clientlibs/#c-plus-plus": "Prometheus C++ Client",
                "https://prometheus.io/docs/instrumenting/clientlibs/#erlang": "Prometheus Erlang Client",
                "https://prometheus.io/docs/instrumenting/clientlibs/#elixir": "Prometheus Elixir Client",
                "https://prometheus.io/docs/instrumenting/clientlibs/#haskell": "Prometheus Haskell Client",
                "https://prometheus.io/docs/instrumenting/clientlibs/#net": "Prometheus .NET Client",
                "https://prometheus.io/docs/instrumenting/clientlibs/#node-js": "Prometheus Node.js Client",
                "https://prometheus.io/docs/instrumenting/clientlibs/#php": "Prometheus PHP Client",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"prometheus-{source_key}" if source_key else "prometheus"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [' | Prometheus', ' - Prometheus']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})

        for url, title in pages.items():
            if not self.running:
                break

            item_id = self.make_id(url)
            content = self.fetch_url(url)

            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)

                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"prometheus-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)  # Respectful rate limit for Prometheus docs

        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0

        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(
                    f"Unknown source key: {self.source_key}. "
                    f"Available: {list(self.SOURCES.keys())}"
                )
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES

        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping prometheus/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    PrometheusScraper(base, source_key).run()
