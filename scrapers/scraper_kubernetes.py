#!/usr/bin/env python3
"""Kubernetes documentation scraper.

Covers:
  - Concepts: pods, services, deployments, namespaces, volumes, etc.
  - Tasks: manage resources, configure pods, debugging, TLS, etc.
  - Reference: kubectl commands, API overview
  - Tutorials: basics, stateless/stateful apps
  - Setup: kubeadm, production best practices
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class KubernetesScraper(BaseScraper):
    """Scrape Kubernetes official documentation."""

    SOURCES = {
        "concepts": {
            "pages": {
                # Overview
                "https://kubernetes.io/docs/concepts/overview/": "Kubernetes Overview",
                "https://kubernetes.io/docs/concepts/overview/what-is-kubernetes/": "What is Kubernetes",
                "https://kubernetes.io/docs/concepts/overview/components/": "Kubernetes Components",
                "https://kubernetes.io/docs/concepts/overview/kubernetes-api/": "The Kubernetes API",
                "https://kubernetes.io/docs/concepts/overview/working-with-objects/": "Working with Kubernetes Objects",
                "https://kubernetes.io/docs/concepts/overview/working-with-objects/kubernetes-objects/": "Understanding Kubernetes Objects",
                "https://kubernetes.io/docs/concepts/overview/working-with-objects/names/": "Object Names and IDs",
                "https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/": "Namespaces",
                "https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/": "Labels and Selectors",
                "https://kubernetes.io/docs/concepts/overview/working-with-objects/annotations/": "Annotations",
                "https://kubernetes.io/docs/concepts/overview/working-with-objects/field-selectors/": "Field Selectors",
                # Architecture
                "https://kubernetes.io/docs/concepts/architecture/": "Cluster Architecture",
                "https://kubernetes.io/docs/concepts/architecture/nodes/": "Nodes",
                "https://kubernetes.io/docs/concepts/architecture/control-plane-node-communication/": "Control Plane-Node Communication",
                "https://kubernetes.io/docs/concepts/architecture/controller/": "Controllers",
                # Workloads
                "https://kubernetes.io/docs/concepts/workloads/": "Workloads",
                "https://kubernetes.io/docs/concepts/workloads/pods/": "Pods",
                "https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/": "Pod Lifecycle",
                "https://kubernetes.io/docs/concepts/workloads/pods/init-containers/": "Init Containers",
                "https://kubernetes.io/docs/concepts/workloads/controllers/deployment/": "Deployments",
                "https://kubernetes.io/docs/concepts/workloads/controllers/replicaset/": "ReplicaSets",
                "https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/": "StatefulSets",
                "https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/": "DaemonSets",
                "https://kubernetes.io/docs/concepts/workloads/controllers/job/": "Jobs",
                "https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/": "CronJobs",
                # Services & Networking
                "https://kubernetes.io/docs/concepts/services-networking/": "Services, Load Balancing, and Networking",
                "https://kubernetes.io/docs/concepts/services-networking/service/": "Service",
                "https://kubernetes.io/docs/concepts/services-networking/ingress/": "Ingress",
                "https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/": "Ingress Controllers",
                "https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/": "EndpointSlices",
                "https://kubernetes.io/docs/concepts/services-networking/network-policies/": "Network Policies",
                "https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/": "DNS for Services and Pods",
                # Storage
                "https://kubernetes.io/docs/concepts/storage/": "Storage",
                "https://kubernetes.io/docs/concepts/storage/volumes/": "Volumes",
                "https://kubernetes.io/docs/concepts/storage/persistent-volumes/": "Persistent Volumes",
                "https://kubernetes.io/docs/concepts/storage/storage-classes/": "Storage Classes",
                "https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/": "Dynamic Volume Provisioning",
                "https://kubernetes.io/docs/concepts/storage/volume-snapshots/": "Volume Snapshots",
                # Configuration
                "https://kubernetes.io/docs/concepts/configuration/": "Configuration",
                "https://kubernetes.io/docs/concepts/configuration/configmap/": "ConfigMaps",
                "https://kubernetes.io/docs/concepts/configuration/secret/": "Secrets",
                "https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/": "Resource Management for Pods and Containers",
                # Security
                "https://kubernetes.io/docs/concepts/security/": "Security",
                "https://kubernetes.io/docs/concepts/security/rbac-good-practices/": "RBAC Good Practices",
                "https://kubernetes.io/docs/concepts/security/pod-security-standards/": "Pod Security Standards",
                "https://kubernetes.io/docs/concepts/security/service-accounts/": "Service Accounts",
                # Scheduling
                "https://kubernetes.io/docs/concepts/scheduling-eviction/": "Scheduling, Preemption and Eviction",
                "https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/": "Assigning Pods to Nodes",
                "https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/": "Taints and Tolerations",
                "https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/": "Pod Priority and Preemption",
                # Cluster Administration
                "https://kubernetes.io/docs/concepts/cluster-administration/": "Cluster Administration",
                "https://kubernetes.io/docs/concepts/cluster-administration/logging/": "Logging Architecture",
                "https://kubernetes.io/docs/concepts/cluster-administration/manage-deployment/": "Managing Resources",
                # Extend
                "https://kubernetes.io/docs/concepts/extend-kubernetes/": "Extending Kubernetes",
                "https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/": "Custom Resources",
                "https://kubernetes.io/docs/concepts/extend-kubernetes/operator/": "Operator Pattern",
            },
        },
        "tasks": {
            "pages": {
                # Managing Resources
                "https://kubernetes.io/docs/tasks/": "Tasks Overview",
                "https://kubernetes.io/docs/tasks/tools/": "Install Tools",
                "https://kubernetes.io/docs/tasks/manage-kubernetes-objects/declarative-config/": "Declarative Management using Config Files",
                "https://kubernetes.io/docs/tasks/manage-kubernetes-objects/imperative-config/": "Imperative Management using Config Files",
                "https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/": "Managing Objects with Kustomize",
                # Configure Pods
                "https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/": "Configure Liveness, Readiness and Startup Probes",
                "https://kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/": "Assign Memory Resources to Containers",
                "https://kubernetes.io/docs/tasks/configure-pod-container/assign-cpu-resource/": "Assign CPU Resources to Containers",
                "https://kubernetes.io/docs/tasks/configure-pod-container/configure-volume-storage/": "Configure a Pod to Use a Volume for Storage",
                "https://kubernetes.io/docs/tasks/configure-pod-container/configure-persistent-volume-storage/": "Configure a Pod to Use a PersistentVolume for Storage",
                "https://kubernetes.io/docs/tasks/configure-pod-container/configure-projected-volume-storage/": "Configure a Pod to Use a Projected Volume",
                "https://kubernetes.io/docs/tasks/configure-pod-container/security-context/": "Configure a Security Context for a Pod or Container",
                "https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/": "Configure Service Accounts for Pods",
                # Inject Data
                "https://kubernetes.io/docs/tasks/inject-data-application/define-command-argument-container/": "Define a Command and Arguments for a Container",
                "https://kubernetes.io/docs/tasks/inject-data-application/define-environment-variable-container/": "Define Environment Variables for a Container",
                "https://kubernetes.io/docs/tasks/inject-data-application/distribute-credentials-secure/": "Distribute Credentials Securely Using Secrets",
                # Run Applications
                "https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/": "Horizontal Pod Autoscaling",
                "https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/": "HPA Walkthrough",
                "https://kubernetes.io/docs/tasks/run-application/run-stateless-application-deployment/": "Run a Stateless Application Using a Deployment",
                "https://kubernetes.io/docs/tasks/run-application/run-single-instance-stateful-application/": "Run a Single-Instance Stateful Application",
                "https://kubernetes.io/docs/tasks/run-application/run-replicated-stateful-application/": "Run a Replicated Stateful Application",
                # Access Applications
                "https://kubernetes.io/docs/tasks/access-application-cluster/web-ui-dashboard/": "Web UI (Dashboard)",
                "https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/": "Use Port Forwarding to Access Applications",
                "https://kubernetes.io/docs/tasks/access-application-cluster/create-external-load-balancer/": "Create an External Load Balancer",
                # Monitoring & Debugging
                "https://kubernetes.io/docs/tasks/debug/debug-application/": "Troubleshooting Applications",
                "https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/": "Debug Pods",
                "https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/": "Debug Services",
                "https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/": "Debug Running Pods",
                "https://kubernetes.io/docs/tasks/debug/debug-cluster/": "Troubleshoot Clusters",
                "https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-usage-monitoring/": "Resource Usage Monitoring",
                # TLS
                "https://kubernetes.io/docs/tasks/tls/managing-tls-in-a-cluster/": "Manage TLS Certificates in a Cluster",
                # Manage Secrets
                "https://kubernetes.io/docs/tasks/configmap-secret/managing-secret-using-kubectl/": "Managing Secrets using kubectl",
                "https://kubernetes.io/docs/tasks/configmap-secret/managing-secret-using-config-file/": "Managing Secrets using Configuration File",
                # Administer Cluster
                "https://kubernetes.io/docs/tasks/administer-cluster/namespaces/": "Share a Cluster with Namespaces",
                "https://kubernetes.io/docs/tasks/administer-cluster/dns-debugging-resolution/": "Debugging DNS Resolution",
                "https://kubernetes.io/docs/tasks/administer-cluster/manage-resources/memory-default-namespace/": "Configure Default Memory Requests and Limits",
                "https://kubernetes.io/docs/tasks/administer-cluster/manage-resources/cpu-default-namespace/": "Configure Default CPU Requests and Limits",
                "https://kubernetes.io/docs/tasks/administer-cluster/manage-resources/quota-memory-cpu-namespace/": "Configure Memory and CPU Quotas for a Namespace",
            },
        },
        "reference": {
            "pages": {
                # kubectl
                "https://kubernetes.io/docs/reference/": "Reference Documentation",
                "https://kubernetes.io/docs/reference/kubectl/": "kubectl Reference",
                "https://kubernetes.io/docs/reference/kubectl/cheatsheet/": "kubectl Cheat Sheet",
                "https://kubernetes.io/docs/reference/kubectl/quick-reference/": "kubectl Quick Reference",
                # API
                "https://kubernetes.io/docs/reference/using-api/": "API Overview",
                "https://kubernetes.io/docs/reference/using-api/api-concepts/": "Kubernetes API Concepts",
                "https://kubernetes.io/docs/reference/using-api/client-libraries/": "Client Libraries",
                # Glossary and tools
                "https://kubernetes.io/docs/reference/glossary/": "Glossary",
                "https://kubernetes.io/docs/reference/setup-tools/kubeadm/": "kubeadm Reference",
                "https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-init/": "kubeadm init",
                "https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-join/": "kubeadm join",
                "https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-upgrade/": "kubeadm upgrade",
                "https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-reset/": "kubeadm reset",
                # Access authn/authz
                "https://kubernetes.io/docs/reference/access-authn-authz/rbac/": "Using RBAC Authorization",
                "https://kubernetes.io/docs/reference/access-authn-authz/authentication/": "Authenticating",
                "https://kubernetes.io/docs/reference/access-authn-authz/authorization/": "Authorization Overview",
                "https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/": "Admission Controllers Reference",
            },
        },
        "tutorials": {
            "pages": {
                "https://kubernetes.io/docs/tutorials/": "Tutorials Overview",
                # Basics
                "https://kubernetes.io/docs/tutorials/kubernetes-basics/": "Learn Kubernetes Basics",
                "https://kubernetes.io/docs/tutorials/kubernetes-basics/create-cluster/cluster-intro/": "Using Minikube to Create a Cluster",
                "https://kubernetes.io/docs/tutorials/kubernetes-basics/deploy-app/deploy-intro/": "Using kubectl to Create a Deployment",
                "https://kubernetes.io/docs/tutorials/kubernetes-basics/explore/explore-intro/": "Viewing Pods and Nodes",
                "https://kubernetes.io/docs/tutorials/kubernetes-basics/expose/expose-intro/": "Using a Service to Expose Your App",
                "https://kubernetes.io/docs/tutorials/kubernetes-basics/scale/scale-intro/": "Running Multiple Instances of Your App",
                "https://kubernetes.io/docs/tutorials/kubernetes-basics/update/update-intro/": "Performing a Rolling Update",
                # Stateless apps
                "https://kubernetes.io/docs/tutorials/stateless-application/guestbook/": "Deploying PHP Guestbook with Redis",
                "https://kubernetes.io/docs/tutorials/stateless-application/expose-external-ip-address/": "Exposing an External IP Address",
                # Stateful apps
                "https://kubernetes.io/docs/tutorials/stateful-application/": "Stateful Applications",
                "https://kubernetes.io/docs/tutorials/stateful-application/basic-stateful-set/": "StatefulSet Basics",
                "https://kubernetes.io/docs/tutorials/stateful-application/mysql-wordpress-persistent-volume/": "Deploying WordPress and MySQL with Persistent Volumes",
                "https://kubernetes.io/docs/tutorials/stateful-application/cassandra/": "Deploying Cassandra with a StatefulSet",
                "https://kubernetes.io/docs/tutorials/stateful-application/zookeeper/": "Running ZooKeeper",
                # Security
                "https://kubernetes.io/docs/tutorials/security/": "Security Tutorials",
                "https://kubernetes.io/docs/tutorials/security/cluster-level-pss/": "Apply Pod Security Standards at the Cluster Level",
                "https://kubernetes.io/docs/tutorials/security/ns-level-pss/": "Apply Pod Security Standards at the Namespace Level",
            },
        },
        "setup": {
            "pages": {
                "https://kubernetes.io/docs/setup/": "Getting Started",
                "https://kubernetes.io/docs/setup/production-environment/": "Production Environment",
                "https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/": "Bootstrapping Clusters with kubeadm",
                "https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/install-kubeadm/": "Installing kubeadm",
                "https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/": "Creating a Cluster with kubeadm",
                "https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/high-availability/": "Creating Highly Available Clusters with kubeadm",
                "https://kubernetes.io/docs/setup/production-environment/container-runtimes/": "Container Runtimes",
                "https://kubernetes.io/docs/setup/best-practices/": "Best Practices",
                "https://kubernetes.io/docs/setup/best-practices/cluster-large/": "Running in Large Clusters",
                "https://kubernetes.io/docs/setup/best-practices/certificates/": "PKI Certificates and Requirements",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"kubernetes-{source_key}" if source_key else "kubernetes"
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
            for suffix in [' | Kubernetes']:
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
                        "category": "kubernetes-docs",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.0)  # Rate limit

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
            self.log.info(f"=== Scraping kubernetes/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    KubernetesScraper(base, source_key).run()
