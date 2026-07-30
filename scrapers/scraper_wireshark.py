#!/usr/bin/env python3
"""Wireshark documentation scraper.

Covers:
  - User guide: introduction, capture, display, filtering, statistics, IO graphs
  - Display filters: reference, syntax, operators, field types
  - Lua API: dissectors, listeners, tvb, tree items, utility functions
  - Man pages: tshark, editcap, mergecap, capinfos, dumpcap, rawshark, text2pcap
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class WiresharkScraper(BaseScraper):
    """Scrape Wireshark official documentation."""

    SOURCES = {
        "user-guide": {
            "pages": {
                "https://www.wireshark.org/docs/wsug_html_chunked/": "Wireshark User's Guide",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChapterIntroduction.html": "Introduction",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChBuildInstall.html": "Building and Installing Wireshark",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChapterUsing.html": "User Interface",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChCapCapture.html": "Capturing Live Network Data",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChCapCaptureFilterSection.html": "Capture Filters",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChCapCaptureOptions.html": "Capture Options",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChCapInterfaceSection.html": "Capture Interface Selection",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChWorkBuildDisplayFilterSection.html": "Building Display Filter Expressions",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChWorkDisplayFilterSection.html": "Filtering Packets While Viewing",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChWorkFindPacketSection.html": "Finding Packets",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChWorkGoToPacketSection.html": "Going to a Specific Packet",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChWorkMarkPacketSection.html": "Marking Packets",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChWorkTimeFormatsSection.html": "Time Display Formats",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChAdvReassembly.html": "Packet Reassembly",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChAdvNameResolutionSection.html": "Name Resolution",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChAdvFollowStreamSection.html": "Following Protocol Streams",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChAdvExpert.html": "Expert Information",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChStatStatistics.html": "Statistics",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChStatSummary.html": "Summary Statistics",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChStatConversations.html": "Conversations",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChStatEndpoints.html": "Endpoints",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChStatIOGraphs.html": "IO Graphs",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChStatFlowGraph.html": "Flow Graph",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChIOFileSetSection.html": "File Sets",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChIOExportSection.html": "Exporting Data",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChIOPrintSection.html": "Printing Packets",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChCustPreferencesSection.html": "Preferences",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChCustColorizationSection.html": "Packet Colorization",
                "https://www.wireshark.org/docs/wsug_html_chunked/ChCustProtocolDissectionSection.html": "Protocol Dissection Settings",
            },
        },
        "display-filters": {
            "pages": {
                "https://www.wireshark.org/docs/dfref/": "Display Filter Reference",
                "https://www.wireshark.org/docs/man-pages/wireshark-filter.html": "Wireshark Filter Syntax",
                "https://www.wireshark.org/docs/dfref/e/eth.html": "Ethernet Display Filters",
                "https://www.wireshark.org/docs/dfref/i/ip.html": "IP Display Filters",
                "https://www.wireshark.org/docs/dfref/t/tcp.html": "TCP Display Filters",
                "https://www.wireshark.org/docs/dfref/u/udp.html": "UDP Display Filters",
                "https://www.wireshark.org/docs/dfref/h/http.html": "HTTP Display Filters",
                "https://www.wireshark.org/docs/dfref/d/dns.html": "DNS Display Filters",
                "https://www.wireshark.org/docs/dfref/t/tls.html": "TLS Display Filters",
                "https://www.wireshark.org/docs/dfref/a/arp.html": "ARP Display Filters",
            },
        },
        "lua-api": {
            "pages": {
                "https://www.wireshark.org/docs/wsdg_html_chunked/wsluarm.html": "Lua Support in Wireshark",
                "https://www.wireshark.org/docs/wsdg_html_chunked/wsluarm_modules.html": "Lua API Reference",
                "https://www.wireshark.org/docs/wsdg_html_chunked/lua_module_Dissector.html": "Dissector Module",
                "https://www.wireshark.org/docs/wsdg_html_chunked/lua_module_Proto.html": "Proto Module",
                "https://www.wireshark.org/docs/wsdg_html_chunked/lua_module_ProtoField.html": "ProtoField Module",
                "https://www.wireshark.org/docs/wsdg_html_chunked/lua_module_Tree.html": "Tree Module",
                "https://www.wireshark.org/docs/wsdg_html_chunked/lua_module_Tvb.html": "Tvb Module",
                "https://www.wireshark.org/docs/wsdg_html_chunked/lua_module_Listener.html": "Listener Module",
                "https://www.wireshark.org/docs/wsdg_html_chunked/lua_module_Pinfo.html": "Pinfo Module",
                "https://www.wireshark.org/docs/wsdg_html_chunked/lua_module_Int64.html": "Int64 Module",
                "https://www.wireshark.org/docs/wsdg_html_chunked/lua_module_GRegex.html": "GRegex Module",
                "https://www.wireshark.org/docs/wsdg_html_chunked/lua_module_Utility.html": "Utility Functions Module",
            },
        },
        "man-pages": {
            "pages": {
                "https://www.wireshark.org/docs/man-pages/wireshark.html": "Wireshark Man Page",
                "https://www.wireshark.org/docs/man-pages/tshark.html": "TShark Man Page",
                "https://www.wireshark.org/docs/man-pages/editcap.html": "Editcap Man Page",
                "https://www.wireshark.org/docs/man-pages/mergecap.html": "Mergecap Man Page",
                "https://www.wireshark.org/docs/man-pages/capinfos.html": "Capinfos Man Page",
                "https://www.wireshark.org/docs/man-pages/dumpcap.html": "Dumpcap Man Page",
                "https://www.wireshark.org/docs/man-pages/rawshark.html": "Rawshark Man Page",
                "https://www.wireshark.org/docs/man-pages/text2pcap.html": "Text2pcap Man Page",
                "https://www.wireshark.org/docs/man-pages/reordercap.html": "Reordercap Man Page",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"wireshark-{source_key}" if source_key else "wireshark"
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
            for suffix in [' - Wireshark', ' | Wireshark',
                           ' - Wireshark Documentation',
                           ' :: Wireshark']:
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
                        "category": f"wireshark-{source_key}",
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
            self.log.info(f"=== Scraping wireshark/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    WiresharkScraper(base, source_key).run()
