#!/usr/bin/env python3
"""Red Hat documentation scraper.

Covers:
  - RHEL 9: system admin, networking, security, storage, kernel, SELinux, etc.
  - OpenShift: architecture, installing, networking, storage, operators, etc.
  - Ansible Automation Platform: getting started, playbooks, collections
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class RedHatScraper(BaseScraper):
    """Scrape Red Hat official documentation."""

    SOURCES = {
        "rhel9-admin": {
            "pages": {
                # System Administration
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_basic_system_settings/index": "Configuring Basic System Settings",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_basic_system_settings/assembly_configuring-system-settings-with-systemctl_configuring-basic-system-settings": "Configuring System Settings with systemctl",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_basic_system_settings/managing-users-and-groups_configuring-basic-system-settings": "Managing Users and Groups",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_basic_system_settings/configuring-time-settings_configuring-basic-system-settings": "Configuring Time Settings",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_software_with_the_dnf_tool/index": "Managing Software with the DNF Tool",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_software_with_the_dnf_tool/assembly_searching-for-rhel-9-content_managing-software-with-the-dnf-tool": "Searching for RHEL 9 Content",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_software_with_the_dnf_tool/assembly_installing-rhel-9-content_managing-software-with-the-dnf-tool": "Installing RHEL 9 Content",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/using_systemd_unit_files_to_customize_and_optimize_your_system/index": "Using systemd Unit Files",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/using_systemd_unit_files_to_customize_and_optimize_your_system/assembly_working-with-systemd-unit-files_using-systemd-unit-files-to-customize-and-optimize-your-system": "Working with systemd Unit Files",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_monitoring_and_updating_the_kernel/index": "Managing the Kernel",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_monitoring_and_updating_the_kernel/assembly_updating-kernel-with-yum_managing-monitoring-and-updating-the-kernel": "Updating the Kernel",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/index": "Monitoring and Managing System Status and Performance",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/setting-up-pcp_monitoring-and-managing-system-status-and-performance": "Setting up PCP",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/monitoring-performance-with-performance-co-pilot_monitoring-and-managing-system-status-and-performance": "Monitoring Performance with PCP",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_virtualization/index": "Configuring and Managing Virtualization",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_virtualization/getting-started-with-virtualization-in-rhel-9_configuring-and-managing-virtualization": "Getting Started with Virtualization",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_virtualization/managing-virtual-machines-with-the-web-console_configuring-and-managing-virtualization": "Managing Virtual Machines with the Web Console",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_idm_users_groups_hosts_and_access_control_rules/index": "Managing IdM Users, Groups, Hosts, and Access Control Rules",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_idm_users_groups_hosts_and_access_control_rules/managing-user-accounts-using-the-command-line_managing-idm-users-groups-hosts-and-access-control-rules": "Managing User Accounts Using the Command Line",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_logical_volumes/index": "Configuring and Managing Logical Volumes",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_logical_volumes/overview-of-logical-volume-management_configuring-and-managing-logical-volumes": "Overview of Logical Volume Management",
            },
        },
        "rhel9-networking": {
            "pages": {
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/index": "Configuring and Managing Networking",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/getting-started-with-networkmanager_configuring-and-managing-networking": "Getting Started with NetworkManager",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/configuring-an-ethernet-connection_configuring-and-managing-networking": "Configuring an Ethernet Connection",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/managing-wifi-connections_configuring-and-managing-networking": "Managing WiFi Connections",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/configuring-vlan-tagging_configuring-and-managing-networking": "Configuring VLAN Tagging",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/configuring-a-network-bridge_configuring-and-managing-networking": "Configuring a Network Bridge",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/configuring-a-network-bond_configuring-and-managing-networking": "Configuring a Network Bond",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/configuring-a-vpn-connection_configuring-and-managing-networking": "Configuring a VPN Connection",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/configuring-ip-tunnels_configuring-and-managing-networking": "Configuring IP Tunnels",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/setting-your-dns-server-order_configuring-and-managing-networking": "Setting Your DNS Server Order",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/configuring-policy-based-routing-to-define-alternative-routes_configuring-and-managing-networking": "Configuring Policy-Based Routing",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/monitoring-and-tuning-the-rx-ring-buffer_configuring-and-managing-networking": "Monitoring and Tuning the RX Ring Buffer",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/configuring-network-teaming_configuring-and-managing-networking": "Configuring Network Teaming",
            },
        },
        "rhel9-security": {
            "pages": {
                # Security Hardening
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/security_hardening/index": "Security Hardening",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/security_hardening/assembly_securing-rhel-during-installation-security-hardening": "Securing RHEL During Installation",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/security_hardening/using-selinux_security-hardening": "Using SELinux",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/security_hardening/assembly_using-the-system-wide-cryptographic-policies_security-hardening": "Using System-Wide Cryptographic Policies",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/security_hardening/assembly_configuring-firewalld_security-hardening": "Configuring firewalld",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/security_hardening/assembly_configuring-automated-unlocking-of-encrypted-volumes-using-policy-based-decryption_security-hardening": "Configuring Automated Unlocking with PBD",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/security_hardening/assembly_auditing-the-system_security-hardening": "Auditing the System",
                # SELinux
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/using_selinux/index": "Using SELinux",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/using_selinux/getting-started-with-selinux_using-selinux": "Getting Started with SELinux",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/using_selinux/changing-selinux-states-and-modes_using-selinux": "Changing SELinux States and Modes",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/using_selinux/managing-confined-and-unconfined-users_using-selinux": "Managing Confined and Unconfined Users",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/using_selinux/configuring-selinux-for-applications-and-services-with-non-standard-configurations_using-selinux": "Configuring SELinux for Applications",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/using_selinux/troubleshooting-problems-related-to-selinux_using-selinux": "Troubleshooting SELinux",
                # Firewall
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_firewalls_and_packet_filters/index": "Configuring Firewalls and Packet Filters",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_firewalls_and_packet_filters/using-and-configuring-firewalld_firewall-packet-filters": "Using and Configuring firewalld",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_firewalls_and_packet_filters/getting-started-with-nftables_firewall-packet-filters": "Getting Started with nftables",
            },
        },
        "rhel9-storage": {
            "pages": {
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_file_systems/index": "Managing File Systems",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_file_systems/overview-of-available-file-systems_managing-file-systems": "Overview of Available File Systems",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_file_systems/mounting-file-systems_managing-file-systems": "Mounting File Systems",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_file_systems/assembly_getting-started-with-an-ext4-file-system_managing-file-systems": "Getting Started with ext4",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_file_systems/getting-started-with-xfs_managing-file-systems": "Getting Started with XFS",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_storage_devices/index": "Managing Storage Devices",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_storage_devices/overview-of-persistent-naming-attributes_managing-storage-devices": "Overview of Persistent Naming Attributes",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_storage_devices/getting-started-with-partitions_managing-storage-devices": "Getting Started with Partitions",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_storage_devices/configuring-an-iscsi-target_managing-storage-devices": "Configuring an iSCSI Target",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_storage_devices/managing-nvme-devices_managing-storage-devices": "Managing NVMe Devices",
                "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/deduplicating_and_compressing_logical_volumes_on_rhel/index": "Deduplicating and Compressing Logical Volumes (VDO)",
            },
        },
        "openshift": {
            "pages": {
                # Architecture
                "https://docs.openshift.com/container-platform/latest/architecture/architecture.html": "OpenShift Architecture",
                "https://docs.openshift.com/container-platform/latest/architecture/architecture-installation.html": "OpenShift Installation and Update",
                "https://docs.openshift.com/container-platform/latest/architecture/control-plane.html": "Control Plane Architecture",
                "https://docs.openshift.com/container-platform/latest/architecture/understanding-development.html": "Understanding OpenShift Development",
                # Installing
                "https://docs.openshift.com/container-platform/latest/installing/index.html": "OpenShift Installation Overview",
                "https://docs.openshift.com/container-platform/latest/installing/installing_aws/ipi/installing-aws-default.html": "Installing on AWS (IPI)",
                "https://docs.openshift.com/container-platform/latest/installing/installing_bare_metal/installing-bare-metal.html": "Installing on Bare Metal",
                "https://docs.openshift.com/container-platform/latest/installing/installing_bare_metal_ipi/ipi-install-overview.html": "Installing on Bare Metal (IPI)",
                "https://docs.openshift.com/container-platform/latest/installing/installing_vsphere/ipi/installing-vsphere-installer-provisioned.html": "Installing on vSphere (IPI)",
                "https://docs.openshift.com/container-platform/latest/installing/disconnected_install/index.html": "Disconnected Installation Mirroring",
                # Networking
                "https://docs.openshift.com/container-platform/latest/networking/understanding-networking.html": "Understanding Networking",
                "https://docs.openshift.com/container-platform/latest/networking/cluster-network-operator.html": "Cluster Network Operator",
                "https://docs.openshift.com/container-platform/latest/networking/ovn_kubernetes_network_provider/about-ovn-kubernetes.html": "About OVN-Kubernetes",
                "https://docs.openshift.com/container-platform/latest/networking/routes/route-configuration.html": "Route Configuration",
                "https://docs.openshift.com/container-platform/latest/networking/ingress-operator.html": "Ingress Operator",
                "https://docs.openshift.com/container-platform/latest/networking/network_policy/about-network-policy.html": "About Network Policy",
                # Storage
                "https://docs.openshift.com/container-platform/latest/storage/understanding-persistent-storage.html": "Understanding Persistent Storage",
                "https://docs.openshift.com/container-platform/latest/storage/persistent_storage/persistent-storage-ocs.html": "Persistent Storage Using OpenShift Data Foundation",
                "https://docs.openshift.com/container-platform/latest/storage/persistent_storage/persistent-storage-nfs.html": "Persistent Storage Using NFS",
                "https://docs.openshift.com/container-platform/latest/storage/persistent_storage/persistent-storage-local.html": "Persistent Storage Using Local Volumes",
                "https://docs.openshift.com/container-platform/latest/storage/container_storage_interface/persistent-storage-csi.html": "Persistent Storage Using CSI",
                # Security
                "https://docs.openshift.com/container-platform/latest/authentication/understanding-authentication.html": "Understanding Authentication",
                "https://docs.openshift.com/container-platform/latest/authentication/using-rbac.html": "Using RBAC to Define and Apply Permissions",
                "https://docs.openshift.com/container-platform/latest/authentication/understanding-and-managing-pod-security-admission.html": "Pod Security Admission",
                "https://docs.openshift.com/container-platform/latest/security/certificates/replacing-default-ingress-certificate.html": "Replacing the Default Ingress Certificate",
                "https://docs.openshift.com/container-platform/latest/security/audit-log-view.html": "Viewing Audit Logs",
                # Operators
                "https://docs.openshift.com/container-platform/latest/operators/understanding/olm-what-operators-are.html": "What Operators Are",
                "https://docs.openshift.com/container-platform/latest/operators/understanding/olm/olm-understanding-olm.html": "Understanding Operator Lifecycle Manager",
                "https://docs.openshift.com/container-platform/latest/operators/admin/olm-adding-operators-to-cluster.html": "Adding Operators to a Cluster",
                "https://docs.openshift.com/container-platform/latest/operators/operator_sdk/osdk-about.html": "About the Operator SDK",
                # Builds & CI/CD
                "https://docs.openshift.com/container-platform/latest/cicd/builds/understanding-image-builds.html": "Understanding Image Builds",
                "https://docs.openshift.com/container-platform/latest/cicd/builds/creating-build-inputs.html": "Creating Build Inputs",
                "https://docs.openshift.com/container-platform/latest/cicd/builds/build-strategies.html": "Build Strategies",
                "https://docs.openshift.com/container-platform/latest/cicd/pipelines/understanding-openshift-pipelines.html": "Understanding OpenShift Pipelines",
                "https://docs.openshift.com/container-platform/latest/cicd/pipelines/creating-applications-with-cicd-pipelines.html": "Creating Applications with CI/CD Pipelines",
                "https://docs.openshift.com/container-platform/latest/cicd/gitops/understanding-openshift-gitops.html": "Understanding OpenShift GitOps",
                # Monitoring & Logging
                "https://docs.openshift.com/container-platform/latest/observability/monitoring/monitoring-overview.html": "Monitoring Overview",
                "https://docs.openshift.com/container-platform/latest/observability/monitoring/configuring-the-monitoring-stack.html": "Configuring the Monitoring Stack",
                "https://docs.openshift.com/container-platform/latest/observability/logging/cluster-logging.html": "About Logging",
                "https://docs.openshift.com/container-platform/latest/observability/logging/cluster-logging-deploying.html": "Installing Logging",
                # Scaling
                "https://docs.openshift.com/container-platform/latest/nodes/pods/nodes-pods-autoscaling.html": "Automatically Scaling Pods",
                "https://docs.openshift.com/container-platform/latest/machine_management/index.html": "Machine Management Overview",
                "https://docs.openshift.com/container-platform/latest/machine_management/applying-autoscaling.html": "Applying Autoscaling to an OpenShift Cluster",
            },
        },
        "ansible": {
            "pages": {
                # Getting Started
                "https://docs.ansible.com/ansible/latest/getting_started/index.html": "Getting Started with Ansible",
                "https://docs.ansible.com/ansible/latest/getting_started/get_started_inventory.html": "Building an Inventory",
                "https://docs.ansible.com/ansible/latest/getting_started/get_started_playbook.html": "Creating a Playbook",
                # User Guide / Playbooks
                "https://docs.ansible.com/ansible/latest/playbook_guide/index.html": "Using Ansible Playbooks",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_intro.html": "Intro to Playbooks",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html": "Using Variables",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_conditionals.html": "Conditionals",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_loops.html": "Loops",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_handlers.html": "Handlers",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_blocks.html": "Blocks",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html": "Roles",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_templating.html": "Templating (Jinja2)",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_filters.html": "Using Filters to Manipulate Data",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_tests.html": "Tests",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_lookups.html": "Lookups",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_delegation.html": "Controlling Task Delegation",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_error_handling.html": "Error Handling in Playbooks",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_strategies.html": "Controlling Playbook Execution Strategies",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_vault.html": "Encrypting Content with Ansible Vault",
                # Inventory
                "https://docs.ansible.com/ansible/latest/inventory_guide/index.html": "Building Ansible Inventories",
                "https://docs.ansible.com/ansible/latest/inventory_guide/intro_inventory.html": "How to Build Your Inventory",
                "https://docs.ansible.com/ansible/latest/inventory_guide/intro_dynamic_inventory.html": "Working with Dynamic Inventory",
                "https://docs.ansible.com/ansible/latest/inventory_guide/intro_patterns.html": "Patterns: Targeting Hosts and Groups",
                "https://docs.ansible.com/ansible/latest/inventory_guide/connection_details.html": "Connection Methods and Details",
                # Collections
                "https://docs.ansible.com/ansible/latest/collections_guide/index.html": "Using Ansible Collections",
                "https://docs.ansible.com/ansible/latest/collections_guide/collections_installing.html": "Installing Collections",
                "https://docs.ansible.com/ansible/latest/collections_guide/collections_using_playbooks.html": "Using Collections in Playbooks",
                # Command line tools
                "https://docs.ansible.com/ansible/latest/command_guide/index.html": "Using Ansible Command Line Tools",
                "https://docs.ansible.com/ansible/latest/command_guide/intro_adhoc.html": "Introduction to ad hoc Commands",
                # Modules and plugins
                "https://docs.ansible.com/ansible/latest/module_plugin_guide/index.html": "Using Ansible Modules and Plugins",
                # Tips and Tricks
                "https://docs.ansible.com/ansible/latest/tips_tricks/index.html": "Ansible Tips and Tricks",
                "https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html": "General Tips",
                # AAP (Ansible Automation Platform)
                "https://access.redhat.com/documentation/en-us/red_hat_ansible_automation_platform/2.4/html/getting_started_with_ansible_automation_platform/index": "Getting Started with AAP",
                "https://access.redhat.com/documentation/en-us/red_hat_ansible_automation_platform/2.4/html/automation_controller_user_guide/index": "Automation Controller User Guide",
                "https://access.redhat.com/documentation/en-us/red_hat_ansible_automation_platform/2.4/html/red_hat_ansible_automation_platform_planning_guide/index": "AAP Planning Guide",
                "https://access.redhat.com/documentation/en-us/red_hat_ansible_automation_platform/2.4/html/red_hat_ansible_automation_platform_installation_guide/index": "AAP Installation Guide",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"redhat-{source_key}" if source_key else "redhat"
        super().__init__(name, base_dir, interval_seconds=7200)
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
            for suffix in [
                ' | Red Hat',
                ' Red Hat Enterprise Linux',
                ' Red Hat Customer Portal',
                ' | Red Hat Customer Portal',
                ' - Red Hat Customer Portal',
                ' | Red Hat Documentation',
            ]:
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
                        "category": "redhat-docs",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(2.0)  # Conservative rate limit for enterprise site

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
            self.log.info(f"=== Scraping redhat/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    RedHatScraper(base, source_key).run()
