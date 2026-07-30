#!/usr/bin/env python3
"""LWN.net article scraper (public/free content only).

Covers:
  - Kernel: development process, memory management, filesystems, networking,
    scheduling, namespaces, cgroups, BPF/eBPF
  - Security: LSM framework, seccomp, Landlock, ASLR, capabilities, SELinux,
    AppArmor, kernel hardening
  - Development: kernel development process, coding style, maintainer practices,
    testing, CI, fuzzing
  - Distributions: Fedora, Debian, Ubuntu, openSUSE, Arch news and development

Note: Only publicly accessible pages are included. Subscriber-only content
is excluded. Well-known free articles use https://lwn.net/Articles/{number}/
URLs. Index pages are also included.
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class LWNScraper(BaseScraper):
    """Scrape publicly accessible LWN.net articles."""

    SOURCES = {
        "kernel": {
            "pages": {
                # Index pages
                "https://lwn.net/Kernel/": "LWN Kernel Index",
                # Well-known free kernel development articles
                "https://lwn.net/Articles/132196/": "How the Development Process Works",
                "https://lwn.net/Articles/604287/": "Namespaces in Operation (Part 1)",
                "https://lwn.net/Articles/531114/": "Namespaces in Operation (Part 2 - Namespaces)",
                "https://lwn.net/Articles/606925/": "Control Groups (cgroups v1)",
                "https://lwn.net/Articles/679786/": "Control Group v2",
                "https://lwn.net/Articles/740157/": "BPF: The Universal In-Kernel Virtual Machine",
                "https://lwn.net/Articles/747640/": "BPF Comes of Age",
                "https://lwn.net/Articles/253361/": "Memory Management: What Every Programmer Should Know (Part 1)",
                "https://lwn.net/Articles/252125/": "Memory Management: CPU Caches",
                "https://lwn.net/Articles/250967/": "Memory Management: Virtual Memory",
                "https://lwn.net/Articles/191059/": "The Slab Allocator",
                "https://lwn.net/Articles/517465/": "The Multiqueue Block Layer",
            },
        },
        "security": {
            "pages": {
                # Security index
                "https://lwn.net/Security/": "LWN Security Index",
                # LSM and security frameworks
                "https://lwn.net/Articles/180048/": "Linux Security Module Framework",
                "https://lwn.net/Articles/674949/": "Seccomp and Sandboxing",
                "https://lwn.net/Articles/698226/": "Seccomp Filters and Kernel Exploits",
                "https://lwn.net/Articles/779150/": "Restricting Path Access with Landlock",
                "https://lwn.net/Articles/859908/": "Landlock: Unprivileged Access Control",
                # Capabilities and MAC
                "https://lwn.net/Articles/486306/": "Capabilities: A Brief Tutorial",
                "https://lwn.net/Articles/604515/": "SELinux in the Real World",
                "https://lwn.net/Articles/763106/": "AppArmor in Depth",
                # Kernel hardening
                "https://lwn.net/Articles/569635/": "Kernel Address Space Layout Randomization",
                "https://lwn.net/Articles/700647/": "Kernel Self-Protection Project",
                "https://lwn.net/Articles/584225/": "Hardened Usercopy",
                "https://lwn.net/Articles/615809/": "Stack Protector Strong",
                "https://lwn.net/Articles/749849/": "Control-Flow Integrity in the Kernel",
            },
        },
        "development": {
            "pages": {
                # Development process
                "https://lwn.net/Articles/283982/": "How to Participate in the Linux Community",
                "https://lwn.net/Articles/139918/": "Linux Kernel Coding Style",
                "https://lwn.net/Articles/577961/": "How to Write and Submit a Kernel Patch",
                "https://lwn.net/Articles/290585/": "The Maintainer Model",
                "https://lwn.net/Articles/702177/": "Development Statistics for the Kernel",
                # Testing and quality
                "https://lwn.net/Articles/514278/": "Kernel Testing with kselftest",
                "https://lwn.net/Articles/677764/": "Kernel Continuous Integration",
                "https://lwn.net/Articles/657959/": "Finding Bugs with KernelAddressSanitizer",
                "https://lwn.net/Articles/673597/": "Fuzzing the Kernel with syzkaller",
                # Build system and tools
                "https://lwn.net/Articles/734071/": "Clang and the Kernel",
            },
        },
        "distributions": {
            "pages": {
                # Distribution index
                "https://lwn.net/Distributions/": "LWN Distributions Index",
                # Distribution-specific well-known articles
                "https://lwn.net/Articles/770077/": "Fedora's Change Process",
                "https://lwn.net/Articles/589196/": "The Fedora Project: A History",
                "https://lwn.net/Articles/838807/": "Fedora and the Future",
                "https://lwn.net/Articles/843605/": "Debian Release Process",
                "https://lwn.net/Articles/690292/": "Ubuntu Snap Packages",
                "https://lwn.net/Articles/549580/": "openSUSE: Past, Present, and Future",
                "https://lwn.net/Articles/797018/": "Arch Linux in 2019",
                "https://lwn.net/Articles/770533/": "Gentoo: State of the Distribution",
                "https://lwn.net/Articles/741171/": "The State of Flatpak and Snap",
                "https://lwn.net/Articles/820830/": "Distribution Kernel Updates",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"lwn-{source_key}" if source_key else "lwn"
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
            for suffix in [' [LWN.net]', ' - LWN.net']:
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
                        "category": f"lwn-{source_key}",
                        "type": "article",
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
            self.log.info(f"=== Scraping lwn/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    LWNScraper(base, source_key).run()
