#!/usr/bin/env python3
"""IETF RFC scraper.

Covers:
  - Transport: TCP, UDP, QUIC, SCTP
  - Security: TLS, IPsec, SSH
  - Routing: BGP, OSPF, IS-IS
  - DNS: Domain Name System
  - DHCP: Dynamic Host Configuration Protocol
  - HTTP: HTTP/1.1, HTTP/2, HTTP/3
  - Email: SMTP, IMAP
  - IPv6: Internet Protocol version 6
  - IoT: CoAP, MQTT standards
  - Web: WebSocket, HTTP/2, HTTP/3
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class RFCScraper(BaseScraper):
    """Scrape IETF RFCs from rfc-editor.org (plain text format)."""

    SOURCES = {
        "transport": {
            "pages": {
                # TCP
                "https://www.rfc-editor.org/rfc/rfc793.txt": "RFC 793 - Transmission Control Protocol (TCP)",
                "https://www.rfc-editor.org/rfc/rfc5681.txt": "RFC 5681 - TCP Congestion Control",
                "https://www.rfc-editor.org/rfc/rfc7323.txt": "RFC 7323 - TCP Extensions for High Performance",
                "https://www.rfc-editor.org/rfc/rfc6298.txt": "RFC 6298 - Computing TCP Retransmission Timer",
                "https://www.rfc-editor.org/rfc/rfc2018.txt": "RFC 2018 - TCP Selective Acknowledgment Options",
                "https://www.rfc-editor.org/rfc/rfc9293.txt": "RFC 9293 - Transmission Control Protocol (TCP) Specification",
                # UDP
                "https://www.rfc-editor.org/rfc/rfc768.txt": "RFC 768 - User Datagram Protocol (UDP)",
                "https://www.rfc-editor.org/rfc/rfc8085.txt": "RFC 8085 - UDP Usage Guidelines",
                # QUIC
                "https://www.rfc-editor.org/rfc/rfc9000.txt": "RFC 9000 - QUIC: A UDP-Based Multiplexed and Secure Transport",
                "https://www.rfc-editor.org/rfc/rfc9001.txt": "RFC 9001 - Using TLS to Secure QUIC",
                "https://www.rfc-editor.org/rfc/rfc9002.txt": "RFC 9002 - QUIC Loss Detection and Congestion Control",
                # SCTP
                "https://www.rfc-editor.org/rfc/rfc9260.txt": "RFC 9260 - Stream Control Transmission Protocol (SCTP)",
                "https://www.rfc-editor.org/rfc/rfc3286.txt": "RFC 3286 - Introduction to SCTP",
            },
        },
        "security": {
            "pages": {
                # TLS
                "https://www.rfc-editor.org/rfc/rfc8446.txt": "RFC 8446 - The Transport Layer Security (TLS) Protocol Version 1.3",
                "https://www.rfc-editor.org/rfc/rfc5246.txt": "RFC 5246 - The Transport Layer Security (TLS) Protocol Version 1.2",
                "https://www.rfc-editor.org/rfc/rfc6066.txt": "RFC 6066 - TLS Extensions: Extension Definitions",
                "https://www.rfc-editor.org/rfc/rfc7301.txt": "RFC 7301 - TLS Application-Layer Protocol Negotiation (ALPN)",
                "https://www.rfc-editor.org/rfc/rfc6125.txt": "RFC 6125 - Representation and Verification of Domain-Based Application Service Identity within PKI",
                # IPsec
                "https://www.rfc-editor.org/rfc/rfc4301.txt": "RFC 4301 - Security Architecture for the Internet Protocol (IPsec)",
                "https://www.rfc-editor.org/rfc/rfc4302.txt": "RFC 4302 - IP Authentication Header (AH)",
                "https://www.rfc-editor.org/rfc/rfc4303.txt": "RFC 4303 - IP Encapsulating Security Payload (ESP)",
                "https://www.rfc-editor.org/rfc/rfc7296.txt": "RFC 7296 - Internet Key Exchange Protocol Version 2 (IKEv2)",
                # SSH
                "https://www.rfc-editor.org/rfc/rfc4251.txt": "RFC 4251 - The Secure Shell (SSH) Protocol Architecture",
                "https://www.rfc-editor.org/rfc/rfc4252.txt": "RFC 4252 - The Secure Shell (SSH) Authentication Protocol",
                "https://www.rfc-editor.org/rfc/rfc4253.txt": "RFC 4253 - The Secure Shell (SSH) Transport Layer Protocol",
                "https://www.rfc-editor.org/rfc/rfc4254.txt": "RFC 4254 - The Secure Shell (SSH) Connection Protocol",
                # X.509 and PKI
                "https://www.rfc-editor.org/rfc/rfc5280.txt": "RFC 5280 - Internet X.509 PKI Certificate and CRL Profile",
                "https://www.rfc-editor.org/rfc/rfc6960.txt": "RFC 6960 - X.509 Internet PKI Online Certificate Status Protocol (OCSP)",
            },
        },
        "routing": {
            "pages": {
                # BGP
                "https://www.rfc-editor.org/rfc/rfc4271.txt": "RFC 4271 - A Border Gateway Protocol 4 (BGP-4)",
                "https://www.rfc-editor.org/rfc/rfc4760.txt": "RFC 4760 - Multiprotocol Extensions for BGP-4",
                "https://www.rfc-editor.org/rfc/rfc7454.txt": "RFC 7454 - BGP Operations and Security",
                "https://www.rfc-editor.org/rfc/rfc4272.txt": "RFC 4272 - BGP Security Vulnerabilities Analysis",
                "https://www.rfc-editor.org/rfc/rfc6811.txt": "RFC 6811 - BGP Prefix Origin Validation (RPKI)",
                # OSPF
                "https://www.rfc-editor.org/rfc/rfc2328.txt": "RFC 2328 - OSPF Version 2",
                "https://www.rfc-editor.org/rfc/rfc5340.txt": "RFC 5340 - OSPF for IPv6 (OSPFv3)",
                "https://www.rfc-editor.org/rfc/rfc3630.txt": "RFC 3630 - Traffic Engineering (TE) Extensions to OSPF Version 2",
                # IS-IS
                "https://www.rfc-editor.org/rfc/rfc1195.txt": "RFC 1195 - Use of OSI IS-IS for Routing in TCP/IP and Dual Environments",
                "https://www.rfc-editor.org/rfc/rfc5305.txt": "RFC 5305 - IS-IS Extensions for Traffic Engineering",
                # RIP
                "https://www.rfc-editor.org/rfc/rfc2453.txt": "RFC 2453 - RIP Version 2",
                # MPLS
                "https://www.rfc-editor.org/rfc/rfc3031.txt": "RFC 3031 - Multiprotocol Label Switching Architecture (MPLS)",
                "https://www.rfc-editor.org/rfc/rfc3032.txt": "RFC 3032 - MPLS Label Stack Encoding",
            },
        },
        "dns": {
            "pages": {
                "https://www.rfc-editor.org/rfc/rfc1034.txt": "RFC 1034 - Domain Names - Concepts and Facilities",
                "https://www.rfc-editor.org/rfc/rfc1035.txt": "RFC 1035 - Domain Names - Implementation and Specification",
                "https://www.rfc-editor.org/rfc/rfc4033.txt": "RFC 4033 - DNS Security Introduction and Requirements (DNSSEC)",
                "https://www.rfc-editor.org/rfc/rfc4034.txt": "RFC 4034 - Resource Records for the DNS Security Extensions",
                "https://www.rfc-editor.org/rfc/rfc4035.txt": "RFC 4035 - Protocol Modifications for the DNS Security Extensions",
                "https://www.rfc-editor.org/rfc/rfc8484.txt": "RFC 8484 - DNS Queries over HTTPS (DoH)",
                "https://www.rfc-editor.org/rfc/rfc7858.txt": "RFC 7858 - Specification for DNS over TLS (DoT)",
                "https://www.rfc-editor.org/rfc/rfc9250.txt": "RFC 9250 - DNS over Dedicated QUIC Connections (DoQ)",
                "https://www.rfc-editor.org/rfc/rfc6891.txt": "RFC 6891 - Extension Mechanisms for DNS (EDNS(0))",
                "https://www.rfc-editor.org/rfc/rfc2136.txt": "RFC 2136 - Dynamic Updates in the DNS",
            },
        },
        "dhcp": {
            "pages": {
                "https://www.rfc-editor.org/rfc/rfc2131.txt": "RFC 2131 - Dynamic Host Configuration Protocol (DHCP)",
                "https://www.rfc-editor.org/rfc/rfc2132.txt": "RFC 2132 - DHCP Options and BOOTP Vendor Extensions",
                "https://www.rfc-editor.org/rfc/rfc8415.txt": "RFC 8415 - Dynamic Host Configuration Protocol for IPv6 (DHCPv6)",
                "https://www.rfc-editor.org/rfc/rfc3315.txt": "RFC 3315 - Dynamic Host Configuration Protocol for IPv6 (DHCPv6) Original",
            },
        },
        "http": {
            "pages": {
                "https://www.rfc-editor.org/rfc/rfc2616.txt": "RFC 2616 - Hypertext Transfer Protocol HTTP/1.1 (Original)",
                "https://www.rfc-editor.org/rfc/rfc9110.txt": "RFC 9110 - HTTP Semantics",
                "https://www.rfc-editor.org/rfc/rfc9111.txt": "RFC 9111 - HTTP Caching",
                "https://www.rfc-editor.org/rfc/rfc9112.txt": "RFC 9112 - HTTP/1.1",
                "https://www.rfc-editor.org/rfc/rfc7540.txt": "RFC 7540 - Hypertext Transfer Protocol Version 2 (HTTP/2)",
                "https://www.rfc-editor.org/rfc/rfc9113.txt": "RFC 9113 - HTTP/2",
                "https://www.rfc-editor.org/rfc/rfc9114.txt": "RFC 9114 - HTTP/3",
                "https://www.rfc-editor.org/rfc/rfc6265.txt": "RFC 6265 - HTTP State Management Mechanism (Cookies)",
                "https://www.rfc-editor.org/rfc/rfc7235.txt": "RFC 7235 - Hypertext Transfer Protocol HTTP/1.1: Authentication",
                "https://www.rfc-editor.org/rfc/rfc7617.txt": "RFC 7617 - The Basic HTTP Authentication Scheme",
                "https://www.rfc-editor.org/rfc/rfc6750.txt": "RFC 6750 - The OAuth 2.0 Authorization Framework: Bearer Token Usage",
            },
        },
        "email": {
            "pages": {
                # SMTP
                "https://www.rfc-editor.org/rfc/rfc5321.txt": "RFC 5321 - Simple Mail Transfer Protocol (SMTP)",
                "https://www.rfc-editor.org/rfc/rfc5322.txt": "RFC 5322 - Internet Message Format",
                "https://www.rfc-editor.org/rfc/rfc6409.txt": "RFC 6409 - Message Submission for Mail",
                # IMAP
                "https://www.rfc-editor.org/rfc/rfc9051.txt": "RFC 9051 - Internet Message Access Protocol (IMAP) Version 4rev2",
                "https://www.rfc-editor.org/rfc/rfc3501.txt": "RFC 3501 - Internet Message Access Protocol (IMAP) Version 4rev1",
                # POP3
                "https://www.rfc-editor.org/rfc/rfc1939.txt": "RFC 1939 - Post Office Protocol Version 3 (POP3)",
                # MIME
                "https://www.rfc-editor.org/rfc/rfc2045.txt": "RFC 2045 - MIME Part One: Format of Internet Message Bodies",
                "https://www.rfc-editor.org/rfc/rfc2046.txt": "RFC 2046 - MIME Part Two: Media Types",
                # Authentication
                "https://www.rfc-editor.org/rfc/rfc7208.txt": "RFC 7208 - Sender Policy Framework (SPF)",
                "https://www.rfc-editor.org/rfc/rfc6376.txt": "RFC 6376 - DomainKeys Identified Mail (DKIM) Signatures",
                "https://www.rfc-editor.org/rfc/rfc7489.txt": "RFC 7489 - Domain-based Message Authentication, Reporting, and Conformance (DMARC)",
            },
        },
        "ipv6": {
            "pages": {
                "https://www.rfc-editor.org/rfc/rfc8200.txt": "RFC 8200 - Internet Protocol, Version 6 (IPv6) Specification",
                "https://www.rfc-editor.org/rfc/rfc4291.txt": "RFC 4291 - IP Version 6 Addressing Architecture",
                "https://www.rfc-editor.org/rfc/rfc4862.txt": "RFC 4862 - IPv6 Stateless Address Autoconfiguration (SLAAC)",
                "https://www.rfc-editor.org/rfc/rfc4861.txt": "RFC 4861 - Neighbor Discovery for IP version 6 (IPv6)",
                "https://www.rfc-editor.org/rfc/rfc6724.txt": "RFC 6724 - Default Address Selection for IPv6",
                "https://www.rfc-editor.org/rfc/rfc6146.txt": "RFC 6146 - Stateful NAT64: Network Address and Protocol Translation",
                "https://www.rfc-editor.org/rfc/rfc6147.txt": "RFC 6147 - DNS64: DNS Extensions for Network Address Translation",
                "https://www.rfc-editor.org/rfc/rfc7084.txt": "RFC 7084 - Basic Requirements for IPv6 Customer Edge Routers",
            },
        },
        "iot": {
            "pages": {
                # CoAP
                "https://www.rfc-editor.org/rfc/rfc7252.txt": "RFC 7252 - The Constrained Application Protocol (CoAP)",
                "https://www.rfc-editor.org/rfc/rfc7959.txt": "RFC 7959 - Block-Wise Transfers in the Constrained Application Protocol (CoAP)",
                "https://www.rfc-editor.org/rfc/rfc7641.txt": "RFC 7641 - Observing Resources in the Constrained Application Protocol (CoAP)",
                "https://www.rfc-editor.org/rfc/rfc8323.txt": "RFC 8323 - CoAP over TCP, TLS, and WebSockets",
                # 6LoWPAN
                "https://www.rfc-editor.org/rfc/rfc4944.txt": "RFC 4944 - Transmission of IPv6 Packets over IEEE 802.15.4 Networks (6LoWPAN)",
                "https://www.rfc-editor.org/rfc/rfc6282.txt": "RFC 6282 - Compression Format for IPv6 Datagrams over IEEE 802.15.4 Networks",
                # RPL
                "https://www.rfc-editor.org/rfc/rfc6550.txt": "RFC 6550 - RPL: IPv6 Routing Protocol for Low-Power and Lossy Networks",
                # CBOR
                "https://www.rfc-editor.org/rfc/rfc8949.txt": "RFC 8949 - Concise Binary Object Representation (CBOR)",
            },
        },
        "web": {
            "pages": {
                # WebSocket
                "https://www.rfc-editor.org/rfc/rfc6455.txt": "RFC 6455 - The WebSocket Protocol",
                # REST/URI
                "https://www.rfc-editor.org/rfc/rfc3986.txt": "RFC 3986 - Uniform Resource Identifier (URI): Generic Syntax",
                "https://www.rfc-editor.org/rfc/rfc7231.txt": "RFC 7231 - Hypertext Transfer Protocol HTTP/1.1: Semantics and Content",
                # OAuth
                "https://www.rfc-editor.org/rfc/rfc6749.txt": "RFC 6749 - The OAuth 2.0 Authorization Framework",
                "https://www.rfc-editor.org/rfc/rfc7519.txt": "RFC 7519 - JSON Web Token (JWT)",
                "https://www.rfc-editor.org/rfc/rfc7515.txt": "RFC 7515 - JSON Web Signature (JWS)",
                "https://www.rfc-editor.org/rfc/rfc7516.txt": "RFC 7516 - JSON Web Encryption (JWE)",
                "https://www.rfc-editor.org/rfc/rfc7517.txt": "RFC 7517 - JSON Web Key (JWK)",
                # JSON
                "https://www.rfc-editor.org/rfc/rfc8259.txt": "RFC 8259 - The JavaScript Object Notation (JSON) Data Interchange Format",
                # IP fundamentals
                "https://www.rfc-editor.org/rfc/rfc791.txt": "RFC 791 - Internet Protocol (IP)",
                "https://www.rfc-editor.org/rfc/rfc792.txt": "RFC 792 - Internet Control Message Protocol (ICMP)",
                # CORS / Content Security
                "https://www.rfc-editor.org/rfc/rfc6454.txt": "RFC 6454 - The Web Origin Concept",
                # Server-Sent Events / HPACK
                "https://www.rfc-editor.org/rfc/rfc7541.txt": "RFC 7541 - HPACK: Header Compression for HTTP/2",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"rfc-{source_key}" if source_key else "rfc"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, content):
        """RFCs are plain text, so just return content directly."""
        return content

    def _extract_title(self, content, fallback):
        """Extract title from RFC plain text header."""
        for line in content.split('\n')[:30]:
            line = line.strip()
            if line.lower().startswith('title:'):
                return line[6:].strip()
        # Try to find an obvious title line (often near the top, all caps or mixed case)
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

            if content and len(content) > 200:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)

                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"rfc-{source_key}",
                        "type": "specification",
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
            self.log.info(f"=== Scraping rfc/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    RFCScraper(base, source_key).run()
