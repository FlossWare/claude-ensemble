#!/usr/bin/env python3
"""Ansible documentation scraper.

Covers:
  - Getting started: introduction, concepts, installation
  - User guide: inventory, playbooks, roles, variables, templates, etc.
  - Playbook guide: working with playbooks, advanced playbooks
  - Module index: top 50 most-used modules
  - Collections: ansible.builtin, ansible.posix, community.general
  - Galaxy: using roles, creating roles
  - Network: network modules, platform guides
  - Reference: configuration, special variables, return values, playbook keywords
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class AnsibleScraper(BaseScraper):
    """Scrape Ansible official documentation."""

    SOURCES = {
        "getting-started": {
            "pages": {
                # Getting Started
                "https://docs.ansible.com/ansible/latest/getting_started/index.html": "Getting Started with Ansible",
                "https://docs.ansible.com/ansible/latest/getting_started/introduction.html": "Introduction to Ansible",
                "https://docs.ansible.com/ansible/latest/getting_started/get_started_inventory.html": "Building an Inventory",
                "https://docs.ansible.com/ansible/latest/getting_started/get_started_playbook.html": "Creating a Playbook",
                "https://docs.ansible.com/ansible/latest/getting_started/basic_concepts.html": "Ansible Concepts",
                # Installation
                "https://docs.ansible.com/ansible/latest/installation_guide/index.html": "Installation Guide",
                "https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html": "Installing Ansible",
                "https://docs.ansible.com/ansible/latest/installation_guide/installation_distros.html": "Installing Ansible on Specific Operating Systems",
            },
        },
        "user-guide": {
            "pages": {
                # Inventory
                "https://docs.ansible.com/ansible/latest/inventory_guide/index.html": "Building Ansible Inventories",
                "https://docs.ansible.com/ansible/latest/inventory_guide/intro_inventory.html": "How to Build Your Inventory",
                "https://docs.ansible.com/ansible/latest/inventory_guide/intro_dynamic_inventory.html": "Working with Dynamic Inventory",
                "https://docs.ansible.com/ansible/latest/inventory_guide/intro_patterns.html": "Patterns: Targeting Hosts and Groups",
                "https://docs.ansible.com/ansible/latest/inventory_guide/connection_details.html": "Connection Methods and Details",
                # Command Line Tools
                "https://docs.ansible.com/ansible/latest/command_guide/index.html": "Using Ansible Command Line Tools",
                "https://docs.ansible.com/ansible/latest/command_guide/intro_adhoc.html": "Introduction to Ad Hoc Commands",
                "https://docs.ansible.com/ansible/latest/command_guide/cheatsheet.html": "Ansible CLI Cheatsheet",
                # Playbooks
                "https://docs.ansible.com/ansible/latest/playbook_guide/index.html": "Using Ansible Playbooks",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_intro.html": "Ansible Playbooks",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_roles.html": "Roles",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html": "Using Variables",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_templating.html": "Templating (Jinja2)",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_conditionals.html": "Conditionals",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_loops.html": "Loops",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_handlers.html": "Handlers: Running Operations on Change",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_tags.html": "Tags",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_blocks.html": "Blocks",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_error_handling.html": "Error Handling in Playbooks",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_delegation.html": "Controlling Where Tasks Run: Delegation and Local Actions",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_strategies.html": "Controlling Playbook Execution: Strategies and More",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_async.html": "Asynchronous Actions and Polling",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse.html": "Re-using Ansible Artifacts",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_includes.html": "Including and Importing",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_filters.html": "Using Filters to Manipulate Data",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_tests.html": "Tests",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_lookups.html": "Lookups",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_prompts.html": "Interactive Input: Prompts",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_vars_facts.html": "Discovering Variables: Facts and Magic Variables",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_advanced_syntax.html": "Advanced Syntax",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_privilege_escalation.html": "Understanding Privilege Escalation: become",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_checkmode.html": "Validating Tasks: Check Mode and Diff Mode",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_debugger.html": "Debugging Tasks",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_startnstep.html": "Executing Playbooks for Troubleshooting",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_environment.html": "Setting the Remote Environment",
                "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_module_defaults.html": "Module Defaults",
                # Vault
                "https://docs.ansible.com/ansible/latest/vault_guide/index.html": "Protecting Sensitive Data with Ansible Vault",
                "https://docs.ansible.com/ansible/latest/vault_guide/vault.html": "Ansible Vault",
                "https://docs.ansible.com/ansible/latest/vault_guide/vault_encrypting_content.html": "Encrypting Content with Ansible Vault",
                "https://docs.ansible.com/ansible/latest/vault_guide/vault_using_encrypted_content.html": "Using Encrypted Variables and Files",
                "https://docs.ansible.com/ansible/latest/vault_guide/vault_managing_passwords.html": "Managing Vault Passwords",
            },
        },
        "modules": {
            "pages": {
                # Module Index and Top Modules
                "https://docs.ansible.com/ansible/latest/collections/index.html": "Collection Index",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/index.html": "Ansible.Builtin Collection",
                # ansible.builtin modules
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/command_module.html": "ansible.builtin.command Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/shell_module.html": "ansible.builtin.shell Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/raw_module.html": "ansible.builtin.raw Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/script_module.html": "ansible.builtin.script Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/copy_module.html": "ansible.builtin.copy Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/file_module.html": "ansible.builtin.file Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/template_module.html": "ansible.builtin.template Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/service_module.html": "ansible.builtin.service Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/systemd_module.html": "ansible.builtin.systemd Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/yum_module.html": "ansible.builtin.yum Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/apt_module.html": "ansible.builtin.apt Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/pip_module.html": "ansible.builtin.pip Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/git_module.html": "ansible.builtin.git Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/user_module.html": "ansible.builtin.user Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/group_module.html": "ansible.builtin.group Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/lineinfile_module.html": "ansible.builtin.lineinfile Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/replace_module.html": "ansible.builtin.replace Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/stat_module.html": "ansible.builtin.stat Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/debug_module.html": "ansible.builtin.debug Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/assert_module.html": "ansible.builtin.assert Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/set_fact_module.html": "ansible.builtin.set_fact Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/include_tasks_module.html": "ansible.builtin.include_tasks Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/import_tasks_module.html": "ansible.builtin.import_tasks Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/include_role_module.html": "ansible.builtin.include_role Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/import_role_module.html": "ansible.builtin.import_role Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/uri_module.html": "ansible.builtin.uri Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/get_url_module.html": "ansible.builtin.get_url Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/unarchive_module.html": "ansible.builtin.unarchive Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/cron_module.html": "ansible.builtin.cron Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/hostname_module.html": "ansible.builtin.hostname Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/setup_module.html": "ansible.builtin.setup Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/gather_facts_module.html": "ansible.builtin.gather_facts Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/package_module.html": "ansible.builtin.package Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/dnf_module.html": "ansible.builtin.dnf Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/fetch_module.html": "ansible.builtin.fetch Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/slurp_module.html": "ansible.builtin.slurp Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/wait_for_module.html": "ansible.builtin.wait_for Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/pause_module.html": "ansible.builtin.pause Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/fail_module.html": "ansible.builtin.fail Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/meta_module.html": "ansible.builtin.meta Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/add_host_module.html": "ansible.builtin.add_host Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/group_by_module.html": "ansible.builtin.group_by Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/blockinfile_module.html": "ansible.builtin.blockinfile Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/reboot_module.html": "ansible.builtin.reboot Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/tempfile_module.html": "ansible.builtin.tempfile Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/known_hosts_module.html": "ansible.builtin.known_hosts Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/expect_module.html": "ansible.builtin.expect Module",
            },
        },
        "collections": {
            "pages": {
                # ansible.posix collection
                "https://docs.ansible.com/ansible/latest/collections/ansible/posix/index.html": "Ansible.Posix Collection",
                "https://docs.ansible.com/ansible/latest/collections/ansible/posix/authorized_key_module.html": "ansible.posix.authorized_key Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/posix/mount_module.html": "ansible.posix.mount Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/posix/seboolean_module.html": "ansible.posix.seboolean Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/posix/selinux_module.html": "ansible.posix.selinux Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/posix/synchronize_module.html": "ansible.posix.synchronize Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/posix/sysctl_module.html": "ansible.posix.sysctl Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/posix/firewalld_module.html": "ansible.posix.firewalld Module",
                "https://docs.ansible.com/ansible/latest/collections/ansible/posix/acl_module.html": "ansible.posix.acl Module",
                # community.general collection
                "https://docs.ansible.com/ansible/latest/collections/community/general/index.html": "Community.General Collection",
                "https://docs.ansible.com/ansible/latest/collections/community/general/ini_file_module.html": "community.general.ini_file Module",
                "https://docs.ansible.com/ansible/latest/collections/community/general/nmcli_module.html": "community.general.nmcli Module",
                "https://docs.ansible.com/ansible/latest/collections/community/general/modprobe_module.html": "community.general.modprobe Module",
                "https://docs.ansible.com/ansible/latest/collections/community/general/timezone_module.html": "community.general.timezone Module",
                "https://docs.ansible.com/ansible/latest/collections/community/general/docker_container_module.html": "community.general.docker_container Module",
                "https://docs.ansible.com/ansible/latest/collections/community/general/docker_image_module.html": "community.general.docker_image Module",
                "https://docs.ansible.com/ansible/latest/collections/community/general/postgresql_db_module.html": "community.general.postgresql_db Module",
                "https://docs.ansible.com/ansible/latest/collections/community/general/postgresql_user_module.html": "community.general.postgresql_user Module",
                "https://docs.ansible.com/ansible/latest/collections/community/general/redis_module.html": "community.general.redis Module",
            },
        },
        "galaxy": {
            "pages": {
                # Galaxy
                "https://docs.ansible.com/ansible/latest/galaxy/user_guide.html": "Galaxy User Guide",
                "https://docs.ansible.com/ansible/latest/galaxy/dev_guide.html": "Galaxy Developer Guide",
                # Tips and Tricks
                "https://docs.ansible.com/ansible/latest/tips_tricks/index.html": "Ansible Tips and Tricks",
                "https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html": "General Tips",
                "https://docs.ansible.com/ansible/latest/tips_tricks/sample_setup.html": "Sample Ansible Setup",
            },
        },
        "network": {
            "pages": {
                # Network Automation
                "https://docs.ansible.com/ansible/latest/network/index.html": "Ansible for Network Automation",
                "https://docs.ansible.com/ansible/latest/network/getting_started/index.html": "Network Getting Started",
                "https://docs.ansible.com/ansible/latest/network/getting_started/basic_concepts.html": "Network Basic Concepts",
                "https://docs.ansible.com/ansible/latest/network/getting_started/first_playbook.html": "Run Your First Network Playbook",
                "https://docs.ansible.com/ansible/latest/network/getting_started/network_differences.html": "How Network Automation is Different",
                "https://docs.ansible.com/ansible/latest/network/user_guide/index.html": "Network User Guide",
                "https://docs.ansible.com/ansible/latest/network/user_guide/network_debug_troubleshooting.html": "Network Debug and Troubleshooting",
                "https://docs.ansible.com/ansible/latest/network/user_guide/platform_index.html": "Platform Options",
            },
        },
        "reference": {
            "pages": {
                # Reference and Appendices
                "https://docs.ansible.com/ansible/latest/reference_appendices/index.html": "Reference and Appendices",
                "https://docs.ansible.com/ansible/latest/reference_appendices/config.html": "Ansible Configuration Settings",
                "https://docs.ansible.com/ansible/latest/reference_appendices/special_variables.html": "Special Variables",
                "https://docs.ansible.com/ansible/latest/reference_appendices/playbooks_keywords.html": "Playbook Keywords",
                "https://docs.ansible.com/ansible/latest/reference_appendices/common_return_values.html": "Return Values",
                "https://docs.ansible.com/ansible/latest/reference_appendices/YAMLSyntax.html": "YAML Syntax",
                "https://docs.ansible.com/ansible/latest/reference_appendices/interpreter_discovery.html": "Interpreter Discovery",
                "https://docs.ansible.com/ansible/latest/reference_appendices/module_utils.html": "Module Utilities",
                "https://docs.ansible.com/ansible/latest/reference_appendices/glossary.html": "Glossary",
                "https://docs.ansible.com/ansible/latest/reference_appendices/faq.html": "Frequently Asked Questions",
                "https://docs.ansible.com/ansible/latest/reference_appendices/release_and_maintenance.html": "Releases and Maintenance",
                "https://docs.ansible.com/ansible/latest/reference_appendices/test_strategies.html": "Testing Strategies",
                # Developer Guide
                "https://docs.ansible.com/ansible/latest/dev_guide/index.html": "Developer Guide",
                "https://docs.ansible.com/ansible/latest/dev_guide/developing_modules_general.html": "Ansible Module Architecture",
                "https://docs.ansible.com/ansible/latest/dev_guide/developing_modules_best_practices.html": "Module Development Best Practices",
                "https://docs.ansible.com/ansible/latest/dev_guide/developing_collections.html": "Developing Collections",
                "https://docs.ansible.com/ansible/latest/dev_guide/developing_plugins.html": "Developing Plugins",
                "https://docs.ansible.com/ansible/latest/dev_guide/developing_inventory.html": "Developing Dynamic Inventory",
                # Porting Guides
                "https://docs.ansible.com/ansible/latest/porting_guides/porting_guides.html": "Ansible Porting Guides",
                # Roadmap
                "https://docs.ansible.com/ansible/latest/roadmap/index.html": "Ansible Roadmap",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"ansible-{source_key}" if source_key else "ansible"
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
            for suffix in [' — Ansible Documentation', ' — Ansible Community Documentation',
                           ' — Ansible', ' - Ansible Documentation']:
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
                        "category": f"ansible-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.0)

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
            self.log.info(f"=== Scraping ansible/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    AnsibleScraper(base, source_key).run()
