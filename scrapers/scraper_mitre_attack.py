#!/usr/bin/env python3
"""MITRE ATT&CK framework scraper.

Covers:
  - ATT&CK tactics (Enterprise, Mobile, ICS)
  - ATT&CK techniques and sub-techniques
  - Mitigations, groups, software
  - Data sources and campaigns
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class MitreAttackScraper(BaseScraper):
    """Scrape MITRE ATT&CK tactics, techniques, mitigations, groups, software, data sources, and campaigns."""

    SOURCES = {
        "tactics": {
            "pages": {
                # Enterprise tactics
                "https://attack.mitre.org/tactics/enterprise/": "Enterprise Tactics Overview",
                "https://attack.mitre.org/tactics/TA0043/": "Reconnaissance",
                "https://attack.mitre.org/tactics/TA0042/": "Resource Development",
                "https://attack.mitre.org/tactics/TA0001/": "Initial Access",
                "https://attack.mitre.org/tactics/TA0002/": "Execution",
                "https://attack.mitre.org/tactics/TA0003/": "Persistence",
                "https://attack.mitre.org/tactics/TA0004/": "Privilege Escalation",
                "https://attack.mitre.org/tactics/TA0005/": "Defense Evasion",
                "https://attack.mitre.org/tactics/TA0006/": "Credential Access",
                "https://attack.mitre.org/tactics/TA0007/": "Discovery",
                "https://attack.mitre.org/tactics/TA0008/": "Lateral Movement",
                "https://attack.mitre.org/tactics/TA0009/": "Collection",
                "https://attack.mitre.org/tactics/TA0011/": "Command and Control",
                "https://attack.mitre.org/tactics/TA0010/": "Exfiltration",
                "https://attack.mitre.org/tactics/TA0040/": "Impact",
                # Mobile tactics
                "https://attack.mitre.org/tactics/mobile/": "Mobile Tactics Overview",
                "https://attack.mitre.org/tactics/TA0027/": "Initial Access (Mobile)",
                "https://attack.mitre.org/tactics/TA0041/": "Execution (Mobile)",
                "https://attack.mitre.org/tactics/TA0028/": "Persistence (Mobile)",
                "https://attack.mitre.org/tactics/TA0029/": "Privilege Escalation (Mobile)",
                "https://attack.mitre.org/tactics/TA0030/": "Defense Evasion (Mobile)",
                "https://attack.mitre.org/tactics/TA0031/": "Credential Access (Mobile)",
                "https://attack.mitre.org/tactics/TA0032/": "Discovery (Mobile)",
                "https://attack.mitre.org/tactics/TA0033/": "Lateral Movement (Mobile)",
                "https://attack.mitre.org/tactics/TA0034/": "Collection (Mobile)",
                "https://attack.mitre.org/tactics/TA0035/": "Command and Control (Mobile)",
                "https://attack.mitre.org/tactics/TA0036/": "Exfiltration (Mobile)",
                "https://attack.mitre.org/tactics/TA0037/": "Impact (Mobile)",
                # ICS tactics
                "https://attack.mitre.org/tactics/TA0108/": "Initial Access (ICS)",
                "https://attack.mitre.org/tactics/TA0104/": "Execution (ICS)",
                "https://attack.mitre.org/tactics/TA0110/": "Persistence (ICS)",
                "https://attack.mitre.org/tactics/TA0111/": "Privilege Escalation (ICS)",
                "https://attack.mitre.org/tactics/TA0103/": "Evasion (ICS)",
                "https://attack.mitre.org/tactics/TA0109/": "Discovery (ICS)",
                "https://attack.mitre.org/tactics/TA0105/": "Lateral Movement (ICS)",
                "https://attack.mitre.org/tactics/TA0100/": "Collection (ICS)",
                "https://attack.mitre.org/tactics/TA0101/": "Command and Control (ICS)",
                "https://attack.mitre.org/tactics/TA0106/": "Inhibit Response Function (ICS)",
                "https://attack.mitre.org/tactics/TA0107/": "Impair Process Control (ICS)",
                "https://attack.mitre.org/tactics/TA0102/": "Impact (ICS)",
            },
        },
        "techniques": {
            "pages": {
                # === Reconnaissance ===
                # T1595 Active Scanning
                "https://attack.mitre.org/techniques/T1595/": "Active Scanning",
                "https://attack.mitre.org/techniques/T1595/001/": "Active Scanning: Scanning IP Blocks",
                "https://attack.mitre.org/techniques/T1595/002/": "Active Scanning: Vulnerability Scanning",
                "https://attack.mitre.org/techniques/T1595/003/": "Active Scanning: Wordlist Scanning",
                # T1592 Gather Victim Host Information
                "https://attack.mitre.org/techniques/T1592/": "Gather Victim Host Information",
                "https://attack.mitre.org/techniques/T1592/001/": "Gather Victim Host Information: Hardware",
                "https://attack.mitre.org/techniques/T1592/002/": "Gather Victim Host Information: Software",
                "https://attack.mitre.org/techniques/T1592/003/": "Gather Victim Host Information: Firmware",
                "https://attack.mitre.org/techniques/T1592/004/": "Gather Victim Host Information: Client Configurations",
                # T1589 Gather Victim Identity Information
                "https://attack.mitre.org/techniques/T1589/": "Gather Victim Identity Information",
                "https://attack.mitre.org/techniques/T1589/001/": "Gather Victim Identity Information: Credentials",
                "https://attack.mitre.org/techniques/T1589/002/": "Gather Victim Identity Information: Email Addresses",
                "https://attack.mitre.org/techniques/T1589/003/": "Gather Victim Identity Information: Employee Names",
                # T1590 Gather Victim Network Information
                "https://attack.mitre.org/techniques/T1590/": "Gather Victim Network Information",
                "https://attack.mitre.org/techniques/T1590/001/": "Gather Victim Network Information: Domain Properties",
                "https://attack.mitre.org/techniques/T1590/002/": "Gather Victim Network Information: DNS",
                "https://attack.mitre.org/techniques/T1590/003/": "Gather Victim Network Information: Network Trust Dependencies",
                "https://attack.mitre.org/techniques/T1590/004/": "Gather Victim Network Information: Network Topology",
                "https://attack.mitre.org/techniques/T1590/005/": "Gather Victim Network Information: IP Addresses",
                "https://attack.mitre.org/techniques/T1590/006/": "Gather Victim Network Information: Network Security Appliances",
                # T1591 Gather Victim Org Information
                "https://attack.mitre.org/techniques/T1591/": "Gather Victim Org Information",
                "https://attack.mitre.org/techniques/T1591/001/": "Gather Victim Org Information: Determine Physical Locations",
                "https://attack.mitre.org/techniques/T1591/002/": "Gather Victim Org Information: Business Relationships",
                "https://attack.mitre.org/techniques/T1591/003/": "Gather Victim Org Information: Identify Business Tempo",
                "https://attack.mitre.org/techniques/T1591/004/": "Gather Victim Org Information: Identify Roles",
                # T1598 Phishing for Information
                "https://attack.mitre.org/techniques/T1598/": "Phishing for Information",
                "https://attack.mitre.org/techniques/T1598/001/": "Phishing for Information: Spearphishing Service",
                "https://attack.mitre.org/techniques/T1598/002/": "Phishing for Information: Spearphishing Attachment",
                "https://attack.mitre.org/techniques/T1598/003/": "Phishing for Information: Spearphishing Link",
                "https://attack.mitre.org/techniques/T1598/004/": "Phishing for Information: Spearphishing Voice",
                # T1597 Search Closed Sources
                "https://attack.mitre.org/techniques/T1597/": "Search Closed Sources",
                "https://attack.mitre.org/techniques/T1597/001/": "Search Closed Sources: Threat Intel Vendors",
                "https://attack.mitre.org/techniques/T1597/002/": "Search Closed Sources: Purchase Technical Data",
                # T1596 Search Open Technical Databases
                "https://attack.mitre.org/techniques/T1596/": "Search Open Technical Databases",
                "https://attack.mitre.org/techniques/T1596/001/": "Search Open Technical Databases: DNS/Passive DNS",
                "https://attack.mitre.org/techniques/T1596/002/": "Search Open Technical Databases: WHOIS",
                "https://attack.mitre.org/techniques/T1596/003/": "Search Open Technical Databases: Digital Certificates",
                "https://attack.mitre.org/techniques/T1596/004/": "Search Open Technical Databases: CDNs",
                "https://attack.mitre.org/techniques/T1596/005/": "Search Open Technical Databases: Scan Databases",
                # T1593 Search Open Websites/Domains
                "https://attack.mitre.org/techniques/T1593/": "Search Open Websites/Domains",
                "https://attack.mitre.org/techniques/T1593/001/": "Search Open Websites/Domains: Social Media",
                "https://attack.mitre.org/techniques/T1593/002/": "Search Open Websites/Domains: Search Engines",
                "https://attack.mitre.org/techniques/T1593/003/": "Search Open Websites/Domains: Code Repositories",
                # T1594 Search Victim-Owned Websites
                "https://attack.mitre.org/techniques/T1594/": "Search Victim-Owned Websites",
                # === Resource Development ===
                # T1583 Acquire Infrastructure
                "https://attack.mitre.org/techniques/T1583/": "Acquire Infrastructure",
                "https://attack.mitre.org/techniques/T1583/001/": "Acquire Infrastructure: Domains",
                "https://attack.mitre.org/techniques/T1583/002/": "Acquire Infrastructure: DNS Server",
                "https://attack.mitre.org/techniques/T1583/003/": "Acquire Infrastructure: Virtual Private Server",
                "https://attack.mitre.org/techniques/T1583/004/": "Acquire Infrastructure: Server",
                "https://attack.mitre.org/techniques/T1583/005/": "Acquire Infrastructure: Botnet",
                "https://attack.mitre.org/techniques/T1583/006/": "Acquire Infrastructure: Web Services",
                "https://attack.mitre.org/techniques/T1583/007/": "Acquire Infrastructure: Serverless",
                "https://attack.mitre.org/techniques/T1583/008/": "Acquire Infrastructure: Malvertising",
                # T1586 Compromise Accounts
                "https://attack.mitre.org/techniques/T1586/": "Compromise Accounts",
                "https://attack.mitre.org/techniques/T1586/001/": "Compromise Accounts: Social Media Accounts",
                "https://attack.mitre.org/techniques/T1586/002/": "Compromise Accounts: Email Accounts",
                "https://attack.mitre.org/techniques/T1586/003/": "Compromise Accounts: Cloud Accounts",
                # T1584 Compromise Infrastructure
                "https://attack.mitre.org/techniques/T1584/": "Compromise Infrastructure",
                "https://attack.mitre.org/techniques/T1584/001/": "Compromise Infrastructure: Domains",
                "https://attack.mitre.org/techniques/T1584/002/": "Compromise Infrastructure: DNS Server",
                "https://attack.mitre.org/techniques/T1584/003/": "Compromise Infrastructure: Virtual Private Server",
                "https://attack.mitre.org/techniques/T1584/004/": "Compromise Infrastructure: Server",
                "https://attack.mitre.org/techniques/T1584/005/": "Compromise Infrastructure: Botnet",
                "https://attack.mitre.org/techniques/T1584/006/": "Compromise Infrastructure: Web Services",
                "https://attack.mitre.org/techniques/T1584/007/": "Compromise Infrastructure: Serverless",
                # T1587 Develop Capabilities
                "https://attack.mitre.org/techniques/T1587/": "Develop Capabilities",
                "https://attack.mitre.org/techniques/T1587/001/": "Develop Capabilities: Malware",
                "https://attack.mitre.org/techniques/T1587/002/": "Develop Capabilities: Code Signing Certificates",
                "https://attack.mitre.org/techniques/T1587/003/": "Develop Capabilities: Digital Certificates",
                "https://attack.mitre.org/techniques/T1587/004/": "Develop Capabilities: Exploits",
                # T1585 Establish Accounts
                "https://attack.mitre.org/techniques/T1585/": "Establish Accounts",
                "https://attack.mitre.org/techniques/T1585/001/": "Establish Accounts: Social Media Accounts",
                "https://attack.mitre.org/techniques/T1585/002/": "Establish Accounts: Email Accounts",
                "https://attack.mitre.org/techniques/T1585/003/": "Establish Accounts: Cloud Accounts",
                # T1588 Obtain Capabilities
                "https://attack.mitre.org/techniques/T1588/": "Obtain Capabilities",
                "https://attack.mitre.org/techniques/T1588/001/": "Obtain Capabilities: Malware",
                "https://attack.mitre.org/techniques/T1588/002/": "Obtain Capabilities: Tool",
                "https://attack.mitre.org/techniques/T1588/003/": "Obtain Capabilities: Code Signing Certificates",
                "https://attack.mitre.org/techniques/T1588/004/": "Obtain Capabilities: Digital Certificates",
                "https://attack.mitre.org/techniques/T1588/005/": "Obtain Capabilities: Exploits",
                "https://attack.mitre.org/techniques/T1588/006/": "Obtain Capabilities: Vulnerabilities",
                # T1608 Stage Capabilities
                "https://attack.mitre.org/techniques/T1608/": "Stage Capabilities",
                "https://attack.mitre.org/techniques/T1608/001/": "Stage Capabilities: Upload Malware",
                "https://attack.mitre.org/techniques/T1608/002/": "Stage Capabilities: Upload Tool",
                "https://attack.mitre.org/techniques/T1608/003/": "Stage Capabilities: Install Digital Certificate",
                "https://attack.mitre.org/techniques/T1608/004/": "Stage Capabilities: Drive-by Target",
                "https://attack.mitre.org/techniques/T1608/005/": "Stage Capabilities: Link Target",
                "https://attack.mitre.org/techniques/T1608/006/": "Stage Capabilities: SEO Poisoning",
                # === Initial Access ===
                "https://attack.mitre.org/techniques/T1189/": "Drive-by Compromise",
                "https://attack.mitre.org/techniques/T1190/": "Exploit Public-Facing Application",
                "https://attack.mitre.org/techniques/T1133/": "External Remote Services",
                "https://attack.mitre.org/techniques/T1200/": "Hardware Additions",
                # T1566 Phishing
                "https://attack.mitre.org/techniques/T1566/": "Phishing",
                "https://attack.mitre.org/techniques/T1566/001/": "Phishing: Spearphishing Attachment",
                "https://attack.mitre.org/techniques/T1566/002/": "Phishing: Spearphishing Link",
                "https://attack.mitre.org/techniques/T1566/003/": "Phishing: Spearphishing via Service",
                "https://attack.mitre.org/techniques/T1566/004/": "Phishing: Spearphishing Voice",
                # T1091 Replication Through Removable Media
                "https://attack.mitre.org/techniques/T1091/": "Replication Through Removable Media",
                # T1195 Supply Chain Compromise
                "https://attack.mitre.org/techniques/T1195/": "Supply Chain Compromise",
                "https://attack.mitre.org/techniques/T1195/001/": "Supply Chain Compromise: Compromise Software Dependencies and Development Tools",
                "https://attack.mitre.org/techniques/T1195/002/": "Supply Chain Compromise: Compromise Software Supply Chain",
                "https://attack.mitre.org/techniques/T1195/003/": "Supply Chain Compromise: Compromise Hardware Supply Chain",
                # T1199 Trusted Relationship
                "https://attack.mitre.org/techniques/T1199/": "Trusted Relationship",
                # T1078 Valid Accounts
                "https://attack.mitre.org/techniques/T1078/": "Valid Accounts",
                "https://attack.mitre.org/techniques/T1078/001/": "Valid Accounts: Default Accounts",
                "https://attack.mitre.org/techniques/T1078/002/": "Valid Accounts: Domain Accounts",
                "https://attack.mitre.org/techniques/T1078/003/": "Valid Accounts: Local Accounts",
                "https://attack.mitre.org/techniques/T1078/004/": "Valid Accounts: Cloud Accounts",
                # === Execution ===
                # T1059 Command and Scripting Interpreter
                "https://attack.mitre.org/techniques/T1059/": "Command and Scripting Interpreter",
                "https://attack.mitre.org/techniques/T1059/001/": "Command and Scripting Interpreter: PowerShell",
                "https://attack.mitre.org/techniques/T1059/002/": "Command and Scripting Interpreter: AppleScript",
                "https://attack.mitre.org/techniques/T1059/003/": "Command and Scripting Interpreter: Windows Command Shell",
                "https://attack.mitre.org/techniques/T1059/004/": "Command and Scripting Interpreter: Unix Shell",
                "https://attack.mitre.org/techniques/T1059/005/": "Command and Scripting Interpreter: Visual Basic",
                "https://attack.mitre.org/techniques/T1059/006/": "Command and Scripting Interpreter: Python",
                "https://attack.mitre.org/techniques/T1059/007/": "Command and Scripting Interpreter: JavaScript",
                "https://attack.mitre.org/techniques/T1059/008/": "Command and Scripting Interpreter: Network Device CLI",
                "https://attack.mitre.org/techniques/T1059/009/": "Command and Scripting Interpreter: Cloud API",
                "https://attack.mitre.org/techniques/T1059/010/": "Command and Scripting Interpreter: AutoHotKey & AutoIT",
                # T1203 Exploitation for Client Execution
                "https://attack.mitre.org/techniques/T1203/": "Exploitation for Client Execution",
                # T1559 Inter-Process Communication
                "https://attack.mitre.org/techniques/T1559/": "Inter-Process Communication",
                "https://attack.mitre.org/techniques/T1559/001/": "Inter-Process Communication: Component Object Model",
                "https://attack.mitre.org/techniques/T1559/002/": "Inter-Process Communication: Dynamic Data Exchange",
                "https://attack.mitre.org/techniques/T1559/003/": "Inter-Process Communication: XPC Services",
                # T1106 Native API
                "https://attack.mitre.org/techniques/T1106/": "Native API",
                # T1053 Scheduled Task/Job
                "https://attack.mitre.org/techniques/T1053/": "Scheduled Task/Job",
                "https://attack.mitre.org/techniques/T1053/001/": "Scheduled Task/Job: At",
                "https://attack.mitre.org/techniques/T1053/002/": "Scheduled Task/Job: At (Windows)",
                "https://attack.mitre.org/techniques/T1053/003/": "Scheduled Task/Job: Cron",
                "https://attack.mitre.org/techniques/T1053/004/": "Scheduled Task/Job: Launchd",
                "https://attack.mitre.org/techniques/T1053/005/": "Scheduled Task/Job: Scheduled Task",
                "https://attack.mitre.org/techniques/T1053/006/": "Scheduled Task/Job: Systemd Timers",
                "https://attack.mitre.org/techniques/T1053/007/": "Scheduled Task/Job: Container Orchestration Job",
                # T1129 Shared Modules
                "https://attack.mitre.org/techniques/T1129/": "Shared Modules",
                # T1072 Software Deployment Tools
                "https://attack.mitre.org/techniques/T1072/": "Software Deployment Tools",
                # T1569 System Services
                "https://attack.mitre.org/techniques/T1569/": "System Services",
                "https://attack.mitre.org/techniques/T1569/001/": "System Services: Launchctl",
                "https://attack.mitre.org/techniques/T1569/002/": "System Services: Service Execution",
                # T1204 User Execution
                "https://attack.mitre.org/techniques/T1204/": "User Execution",
                "https://attack.mitre.org/techniques/T1204/001/": "User Execution: Malicious Link",
                "https://attack.mitre.org/techniques/T1204/002/": "User Execution: Malicious File",
                "https://attack.mitre.org/techniques/T1204/003/": "User Execution: Malicious Image",
                # T1047 Windows Management Instrumentation
                "https://attack.mitre.org/techniques/T1047/": "Windows Management Instrumentation",
                # === Persistence ===
                # T1098 Account Manipulation
                "https://attack.mitre.org/techniques/T1098/": "Account Manipulation",
                "https://attack.mitre.org/techniques/T1098/001/": "Account Manipulation: Additional Cloud Credentials",
                "https://attack.mitre.org/techniques/T1098/002/": "Account Manipulation: Additional Email Delegate Permissions",
                "https://attack.mitre.org/techniques/T1098/003/": "Account Manipulation: Additional Cloud Roles",
                "https://attack.mitre.org/techniques/T1098/004/": "Account Manipulation: SSH Authorized Keys",
                "https://attack.mitre.org/techniques/T1098/005/": "Account Manipulation: Device Registration",
                "https://attack.mitre.org/techniques/T1098/006/": "Account Manipulation: Additional Container Cluster Roles",
                # T1197 BITS Jobs
                "https://attack.mitre.org/techniques/T1197/": "BITS Jobs",
                # T1547 Boot or Logon Autostart Execution
                "https://attack.mitre.org/techniques/T1547/": "Boot or Logon Autostart Execution",
                "https://attack.mitre.org/techniques/T1547/001/": "Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder",
                "https://attack.mitre.org/techniques/T1547/002/": "Boot or Logon Autostart Execution: Authentication Package",
                "https://attack.mitre.org/techniques/T1547/003/": "Boot or Logon Autostart Execution: Time Providers",
                "https://attack.mitre.org/techniques/T1547/004/": "Boot or Logon Autostart Execution: Winlogon Helper DLL",
                "https://attack.mitre.org/techniques/T1547/005/": "Boot or Logon Autostart Execution: Security Support Provider",
                "https://attack.mitre.org/techniques/T1547/006/": "Boot or Logon Autostart Execution: Kernel Modules and Extensions",
                "https://attack.mitre.org/techniques/T1547/007/": "Boot or Logon Autostart Execution: Re-opened Applications",
                "https://attack.mitre.org/techniques/T1547/008/": "Boot or Logon Autostart Execution: LSASS Driver",
                "https://attack.mitre.org/techniques/T1547/009/": "Boot or Logon Autostart Execution: Shortcut Modification",
                "https://attack.mitre.org/techniques/T1547/010/": "Boot or Logon Autostart Execution: Port Monitors",
                "https://attack.mitre.org/techniques/T1547/011/": "Boot or Logon Autostart Execution: Plist Modification",
                "https://attack.mitre.org/techniques/T1547/012/": "Boot or Logon Autostart Execution: Print Processors",
                "https://attack.mitre.org/techniques/T1547/013/": "Boot or Logon Autostart Execution: XDG Autostart Entries",
                "https://attack.mitre.org/techniques/T1547/014/": "Boot or Logon Autostart Execution: Active Setup",
                "https://attack.mitre.org/techniques/T1547/015/": "Boot or Logon Autostart Execution: Login Items",
                # T1037 Boot or Logon Initialization Scripts
                "https://attack.mitre.org/techniques/T1037/": "Boot or Logon Initialization Scripts",
                "https://attack.mitre.org/techniques/T1037/001/": "Boot or Logon Initialization Scripts: Logon Script (Windows)",
                "https://attack.mitre.org/techniques/T1037/002/": "Boot or Logon Initialization Scripts: Login Hook",
                "https://attack.mitre.org/techniques/T1037/003/": "Boot or Logon Initialization Scripts: Network Logon Script",
                "https://attack.mitre.org/techniques/T1037/004/": "Boot or Logon Initialization Scripts: RC Scripts",
                "https://attack.mitre.org/techniques/T1037/005/": "Boot or Logon Initialization Scripts: Startup Items",
                # T1176 Browser Extensions
                "https://attack.mitre.org/techniques/T1176/": "Browser Extensions",
                # T1554 Compromise Host Software Binary
                "https://attack.mitre.org/techniques/T1554/": "Compromise Host Software Binary",
                # T1136 Create Account
                "https://attack.mitre.org/techniques/T1136/": "Create Account",
                "https://attack.mitre.org/techniques/T1136/001/": "Create Account: Local Account",
                "https://attack.mitre.org/techniques/T1136/002/": "Create Account: Domain Account",
                "https://attack.mitre.org/techniques/T1136/003/": "Create Account: Cloud Account",
                # T1543 Create or Modify System Process
                "https://attack.mitre.org/techniques/T1543/": "Create or Modify System Process",
                "https://attack.mitre.org/techniques/T1543/001/": "Create or Modify System Process: Launch Agent",
                "https://attack.mitre.org/techniques/T1543/002/": "Create or Modify System Process: Systemd Service",
                "https://attack.mitre.org/techniques/T1543/003/": "Create or Modify System Process: Windows Service",
                "https://attack.mitre.org/techniques/T1543/004/": "Create or Modify System Process: Launch Daemon",
                "https://attack.mitre.org/techniques/T1543/005/": "Create or Modify System Process: Container Service",
                # T1546 Event Triggered Execution
                "https://attack.mitre.org/techniques/T1546/": "Event Triggered Execution",
                "https://attack.mitre.org/techniques/T1546/001/": "Event Triggered Execution: Change Default File Association",
                "https://attack.mitre.org/techniques/T1546/002/": "Event Triggered Execution: Screensaver",
                "https://attack.mitre.org/techniques/T1546/003/": "Event Triggered Execution: Windows Management Instrumentation Event Subscription",
                "https://attack.mitre.org/techniques/T1546/004/": "Event Triggered Execution: Unix Shell Configuration Modification",
                "https://attack.mitre.org/techniques/T1546/005/": "Event Triggered Execution: Trap",
                "https://attack.mitre.org/techniques/T1546/006/": "Event Triggered Execution: LC_LOAD_DYLIB Addition",
                "https://attack.mitre.org/techniques/T1546/007/": "Event Triggered Execution: Netsh Helper DLL",
                "https://attack.mitre.org/techniques/T1546/008/": "Event Triggered Execution: Accessibility Features",
                "https://attack.mitre.org/techniques/T1546/009/": "Event Triggered Execution: AppCert DLLs",
                "https://attack.mitre.org/techniques/T1546/010/": "Event Triggered Execution: AppInit DLLs",
                "https://attack.mitre.org/techniques/T1546/011/": "Event Triggered Execution: Application Shimming",
                "https://attack.mitre.org/techniques/T1546/012/": "Event Triggered Execution: Image File Execution Options Injection",
                "https://attack.mitre.org/techniques/T1546/013/": "Event Triggered Execution: PowerShell Profile",
                "https://attack.mitre.org/techniques/T1546/014/": "Event Triggered Execution: Emond",
                "https://attack.mitre.org/techniques/T1546/015/": "Event Triggered Execution: Component Object Model Hijacking",
                "https://attack.mitre.org/techniques/T1546/016/": "Event Triggered Execution: Installer Packages",
                # T1574 Hijack Execution Flow
                "https://attack.mitre.org/techniques/T1574/": "Hijack Execution Flow",
                "https://attack.mitre.org/techniques/T1574/001/": "Hijack Execution Flow: DLL Search Order Hijacking",
                "https://attack.mitre.org/techniques/T1574/002/": "Hijack Execution Flow: DLL Side-Loading",
                "https://attack.mitre.org/techniques/T1574/004/": "Hijack Execution Flow: Dylib Hijacking",
                "https://attack.mitre.org/techniques/T1574/005/": "Hijack Execution Flow: Executable Installer File Permissions Weakness",
                "https://attack.mitre.org/techniques/T1574/006/": "Hijack Execution Flow: Dynamic Linker Hijacking",
                "https://attack.mitre.org/techniques/T1574/007/": "Hijack Execution Flow: Path Interception by PATH Environment Variable",
                "https://attack.mitre.org/techniques/T1574/008/": "Hijack Execution Flow: Path Interception by Search Order Hijacking",
                "https://attack.mitre.org/techniques/T1574/009/": "Hijack Execution Flow: Path Interception by Unquoted Path",
                "https://attack.mitre.org/techniques/T1574/010/": "Hijack Execution Flow: Services File Permissions Weakness",
                "https://attack.mitre.org/techniques/T1574/011/": "Hijack Execution Flow: Services Registry Permissions Weakness",
                "https://attack.mitre.org/techniques/T1574/012/": "Hijack Execution Flow: COR_PROFILER",
                "https://attack.mitre.org/techniques/T1574/013/": "Hijack Execution Flow: KernelCallbackTable",
                # T1525 Implant Internal Image
                "https://attack.mitre.org/techniques/T1525/": "Implant Internal Image",
                # T1556 Modify Authentication Process
                "https://attack.mitre.org/techniques/T1556/": "Modify Authentication Process",
                "https://attack.mitre.org/techniques/T1556/001/": "Modify Authentication Process: Domain Controller Authentication",
                "https://attack.mitre.org/techniques/T1556/002/": "Modify Authentication Process: Password Filter DLL",
                "https://attack.mitre.org/techniques/T1556/003/": "Modify Authentication Process: Pluggable Authentication Modules",
                "https://attack.mitre.org/techniques/T1556/004/": "Modify Authentication Process: Network Device Authentication",
                "https://attack.mitre.org/techniques/T1556/005/": "Modify Authentication Process: Reversible Encryption",
                "https://attack.mitre.org/techniques/T1556/006/": "Modify Authentication Process: Multi-Factor Authentication",
                "https://attack.mitre.org/techniques/T1556/007/": "Modify Authentication Process: Hybrid Identity",
                "https://attack.mitre.org/techniques/T1556/008/": "Modify Authentication Process: Network Provider DLL",
                "https://attack.mitre.org/techniques/T1556/009/": "Modify Authentication Process: Conditional Access Policies",
                # T1137 Office Application Startup
                "https://attack.mitre.org/techniques/T1137/": "Office Application Startup",
                "https://attack.mitre.org/techniques/T1137/001/": "Office Application Startup: Office Template Macros",
                "https://attack.mitre.org/techniques/T1137/002/": "Office Application Startup: Office Test",
                "https://attack.mitre.org/techniques/T1137/003/": "Office Application Startup: Outlook Forms",
                "https://attack.mitre.org/techniques/T1137/004/": "Office Application Startup: Outlook Home Page",
                "https://attack.mitre.org/techniques/T1137/005/": "Office Application Startup: Outlook Rules",
                "https://attack.mitre.org/techniques/T1137/006/": "Office Application Startup: Add-ins",
                # T1542 Pre-OS Boot
                "https://attack.mitre.org/techniques/T1542/": "Pre-OS Boot",
                "https://attack.mitre.org/techniques/T1542/001/": "Pre-OS Boot: System Firmware",
                "https://attack.mitre.org/techniques/T1542/002/": "Pre-OS Boot: Component Firmware",
                "https://attack.mitre.org/techniques/T1542/003/": "Pre-OS Boot: Bootkit",
                "https://attack.mitre.org/techniques/T1542/004/": "Pre-OS Boot: ROMMONkit",
                "https://attack.mitre.org/techniques/T1542/005/": "Pre-OS Boot: TFTP Boot",
                # T1505 Server Software Component
                "https://attack.mitre.org/techniques/T1505/": "Server Software Component",
                "https://attack.mitre.org/techniques/T1505/001/": "Server Software Component: SQL Stored Procedures",
                "https://attack.mitre.org/techniques/T1505/002/": "Server Software Component: Transport Agent",
                "https://attack.mitre.org/techniques/T1505/003/": "Server Software Component: Web Shell",
                "https://attack.mitre.org/techniques/T1505/004/": "Server Software Component: IIS Components",
                "https://attack.mitre.org/techniques/T1505/005/": "Server Software Component: Terminal Services DLL",
                # T1205 Traffic Signaling
                "https://attack.mitre.org/techniques/T1205/": "Traffic Signaling",
                "https://attack.mitre.org/techniques/T1205/001/": "Traffic Signaling: Port Knocking",
                "https://attack.mitre.org/techniques/T1205/002/": "Traffic Signaling: Socket Filters",
                # === Privilege Escalation ===
                # T1548 Abuse Elevation Control Mechanism
                "https://attack.mitre.org/techniques/T1548/": "Abuse Elevation Control Mechanism",
                "https://attack.mitre.org/techniques/T1548/001/": "Abuse Elevation Control Mechanism: Setuid and Setgid",
                "https://attack.mitre.org/techniques/T1548/002/": "Abuse Elevation Control Mechanism: Bypass User Account Control",
                "https://attack.mitre.org/techniques/T1548/003/": "Abuse Elevation Control Mechanism: Sudo and Sudo Caching",
                "https://attack.mitre.org/techniques/T1548/004/": "Abuse Elevation Control Mechanism: Elevated Execution with Prompt",
                "https://attack.mitre.org/techniques/T1548/005/": "Abuse Elevation Control Mechanism: Temporary Elevated Cloud Access",
                # T1134 Access Token Manipulation
                "https://attack.mitre.org/techniques/T1134/": "Access Token Manipulation",
                "https://attack.mitre.org/techniques/T1134/001/": "Access Token Manipulation: Token Impersonation/Theft",
                "https://attack.mitre.org/techniques/T1134/002/": "Access Token Manipulation: Create Process with Token",
                "https://attack.mitre.org/techniques/T1134/003/": "Access Token Manipulation: Make and Impersonate Token",
                "https://attack.mitre.org/techniques/T1134/004/": "Access Token Manipulation: Parent PID Spoofing",
                "https://attack.mitre.org/techniques/T1134/005/": "Access Token Manipulation: SID-History Injection",
                # T1068 Exploitation for Privilege Escalation
                "https://attack.mitre.org/techniques/T1068/": "Exploitation for Privilege Escalation",
                # T1484 Domain or Tenant Policy Modification
                "https://attack.mitre.org/techniques/T1484/": "Domain or Tenant Policy Modification",
                "https://attack.mitre.org/techniques/T1484/001/": "Domain or Tenant Policy Modification: Group Policy Modification",
                "https://attack.mitre.org/techniques/T1484/002/": "Domain or Tenant Policy Modification: Trust Modification",
                # T1611 Escape to Host
                "https://attack.mitre.org/techniques/T1611/": "Escape to Host",
                # T1055 Process Injection
                "https://attack.mitre.org/techniques/T1055/": "Process Injection",
                "https://attack.mitre.org/techniques/T1055/001/": "Process Injection: Dynamic-link Library Injection",
                "https://attack.mitre.org/techniques/T1055/002/": "Process Injection: Portable Executable Injection",
                "https://attack.mitre.org/techniques/T1055/003/": "Process Injection: Thread Execution Hijacking",
                "https://attack.mitre.org/techniques/T1055/004/": "Process Injection: Asynchronous Procedure Call",
                "https://attack.mitre.org/techniques/T1055/005/": "Process Injection: Thread Local Storage",
                "https://attack.mitre.org/techniques/T1055/008/": "Process Injection: Ptrace System Calls",
                "https://attack.mitre.org/techniques/T1055/009/": "Process Injection: Proc Memory",
                "https://attack.mitre.org/techniques/T1055/011/": "Process Injection: Extra Window Memory Injection",
                "https://attack.mitre.org/techniques/T1055/012/": "Process Injection: Process Hollowing",
                "https://attack.mitre.org/techniques/T1055/013/": "Process Injection: Process Doppelganging",
                "https://attack.mitre.org/techniques/T1055/014/": "Process Injection: VDSO Hijacking",
                "https://attack.mitre.org/techniques/T1055/015/": "Process Injection: ListPlanting",
                # === Defense Evasion ===
                # T1140 Deobfuscate/Decode Files or Information
                "https://attack.mitre.org/techniques/T1140/": "Deobfuscate/Decode Files or Information",
                # T1006 Direct Volume Access
                "https://attack.mitre.org/techniques/T1006/": "Direct Volume Access",
                # T1480 Execution Guardrails
                "https://attack.mitre.org/techniques/T1480/": "Execution Guardrails",
                "https://attack.mitre.org/techniques/T1480/001/": "Execution Guardrails: Environmental Keying",
                "https://attack.mitre.org/techniques/T1480/002/": "Execution Guardrails: Mutual Exclusion",
                # T1211 Exploitation for Defense Evasion
                "https://attack.mitre.org/techniques/T1211/": "Exploitation for Defense Evasion",
                # T1222 File and Directory Permissions Modification
                "https://attack.mitre.org/techniques/T1222/": "File and Directory Permissions Modification",
                "https://attack.mitre.org/techniques/T1222/001/": "File and Directory Permissions Modification: Windows File and Directory Permissions Modification",
                "https://attack.mitre.org/techniques/T1222/002/": "File and Directory Permissions Modification: Linux and Mac File and Directory Permissions Modification",
                # T1564 Hide Artifacts
                "https://attack.mitre.org/techniques/T1564/": "Hide Artifacts",
                "https://attack.mitre.org/techniques/T1564/001/": "Hide Artifacts: Hidden Files and Directories",
                "https://attack.mitre.org/techniques/T1564/002/": "Hide Artifacts: Hidden Users",
                "https://attack.mitre.org/techniques/T1564/003/": "Hide Artifacts: Hidden Window",
                "https://attack.mitre.org/techniques/T1564/004/": "Hide Artifacts: NTFS File Attributes",
                "https://attack.mitre.org/techniques/T1564/005/": "Hide Artifacts: Hidden File System",
                "https://attack.mitre.org/techniques/T1564/006/": "Hide Artifacts: Run Virtual Instance",
                "https://attack.mitre.org/techniques/T1564/007/": "Hide Artifacts: VBA Stomping",
                "https://attack.mitre.org/techniques/T1564/008/": "Hide Artifacts: Email Hiding Rules",
                "https://attack.mitre.org/techniques/T1564/009/": "Hide Artifacts: Resource Forking",
                "https://attack.mitre.org/techniques/T1564/010/": "Hide Artifacts: Process Argument Spoofing",
                "https://attack.mitre.org/techniques/T1564/011/": "Hide Artifacts: Ignore Process Interrupts",
                # T1562 Impair Defenses
                "https://attack.mitre.org/techniques/T1562/": "Impair Defenses",
                "https://attack.mitre.org/techniques/T1562/001/": "Impair Defenses: Disable or Modify Tools",
                "https://attack.mitre.org/techniques/T1562/002/": "Impair Defenses: Disable Windows Event Logging",
                "https://attack.mitre.org/techniques/T1562/003/": "Impair Defenses: Impair Command History Logging",
                "https://attack.mitre.org/techniques/T1562/004/": "Impair Defenses: Disable or Modify System Firewall",
                "https://attack.mitre.org/techniques/T1562/006/": "Impair Defenses: Indicator Blocking",
                "https://attack.mitre.org/techniques/T1562/007/": "Impair Defenses: Disable or Modify Cloud Firewall",
                "https://attack.mitre.org/techniques/T1562/008/": "Impair Defenses: Disable or Modify Cloud Logs",
                "https://attack.mitre.org/techniques/T1562/009/": "Impair Defenses: Safe Mode Boot",
                "https://attack.mitre.org/techniques/T1562/010/": "Impair Defenses: Downgrade Attack",
                "https://attack.mitre.org/techniques/T1562/011/": "Impair Defenses: Spoof Security Alerting",
                "https://attack.mitre.org/techniques/T1562/012/": "Impair Defenses: Disable or Modify Linux Audit System",
                # T1070 Indicator Removal
                "https://attack.mitre.org/techniques/T1070/": "Indicator Removal",
                "https://attack.mitre.org/techniques/T1070/001/": "Indicator Removal: Clear Windows Event Logs",
                "https://attack.mitre.org/techniques/T1070/002/": "Indicator Removal: Clear Linux or Mac System Logs",
                "https://attack.mitre.org/techniques/T1070/003/": "Indicator Removal: Clear Command History",
                "https://attack.mitre.org/techniques/T1070/004/": "Indicator Removal: File Deletion",
                "https://attack.mitre.org/techniques/T1070/005/": "Indicator Removal: Network Share Connection Removal",
                "https://attack.mitre.org/techniques/T1070/006/": "Indicator Removal: Timestomp",
                "https://attack.mitre.org/techniques/T1070/007/": "Indicator Removal: Clear Network Connection History and Configurations",
                "https://attack.mitre.org/techniques/T1070/008/": "Indicator Removal: Clear Mailbox Data",
                "https://attack.mitre.org/techniques/T1070/009/": "Indicator Removal: Clear Persistence",
                # T1202 Indirect Command Execution
                "https://attack.mitre.org/techniques/T1202/": "Indirect Command Execution",
                # T1036 Masquerading
                "https://attack.mitre.org/techniques/T1036/": "Masquerading",
                "https://attack.mitre.org/techniques/T1036/001/": "Masquerading: Invalid Code Signature",
                "https://attack.mitre.org/techniques/T1036/002/": "Masquerading: Right-to-Left Override",
                "https://attack.mitre.org/techniques/T1036/003/": "Masquerading: Rename System Utilities",
                "https://attack.mitre.org/techniques/T1036/004/": "Masquerading: Masquerade Task or Service",
                "https://attack.mitre.org/techniques/T1036/005/": "Masquerading: Match Legitimate Name or Location",
                "https://attack.mitre.org/techniques/T1036/006/": "Masquerading: Space after Filename",
                "https://attack.mitre.org/techniques/T1036/007/": "Masquerading: Double File Extension",
                "https://attack.mitre.org/techniques/T1036/008/": "Masquerading: Masquerade File Type",
                "https://attack.mitre.org/techniques/T1036/009/": "Masquerading: Break Process Trees",
                # T1112 Modify Registry
                "https://attack.mitre.org/techniques/T1112/": "Modify Registry",
                # T1027 Obfuscated Files or Information
                "https://attack.mitre.org/techniques/T1027/": "Obfuscated Files or Information",
                "https://attack.mitre.org/techniques/T1027/001/": "Obfuscated Files or Information: Binary Padding",
                "https://attack.mitre.org/techniques/T1027/002/": "Obfuscated Files or Information: Software Packing",
                "https://attack.mitre.org/techniques/T1027/003/": "Obfuscated Files or Information: Steganography",
                "https://attack.mitre.org/techniques/T1027/004/": "Obfuscated Files or Information: Compile After Delivery",
                "https://attack.mitre.org/techniques/T1027/005/": "Obfuscated Files or Information: Indicator Removal from Tools",
                "https://attack.mitre.org/techniques/T1027/006/": "Obfuscated Files or Information: HTML Smuggling",
                "https://attack.mitre.org/techniques/T1027/007/": "Obfuscated Files or Information: Dynamic API Resolution",
                "https://attack.mitre.org/techniques/T1027/008/": "Obfuscated Files or Information: Stripped Payloads",
                "https://attack.mitre.org/techniques/T1027/009/": "Obfuscated Files or Information: Embedded Payloads",
                "https://attack.mitre.org/techniques/T1027/010/": "Obfuscated Files or Information: Command Obfuscation",
                "https://attack.mitre.org/techniques/T1027/011/": "Obfuscated Files or Information: Fileless Storage",
                "https://attack.mitre.org/techniques/T1027/012/": "Obfuscated Files or Information: LNK Icon Smuggling",
                "https://attack.mitre.org/techniques/T1027/013/": "Obfuscated Files or Information: Encrypted/Encoded File",
                # T1207 Rogue Domain Controller
                "https://attack.mitre.org/techniques/T1207/": "Rogue Domain Controller",
                # T1014 Rootkit
                "https://attack.mitre.org/techniques/T1014/": "Rootkit",
                # T1218 System Binary Proxy Execution
                "https://attack.mitre.org/techniques/T1218/": "System Binary Proxy Execution",
                "https://attack.mitre.org/techniques/T1218/001/": "System Binary Proxy Execution: Compiled HTML File",
                "https://attack.mitre.org/techniques/T1218/002/": "System Binary Proxy Execution: Control Panel",
                "https://attack.mitre.org/techniques/T1218/003/": "System Binary Proxy Execution: CMSTP",
                "https://attack.mitre.org/techniques/T1218/004/": "System Binary Proxy Execution: InstallUtil",
                "https://attack.mitre.org/techniques/T1218/005/": "System Binary Proxy Execution: Mshta",
                "https://attack.mitre.org/techniques/T1218/007/": "System Binary Proxy Execution: Msiexec",
                "https://attack.mitre.org/techniques/T1218/008/": "System Binary Proxy Execution: Odbcconf",
                "https://attack.mitre.org/techniques/T1218/009/": "System Binary Proxy Execution: Regsvcs/Regasm",
                "https://attack.mitre.org/techniques/T1218/010/": "System Binary Proxy Execution: Regsvr32",
                "https://attack.mitre.org/techniques/T1218/011/": "System Binary Proxy Execution: Rundll32",
                "https://attack.mitre.org/techniques/T1218/012/": "System Binary Proxy Execution: Verclsid",
                "https://attack.mitre.org/techniques/T1218/013/": "System Binary Proxy Execution: Mavinject",
                "https://attack.mitre.org/techniques/T1218/014/": "System Binary Proxy Execution: MMC",
                "https://attack.mitre.org/techniques/T1218/015/": "System Binary Proxy Execution: Electron Applications",
                # T1216 System Script Proxy Execution
                "https://attack.mitre.org/techniques/T1216/": "System Script Proxy Execution",
                "https://attack.mitre.org/techniques/T1216/001/": "System Script Proxy Execution: PubPrn",
                "https://attack.mitre.org/techniques/T1216/002/": "System Script Proxy Execution: SyncAppvPublishingServer",
                # T1221 Template Injection
                "https://attack.mitre.org/techniques/T1221/": "Template Injection",
                # T1127 Trusted Developer Utilities Proxy Execution
                "https://attack.mitre.org/techniques/T1127/": "Trusted Developer Utilities Proxy Execution",
                "https://attack.mitre.org/techniques/T1127/001/": "Trusted Developer Utilities Proxy Execution: MSBuild",
                # T1535 Unused/Unsupported Cloud Regions
                "https://attack.mitre.org/techniques/T1535/": "Unused/Unsupported Cloud Regions",
                # T1550 Use Alternate Authentication Material
                "https://attack.mitre.org/techniques/T1550/": "Use Alternate Authentication Material",
                "https://attack.mitre.org/techniques/T1550/001/": "Use Alternate Authentication Material: Application Access Token",
                "https://attack.mitre.org/techniques/T1550/002/": "Use Alternate Authentication Material: Pass the Hash",
                "https://attack.mitre.org/techniques/T1550/003/": "Use Alternate Authentication Material: Pass the Ticket",
                "https://attack.mitre.org/techniques/T1550/004/": "Use Alternate Authentication Material: Web Session Cookie",
                # T1497 Virtualization/Sandbox Evasion
                "https://attack.mitre.org/techniques/T1497/": "Virtualization/Sandbox Evasion",
                "https://attack.mitre.org/techniques/T1497/001/": "Virtualization/Sandbox Evasion: System Checks",
                "https://attack.mitre.org/techniques/T1497/002/": "Virtualization/Sandbox Evasion: User Activity Based Checks",
                "https://attack.mitre.org/techniques/T1497/003/": "Virtualization/Sandbox Evasion: Time Based Evasion",
                # T1600 Weaken Encryption
                "https://attack.mitre.org/techniques/T1600/": "Weaken Encryption",
                "https://attack.mitre.org/techniques/T1600/001/": "Weaken Encryption: Reduce Key Space",
                "https://attack.mitre.org/techniques/T1600/002/": "Weaken Encryption: Disable Crypto Hardware",
                # T1220 XSL Script Processing
                "https://attack.mitre.org/techniques/T1220/": "XSL Script Processing",
                # === Credential Access ===
                # T1557 Adversary-in-the-Middle
                "https://attack.mitre.org/techniques/T1557/": "Adversary-in-the-Middle",
                "https://attack.mitre.org/techniques/T1557/001/": "Adversary-in-the-Middle: LLMNR/NBT-NS Poisoning and SMB Relay",
                "https://attack.mitre.org/techniques/T1557/002/": "Adversary-in-the-Middle: ARP Cache Poisoning",
                "https://attack.mitre.org/techniques/T1557/003/": "Adversary-in-the-Middle: DHCP Spoofing",
                # T1110 Brute Force
                "https://attack.mitre.org/techniques/T1110/": "Brute Force",
                "https://attack.mitre.org/techniques/T1110/001/": "Brute Force: Password Guessing",
                "https://attack.mitre.org/techniques/T1110/002/": "Brute Force: Password Cracking",
                "https://attack.mitre.org/techniques/T1110/003/": "Brute Force: Password Spraying",
                "https://attack.mitre.org/techniques/T1110/004/": "Brute Force: Credential Stuffing",
                # T1555 Credentials from Password Stores
                "https://attack.mitre.org/techniques/T1555/": "Credentials from Password Stores",
                "https://attack.mitre.org/techniques/T1555/001/": "Credentials from Password Stores: Keychain",
                "https://attack.mitre.org/techniques/T1555/002/": "Credentials from Password Stores: Securityd Memory",
                "https://attack.mitre.org/techniques/T1555/003/": "Credentials from Password Stores: Credentials from Web Browsers",
                "https://attack.mitre.org/techniques/T1555/004/": "Credentials from Password Stores: Windows Credential Manager",
                "https://attack.mitre.org/techniques/T1555/005/": "Credentials from Password Stores: Password Managers",
                "https://attack.mitre.org/techniques/T1555/006/": "Credentials from Password Stores: Cloud Secrets Management Stores",
                # T1212 Exploitation for Credential Access
                "https://attack.mitre.org/techniques/T1212/": "Exploitation for Credential Access",
                # T1187 Forced Authentication
                "https://attack.mitre.org/techniques/T1187/": "Forced Authentication",
                # T1606 Forge Web Credentials
                "https://attack.mitre.org/techniques/T1606/": "Forge Web Credentials",
                "https://attack.mitre.org/techniques/T1606/001/": "Forge Web Credentials: Web Cookies",
                "https://attack.mitre.org/techniques/T1606/002/": "Forge Web Credentials: SAML Tokens",
                # T1056 Input Capture
                "https://attack.mitre.org/techniques/T1056/": "Input Capture",
                "https://attack.mitre.org/techniques/T1056/001/": "Input Capture: Keylogging",
                "https://attack.mitre.org/techniques/T1056/002/": "Input Capture: GUI Input Capture",
                "https://attack.mitre.org/techniques/T1056/003/": "Input Capture: Web Portal Capture",
                "https://attack.mitre.org/techniques/T1056/004/": "Input Capture: Credential API Hooking",
                # T1111 Multi-Factor Authentication Interception
                "https://attack.mitre.org/techniques/T1111/": "Multi-Factor Authentication Interception",
                # T1621 Multi-Factor Authentication Request Generation
                "https://attack.mitre.org/techniques/T1621/": "Multi-Factor Authentication Request Generation",
                # T1040 Network Sniffing
                "https://attack.mitre.org/techniques/T1040/": "Network Sniffing",
                # T1003 OS Credential Dumping
                "https://attack.mitre.org/techniques/T1003/": "OS Credential Dumping",
                "https://attack.mitre.org/techniques/T1003/001/": "OS Credential Dumping: LSASS Memory",
                "https://attack.mitre.org/techniques/T1003/002/": "OS Credential Dumping: Security Account Manager",
                "https://attack.mitre.org/techniques/T1003/003/": "OS Credential Dumping: NTDS",
                "https://attack.mitre.org/techniques/T1003/004/": "OS Credential Dumping: LSA Secrets",
                "https://attack.mitre.org/techniques/T1003/005/": "OS Credential Dumping: Cached Domain Credentials",
                "https://attack.mitre.org/techniques/T1003/006/": "OS Credential Dumping: DCSync",
                "https://attack.mitre.org/techniques/T1003/007/": "OS Credential Dumping: Proc Filesystem",
                "https://attack.mitre.org/techniques/T1003/008/": "OS Credential Dumping: /etc/passwd and /etc/shadow",
                # T1528 Steal Application Access Token
                "https://attack.mitre.org/techniques/T1528/": "Steal Application Access Token",
                # T1558 Steal or Forge Kerberos Tickets
                "https://attack.mitre.org/techniques/T1558/": "Steal or Forge Kerberos Tickets",
                "https://attack.mitre.org/techniques/T1558/001/": "Steal or Forge Kerberos Tickets: Golden Ticket",
                "https://attack.mitre.org/techniques/T1558/002/": "Steal or Forge Kerberos Tickets: Silver Ticket",
                "https://attack.mitre.org/techniques/T1558/003/": "Steal or Forge Kerberos Tickets: Kerberoasting",
                "https://attack.mitre.org/techniques/T1558/004/": "Steal or Forge Kerberos Tickets: AS-REP Roasting",
                # T1539 Steal Web Session Cookie
                "https://attack.mitre.org/techniques/T1539/": "Steal Web Session Cookie",
                # T1552 Unsecured Credentials
                "https://attack.mitre.org/techniques/T1552/": "Unsecured Credentials",
                "https://attack.mitre.org/techniques/T1552/001/": "Unsecured Credentials: Credentials In Files",
                "https://attack.mitre.org/techniques/T1552/002/": "Unsecured Credentials: Credentials in Registry",
                "https://attack.mitre.org/techniques/T1552/003/": "Unsecured Credentials: Bash History",
                "https://attack.mitre.org/techniques/T1552/004/": "Unsecured Credentials: Private Keys",
                "https://attack.mitre.org/techniques/T1552/005/": "Unsecured Credentials: Cloud Instance Metadata API",
                "https://attack.mitre.org/techniques/T1552/006/": "Unsecured Credentials: Group Policy Preferences",
                "https://attack.mitre.org/techniques/T1552/007/": "Unsecured Credentials: Container API",
                "https://attack.mitre.org/techniques/T1552/008/": "Unsecured Credentials: Chat Messages",
                # === Discovery ===
                # T1087 Account Discovery
                "https://attack.mitre.org/techniques/T1087/": "Account Discovery",
                "https://attack.mitre.org/techniques/T1087/001/": "Account Discovery: Local Account",
                "https://attack.mitre.org/techniques/T1087/002/": "Account Discovery: Domain Account",
                "https://attack.mitre.org/techniques/T1087/003/": "Account Discovery: Email Account",
                "https://attack.mitre.org/techniques/T1087/004/": "Account Discovery: Cloud Account",
                # T1010 Application Window Discovery
                "https://attack.mitre.org/techniques/T1010/": "Application Window Discovery",
                # T1217 Browser Information Discovery
                "https://attack.mitre.org/techniques/T1217/": "Browser Information Discovery",
                # T1580 Cloud Infrastructure Discovery
                "https://attack.mitre.org/techniques/T1580/": "Cloud Infrastructure Discovery",
                # T1538 Cloud Service Dashboard
                "https://attack.mitre.org/techniques/T1538/": "Cloud Service Dashboard",
                # T1526 Cloud Service Discovery
                "https://attack.mitre.org/techniques/T1526/": "Cloud Service Discovery",
                # T1613 Container and Resource Discovery
                "https://attack.mitre.org/techniques/T1613/": "Container and Resource Discovery",
                # T1482 Domain Trust Discovery
                "https://attack.mitre.org/techniques/T1482/": "Domain Trust Discovery",
                # T1083 File and Directory Discovery
                "https://attack.mitre.org/techniques/T1083/": "File and Directory Discovery",
                # T1615 Group Policy Discovery
                "https://attack.mitre.org/techniques/T1615/": "Group Policy Discovery",
                # T1046 Network Service Discovery
                "https://attack.mitre.org/techniques/T1046/": "Network Service Discovery",
                # T1135 Network Share Discovery
                "https://attack.mitre.org/techniques/T1135/": "Network Share Discovery",
                # T1201 Password Policy Discovery
                "https://attack.mitre.org/techniques/T1201/": "Password Policy Discovery",
                # T1120 Peripheral Device Discovery
                "https://attack.mitre.org/techniques/T1120/": "Peripheral Device Discovery",
                # T1069 Permission Groups Discovery
                "https://attack.mitre.org/techniques/T1069/": "Permission Groups Discovery",
                "https://attack.mitre.org/techniques/T1069/001/": "Permission Groups Discovery: Local Groups",
                "https://attack.mitre.org/techniques/T1069/002/": "Permission Groups Discovery: Domain Groups",
                "https://attack.mitre.org/techniques/T1069/003/": "Permission Groups Discovery: Cloud Groups",
                # T1057 Process Discovery
                "https://attack.mitre.org/techniques/T1057/": "Process Discovery",
                # T1012 Query Registry
                "https://attack.mitre.org/techniques/T1012/": "Query Registry",
                # T1018 Remote System Discovery
                "https://attack.mitre.org/techniques/T1018/": "Remote System Discovery",
                # T1518 Software Discovery
                "https://attack.mitre.org/techniques/T1518/": "Software Discovery",
                "https://attack.mitre.org/techniques/T1518/001/": "Software Discovery: Security Software Discovery",
                # T1082 System Information Discovery
                "https://attack.mitre.org/techniques/T1082/": "System Information Discovery",
                # T1016 System Network Configuration Discovery
                "https://attack.mitre.org/techniques/T1016/": "System Network Configuration Discovery",
                "https://attack.mitre.org/techniques/T1016/001/": "System Network Configuration Discovery: Internet Connection Discovery",
                "https://attack.mitre.org/techniques/T1016/002/": "System Network Configuration Discovery: Wi-Fi Discovery",
                # T1049 System Network Connections Discovery
                "https://attack.mitre.org/techniques/T1049/": "System Network Connections Discovery",
                # T1033 System Owner/User Discovery
                "https://attack.mitre.org/techniques/T1033/": "System Owner/User Discovery",
                # T1007 System Service Discovery
                "https://attack.mitre.org/techniques/T1007/": "System Service Discovery",
                # T1124 System Time Discovery
                "https://attack.mitre.org/techniques/T1124/": "System Time Discovery",
                # === Lateral Movement ===
                # T1210 Exploitation of Remote Services
                "https://attack.mitre.org/techniques/T1210/": "Exploitation of Remote Services",
                # T1534 Internal Spearphishing
                "https://attack.mitre.org/techniques/T1534/": "Internal Spearphishing",
                # T1570 Lateral Tool Transfer
                "https://attack.mitre.org/techniques/T1570/": "Lateral Tool Transfer",
                # T1563 Remote Service Session Hijacking
                "https://attack.mitre.org/techniques/T1563/": "Remote Service Session Hijacking",
                "https://attack.mitre.org/techniques/T1563/001/": "Remote Service Session Hijacking: SSH Hijacking",
                "https://attack.mitre.org/techniques/T1563/002/": "Remote Service Session Hijacking: RDP Hijacking",
                # T1021 Remote Services
                "https://attack.mitre.org/techniques/T1021/": "Remote Services",
                "https://attack.mitre.org/techniques/T1021/001/": "Remote Services: Remote Desktop Protocol",
                "https://attack.mitre.org/techniques/T1021/002/": "Remote Services: SMB/Windows Admin Shares",
                "https://attack.mitre.org/techniques/T1021/003/": "Remote Services: Distributed Component Object Model",
                "https://attack.mitre.org/techniques/T1021/004/": "Remote Services: SSH",
                "https://attack.mitre.org/techniques/T1021/005/": "Remote Services: VNC",
                "https://attack.mitre.org/techniques/T1021/006/": "Remote Services: Windows Remote Management",
                "https://attack.mitre.org/techniques/T1021/007/": "Remote Services: Cloud Services",
                # T1080 Taint Shared Content
                "https://attack.mitre.org/techniques/T1080/": "Taint Shared Content",
                # === Collection ===
                # T1560 Archive Collected Data
                "https://attack.mitre.org/techniques/T1560/": "Archive Collected Data",
                "https://attack.mitre.org/techniques/T1560/001/": "Archive Collected Data: Archive via Utility",
                "https://attack.mitre.org/techniques/T1560/002/": "Archive Collected Data: Archive via Library",
                "https://attack.mitre.org/techniques/T1560/003/": "Archive Collected Data: Archive via Custom Method",
                # T1123 Audio Capture
                "https://attack.mitre.org/techniques/T1123/": "Audio Capture",
                # T1119 Automated Collection
                "https://attack.mitre.org/techniques/T1119/": "Automated Collection",
                # T1185 Browser Session Hijacking
                "https://attack.mitre.org/techniques/T1185/": "Browser Session Hijacking",
                # T1115 Clipboard Data
                "https://attack.mitre.org/techniques/T1115/": "Clipboard Data",
                # T1530 Data from Cloud Storage
                "https://attack.mitre.org/techniques/T1530/": "Data from Cloud Storage",
                # T1213 Data from Information Repositories
                "https://attack.mitre.org/techniques/T1213/": "Data from Information Repositories",
                "https://attack.mitre.org/techniques/T1213/001/": "Data from Information Repositories: Confluence",
                "https://attack.mitre.org/techniques/T1213/002/": "Data from Information Repositories: Sharepoint",
                "https://attack.mitre.org/techniques/T1213/003/": "Data from Information Repositories: Code Repositories",
                # T1005 Data from Local System
                "https://attack.mitre.org/techniques/T1005/": "Data from Local System",
                # T1039 Data from Network Shared Drive
                "https://attack.mitre.org/techniques/T1039/": "Data from Network Shared Drive",
                # T1025 Data from Removable Media
                "https://attack.mitre.org/techniques/T1025/": "Data from Removable Media",
                # T1074 Data Staged
                "https://attack.mitre.org/techniques/T1074/": "Data Staged",
                "https://attack.mitre.org/techniques/T1074/001/": "Data Staged: Local Data Staging",
                "https://attack.mitre.org/techniques/T1074/002/": "Data Staged: Remote Data Staging",
                # T1114 Email Collection
                "https://attack.mitre.org/techniques/T1114/": "Email Collection",
                "https://attack.mitre.org/techniques/T1114/001/": "Email Collection: Local Email Collection",
                "https://attack.mitre.org/techniques/T1114/002/": "Email Collection: Remote Email Collection",
                "https://attack.mitre.org/techniques/T1114/003/": "Email Collection: Email Forwarding Rule",
                # T1113 Screen Capture
                "https://attack.mitre.org/techniques/T1113/": "Screen Capture",
                # T1125 Video Capture
                "https://attack.mitre.org/techniques/T1125/": "Video Capture",
                # === Command and Control ===
                # T1071 Application Layer Protocol
                "https://attack.mitre.org/techniques/T1071/": "Application Layer Protocol",
                "https://attack.mitre.org/techniques/T1071/001/": "Application Layer Protocol: Web Protocols",
                "https://attack.mitre.org/techniques/T1071/002/": "Application Layer Protocol: File Transfer Protocols",
                "https://attack.mitre.org/techniques/T1071/003/": "Application Layer Protocol: Mail Protocols",
                "https://attack.mitre.org/techniques/T1071/004/": "Application Layer Protocol: DNS",
                # T1132 Data Encoding
                "https://attack.mitre.org/techniques/T1132/": "Data Encoding",
                "https://attack.mitre.org/techniques/T1132/001/": "Data Encoding: Standard Encoding",
                "https://attack.mitre.org/techniques/T1132/002/": "Data Encoding: Non-Standard Encoding",
                # T1001 Data Obfuscation
                "https://attack.mitre.org/techniques/T1001/": "Data Obfuscation",
                "https://attack.mitre.org/techniques/T1001/001/": "Data Obfuscation: Junk Data",
                "https://attack.mitre.org/techniques/T1001/002/": "Data Obfuscation: Steganography",
                "https://attack.mitre.org/techniques/T1001/003/": "Data Obfuscation: Protocol Impersonation",
                # T1568 Dynamic Resolution
                "https://attack.mitre.org/techniques/T1568/": "Dynamic Resolution",
                "https://attack.mitre.org/techniques/T1568/001/": "Dynamic Resolution: Fast Flux DNS",
                "https://attack.mitre.org/techniques/T1568/002/": "Dynamic Resolution: Domain Generation Algorithms",
                "https://attack.mitre.org/techniques/T1568/003/": "Dynamic Resolution: DNS Calculation",
                # T1573 Encrypted Channel
                "https://attack.mitre.org/techniques/T1573/": "Encrypted Channel",
                "https://attack.mitre.org/techniques/T1573/001/": "Encrypted Channel: Symmetric Cryptography",
                "https://attack.mitre.org/techniques/T1573/002/": "Encrypted Channel: Asymmetric Cryptography",
                # T1008 Fallback Channels
                "https://attack.mitre.org/techniques/T1008/": "Fallback Channels",
                # T1105 Ingress Tool Transfer
                "https://attack.mitre.org/techniques/T1105/": "Ingress Tool Transfer",
                # T1104 Multi-Stage Channels
                "https://attack.mitre.org/techniques/T1104/": "Multi-Stage Channels",
                # T1095 Non-Application Layer Protocol
                "https://attack.mitre.org/techniques/T1095/": "Non-Application Layer Protocol",
                # T1571 Non-Standard Port
                "https://attack.mitre.org/techniques/T1571/": "Non-Standard Port",
                # T1572 Protocol Tunneling
                "https://attack.mitre.org/techniques/T1572/": "Protocol Tunneling",
                # T1090 Proxy
                "https://attack.mitre.org/techniques/T1090/": "Proxy",
                "https://attack.mitre.org/techniques/T1090/001/": "Proxy: Internal Proxy",
                "https://attack.mitre.org/techniques/T1090/002/": "Proxy: External Proxy",
                "https://attack.mitre.org/techniques/T1090/003/": "Proxy: Multi-hop Proxy",
                "https://attack.mitre.org/techniques/T1090/004/": "Proxy: Domain Fronting",
                # T1219 Remote Access Software
                "https://attack.mitre.org/techniques/T1219/": "Remote Access Software",
                # T1102 Web Service
                "https://attack.mitre.org/techniques/T1102/": "Web Service",
                "https://attack.mitre.org/techniques/T1102/001/": "Web Service: Dead Drop Resolver",
                "https://attack.mitre.org/techniques/T1102/002/": "Web Service: Bidirectional Communication",
                "https://attack.mitre.org/techniques/T1102/003/": "Web Service: One-Way Communication",
                # === Exfiltration ===
                # T1020 Automated Exfiltration
                "https://attack.mitre.org/techniques/T1020/": "Automated Exfiltration",
                "https://attack.mitre.org/techniques/T1020/001/": "Automated Exfiltration: Traffic Duplication",
                "https://attack.mitre.org/techniques/T1020/002/": "Automated Exfiltration: Configuration Harvesting",
                # T1030 Data Transfer Size Limits
                "https://attack.mitre.org/techniques/T1030/": "Data Transfer Size Limits",
                # T1048 Exfiltration Over Alternative Protocol
                "https://attack.mitre.org/techniques/T1048/": "Exfiltration Over Alternative Protocol",
                "https://attack.mitre.org/techniques/T1048/001/": "Exfiltration Over Alternative Protocol: Exfiltration Over Symmetric Encrypted Non-C2 Protocol",
                "https://attack.mitre.org/techniques/T1048/002/": "Exfiltration Over Alternative Protocol: Exfiltration Over Asymmetric Encrypted Non-C2 Protocol",
                "https://attack.mitre.org/techniques/T1048/003/": "Exfiltration Over Alternative Protocol: Exfiltration Over Unencrypted Non-C2 Protocol",
                # T1041 Exfiltration Over C2 Channel
                "https://attack.mitre.org/techniques/T1041/": "Exfiltration Over C2 Channel",
                # T1011 Exfiltration Over Other Network Medium
                "https://attack.mitre.org/techniques/T1011/": "Exfiltration Over Other Network Medium",
                "https://attack.mitre.org/techniques/T1011/001/": "Exfiltration Over Other Network Medium: Exfiltration Over Bluetooth",
                # T1052 Exfiltration Over Physical Medium
                "https://attack.mitre.org/techniques/T1052/": "Exfiltration Over Physical Medium",
                "https://attack.mitre.org/techniques/T1052/001/": "Exfiltration Over Physical Medium: Exfiltration over USB",
                # T1567 Exfiltration Over Web Service
                "https://attack.mitre.org/techniques/T1567/": "Exfiltration Over Web Service",
                "https://attack.mitre.org/techniques/T1567/001/": "Exfiltration Over Web Service: Exfiltration to Code Repository",
                "https://attack.mitre.org/techniques/T1567/002/": "Exfiltration Over Web Service: Exfiltration to Cloud Storage",
                "https://attack.mitre.org/techniques/T1567/003/": "Exfiltration Over Web Service: Exfiltration to Text Storage Sites",
                "https://attack.mitre.org/techniques/T1567/004/": "Exfiltration Over Web Service: Exfiltration Over Webhook",
                # T1029 Scheduled Transfer
                "https://attack.mitre.org/techniques/T1029/": "Scheduled Transfer",
                # T1537 Transfer Data to Cloud Account
                "https://attack.mitre.org/techniques/T1537/": "Transfer Data to Cloud Account",
                # === Impact ===
                # T1531 Account Access Removal
                "https://attack.mitre.org/techniques/T1531/": "Account Access Removal",
                # T1485 Data Destruction
                "https://attack.mitre.org/techniques/T1485/": "Data Destruction",
                # T1486 Data Encrypted for Impact
                "https://attack.mitre.org/techniques/T1486/": "Data Encrypted for Impact",
                # T1565 Data Manipulation
                "https://attack.mitre.org/techniques/T1565/": "Data Manipulation",
                "https://attack.mitre.org/techniques/T1565/001/": "Data Manipulation: Stored Data Manipulation",
                "https://attack.mitre.org/techniques/T1565/002/": "Data Manipulation: Transmitted Data Manipulation",
                "https://attack.mitre.org/techniques/T1565/003/": "Data Manipulation: Runtime Data Manipulation",
                # T1491 Defacement
                "https://attack.mitre.org/techniques/T1491/": "Defacement",
                "https://attack.mitre.org/techniques/T1491/001/": "Defacement: Internal Defacement",
                "https://attack.mitre.org/techniques/T1491/002/": "Defacement: External Defacement",
                # T1561 Disk Wipe
                "https://attack.mitre.org/techniques/T1561/": "Disk Wipe",
                "https://attack.mitre.org/techniques/T1561/001/": "Disk Wipe: Disk Content Wipe",
                "https://attack.mitre.org/techniques/T1561/002/": "Disk Wipe: Disk Structure Wipe",
                # T1499 Endpoint Denial of Service
                "https://attack.mitre.org/techniques/T1499/": "Endpoint Denial of Service",
                "https://attack.mitre.org/techniques/T1499/001/": "Endpoint Denial of Service: OS Exhaustion Flood",
                "https://attack.mitre.org/techniques/T1499/002/": "Endpoint Denial of Service: Service Exhaustion Flood",
                "https://attack.mitre.org/techniques/T1499/003/": "Endpoint Denial of Service: Application Exhaustion Flood",
                "https://attack.mitre.org/techniques/T1499/004/": "Endpoint Denial of Service: Application or System Exploitation",
                # T1495 Firmware Corruption
                "https://attack.mitre.org/techniques/T1495/": "Firmware Corruption",
                # T1490 Inhibit System Recovery
                "https://attack.mitre.org/techniques/T1490/": "Inhibit System Recovery",
                # T1498 Network Denial of Service
                "https://attack.mitre.org/techniques/T1498/": "Network Denial of Service",
                "https://attack.mitre.org/techniques/T1498/001/": "Network Denial of Service: Direct Network Flood",
                "https://attack.mitre.org/techniques/T1498/002/": "Network Denial of Service: Reflection Amplification",
                # T1496 Resource Hijacking
                "https://attack.mitre.org/techniques/T1496/": "Resource Hijacking",
                "https://attack.mitre.org/techniques/T1496/001/": "Resource Hijacking: Compute Hijacking",
                "https://attack.mitre.org/techniques/T1496/002/": "Resource Hijacking: Bandwidth Hijacking",
                "https://attack.mitre.org/techniques/T1496/003/": "Resource Hijacking: SMS Pumping",
                # T1489 Service Stop
                "https://attack.mitre.org/techniques/T1489/": "Service Stop",
                # T1529 System Shutdown/Reboot
                "https://attack.mitre.org/techniques/T1529/": "System Shutdown/Reboot",
            },
        },
        "mitigations": {
            "pages": {
                "https://attack.mitre.org/mitigations/enterprise/": "Enterprise Mitigations Overview",
                "https://attack.mitre.org/mitigations/M1036/": "Account Use Policies",
                "https://attack.mitre.org/mitigations/M1015/": "Active Directory Configuration",
                "https://attack.mitre.org/mitigations/M1049/": "Antivirus/Antimalware",
                "https://attack.mitre.org/mitigations/M1048/": "Application Isolation and Sandboxing",
                "https://attack.mitre.org/mitigations/M1047/": "Audit",
                "https://attack.mitre.org/mitigations/M1040/": "Behavior Prevention on Endpoint",
                "https://attack.mitre.org/mitigations/M1046/": "Boot Integrity",
                "https://attack.mitre.org/mitigations/M1045/": "Code Signing",
                "https://attack.mitre.org/mitigations/M1043/": "Credential Access Protection",
                "https://attack.mitre.org/mitigations/M1053/": "Data Loss Prevention",
                "https://attack.mitre.org/mitigations/M1042/": "Disable or Remove Feature or Program",
                "https://attack.mitre.org/mitigations/M1055/": "Do Not Mitigate",
                "https://attack.mitre.org/mitigations/M1041/": "Encrypt Sensitive Information",
                "https://attack.mitre.org/mitigations/M1039/": "Environment Variable Permissions",
                "https://attack.mitre.org/mitigations/M1038/": "Execution Prevention",
                "https://attack.mitre.org/mitigations/M1050/": "Exploit Protection",
                "https://attack.mitre.org/mitigations/M1037/": "Filter Network Traffic",
                "https://attack.mitre.org/mitigations/M1035/": "Limit Access to Resource Over Network",
                "https://attack.mitre.org/mitigations/M1034/": "Limit Hardware Installation",
                "https://attack.mitre.org/mitigations/M1033/": "Limit Software Installation",
                "https://attack.mitre.org/mitigations/M1032/": "Multi-factor Authentication",
                "https://attack.mitre.org/mitigations/M1031/": "Network Intrusion Prevention",
                "https://attack.mitre.org/mitigations/M1030/": "Network Segmentation",
                "https://attack.mitre.org/mitigations/M1028/": "Operating System Configuration",
                "https://attack.mitre.org/mitigations/M1027/": "Password Policies",
                "https://attack.mitre.org/mitigations/M1026/": "Privileged Account Management",
                "https://attack.mitre.org/mitigations/M1025/": "Privileged Process Integrity",
                "https://attack.mitre.org/mitigations/M1029/": "Remote Data Storage",
                "https://attack.mitre.org/mitigations/M1054/": "Software Configuration",
                "https://attack.mitre.org/mitigations/M1024/": "Restrict Registry Permissions",
                "https://attack.mitre.org/mitigations/M1044/": "Restrict Web-Based Content",
                "https://attack.mitre.org/mitigations/M1022/": "Restrict File and Directory Permissions",
                "https://attack.mitre.org/mitigations/M1018/": "User Account Management",
                "https://attack.mitre.org/mitigations/M1017/": "User Training",
                "https://attack.mitre.org/mitigations/M1016/": "Vulnerability Scanning",
                "https://attack.mitre.org/mitigations/M1051/": "Update Software",
                "https://attack.mitre.org/mitigations/M1052/": "User Account Control",
                "https://attack.mitre.org/mitigations/M1056/": "Pre-compromise",
                "https://attack.mitre.org/mitigations/M1057/": "Data Loss Prevention",
                "https://attack.mitre.org/mitigations/M1021/": "Restrict Web-Based Content",
            },
        },
        "groups": {
            "pages": {
                "https://attack.mitre.org/groups/G0007/": "APT28",
                "https://attack.mitre.org/groups/G0016/": "APT29",
                "https://attack.mitre.org/groups/G0022/": "APT3",
                "https://attack.mitre.org/groups/G0050/": "APT32",
                "https://attack.mitre.org/groups/G0064/": "APT33",
                "https://attack.mitre.org/groups/G0067/": "APT37",
                "https://attack.mitre.org/groups/G0082/": "APT38",
                "https://attack.mitre.org/groups/G0096/": "APT41",
                "https://attack.mitre.org/groups/G0001/": "Axiom",
                "https://attack.mitre.org/groups/G0060/": "BRONZE BUTLER",
                "https://attack.mitre.org/groups/G0008/": "Carbanak",
                "https://attack.mitre.org/groups/G0114/": "Chimera",
                "https://attack.mitre.org/groups/G0080/": "Cobalt Group",
                "https://attack.mitre.org/groups/G0009/": "Deep Panda",
                "https://attack.mitre.org/groups/G0035/": "Dragonfly",
                "https://attack.mitre.org/groups/G0074/": "Dragonfly 2.0",
                "https://attack.mitre.org/groups/G0066/": "Elderwood",
                "https://attack.mitre.org/groups/G0032/": "Lazarus Group",
                "https://attack.mitre.org/groups/G0077/": "Leafminer",
                "https://attack.mitre.org/groups/G0059/": "Magic Hound",
                "https://attack.mitre.org/groups/G0045/": "menuPass",
                "https://attack.mitre.org/groups/G0069/": "MuddyWater",
                "https://attack.mitre.org/groups/G0129/": "Mustang Panda",
                "https://attack.mitre.org/groups/G0049/": "OilRig",
                "https://attack.mitre.org/groups/G0068/": "PLATINUM",
                "https://attack.mitre.org/groups/G0034/": "Sandworm Team",
                "https://attack.mitre.org/groups/G0091/": "Silence",
                "https://attack.mitre.org/groups/G0027/": "Threat Group-3390",
                "https://attack.mitre.org/groups/G0010/": "Turla",
                "https://attack.mitre.org/groups/G0102/": "Wizard Spider",
                "https://attack.mitre.org/groups/G0100/": "Inception",
                "https://attack.mitre.org/groups/G0065/": "Leviathan",
                "https://attack.mitre.org/groups/G0004/": "Ke3chang",
                "https://attack.mitre.org/groups/G0026/": "APT18",
                "https://attack.mitre.org/groups/G0073/": "APT19",
                "https://attack.mitre.org/groups/G0005/": "APT12",
                "https://attack.mitre.org/groups/G0006/": "APT1",
                "https://attack.mitre.org/groups/G0023/": "APT16",
                "https://attack.mitre.org/groups/G0025/": "APT17",
                "https://attack.mitre.org/groups/G0079/": "DarkHydrus",
                "https://attack.mitre.org/groups/G0085/": "FIN4",
                "https://attack.mitre.org/groups/G0037/": "FIN6",
                "https://attack.mitre.org/groups/G0046/": "FIN7",
                "https://attack.mitre.org/groups/G0061/": "FIN8",
                "https://attack.mitre.org/groups/G0047/": "Gamaredon Group",
                "https://attack.mitre.org/groups/G0078/": "Gorgon Group",
                "https://attack.mitre.org/groups/G0043/": "Group5",
                "https://attack.mitre.org/groups/G0125/": "HAFNIUM",
                "https://attack.mitre.org/groups/G0126/": "Higaisa",
                "https://attack.mitre.org/groups/G0136/": "IndigoZebra",
                "https://attack.mitre.org/groups/G0094/": "Kimsuky",
                "https://attack.mitre.org/groups/G0095/": "Machete",
                "https://attack.mitre.org/groups/G0103/": "Mofang",
                "https://attack.mitre.org/groups/G0021/": "Molerats",
                "https://attack.mitre.org/groups/G0019/": "Naikon",
                "https://attack.mitre.org/groups/G0098/": "BlackTech",
                "https://attack.mitre.org/groups/G0115/": "GOLD SOUTHFIELD",
                "https://attack.mitre.org/groups/G0092/": "TA505",
                "https://attack.mitre.org/groups/G0131/": "Tonto Team",
                "https://attack.mitre.org/groups/G0081/": "Tropic Trooper",
                "https://attack.mitre.org/groups/G0128/": "ZIRCONIUM",
                "https://attack.mitre.org/groups/G0134/": "Transparent Tribe",
                "https://attack.mitre.org/groups/G0135/": "BackdoorDiplomacy",
                "https://attack.mitre.org/groups/G0127/": "Aoqin Dragon",
                "https://attack.mitre.org/groups/G0130/": "Ajax Security Team",
            },
        },
        "software": {
            "pages": {
                "https://attack.mitre.org/software/S0154/": "Cobalt Strike",
                "https://attack.mitre.org/software/S0005/": "Mimikatz",
                "https://attack.mitre.org/software/S0029/": "PsExec",
                "https://attack.mitre.org/software/S0039/": "Net",
                "https://attack.mitre.org/software/S0106/": "cmd",
                "https://attack.mitre.org/software/S0357/": "Impacket",
                "https://attack.mitre.org/software/S0552/": "AdFind",
                "https://attack.mitre.org/software/S0075/": "Reg",
                "https://attack.mitre.org/software/S0194/": "PowerSploit",
                "https://attack.mitre.org/software/S0521/": "BloodHound",
                "https://attack.mitre.org/software/S0160/": "certutil",
                "https://attack.mitre.org/software/S0349/": "LaZagne",
                "https://attack.mitre.org/software/S0111/": "Cobalt",
                "https://attack.mitre.org/software/S0183/": "Empire",
                "https://attack.mitre.org/software/S0105/": "dsquery",
                "https://attack.mitre.org/software/S0100/": "ipconfig",
                "https://attack.mitre.org/software/S0057/": "Tasklist",
                "https://attack.mitre.org/software/S0168/": "Gazer",
                "https://attack.mitre.org/software/S0386/": "Ursnif",
                "https://attack.mitre.org/software/S0266/": "TrickBot",
                "https://attack.mitre.org/software/S0367/": "Emotet",
                "https://attack.mitre.org/software/S0598/": "P.A.S. Webshell",
                "https://attack.mitre.org/software/S0650/": "QakBot",
                "https://attack.mitre.org/software/S0032/": "gh0st RAT",
                "https://attack.mitre.org/software/S0002/": "njRAT",
                "https://attack.mitre.org/software/S0013/": "PlugX",
                "https://attack.mitre.org/software/S0279/": "Proton",
                "https://attack.mitre.org/software/S0145/": "POWERSOURCE",
                "https://attack.mitre.org/software/S0378/": "PoshC2",
                "https://attack.mitre.org/software/S0192/": "Pupy",
                "https://attack.mitre.org/software/S0196/": "PUNCHBUGGY",
                "https://attack.mitre.org/software/S0223/": "POWERSTATS",
                "https://attack.mitre.org/software/S0269/": "QUADAGENT",
                "https://attack.mitre.org/software/S0458/": "Ramsay",
                "https://attack.mitre.org/software/S0481/": "Ragnar Locker",
                "https://attack.mitre.org/software/S0496/": "REvil",
                "https://attack.mitre.org/software/S0446/": "Ryuk",
                "https://attack.mitre.org/software/S0370/": "SamSam",
                "https://attack.mitre.org/software/S0053/": "SeaDuke",
                "https://attack.mitre.org/software/S0382/": "ServHelper",
                "https://attack.mitre.org/software/S0589/": "Sibot",
                "https://attack.mitre.org/software/S0226/": "Smoke Loader",
                "https://attack.mitre.org/software/S0273/": "Socksbot",
                "https://attack.mitre.org/software/S0615/": "SombRAT",
                "https://attack.mitre.org/software/S0380/": "StoneDrill",
                "https://attack.mitre.org/software/S0559/": "SUNBURST",
                "https://attack.mitre.org/software/S0562/": "TEARDROP",
                "https://attack.mitre.org/software/S0476/": "Valak",
                "https://attack.mitre.org/software/S0515/": "WellMail",
                "https://attack.mitre.org/software/S0161/": "XAgent",
                "https://attack.mitre.org/software/S0658/": "XCSSET",
                "https://attack.mitre.org/software/S0412/": "ZxShell",
            },
        },
        "data-sources": {
            "pages": {
                "https://attack.mitre.org/datasources/": "Data Sources Overview",
                "https://attack.mitre.org/datasources/DS0015/": "Application Log",
                "https://attack.mitre.org/datasources/DS0017/": "Command",
                "https://attack.mitre.org/datasources/DS0022/": "File",
                "https://attack.mitre.org/datasources/DS0009/": "Process",
                "https://attack.mitre.org/datasources/DS0029/": "Network Traffic",
                "https://attack.mitre.org/datasources/DS0024/": "Windows Registry",
                "https://attack.mitre.org/datasources/DS0002/": "User Account",
                "https://attack.mitre.org/datasources/DS0019/": "Service",
                "https://attack.mitre.org/datasources/DS0026/": "Active Directory",
                "https://attack.mitre.org/datasources/DS0025/": "Cloud Service",
                "https://attack.mitre.org/datasources/DS0030/": "Instance",
                "https://attack.mitre.org/datasources/DS0014/": "Pod",
                "https://attack.mitre.org/datasources/DS0016/": "Drive",
                "https://attack.mitre.org/datasources/DS0006/": "Web Credential",
                "https://attack.mitre.org/datasources/DS0028/": "Logon Session",
                "https://attack.mitre.org/datasources/DS0020/": "Snapshot",
                "https://attack.mitre.org/datasources/DS0034/": "Volume",
                "https://attack.mitre.org/datasources/DS0010/": "Cloud Storage",
                "https://attack.mitre.org/datasources/DS0018/": "Firewall",
                "https://attack.mitre.org/datasources/DS0033/": "Network Share",
                "https://attack.mitre.org/datasources/DS0013/": "Sensor Health",
                "https://attack.mitre.org/datasources/DS0031/": "Cluster",
                "https://attack.mitre.org/datasources/DS0032/": "Container",
                "https://attack.mitre.org/datasources/DS0035/": "Internet Scan",
                "https://attack.mitre.org/datasources/DS0036/": "Group",
                "https://attack.mitre.org/datasources/DS0037/": "Certificate",
                "https://attack.mitre.org/datasources/DS0038/": "Domain Name",
                "https://attack.mitre.org/datasources/DS0001/": "Firmware",
                "https://attack.mitre.org/datasources/DS0003/": "Scheduled Job",
            },
        },
        "campaigns": {
            "pages": {
                "https://attack.mitre.org/campaigns/": "Campaigns Overview",
                "https://attack.mitre.org/campaigns/C0028/": "2015 Ukraine Electric Power Attack",
                "https://attack.mitre.org/campaigns/C0034/": "2016 Ukraine Electric Power Attack",
                "https://attack.mitre.org/campaigns/C0001/": "Frankenstein",
                "https://attack.mitre.org/campaigns/C0004/": "CostaRicto",
                "https://attack.mitre.org/campaigns/C0006/": "Operation Honeybee",
                "https://attack.mitre.org/campaigns/C0010/": "C0010",
                "https://attack.mitre.org/campaigns/C0011/": "C0011",
                "https://attack.mitre.org/campaigns/C0012/": "Operation Elephant Beetle",
                "https://attack.mitre.org/campaigns/C0014/": "Operation Wocao",
                "https://attack.mitre.org/campaigns/C0015/": "C0015",
                "https://attack.mitre.org/campaigns/C0017/": "C0017",
                "https://attack.mitre.org/campaigns/C0018/": "C0018",
                "https://attack.mitre.org/campaigns/C0021/": "C0021",
                "https://attack.mitre.org/campaigns/C0022/": "C0022",
                "https://attack.mitre.org/campaigns/C0024/": "SolarWinds",
                "https://attack.mitre.org/campaigns/C0026/": "C0026",
                "https://attack.mitre.org/campaigns/C0027/": "C0027",
                "https://attack.mitre.org/campaigns/C0029/": "Cutting Edge",
                "https://attack.mitre.org/campaigns/C0032/": "C0032",
                "https://attack.mitre.org/campaigns/C0036/": "C0036",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"mitre-attack-{source_key}" if source_key else "mitre-attack"
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
            for suffix in [' | MITRE ATT&CK', ' - ATT&CK']:
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
                        "category": f"mitre-attack-{source_key}",
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
            self.log.info(f"=== Scraping mitre-attack/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    MitreAttackScraper(base, source_key).run()
