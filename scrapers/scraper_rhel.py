#!/usr/bin/env python3
"""Red Hat Enterprise Linux 9 documentation scraper.

Covers:
  - Installation and initial setup
  - System administration and configuration
  - Security hardening and compliance
  - Networking configuration and management
  - Storage devices and file systems
  - Containers with Podman and Buildah
  - SELinux policy and management
  - systemd services and targets
  - Kernel tuning and modules
  - Performance monitoring and optimization
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class RHELScraper(BaseScraper):
    """Scrape Red Hat Enterprise Linux 9 documentation across all sections."""

    SOURCES = {
        "installation": {
            "pages": {
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/performing_a_standard_rhel_9_installation/index": "Performing a Standard RHEL 9 Installation",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/performing_an_advanced_rhel_9_installation/index": "Performing an Advanced RHEL 9 Installation",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/boot_options_for_rhel_installer/index": "Boot Options for RHEL Installer",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/composing_a_customized_rhel_system_image/index": "Composing a Customized RHEL System Image",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/upgrading_from_rhel_8_to_rhel_9/index": "Upgrading from RHEL 8 to RHEL 9",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/composing_installing_and_managing_rhel_for_edge_images/index": "RHEL for Edge Images",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/interactively_installing_rhel_from_installation_media/index": "Interactive Installation from Media",
            },
        },
        "administration": {
            "pages": {
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_basic_system_settings/index": "Configuring Basic System Settings",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_software_with_the_dnf_tool/index": "Managing Software with DNF",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_user_and_group_accounts/index": "Managing User and Group Accounts",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/automating_system_administration_by_using_rhel_system_roles/index": "RHEL System Roles",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_and_using_a_rhel_web_console/index": "Web Console (Cockpit)",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_the_desktop_environment/index": "Using the Desktop Environment",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_and_monitoring_security_updates/index": "Managing Security Updates",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_monitoring_and_updating_the_kernel/index": "Managing the Kernel",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_the_system_locale_and_keyboard_layout/index": "System Locale and Keyboard Layout",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_time_synchronization/index": "Configuring Time Synchronization",
            },
        },
        "security": {
            "pages": {
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/security_hardening/index": "Security Hardening",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_certificates_and_associated_keys/index": "Managing Certificates and Keys",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/securing_networks/index": "Securing Networks",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_authentication_and_authorization_in_rhel/index": "Authentication and Authorization",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_identity_management/index": "Identity Management (IdM)",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_smart_card_authentication/index": "Smart Card Authentication",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_and_managing_identity_management/index": "Configuring Identity Management",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/integrating_rhel_systems_directly_with_windows_active_directory/index": "Active Directory Integration",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_rhel_9_with_fips_140_validated_cryptography/index": "FIPS 140 Cryptography",
            },
        },
        "networking": {
            "pages": {
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/index": "Configuring and Managing Networking",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_firewalls_and_packet_filters/index": "Firewalls and Packet Filters",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_networking_infrastructure_services/index": "Networking Infrastructure Services",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_vpn_connections/index": "Configuring VPN Connections",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_infiniband_and_rdma_networks/index": "InfiniBand and RDMA Networks",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/deploying_mail_servers/index": "Deploying Mail Servers",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/deploying_web_servers_and_reverse_proxies/index": "Deploying Web Servers and Reverse Proxies",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/deploying_different_types_of_servers/index": "Deploying Different Types of Servers",
            },
        },
        "storage": {
            "pages": {
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_storage_devices/index": "Managing Storage Devices",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_file_systems/index": "Managing File Systems",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_and_using_network_file_services/index": "Network File Services",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/deduplicating_and_compressing_logical_volumes_on_rhel/index": "Deduplicating and Compressing (VDO)",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_local_storage_with_rhel_system_roles/index": "Local Storage with System Roles",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_and_managing_logical_volumes/index": "Logical Volumes (LVM)",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_raid/index": "Managing RAID",
            },
        },
        "containers": {
            "pages": {
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/building_running_and_managing_containers/index": "Building Running and Managing Containers",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/building_running_and_managing_containers/assembly_starting-with-containers": "Getting Started with Containers",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/building_running_and_managing_containers/assembly_working-with-container-images": "Working with Container Images",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/building_running_and_managing_containers/assembly_working-with-containers": "Working with Containers",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/building_running_and_managing_containers/assembly_porting-containers-to-systemd-using-podman": "Containers with systemd and Podman",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/building_running_and_managing_containers/assembly_signing-container-images": "Signing Container Images",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/building_running_and_managing_containers/proc_building-container-images-with-buildah": "Building Images with Buildah",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/building_running_and_managing_containers/assembly_working-with-pods": "Working with Pods",
            },
        },
        "selinux": {
            "pages": {
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_selinux/index": "Using SELinux",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_selinux/getting-started-with-selinux_using-selinux": "Getting Started with SELinux",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_selinux/changing-selinux-states-and-modes_using-selinux": "Changing SELinux States and Modes",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_selinux/managing-confined-and-unconfined-users_using-selinux": "Managing Confined and Unconfined Users",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_selinux/configuring-selinux-for-applications-and-services-with-non-standard-configurations_using-selinux": "SELinux for Non-Standard Configurations",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_selinux/troubleshooting-problems-related-to-selinux_using-selinux": "Troubleshooting SELinux",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_selinux/writing-a-custom-selinux-policy_using-selinux": "Writing a Custom SELinux Policy",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_selinux/managing-selinux-booleans_using-selinux": "Managing SELinux Booleans",
            },
        },
        "systemd": {
            "pages": {
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_basic_system_settings/managing-system-services-with-systemctl_configuring-basic-system-settings": "Managing Services with systemctl",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_basic_system_settings/working-with-systemd-unit-files_configuring-basic-system-settings": "Working with systemd Unit Files",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_basic_system_settings/managing-systemd-targets_configuring-basic-system-settings": "Managing systemd Targets",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_basic_system_settings/optimizing-systemd-to-shorten-boot-time_configuring-basic-system-settings": "Optimizing Boot Time",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_basic_system_settings/introduction-to-systemd_configuring-basic-system-settings": "Introduction to systemd",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_basic_system_settings/managing-system-journal-with-journalctl_configuring-basic-system-settings": "Managing Journal with journalctl",
            },
        },
        "kernel": {
            "pages": {
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_monitoring_and_updating_the_kernel/index": "Managing and Updating the Kernel",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_monitoring_and_updating_the_kernel/assembly_updating-kernel-with-yum_managing-monitoring-and-updating-the-kernel": "Updating the Kernel",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_monitoring_and_updating_the_kernel/assembly_installing-and-configuring-kdump_managing-monitoring-and-updating-the-kernel": "Installing and Configuring kdump",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_monitoring_and_updating_the_kernel/managing-kernel-modules_managing-monitoring-and-updating-the-kernel": "Managing Kernel Modules",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_monitoring_and_updating_the_kernel/configuring-kernel-command-line-parameters_managing-monitoring-and-updating-the-kernel": "Kernel Command-Line Parameters",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_monitoring_and_updating_the_kernel/assembly_getting-started-with-kernel-logging_managing-monitoring-and-updating-the-kernel": "Kernel Logging",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_monitoring_and_updating_the_kernel/using-the-kernel-abi_managing-monitoring-and-updating-the-kernel": "Using the Kernel ABI",
            },
        },
        "performance": {
            "pages": {
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/index": "Monitoring and Managing Performance",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/setting-up-pcp_monitoring-and-managing-system-status-and-performance": "Setting Up PCP",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/logging-performance-data-with-pmlogger_monitoring-and-managing-system-status-and-performance": "Logging with pmlogger",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/monitoring-performance-with-performance-co-pilot_monitoring-and-managing-system-status-and-performance": "Monitoring with PCP",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/getting-started-with-tuned_monitoring-and-managing-system-status-and-performance": "Getting Started with TuneD",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/customizing-tuned-profiles_monitoring-and-managing-system-status-and-performance": "Customizing TuneD Profiles",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/reviewing-resource-consumption-with-perf_monitoring-and-managing-system-status-and-performance": "Reviewing Resources with perf",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/configuring-an-operating-system-to-optimize-cpu-utilization_monitoring-and-managing-system-status-and-performance": "Optimizing CPU Utilization",
                "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/configuring-an-operating-system-to-optimize-memory-access_monitoring-and-managing-system-status-and-performance": "Optimizing Memory Access",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"rhel-{source_key}" if source_key else "rhel"
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
            for suffix in [' | Red Hat Documentation', ' | Red Hat Product Documentation',
                           ' Red Hat Enterprise Linux 9', ' - Red Hat Customer Portal']:
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
                        "category": f"rhel-{source_key}",
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
            self.log.info(f"=== Scraping rhel/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    RHELScraper(base, source_key).run()
