#!/usr/bin/env python3
"""ZipCPU blog scraper.

Covers:
  - Blog posts on FPGA design, formal verification, Verilog
  - Formal verification tutorials
  - FPGA design articles and methodology
  - ZipCPU processor design articles

Blog-style site. Enumerates blog post URLs from archive/index pages.

Rate limit: 1.5s between fetches
Est ~200 URLs
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class ZipCpuScraper(BaseScraper):
    """Scrape ZipCPU blog posts and FPGA design tutorials."""

    SOURCES = {
        "blog": {
            "pages": {
                # Formal verification series
                "https://zipcpu.com/blog/2017/10/19/formal-intro.html": "Introduction to Formal Verification",
                "https://zipcpu.com/formal/2018/12/28/axilite.html": "Formally Verifying AXI-Lite",
                "https://zipcpu.com/formal/2019/02/21/avalon.html": "Formally Verifying Avalon",
                "https://zipcpu.com/formal/2018/04/23/axi-protocol.html": "AXI Protocol Formal Verification",
                "https://zipcpu.com/formal/2018/03/10/induction-exercise.html": "Formal Induction Exercise",
                "https://zipcpu.com/formal/2017/10/19/formal-intro.html": "Formal Verification Introduction",
                "https://zipcpu.com/blog/2018/01/22/formal-progress.html": "Formal Verification Progress",
                "https://zipcpu.com/zipcpu/2018/07/13/formal-cpu-bugs.html": "Formal Verification Finds CPU Bugs",
                "https://zipcpu.com/formal/2019/11/18/genuctrl.html": "Generic Unit Controller Formal Verify",
                "https://zipcpu.com/formal/2020/06/12/four-keys.html": "Four Keys to Formal Verification",
                # FPGA design articles
                "https://zipcpu.com/blog/2017/06/02/design-process.html": "FPGA Design Process",
                "https://zipcpu.com/blog/2017/06/12/minimizing-luts.html": "Minimizing LUT Usage",
                "https://zipcpu.com/blog/2017/06/23/my-dbg-philosophy.html": "Debug Philosophy",
                "https://zipcpu.com/blog/2017/07/08/getting-started-with-fpgas.html": "Getting Started with FPGAs",
                "https://zipcpu.com/blog/2017/08/21/rules-for-newbies.html": "Rules for FPGA Newbies",
                "https://zipcpu.com/blog/2017/09/14/even-i-get-stuck.html": "Even I Get Stuck",
                "https://zipcpu.com/blog/2017/10/13/fpga-v-cpu.html": "FPGA vs CPU",
                "https://zipcpu.com/blog/2018/08/04/sim-mismatch.html": "Simulation Mismatch",
                "https://zipcpu.com/blog/2019/05/22/eth-as-iobuf.html": "Ethernet as IO Buffer",
                "https://zipcpu.com/blog/2019/07/17/crossbar.html": "AXI Crossbar Design",
                "https://zipcpu.com/blog/2020/01/13/reuse.html": "Design Reuse",
                # Clock and timing
                "https://zipcpu.com/blog/2017/06/02/generating-timing.html": "Generating Timing",
                "https://zipcpu.com/blog/2017/09/28/multiclk-design.html": "Multi-Clock Design",
                "https://zipcpu.com/blog/2018/07/06/async-fifo.html": "Asynchronous FIFO",
                "https://zipcpu.com/blog/2017/10/20/cdc.html": "Clock Domain Crossing",
                # Bus interfaces
                "https://zipcpu.com/blog/2019/01/12/dma.html": "DMA Controller",
                "https://zipcpu.com/blog/2020/03/08/easyaxil.html": "Easy AXI-Lite",
                "https://zipcpu.com/blog/2019/05/29/demoaxi.html": "Demo AXI Slave",
                "https://zipcpu.com/blog/2021/05/22/vhdlaxil.html": "VHDL AXI-Lite",
                "https://zipcpu.com/blog/2020/06/16/axiaddr-limits.html": "AXI Address Limits",
                "https://zipcpu.com/blog/2020/10/09/wb2axil.html": "Wishbone to AXI-Lite",
                "https://zipcpu.com/blog/2021/08/28/axi-rules.html": "AXI Rules",
                "https://zipcpu.com/blog/2022/01/22/axi-exclusive.html": "AXI Exclusive Access",
                # Wishbone bus
                "https://zipcpu.com/blog/2017/06/08/simple-wb-master.html": "Simple Wishbone Master",
                "https://zipcpu.com/blog/2017/06/15/simple-wb-slave.html": "Simple Wishbone Slave",
                "https://zipcpu.com/blog/2017/06/22/simple-wb-interconnect.html": "Simple Wishbone Interconnect",
                "https://zipcpu.com/blog/2017/11/07/wb-formal.html": "Formal Verifying Wishbone",
                "https://zipcpu.com/zipcpu/2017/11/18/wb-prefetch.html": "Wishbone Prefetch",
                # ZipCPU processor
                "https://zipcpu.com/about/zipcpu.html": "About ZipCPU",
                "https://zipcpu.com/zipcpu/2018/01/01/zipcpu-isa.html": "ZipCPU Instruction Set",
                "https://zipcpu.com/zipcpu/2018/02/12/high-speed.html": "High Speed ZipCPU",
                "https://zipcpu.com/zipcpu/2018/03/21/dblfetch.html": "ZipCPU Double Fetch",
                "https://zipcpu.com/zipcpu/2018/04/13/axilperf.html": "ZipCPU AXI-Lite Performance",
                "https://zipcpu.com/zipcpu/2019/01/18/alu-verification.html": "ZipCPU ALU Verification",
                "https://zipcpu.com/zipcpu/2019/03/12/prefetch.html": "ZipCPU Prefetch",
                "https://zipcpu.com/zipcpu/2019/09/03/cpu-pipeline.html": "ZipCPU Pipeline",
                # DSP articles
                "https://zipcpu.com/dsp/2017/07/11/simplest-sinewave-generator.html": "Simplest Sinewave Generator",
                "https://zipcpu.com/dsp/2017/08/26/quarterwave.html": "Quarter Wave Sinewave",
                "https://zipcpu.com/dsp/2017/09/01/generating-sinewave.html": "Generating a Sinewave",
                "https://zipcpu.com/dsp/2017/09/15/fastfir.html": "Fast FIR Filter",
                "https://zipcpu.com/dsp/2017/10/16/boxcar.html": "Boxcar Filter",
                "https://zipcpu.com/dsp/2017/11/04/genfir-config.html": "Generic FIR Configuration",
                "https://zipcpu.com/dsp/2017/11/10/delayw.html": "Delay Filter",
                "https://zipcpu.com/dsp/2017/11/22/fltr-discovery.html": "Filter Discovery",
                "https://zipcpu.com/dsp/2017/12/06/fft-in-fpga.html": "FFT in an FPGA",
                "https://zipcpu.com/dsp/2018/02/14/fft-extra.html": "FFT Extra Bits",
                "https://zipcpu.com/dsp/2018/10/02/fft.html": "FFT",
                "https://zipcpu.com/dsp/2020/06/15/fft-demo.html": "FFT Demo",
                # Serial interfaces
                "https://zipcpu.com/blog/2017/06/16/dbg-bus-overview.html": "Debug Bus Overview",
                "https://zipcpu.com/blog/2017/06/29/sw-dev-process.html": "Software Development Process",
                "https://zipcpu.com/blog/2017/07/08/serialport.html": "Serial Port",
                "https://zipcpu.com/blog/2017/07/31/vcd.html": "VCD Trace Files",
                # Video
                "https://zipcpu.com/blog/2018/11/29/llvga.html": "Low Latency VGA",
                "https://zipcpu.com/blog/2019/06/07/hdmi.html": "HDMI Interface",
                # Memory interfaces
                "https://zipcpu.com/blog/2019/03/27/qflexpress.html": "Quad SPI Flash",
                "https://zipcpu.com/blog/2020/01/20/lfsr-access.html": "LFSR Random Access",
                "https://zipcpu.com/blog/2020/04/01/ddrdma.html": "DDR DMA",
                # Simulation and testing
                "https://zipcpu.com/blog/2017/06/21/looking-at-verilator.html": "Looking at Verilator",
                "https://zipcpu.com/blog/2017/06/28/hw-debugging.html": "Hardware Debugging",
                "https://zipcpu.com/blog/2018/08/22/what-is-simulation.html": "What is Simulation",
                "https://zipcpu.com/blog/2018/09/06/tbclock.html": "Testbench Clocking",
                "https://zipcpu.com/blog/2020/12/22/tb-method.html": "Testbench Methodology",
                # Makefile and tool-related
                "https://zipcpu.com/blog/2017/10/05/autofpga-intro.html": "AutoFPGA Introduction",
                "https://zipcpu.com/blog/2017/11/03/autofpga-data.html": "AutoFPGA Data Files",
                "https://zipcpu.com/blog/2018/10/05/autofpga-icoboard.html": "AutoFPGA ICO Board",
                # Peripheral design
                "https://zipcpu.com/blog/2017/05/26/simplebus.html": "Simple Bus Design",
                "https://zipcpu.com/blog/2017/07/29/fifo.html": "FIFO Design",
                "https://zipcpu.com/blog/2017/08/14/strategies-for-pipelining.html": "Strategies for Pipelining",
                "https://zipcpu.com/blog/2021/01/29/axis-homogeneous.html": "AXI Stream Homogeneous",
            },
        },
        "formal": {
            "pages": {
                # Dedicated formal verification section
                "https://zipcpu.com/formal/formal.html": "Formal Verification Portal",
                "https://zipcpu.com/blog/2017/10/19/formal-intro.html": "Formal Intro Blog Post",
                "https://zipcpu.com/formal/2018/04/23/axi-protocol.html": "Formal AXI Protocol",
                "https://zipcpu.com/formal/2018/12/28/axilite.html": "Formal AXI-Lite",
                "https://zipcpu.com/formal/2019/02/21/avalon.html": "Formal Avalon Bus",
                "https://zipcpu.com/formal/2018/03/10/induction-exercise.html": "Formal Induction Exercise",
                "https://zipcpu.com/formal/2019/11/18/genuctrl.html": "Formal Generic Unit Controller",
                "https://zipcpu.com/formal/2020/06/12/four-keys.html": "Four Keys Formal Verification",
                "https://zipcpu.com/blog/2017/11/07/wb-formal.html": "Wishbone Formal",
            },
        },
    }

    # Archive pages to crawl for discovering additional blog post URLs
    ARCHIVE_URLS = [
        "https://zipcpu.com/",
        "https://zipcpu.com/blog/",
        "https://zipcpu.com/dsp/dsp.html",
        "https://zipcpu.com/formal/formal.html",
        "https://zipcpu.com/zipcpu/zipcpu.html",
    ]

    def __init__(self, base_dir, source_key=None):
        name = f"zipcpu-{source_key}" if source_key else "zipcpu"
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
            for suffix in [' - ZipCPU', ' | ZipCPU', " - The Zip CPU's blog",
                           " - ZipCPU Blog", " | The Zip CPU's blog"]:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _discover_blog_urls(self):
        """Crawl archive/index pages to discover blog post URLs."""
        discovered = {}

        for archive_url in self.ARCHIVE_URLS:
            if not self.running:
                break

            content = self.fetch_url(archive_url)
            if not content:
                continue

            # Find all links to blog posts (pattern: /category/YYYY/MM/DD/slug.html)
            pattern = r'href=["\'](?:https?://zipcpu\.com)?((?:/blog|/dsp|/formal|/zipcpu)/\d{4}/\d{2}/\d{2}/[^"\'#]+\.html)["\']'
            matches = re.findall(pattern, content, re.IGNORECASE)

            for path in matches:
                url = f"https://zipcpu.com{path}"
                slug = path.rstrip('/').split('/')[-1].replace('.html', '')
                title = slug.replace('-', ' ').title()
                if url not in discovered:
                    discovered[url] = title

            time.sleep(1.5)

        self.log.info(f"  Discovered {len(discovered)} blog post URLs from archives")
        return discovered

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = dict(config.get("pages", {}))

        # For blog section, also discover URLs from archive pages
        if source_key == "blog":
            discovered = self._discover_blog_urls()
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
                        "category": f"zipcpu-{source_key}",
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
            self.log.info(f"=== Scraping zipcpu/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    ZipCpuScraper(base, source_key).run()
