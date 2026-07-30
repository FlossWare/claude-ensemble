#!/usr/bin/env python3
"""eBPF documentation scraper.

Covers:
  - Introduction: what is eBPF, why eBPF, use cases
  - Concepts: program types, maps, helpers, verifier, JIT
  - BPF guide: Cilium BPF and XDP reference guide
  - Tutorials: getting started, tracing, networking
  - Cilium BPF: architecture, datapath, policy enforcement
  - Reference: bpftool, libbpf, kernel documentation
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class EBPFScraper(BaseScraper):
    """Scrape eBPF documentation from ebpf.io and docs.cilium.io."""

    SOURCES = {
        "introduction": {
            "pages": {
                "https://ebpf.io/what-is-ebpf/": "What is eBPF?",
                "https://ebpf.io/": "eBPF - Introduction",
                "https://ebpf.io/applications/": "eBPF Applications",
                "https://ebpf.io/infrastructure/": "eBPF Infrastructure",
                "https://ebpf.io/get-started/": "Get Started with eBPF",
            },
        },
        "concepts": {
            "pages": {
                # ebpf.io concept pages
                "https://docs.kernel.org/bpf/index.html": "BPF Documentation Index (Kernel)",
                "https://docs.kernel.org/bpf/instruction-set.html": "eBPF Instruction Set",
                "https://docs.kernel.org/bpf/verifier.html": "eBPF Verifier",
                "https://docs.kernel.org/bpf/libbpf/index.html": "libbpf Documentation",
                "https://docs.kernel.org/bpf/libbpf/libbpf_overview.html": "libbpf Overview",
                "https://docs.kernel.org/bpf/libbpf/program_types.html": "libbpf Program Types",
                "https://docs.kernel.org/bpf/maps.html": "BPF Maps",
                "https://docs.kernel.org/bpf/helpers.html": "BPF Helper Functions",
                "https://docs.kernel.org/bpf/kfuncs.html": "BPF Kernel Functions (kfuncs)",
                "https://docs.kernel.org/bpf/programs.html": "BPF Program Types",
                "https://docs.kernel.org/bpf/map_hash.html": "BPF Hash Maps",
                "https://docs.kernel.org/bpf/map_array.html": "BPF Array Maps",
                "https://docs.kernel.org/bpf/map_of_maps.html": "BPF Map-in-Map",
                "https://docs.kernel.org/bpf/ringbuf.html": "BPF Ring Buffer",
                "https://docs.kernel.org/bpf/btf.html": "BPF Type Format (BTF)",
                "https://docs.kernel.org/bpf/bpf_iterators.html": "BPF Iterators",
                "https://docs.kernel.org/bpf/classic_vs_extended.html": "Classic BPF vs Extended BPF",
                "https://docs.kernel.org/bpf/bpf_design_QA.html": "BPF Design Q&A",
            },
        },
        "bpf-guide": {
            "pages": {
                # Cilium BPF and XDP Reference Guide (comprehensive)
                "https://docs.cilium.io/en/stable/bpf/": "BPF and XDP Reference Guide",
                "https://docs.cilium.io/en/stable/bpf/architecture/": "BPF Architecture",
                "https://docs.cilium.io/en/stable/bpf/toolchain/": "BPF Toolchain",
                "https://docs.cilium.io/en/stable/bpf/progtypes/": "BPF Program Types (Cilium)",
                "https://docs.cilium.io/en/stable/bpf/maps/": "BPF Maps (Cilium Reference)",
                "https://docs.cilium.io/en/stable/bpf/libbpf/": "libbpf (Cilium Reference)",
            },
        },
        "tutorials": {
            "pages": {
                # eBPF tutorials and learning resources
                "https://ebpf.io/blog/": "eBPF Blog",
                "https://docs.cilium.io/en/stable/bpf/instruction-set/": "BPF Instruction Set Reference",
                # Kernel tracing
                "https://docs.kernel.org/trace/kprobes.html": "Kernel Probes (Kprobes)",
                "https://docs.kernel.org/trace/uprobetracer.html": "Uprobe-based Event Tracing",
                "https://docs.kernel.org/trace/tracepoints.html": "Tracepoints",
                "https://docs.kernel.org/trace/events.html": "Event Tracing",
                "https://docs.kernel.org/trace/ftrace.html": "ftrace - Function Tracer",
                "https://docs.kernel.org/trace/index.html": "Linux Tracing Technologies",
            },
        },
        "cilium-bpf": {
            "pages": {
                # Cilium network security using eBPF
                "https://docs.cilium.io/en/stable/overview/intro/": "Introduction to Cilium",
                "https://docs.cilium.io/en/stable/overview/component-overview/": "Cilium Component Overview",
                "https://docs.cilium.io/en/stable/concepts/networking/": "Cilium Networking Concepts",
                "https://docs.cilium.io/en/stable/concepts/networking/routing/": "Cilium Routing",
                "https://docs.cilium.io/en/stable/concepts/networking/ipam/": "Cilium IPAM",
                "https://docs.cilium.io/en/stable/concepts/security/": "Cilium Security Concepts",
                "https://docs.cilium.io/en/stable/concepts/observability/": "Cilium Observability",
                "https://docs.cilium.io/en/stable/network/concepts/ipam/": "Cilium Network IPAM",
                "https://docs.cilium.io/en/stable/security/policy/": "Cilium Network Policy",
                "https://docs.cilium.io/en/stable/security/policy/language/": "Cilium Policy Language",
                "https://docs.cilium.io/en/stable/gettingstarted/": "Cilium Getting Started",
                "https://docs.cilium.io/en/stable/gettingstarted/k8s-install-default/": "Cilium Quick Installation",
                "https://docs.cilium.io/en/stable/gettingstarted/hubble_setup/": "Setting up Hubble Observability",
                "https://docs.cilium.io/en/stable/operations/performance/tuning/": "Cilium Performance Tuning",
            },
        },
        "reference": {
            "pages": {
                # bpftool
                "https://docs.kernel.org/bpf/bpf_devel_QA.html": "BPF Development Q&A",
                "https://docs.kernel.org/bpf/bpf_licensing.html": "BPF Licensing",
                "https://docs.kernel.org/bpf/test_debug.html": "BPF Testing and Debugging",
                "https://docs.kernel.org/bpf/standardization/instruction-set-v1.html": "BPF ISA v1 Standardization",
                # XDP
                "https://docs.kernel.org/networking/af_xdp.html": "AF_XDP",
                "https://docs.kernel.org/networking/xdp-rx-metadata.html": "XDP RX Metadata",
                # TC / Traffic Control
                "https://docs.kernel.org/networking/tc-actions-env-rules.html": "TC Actions Environment Rules",
                # Cgroup BPF
                "https://docs.kernel.org/admin-guide/cgroup-v2.html": "Control Group v2",
                # libbpf API and CO-RE
                "https://docs.kernel.org/bpf/libbpf/libbpf_naming_convention.html": "libbpf Naming Convention",
                "https://docs.kernel.org/bpf/libbpf/libbpf_build.html": "Building libbpf",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"ebpf-{source_key}" if source_key else "ebpf"
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
            for suffix in [' — Cilium documentation', ' - Cilium documentation',
                           ' — eBPF', ' - eBPF', ' — The Linux Kernel documentation',
                           ' - The Linux Kernel documentation', ' | eBPF']:
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
                        "category": f"ebpf-{source_key}",
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
            self.log.info(f"=== Scraping ebpf/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    EBPFScraper(base, source_key).run()
