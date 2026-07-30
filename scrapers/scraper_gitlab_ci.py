#!/usr/bin/env python3
"""GitLab CI/CD documentation scraper.

Covers:
  - Pipeline configuration and architecture
  - Jobs, stages, and workflow rules
  - .gitlab-ci.yml YAML reference
  - Runners installation and configuration
  - CI/CD variables and environments
  - Artifacts, caching, and dependencies
  - Docker integration and services
  - Security scanning and compliance
  - Includes, templates, and components
  - Testing and code quality
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class GitLabCIScraper(BaseScraper):
    """Scrape GitLab CI/CD documentation across all sections."""

    SOURCES = {
        "pipelines": {
            "pages": {
                "https://docs.gitlab.com/ee/ci/pipelines/": "CI/CD Pipelines Overview",
                "https://docs.gitlab.com/ee/ci/pipelines/pipeline_architectures.html": "Pipeline Architectures",
                "https://docs.gitlab.com/ee/ci/pipelines/merge_request_pipelines.html": "Merge Request Pipelines",
                "https://docs.gitlab.com/ee/ci/pipelines/merged_results_pipelines.html": "Merged Results Pipelines",
                "https://docs.gitlab.com/ee/ci/pipelines/merge_trains.html": "Merge Trains",
                "https://docs.gitlab.com/ee/ci/pipelines/downstream_pipelines.html": "Downstream Pipelines",
                "https://docs.gitlab.com/ee/ci/pipelines/parent_child_pipelines.html": "Parent-Child Pipelines",
                "https://docs.gitlab.com/ee/ci/pipelines/multi_project_pipelines.html": "Multi-Project Pipelines",
                "https://docs.gitlab.com/ee/ci/pipelines/schedules.html": "Pipeline Schedules",
                "https://docs.gitlab.com/ee/ci/pipelines/settings.html": "Pipeline Settings",
                "https://docs.gitlab.com/ee/ci/pipelines/pipeline_efficiency.html": "Pipeline Efficiency",
                "https://docs.gitlab.com/ee/ci/pipelines/cicd_minutes.html": "CI/CD Minutes",
            },
        },
        "jobs": {
            "pages": {
                "https://docs.gitlab.com/ee/ci/jobs/": "CI/CD Jobs Overview",
                "https://docs.gitlab.com/ee/ci/jobs/job_control.html": "Job Control",
                "https://docs.gitlab.com/ee/ci/jobs/job_artifacts.html": "Job Artifacts",
                "https://docs.gitlab.com/ee/ci/jobs/ci_job_token.html": "CI Job Token",
                "https://docs.gitlab.com/ee/ci/jobs/job_troubleshooting.html": "Job Troubleshooting",
                "https://docs.gitlab.com/ee/ci/resource_groups/": "Resource Groups",
                "https://docs.gitlab.com/ee/ci/directed_acyclic_graph/": "Directed Acyclic Graph",
            },
        },
        "yaml-reference": {
            "pages": {
                "https://docs.gitlab.com/ee/ci/yaml/": ".gitlab-ci.yml Reference",
                "https://docs.gitlab.com/ee/ci/yaml/yaml_optimization.html": "YAML Optimization",
                "https://docs.gitlab.com/ee/ci/yaml/script.html": "Script Keyword",
                "https://docs.gitlab.com/ee/ci/yaml/artifacts_reports.html": "Artifacts Reports",
                "https://docs.gitlab.com/ee/ci/yaml/needs.html": "Needs Keyword",
                "https://docs.gitlab.com/ee/ci/yaml/workflow.html": "Workflow Keyword",
                "https://docs.gitlab.com/ee/ci/yaml/inputs.html": "Inputs Keyword",
                "https://docs.gitlab.com/ee/ci/yaml/signing_examples.html": "Signing Examples",
            },
        },
        "runners": {
            "pages": {
                "https://docs.gitlab.com/runner/": "GitLab Runner Overview",
                "https://docs.gitlab.com/runner/install/": "Runner Installation",
                "https://docs.gitlab.com/runner/install/linux-repository.html": "Install Runner on Linux",
                "https://docs.gitlab.com/runner/install/linux-manually.html": "Install Runner Manually on Linux",
                "https://docs.gitlab.com/runner/install/osx.html": "Install Runner on macOS",
                "https://docs.gitlab.com/runner/install/windows.html": "Install Runner on Windows",
                "https://docs.gitlab.com/runner/install/docker.html": "Install Runner with Docker",
                "https://docs.gitlab.com/runner/install/kubernetes.html": "Install Runner on Kubernetes",
                "https://docs.gitlab.com/runner/register/": "Register a Runner",
                "https://docs.gitlab.com/runner/configuration/": "Runner Configuration",
                "https://docs.gitlab.com/runner/configuration/advanced-configuration.html": "Runner Advanced Configuration",
                "https://docs.gitlab.com/runner/configuration/autoscale.html": "Runner Autoscaling",
                "https://docs.gitlab.com/runner/executors/": "Runner Executors",
                "https://docs.gitlab.com/runner/executors/docker.html": "Docker Executor",
                "https://docs.gitlab.com/runner/executors/shell.html": "Shell Executor",
                "https://docs.gitlab.com/runner/executors/kubernetes/": "Kubernetes Executor",
                "https://docs.gitlab.com/runner/executors/docker_machine.html": "Docker Machine Executor",
                "https://docs.gitlab.com/runner/executors/ssh.html": "SSH Executor",
                "https://docs.gitlab.com/runner/executors/virtualbox.html": "VirtualBox Executor",
                "https://docs.gitlab.com/runner/executors/parallels.html": "Parallels Executor",
                "https://docs.gitlab.com/runner/security/": "Runner Security",
                "https://docs.gitlab.com/runner/monitoring/": "Runner Monitoring",
                "https://docs.gitlab.com/runner/fleet_scaling/": "Fleet Scaling",
                "https://docs.gitlab.com/ee/ci/runners/runners_scope.html": "Runner Scope",
                "https://docs.gitlab.com/ee/ci/runners/configure_runners.html": "Configure Runners",
                "https://docs.gitlab.com/ee/ci/runners/saas/linux_saas_runner.html": "SaaS Linux Runners",
            },
        },
        "variables": {
            "pages": {
                "https://docs.gitlab.com/ee/ci/variables/": "CI/CD Variables",
                "https://docs.gitlab.com/ee/ci/variables/predefined_variables.html": "Predefined Variables",
                "https://docs.gitlab.com/ee/ci/variables/where_variables_can_be_used.html": "Where Variables Can Be Used",
                "https://docs.gitlab.com/ee/ci/secrets/": "CI/CD Secrets",
                "https://docs.gitlab.com/ee/ci/secrets/hashicorp_vault.html": "HashiCorp Vault Integration",
                "https://docs.gitlab.com/ee/ci/secrets/azure_key_vault.html": "Azure Key Vault Integration",
                "https://docs.gitlab.com/ee/ci/secrets/gcp_secret_manager.html": "GCP Secret Manager Integration",
            },
        },
        "environments": {
            "pages": {
                "https://docs.gitlab.com/ee/ci/environments/": "Environments and Deployments",
                "https://docs.gitlab.com/ee/ci/environments/protected_environments.html": "Protected Environments",
                "https://docs.gitlab.com/ee/ci/environments/deployment_safety.html": "Deployment Safety",
                "https://docs.gitlab.com/ee/ci/environments/deployment_approvals.html": "Deployment Approvals",
                "https://docs.gitlab.com/ee/ci/environments/incremental_rollouts.html": "Incremental Rollouts",
                "https://docs.gitlab.com/ee/ci/environments/kubernetes_dashboard.html": "Kubernetes Dashboard",
                "https://docs.gitlab.com/ee/ci/review_apps/": "Review Apps",
            },
        },
        "artifacts": {
            "pages": {
                "https://docs.gitlab.com/ee/ci/jobs/job_artifacts.html": "Job Artifacts",
                "https://docs.gitlab.com/ee/ci/yaml/artifacts_reports.html": "Artifacts Reports Types",
                "https://docs.gitlab.com/ee/ci/unit_test_reports.html": "Unit Test Reports",
                "https://docs.gitlab.com/ee/ci/testing/code_coverage.html": "Code Coverage",
                "https://docs.gitlab.com/ee/ci/testing/test_coverage_visualization.html": "Test Coverage Visualization",
                "https://docs.gitlab.com/ee/ci/testing/metrics_reports.html": "Metrics Reports",
                "https://docs.gitlab.com/ee/ci/pipelines/job_artifacts.html": "Pipeline Job Artifacts",
            },
        },
        "security": {
            "pages": {
                "https://docs.gitlab.com/ee/user/application_security/": "Application Security Overview",
                "https://docs.gitlab.com/ee/user/application_security/sast/": "SAST",
                "https://docs.gitlab.com/ee/user/application_security/dast/": "DAST",
                "https://docs.gitlab.com/ee/user/application_security/dependency_scanning/": "Dependency Scanning",
                "https://docs.gitlab.com/ee/user/application_security/container_scanning/": "Container Scanning",
                "https://docs.gitlab.com/ee/user/application_security/secret_detection/": "Secret Detection",
                "https://docs.gitlab.com/ee/user/application_security/iac_scanning/": "IaC Scanning",
                "https://docs.gitlab.com/ee/user/application_security/license_compliance/": "License Compliance",
                "https://docs.gitlab.com/ee/user/application_security/vulnerability_report/": "Vulnerability Report",
                "https://docs.gitlab.com/ee/user/application_security/security_dashboard/": "Security Dashboard",
                "https://docs.gitlab.com/ee/user/application_security/policies/": "Security Policies",
                "https://docs.gitlab.com/ee/user/application_security/api_fuzzing/": "API Fuzzing",
                "https://docs.gitlab.com/ee/user/application_security/coverage_fuzzing/": "Coverage Fuzzing",
            },
        },
        "docker": {
            "pages": {
                "https://docs.gitlab.com/ee/ci/docker/using_docker_build.html": "Use Docker to Build Docker Images",
                "https://docs.gitlab.com/ee/ci/docker/using_docker_images.html": "Use Docker Images",
                "https://docs.gitlab.com/ee/ci/docker/using_kaniko.html": "Use Kaniko",
                "https://docs.gitlab.com/ee/user/packages/container_registry/": "Container Registry",
                "https://docs.gitlab.com/ee/user/packages/container_registry/build_and_push_images.html": "Build and Push Images",
                "https://docs.gitlab.com/ee/user/packages/container_registry/reduce_container_registry_storage.html": "Reduce Registry Storage",
            },
        },
        "services": {
            "pages": {
                "https://docs.gitlab.com/ee/ci/services/": "Services Overview",
                "https://docs.gitlab.com/ee/ci/services/postgres.html": "Using PostgreSQL",
                "https://docs.gitlab.com/ee/ci/services/mysql.html": "Using MySQL",
                "https://docs.gitlab.com/ee/ci/services/redis.html": "Using Redis",
                "https://docs.gitlab.com/ee/ci/services/gitlab.html": "Using GitLab as a Service",
            },
        },
        "caching": {
            "pages": {
                "https://docs.gitlab.com/ee/ci/caching/": "Caching in CI/CD",
                "https://docs.gitlab.com/ee/ci/caching/index.html": "Cache Configuration",
                "https://docs.gitlab.com/ee/ci/large_repositories/": "Large Repositories Optimization",
                "https://docs.gitlab.com/ee/ci/git_submodules.html": "Git Submodules in CI/CD",
            },
        },
        "includes": {
            "pages": {
                "https://docs.gitlab.com/ee/ci/yaml/includes.html": "Include Keyword",
                "https://docs.gitlab.com/ee/ci/components/": "CI/CD Components",
                "https://docs.gitlab.com/ee/ci/components/catalog.html": "CI/CD Catalog",
                "https://docs.gitlab.com/ee/ci/templates/": "CI/CD Templates",
                "https://docs.gitlab.com/ee/development/cicd/templates.html": "Template Development Guide",
                "https://docs.gitlab.com/ee/ci/yaml/yaml_optimization.html": "YAML Optimization and Anchors",
            },
        },
        "testing": {
            "pages": {
                "https://docs.gitlab.com/ee/ci/testing/": "Testing Overview",
                "https://docs.gitlab.com/ee/ci/testing/code_quality.html": "Code Quality",
                "https://docs.gitlab.com/ee/ci/testing/browser_performance_testing.html": "Browser Performance Testing",
                "https://docs.gitlab.com/ee/ci/testing/load_performance_testing.html": "Load Performance Testing",
                "https://docs.gitlab.com/ee/ci/testing/accessibility_testing.html": "Accessibility Testing",
                "https://docs.gitlab.com/ee/ci/testing/fail_fast_testing.html": "Fail Fast Testing",
                "https://docs.gitlab.com/ee/ci/unit_test_reports.html": "Unit Test Reports",
                "https://docs.gitlab.com/ee/ci/testing/code_coverage.html": "Code Coverage Reports",
                "https://docs.gitlab.com/ee/ci/testing/test_coverage_visualization.html": "Test Coverage Visualization",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"gitlab-ci-{source_key}" if source_key else "gitlab-ci"
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
            for suffix in [' | GitLab', ' | GitLab Docs', ' - GitLab Documentation']:
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
                        "category": f"gitlab-ci-{source_key}",
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
            self.log.info(f"=== Scraping gitlab-ci/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    GitLabCIScraper(base, source_key).run()
