#!/usr/bin/env python3
"""ARM Developer documentation scraper.

Covers:
  - Architecture: ARMv8-A, ARMv9, AArch64, AArch32, exception model
  - Instruction Sets: A64, A32, T32, encoding, system instructions
  - Cortex-A: application processors, MMU, caches, performance
  - Cortex-M: microcontroller processors, NVIC, MPU, low-power
  - NEON: Advanced SIMD, intrinsics, data processing
  - SVE: Scalable Vector Extension, SVE2, vector length agnostic
  - Tools: Arm Compiler, Arm DS, performance analysis, profiling
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class ArmScraper(BaseScraper):
    """Scrape ARM Developer documentation."""

    SOURCES = {
        "architecture": {
            "pages": {
                "https://developer.arm.com/documentation/102404/latest/": "ARMv8-A Architecture Overview",
                "https://developer.arm.com/documentation/den0024/latest/": "ARMv8-A Programmer's Guide",
                "https://developer.arm.com/documentation/den0013/latest/": "ARM Cortex-A Series Programmer's Guide for ARMv7-A",
                "https://developer.arm.com/documentation/102374/latest/": "AArch64 Exception Model",
                "https://developer.arm.com/documentation/102375/latest/": "AArch64 Memory Model",
                "https://developer.arm.com/documentation/102376/latest/": "AArch64 Memory Management",
                "https://developer.arm.com/Architectures/A-Profile%20Architecture": "A-Profile Architecture",
                "https://developer.arm.com/Architectures/R-Profile%20Architecture": "R-Profile Architecture",
                "https://developer.arm.com/Architectures/M-Profile%20Architecture": "M-Profile Architecture",
                "https://developer.arm.com/documentation/ddi0487/latest/": "ARM Architecture Reference Manual ARMv8-A",
            },
        },
        "instruction-sets": {
            "pages": {
                "https://developer.arm.com/documentation/dui0801/latest/": "A64 Instruction Set Reference",
                "https://developer.arm.com/documentation/dui0802/latest/": "A32 and T32 Instruction Set Reference",
                "https://developer.arm.com/documentation/102159/latest/": "A64 Instruction Set Architecture",
                "https://developer.arm.com/documentation/ddi0596/latest/": "A64 ISA XML",
                "https://developer.arm.com/documentation/100076/latest/": "A64 Instruction Set for ARMv8-A",
            },
        },
        "cortex-a": {
            "pages": {
                "https://developer.arm.com/Processors/Cortex-A78": "Cortex-A78",
                "https://developer.arm.com/Processors/Cortex-A77": "Cortex-A77",
                "https://developer.arm.com/Processors/Cortex-A76": "Cortex-A76",
                "https://developer.arm.com/Processors/Cortex-A75": "Cortex-A75",
                "https://developer.arm.com/Processors/Cortex-A73": "Cortex-A73",
                "https://developer.arm.com/Processors/Cortex-A72": "Cortex-A72",
                "https://developer.arm.com/Processors/Cortex-A55": "Cortex-A55",
                "https://developer.arm.com/Processors/Cortex-A53": "Cortex-A53",
                "https://developer.arm.com/documentation/102107/latest/": "Cortex-A Performance Analysis",
            },
        },
        "cortex-m": {
            "pages": {
                "https://developer.arm.com/Processors/Cortex-M33": "Cortex-M33",
                "https://developer.arm.com/Processors/Cortex-M23": "Cortex-M23",
                "https://developer.arm.com/Processors/Cortex-M7": "Cortex-M7",
                "https://developer.arm.com/Processors/Cortex-M4": "Cortex-M4",
                "https://developer.arm.com/Processors/Cortex-M3": "Cortex-M3",
                "https://developer.arm.com/Processors/Cortex-M0%2B": "Cortex-M0+",
                "https://developer.arm.com/Processors/Cortex-M0": "Cortex-M0",
                "https://developer.arm.com/documentation/dui0553/latest/": "Cortex-M4 Generic User Guide",
                "https://developer.arm.com/documentation/dui0552/latest/": "Cortex-M3 Generic User Guide",
            },
        },
        "neon": {
            "pages": {
                "https://developer.arm.com/Architectures/Neon": "NEON Overview",
                "https://developer.arm.com/documentation/102474/latest/": "NEON Programmer's Guide",
                "https://developer.arm.com/documentation/den0018/latest/": "NEON Programmer's Guide for ARMv7-A",
                "https://developer.arm.com/documentation/ihi0073/latest/": "ARM NEON Intrinsics Reference",
                "https://developer.arm.com/documentation/102467/latest/": "Coding for NEON",
            },
        },
        "sve": {
            "pages": {
                "https://developer.arm.com/Architectures/Scalable%20Vector%20Extensions": "SVE Overview",
                "https://developer.arm.com/documentation/102476/latest/": "SVE Programmer's Guide",
                "https://developer.arm.com/documentation/102340/latest/": "Introducing SVE2",
                "https://developer.arm.com/documentation/dai0548/latest/": "SVE Coding Considerations",
            },
        },
        "tools": {
            "pages": {
                "https://developer.arm.com/Tools%20and%20Software/Arm%20Compiler%20for%20Embedded": "Arm Compiler for Embedded",
                "https://developer.arm.com/Tools%20and%20Software/Arm%20Development%20Studio": "Arm Development Studio",
                "https://developer.arm.com/Tools%20and%20Software/GNU%20Toolchain": "GNU Toolchain for Arm",
                "https://developer.arm.com/documentation/101754/latest/": "Arm Compiler Reference Guide",
                "https://developer.arm.com/documentation/100748/latest/": "Arm Compiler User Guide",
                "https://developer.arm.com/documentation/ka004293/latest/": "Arm Performance Reports",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"arm-{source_key}" if source_key else "arm"
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
            for suffix in [' - Arm Developer', ' | Arm Developer',
                           ' - ARM Developer', ' | ARM']:
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
                        "category": f"arm-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)  # Rate limit

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
            self.log.info(f"=== Scraping arm/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    ArmScraper(base, source_key).run()
