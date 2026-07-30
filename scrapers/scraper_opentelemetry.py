#!/usr/bin/env python3
"""OpenTelemetry documentation scraper.

Covers:
  - Concepts: traces, metrics, logs, baggage, context propagation
  - Collector: configuration, deployment, processors, exporters, receivers
  - Languages: Python, Go, Java, JavaScript SDK guides
  - Instrumentation: auto-instrumentation, manual instrumentation, libraries
  - Specification: semantic conventions, resource, trace, metric, log specs
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class OpenTelemetryScraper(BaseScraper):
    """Scrape OpenTelemetry official documentation."""

    SOURCES = {
        "concepts": {
            "pages": {
                "https://opentelemetry.io/docs/": "OpenTelemetry Documentation",
                "https://opentelemetry.io/docs/what-is-opentelemetry/": "What is OpenTelemetry?",
                "https://opentelemetry.io/docs/concepts/": "OpenTelemetry Concepts",
                "https://opentelemetry.io/docs/concepts/observability-primer/": "Observability Primer",
                "https://opentelemetry.io/docs/concepts/signals/": "Signals Overview",
                "https://opentelemetry.io/docs/concepts/signals/traces/": "Traces",
                "https://opentelemetry.io/docs/concepts/signals/metrics/": "Metrics",
                "https://opentelemetry.io/docs/concepts/signals/logs/": "Logs",
                "https://opentelemetry.io/docs/concepts/signals/baggage/": "Baggage",
                "https://opentelemetry.io/docs/concepts/context-propagation/": "Context Propagation",
                "https://opentelemetry.io/docs/concepts/instrumentation/": "Instrumentation",
                "https://opentelemetry.io/docs/concepts/instrumentation/zero-code/": "Zero-Code Instrumentation",
                "https://opentelemetry.io/docs/concepts/instrumentation/code-based/": "Code-Based Instrumentation",
                "https://opentelemetry.io/docs/concepts/instrumentation/libraries/": "Instrumentation Libraries",
                "https://opentelemetry.io/docs/concepts/components/": "Components",
                "https://opentelemetry.io/docs/concepts/sdk-configuration/": "SDK Configuration",
                "https://opentelemetry.io/docs/concepts/sdk-configuration/otlp-exporter-configuration/": "OTLP Exporter Configuration",
                "https://opentelemetry.io/docs/concepts/sdk-configuration/general-sdk-configuration/": "General SDK Configuration",
            },
        },
        "collector": {
            "pages": {
                "https://opentelemetry.io/docs/collector/": "OpenTelemetry Collector",
                "https://opentelemetry.io/docs/collector/quick-start/": "Collector Quick Start",
                "https://opentelemetry.io/docs/collector/installation/": "Collector Installation",
                "https://opentelemetry.io/docs/collector/configuration/": "Collector Configuration",
                "https://opentelemetry.io/docs/collector/deployment/": "Collector Deployment",
                "https://opentelemetry.io/docs/collector/deployment/agent/": "Collector as Agent",
                "https://opentelemetry.io/docs/collector/deployment/gateway/": "Collector as Gateway",
                "https://opentelemetry.io/docs/collector/transforming-telemetry/": "Transforming Telemetry",
                "https://opentelemetry.io/docs/collector/scaling/": "Scaling the Collector",
                "https://opentelemetry.io/docs/collector/troubleshooting/": "Collector Troubleshooting",
                "https://opentelemetry.io/docs/collector/building/": "Building a Custom Collector",
                "https://opentelemetry.io/docs/collector/internal-telemetry/": "Internal Telemetry",
            },
        },
        "languages": {
            "pages": {
                # Python
                "https://opentelemetry.io/docs/languages/python/": "Python SDK Overview",
                "https://opentelemetry.io/docs/languages/python/getting-started/": "Python Getting Started",
                "https://opentelemetry.io/docs/languages/python/instrumentation/": "Python Instrumentation",
                "https://opentelemetry.io/docs/languages/python/exporters/": "Python Exporters",
                "https://opentelemetry.io/docs/languages/python/resources/": "Python Resources",
                # Go
                "https://opentelemetry.io/docs/languages/go/": "Go SDK Overview",
                "https://opentelemetry.io/docs/languages/go/getting-started/": "Go Getting Started",
                "https://opentelemetry.io/docs/languages/go/instrumentation/": "Go Instrumentation",
                "https://opentelemetry.io/docs/languages/go/exporters/": "Go Exporters",
                "https://opentelemetry.io/docs/languages/go/resources/": "Go Resources",
                # Java
                "https://opentelemetry.io/docs/languages/java/": "Java SDK Overview",
                "https://opentelemetry.io/docs/languages/java/getting-started/": "Java Getting Started",
                "https://opentelemetry.io/docs/languages/java/instrumentation/": "Java Instrumentation",
                "https://opentelemetry.io/docs/languages/java/exporters/": "Java Exporters",
                "https://opentelemetry.io/docs/languages/java/resources/": "Java Resources",
                "https://opentelemetry.io/docs/languages/java/configuration/": "Java Configuration",
                # JavaScript / Node.js
                "https://opentelemetry.io/docs/languages/js/": "JavaScript SDK Overview",
                "https://opentelemetry.io/docs/languages/js/getting-started/": "JavaScript Getting Started",
                "https://opentelemetry.io/docs/languages/js/getting-started/nodejs/": "Node.js Getting Started",
                "https://opentelemetry.io/docs/languages/js/getting-started/browser/": "Browser Getting Started",
                "https://opentelemetry.io/docs/languages/js/instrumentation/": "JavaScript Instrumentation",
                "https://opentelemetry.io/docs/languages/js/exporters/": "JavaScript Exporters",
                "https://opentelemetry.io/docs/languages/js/resources/": "JavaScript Resources",
            },
        },
        "instrumentation": {
            "pages": {
                "https://opentelemetry.io/docs/zero-code/": "Zero-Code Instrumentation Overview",
                "https://opentelemetry.io/docs/zero-code/java/": "Java Zero-Code Instrumentation",
                "https://opentelemetry.io/docs/zero-code/java/agent/": "Java Agent",
                "https://opentelemetry.io/docs/zero-code/java/agent/configuration/": "Java Agent Configuration",
                "https://opentelemetry.io/docs/zero-code/python/": "Python Zero-Code Instrumentation",
                "https://opentelemetry.io/docs/zero-code/js/": "JavaScript Zero-Code Instrumentation",
                "https://opentelemetry.io/docs/zero-code/go/": "Go Zero-Code Instrumentation",
                "https://opentelemetry.io/docs/zero-code/dotnet/": ".NET Zero-Code Instrumentation",
            },
        },
        "specification": {
            "pages": {
                "https://opentelemetry.io/docs/specs/": "OpenTelemetry Specification",
                "https://opentelemetry.io/docs/specs/otel/": "OpenTelemetry Spec Overview",
                "https://opentelemetry.io/docs/specs/otel/overview/": "Specification Overview",
                "https://opentelemetry.io/docs/specs/otel/trace/": "Trace Specification",
                "https://opentelemetry.io/docs/specs/otel/trace/api/": "Trace API",
                "https://opentelemetry.io/docs/specs/otel/trace/sdk/": "Trace SDK",
                "https://opentelemetry.io/docs/specs/otel/metrics/": "Metrics Specification",
                "https://opentelemetry.io/docs/specs/otel/metrics/api/": "Metrics API",
                "https://opentelemetry.io/docs/specs/otel/metrics/sdk/": "Metrics SDK",
                "https://opentelemetry.io/docs/specs/otel/logs/": "Logs Specification",
                "https://opentelemetry.io/docs/specs/otel/resource/": "Resource Specification",
                "https://opentelemetry.io/docs/specs/otel/context/": "Context Specification",
                "https://opentelemetry.io/docs/specs/otel/baggage/": "Baggage Specification",
                "https://opentelemetry.io/docs/specs/semconv/": "Semantic Conventions",
                "https://opentelemetry.io/docs/specs/semconv/general/": "General Semantic Conventions",
                "https://opentelemetry.io/docs/specs/semconv/http/": "HTTP Semantic Conventions",
                "https://opentelemetry.io/docs/specs/semconv/database/": "Database Semantic Conventions",
                "https://opentelemetry.io/docs/specs/semconv/messaging/": "Messaging Semantic Conventions",
                "https://opentelemetry.io/docs/specs/semconv/resource/": "Resource Semantic Conventions",
                "https://opentelemetry.io/docs/specs/otlp/": "OTLP Specification",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"opentelemetry-{source_key}" if source_key else "opentelemetry"
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
            for suffix in [' | OpenTelemetry', ' - OpenTelemetry',
                           ' | OTel', ' :: OpenTelemetry']:
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
                        "category": f"opentelemetry-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)

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
            self.log.info(f"=== Scraping opentelemetry/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    OpenTelemetryScraper(base, source_key).run()
