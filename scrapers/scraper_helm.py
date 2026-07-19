#!/usr/bin/env python3
"""Helm documentation scraper.

Covers:
  - Helm introduction, quickstart, installation
  - Helm commands (install, upgrade, repo, search, etc.)
  - Chart template guide (values, functions, control structures)
  - How-to guides, topics, community resources
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class HelmScraper(BaseScraper):
    """Scrape Helm documentation across all sections."""

    SOURCES = {
        "intro": {
            "pages": {
                "https://helm.sh/docs/intro/": "Helm Introduction",
                "https://helm.sh/docs/intro/quickstart/": "Helm Quickstart",
                "https://helm.sh/docs/intro/install/": "Helm Install",
                "https://helm.sh/docs/intro/using_helm/": "Using Helm",
                "https://helm.sh/docs/intro/cheatsheet/": "Helm Cheatsheet",
                "https://helm.sh/docs/": "Helm Docs Home",
                "https://helm.sh/docs/intro/getting_started/": "Getting Started with Helm",
                "https://helm.sh/docs/intro/three_big_concepts/": "Three Big Concepts",
            },
        },
        "using-helm": {
            "pages": {
                "https://helm.sh/docs/helm/": "Helm Commands",
                "https://helm.sh/docs/helm/helm/": "Helm",
                "https://helm.sh/docs/helm/helm_install/": "helm install",
                "https://helm.sh/docs/helm/helm_upgrade/": "helm upgrade",
                "https://helm.sh/docs/helm/helm_uninstall/": "helm uninstall",
                "https://helm.sh/docs/helm/helm_rollback/": "helm rollback",
                "https://helm.sh/docs/helm/helm_list/": "helm list",
                "https://helm.sh/docs/helm/helm_status/": "helm status",
                "https://helm.sh/docs/helm/helm_repo/": "helm repo",
                "https://helm.sh/docs/helm/helm_repo_add/": "helm repo add",
                "https://helm.sh/docs/helm/helm_repo_update/": "helm repo update",
                "https://helm.sh/docs/helm/helm_search/": "helm search",
                "https://helm.sh/docs/helm/helm_search_hub/": "helm search hub",
                "https://helm.sh/docs/helm/helm_search_repo/": "helm search repo",
                "https://helm.sh/docs/helm/helm_pull/": "helm pull",
                "https://helm.sh/docs/helm/helm_show/": "helm show",
                "https://helm.sh/docs/helm/helm_show_values/": "helm show values",
                "https://helm.sh/docs/helm/helm_show_chart/": "helm show chart",
                "https://helm.sh/docs/helm/helm_template/": "helm template",
                "https://helm.sh/docs/helm/helm_create/": "helm create",
                "https://helm.sh/docs/helm/helm_package/": "helm package",
                "https://helm.sh/docs/helm/helm_lint/": "helm lint",
                "https://helm.sh/docs/helm/helm_test/": "helm test",
                "https://helm.sh/docs/helm/helm_history/": "helm history",
                "https://helm.sh/docs/helm/helm_get/": "helm get",
                "https://helm.sh/docs/helm/helm_get_values/": "helm get values",
                "https://helm.sh/docs/helm/helm_get_manifest/": "helm get manifest",
                "https://helm.sh/docs/helm/helm_dependency/": "helm dependency",
                "https://helm.sh/docs/helm/helm_dependency_update/": "helm dependency update",
                "https://helm.sh/docs/helm/helm_dependency_build/": "helm dependency build",
                "https://helm.sh/docs/helm/helm_plugin/": "helm plugin",
                "https://helm.sh/docs/helm/helm_env/": "helm env",
                "https://helm.sh/docs/helm/helm_verify/": "helm verify",
                "https://helm.sh/docs/helm/helm_version/": "helm version",
                "https://helm.sh/docs/helm/helm_completion/": "helm completion",
                "https://helm.sh/docs/helm/helm_repo_list/": "helm repo list",
                "https://helm.sh/docs/helm/helm_repo_remove/": "helm repo remove",
                "https://helm.sh/docs/helm/helm_repo_index/": "helm repo index",
                "https://helm.sh/docs/helm/helm_get_hooks/": "helm get hooks",
                "https://helm.sh/docs/helm/helm_get_notes/": "helm get notes",
                "https://helm.sh/docs/helm/helm_get_all/": "helm get all",
                "https://helm.sh/docs/helm/helm_show_all/": "helm show all",
                "https://helm.sh/docs/helm/helm_show_readme/": "helm show readme",
                "https://helm.sh/docs/helm/helm_plugin_install/": "helm plugin install",
                "https://helm.sh/docs/helm/helm_plugin_list/": "helm plugin list",
                "https://helm.sh/docs/helm/helm_plugin_uninstall/": "helm plugin uninstall",
                "https://helm.sh/docs/helm/helm_plugin_update/": "helm plugin update",
            },
        },
        "chart-template-guide": {
            "pages": {
                "https://helm.sh/docs/chart_template_guide/": "Chart Template Guide",
                "https://helm.sh/docs/chart_template_guide/getting_started/": "Templates Getting Started",
                "https://helm.sh/docs/chart_template_guide/builtin_objects/": "Built-in Objects",
                "https://helm.sh/docs/chart_template_guide/values_files/": "Values Files",
                "https://helm.sh/docs/chart_template_guide/functions_and_pipelines/": "Functions and Pipelines",
                "https://helm.sh/docs/chart_template_guide/function_list/": "Function List",
                "https://helm.sh/docs/chart_template_guide/control_structures/": "Control Structures",
                "https://helm.sh/docs/chart_template_guide/variables/": "Variables",
                "https://helm.sh/docs/chart_template_guide/named_templates/": "Named Templates",
                "https://helm.sh/docs/chart_template_guide/accessing_files/": "Accessing Files",
                "https://helm.sh/docs/chart_template_guide/notes_files/": "NOTES.txt",
                "https://helm.sh/docs/chart_template_guide/subcharts_and_globals/": "Subcharts and Globals",
                "https://helm.sh/docs/chart_template_guide/debugging/": "Debugging Templates",
                "https://helm.sh/docs/chart_template_guide/wrapping_up/": "Wrapping Up",
                "https://helm.sh/docs/chart_template_guide/yaml_techniques/": "YAML Techniques",
                "https://helm.sh/docs/chart_template_guide/data_types/": "Data Types",
                "https://helm.sh/docs/chart_template_guide/crd_hook/": "CRD Hook",
                "https://helm.sh/docs/chart_template_guide/ext_template/": "External Templates",
            },
        },
        "howto": {
            "pages": {
                "https://helm.sh/docs/howto/": "How-To Guides",
                "https://helm.sh/docs/howto/chart_releaser_action/": "Chart Releaser Action",
                "https://helm.sh/docs/howto/chart_repository_sync_example/": "Chart Repository Sync",
                "https://helm.sh/docs/howto/charts_tips_and_tricks/": "Charts Tips and Tricks",
                "https://helm.sh/docs/howto/auth_pass_credentials/": "Auth Pass Credentials",
                "https://helm.sh/docs/howto/deprecate_a_chart/": "Deprecate a Chart",
            },
        },
        "topics": {
            "pages": {
                "https://helm.sh/docs/topics/": "Helm Topics",
                "https://helm.sh/docs/topics/architecture/": "Helm Architecture",
                "https://helm.sh/docs/topics/charts/": "Charts",
                "https://helm.sh/docs/topics/charts_hooks/": "Chart Hooks",
                "https://helm.sh/docs/topics/chart_repository/": "Chart Repository",
                "https://helm.sh/docs/topics/chart_tests/": "Chart Tests",
                "https://helm.sh/docs/topics/library_charts/": "Library Charts",
                "https://helm.sh/docs/topics/plugins/": "Plugins",
                "https://helm.sh/docs/topics/provenance/": "Provenance and Integrity",
                "https://helm.sh/docs/topics/rbac/": "Role-Based Access Control",
                "https://helm.sh/docs/topics/registries/": "Registries",
                "https://helm.sh/docs/topics/kubernetes_distros/": "Kubernetes Distributions",
                "https://helm.sh/docs/topics/v2_v3_migration/": "V2 to V3 Migration",
                "https://helm.sh/docs/topics/advanced/": "Advanced Helm Techniques",
                "https://helm.sh/docs/topics/permissions_sql_storage_backend/": "Permissions SQL Backend",
                "https://helm.sh/docs/topics/kubernetes_apis/": "Kubernetes APIs",
                "https://helm.sh/docs/topics/version_skew/": "Version Skew",
                "https://helm.sh/docs/topics/release_policy/": "Release Policy",
            },
        },
        "community": {
            "pages": {
                "https://helm.sh/docs/community/": "Helm Community",
                "https://helm.sh/docs/community/developers/": "Developers",
                "https://helm.sh/docs/community/history/": "History",
                "https://helm.sh/docs/community/localization/": "Localization",
                "https://helm.sh/docs/community/related/": "Related Projects",
                "https://helm.sh/docs/community/release_checklist/": "Release Checklist",
            },
        },
        "helm-commands": {
            "pages": {
                "https://helm.sh/docs/faq/": "Helm FAQ",
                "https://helm.sh/docs/glossary/": "Helm Glossary",
                "https://helm.sh/blog/": "Helm Blog",
                "https://helm.sh/docs/chart_best_practices/": "Chart Best Practices",
                "https://helm.sh/docs/chart_best_practices/conventions/": "Conventions",
                "https://helm.sh/docs/chart_best_practices/values/": "Values Best Practices",
                "https://helm.sh/docs/chart_best_practices/templates/": "Templates Best Practices",
                "https://helm.sh/docs/chart_best_practices/dependencies/": "Dependencies Best Practices",
                "https://helm.sh/docs/chart_best_practices/labels/": "Labels Best Practices",
                "https://helm.sh/docs/chart_best_practices/pods/": "Pods Best Practices",
                "https://helm.sh/docs/chart_best_practices/custom_resource_definitions/": "CRDs Best Practices",
                "https://helm.sh/docs/chart_best_practices/rbac/": "RBAC Best Practices",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"helm-{source_key}" if source_key else "helm"
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
            for suffix in [' | Helm', ' - Helm']:
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
                        "category": f"helm-{source_key}",
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
            self.log.info(f"=== Scraping helm/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    HelmScraper(base, source_key).run()
