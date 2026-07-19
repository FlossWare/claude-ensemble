#!/usr/bin/env python3
"""Argo CD documentation scraper.

Covers:
  - Getting Started: overview, basics, quick start
  - Core Concepts: architecture, application model
  - User Guide: CLI commands, sync, helm, kustomize, projects
  - Operator Manual: installation, HA, security, RBAC, SSO, ApplicationSet
  - Developer Guide: API docs, contributing, extensions
  - FAQ: common questions
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class ArgoCdScraper(BaseScraper):
    """Scrape Argo CD official documentation."""

    SOURCES = {
        "getting-started": {
            "pages": {
                "https://argo-cd.readthedocs.io/en/stable/": "Argo CD Overview",
                "https://argo-cd.readthedocs.io/en/stable/getting_started/": "Argo CD Getting Started",
                "https://argo-cd.readthedocs.io/en/stable/understand_the_basics/": "Understanding the Basics",
                "https://argo-cd.readthedocs.io/en/stable/getting_started/install/": "Installation Quick Start",
                "https://argo-cd.readthedocs.io/en/stable/getting_started/first-application/": "Deploy First Application",
            },
        },
        "core-concepts": {
            "pages": {
                "https://argo-cd.readthedocs.io/en/stable/core_concepts/": "Argo CD Core Concepts",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/architecture/": "Argo CD Architecture",
                "https://argo-cd.readthedocs.io/en/stable/core_concepts/application-sources/": "Application Sources",
                "https://argo-cd.readthedocs.io/en/stable/core_concepts/sync-and-diff/": "Sync and Diff",
                "https://argo-cd.readthedocs.io/en/stable/core_concepts/health/": "Health Status",
            },
        },
        "user-guide": {
            "pages": {
                # Application Specification
                "https://argo-cd.readthedocs.io/en/stable/user-guide/application-specification/": "Application Specification",
                # CLI Commands
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd/": "argocd CLI",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app/": "argocd app",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_create/": "argocd app create",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_sync/": "argocd app sync",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_get/": "argocd app get",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_delete/": "argocd app delete",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_list/": "argocd app list",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_set/": "argocd app set",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_diff/": "argocd app diff",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_history/": "argocd app history",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_rollback/": "argocd app rollback",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_logs/": "argocd app logs",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_manifests/": "argocd app manifests",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_patch/": "argocd app patch",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_patch-resource/": "argocd app patch-resource",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_resources/": "argocd app resources",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_terminate-op/": "argocd app terminate-op",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_unset/": "argocd app unset",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_wait/": "argocd app wait",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_cluster/": "argocd cluster",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_cluster_add/": "argocd cluster add",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_cluster_get/": "argocd cluster get",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_cluster_list/": "argocd cluster list",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_cluster_rm/": "argocd cluster rm",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_login/": "argocd login",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_logout/": "argocd logout",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_repo/": "argocd repo",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_repo_add/": "argocd repo add",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_repo_list/": "argocd repo list",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_repo_rm/": "argocd repo rm",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_project/": "argocd project",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_project_create/": "argocd project create",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_project_get/": "argocd project get",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_project_list/": "argocd project list",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_project_delete/": "argocd project delete",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_account/": "argocd account",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_account_update-password/": "argocd account update-password",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_account_generate-token/": "argocd account generate-token",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_cert/": "argocd cert",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_cert_add-tls/": "argocd cert add-tls",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_cert_list/": "argocd cert list",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_gpg/": "argocd gpg",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_admin/": "argocd admin",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_version/": "argocd version",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_context/": "argocd context",
                # Features & Guides
                "https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/": "Auto-Sync Policy",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/": "Best Practices",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/ci_automation/": "CI Automation",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/config-management-plugins/": "Config Management Plugins",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/directory/": "Directory Applications",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/diffing/": "Diffing Customization",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/external-url/": "External URLs",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/helm/": "Helm Integration",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/jsonnet/": "Jsonnet Integration",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/kustomize/": "Kustomize Integration",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/multiple_sources/": "Multiple Sources",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/orphaned-resources/": "Orphaned Resources",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/parameters/": "Parameters",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/private-repositories/": "Private Repositories",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/projects/": "Projects",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/resource_hooks/": "Resource Hooks",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/resource_tracking/": "Resource Tracking",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/selective_sync/": "Selective Sync",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/status-badge/": "Status Badge",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/": "Sync Options",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/": "Sync Waves",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/tool_detection/": "Tool Detection",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/tracking_strategies/": "Tracking Strategies",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/app_deletion/": "Application Deletion",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/annotations/": "Annotations and Labels",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/build-environment/": "Build Environment",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/extra-info/": "Extra Application Info",
                "https://argo-cd.readthedocs.io/en/stable/user-guide/gpg-verification/": "GnuPG Verification",
            },
        },
        "operator-manual": {
            "pages": {
                # Core Operations
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/": "Operator Manual",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/installation/": "Installation",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/core/": "Core Installation",
                # Server Components
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/server-commands/argocd-server/": "argocd-server",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/server-commands/argocd-repo-server/": "argocd-repo-server",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/server-commands/argocd-application-controller/": "argocd-application-controller",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/server-commands/argocd-dex/": "argocd-dex",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/server-commands/argocd-cmp-server/": "argocd-cmp-server",
                # Setup & Configuration
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/": "Declarative Setup",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/high_availability/": "High Availability",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/disaster_recovery/": "Disaster Recovery",
                # Security & Auth
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/security/": "Security",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/": "User Management",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/": "RBAC Configuration",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/sso/": "SSO Configuration",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/sso/dex/": "Dex SSO",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/sso/okta/": "Okta SSO",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/sso/microsoft/": "Microsoft SSO",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/sso/google/": "Google SSO",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/sso/keycloak/": "Keycloak SSO",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/sso/gitlab/": "GitLab SSO",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/sso/github/": "GitHub SSO",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/sso/OIDC/": "OIDC SSO",
                # Networking
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/ingress/": "Ingress Configuration",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/tls/": "TLS Configuration",
                # Monitoring
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/metrics/": "Metrics",
                # Notifications
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/": "Notifications",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/templates/": "Notification Templates",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/triggers/": "Notification Triggers",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/services/slack/": "Slack Notifications",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/services/email/": "Email Notifications",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/services/webhook/": "Webhook Notifications",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/services/teams/": "Teams Notifications",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/services/grafana/": "Grafana Notifications",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/services/opsgenie/": "OpsGenie Notifications",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/services/pagerduty/": "PagerDuty Notifications",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/services/github/": "GitHub Notifications",
                # ApplicationSet
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/": "ApplicationSet",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Getting-Started/": "ApplicationSet Getting Started",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators/": "ApplicationSet Generators",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-List/": "List Generator",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Cluster/": "Cluster Generator",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Git/": "Git Generator",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Matrix/": "Matrix Generator",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Merge/": "Merge Generator",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Pull-Request/": "Pull Request Generator",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-SCM-Provider/": "SCM Provider Generator",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Cluster-Decision-Resource/": "Cluster Decision Resource Generator",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Template/": "ApplicationSet Template",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Policy/": "ApplicationSet Policy",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Controlling-Resource-Modification/": "Controlling Resource Modification",
                # Other Operations
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/custom_tools/": "Custom Tools",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/health/": "Health Assessment",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/resource_actions/": "Resource Actions",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/troubleshooting/": "Troubleshooting",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/upgrading/overview/": "Upgrading",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/webhook/": "Webhooks",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/config-management-plugins/": "Config Management Plugins (Operator)",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/dynamic-cluster-distribution/": "Dynamic Cluster Distribution",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/signed-release-assets/": "Signed Release Assets",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/project-specification/": "Project Specification",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/argocd-cm-yaml/": "argocd-cm ConfigMap Reference",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/argocd-cmd-params-cm-yaml/": "argocd-cmd-params-cm ConfigMap Reference",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/argocd-rbac-cm-yaml/": "argocd-rbac-cm ConfigMap Reference",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/argocd-secret-yaml/": "argocd-secret Reference",
                "https://argo-cd.readthedocs.io/en/stable/operator-manual/app-any-namespace/": "Applications in Any Namespace",
            },
        },
        "developer-guide": {
            "pages": {
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/": "Developer Guide",
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/api-docs/": "API Documentation",
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/architecture/": "Developer Architecture",
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/ci/": "CI/CD",
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/contributing/": "Contributing",
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/running-locally/": "Running Locally",
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/test-e2e/": "E2E Testing",
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/toolchain-guide/": "Toolchain Guide",
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/extensions/": "Extensions",
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/faq/": "Developer FAQ",
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/site/": "Site Documentation",
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/debugging-remote-environment/": "Debugging Remote Environment",
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/release-process-and-cadence/": "Release Process and Cadence",
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/static-code-analysis/": "Static Code Analysis",
                "https://argo-cd.readthedocs.io/en/stable/developer-guide/dependencies/": "Dependencies",
            },
        },
        "faq": {
            "pages": {
                "https://argo-cd.readthedocs.io/en/stable/faq/": "FAQ",
                "https://argo-cd.readthedocs.io/en/stable/support/": "Support",
                "https://argo-cd.readthedocs.io/en/stable/roadmap/": "Roadmap",
                "https://argo-cd.readthedocs.io/en/stable/releases/": "Releases",
                "https://argo-cd.readthedocs.io/en/stable/security_considerations/": "Security Considerations",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"argocd-{source_key}" if source_key else "argocd"
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
            for suffix in [' - Argo CD - Declarative GitOps CD for Kubernetes',
                           ' - Argo CD', ' | Argo CD']:
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
                        "category": f"argocd-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)  # Rate limit

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
            self.log.info(f"=== Scraping argocd/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    ArgoCdScraper(base, source_key).run()
