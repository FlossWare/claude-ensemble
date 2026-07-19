#!/usr/bin/env python3
"""FPGA4Fun documentation scraper.

Covers:
  - FPGA introduction and basics
  - Music box project tutorials
  - Pong game project tutorials
  - Serial interface (RS-232, SPI, I2C)
  - Ethernet
  - PCI bus
  - SDRAM controller
  - HDMI
  - JTAG

Rate limit: 1.5s between fetches
Est ~80 URLs
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class Fpga4FunScraper(BaseScraper):
    """Scrape FPGA4Fun project-based FPGA tutorials."""

    SOURCES = {
        "fpga-intro": {
            "pages": {
                "https://www.fpga4fun.com/": "FPGA4Fun Home",
                "https://www.fpga4fun.com/FPGAinfo1.html": "FPGA Info 1 - What is an FPGA",
                "https://www.fpga4fun.com/FPGAinfo2.html": "FPGA Info 2 - How FPGAs Work",
                "https://www.fpga4fun.com/FPGAinfo3.html": "FPGA Info 3 - Internal Structure",
                "https://www.fpga4fun.com/FPGAinfo4.html": "FPGA Info 4 - Design Flow",
                "https://www.fpga4fun.com/FPGAinfo5.html": "FPGA Info 5 - Programming",
                "https://www.fpga4fun.com/Counters.html": "Counters",
                "https://www.fpga4fun.com/Counters1.html": "Counters Part 1",
                "https://www.fpga4fun.com/Counters2.html": "Counters Part 2",
                "https://www.fpga4fun.com/Counters3.html": "Counters Part 3",
                "https://www.fpga4fun.com/PWM_DAC.html": "PWM DAC",
                "https://www.fpga4fun.com/PWM_DAC2.html": "PWM DAC Part 2",
                "https://www.fpga4fun.com/PWM_DAC3.html": "PWM DAC Part 3",
            },
        },
        "music-box": {
            "pages": {
                "https://www.fpga4fun.com/MusicBox.html": "Music Box Introduction",
                "https://www.fpga4fun.com/MusicBox1.html": "Music Box Part 1",
                "https://www.fpga4fun.com/MusicBox2.html": "Music Box Part 2",
                "https://www.fpga4fun.com/MusicBox3.html": "Music Box Part 3",
                "https://www.fpga4fun.com/MusicBox4.html": "Music Box Part 4",
                "https://www.fpga4fun.com/MusicBox5.html": "Music Box Part 5",
                "https://www.fpga4fun.com/MusicBox6.html": "Music Box Part 6",
                "https://www.fpga4fun.com/MusicBox7.html": "Music Box Part 7",
                "https://www.fpga4fun.com/MusicBox8.html": "Music Box Part 8",
                "https://www.fpga4fun.com/MusicBox9.html": "Music Box Part 9",
                "https://www.fpga4fun.com/MusicBox10.html": "Music Box Part 10",
                "https://www.fpga4fun.com/MusicBox11.html": "Music Box Part 11",
            },
        },
        "pong-game": {
            "pages": {
                "https://www.fpga4fun.com/PongGame.html": "Pong Game Introduction",
                "https://www.fpga4fun.com/PongGame1.html": "Pong Game Part 1 - VGA",
                "https://www.fpga4fun.com/PongGame2.html": "Pong Game Part 2 - Ball",
                "https://www.fpga4fun.com/PongGame3.html": "Pong Game Part 3 - Paddle",
                "https://www.fpga4fun.com/PongGame4.html": "Pong Game Part 4 - Scoring",
            },
        },
        "serial-interface": {
            "pages": {
                "https://www.fpga4fun.com/SerialInterface.html": "Serial Interface Introduction",
                "https://www.fpga4fun.com/SerialInterface1.html": "Serial Interface Part 1 - RS-232",
                "https://www.fpga4fun.com/SerialInterface2.html": "Serial Interface Part 2 - Receiver",
                "https://www.fpga4fun.com/SerialInterface3.html": "Serial Interface Part 3 - Transmitter",
                "https://www.fpga4fun.com/SerialInterface4.html": "Serial Interface Part 4 - Loopback",
                "https://www.fpga4fun.com/SPI.html": "SPI Introduction",
                "https://www.fpga4fun.com/SPI1.html": "SPI Part 1",
                "https://www.fpga4fun.com/SPI2.html": "SPI Part 2",
                "https://www.fpga4fun.com/SPI3.html": "SPI Part 3",
                "https://www.fpga4fun.com/I2C.html": "I2C Introduction",
                "https://www.fpga4fun.com/I2C1.html": "I2C Part 1",
                "https://www.fpga4fun.com/I2C2.html": "I2C Part 2",
            },
        },
        "ethernet": {
            "pages": {
                "https://www.fpga4fun.com/10BASE-T.html": "10BASE-T Introduction",
                "https://www.fpga4fun.com/10BASE-T0.html": "10BASE-T Part 0 - Physical Layer",
                "https://www.fpga4fun.com/10BASE-T1.html": "10BASE-T Part 1 - Wiring",
                "https://www.fpga4fun.com/10BASE-T2.html": "10BASE-T Part 2 - Manchester",
                "https://www.fpga4fun.com/10BASE-T3.html": "10BASE-T Part 3 - Receiver",
                "https://www.fpga4fun.com/10BASE-T4.html": "10BASE-T Part 4 - Transmitter",
                "https://www.fpga4fun.com/10BASE-T5.html": "10BASE-T Part 5 - Packets",
                "https://www.fpga4fun.com/10BASE-T6.html": "10BASE-T Part 6 - Ping",
            },
        },
        "pci": {
            "pages": {
                "https://www.fpga4fun.com/PCI.html": "PCI Introduction",
                "https://www.fpga4fun.com/PCI1.html": "PCI Part 1 - Bus Signals",
                "https://www.fpga4fun.com/PCI2.html": "PCI Part 2 - Protocol",
                "https://www.fpga4fun.com/PCI3.html": "PCI Part 3 - Target",
                "https://www.fpga4fun.com/PCI4.html": "PCI Part 4 - Master",
                "https://www.fpga4fun.com/PCI5.html": "PCI Part 5 - Configuration",
            },
        },
        "sdram": {
            "pages": {
                "https://www.fpga4fun.com/SDRAM.html": "SDRAM Introduction",
                "https://www.fpga4fun.com/SDRAM1.html": "SDRAM Part 1 - Architecture",
                "https://www.fpga4fun.com/SDRAM2.html": "SDRAM Part 2 - Read/Write",
                "https://www.fpga4fun.com/SDRAM3.html": "SDRAM Part 3 - Controller",
            },
        },
        "hdmi": {
            "pages": {
                "https://www.fpga4fun.com/HDMI.html": "HDMI Introduction",
                "https://www.fpga4fun.com/HDMI1.html": "HDMI Part 1 - TMDS",
                "https://www.fpga4fun.com/HDMI2.html": "HDMI Part 2 - Video",
                "https://www.fpga4fun.com/HDMI3.html": "HDMI Part 3 - Audio",
                "https://www.fpga4fun.com/HDMI4.html": "HDMI Part 4 - Implementation",
            },
        },
        "jtag": {
            "pages": {
                "https://www.fpga4fun.com/JTAG.html": "JTAG Introduction",
                "https://www.fpga4fun.com/JTAG1.html": "JTAG Part 1 - TAP Controller",
                "https://www.fpga4fun.com/JTAG2.html": "JTAG Part 2 - Registers",
                "https://www.fpga4fun.com/JTAG3.html": "JTAG Part 3 - Boundary Scan",
                "https://www.fpga4fun.com/JTAG4.html": "JTAG Part 4 - Debugging",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"fpga4fun-{source_key}" if source_key else "fpga4fun"
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
            for suffix in [' - FPGA4Fun', ' | FPGA4Fun', ' - fpga4fun.com',
                           ' - FPGA4fun.com', ' :: FPGA4Fun']:
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
                        "category": f"fpga4fun-{source_key}",
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
            self.log.info(f"=== Scraping fpga4fun/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    Fpga4FunScraper(base, source_key).run()
