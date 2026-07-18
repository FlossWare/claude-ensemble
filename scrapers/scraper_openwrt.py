#!/usr/bin/env python3
"""OpenWrt documentation scraper.

Covers:
  - OpenWrt wiki/docs (installation, configuration, hardware)
  - OpenWrt packages (package index and descriptions)
  - OpenWrt forum topics (community discussions)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class OpenWrtScraper(BaseScraper):
    """Scrape OpenWrt wiki, package docs, and forum topics."""

    SOURCES = {
        "docs": {
            "pages": {
                # Getting started
                "https://openwrt.org/docs/start": "OpenWrt Documentation Start",
                "https://openwrt.org/docs/guide-quick-start/start": "OpenWrt Quick Start Guide",
                "https://openwrt.org/docs/guide-quick-start/factory_installation": "OpenWrt Factory Installation",
                "https://openwrt.org/docs/guide-quick-start/ssid_sniffing": "OpenWrt SSID Sniffing",
                "https://openwrt.org/docs/guide-quick-start/walkthrough_login": "OpenWrt Login Walkthrough",
                "https://openwrt.org/docs/guide-quick-start/webadmingui": "OpenWrt Web Admin GUI",
                # User guide
                "https://openwrt.org/docs/guide-user/start": "OpenWrt User Guide",
                "https://openwrt.org/docs/guide-user/base-system/start": "OpenWrt Base System",
                "https://openwrt.org/docs/guide-user/base-system/uci": "OpenWrt UCI System",
                "https://openwrt.org/docs/guide-user/base-system/system_configuration": "OpenWrt System Configuration",
                "https://openwrt.org/docs/guide-user/base-system/dropbear": "OpenWrt Dropbear SSH",
                "https://openwrt.org/docs/guide-user/base-system/cron": "OpenWrt Cron",
                "https://openwrt.org/docs/guide-user/base-system/log.essentials": "OpenWrt Logging",
                # Networking
                "https://openwrt.org/docs/guide-user/network/start": "OpenWrt Network Guide",
                "https://openwrt.org/docs/guide-user/network/ip_configuration": "OpenWrt IP Configuration",
                "https://openwrt.org/docs/guide-user/network/ipv6/start": "OpenWrt IPv6",
                "https://openwrt.org/docs/guide-user/network/wifi/start": "OpenWrt WiFi",
                "https://openwrt.org/docs/guide-user/network/wifi/basic": "OpenWrt WiFi Basic Setup",
                "https://openwrt.org/docs/guide-user/network/wifi/encryption": "OpenWrt WiFi Encryption",
                "https://openwrt.org/docs/guide-user/network/wifi/connect_client_wifi": "OpenWrt WiFi Client",
                "https://openwrt.org/docs/guide-user/network/vlan/start": "OpenWrt VLANs",
                "https://openwrt.org/docs/guide-user/network/switch_router_gateway_and_nat": "OpenWrt Switch/Router/Gateway/NAT",
                "https://openwrt.org/docs/guide-user/network/routing/start": "OpenWrt Routing",
                "https://openwrt.org/docs/guide-user/network/routing/ip_rules": "OpenWrt IP Rules",
                # Firewall
                "https://openwrt.org/docs/guide-user/firewall/start": "OpenWrt Firewall",
                "https://openwrt.org/docs/guide-user/firewall/firewall_configuration": "OpenWrt Firewall Configuration",
                "https://openwrt.org/docs/guide-user/firewall/fw3_configurations/start": "OpenWrt fw3 Configurations",
                # Services
                "https://openwrt.org/docs/guide-user/services/start": "OpenWrt Services",
                "https://openwrt.org/docs/guide-user/services/dns/start": "OpenWrt DNS",
                "https://openwrt.org/docs/guide-user/services/dns/dnsmasq": "OpenWrt dnsmasq",
                "https://openwrt.org/docs/guide-user/services/vpn/start": "OpenWrt VPN",
                "https://openwrt.org/docs/guide-user/services/vpn/openvpn/start": "OpenWrt OpenVPN",
                "https://openwrt.org/docs/guide-user/services/vpn/wireguard/start": "OpenWrt WireGuard",
                "https://openwrt.org/docs/guide-user/services/ddns/start": "OpenWrt DDNS",
                "https://openwrt.org/docs/guide-user/services/webserver/start": "OpenWrt Web Server",
                # Storage & USB
                "https://openwrt.org/docs/guide-user/storage/start": "OpenWrt Storage",
                "https://openwrt.org/docs/guide-user/storage/usb-drives-quickstart": "OpenWrt USB Drives",
                "https://openwrt.org/docs/guide-user/storage/usb-installing": "OpenWrt USB Installation",
                # Sysupgrade & flashing
                "https://openwrt.org/docs/guide-user/installation/sysupgrade.cli": "OpenWrt Sysupgrade CLI",
                "https://openwrt.org/docs/guide-user/installation/sysupgrade.luci": "OpenWrt Sysupgrade LuCI",
                "https://openwrt.org/docs/guide-user/installation/generic.sysupgrade": "OpenWrt Generic Sysupgrade",
                "https://openwrt.org/docs/guide-user/installation/generic.flashing.tftp": "OpenWrt TFTP Flash",
                # Security
                "https://openwrt.org/docs/guide-user/security/start": "OpenWrt Security Guide",
                "https://openwrt.org/docs/guide-user/security/secure.access": "OpenWrt Secure Access",
                # Developer guide
                "https://openwrt.org/docs/guide-developer/start": "OpenWrt Developer Guide",
                "https://openwrt.org/docs/guide-developer/toolchain/start": "OpenWrt Toolchain",
                "https://openwrt.org/docs/guide-developer/toolchain/use-buildsystem": "OpenWrt Build System",
                "https://openwrt.org/docs/guide-developer/packages": "OpenWrt Package Development",
                "https://openwrt.org/docs/guide-developer/build-system/use-patches-with-buildsystem": "OpenWrt Patches",
                # Hardware
                "https://openwrt.org/toh/start": "OpenWrt Table of Hardware",
                "https://openwrt.org/supported_devices": "OpenWrt Supported Devices",
                # About
                "https://openwrt.org/about": "About OpenWrt",
                "https://openwrt.org/releases/start": "OpenWrt Releases",
                "https://openwrt.org/docs/techref/start": "OpenWrt Technical Reference",
                "https://openwrt.org/docs/techref/flash.layout": "OpenWrt Flash Layout",
                "https://openwrt.org/docs/techref/initscripts": "OpenWrt Init Scripts",
                "https://openwrt.org/docs/techref/opkg": "OpenWrt opkg Package Manager",
                "https://openwrt.org/docs/techref/procd": "OpenWrt procd Init System",
                "https://openwrt.org/docs/techref/ubus": "OpenWrt ubus",
                "https://openwrt.org/docs/techref/netifd": "OpenWrt netifd",
            },
        },
        "packages": {
            "pages": {
                "https://openwrt.org/packages/start": "OpenWrt Packages Overview",
                "https://openwrt.org/packages/table/start": "OpenWrt Package Table",
                "https://openwrt.org/docs/guide-user/additional-software/opkg": "OpenWrt opkg Usage",
                "https://openwrt.org/docs/guide-user/additional-software/managing-packages": "OpenWrt Managing Packages",
                # Popular packages
                "https://openwrt.org/docs/guide-user/services/webserver/uhttpd": "OpenWrt uhttpd",
                "https://openwrt.org/docs/guide-user/luci/start": "OpenWrt LuCI",
                "https://openwrt.org/docs/guide-user/luci/luci.essentials": "OpenWrt LuCI Essentials",
                "https://openwrt.org/docs/guide-user/perf_and_log/start": "OpenWrt Performance & Logging",
                "https://openwrt.org/docs/guide-user/perf_and_log/bandwidth_monitoring": "OpenWrt Bandwidth Monitoring",
                "https://openwrt.org/docs/guide-user/network/traffic-shaping/start": "OpenWrt Traffic Shaping",
                "https://openwrt.org/docs/guide-user/network/traffic-shaping/sqm": "OpenWrt SQM QoS",
                "https://openwrt.org/docs/guide-user/services/tor": "OpenWrt Tor",
                "https://openwrt.org/docs/guide-user/services/proxy/overview": "OpenWrt Proxy Overview",
                "https://openwrt.org/docs/guide-user/network/uclient-fetch": "OpenWrt uclient-fetch",
            },
        },
        "forum": {
            "pages": {
                # Forum landing pages with recent activity
                "https://forum.openwrt.org/": "OpenWrt Forum Home",
                "https://forum.openwrt.org/c/installation/5": "OpenWrt Forum: Installation",
                "https://forum.openwrt.org/c/network-and-wireless-configuration/6": "OpenWrt Forum: Network Config",
                "https://forum.openwrt.org/c/hardware-questions-and-recommendations/7": "OpenWrt Forum: Hardware",
                "https://forum.openwrt.org/c/for-developers/8": "OpenWrt Forum: Developers",
                "https://forum.openwrt.org/c/community-builds-projects-and-packages/17": "OpenWrt Forum: Community Builds",
                "https://forum.openwrt.org/c/other/off-topic/20": "OpenWrt Forum: Off Topic",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"openwrt-{source_key}" if source_key else "openwrt"
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
            # Clean common suffixes
            for suffix in [' [OpenWrt Wiki]', ' - OpenWrt', ' | OpenWrt']:
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
                        "category": f"openwrt-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.0)  # Respectful rate limit for wiki

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
            self.log.info(f"=== Scraping openwrt/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    OpenWrtScraper(base, source_key).run()
