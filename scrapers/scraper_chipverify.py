#!/usr/bin/env python3
"""ChipVerify documentation scraper.

Covers:
  - Verilog tutorials (basics, operators, data types, modules, testbench, etc.)
  - SystemVerilog tutorials (data types, interfaces, classes, constraints, etc.)
  - UVM tutorials (components, sequences, TLM, factory, config-db, etc.)

Rate limit: 1.5s between fetches
Est ~300 URLs
"""
import re
import time
import html as html_mod
import urllib.parse
from scraper_base import BaseScraper


class ChipVerifyScraper(BaseScraper):
    """Scrape ChipVerify Verilog, SystemVerilog, and UVM tutorials."""

    SOURCES = {
        "verilog": {
            "pages": {
                # Verilog Basics
                "https://www.chipverify.com/verilog/verilog-introduction": "Verilog Introduction",
                "https://www.chipverify.com/verilog/verilog-data-types": "Verilog Data Types",
                "https://www.chipverify.com/verilog/verilog-scalar-and-vector": "Verilog Scalar and Vector",
                "https://www.chipverify.com/verilog/verilog-arrays": "Verilog Arrays",
                "https://www.chipverify.com/verilog/verilog-module": "Verilog Module",
                "https://www.chipverify.com/verilog/verilog-port": "Verilog Ports",
                "https://www.chipverify.com/verilog/verilog-assign-statement": "Verilog Assign Statement",
                "https://www.chipverify.com/verilog/verilog-operators": "Verilog Operators",
                "https://www.chipverify.com/verilog/verilog-concatenation": "Verilog Concatenation",
                "https://www.chipverify.com/verilog/verilog-always-block": "Verilog Always Block",
                "https://www.chipverify.com/verilog/verilog-initial-block": "Verilog Initial Block",
                "https://www.chipverify.com/verilog/verilog-if-else": "Verilog If-Else",
                "https://www.chipverify.com/verilog/verilog-case-statement": "Verilog Case Statement",
                "https://www.chipverify.com/verilog/verilog-for-loop": "Verilog For Loop",
                "https://www.chipverify.com/verilog/verilog-while-loop": "Verilog While Loop",
                "https://www.chipverify.com/verilog/verilog-forever-loop": "Verilog Forever Loop",
                "https://www.chipverify.com/verilog/verilog-repeat-loop": "Verilog Repeat Loop",
                "https://www.chipverify.com/verilog/verilog-blocking-non-blocking": "Verilog Blocking Non-Blocking",
                "https://www.chipverify.com/verilog/verilog-parameters": "Verilog Parameters",
                "https://www.chipverify.com/verilog/verilog-generate-block": "Verilog Generate Block",
                # Gate-level modeling
                "https://www.chipverify.com/verilog/verilog-gate-level-modeling": "Verilog Gate Level Modeling",
                "https://www.chipverify.com/verilog/verilog-gate-delay": "Verilog Gate Delay",
                "https://www.chipverify.com/verilog/verilog-switch-level-modeling": "Verilog Switch Level Modeling",
                "https://www.chipverify.com/verilog/verilog-user-defined-primitives": "Verilog User Defined Primitives",
                # Behavioral modeling
                "https://www.chipverify.com/verilog/verilog-behavioral-modeling": "Verilog Behavioral Modeling",
                "https://www.chipverify.com/verilog/verilog-delay-control": "Verilog Delay Control",
                "https://www.chipverify.com/verilog/verilog-event-control": "Verilog Event Control",
                "https://www.chipverify.com/verilog/verilog-inter-intra-delay": "Verilog Inter Intra Delay",
                # Tasks and functions
                "https://www.chipverify.com/verilog/verilog-task": "Verilog Task",
                "https://www.chipverify.com/verilog/verilog-function": "Verilog Function",
                "https://www.chipverify.com/verilog/verilog-task-function-difference": "Verilog Task vs Function",
                # Testbench
                "https://www.chipverify.com/verilog/verilog-testbench": "Verilog Testbench",
                "https://www.chipverify.com/verilog/verilog-timescale": "Verilog Timescale",
                "https://www.chipverify.com/verilog/verilog-simulation": "Verilog Simulation",
                "https://www.chipverify.com/verilog/verilog-display-task": "Verilog Display Task",
                "https://www.chipverify.com/verilog/verilog-file-io": "Verilog File IO",
                "https://www.chipverify.com/verilog/verilog-clock-generator": "Verilog Clock Generator",
                "https://www.chipverify.com/verilog/verilog-compiler-directives": "Verilog Compiler Directives",
                "https://www.chipverify.com/verilog/verilog-ifdef-ifndef": "Verilog ifdef ifndef",
                "https://www.chipverify.com/verilog/verilog-system-tasks": "Verilog System Tasks",
                "https://www.chipverify.com/verilog/verilog-value-change-dump": "Verilog Value Change Dump",
                "https://www.chipverify.com/verilog/verilog-math-functions": "Verilog Math Functions",
                # Design examples
                "https://www.chipverify.com/verilog/verilog-d-flip-flop": "Verilog D Flip Flop",
                "https://www.chipverify.com/verilog/verilog-t-flip-flop": "Verilog T Flip Flop",
                "https://www.chipverify.com/verilog/verilog-jk-flip-flop": "Verilog JK Flip Flop",
                "https://www.chipverify.com/verilog/verilog-counter": "Verilog Counter",
                "https://www.chipverify.com/verilog/verilog-4-bit-counter": "Verilog 4-bit Counter",
                "https://www.chipverify.com/verilog/verilog-mod-n-counter": "Verilog Mod-N Counter",
                "https://www.chipverify.com/verilog/verilog-gray-counter": "Verilog Gray Counter",
                "https://www.chipverify.com/verilog/verilog-ripple-counter": "Verilog Ripple Counter",
                "https://www.chipverify.com/verilog/verilog-mux": "Verilog Multiplexer",
                "https://www.chipverify.com/verilog/verilog-demux": "Verilog Demultiplexer",
                "https://www.chipverify.com/verilog/verilog-decoder": "Verilog Decoder",
                "https://www.chipverify.com/verilog/verilog-encoder": "Verilog Encoder",
                "https://www.chipverify.com/verilog/verilog-priority-encoder": "Verilog Priority Encoder",
                "https://www.chipverify.com/verilog/verilog-full-adder": "Verilog Full Adder",
                "https://www.chipverify.com/verilog/verilog-shift-register": "Verilog Shift Register",
                "https://www.chipverify.com/verilog/verilog-fifo": "Verilog FIFO",
                "https://www.chipverify.com/verilog/verilog-single-port-ram": "Verilog Single Port RAM",
                "https://www.chipverify.com/verilog/verilog-dual-port-ram": "Verilog Dual Port RAM",
                "https://www.chipverify.com/verilog/verilog-alu": "Verilog ALU",
                # Misc
                "https://www.chipverify.com/verilog/verilog-tutorial": "Verilog Tutorial Index",
                "https://www.chipverify.com/verilog/verilog-syntax": "Verilog Syntax",
                "https://www.chipverify.com/verilog/verilog-identifiers": "Verilog Identifiers",
                "https://www.chipverify.com/verilog/verilog-comments": "Verilog Comments",
                "https://www.chipverify.com/verilog/verilog-integer": "Verilog Integer",
                "https://www.chipverify.com/verilog/verilog-real": "Verilog Real",
                "https://www.chipverify.com/verilog/verilog-time": "Verilog Time",
                "https://www.chipverify.com/verilog/verilog-string": "Verilog String",
                "https://www.chipverify.com/verilog/verilog-wire": "Verilog Wire",
                "https://www.chipverify.com/verilog/verilog-reg": "Verilog Reg",
                "https://www.chipverify.com/verilog/verilog-net-types": "Verilog Net Types",
                "https://www.chipverify.com/verilog/verilog-strength": "Verilog Strength",
            },
        },
        "systemverilog": {
            "pages": {
                # Data Types
                "https://www.chipverify.com/systemverilog/systemverilog-tutorial": "SystemVerilog Tutorial Index",
                "https://www.chipverify.com/systemverilog/systemverilog-data-types": "SystemVerilog Data Types",
                "https://www.chipverify.com/systemverilog/systemverilog-logic": "SystemVerilog Logic",
                "https://www.chipverify.com/systemverilog/systemverilog-bit": "SystemVerilog Bit",
                "https://www.chipverify.com/systemverilog/systemverilog-byte-shortint-int-longint": "SystemVerilog Integer Types",
                "https://www.chipverify.com/systemverilog/systemverilog-real-shortreal": "SystemVerilog Real Types",
                "https://www.chipverify.com/systemverilog/systemverilog-string": "SystemVerilog String",
                "https://www.chipverify.com/systemverilog/systemverilog-enum": "SystemVerilog Enum",
                "https://www.chipverify.com/systemverilog/systemverilog-struct": "SystemVerilog Struct",
                "https://www.chipverify.com/systemverilog/systemverilog-union": "SystemVerilog Union",
                "https://www.chipverify.com/systemverilog/systemverilog-typedef": "SystemVerilog Typedef",
                "https://www.chipverify.com/systemverilog/systemverilog-arrays": "SystemVerilog Arrays",
                "https://www.chipverify.com/systemverilog/systemverilog-dynamic-array": "SystemVerilog Dynamic Array",
                "https://www.chipverify.com/systemverilog/systemverilog-associative-array": "SystemVerilog Associative Array",
                "https://www.chipverify.com/systemverilog/systemverilog-queue": "SystemVerilog Queue",
                "https://www.chipverify.com/systemverilog/systemverilog-casting": "SystemVerilog Casting",
                # Interfaces
                "https://www.chipverify.com/systemverilog/systemverilog-interface": "SystemVerilog Interface",
                "https://www.chipverify.com/systemverilog/systemverilog-modport": "SystemVerilog Modport",
                "https://www.chipverify.com/systemverilog/systemverilog-virtual-interface": "SystemVerilog Virtual Interface",
                "https://www.chipverify.com/systemverilog/systemverilog-clocking-block": "SystemVerilog Clocking Block",
                # Classes
                "https://www.chipverify.com/systemverilog/systemverilog-class": "SystemVerilog Class",
                "https://www.chipverify.com/systemverilog/systemverilog-class-constructor": "SystemVerilog Class Constructor",
                "https://www.chipverify.com/systemverilog/systemverilog-inheritance": "SystemVerilog Inheritance",
                "https://www.chipverify.com/systemverilog/systemverilog-polymorphism": "SystemVerilog Polymorphism",
                "https://www.chipverify.com/systemverilog/systemverilog-abstract-class": "SystemVerilog Abstract Class",
                "https://www.chipverify.com/systemverilog/systemverilog-parameterized-class": "SystemVerilog Parameterized Class",
                "https://www.chipverify.com/systemverilog/systemverilog-shallow-deep-copy": "SystemVerilog Shallow Deep Copy",
                "https://www.chipverify.com/systemverilog/systemverilog-scope-resolution-operator": "SystemVerilog Scope Resolution",
                # Constraints
                "https://www.chipverify.com/systemverilog/systemverilog-constraints": "SystemVerilog Constraints",
                "https://www.chipverify.com/systemverilog/systemverilog-randomization": "SystemVerilog Randomization",
                "https://www.chipverify.com/systemverilog/systemverilog-rand-randc": "SystemVerilog rand randc",
                "https://www.chipverify.com/systemverilog/systemverilog-constraint-block": "SystemVerilog Constraint Block",
                "https://www.chipverify.com/systemverilog/systemverilog-inline-constraints": "SystemVerilog Inline Constraints",
                "https://www.chipverify.com/systemverilog/systemverilog-soft-constraints": "SystemVerilog Soft Constraints",
                "https://www.chipverify.com/systemverilog/systemverilog-constraint-inside": "SystemVerilog Constraint Inside",
                "https://www.chipverify.com/systemverilog/systemverilog-solve-before": "SystemVerilog Solve Before",
                "https://www.chipverify.com/systemverilog/systemverilog-unique-constraint": "SystemVerilog Unique Constraint",
                "https://www.chipverify.com/systemverilog/systemverilog-foreach-constraint": "SystemVerilog Foreach Constraint",
                "https://www.chipverify.com/systemverilog/systemverilog-distribution-constraint": "SystemVerilog Distribution Constraint",
                # Assertions
                "https://www.chipverify.com/systemverilog/systemverilog-assertions": "SystemVerilog Assertions",
                "https://www.chipverify.com/systemverilog/systemverilog-immediate-assertion": "SystemVerilog Immediate Assertion",
                "https://www.chipverify.com/systemverilog/systemverilog-concurrent-assertion": "SystemVerilog Concurrent Assertion",
                "https://www.chipverify.com/systemverilog/systemverilog-sequence": "SystemVerilog Sequence",
                "https://www.chipverify.com/systemverilog/systemverilog-property": "SystemVerilog Property",
                "https://www.chipverify.com/systemverilog/systemverilog-assertion-operators": "SystemVerilog Assertion Operators",
                # Coverage
                "https://www.chipverify.com/systemverilog/systemverilog-functional-coverage": "SystemVerilog Functional Coverage",
                "https://www.chipverify.com/systemverilog/systemverilog-covergroup": "SystemVerilog Covergroup",
                "https://www.chipverify.com/systemverilog/systemverilog-coverpoint": "SystemVerilog Coverpoint",
                "https://www.chipverify.com/systemverilog/systemverilog-cross-coverage": "SystemVerilog Cross Coverage",
                "https://www.chipverify.com/systemverilog/systemverilog-coverage-options": "SystemVerilog Coverage Options",
                # Testbench
                "https://www.chipverify.com/systemverilog/systemverilog-testbench": "SystemVerilog Testbench",
                "https://www.chipverify.com/systemverilog/systemverilog-program-block": "SystemVerilog Program Block",
                "https://www.chipverify.com/systemverilog/systemverilog-semaphore": "SystemVerilog Semaphore",
                "https://www.chipverify.com/systemverilog/systemverilog-mailbox": "SystemVerilog Mailbox",
                "https://www.chipverify.com/systemverilog/systemverilog-event": "SystemVerilog Event",
                "https://www.chipverify.com/systemverilog/systemverilog-fork-join": "SystemVerilog Fork Join",
                "https://www.chipverify.com/systemverilog/systemverilog-wait-fork": "SystemVerilog Wait Fork",
                "https://www.chipverify.com/systemverilog/systemverilog-disable-fork": "SystemVerilog Disable Fork",
                # Misc
                "https://www.chipverify.com/systemverilog/systemverilog-always-comb": "SystemVerilog always_comb",
                "https://www.chipverify.com/systemverilog/systemverilog-always-ff": "SystemVerilog always_ff",
                "https://www.chipverify.com/systemverilog/systemverilog-always-latch": "SystemVerilog always_latch",
                "https://www.chipverify.com/systemverilog/systemverilog-unique-priority": "SystemVerilog Unique Priority",
                "https://www.chipverify.com/systemverilog/systemverilog-package": "SystemVerilog Package",
                "https://www.chipverify.com/systemverilog/systemverilog-timeunit-timeprecision": "SystemVerilog Timeunit Timeprecision",
            },
        },
        "uvm": {
            "pages": {
                # UVM Overview
                "https://www.chipverify.com/uvm/uvm-tutorial": "UVM Tutorial Index",
                "https://www.chipverify.com/uvm/uvm-introduction": "UVM Introduction",
                "https://www.chipverify.com/uvm/uvm-testbench-architecture": "UVM Testbench Architecture",
                "https://www.chipverify.com/uvm/uvm-hello-world": "UVM Hello World",
                # Components
                "https://www.chipverify.com/uvm/uvm-component": "UVM Component",
                "https://www.chipverify.com/uvm/uvm-object": "UVM Object",
                "https://www.chipverify.com/uvm/uvm-driver": "UVM Driver",
                "https://www.chipverify.com/uvm/uvm-monitor": "UVM Monitor",
                "https://www.chipverify.com/uvm/uvm-sequencer": "UVM Sequencer",
                "https://www.chipverify.com/uvm/uvm-agent": "UVM Agent",
                "https://www.chipverify.com/uvm/uvm-env": "UVM Env",
                "https://www.chipverify.com/uvm/uvm-test": "UVM Test",
                "https://www.chipverify.com/uvm/uvm-scoreboard": "UVM Scoreboard",
                "https://www.chipverify.com/uvm/uvm-subscriber": "UVM Subscriber",
                # Sequences
                "https://www.chipverify.com/uvm/uvm-sequence": "UVM Sequence",
                "https://www.chipverify.com/uvm/uvm-sequence-item": "UVM Sequence Item",
                "https://www.chipverify.com/uvm/uvm-sequence-library": "UVM Sequence Library",
                "https://www.chipverify.com/uvm/uvm-virtual-sequence": "UVM Virtual Sequence",
                "https://www.chipverify.com/uvm/uvm-virtual-sequencer": "UVM Virtual Sequencer",
                "https://www.chipverify.com/uvm/uvm-sequence-start": "UVM Sequence Start",
                # TLM
                "https://www.chipverify.com/uvm/uvm-tlm": "UVM TLM",
                "https://www.chipverify.com/uvm/uvm-tlm-port": "UVM TLM Port",
                "https://www.chipverify.com/uvm/uvm-tlm-export": "UVM TLM Export",
                "https://www.chipverify.com/uvm/uvm-tlm-imp": "UVM TLM Imp",
                "https://www.chipverify.com/uvm/uvm-tlm-fifo": "UVM TLM FIFO",
                "https://www.chipverify.com/uvm/uvm-analysis-port": "UVM Analysis Port",
                # Factory
                "https://www.chipverify.com/uvm/uvm-factory": "UVM Factory",
                "https://www.chipverify.com/uvm/uvm-factory-override": "UVM Factory Override",
                "https://www.chipverify.com/uvm/uvm-factory-type-override": "UVM Factory Type Override",
                "https://www.chipverify.com/uvm/uvm-factory-instance-override": "UVM Factory Instance Override",
                # Config DB
                "https://www.chipverify.com/uvm/uvm-config-db": "UVM Config DB",
                "https://www.chipverify.com/uvm/uvm-config-db-set": "UVM Config DB Set",
                "https://www.chipverify.com/uvm/uvm-config-db-get": "UVM Config DB Get",
                "https://www.chipverify.com/uvm/uvm-config-db-examples": "UVM Config DB Examples",
                # Phases
                "https://www.chipverify.com/uvm/uvm-phases": "UVM Phases",
                "https://www.chipverify.com/uvm/uvm-build-phase": "UVM Build Phase",
                "https://www.chipverify.com/uvm/uvm-connect-phase": "UVM Connect Phase",
                "https://www.chipverify.com/uvm/uvm-run-phase": "UVM Run Phase",
                "https://www.chipverify.com/uvm/uvm-phase-methods": "UVM Phase Methods",
                # Misc UVM
                "https://www.chipverify.com/uvm/uvm-reporting": "UVM Reporting",
                "https://www.chipverify.com/uvm/uvm-objection": "UVM Objection",
                "https://www.chipverify.com/uvm/uvm-callback": "UVM Callback",
                "https://www.chipverify.com/uvm/uvm-register-model": "UVM Register Model",
                "https://www.chipverify.com/uvm/uvm-reg-block": "UVM Reg Block",
                "https://www.chipverify.com/uvm/uvm-reg-field": "UVM Reg Field",
                "https://www.chipverify.com/uvm/uvm-reg-map": "UVM Reg Map",
                "https://www.chipverify.com/uvm/uvm-reg-adapter": "UVM Reg Adapter",
                "https://www.chipverify.com/uvm/uvm-reg-sequence": "UVM Reg Sequence",
                "https://www.chipverify.com/uvm/uvm-heartbeat": "UVM Heartbeat",
                "https://www.chipverify.com/uvm/uvm-event-pool": "UVM Event Pool",
                "https://www.chipverify.com/uvm/uvm-barrier": "UVM Barrier",
                "https://www.chipverify.com/uvm/uvm-printer": "UVM Printer",
                "https://www.chipverify.com/uvm/uvm-comparer": "UVM Comparer",
                "https://www.chipverify.com/uvm/uvm-packer": "UVM Packer",
            },
        },
    }

    # Index pages to crawl for discovering additional article URLs
    INDEX_URLS = {
        "verilog": "https://www.chipverify.com/verilog/verilog-tutorial",
        "systemverilog": "https://www.chipverify.com/systemverilog/systemverilog-tutorial",
        "uvm": "https://www.chipverify.com/uvm/uvm-tutorial",
    }

    def __init__(self, base_dir, source_key=None):
        name = f"chipverify-{source_key}" if source_key else "chipverify"
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
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [' - ChipVerify', ' | ChipVerify', ' - chipverify']:
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

        # Find all links to articles in this section
        pattern = rf'href=["\'](?:https?://(?:www\.)?chipverify\.com)?(/(?:{section})/([^"\'#]+))["\']'
        matches = re.findall(pattern, content, re.IGNORECASE)

        for path, _ in matches:
            url = f"https://www.chipverify.com{path}"
            # Derive a title from the URL slug
            slug = path.rstrip('/').split('/')[-1]
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
                        "category": f"chipverify-{source_key}",
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
            self.log.info(f"=== Scraping chipverify/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    ChipVerifyScraper(base, source_key).run()
