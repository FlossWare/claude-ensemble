#!/usr/bin/env python3
"""
Combine firmware URLs from both crawls and add manually curated lists.
"""

import json
import requests

# Load both crawl results
with open('/tmp/firmware-urls.json') as f:
    basic = json.load(f)

with open('/tmp/firmware-urls-enhanced.json') as f:
    enhanced = json.load(f)

# Combine URLs
combined = {
    'ddwrt': set(basic['urls']['ddwrt'] + enhanced['urls']['ddwrt']),
    'tomato': set(basic['urls']['tomato'] + enhanced['urls']['tomato']),
    'openwrt': set(basic['urls']['openwrt'] + enhanced['urls']['openwrt'])
}

# Add manually curated DD-WRT URLs (from known documentation structure)
ddwrt_manual = [
    # Main sections
    'https://wiki.dd-wrt.com/wiki/index.php/Main_Page',
    'https://wiki.dd-wrt.com/wiki/index.php/Installation',
    'https://wiki.dd-wrt.com/wiki/index.php/Wireless_Configuration',
    'https://wiki.dd-wrt.com/wiki/index.php/Basic_Setup',
    'https://wiki.dd-wrt.com/wiki/index.php/Networking',
    'https://wiki.dd-wrt.com/wiki/index.php/Firewall',
    'https://wiki.dd-wrt.com/wiki/index.php/VPN',
    'https://wiki.dd-wrt.com/wiki/index.php/USB_Storage',
    'https://wiki.dd-wrt.com/wiki/index.php/Scripts',
    'https://wiki.dd-wrt.com/wiki/index.php/Telnet/SSH_and_the_Command_Line',

    # Router database
    'https://wiki.dd-wrt.com/wiki/index.php/Supported_Devices',
    'https://wiki.dd-wrt.com/wiki/index.php/Router_Database',

    # Common tutorials
    'https://wiki.dd-wrt.com/wiki/index.php/Basic_Wireless_Settings',
    'https://wiki.dd-wrt.com/wiki/index.php/Wireless_Security',
    'https://wiki.dd-wrt.com/wiki/index.php/Quality_of_Service',
    'https://wiki.dd-wrt.com/wiki/index.php/Dynamic_DNS',
    'https://wiki.dd-wrt.com/wiki/index.php/Port_Forwarding',
    'https://wiki.dd-wrt.com/wiki/index.php/OpenVPN',
    'https://wiki.dd-wrt.com/wiki/index.php/PPTP',
    'https://wiki.dd-wrt.com/wiki/index.php/Samba',
    'https://wiki.dd-wrt.com/wiki/index.php/NFS',
    'https://wiki.dd-wrt.com/wiki/index.php/Lighttpd',
]

# Add manually curated OpenWrt URLs
openwrt_manual = [
    # Quick start
    'https://openwrt.org/docs/guide-quick-start/start',
    'https://openwrt.org/docs/guide-quick-start/factory_installation',
    'https://openwrt.org/docs/guide-quick-start/sysupgrade.luci',
    'https://openwrt.org/docs/guide-quick-start/ssh_access',

    # User guide - Base system
    'https://openwrt.org/docs/guide-user/base-system/basic-networking',
    'https://openwrt.org/docs/guide-user/base-system/dhcp',
    'https://openwrt.org/docs/guide-user/base-system/system_configuration',
    'https://openwrt.org/docs/guide-user/base-system/led_configuration',
    'https://openwrt.org/docs/guide-user/base-system/uci',

    # User guide - Network
    'https://openwrt.org/docs/guide-user/network/wifi/basic',
    'https://openwrt.org/docs/guide-user/network/wifi/encryption',
    'https://openwrt.org/docs/guide-user/network/vlan/switch_configuration',
    'https://openwrt.org/docs/guide-user/network/routing/routes_configuration',
    'https://openwrt.org/docs/guide-user/network/wan/wwan/start',

    # User guide - Firewall
    'https://openwrt.org/docs/guide-user/firewall/firewall_configuration',
    'https://openwrt.org/docs/guide-user/firewall/fw3_configurations/port_forwarding',
    'https://openwrt.org/docs/guide-user/firewall/fw3_configurations/dmz_based_on_interface',

    # User guide - Services
    'https://openwrt.org/docs/guide-user/services/vpn/openvpn/start',
    'https://openwrt.org/docs/guide-user/services/vpn/wireguard/start',
    'https://openwrt.org/docs/guide-user/services/dns/dnsmasq',
    'https://openwrt.org/docs/guide-user/services/ddns/client',

    # Developer guide
    'https://openwrt.org/docs/guide-developer/toolchain/use-buildsystem',
    'https://openwrt.org/docs/guide-developer/packages',
    'https://openwrt.org/docs/guide-developer/procd-init-scripts',

    # Hardware
    'https://openwrt.org/toh/start',
    'https://openwrt.org/toh/views/toh_fwdownload',
]

combined['ddwrt'].update(ddwrt_manual)
combined['openwrt'].update(openwrt_manual)

# Convert to lists and save
final = {
    'total_urls': sum(len(urls) for urls in combined.values()),
    'by_firmware': {
        'ddwrt': len(combined['ddwrt']),
        'tomato': len(combined['tomato']),
        'openwrt': len(combined['openwrt'])
    },
    'urls': {k: sorted(list(v)) for k, v in combined.items()}
}

with open('/tmp/firmware-urls-final.json', 'w') as f:
    json.dump(final, f, indent=2)

print(f"=== FINAL COMBINED RESULTS ===")
print(f"Total URLs: {final['total_urls']}")
print(f"  DD-WRT:   {final['by_firmware']['ddwrt']}")
print(f"  Tomato:   {final['by_firmware']['tomato']}")
print(f"  OpenWrt:  {final['by_firmware']['openwrt']}")

# Also create a flat list for easy loading
all_urls = []
for firmware, urls in final['urls'].items():
    all_urls.extend(urls)

with open('/tmp/firmware-urls-flat.txt', 'w') as f:
    f.write('\n'.join(all_urls))

print(f"\nSaved {len(all_urls)} URLs to /tmp/firmware-urls-flat.txt")
print("\nSample URLs:")
print("DD-WRT:")
for url in list(combined['ddwrt'])[:3]:
    print(f"  - {url}")
print("Tomato:")
for url in list(combined['tomato'])[:3]:
    print(f"  - {url}")
print("OpenWrt:")
for url in list(combined['openwrt'])[:3]:
    print(f"  - {url}")
