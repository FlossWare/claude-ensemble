#!/usr/bin/env python3
"""Nandland documentation scraper.

Covers:
  - Verilog tutorials (basics, modules, common designs)
  - VHDL tutorials (basics, modules, common designs)
  - FPGA fundamentals (basics, design techniques, common modules)
  - Project-based tutorials (FIFO, UART, SPI, I2C, VGA, PWM)

Rate limit: 1.5s between fetches
Est ~150 URLs
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class NandlandScraper(BaseScraper):
    """Scrape Nandland Verilog, VHDL, and FPGA tutorials."""

    SOURCES = {
        "verilog": {
            "pages": {
                # Verilog tutorials
                "https://nandland.com/verilog-tutorials/": "Verilog Tutorials Index",
                "https://nandland.com/introduction-to-verilog-for-beginners-with-code-examples/": "Introduction to Verilog",
                "https://nandland.com/verilog-modules/": "Verilog Modules",
                "https://nandland.com/verilog-primitives/": "Verilog Primitives",
                "https://nandland.com/verilog-data-types/": "Verilog Data Types",
                "https://nandland.com/assign-statement-verilog/": "Verilog Assign Statement",
                "https://nandland.com/always-block-combinational/": "Verilog Always Block Combinational",
                "https://nandland.com/always-block-sequential/": "Verilog Always Block Sequential",
                "https://nandland.com/blocking-vs-nonblocking/": "Verilog Blocking vs Nonblocking",
                "https://nandland.com/if-statement-verilog/": "Verilog If Statement",
                "https://nandland.com/case-statement-verilog/": "Verilog Case Statement",
                "https://nandland.com/for-loop-verilog/": "Verilog For Loop",
                "https://nandland.com/while-loop-verilog/": "Verilog While Loop",
                "https://nandland.com/verilog-parameters/": "Verilog Parameters",
                "https://nandland.com/verilog-generate/": "Verilog Generate",
                "https://nandland.com/verilog-tasks/": "Verilog Tasks",
                "https://nandland.com/verilog-functions/": "Verilog Functions",
                "https://nandland.com/verilog-operators/": "Verilog Operators",
                "https://nandland.com/signed-vs-unsigned/": "Verilog Signed vs Unsigned",
                "https://nandland.com/concatenation-operator-verilog/": "Verilog Concatenation",
                "https://nandland.com/replication-operator-verilog/": "Verilog Replication Operator",
                "https://nandland.com/initial-block-verilog/": "Verilog Initial Block",
                "https://nandland.com/verilog-testbench/": "Verilog Testbench",
                # Verilog design examples
                "https://nandland.com/and-gate/": "Verilog AND Gate",
                "https://nandland.com/or-gate/": "Verilog OR Gate",
                "https://nandland.com/not-gate-inverter/": "Verilog NOT Gate",
                "https://nandland.com/nand-gate/": "Verilog NAND Gate",
                "https://nandland.com/nor-gate/": "Verilog NOR Gate",
                "https://nandland.com/xor-gate/": "Verilog XOR Gate",
                "https://nandland.com/xnor-gate/": "Verilog XNOR Gate",
                "https://nandland.com/mux-multiplexer/": "Verilog Multiplexer",
                "https://nandland.com/demux-demultiplexer/": "Verilog Demultiplexer",
                "https://nandland.com/flip-flop-d-flip-flop/": "Verilog D Flip-Flop",
                "https://nandland.com/jk-flip-flop/": "Verilog JK Flip-Flop",
                "https://nandland.com/half-adder/": "Verilog Half Adder",
                "https://nandland.com/full-adder/": "Verilog Full Adder",
                "https://nandland.com/latch/": "Verilog Latch",
                "https://nandland.com/decoder/": "Verilog Decoder",
                "https://nandland.com/encoder/": "Verilog Encoder",
                "https://nandland.com/priority-encoder/": "Verilog Priority Encoder",
                "https://nandland.com/shift-register/": "Verilog Shift Register",
                "https://nandland.com/barrel-shifter/": "Verilog Barrel Shifter",
                "https://nandland.com/comparator/": "Verilog Comparator",
            },
        },
        "vhdl": {
            "pages": {
                # VHDL tutorials
                "https://nandland.com/vhdl-tutorials/": "VHDL Tutorials Index",
                "https://nandland.com/introduction-to-vhdl-for-beginners-with-code-examples/": "Introduction to VHDL",
                "https://nandland.com/vhdl-entity/": "VHDL Entity",
                "https://nandland.com/vhdl-architecture/": "VHDL Architecture",
                "https://nandland.com/vhdl-data-types/": "VHDL Data Types",
                "https://nandland.com/signal-assignment-vhdl/": "VHDL Signal Assignment",
                "https://nandland.com/process-vhdl/": "VHDL Process",
                "https://nandland.com/sensitivity-list-vhdl/": "VHDL Sensitivity List",
                "https://nandland.com/if-statement-vhdl/": "VHDL If Statement",
                "https://nandland.com/case-statement-vhdl/": "VHDL Case Statement",
                "https://nandland.com/for-loop-vhdl/": "VHDL For Loop",
                "https://nandland.com/while-loop-vhdl/": "VHDL While Loop",
                "https://nandland.com/vhdl-generics/": "VHDL Generics",
                "https://nandland.com/vhdl-generate/": "VHDL Generate",
                "https://nandland.com/vhdl-procedures/": "VHDL Procedures",
                "https://nandland.com/vhdl-functions/": "VHDL Functions",
                "https://nandland.com/vhdl-packages/": "VHDL Packages",
                "https://nandland.com/vhdl-operators/": "VHDL Operators",
                "https://nandland.com/vhdl-signed-vs-unsigned/": "VHDL Signed vs Unsigned",
                "https://nandland.com/vhdl-concatenation/": "VHDL Concatenation",
                "https://nandland.com/vhdl-testbench/": "VHDL Testbench",
                "https://nandland.com/vhdl-record/": "VHDL Record",
                "https://nandland.com/vhdl-constants/": "VHDL Constants",
                "https://nandland.com/vhdl-component/": "VHDL Component",
                "https://nandland.com/vhdl-port-map/": "VHDL Port Map",
            },
        },
        "fpga": {
            "pages": {
                # FPGA basics
                "https://nandland.com/fpga-101/": "FPGA 101",
                "https://nandland.com/fpga-tutorials/": "FPGA Tutorials Index",
                "https://nandland.com/lesson-1-what-is-an-fpga/": "What is an FPGA",
                "https://nandland.com/lesson-2-what-is-a-lut/": "What is a LUT",
                "https://nandland.com/lesson-3-what-is-a-flip-flop/": "What is a Flip-Flop",
                "https://nandland.com/lesson-4-what-is-an-fpga-development-board/": "FPGA Development Board",
                "https://nandland.com/lesson-5-what-is-a-clock/": "What is a Clock",
                "https://nandland.com/lesson-6-what-is-a-testbench/": "What is a Testbench",
                "https://nandland.com/lesson-7-what-is-a-state-machine/": "What is a State Machine",
                "https://nandland.com/lesson-8-what-is-a-pll/": "What is a PLL",
                "https://nandland.com/lesson-9-what-is-a-block-ram/": "What is a Block RAM",
                "https://nandland.com/lesson-10-what-is-an-io-pin/": "What is an IO Pin",
                "https://nandland.com/lesson-11-what-is-fpga-timing/": "FPGA Timing",
                "https://nandland.com/lesson-12-what-is-metastability/": "FPGA Metastability",
                "https://nandland.com/getting-started-with-fpgas/": "Getting Started with FPGAs",
                # Common FPGA modules
                "https://nandland.com/uart-serial-port-module/": "UART Module",
                "https://nandland.com/spi-master/": "SPI Master",
                "https://nandland.com/i2c-master/": "I2C Master",
                "https://nandland.com/fifo-buffer/": "FIFO Buffer",
                "https://nandland.com/pwm-pulse-width-modulation/": "PWM Module",
                "https://nandland.com/vga-from-fpga/": "VGA from FPGA",
                "https://nandland.com/debounce-a-switch/": "Debounce a Switch",
                "https://nandland.com/clock-divider/": "Clock Divider",
                "https://nandland.com/dual-port-ram/": "Dual Port RAM",
                "https://nandland.com/binary-to-bcd-converter/": "Binary to BCD Converter",
                "https://nandland.com/seven-segment-display/": "Seven Segment Display",
                "https://nandland.com/lfsr-linear-feedback-shift-register/": "LFSR",
                "https://nandland.com/crc-cyclic-redundancy-check/": "CRC",
                "https://nandland.com/pipelined-add/": "Pipelined Add",
                # Design techniques
                "https://nandland.com/crossing-clock-domains/": "Crossing Clock Domains",
                "https://nandland.com/synchronizer-flip-flop/": "Synchronizer Flip-Flop",
                "https://nandland.com/fpga-counter/": "FPGA Counter",
                "https://nandland.com/fpga-state-machine/": "FPGA State Machine",
                # Projects
                "https://nandland.com/project-go-board/": "Go Board Project",
                "https://nandland.com/project-1-blink-an-led/": "Project Blink LED",
                "https://nandland.com/project-2-turn-on-leds-with-switches/": "Project Switches and LEDs",
                "https://nandland.com/project-3-uart/": "Project UART",
                "https://nandland.com/project-4-seven-segment-display/": "Project Seven Segment",
                "https://nandland.com/project-5-vga/": "Project VGA",
                "https://nandland.com/project-6-pong/": "Project Pong",
            },
        },
    }

    # Index pages to crawl for discovering additional article URLs
    INDEX_URLS = {
        "verilog": "https://nandland.com/verilog-tutorials/",
        "vhdl": "https://nandland.com/vhdl-tutorials/",
        "fpga": "https://nandland.com/fpga-tutorials/",
    }

    def __init__(self, base_dir, source_key=None):
        name = f"nandland-{source_key}" if source_key else "nandland"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL)
        text = re.sub(r'<aside[^>]*>.*?</aside>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [' - Nandland', ' | Nandland', ' - nandland',
                           ' | nandland', ' - Nandland.com']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _discover_urls(self, section):
        """Crawl index page for a section to discover article URLs."""
        discovered = {}
        index_url = self.INDEX_URLS.get(section)
        if not index_url:
            return discovered

        content = self.fetch_url(index_url)
        if not content:
            return discovered

        # Find all links within nandland.com
        pattern = r'href=["\'](?:https?://(?:www\.)?nandland\.com)?(/[^"\'#]+/?)["\']'
        matches = re.findall(pattern, content, re.IGNORECASE)

        for path in matches:
            # Skip non-article paths
            if any(skip in path for skip in ['/wp-', '/tag/', '/category/',
                                              '/author/', '/feed/', '/page/',
                                              '.css', '.js', '.png', '.jpg',
                                              '/cart/', '/shop/', '/product/']):
                continue

            url = f"https://nandland.com{path}"
            slug = path.strip('/').split('/')[-1]
            if slug:
                title = slug.replace('-', ' ').title()
                if url not in discovered:
                    discovered[url] = title

        self.log.info(f"  Discovered {len(discovered)} URLs from {section} index")
        time.sleep(1.5)
        return discovered

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = dict(config.get("pages", {}))

        # Discover additional URLs from index pages
        discovered = self._discover_urls(source_key)
        for url, title in discovered.items():
            if url not in pages:
                pages[url] = title

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
                        "category": f"nandland-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {page_title}")

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
            self.log.info(f"=== Scraping nandland/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    NandlandScraper(base, source_key).run()
