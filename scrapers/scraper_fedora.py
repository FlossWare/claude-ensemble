#!/usr/bin/env python3
"""Fedora documentation scraper.

Covers:
  - Installation: Fedora install guides, media creation, partitioning
  - Administration: system admin, DNF, Flatpak, Toolbox, systemd, firewalld
  - Release notes: Fedora 39/40/41 release highlights
  - Packaging: RPM packaging guidelines, spec files, mock builds
  - CoreOS: Fedora CoreOS provisioning, Ignition, updates
  - IoT: Fedora IoT edition, device management
  - Silverblue: immutable desktop, rpm-ostree, layering
  - Quick docs: community quick-start guides and howtos
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class FedoraScraper(BaseScraper):
    """Scrape Fedora official documentation."""

    SOURCES = {
        "installation": {
            "pages": {
                "https://docs.fedoraproject.org/en-US/fedora/latest/install-guide/": "Fedora Installation Guide",
                "https://docs.fedoraproject.org/en-US/fedora/latest/install-guide/install/Booting_the_Installation/": "Booting the Installation",
                "https://docs.fedoraproject.org/en-US/fedora/latest/install-guide/install/Installing_Using_Anaconda/": "Installing Using Anaconda",
                "https://docs.fedoraproject.org/en-US/fedora/latest/install-guide/install/Troubleshooting/": "Installation Troubleshooting",
                "https://docs.fedoraproject.org/en-US/fedora/latest/install-guide/advanced/Boot_Options/": "Boot Options",
                "https://docs.fedoraproject.org/en-US/fedora/latest/install-guide/advanced/Kickstart_Installations/": "Kickstart Installations",
                "https://docs.fedoraproject.org/en-US/fedora/latest/install-guide/appendixes/Disk_Partitions/": "Disk Partitions",
                "https://docs.fedoraproject.org/en-US/fedora/latest/preparing-boot-media/": "Preparing Boot Media",
                "https://fedoraproject.org/wiki/How_to_create_and_use_Live_USB": "How to Create and Use Live USB",
                "https://fedoraproject.org/wiki/Installation_Guide": "Installation Guide (Wiki)",
            },
        },
        "administration": {
            "pages": {
                "https://docs.fedoraproject.org/en-US/fedora/latest/system-administrators-guide/": "System Administrators Guide",
                "https://docs.fedoraproject.org/en-US/fedora/latest/system-administrators-guide/basic-system-configuration/": "Basic System Configuration",
                "https://docs.fedoraproject.org/en-US/fedora/latest/system-administrators-guide/package-management/DNF/": "DNF Package Manager",
                "https://docs.fedoraproject.org/en-US/fedora/latest/system-administrators-guide/package-management/rpm/": "RPM Package Manager",
                "https://docs.fedoraproject.org/en-US/fedora/latest/system-administrators-guide/servers/Web_Servers/": "Web Servers",
                "https://docs.fedoraproject.org/en-US/fedora/latest/system-administrators-guide/servers/File_and_Print_Servers/": "File and Print Servers",
                "https://docs.fedoraproject.org/en-US/fedora/latest/system-administrators-guide/infrastructure-services/": "Infrastructure Services",
                "https://docs.fedoraproject.org/en-US/fedora/latest/system-administrators-guide/kernel-module-driver-configuration/Working_with_the_GRUB_2_Boot_Loader/": "Working with GRUB 2 Boot Loader",
                "https://docs.fedoraproject.org/en-US/fedora/latest/system-administrators-guide/monitoring-and-automation/System_Monitoring_Tools/": "System Monitoring Tools",
                "https://docs.fedoraproject.org/en-US/fedora/latest/system-administrators-guide/monitoring-and-automation/Automating_System_Tasks/": "Automating System Tasks",
                "https://docs.fedoraproject.org/en-US/quick-docs/dnf/": "DNF Quick Reference",
                "https://docs.fedoraproject.org/en-US/quick-docs/dnf-vs-yum/": "DNF vs Yum",
                "https://docs.fedoraproject.org/en-US/quick-docs/firewalld/": "Configuring Firewalld",
                "https://docs.fedoraproject.org/en-US/quick-docs/getting-started-with-systemd/": "Getting Started with systemd",
                "https://docs.fedoraproject.org/en-US/quick-docs/installing-and-managing-flatpak/": "Installing and Managing Flatpak",
                "https://docs.fedoraproject.org/en-US/quick-docs/toolbox/": "Using Toolbox",
                "https://fedoraproject.org/wiki/SELinux": "SELinux on Fedora",
                "https://fedoraproject.org/wiki/Networking/CLI": "Networking CLI (NetworkManager)",
            },
        },
        "release-notes": {
            "pages": {
                "https://docs.fedoraproject.org/en-US/fedora/latest/release-notes/": "Fedora Latest Release Notes",
                "https://docs.fedoraproject.org/en-US/fedora/latest/release-notes/welcome/": "Welcome to Fedora",
                "https://docs.fedoraproject.org/en-US/fedora/latest/release-notes/sysadmin/": "Changes for System Administrators",
                "https://docs.fedoraproject.org/en-US/fedora/latest/release-notes/developers/": "Changes for Developers",
                "https://fedoraproject.org/wiki/Releases/41/ChangeSet": "Fedora 41 Change Set",
                "https://fedoraproject.org/wiki/Releases/40/ChangeSet": "Fedora 40 Change Set",
                "https://fedoraproject.org/wiki/Releases/39/ChangeSet": "Fedora 39 Change Set",
            },
        },
        "packaging": {
            "pages": {
                "https://docs.fedoraproject.org/en-US/packaging-guidelines/": "Fedora Packaging Guidelines",
                "https://docs.fedoraproject.org/en-US/packaging-guidelines/RPMMacros/": "RPM Macros",
                "https://docs.fedoraproject.org/en-US/packaging-guidelines/Scriptlets/": "Scriptlets",
                "https://docs.fedoraproject.org/en-US/packaging-guidelines/LicensingGuidelines/": "Licensing Guidelines",
                "https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/": "Python Packaging Guidelines",
                "https://docs.fedoraproject.org/en-US/packaging-guidelines/Golang/": "Go Packaging Guidelines",
                "https://docs.fedoraproject.org/en-US/packaging-guidelines/Rust/": "Rust Packaging Guidelines",
                "https://docs.fedoraproject.org/en-US/packaging-guidelines/CMake/": "CMake Packaging Guidelines",
                "https://fedoraproject.org/wiki/How_to_create_an_RPM_package": "How to Create an RPM Package",
                "https://fedoraproject.org/wiki/Mock": "Mock Build System",
                "https://fedoraproject.org/wiki/Koji": "Koji Build System",
                "https://fedoraproject.org/wiki/Using_the_Koji_build_system": "Using the Koji Build System",
            },
        },
        "coreos": {
            "pages": {
                "https://docs.fedoraproject.org/en-US/fedora-coreos/": "Fedora CoreOS Documentation",
                "https://docs.fedoraproject.org/en-US/fedora-coreos/getting-started/": "Getting Started with Fedora CoreOS",
                "https://docs.fedoraproject.org/en-US/fedora-coreos/producing-ign/": "Producing an Ignition Config",
                "https://docs.fedoraproject.org/en-US/fedora-coreos/bare-metal/": "Installing on Bare Metal",
                "https://docs.fedoraproject.org/en-US/fedora-coreos/provisioning-aws/": "Provisioning on AWS",
                "https://docs.fedoraproject.org/en-US/fedora-coreos/provisioning-gcp/": "Provisioning on GCP",
                "https://docs.fedoraproject.org/en-US/fedora-coreos/provisioning-azure/": "Provisioning on Azure",
                "https://docs.fedoraproject.org/en-US/fedora-coreos/auto-updates/": "Auto-Updates",
                "https://docs.fedoraproject.org/en-US/fedora-coreos/sysconfig-network-configuration/": "Network Configuration",
                "https://docs.fedoraproject.org/en-US/fedora-coreos/running-containers/": "Running Containers",
            },
        },
        "iot": {
            "pages": {
                "https://docs.fedoraproject.org/en-US/iot/": "Fedora IoT Documentation",
                "https://docs.fedoraproject.org/en-US/iot/getting-started/": "Getting Started with Fedora IoT",
                "https://docs.fedoraproject.org/en-US/iot/physical-device-setup/": "Physical Device Setup",
                "https://docs.fedoraproject.org/en-US/iot/virtual-machine-setup/": "Virtual Machine Setup",
                "https://docs.fedoraproject.org/en-US/iot/applying-updates-UG/": "Applying Updates",
                "https://docs.fedoraproject.org/en-US/iot/add-layered/": "Adding Layered Packages",
                "https://docs.fedoraproject.org/en-US/iot/rebasing/": "Rebasing to a New Release",
                "https://docs.fedoraproject.org/en-US/iot/ignition/": "Ignition on Fedora IoT",
            },
        },
        "silverblue": {
            "pages": {
                "https://docs.fedoraproject.org/en-US/fedora-silverblue/": "Fedora Silverblue Documentation",
                "https://docs.fedoraproject.org/en-US/fedora-silverblue/installation/": "Silverblue Installation",
                "https://docs.fedoraproject.org/en-US/fedora-silverblue/getting-started/": "Getting Started with Silverblue",
                "https://docs.fedoraproject.org/en-US/fedora-silverblue/toolbox/": "Toolbox on Silverblue",
                "https://docs.fedoraproject.org/en-US/fedora-silverblue/updates-upgrades-rollbacks/": "Updates, Upgrades and Rollbacks",
                "https://docs.fedoraproject.org/en-US/fedora-silverblue/tips-and-tricks/": "Silverblue Tips and Tricks",
                "https://docs.fedoraproject.org/en-US/fedora-silverblue/troubleshooting/": "Silverblue Troubleshooting",
                "https://fedoraproject.org/wiki/Workstation/OstreeBasedDesktop": "OSTree-Based Desktop",
            },
        },
        "quick-docs": {
            "pages": {
                "https://docs.fedoraproject.org/en-US/quick-docs/": "Fedora Quick Docs Index",
                "https://docs.fedoraproject.org/en-US/quick-docs/creating-and-using-a-live-installation-image/": "Creating a Live Installation Image",
                "https://docs.fedoraproject.org/en-US/quick-docs/adding-or-removing-software-repositories-in-fedora/": "Adding or Removing Software Repositories",
                "https://docs.fedoraproject.org/en-US/quick-docs/configuring-x-window-system-using-the-xorg-conf-file/": "Configuring X Window System",
                "https://docs.fedoraproject.org/en-US/quick-docs/setup-vscodium/": "Setting Up VSCodium",
                "https://docs.fedoraproject.org/en-US/quick-docs/upgrading-fedora-new-release/": "Upgrading Fedora to a New Release",
                "https://docs.fedoraproject.org/en-US/quick-docs/enabling-the-rpmfusion-repositories/": "Enabling RPM Fusion Repositories",
                "https://docs.fedoraproject.org/en-US/quick-docs/assembly_installing-plugins-for-playing-movies-and-music/": "Installing Multimedia Plugins",
                "https://docs.fedoraproject.org/en-US/quick-docs/set-hostname/": "Setting the Hostname",
                "https://docs.fedoraproject.org/en-US/quick-docs/managing-software-packages-using-dnf/": "Managing Packages Using DNF",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"fedora-{source_key}" if source_key else "fedora"
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
            for suffix in [' :: Fedora Docs', ' - Fedora Project Wiki',
                           ' :: Fedora Documentation', ' - Fedora Documentation',
                           ' - Fedora Project']:
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
                        "category": f"fedora-{source_key}",
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
            self.log.info(f"=== Scraping fedora/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    FedoraScraper(base, source_key).run()
