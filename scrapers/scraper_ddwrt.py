#!/usr/bin/env python3
"""DD-WRT wiki scraper.

Covers:
  - Installation: flashing guides, firmware types, recovery
  - Configuration: basic setup, wireless, VLAN, QoS
  - Networking: firewall, iptables, routing, DNS
  - VPN: OpenVPN, WireGuard, PPTP, IPsec
  - Scripting: startup scripts, cron, jffs, custom commands
  - Hardware: supported devices, router database, USB, NAS
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class DdWrtScraper(BaseScraper):
    """Scrape DD-WRT wiki documentation."""

    SOURCES = {
        "installation": {
            "pages": {
                "https://wiki.dd-wrt.com/wiki/index.php/Installation": "DD-WRT Installation",
                "https://wiki.dd-wrt.com/wiki/index.php/Firmware_FAQ": "Firmware FAQ",
                "https://wiki.dd-wrt.com/wiki/index.php/What_is_DD-WRT%3F": "What is DD-WRT",
                "https://wiki.dd-wrt.com/wiki/index.php/Supported_Devices": "Supported Devices",
                "https://wiki.dd-wrt.com/wiki/index.php/Router_Database": "Router Database",
                "https://wiki.dd-wrt.com/wiki/index.php/Peacock_Thread": "Peacock Thread - Read First",
                "https://wiki.dd-wrt.com/wiki/index.php/Hard_reset_or_30/30/30": "Hard Reset 30/30/30",
                "https://wiki.dd-wrt.com/wiki/index.php/Recover_from_a_Bad_Flash": "Recover from Bad Flash",
                "https://wiki.dd-wrt.com/wiki/index.php/TFTP_flash": "TFTP Flash",
                "https://wiki.dd-wrt.com/wiki/index.php/Firmware_Types": "Firmware Types",
            },
        },
        "configuration": {
            "pages": {
                "https://wiki.dd-wrt.com/wiki/index.php/Basic_Wireless_Settings": "Basic Wireless Settings",
                "https://wiki.dd-wrt.com/wiki/index.php/Advanced_Wireless_Settings": "Advanced Wireless Settings",
                "https://wiki.dd-wrt.com/wiki/index.php/Wireless_Security": "Wireless Security",
                "https://wiki.dd-wrt.com/wiki/index.php/WPA/WPA2": "WPA/WPA2 Setup",
                "https://wiki.dd-wrt.com/wiki/index.php/VLAN_Detached_Networks_(Scalable_Approach)": "VLAN Detached Networks",
                "https://wiki.dd-wrt.com/wiki/index.php/Switched_Ports": "Switched Ports / VLAN",
                "https://wiki.dd-wrt.com/wiki/index.php/QoS": "Quality of Service (QoS)",
                "https://wiki.dd-wrt.com/wiki/index.php/QoS_Settings": "QoS Settings",
                "https://wiki.dd-wrt.com/wiki/index.php/Quality_of_Service": "Quality of Service Guide",
                "https://wiki.dd-wrt.com/wiki/index.php/Access_Restrictions": "Access Restrictions",
                "https://wiki.dd-wrt.com/wiki/index.php/Wireless_Bridge": "Wireless Bridge",
                "https://wiki.dd-wrt.com/wiki/index.php/Repeater_Bridge": "Repeater Bridge",
                "https://wiki.dd-wrt.com/wiki/index.php/Client_Bridged": "Client Bridged",
                "https://wiki.dd-wrt.com/wiki/index.php/Client_Mode_Wireless": "Client Mode Wireless",
                "https://wiki.dd-wrt.com/wiki/index.php/WDS": "WDS (Wireless Distribution System)",
            },
        },
        "networking": {
            "pages": {
                "https://wiki.dd-wrt.com/wiki/index.php/Firewall": "Firewall",
                "https://wiki.dd-wrt.com/wiki/index.php/Iptables": "Iptables",
                "https://wiki.dd-wrt.com/wiki/index.php/Iptables_command": "Iptables Commands",
                "https://wiki.dd-wrt.com/wiki/index.php/Port_Forwarding": "Port Forwarding",
                "https://wiki.dd-wrt.com/wiki/index.php/DMZ": "DMZ Configuration",
                "https://wiki.dd-wrt.com/wiki/index.php/Static_Routing": "Static Routing",
                "https://wiki.dd-wrt.com/wiki/index.php/DNSMasq_as_DHCP_server": "DNSMasq as DHCP Server",
                "https://wiki.dd-wrt.com/wiki/index.php/DNSMasq": "DNSMasq",
                "https://wiki.dd-wrt.com/wiki/index.php/Multiple_WAN_Connections": "Multiple WAN Connections",
                "https://wiki.dd-wrt.com/wiki/index.php/IPv6": "IPv6 Support",
            },
        },
        "vpn": {
            "pages": {
                "https://wiki.dd-wrt.com/wiki/index.php/VPN_(the_easy_way)_v24+": "VPN Easy Way",
                "https://wiki.dd-wrt.com/wiki/index.php/OpenVPN": "OpenVPN",
                "https://wiki.dd-wrt.com/wiki/index.php/OpenVPN_server_setup_guide_for_beginners": "OpenVPN Server Setup Guide",
                "https://wiki.dd-wrt.com/wiki/index.php/OpenVPN_setting_up_a_routed_VPN": "OpenVPN Routed VPN",
                "https://wiki.dd-wrt.com/wiki/index.php/WireGuard": "WireGuard",
                "https://wiki.dd-wrt.com/wiki/index.php/PPTP_Server_Configuration": "PPTP Server Configuration",
                "https://wiki.dd-wrt.com/wiki/index.php/PPTP_Client_Setup": "PPTP Client Setup",
                "https://wiki.dd-wrt.com/wiki/index.php/IPSec": "IPsec VPN",
            },
        },
        "scripting": {
            "pages": {
                "https://wiki.dd-wrt.com/wiki/index.php/Script_Execution": "Script Execution",
                "https://wiki.dd-wrt.com/wiki/index.php/Startup_Scripts": "Startup Scripts",
                "https://wiki.dd-wrt.com/wiki/index.php/Cron": "Cron Jobs",
                "https://wiki.dd-wrt.com/wiki/index.php/JFFS": "JFFS Storage",
                "https://wiki.dd-wrt.com/wiki/index.php/Useful_Scripts": "Useful Scripts",
                "https://wiki.dd-wrt.com/wiki/index.php/Telnet/SSH_and_the_Command_Line": "Telnet/SSH and Command Line",
            },
        },
        "hardware": {
            "pages": {
                "https://wiki.dd-wrt.com/wiki/index.php/USB": "USB Support",
                "https://wiki.dd-wrt.com/wiki/index.php/USB_storage": "USB Storage",
                "https://wiki.dd-wrt.com/wiki/index.php/NAS": "NAS Setup",
                "https://wiki.dd-wrt.com/wiki/index.php/Samba": "Samba File Sharing",
                "https://wiki.dd-wrt.com/wiki/index.php/FTP": "FTP Server",
                "https://wiki.dd-wrt.com/wiki/index.php/Optware": "Optware Package Manager",
                "https://wiki.dd-wrt.com/wiki/index.php/Entware": "Entware Package Manager",
                "https://wiki.dd-wrt.com/wiki/index.php/Supported_Devices/Broadcom": "Broadcom Devices",
                "https://wiki.dd-wrt.com/wiki/index.php/Supported_Devices/Atheros": "Atheros Devices",
                "https://wiki.dd-wrt.com/wiki/index.php/Supported_Devices/MediaTek": "MediaTek Devices",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"ddwrt-{source_key}" if source_key else "ddwrt"
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
            for suffix in [' - DD-WRT Wiki', ' - DD-WRT', ' | DD-WRT']:
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
                        "category": f"ddwrt-{source_key}",
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
            self.log.info(f"=== Scraping ddwrt/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    DdWrtScraper(base, source_key).run()
