#!/usr/bin/env python3
"""RISC-V specifications and documentation scraper.

Covers:
  - Specifications: ISA base specs, privileged spec, debug spec
  - Extensions: M, A, F, D, C, V, Zicsr, Zifencei, and more
  - Software: toolchain (GCC, LLVM), OS support, simulators
  - Community: working groups, ratification, ecosystem
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class RiscvScraper(BaseScraper):
    """Scrape RISC-V specifications and documentation."""

    SOURCES = {
        "specifications": {
            "pages": {
                "https://riscv.org/technical/specifications/": "RISC-V Specifications",
                "https://riscv.org/wp-content/uploads/2017/05/riscv-spec-v2.2.pdf": "RISC-V ISA Spec v2.2",
                "https://riscv.org/technical/specifications/privileged-isa/": "Privileged ISA Specification",
                "https://riscv.org/technical/specifications/isa-spec-pdf/": "ISA Specification PDF",
                "https://riscv.github.io/ISA_Formal_Spec_Public_Review/": "ISA Formal Spec Public Review",
                "https://riscv.org/about/risc-v-branding-guidelines/": "RISC-V Branding Guidelines",
                "https://riscv.org/about/history/": "RISC-V History",
                "https://riscv.org/about/faq/": "RISC-V FAQ",
            },
        },
        "extensions": {
            "pages": {
                "https://riscv.github.io/riscv-isa-manual/latest/rv32.html": "RV32I Base Integer Instruction Set",
                "https://riscv.github.io/riscv-isa-manual/latest/rv64.html": "RV64I Base Integer Instruction Set",
                "https://riscv.github.io/riscv-isa-manual/latest/m.html": "M Standard Extension (Multiply/Divide)",
                "https://riscv.github.io/riscv-isa-manual/latest/a.html": "A Standard Extension (Atomics)",
                "https://riscv.github.io/riscv-isa-manual/latest/f.html": "F Standard Extension (Single-Precision Float)",
                "https://riscv.github.io/riscv-isa-manual/latest/d.html": "D Standard Extension (Double-Precision Float)",
                "https://riscv.github.io/riscv-isa-manual/latest/c.html": "C Standard Extension (Compressed)",
                "https://riscv.github.io/riscv-isa-manual/latest/v.html": "V Standard Extension (Vector)",
                "https://riscv.github.io/riscv-isa-manual/latest/zicsr.html": "Zicsr (CSR Instructions)",
                "https://riscv.github.io/riscv-isa-manual/latest/zifencei.html": "Zifencei (Instruction-Fetch Fence)",
            },
        },
        "software": {
            "pages": {
                "https://riscv.org/software-tools/": "RISC-V Software Tools",
                "https://riscv.org/software-tools/risc-v-tools/": "RISC-V Tools Ecosystem",
                "https://riscv.org/exchange/software/": "RISC-V Software Exchange",
                "https://riscv.github.io/riscv-elf-psabi-doc/": "RISC-V ELF psABI Documentation",
                "https://riscv.github.io/riscv-c-api-doc/": "RISC-V C API Documentation",
                "https://riscv.github.io/riscv-asm-manual/riscv-asm.html": "RISC-V Assembly Manual",
            },
        },
        "community": {
            "pages": {
                "https://riscv.org/community/": "RISC-V Community",
                "https://riscv.org/technical/technical-forums/": "Technical Forums",
                "https://riscv.org/membership/members/": "RISC-V Members",
                "https://riscv.org/news/": "RISC-V News",
                "https://riscv.org/exchange/": "RISC-V Exchange",
                "https://riscv.org/learn/": "Learn RISC-V",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"riscv-{source_key}" if source_key else "riscv"
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
            for suffix in [' - RISC-V International', ' | RISC-V International',
                           ' - RISC-V', ' | RISC-V']:
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
                        "category": f"riscv-{source_key}",
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
            self.log.info(f"=== Scraping riscv/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    RiscvScraper(base, source_key).run()
