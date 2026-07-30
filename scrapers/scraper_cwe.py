#!/usr/bin/env python3
"""Common Weakness Enumeration (CWE) scraper.

Covers:
  - Top 25: CWE Top 25 Most Dangerous Software Weaknesses
  - Software errors: memory safety, injection, authentication, crypto, etc.
  - Hardware: hardware design weaknesses
  - Categories: CWE categories and views
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class CWEScraper(BaseScraper):
    """Scrape Common Weakness Enumeration entries from cwe.mitre.org."""

    SOURCES = {
        "top-25": {
            "pages": {
                # CWE Top 25 overview
                "https://cwe.mitre.org/top25/archive/2023/2023_top25_list.html": "CWE Top 25 Most Dangerous Software Weaknesses (2023)",
                "https://cwe.mitre.org/top25/archive/2024/2024_top25_list.html": "CWE Top 25 Most Dangerous Software Weaknesses (2024)",
                # Top 25 individual entries
                "https://cwe.mitre.org/data/definitions/787.html": "CWE-787: Out-of-bounds Write",
                "https://cwe.mitre.org/data/definitions/79.html": "CWE-79: Improper Neutralization of Input During Web Page Generation (XSS)",
                "https://cwe.mitre.org/data/definitions/89.html": "CWE-89: Improper Neutralization of Special Elements used in an SQL Command (SQL Injection)",
                "https://cwe.mitre.org/data/definitions/416.html": "CWE-416: Use After Free",
                "https://cwe.mitre.org/data/definitions/78.html": "CWE-78: Improper Neutralization of Special Elements used in an OS Command (OS Command Injection)",
                "https://cwe.mitre.org/data/definitions/20.html": "CWE-20: Improper Input Validation",
                "https://cwe.mitre.org/data/definitions/125.html": "CWE-125: Out-of-bounds Read",
                "https://cwe.mitre.org/data/definitions/22.html": "CWE-22: Improper Limitation of a Pathname to a Restricted Directory (Path Traversal)",
                "https://cwe.mitre.org/data/definitions/352.html": "CWE-352: Cross-Site Request Forgery (CSRF)",
                "https://cwe.mitre.org/data/definitions/434.html": "CWE-434: Unrestricted Upload of File with Dangerous Type",
                "https://cwe.mitre.org/data/definitions/862.html": "CWE-862: Missing Authorization",
                "https://cwe.mitre.org/data/definitions/476.html": "CWE-476: NULL Pointer Dereference",
                "https://cwe.mitre.org/data/definitions/287.html": "CWE-287: Improper Authentication",
                "https://cwe.mitre.org/data/definitions/190.html": "CWE-190: Integer Overflow or Wraparound",
                "https://cwe.mitre.org/data/definitions/502.html": "CWE-502: Deserialization of Untrusted Data",
                "https://cwe.mitre.org/data/definitions/77.html": "CWE-77: Improper Neutralization of Special Elements used in a Command (Command Injection)",
                "https://cwe.mitre.org/data/definitions/119.html": "CWE-119: Improper Restriction of Operations within the Bounds of a Memory Buffer",
                "https://cwe.mitre.org/data/definitions/798.html": "CWE-798: Use of Hard-coded Credentials",
                "https://cwe.mitre.org/data/definitions/918.html": "CWE-918: Server-Side Request Forgery (SSRF)",
                "https://cwe.mitre.org/data/definitions/306.html": "CWE-306: Missing Authentication for Critical Function",
                "https://cwe.mitre.org/data/definitions/362.html": "CWE-362: Concurrent Execution using Shared Resource with Improper Synchronization (Race Condition)",
                "https://cwe.mitre.org/data/definitions/269.html": "CWE-269: Improper Privilege Management",
                "https://cwe.mitre.org/data/definitions/94.html": "CWE-94: Improper Control of Generation of Code (Code Injection)",
                "https://cwe.mitre.org/data/definitions/863.html": "CWE-863: Incorrect Authorization",
                "https://cwe.mitre.org/data/definitions/276.html": "CWE-276: Incorrect Default Permissions",
            },
        },
        "software-errors": {
            "pages": {
                # Memory safety
                "https://cwe.mitre.org/data/definitions/120.html": "CWE-120: Buffer Copy without Checking Size of Input (Classic Buffer Overflow)",
                "https://cwe.mitre.org/data/definitions/122.html": "CWE-122: Heap-based Buffer Overflow",
                "https://cwe.mitre.org/data/definitions/121.html": "CWE-121: Stack-based Buffer Overflow",
                "https://cwe.mitre.org/data/definitions/415.html": "CWE-415: Double Free",
                "https://cwe.mitre.org/data/definitions/401.html": "CWE-401: Missing Release of Memory after Effective Lifetime (Memory Leak)",
                "https://cwe.mitre.org/data/definitions/824.html": "CWE-824: Access of Uninitialized Pointer",
                "https://cwe.mitre.org/data/definitions/126.html": "CWE-126: Buffer Over-read",
                "https://cwe.mitre.org/data/definitions/127.html": "CWE-127: Buffer Under-read",
                "https://cwe.mitre.org/data/definitions/131.html": "CWE-131: Incorrect Calculation of Buffer Size",
                "https://cwe.mitre.org/data/definitions/134.html": "CWE-134: Use of Externally-Controlled Format String",
                # Injection
                "https://cwe.mitre.org/data/definitions/90.html": "CWE-90: Improper Neutralization of Special Elements used in an LDAP Query (LDAP Injection)",
                "https://cwe.mitre.org/data/definitions/91.html": "CWE-91: XML Injection",
                "https://cwe.mitre.org/data/definitions/611.html": "CWE-611: Improper Restriction of XML External Entity Reference (XXE)",
                "https://cwe.mitre.org/data/definitions/917.html": "CWE-917: Improper Neutralization of Special Elements used in an Expression Language Statement (EL Injection)",
                "https://cwe.mitre.org/data/definitions/1236.html": "CWE-1236: Improper Neutralization of Formula Elements in a CSV File",
                # Authentication and session management
                "https://cwe.mitre.org/data/definitions/384.html": "CWE-384: Session Fixation",
                "https://cwe.mitre.org/data/definitions/613.html": "CWE-613: Insufficient Session Expiration",
                "https://cwe.mitre.org/data/definitions/307.html": "CWE-307: Improper Restriction of Excessive Authentication Attempts",
                "https://cwe.mitre.org/data/definitions/521.html": "CWE-521: Weak Password Requirements",
                "https://cwe.mitre.org/data/definitions/640.html": "CWE-640: Weak Password Recovery Mechanism for Forgotten Password",
                # Cryptographic issues
                "https://cwe.mitre.org/data/definitions/327.html": "CWE-327: Use of a Broken or Risky Cryptographic Algorithm",
                "https://cwe.mitre.org/data/definitions/328.html": "CWE-328: Use of Weak Hash",
                "https://cwe.mitre.org/data/definitions/330.html": "CWE-330: Use of Insufficiently Random Values",
                "https://cwe.mitre.org/data/definitions/326.html": "CWE-326: Inadequate Encryption Strength",
                "https://cwe.mitre.org/data/definitions/295.html": "CWE-295: Improper Certificate Validation",
                "https://cwe.mitre.org/data/definitions/311.html": "CWE-311: Missing Encryption of Sensitive Data",
                "https://cwe.mitre.org/data/definitions/312.html": "CWE-312: Cleartext Storage of Sensitive Information",
                "https://cwe.mitre.org/data/definitions/319.html": "CWE-319: Cleartext Transmission of Sensitive Information",
                # Information exposure
                "https://cwe.mitre.org/data/definitions/200.html": "CWE-200: Exposure of Sensitive Information to an Unauthorized Actor",
                "https://cwe.mitre.org/data/definitions/209.html": "CWE-209: Generation of Error Message Containing Sensitive Information",
                "https://cwe.mitre.org/data/definitions/532.html": "CWE-532: Insertion of Sensitive Information into Log File",
                "https://cwe.mitre.org/data/definitions/359.html": "CWE-359: Exposure of Private Personal Information to an Unauthorized Actor",
            },
        },
        "hardware": {
            "pages": {
                "https://cwe.mitre.org/data/definitions/1189.html": "CWE-1189: Improper Isolation of Shared Resources on System-on-a-Chip (SoC)",
                "https://cwe.mitre.org/data/definitions/1191.html": "CWE-1191: On-Chip Debug and Test Interface With Improper Access Control",
                "https://cwe.mitre.org/data/definitions/1220.html": "CWE-1220: Insufficient Granularity of Access Control",
                "https://cwe.mitre.org/data/definitions/1231.html": "CWE-1231: Improper Prevention of Lock Bit Modification",
                "https://cwe.mitre.org/data/definitions/1233.html": "CWE-1233: Security-Sensitive Hardware Controls with Missing Lock Bit Protection",
                "https://cwe.mitre.org/data/definitions/1234.html": "CWE-1234: Hardware Internal or Debug Modes Allow Override of Locks",
                "https://cwe.mitre.org/data/definitions/1240.html": "CWE-1240: Use of a Cryptographic Primitive with a Risky Implementation",
                "https://cwe.mitre.org/data/definitions/1243.html": "CWE-1243: Sensitive Non-Volatile Information Not Protected During Debug",
                "https://cwe.mitre.org/data/definitions/1244.html": "CWE-1244: Internal Asset Exposed to Unsafe Debug Access Level or State",
                "https://cwe.mitre.org/data/definitions/1256.html": "CWE-1256: Improper Restriction of Software Interfaces to Hardware Features",
                "https://cwe.mitre.org/data/definitions/1260.html": "CWE-1260: Improper Handling of Overlap Between Protected Memory Ranges",
                "https://cwe.mitre.org/data/definitions/1262.html": "CWE-1262: Improper Access Control for Register Interface",
                "https://cwe.mitre.org/data/definitions/1272.html": "CWE-1272: Sensitive Information Uncleared Before Debug/Power State Transition",
                "https://cwe.mitre.org/data/definitions/1274.html": "CWE-1274: Improper Access Control for Volatile Memory Containing Boot Code",
            },
        },
        "categories": {
            "pages": {
                # Major CWE views and categories
                "https://cwe.mitre.org/data/definitions/1000.html": "CWE-1000: Research Concepts",
                "https://cwe.mitre.org/data/definitions/699.html": "CWE-699: Software Development",
                "https://cwe.mitre.org/data/definitions/1194.html": "CWE-1194: Hardware Design",
                "https://cwe.mitre.org/data/definitions/1387.html": "CWE-1387: Weaknesses in the 2022 CWE Top 25",
                # Commonly referenced categories
                "https://cwe.mitre.org/data/definitions/254.html": "CWE-254: 7PK - Security Features",
                "https://cwe.mitre.org/data/definitions/310.html": "CWE-310: Cryptographic Issues",
                "https://cwe.mitre.org/data/definitions/320.html": "CWE-320: Key Management Errors",
                "https://cwe.mitre.org/data/definitions/345.html": "CWE-345: Insufficient Verification of Data Authenticity",
                "https://cwe.mitre.org/data/definitions/399.html": "CWE-399: Resource Management Errors",
                "https://cwe.mitre.org/data/definitions/264.html": "CWE-264: Permissions, Privileges, and Access Controls",
                "https://cwe.mitre.org/data/definitions/189.html": "CWE-189: Numeric Errors",
                "https://cwe.mitre.org/data/definitions/361.html": "CWE-361: 7PK - Time and State",
                # Additional important individual CWEs
                "https://cwe.mitre.org/data/definitions/400.html": "CWE-400: Uncontrolled Resource Consumption",
                "https://cwe.mitre.org/data/definitions/770.html": "CWE-770: Allocation of Resources Without Limits or Throttling",
                "https://cwe.mitre.org/data/definitions/772.html": "CWE-772: Missing Release of Resource after Effective Lifetime",
                "https://cwe.mitre.org/data/definitions/601.html": "CWE-601: URL Redirection to Untrusted Site (Open Redirect)",
                "https://cwe.mitre.org/data/definitions/347.html": "CWE-347: Improper Verification of Cryptographic Signature",
                "https://cwe.mitre.org/data/definitions/843.html": "CWE-843: Access of Resource Using Incompatible Type (Type Confusion)",
                "https://cwe.mitre.org/data/definitions/908.html": "CWE-908: Use of Uninitialized Resource",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"cwe-{source_key}" if source_key else "cwe"
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
            for suffix in [' - CWE', ' | CWE - MITRE', ' - MITRE']:
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
                        "category": f"cwe-{source_key}",
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
            self.log.info(f"=== Scraping cwe/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    CWEScraper(base, source_key).run()
