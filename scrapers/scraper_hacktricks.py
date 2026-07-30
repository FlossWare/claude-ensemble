#!/usr/bin/env python3
"""HackTricks scraper.

Covers:
  - reconnaissance: enumeration, scanning, OSINT, information gathering
  - exploitation: common exploitation techniques, payload generation
  - privilege-escalation: Linux and Windows privilege escalation techniques
  - post-exploitation: persistence, lateral movement, data exfiltration
  - web: SQL injection, XSS, SSRF, SSTI, deserialization, file inclusion, CSRF
  - network: SMB, LDAP, Kerberos, SSH, DNS, FTP, SNMP, NFS service pentesting
  - linux: Linux hardening, enumeration, useful commands
  - windows: Windows hardening, enumeration, Active Directory
  - cloud: AWS, Azure, GCP pentesting and enumeration
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


HT = "https://book.hacktricks.xyz"


class HackTricksScraper(BaseScraper):
    """Scrape HackTricks pentesting documentation."""

    SOURCES = {
        "reconnaissance": {
            "pages": {
                f"{HT}/generic-methodologies-and-resources/pentesting-methodology": "Pentesting Methodology",
                f"{HT}/generic-methodologies-and-resources/external-recon-methodology": "External Recon Methodology",
                f"{HT}/generic-methodologies-and-resources/information-gathering": "Information Gathering",
                f"{HT}/network-services-pentesting": "Network Services Pentesting Overview",
                f"{HT}/network-services-pentesting/pentesting-web": "Pentesting Web Methodology",
                f"{HT}/generic-methodologies-and-resources/shells/linux": "Linux Shells and Reverse Shells",
                f"{HT}/generic-methodologies-and-resources/shells/windows": "Windows Shells and Reverse Shells",
            },
        },
        "exploitation": {
            "pages": {
                f"{HT}/generic-methodologies-and-resources/phishing-methodology": "Phishing Methodology",
                f"{HT}/generic-methodologies-and-resources/brute-force": "Brute Force Cheatsheet",
                f"{HT}/generic-methodologies-and-resources/tunneling-and-port-forwarding": "Tunneling and Port Forwarding",
                f"{HT}/generic-methodologies-and-resources/exfiltration": "Exfiltration",
                f"{HT}/exploiting/linux-exploiting-basic-esp": "Linux Exploiting Basic (ESP)",
            },
        },
        "privilege-escalation": {
            "pages": {
                f"{HT}/linux-hardening/privilege-escalation": "Linux Privilege Escalation",
                f"{HT}/linux-hardening/privilege-escalation/interesting-groups-linux-pe": "Interesting Groups - Linux PE",
                f"{HT}/linux-hardening/privilege-escalation/linux-capabilities": "Linux Capabilities",
                f"{HT}/linux-hardening/privilege-escalation/docker-security": "Docker Security",
                f"{HT}/linux-hardening/privilege-escalation/escaping-from-limited-bash": "Escaping from Restricted Shells",
                f"{HT}/windows-hardening/windows-local-privilege-escalation": "Windows Local Privilege Escalation",
                f"{HT}/windows-hardening/windows-local-privilege-escalation/privilege-escalation-abusing-tokens": "Abusing Tokens",
                f"{HT}/windows-hardening/windows-local-privilege-escalation/dll-hijacking": "DLL Hijacking",
            },
        },
        "post-exploitation": {
            "pages": {
                f"{HT}/linux-hardening/useful-linux-commands": "Useful Linux Commands",
                f"{HT}/windows-hardening/basic-cmd-for-pentesters": "Basic CMD for Pentesters",
                f"{HT}/windows-hardening/basic-powershell-for-pentesters": "Basic PowerShell for Pentesters",
                f"{HT}/generic-methodologies-and-resources/lateral-movement": "Lateral Movement",
                f"{HT}/windows-hardening/active-directory-methodology/pass-the-hash-pth": "Pass the Hash (PtH)",
            },
        },
        "web": {
            "pages": {
                f"{HT}/pentesting-web/sql-injection": "SQL Injection",
                f"{HT}/pentesting-web/sql-injection/sqlmap": "SQLMap",
                f"{HT}/pentesting-web/xss-cross-site-scripting": "XSS (Cross Site Scripting)",
                f"{HT}/pentesting-web/ssrf-server-side-request-forgery": "SSRF (Server Side Request Forgery)",
                f"{HT}/pentesting-web/ssti-server-side-template-injection": "SSTI (Server Side Template Injection)",
                f"{HT}/pentesting-web/deserialization": "Deserialization",
                f"{HT}/pentesting-web/file-inclusion": "File Inclusion / Path Traversal",
                f"{HT}/pentesting-web/file-upload": "File Upload",
                f"{HT}/pentesting-web/command-injection": "Command Injection",
                f"{HT}/pentesting-web/csrf-cross-site-request-forgery": "CSRF (Cross Site Request Forgery)",
                f"{HT}/pentesting-web/xxe-xee-xml-external-entity": "XXE (XML External Entity)",
                f"{HT}/pentesting-web/idor": "IDOR (Insecure Direct Object Reference)",
                f"{HT}/pentesting-web/cors-bypass": "CORS Bypass",
                f"{HT}/pentesting-web/content-security-policy-csp-bypass": "CSP Bypass",
                f"{HT}/pentesting-web/jwt-json-web-tokens": "JWT (JSON Web Tokens)",
            },
        },
        "network": {
            "pages": {
                f"{HT}/network-services-pentesting/pentesting-smb": "Pentesting SMB",
                f"{HT}/network-services-pentesting/pentesting-ldap": "Pentesting LDAP",
                f"{HT}/network-services-pentesting/pentesting-kerberos-88": "Pentesting Kerberos",
                f"{HT}/network-services-pentesting/pentesting-ssh": "Pentesting SSH",
                f"{HT}/network-services-pentesting/pentesting-dns": "Pentesting DNS",
                f"{HT}/network-services-pentesting/pentesting-ftp": "Pentesting FTP",
                f"{HT}/network-services-pentesting/pentesting-snmp": "Pentesting SNMP",
                f"{HT}/network-services-pentesting/nfs-service-pentesting": "Pentesting NFS",
                f"{HT}/network-services-pentesting/pentesting-smtp": "Pentesting SMTP",
                f"{HT}/network-services-pentesting/pentesting-mysql": "Pentesting MySQL",
            },
        },
        "linux": {
            "pages": {
                f"{HT}/linux-hardening": "Linux Hardening",
                f"{HT}/linux-hardening/linux-environment-enumeration": "Linux Environment Enumeration",
                f"{HT}/linux-hardening/linux-post-exploitation": "Linux Post Exploitation",
                f"{HT}/linux-hardening/bypass-bash-restrictions": "Bypass Bash Restrictions",
                f"{HT}/linux-hardening/privilege-escalation/linux-active-directory": "Linux Active Directory",
            },
        },
        "windows": {
            "pages": {
                f"{HT}/windows-hardening": "Windows Hardening",
                f"{HT}/windows-hardening/active-directory-methodology": "Active Directory Methodology",
                f"{HT}/windows-hardening/active-directory-methodology/kerberoast": "Kerberoast",
                f"{HT}/windows-hardening/active-directory-methodology/asreproast": "AS-REP Roasting",
                f"{HT}/windows-hardening/active-directory-methodology/dcsync": "DCSync",
                f"{HT}/windows-hardening/active-directory-methodology/golden-ticket": "Golden Ticket",
                f"{HT}/windows-hardening/active-directory-methodology/bloodhound": "BloodHound",
                f"{HT}/windows-hardening/ntlm": "NTLM",
                f"{HT}/windows-hardening/stealing-credentials": "Stealing Windows Credentials",
                f"{HT}/windows-hardening/av-bypass": "AV Bypass",
            },
        },
        "cloud": {
            "pages": {
                f"{HT}/pentesting-cloud/pentesting-cloud-methodology": "Cloud Pentesting Methodology",
                f"{HT}/pentesting-cloud/aws-security": "AWS Security",
                f"{HT}/pentesting-cloud/aws-security/aws-privilege-escalation": "AWS Privilege Escalation",
                f"{HT}/pentesting-cloud/aws-security/aws-services/aws-s3-and-glacier": "AWS S3 and Glacier",
                f"{HT}/pentesting-cloud/aws-security/aws-services/aws-iam-and-sts": "AWS IAM and STS",
                f"{HT}/pentesting-cloud/azure-security": "Azure Security",
                f"{HT}/pentesting-cloud/azure-security/az-privilege-escalation": "Azure Privilege Escalation",
                f"{HT}/pentesting-cloud/azure-security/az-services/az-azure-ad": "Azure AD",
                f"{HT}/pentesting-cloud/gcp-security": "GCP Security",
                f"{HT}/pentesting-cloud/gcp-security/gcp-privilege-escalation": "GCP Privilege Escalation",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"hacktricks-{source_key}" if source_key else "hacktricks"
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
            for suffix in [' | HackTricks', ' - HackTricks', ' | HackTricks Wiki',
                           ' - HackTricks Wiki']:
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
                        "category": f"hacktricks-{source_key}",
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
            self.log.info(f"=== Scraping hacktricks/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    HackTricksScraper(base, source_key).run()
