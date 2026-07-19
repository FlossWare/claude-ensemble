#!/usr/bin/env python3
"""ASIC World documentation scraper.

Covers:
  - Verilog tutorials and reference
  - VHDL tutorials and reference
  - SystemVerilog tutorials
  - Synthesis guides
  - Timing analysis
  - Scripting (Perl/Tcl for EDA)
  - Digital design fundamentals

Rate limit: 1.5s between fetches
Est ~400 URLs
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class AsicWorldScraper(BaseScraper):
    """Scrape ASIC World Verilog, VHDL, SystemVerilog, and EDA tutorials."""

    SOURCES = {
        "verilog": {
            "pages": {
                # Verilog tutorial index and basics
                "https://www.asic-world.com/verilog/veritut.html": "Verilog Tutorial Index",
                "https://www.asic-world.com/verilog/intro.html": "Verilog Introduction",
                "https://www.asic-world.com/verilog/history.html": "Verilog History",
                "https://www.asic-world.com/verilog/design.html": "Verilog Design Methodology",
                "https://www.asic-world.com/verilog/syntax.html": "Verilog Syntax",
                "https://www.asic-world.com/verilog/data1.html": "Verilog Data Types Part 1",
                "https://www.asic-world.com/verilog/data2.html": "Verilog Data Types Part 2",
                "https://www.asic-world.com/verilog/data3.html": "Verilog Data Types Part 3",
                "https://www.asic-world.com/verilog/data4.html": "Verilog Data Types Part 4",
                "https://www.asic-world.com/verilog/module.html": "Verilog Module",
                "https://www.asic-world.com/verilog/port.html": "Verilog Ports",
                "https://www.asic-world.com/verilog/operator1.html": "Verilog Operators Part 1",
                "https://www.asic-world.com/verilog/operator2.html": "Verilog Operators Part 2",
                "https://www.asic-world.com/verilog/operator3.html": "Verilog Operators Part 3",
                "https://www.asic-world.com/verilog/control1.html": "Verilog Control Statements Part 1",
                "https://www.asic-world.com/verilog/control2.html": "Verilog Control Statements Part 2",
                "https://www.asic-world.com/verilog/assign.html": "Verilog Assign",
                "https://www.asic-world.com/verilog/always.html": "Verilog Always Block",
                "https://www.asic-world.com/verilog/initial.html": "Verilog Initial Block",
                "https://www.asic-world.com/verilog/gate1.html": "Verilog Gate Level Part 1",
                "https://www.asic-world.com/verilog/gate2.html": "Verilog Gate Level Part 2",
                "https://www.asic-world.com/verilog/gate3.html": "Verilog Gate Level Part 3",
                "https://www.asic-world.com/verilog/gate4.html": "Verilog Gate Level Part 4",
                "https://www.asic-world.com/verilog/gate5.html": "Verilog Gate Level Part 5",
                "https://www.asic-world.com/verilog/task.html": "Verilog Tasks",
                "https://www.asic-world.com/verilog/func1.html": "Verilog Functions Part 1",
                "https://www.asic-world.com/verilog/func2.html": "Verilog Functions Part 2",
                "https://www.asic-world.com/verilog/delay.html": "Verilog Delays",
                "https://www.asic-world.com/verilog/param.html": "Verilog Parameters",
                "https://www.asic-world.com/verilog/udp.html": "Verilog UDP",
                "https://www.asic-world.com/verilog/pli.html": "Verilog PLI",
                "https://www.asic-world.com/verilog/pli2.html": "Verilog PLI Part 2",
                "https://www.asic-world.com/verilog/pli3.html": "Verilog PLI Part 3",
                "https://www.asic-world.com/verilog/pli4.html": "Verilog PLI Part 4",
                "https://www.asic-world.com/verilog/pli5.html": "Verilog PLI Part 5",
                # Testbench and simulation
                "https://www.asic-world.com/verilog/test1.html": "Verilog Testbench Part 1",
                "https://www.asic-world.com/verilog/test2.html": "Verilog Testbench Part 2",
                "https://www.asic-world.com/verilog/test3.html": "Verilog Testbench Part 3",
                "https://www.asic-world.com/verilog/test4.html": "Verilog Testbench Part 4",
                "https://www.asic-world.com/verilog/file_io.html": "Verilog File IO",
                "https://www.asic-world.com/verilog/system.html": "Verilog System Tasks",
                "https://www.asic-world.com/verilog/display.html": "Verilog Display Tasks",
                "https://www.asic-world.com/verilog/compiler1.html": "Verilog Compiler Directives Part 1",
                "https://www.asic-world.com/verilog/compiler2.html": "Verilog Compiler Directives Part 2",
                # Design examples
                "https://www.asic-world.com/verilog/counter.html": "Verilog Counter",
                "https://www.asic-world.com/verilog/mux.html": "Verilog Multiplexer",
                "https://www.asic-world.com/verilog/decoder.html": "Verilog Decoder",
                "https://www.asic-world.com/verilog/encoder.html": "Verilog Encoder",
                "https://www.asic-world.com/verilog/parity.html": "Verilog Parity",
                "https://www.asic-world.com/verilog/fifo.html": "Verilog FIFO",
                "https://www.asic-world.com/verilog/memory.html": "Verilog Memory",
                "https://www.asic-world.com/verilog/fsm1.html": "Verilog FSM Part 1",
                "https://www.asic-world.com/verilog/fsm2.html": "Verilog FSM Part 2",
                "https://www.asic-world.com/verilog/fsm3.html": "Verilog FSM Part 3",
                "https://www.asic-world.com/verilog/fsm4.html": "Verilog FSM Part 4",
                "https://www.asic-world.com/verilog/cpu.html": "Verilog CPU Design",
                "https://www.asic-world.com/verilog/art_fault.html": "Verilog Fault Simulation",
                # Verilog 2001
                "https://www.asic-world.com/verilog/v2001.html": "Verilog-2001 Features",
                "https://www.asic-world.com/verilog/v2001_2.html": "Verilog-2001 Part 2",
                "https://www.asic-world.com/verilog/v2001_3.html": "Verilog-2001 Part 3",
            },
        },
        "vhdl": {
            "pages": {
                "https://www.asic-world.com/vhdl/index.html": "VHDL Tutorial Index",
                "https://www.asic-world.com/vhdl/intro.html": "VHDL Introduction",
                "https://www.asic-world.com/vhdl/history.html": "VHDL History",
                "https://www.asic-world.com/vhdl/syntax.html": "VHDL Syntax",
                "https://www.asic-world.com/vhdl/data1.html": "VHDL Data Types Part 1",
                "https://www.asic-world.com/vhdl/data2.html": "VHDL Data Types Part 2",
                "https://www.asic-world.com/vhdl/data3.html": "VHDL Data Types Part 3",
                "https://www.asic-world.com/vhdl/entity.html": "VHDL Entity",
                "https://www.asic-world.com/vhdl/arch.html": "VHDL Architecture",
                "https://www.asic-world.com/vhdl/signal.html": "VHDL Signals",
                "https://www.asic-world.com/vhdl/process.html": "VHDL Process",
                "https://www.asic-world.com/vhdl/operator.html": "VHDL Operators",
                "https://www.asic-world.com/vhdl/control.html": "VHDL Control Statements",
                "https://www.asic-world.com/vhdl/func.html": "VHDL Functions",
                "https://www.asic-world.com/vhdl/procedure.html": "VHDL Procedures",
                "https://www.asic-world.com/vhdl/package.html": "VHDL Packages",
                "https://www.asic-world.com/vhdl/component.html": "VHDL Components",
                "https://www.asic-world.com/vhdl/generate.html": "VHDL Generate",
                "https://www.asic-world.com/vhdl/generic.html": "VHDL Generics",
                "https://www.asic-world.com/vhdl/config.html": "VHDL Configuration",
                "https://www.asic-world.com/vhdl/test.html": "VHDL Testbench",
                "https://www.asic-world.com/vhdl/test2.html": "VHDL Testbench Part 2",
                "https://www.asic-world.com/vhdl/file_io.html": "VHDL File IO",
                "https://www.asic-world.com/vhdl/record.html": "VHDL Records",
                "https://www.asic-world.com/vhdl/array.html": "VHDL Arrays",
                "https://www.asic-world.com/vhdl/assert.html": "VHDL Assert",
                "https://www.asic-world.com/vhdl/attribute.html": "VHDL Attributes",
                "https://www.asic-world.com/vhdl/library.html": "VHDL Libraries",
                "https://www.asic-world.com/vhdl/fsm.html": "VHDL FSM",
                "https://www.asic-world.com/vhdl/fsm2.html": "VHDL FSM Part 2",
                "https://www.asic-world.com/vhdl/counter.html": "VHDL Counter",
                "https://www.asic-world.com/vhdl/mux.html": "VHDL Multiplexer",
                "https://www.asic-world.com/vhdl/decoder.html": "VHDL Decoder",
                "https://www.asic-world.com/vhdl/fifo.html": "VHDL FIFO",
                "https://www.asic-world.com/vhdl/memory.html": "VHDL Memory",
            },
        },
        "systemverilog": {
            "pages": {
                "https://www.asic-world.com/systemverilog/index.html": "SystemVerilog Tutorial Index",
                "https://www.asic-world.com/systemverilog/intro.html": "SystemVerilog Introduction",
                "https://www.asic-world.com/systemverilog/data1.html": "SystemVerilog Data Types Part 1",
                "https://www.asic-world.com/systemverilog/data2.html": "SystemVerilog Data Types Part 2",
                "https://www.asic-world.com/systemverilog/data3.html": "SystemVerilog Data Types Part 3",
                "https://www.asic-world.com/systemverilog/data4.html": "SystemVerilog Data Types Part 4",
                "https://www.asic-world.com/systemverilog/operators.html": "SystemVerilog Operators",
                "https://www.asic-world.com/systemverilog/procedural1.html": "SystemVerilog Procedural Part 1",
                "https://www.asic-world.com/systemverilog/procedural2.html": "SystemVerilog Procedural Part 2",
                "https://www.asic-world.com/systemverilog/interface.html": "SystemVerilog Interface",
                "https://www.asic-world.com/systemverilog/interface2.html": "SystemVerilog Interface Part 2",
                "https://www.asic-world.com/systemverilog/class1.html": "SystemVerilog Classes Part 1",
                "https://www.asic-world.com/systemverilog/class2.html": "SystemVerilog Classes Part 2",
                "https://www.asic-world.com/systemverilog/class3.html": "SystemVerilog Classes Part 3",
                "https://www.asic-world.com/systemverilog/random1.html": "SystemVerilog Randomization Part 1",
                "https://www.asic-world.com/systemverilog/random2.html": "SystemVerilog Randomization Part 2",
                "https://www.asic-world.com/systemverilog/assert1.html": "SystemVerilog Assertions Part 1",
                "https://www.asic-world.com/systemverilog/assert2.html": "SystemVerilog Assertions Part 2",
                "https://www.asic-world.com/systemverilog/assert3.html": "SystemVerilog Assertions Part 3",
                "https://www.asic-world.com/systemverilog/coverage1.html": "SystemVerilog Coverage Part 1",
                "https://www.asic-world.com/systemverilog/coverage2.html": "SystemVerilog Coverage Part 2",
                "https://www.asic-world.com/systemverilog/thread1.html": "SystemVerilog Threads Part 1",
                "https://www.asic-world.com/systemverilog/thread2.html": "SystemVerilog Threads Part 2",
                "https://www.asic-world.com/systemverilog/mailbox.html": "SystemVerilog Mailbox",
                "https://www.asic-world.com/systemverilog/semaphore.html": "SystemVerilog Semaphore",
                "https://www.asic-world.com/systemverilog/event.html": "SystemVerilog Events",
                "https://www.asic-world.com/systemverilog/program.html": "SystemVerilog Program Block",
                "https://www.asic-world.com/systemverilog/clocking.html": "SystemVerilog Clocking Block",
                "https://www.asic-world.com/systemverilog/dpi1.html": "SystemVerilog DPI Part 1",
                "https://www.asic-world.com/systemverilog/dpi2.html": "SystemVerilog DPI Part 2",
            },
        },
        "synthesis": {
            "pages": {
                "https://www.asic-world.com/synthesis/index.html": "Synthesis Tutorial Index",
                "https://www.asic-world.com/synthesis/intro.html": "Synthesis Introduction",
                "https://www.asic-world.com/synthesis/flow.html": "Synthesis Flow",
                "https://www.asic-world.com/synthesis/synth1.html": "Synthesis Part 1",
                "https://www.asic-world.com/synthesis/synth2.html": "Synthesis Part 2",
                "https://www.asic-world.com/synthesis/synth3.html": "Synthesis Part 3",
                "https://www.asic-world.com/synthesis/synth4.html": "Synthesis Part 4",
                "https://www.asic-world.com/synthesis/synth5.html": "Synthesis Part 5",
                "https://www.asic-world.com/synthesis/synth6.html": "Synthesis Part 6",
                "https://www.asic-world.com/synthesis/synth7.html": "Synthesis Part 7",
                "https://www.asic-world.com/synthesis/synth8.html": "Synthesis Part 8",
                "https://www.asic-world.com/synthesis/synth9.html": "Synthesis Part 9",
                "https://www.asic-world.com/synthesis/coding.html": "Synthesis Coding Guidelines",
                "https://www.asic-world.com/synthesis/gate.html": "Synthesis Gate Level",
                "https://www.asic-world.com/synthesis/timing.html": "Synthesis Timing",
            },
        },
        "timing": {
            "pages": {
                "https://www.asic-world.com/timing/index.html": "Timing Analysis Index",
                "https://www.asic-world.com/timing/intro.html": "Timing Analysis Introduction",
                "https://www.asic-world.com/timing/sta1.html": "Static Timing Analysis Part 1",
                "https://www.asic-world.com/timing/sta2.html": "Static Timing Analysis Part 2",
                "https://www.asic-world.com/timing/sta3.html": "Static Timing Analysis Part 3",
                "https://www.asic-world.com/timing/sta4.html": "Static Timing Analysis Part 4",
                "https://www.asic-world.com/timing/sta5.html": "Static Timing Analysis Part 5",
                "https://www.asic-world.com/timing/sdf1.html": "SDF Part 1",
                "https://www.asic-world.com/timing/sdf2.html": "SDF Part 2",
                "https://www.asic-world.com/timing/sdf3.html": "SDF Part 3",
                "https://www.asic-world.com/timing/delay1.html": "Timing Delay Part 1",
                "https://www.asic-world.com/timing/delay2.html": "Timing Delay Part 2",
                "https://www.asic-world.com/timing/clock.html": "Clock Analysis",
                "https://www.asic-world.com/timing/setup_hold.html": "Setup and Hold Times",
                "https://www.asic-world.com/timing/cdc.html": "Clock Domain Crossing",
            },
        },
        "scripting": {
            "pages": {
                "https://www.asic-world.com/scripting/index.html": "Scripting Tutorial Index",
                "https://www.asic-world.com/scripting/perl1.html": "Perl for EDA Part 1",
                "https://www.asic-world.com/scripting/perl2.html": "Perl for EDA Part 2",
                "https://www.asic-world.com/scripting/perl3.html": "Perl for EDA Part 3",
                "https://www.asic-world.com/scripting/perl4.html": "Perl for EDA Part 4",
                "https://www.asic-world.com/scripting/perl5.html": "Perl for EDA Part 5",
                "https://www.asic-world.com/scripting/perl6.html": "Perl for EDA Part 6",
                "https://www.asic-world.com/scripting/perl7.html": "Perl for EDA Part 7",
                "https://www.asic-world.com/scripting/tcl1.html": "Tcl for EDA Part 1",
                "https://www.asic-world.com/scripting/tcl2.html": "Tcl for EDA Part 2",
                "https://www.asic-world.com/scripting/tcl3.html": "Tcl for EDA Part 3",
                "https://www.asic-world.com/scripting/tcl4.html": "Tcl for EDA Part 4",
                "https://www.asic-world.com/scripting/tcl5.html": "Tcl for EDA Part 5",
                "https://www.asic-world.com/scripting/tcl6.html": "Tcl for EDA Part 6",
                "https://www.asic-world.com/scripting/tcl7.html": "Tcl for EDA Part 7",
            },
        },
        "digital": {
            "pages": {
                "https://www.asic-world.com/digital/index.html": "Digital Design Index",
                "https://www.asic-world.com/digital/intro.html": "Digital Design Introduction",
                "https://www.asic-world.com/digital/gates.html": "Digital Gates",
                "https://www.asic-world.com/digital/boolean.html": "Boolean Algebra",
                "https://www.asic-world.com/digital/combo.html": "Combinational Logic",
                "https://www.asic-world.com/digital/combo2.html": "Combinational Logic Part 2",
                "https://www.asic-world.com/digital/combo3.html": "Combinational Logic Part 3",
                "https://www.asic-world.com/digital/seq.html": "Sequential Logic",
                "https://www.asic-world.com/digital/seq2.html": "Sequential Logic Part 2",
                "https://www.asic-world.com/digital/seq3.html": "Sequential Logic Part 3",
                "https://www.asic-world.com/digital/d_flop.html": "D Flip-Flop",
                "https://www.asic-world.com/digital/jk_flop.html": "JK Flip-Flop",
                "https://www.asic-world.com/digital/t_flop.html": "T Flip-Flop",
                "https://www.asic-world.com/digital/counter.html": "Digital Counter",
                "https://www.asic-world.com/digital/mux.html": "Digital Multiplexer",
                "https://www.asic-world.com/digital/demux.html": "Digital Demultiplexer",
                "https://www.asic-world.com/digital/decoder.html": "Digital Decoder",
                "https://www.asic-world.com/digital/encoder.html": "Digital Encoder",
                "https://www.asic-world.com/digital/adder.html": "Digital Adder",
                "https://www.asic-world.com/digital/subtractor.html": "Digital Subtractor",
                "https://www.asic-world.com/digital/comparator.html": "Digital Comparator",
                "https://www.asic-world.com/digital/shift_reg.html": "Digital Shift Register",
                "https://www.asic-world.com/digital/ram.html": "Digital RAM",
                "https://www.asic-world.com/digital/rom.html": "Digital ROM",
                "https://www.asic-world.com/digital/number.html": "Number Systems",
                "https://www.asic-world.com/digital/number2.html": "Number Systems Part 2",
            },
        },
    }

    # Index pages to crawl for discovering additional article URLs
    INDEX_URLS = {
        "verilog": "https://www.asic-world.com/verilog/veritut.html",
        "vhdl": "https://www.asic-world.com/vhdl/index.html",
        "systemverilog": "https://www.asic-world.com/systemverilog/index.html",
        "synthesis": "https://www.asic-world.com/synthesis/index.html",
        "timing": "https://www.asic-world.com/timing/index.html",
        "scripting": "https://www.asic-world.com/scripting/index.html",
        "digital": "https://www.asic-world.com/digital/index.html",
    }

    def __init__(self, base_dir, source_key=None):
        name = f"asicworld-{source_key}" if source_key else "asicworld"
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
            for suffix in [' - ASIC World', ' | ASIC World', ' - asic-world.com',
                           ' :: ASIC World', ' :: asic-world.com']:
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
        pattern = rf'href=["\'](?:https?://(?:www\.)?asic-world\.com)?(/(?:{section})/([^"\'#]+\.html))["\']'
        matches = re.findall(pattern, content, re.IGNORECASE)

        for path, _ in matches:
            url = f"https://www.asic-world.com{path}"
            slug = path.rstrip('/').split('/')[-1].replace('.html', '')
            title = slug.replace('_', ' ').replace('-', ' ').title()
            if url not in discovered:
                discovered[url] = f"ASIC World {section.title()} - {title}"

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
                        "category": f"asicworld-{source_key}",
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
            self.log.info(f"=== Scraping asicworld/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    AsicWorldScraper(base, source_key).run()
