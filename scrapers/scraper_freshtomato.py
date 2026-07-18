#!/usr/bin/env python3
"""FreshTomato firmware documentation scraper.

Covers:
  - FreshTomato wiki documentation (configuration, networking, VPN, etc.)
  - FreshTomato HOWTOs (scripting, security, wireless, USB, etc.)
  - FreshTomato project pages (features, hardware compatibility, releases)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class FreshTomatoScraper(BaseScraper):
    """Scrape FreshTomato wiki, HOWTOs, and project pages."""

    SOURCES = {
        "docs": {
            "pages": {
                # Core documentation pages
                "https://wiki.freshtomato.org/doku.php/start": "FreshTomato Wiki Home",
                "https://wiki.freshtomato.org/doku.php/documentation": "FreshTomato Documentation Index",
                "https://wiki.freshtomato.org/doku.php/releases": "FreshTomato Releases",
                "https://wiki.freshtomato.org/doku.php/hardware_compatibility": "FreshTomato Hardware Compatibility",
                "https://wiki.freshtomato.org/doku.php/dongle_compatibility": "FreshTomato 3G/4G/5G Dongle Compatibility",
                "https://wiki.freshtomato.org/doku.php/feature_matrix": "FreshTomato Feature Matrix",
                "https://wiki.freshtomato.org/doku.php/faq": "FreshTomato FAQ",
                "https://wiki.freshtomato.org/doku.php/credits": "FreshTomato Credits",
                "https://wiki.freshtomato.org/doku.php/about": "FreshTomato About",
                # Basic settings
                "https://wiki.freshtomato.org/doku.php/basic-network": "FreshTomato Basic Network",
                "https://wiki.freshtomato.org/doku.php/basic-ipv6": "FreshTomato Basic IPv6",
                "https://wiki.freshtomato.org/doku.php/basic-ident": "FreshTomato Basic Identification",
                "https://wiki.freshtomato.org/doku.php/basic-time": "FreshTomato Basic Time",
                "https://wiki.freshtomato.org/doku.php/basic-ddns": "FreshTomato Basic DDNS",
                "https://wiki.freshtomato.org/doku.php/basic-static": "FreshTomato Basic Static DHCP",
                "https://wiki.freshtomato.org/doku.php/basic-wfilter": "FreshTomato Basic Wireless Filter",
                # Advanced settings
                "https://wiki.freshtomato.org/doku.php/advanced-ctnf": "FreshTomato Advanced Conntrack/Netfilter",
                "https://wiki.freshtomato.org/doku.php/advanced-dhcpdns": "FreshTomato Advanced DHCP/DNS",
                "https://wiki.freshtomato.org/doku.php/advanced-firewall": "FreshTomato Advanced Firewall",
                "https://wiki.freshtomato.org/doku.php/advanced-adblock": "FreshTomato Advanced Adblock",
                "https://wiki.freshtomato.org/doku.php/advanced-mac": "FreshTomato Advanced MAC Address",
                "https://wiki.freshtomato.org/doku.php/advanced-misc": "FreshTomato Advanced Miscellaneous",
                "https://wiki.freshtomato.org/doku.php/advanced-routing": "FreshTomato Advanced Routing",
                "https://wiki.freshtomato.org/doku.php/advanced-pbr": "FreshTomato Policy-Based Routing",
                "https://wiki.freshtomato.org/doku.php/advanced-tor": "FreshTomato Advanced Tor",
                "https://wiki.freshtomato.org/doku.php/advanced-vlan": "FreshTomato Advanced VLAN",
                "https://wiki.freshtomato.org/doku.php/advanced-access": "FreshTomato Advanced Access Restriction",
                "https://wiki.freshtomato.org/doku.php/advanced-wlanvifs": "FreshTomato Advanced WLAN Virtual Interfaces",
                "https://wiki.freshtomato.org/doku.php/advanced-wireless": "FreshTomato Advanced Wireless",
                # Port forwarding
                "https://wiki.freshtomato.org/doku.php/forward-basic": "FreshTomato Port Forwarding",
                "https://wiki.freshtomato.org/doku.php/forward-basic-ipv6": "FreshTomato IPv6 Port Forwarding",
                "https://wiki.freshtomato.org/doku.php/forward-dmz": "FreshTomato DMZ",
                "https://wiki.freshtomato.org/doku.php/forward-triggered": "FreshTomato Triggered Forwarding",
                "https://wiki.freshtomato.org/doku.php/forward-upnp": "FreshTomato UPnP",
                # VPN
                "https://wiki.freshtomato.org/doku.php/vpn-server": "FreshTomato VPN Server",
                "https://wiki.freshtomato.org/doku.php/vpn-client": "FreshTomato VPN Client",
                "https://wiki.freshtomato.org/doku.php/vpn-pptp-server": "FreshTomato PPTP Server",
                "https://wiki.freshtomato.org/doku.php/vpn-pptp-online": "FreshTomato PPTP Online",
                "https://wiki.freshtomato.org/doku.php/vpn-pptp": "FreshTomato PPTP",
                "https://wiki.freshtomato.org/doku.php/vpn-wireguard": "FreshTomato WireGuard",
                "https://wiki.freshtomato.org/doku.php/vpn-tinc": "FreshTomato Tinc VPN",
                # QoS
                "https://wiki.freshtomato.org/doku.php/qos-settings": "FreshTomato QoS Settings",
                "https://wiki.freshtomato.org/doku.php/qos-classify": "FreshTomato QoS Classification",
                "https://wiki.freshtomato.org/doku.php/qos-graphs": "FreshTomato QoS Graphs",
                "https://wiki.freshtomato.org/doku.php/qos-detailed": "FreshTomato QoS Detailed",
                "https://wiki.freshtomato.org/doku.php/qos-ctrate": "FreshTomato QoS Connection Rate",
                # USB and NAS
                "https://wiki.freshtomato.org/doku.php/nas-usb": "FreshTomato USB Support",
                "https://wiki.freshtomato.org/doku.php/nas-ftp": "FreshTomato FTP Server",
                "https://wiki.freshtomato.org/doku.php/nas-samba": "FreshTomato Samba File Sharing",
                "https://wiki.freshtomato.org/doku.php/nas-media": "FreshTomato Media Server",
                "https://wiki.freshtomato.org/doku.php/nas-ups": "FreshTomato UPS Support",
                "https://wiki.freshtomato.org/doku.php/nas-bittorrent": "FreshTomato BitTorrent",
                # Web server
                "https://wiki.freshtomato.org/doku.php/web-nginx": "FreshTomato Nginx Web Server",
                "https://wiki.freshtomato.org/doku.php/web-mysql": "FreshTomato MySQL",
                # Administration
                "https://wiki.freshtomato.org/doku.php/admin-access": "FreshTomato Admin Access",
                "https://wiki.freshtomato.org/doku.php/admin-tomatoanon": "FreshTomato TomatoAnon",
                "https://wiki.freshtomato.org/doku.php/admin-bwm": "FreshTomato Bandwidth Monitoring",
                "https://wiki.freshtomato.org/doku.php/admin-iptraffic": "FreshTomato IP Traffic Monitoring",
                "https://wiki.freshtomato.org/doku.php/admin-buttons": "FreshTomato Buttons/LED",
                "https://wiki.freshtomato.org/doku.php/admin-cifs": "FreshTomato CIFS Client",
                "https://wiki.freshtomato.org/doku.php/admin-config": "FreshTomato Configuration",
                "https://wiki.freshtomato.org/doku.php/admin-debug": "FreshTomato Debugging",
                "https://wiki.freshtomato.org/doku.php/admin-jffs2": "FreshTomato JFFS2",
                "https://wiki.freshtomato.org/doku.php/admin-nfs": "FreshTomato NFS Client",
                "https://wiki.freshtomato.org/doku.php/admin-snmp": "FreshTomato SNMP",
                "https://wiki.freshtomato.org/doku.php/admin-log": "FreshTomato Logging",
                "https://wiki.freshtomato.org/doku.php/admin-sched": "FreshTomato Scheduler",
                "https://wiki.freshtomato.org/doku.php/admin-scripts": "FreshTomato Scripts",
                "https://wiki.freshtomato.org/doku.php/admin-upgrade": "FreshTomato Firmware Upgrade",
                # Status pages
                "https://wiki.freshtomato.org/doku.php/status-overview": "FreshTomato Status Overview",
                "https://wiki.freshtomato.org/doku.php/status-devices": "FreshTomato Status Devices",
                "https://wiki.freshtomato.org/doku.php/status-webmon": "FreshTomato Web Monitor",
                "https://wiki.freshtomato.org/doku.php/status-log": "FreshTomato Status Log",
                # Tools
                "https://wiki.freshtomato.org/doku.php/tools-ping": "FreshTomato Ping Tool",
                "https://wiki.freshtomato.org/doku.php/tools-trace": "FreshTomato Traceroute Tool",
                "https://wiki.freshtomato.org/doku.php/tools-shell": "FreshTomato Shell Tool",
                "https://wiki.freshtomato.org/doku.php/tools-survey": "FreshTomato WiFi Survey Tool",
                "https://wiki.freshtomato.org/doku.php/tools-wol": "FreshTomato Wake-on-LAN",
                "https://wiki.freshtomato.org/doku.php/tools-iperf": "FreshTomato iPerf Tool",
                # Bandwidth & IP Traffic
                "https://wiki.freshtomato.org/doku.php/bwm-realtime": "FreshTomato Bandwidth Real-Time",
                "https://wiki.freshtomato.org/doku.php/bwm-24": "FreshTomato Bandwidth 24h",
                "https://wiki.freshtomato.org/doku.php/bwm-daily": "FreshTomato Bandwidth Daily",
                "https://wiki.freshtomato.org/doku.php/bwm-monthly": "FreshTomato Bandwidth Monthly",
                "https://wiki.freshtomato.org/doku.php/ipt-realtime": "FreshTomato IP Traffic Real-Time",
                # Misc
                "https://wiki.freshtomato.org/doku.php/restrict": "FreshTomato Access Restrictions",
                "https://wiki.freshtomato.org/doku.php/bwlimit": "FreshTomato Bandwidth Limiter",
                "https://wiki.freshtomato.org/doku.php/splashd": "FreshTomato Captive Portal (splashd)",
            },
        },
        "howtos": {
            "pages": {
                "https://wiki.freshtomato.org/doku.php/howtos": "FreshTomato HOWTOs Index",
                # Installation / upgrade
                "https://wiki.freshtomato.org/doku.php/firmware_basics_procedures": "FreshTomato Installation Guide",
                "https://wiki.freshtomato.org/doku.php/remote_upgrade_poc": "FreshTomato Remote Upgrade",
                # Networking
                "https://wiki.freshtomato.org/doku.php/switch_or_ap_mode": "FreshTomato Switch/AP Mode",
                # Scripting
                "https://wiki.freshtomato.org/doku.php/access_restrictions": "FreshTomato Access Restrictions Script",
                "https://wiki.freshtomato.org/doku.php/device_filtering": "FreshTomato Device Filtering",
                "https://wiki.freshtomato.org/doku.php/connectivity_watchdog": "FreshTomato Connectivity Watchdog",
                "https://wiki.freshtomato.org/doku.php/limit_number_of_sessions_per_device_subnet": "FreshTomato Session Limits",
                "https://wiki.freshtomato.org/doku.php/retain_dhcp_lease_info_after_a_reboot": "FreshTomato DHCP Lease Retention",
                "https://wiki.freshtomato.org/doku.php/backup_script": "FreshTomato Backup Script",
                "https://wiki.freshtomato.org/doku.php/clearing_iptables": "FreshTomato Clearing iptables",
                "https://wiki.freshtomato.org/doku.php/ip_script": "FreshTomato IP Script",
                "https://wiki.freshtomato.org/doku.php/one_off_reboot": "FreshTomato One-Off Reboot Script",
                "https://wiki.freshtomato.org/doku.php/monitor_connections": "FreshTomato Monitor Connections",
                "https://wiki.freshtomato.org/doku.php/enable_disable_ethernet_port": "FreshTomato Enable/Disable Ethernet Port",
                "https://wiki.freshtomato.org/doku.php/aria": "FreshTomato Aria2 Download Manager",
                "https://wiki.freshtomato.org/doku.php/ash_history": "FreshTomato ASH History",
                "https://wiki.freshtomato.org/doku.php/static2json": "FreshTomato Static2JSON",
                # Security
                "https://wiki.freshtomato.org/doku.php/basic_hardening": "FreshTomato Basic Hardening",
                "https://wiki.freshtomato.org/doku.php/2fa": "FreshTomato Two-Factor Auth",
                "https://wiki.freshtomato.org/doku.php/custom_ssl_cert_local_cert_authority": "FreshTomato Custom SSL Cert",
                # DNS
                "https://wiki.freshtomato.org/doku.php/opendns_on_tomato": "FreshTomato OpenDNS Setup",
                "https://wiki.freshtomato.org/doku.php/stubby": "FreshTomato Stubby DNS-over-TLS",
                "https://wiki.freshtomato.org/doku.php/dns_flag_day_2020": "FreshTomato DNS Flag Day 2020",
                "https://wiki.freshtomato.org/doku.php/adblock_dns_filtering": "FreshTomato Adblock DNS Filtering",
                # SSH
                "https://wiki.freshtomato.org/doku.php/enable_ssh": "FreshTomato Enable SSH",
                "https://wiki.freshtomato.org/doku.php/generate_ssh_keys": "FreshTomato Generate SSH Keys",
                "https://wiki.freshtomato.org/doku.php/putty_automation": "FreshTomato PuTTY Automation",
                "https://wiki.freshtomato.org/doku.php/router_to_router_ssh": "FreshTomato Router-to-Router SSH",
                # USB
                "https://wiki.freshtomato.org/doku.php/usb_formatting_with_swap_partition": "FreshTomato USB Formatting + Swap",
                "https://wiki.freshtomato.org/doku.php/entware_installation_usage": "FreshTomato Entware Installation",
                "https://wiki.freshtomato.org/doku.php/usb_filesystem_check_repair": "FreshTomato USB Filesystem Repair",
                # VPN howtos
                "https://wiki.freshtomato.org/doku.php/openvpn_extra_connection": "FreshTomato OpenVPN Extra Connection",
                "https://wiki.freshtomato.org/doku.php/setting_up_a_tinc_full_mash_network": "FreshTomato Tinc Full Mesh",
                "https://wiki.freshtomato.org/doku.php/wireguard_on_freshtomato": "FreshTomato WireGuard Setup",
                "https://wiki.freshtomato.org/doku.php/wireguard_on_freshtomato_with_bird": "FreshTomato WireGuard with BIRD",
                "https://wiki.freshtomato.org/doku.php/ipsec_on_freshtomato": "FreshTomato IPsec Setup",
                "https://wiki.freshtomato.org/doku.php/freshtomato_zerotier": "FreshTomato ZeroTier Setup",
                # Advanced wireless
                "https://wiki.freshtomato.org/doku.php/wireless_interface_modes_table": "FreshTomato Wireless Interface Modes",
                "https://wiki.freshtomato.org/doku.php/wireless_ethernet_bridge": "FreshTomato Wireless Ethernet Bridge",
                "https://wiki.freshtomato.org/doku.php/media_bridge": "FreshTomato Media Bridge",
                "https://wiki.freshtomato.org/doku.php/advanced_scenarios": "FreshTomato Advanced Wireless Scenarios",
                "https://wiki.freshtomato.org/doku.php/wireless_interoperability": "FreshTomato Wireless Interoperability",
                "https://wiki.freshtomato.org/doku.php/toggle_radio": "FreshTomato Toggle Radio",
                "https://wiki.freshtomato.org/doku.php/wireless_filtering": "FreshTomato Wireless Filtering",
                # Debugging
                "https://wiki.freshtomato.org/doku.php/onlinetests": "FreshTomato Online Tests",
                "https://wiki.freshtomato.org/doku.php/crash_log": "FreshTomato Crash Log",
                "https://wiki.freshtomato.org/doku.php/speedtest": "FreshTomato Speed Test",
                # Home automation
                "https://wiki.freshtomato.org/doku.php/integrating_home_assistant_with_freshtomato": "FreshTomato Home Assistant Integration",
                # Scheduling
                "https://wiki.freshtomato.org/doku.php/schedule_wol": "FreshTomato Schedule Wake-on-LAN",
            },
        },
        "project": {
            "pages": {
                # Project website
                "https://freshtomato.org/": "FreshTomato Home",
                "https://freshtomato.org/features.html": "FreshTomato Features",
                "https://freshtomato.org/screenshots.html": "FreshTomato Screenshots",
                # LinksysInfo forum (community hub)
                "https://www.linksysinfo.org/index.php?forums/tomato-firmware.33/": "FreshTomato Forum (LinksysInfo)",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"freshtomato-{source_key}" if source_key else "freshtomato"
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
            for suffix in [' [FreshTomato Wiki]', ' - FreshTomato', ' | FreshTomato']:
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
                        "category": f"freshtomato-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)  # Respectful rate limit for wiki

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
            self.log.info(f"=== Scraping freshtomato/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    FreshTomatoScraper(base, source_key).run()
