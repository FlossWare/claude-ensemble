#!/usr/bin/env python3
"""OWASP security documentation scraper.

Covers:
  - OWASP Cheat Sheet Series (cheatsheetseries.owasp.org)
  - OWASP Top 10 (owasp.org/Top10/)
  - Web Security Testing Guide (owasp.org/www-project-web-security-testing-guide/)
  - Mobile Top 10 (owasp.org/www-project-mobile-top-10/)
  - API Security Top 10 (owasp.org/API-Security/)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class OwaspScraper(BaseScraper):
    """Scrape OWASP cheat sheets, top 10 lists, and testing guides."""

    SOURCES = {
        "cheatsheets": {
            "pages": {
                # Authentication & Authorization
                "https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html": "Authentication Cheat Sheet",
                "https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html": "Authorization Cheat Sheet",
                "https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Testing_Automation_Cheat_Sheet.html": "Authorization Testing Automation Cheat Sheet",
                # Clickjacking & CSP
                "https://cheatsheetseries.owasp.org/cheatsheets/Clickjacking_Defense_Cheat_Sheet.html": "Clickjacking Defense Cheat Sheet",
                "https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html": "Content Security Policy Cheat Sheet",
                # CSRF
                "https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html": "Cross-Site Request Forgery Prevention Cheat Sheet",
                # Cryptography & Storage
                "https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html": "Cryptographic Storage Cheat Sheet",
                # Database
                "https://cheatsheetseries.owasp.org/cheatsheets/Database_Security_Cheat_Sheet.html": "Database Security Cheat Sheet",
                # DoS
                "https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html": "Denial of Service Cheat Sheet",
                # Deserialization
                "https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html": "Deserialization Cheat Sheet",
                # DOM XSS
                "https://cheatsheetseries.owasp.org/cheatsheets/DOM_based_XSS_Prevention_Cheat_Sheet.html": "DOM based XSS Prevention Cheat Sheet",
                # Error Handling
                "https://cheatsheetseries.owasp.org/cheatsheets/Error_Handling_Cheat_Sheet.html": "Error Handling Cheat Sheet",
                # File Upload
                "https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html": "File Upload Cheat Sheet",
                # Forgot Password
                "https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html": "Forgot Password Cheat Sheet",
                # HTTP Headers
                "https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html": "HTTP Headers Cheat Sheet",
                # HSTS
                "https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Strict_Transport_Security_Cheat_Sheet.html": "HTTP Strict Transport Security Cheat Sheet",
                # HTML5
                "https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html": "HTML5 Security Cheat Sheet",
                # Injection Prevention
                "https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_Cheat_Sheet.html": "Injection Prevention Cheat Sheet",
                # Input Validation
                "https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html": "Input Validation Cheat Sheet",
                # IDOR
                "https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html": "Insecure Direct Object Reference Prevention Cheat Sheet",
                # JWT
                "https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html": "JSON Web Token for Java Cheat Sheet",
                # Key Management
                "https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html": "Key Management Cheat Sheet",
                # LDAP Injection
                "https://cheatsheetseries.owasp.org/cheatsheets/LDAP_Injection_Prevention_Cheat_Sheet.html": "LDAP Injection Prevention Cheat Sheet",
                # Logging
                "https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html": "Logging Cheat Sheet",
                # Mass Assignment
                "https://cheatsheetseries.owasp.org/cheatsheets/Mass_Assignment_Cheat_Sheet.html": "Mass Assignment Cheat Sheet",
                # Microservices
                "https://cheatsheetseries.owasp.org/cheatsheets/Microservices_Security_Cheat_Sheet.html": "Microservices Security Cheat Sheet",
                # MFA
                "https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html": "Multifactor Authentication Cheat Sheet",
                # OS Command Injection
                "https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html": "OS Command Injection Defense Cheat Sheet",
                # Password Storage
                "https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html": "Password Storage Cheat Sheet",
                # Pinning
                "https://cheatsheetseries.owasp.org/cheatsheets/Pinning_Cheat_Sheet.html": "Pinning Cheat Sheet",
                # Query Parameterization
                "https://cheatsheetseries.owasp.org/cheatsheets/Query_Parameterization_Cheat_Sheet.html": "Query Parameterization Cheat Sheet",
                # REST
                "https://cheatsheetseries.owasp.org/cheatsheets/REST_Assessment_Cheat_Sheet.html": "REST Assessment Cheat Sheet",
                "https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html": "REST Security Cheat Sheet",
                # SAML
                "https://cheatsheetseries.owasp.org/cheatsheets/SAML_Security_Cheat_Sheet.html": "SAML Security Cheat Sheet",
                # SSRF
                "https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html": "Server Side Request Forgery Prevention Cheat Sheet",
                # Session Management
                "https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html": "Session Management Cheat Sheet",
                # SQL Injection
                "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html": "SQL Injection Prevention Cheat Sheet",
                # Third Party JS
                "https://cheatsheetseries.owasp.org/cheatsheets/Third_Party_Javascript_Management_Cheat_Sheet.html": "Third Party Javascript Management Cheat Sheet",
                # TLS
                "https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html": "Transport Layer Security Cheat Sheet",
                # Unvalidated Redirects
                "https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html": "Unvalidated Redirects and Forwards Cheat Sheet",
                # User Privacy
                "https://cheatsheetseries.owasp.org/cheatsheets/User_Privacy_Protection_Cheat_Sheet.html": "User Privacy Protection Cheat Sheet",
                # Vulnerability Disclosure
                "https://cheatsheetseries.owasp.org/cheatsheets/Vulnerability_Disclosure_Cheat_Sheet.html": "Vulnerability Disclosure Cheat Sheet",
                # Web Service Security
                "https://cheatsheetseries.owasp.org/cheatsheets/Web_Service_Security_Cheat_Sheet.html": "Web Service Security Cheat Sheet",
                # XXE
                "https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html": "XML External Entity Prevention Cheat Sheet",
                # XML Security
                "https://cheatsheetseries.owasp.org/cheatsheets/XML_Security_Cheat_Sheet.html": "XML Security Cheat Sheet",
                # XSS
                "https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html": "XSS Prevention Cheat Sheet",
            },
        },
        "top10": {
            "pages": {
                # OWASP Top 10 (2021)
                "https://owasp.org/Top10/": "OWASP Top 10 Introduction",
                "https://owasp.org/Top10/A01_2021-Broken_Access_Control/": "A01:2021 Broken Access Control",
                "https://owasp.org/Top10/A02_2021-Cryptographic_Failures/": "A02:2021 Cryptographic Failures",
                "https://owasp.org/Top10/A03_2021-Injection/": "A03:2021 Injection",
                "https://owasp.org/Top10/A04_2021-Insecure_Design/": "A04:2021 Insecure Design",
                "https://owasp.org/Top10/A05_2021-Security_Misconfiguration/": "A05:2021 Security Misconfiguration",
                "https://owasp.org/Top10/A06_2021-Vulnerable_and_Outdated_Components/": "A06:2021 Vulnerable and Outdated Components",
                "https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/": "A07:2021 Identification and Authentication Failures",
                "https://owasp.org/Top10/A08_2021-Software_and_Data_Integrity_Failures/": "A08:2021 Software and Data Integrity Failures",
                "https://owasp.org/Top10/A09_2021-Security_Logging_and_Monitoring_Failures/": "A09:2021 Security Logging and Monitoring Failures",
                "https://owasp.org/Top10/A10_2021-Server-Side_Request_Forgery_%28SSRF%29/": "A10:2021 Server-Side Request Forgery (SSRF)",
                "https://owasp.org/Top10/A11_2021-Next_Steps/": "A11:2021 Next Steps",
            },
        },
        "wstg": {
            "pages": {
                # Web Security Testing Guide
                "https://owasp.org/www-project-web-security-testing-guide/latest/": "Web Security Testing Guide",
                "https://owasp.org/www-project-web-security-testing-guide/latest/1-Frontispiece/": "WSTG Frontispiece",
                "https://owasp.org/www-project-web-security-testing-guide/latest/2-Introduction/": "WSTG Introduction",
                "https://owasp.org/www-project-web-security-testing-guide/latest/3-The_OWASP_Testing_Framework/": "WSTG The OWASP Testing Framework",
                "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/": "WSTG Web Application Security Testing",
                "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/01-Information_Gathering/": "WSTG Information Gathering",
                "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/02-Configuration_and_Deployment_Management_Testing/": "WSTG Configuration and Deployment Management",
                "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/03-Identity_Management_Testing/": "WSTG Identity Management Testing",
                "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/04-Authentication_Testing/": "WSTG Authentication Testing",
                "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/05-Authorization_Testing/": "WSTG Authorization Testing",
                "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/06-Session_Management_Testing/": "WSTG Session Management Testing",
                "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/": "WSTG Input Validation Testing",
                "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/08-Testing_for_Error_Handling/": "WSTG Error Handling Testing",
                "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/09-Testing_for_Weak_Cryptography/": "WSTG Weak Cryptography Testing",
                "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/10-Business_Logic_Testing/": "WSTG Business Logic Testing",
                "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/11-Client-side_Testing/": "WSTG Client-side Testing",
                "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/12-API_Testing/": "WSTG API Testing",
                "https://owasp.org/www-project-web-security-testing-guide/latest/5-Reporting/": "WSTG Reporting",
                "https://owasp.org/www-project-web-security-testing-guide/latest/6-Appendix/": "WSTG Appendix",
            },
        },
        "mobile": {
            "pages": {
                # Mobile Top 10
                "https://owasp.org/www-project-mobile-top-10/": "OWASP Mobile Top 10",
                "https://owasp.org/www-project-mobile-top-10/2024-risks/": "Mobile Top 10 2024 Risks",
                "https://owasp.org/www-project-mobile-top-10/2024-risks/m1-improper-credential-usage.html": "M1 Improper Credential Usage",
                "https://owasp.org/www-project-mobile-top-10/2024-risks/m2-inadequate-supply-chain-security.html": "M2 Inadequate Supply Chain Security",
                "https://owasp.org/www-project-mobile-top-10/2024-risks/m3-insecure-authentication-authorization.html": "M3 Insecure Authentication/Authorization",
                "https://owasp.org/www-project-mobile-top-10/2024-risks/m4-insufficient-input-output-validation.html": "M4 Insufficient Input/Output Validation",
                "https://owasp.org/www-project-mobile-top-10/2024-risks/m5-insecure-communication.html": "M5 Insecure Communication",
                "https://owasp.org/www-project-mobile-top-10/2024-risks/m6-inadequate-privacy-controls.html": "M6 Inadequate Privacy Controls",
                "https://owasp.org/www-project-mobile-top-10/2024-risks/m7-insufficient-binary-protections.html": "M7 Insufficient Binary Protections",
                "https://owasp.org/www-project-mobile-top-10/2024-risks/m8-security-misconfiguration.html": "M8 Security Misconfiguration",
                "https://owasp.org/www-project-mobile-top-10/2024-risks/m9-insecure-data-storage.html": "M9 Insecure Data Storage",
                "https://owasp.org/www-project-mobile-top-10/2024-risks/m10-insufficient-cryptography.html": "M10 Insufficient Cryptography",
            },
        },
        "api-security": {
            "pages": {
                # API Security Top 10 (2023)
                "https://owasp.org/API-Security/editions/2023/en/0x00-header/": "API Security Top 10 Header",
                "https://owasp.org/API-Security/editions/2023/en/0x01-about-owasp/": "API Security About OWASP",
                "https://owasp.org/API-Security/editions/2023/en/0x02-foreword/": "API Security Foreword",
                "https://owasp.org/API-Security/editions/2023/en/0x03-introduction/": "API Security Introduction",
                "https://owasp.org/API-Security/editions/2023/en/0x04-release-notes/": "API Security Release Notes",
                "https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/": "API1 Broken Object Level Authorization",
                "https://owasp.org/API-Security/editions/2023/en/0xa2-broken-authentication/": "API2 Broken Authentication",
                "https://owasp.org/API-Security/editions/2023/en/0xa3-broken-object-property-level-authorization/": "API3 Broken Object Property Level Authorization",
                "https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/": "API4 Unrestricted Resource Consumption",
                "https://owasp.org/API-Security/editions/2023/en/0xa5-broken-function-level-authorization/": "API5 Broken Function Level Authorization",
                "https://owasp.org/API-Security/editions/2023/en/0xa6-unrestricted-access-to-sensitive-business-flows/": "API6 Unrestricted Access to Sensitive Business Flows",
                "https://owasp.org/API-Security/editions/2023/en/0xa7-server-side-request-forgery/": "API7 Server Side Request Forgery",
                "https://owasp.org/API-Security/editions/2023/en/0xa8-security-misconfiguration/": "API8 Security Misconfiguration",
                "https://owasp.org/API-Security/editions/2023/en/0xa9-improper-inventory-management/": "API9 Improper Inventory Management",
                "https://owasp.org/API-Security/editions/2023/en/0xaa-unsafe-consumption-of-apis/": "API10 Unsafe Consumption of APIs",
                "https://owasp.org/API-Security/editions/2023/en/0xb0-next-devs/": "API Security Next Steps for Developers",
                "https://owasp.org/API-Security/editions/2023/en/0xb1-next-devsecops/": "API Security Next Steps for DevSecOps",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"owasp-{source_key}" if source_key else "owasp"
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
            for suffix in [' | OWASP', ' - OWASP Cheat Sheet Series',
                           ' - OWASP', ' | OWASP Foundation']:
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
                        "category": "owasp-security",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)  # Respectful rate limit

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
            self.log.info(f"=== Scraping owasp/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    OwaspScraper(base, source_key).run()
