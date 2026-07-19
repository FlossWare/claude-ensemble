#!/usr/bin/env python3
"""Istio service mesh documentation scraper.

Covers:
  - Concepts: traffic management, security, observability, extensibility
  - Setup: installation methods, platform setup, upgrades
  - Tasks: traffic management, security, observability, extensibility tasks
  - Operations: deployment, configuration, best practices, diagnostics, integrations
  - Reference: networking, security, telemetry configs, commands
  - Examples: Bookinfo, Hello World, multicluster, VMs
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class IstioScraper(BaseScraper):
    """Scrape Istio official documentation."""

    SOURCES = {
        "concepts": {
            "pages": {
                "https://istio.io/latest/docs/concepts/what-is-istio/": "What Is Istio",
                "https://istio.io/latest/docs/concepts/traffic-management/": "Traffic Management",
                "https://istio.io/latest/docs/concepts/security/": "Security",
                "https://istio.io/latest/docs/concepts/observability/": "Observability",
                "https://istio.io/latest/docs/concepts/wasm/": "Extensibility with Wasm",
                "https://istio.io/latest/docs/overview/": "Overview",
                "https://istio.io/latest/about/service-mesh/": "What is a Service Mesh",
                "https://istio.io/latest/docs/overview/what-is-istio/": "What is Istio Overview",
                "https://istio.io/latest/about/faq/": "FAQ",
                "https://istio.io/latest/docs/ambient/overview/": "Ambient Mesh Overview",
                "https://istio.io/latest/about/faq/distributed-tracing/": "FAQ Distributed Tracing",
                "https://istio.io/latest/about/faq/metrics-and-logs/": "FAQ Metrics and Logs",
                "https://istio.io/latest/about/faq/security/": "FAQ Security",
                "https://istio.io/latest/about/faq/setup/": "FAQ Setup",
                "https://istio.io/latest/about/faq/traffic-management/": "FAQ Traffic Management",
            },
        },
        "setup": {
            "pages": {
                # Core Setup
                "https://istio.io/latest/docs/setup/": "Setup",
                "https://istio.io/latest/docs/setup/getting-started/": "Getting Started",
                # Install Methods
                "https://istio.io/latest/docs/setup/install/": "Install",
                "https://istio.io/latest/docs/setup/install/istioctl/": "Install with istioctl",
                "https://istio.io/latest/docs/setup/install/helm/": "Install with Helm",
                "https://istio.io/latest/docs/setup/install/operator/": "Install with Operator",
                # Multi-cluster
                "https://istio.io/latest/docs/setup/install/multicluster/": "Multi-Cluster Install",
                "https://istio.io/latest/docs/setup/install/multicluster/primary-remote/": "Primary-Remote",
                "https://istio.io/latest/docs/setup/install/multicluster/multi-primary/": "Multi-Primary",
                "https://istio.io/latest/docs/setup/install/multicluster/primary-remote_multi-network/": "Primary-Remote Multi-Network",
                "https://istio.io/latest/docs/setup/install/multicluster/multi-primary_multi-network/": "Multi-Primary Multi-Network",
                "https://istio.io/latest/docs/setup/install/multicluster/verify/": "Verify Multicluster",
                # External & VM
                "https://istio.io/latest/docs/setup/install/external-controlplane/": "External Control Plane",
                "https://istio.io/latest/docs/setup/install/virtual-machine/": "Virtual Machine Install",
                # Platform Setup
                "https://istio.io/latest/docs/setup/platform-setup/": "Platform Setup",
                "https://istio.io/latest/docs/setup/platform-setup/gke/": "GKE Setup",
                "https://istio.io/latest/docs/setup/platform-setup/eks/": "EKS Setup",
                "https://istio.io/latest/docs/setup/platform-setup/aks/": "AKS Setup",
                "https://istio.io/latest/docs/setup/platform-setup/minikube/": "Minikube Setup",
                "https://istio.io/latest/docs/setup/platform-setup/kind/": "Kind Setup",
                "https://istio.io/latest/docs/setup/platform-setup/openshift/": "OpenShift Setup",
                "https://istio.io/latest/docs/setup/platform-setup/docker-desktop/": "Docker Desktop Setup",
                "https://istio.io/latest/docs/setup/platform-setup/k3d/": "K3d Setup",
                "https://istio.io/latest/docs/setup/platform-setup/microk8s/": "MicroK8s Setup",
                "https://istio.io/latest/docs/setup/platform-setup/gardener/": "Gardener Setup",
                # Additional Setup
                "https://istio.io/latest/docs/setup/additional-setup/": "Additional Setup",
                "https://istio.io/latest/docs/setup/additional-setup/config-profiles/": "Config Profiles",
                "https://istio.io/latest/docs/setup/additional-setup/customize-installation/": "Customize Installation",
                "https://istio.io/latest/docs/setup/additional-setup/gateway/": "Gateway Setup",
                "https://istio.io/latest/docs/setup/additional-setup/sidecar-injection/": "Sidecar Injection",
                "https://istio.io/latest/docs/setup/additional-setup/cni/": "Istio CNI",
                "https://istio.io/latest/docs/setup/additional-setup/dual-stack/": "Dual Stack",
                "https://istio.io/latest/docs/setup/additional-setup/external-controlplane/": "External Control Plane Setup",
                # Upgrade
                "https://istio.io/latest/docs/setup/upgrade/": "Upgrade",
                "https://istio.io/latest/docs/setup/upgrade/canary/": "Canary Upgrade",
                "https://istio.io/latest/docs/setup/upgrade/in-place/": "In-Place Upgrade",
                "https://istio.io/latest/docs/setup/upgrade/helm/": "Helm Upgrade",
                "https://istio.io/latest/docs/setup/additional-setup/download-istio-release/": "Download Istio Release",
                "https://istio.io/latest/docs/setup/additional-setup/pod-security-admission/": "Pod Security Admission",
                "https://istio.io/latest/docs/setup/platform-setup/rancher/": "Rancher Setup",
                "https://istio.io/latest/docs/setup/platform-setup/ibm/": "IBM Cloud Setup",
                "https://istio.io/latest/docs/setup/platform-setup/oci/": "Oracle Cloud Setup",
                "https://istio.io/latest/docs/setup/platform-setup/azure/": "Azure Setup",
                "https://istio.io/latest/docs/setup/platform-setup/huawei/": "Huawei Cloud Setup",
                "https://istio.io/latest/docs/setup/install/multicluster/before-you-begin/": "Multicluster Before You Begin",
                "https://istio.io/latest/docs/setup/additional-setup/external-controlplane/": "Additional External Control Plane",
                "https://istio.io/latest/docs/setup/upgrade/gateways/": "Gateway Upgrade",
            },
        },
        "tasks": {
            "pages": {
                # Overview
                "https://istio.io/latest/docs/tasks/": "Tasks Overview",
                # Traffic Management
                "https://istio.io/latest/docs/tasks/traffic-management/": "Traffic Management Tasks",
                "https://istio.io/latest/docs/tasks/traffic-management/request-routing/": "Request Routing",
                "https://istio.io/latest/docs/tasks/traffic-management/fault-injection/": "Fault Injection",
                "https://istio.io/latest/docs/tasks/traffic-management/traffic-shifting/": "Traffic Shifting",
                "https://istio.io/latest/docs/tasks/traffic-management/tcp-traffic-shifting/": "TCP Traffic Shifting",
                "https://istio.io/latest/docs/tasks/traffic-management/request-timeouts/": "Request Timeouts",
                "https://istio.io/latest/docs/tasks/traffic-management/circuit-breaking/": "Circuit Breaking",
                "https://istio.io/latest/docs/tasks/traffic-management/mirroring/": "Traffic Mirroring",
                # Ingress
                "https://istio.io/latest/docs/tasks/traffic-management/ingress/": "Ingress",
                "https://istio.io/latest/docs/tasks/traffic-management/ingress/ingress-control/": "Ingress Control",
                "https://istio.io/latest/docs/tasks/traffic-management/ingress/secure-ingress/": "Secure Ingress",
                "https://istio.io/latest/docs/tasks/traffic-management/ingress/kubernetes-ingress/": "Kubernetes Ingress",
                "https://istio.io/latest/docs/tasks/traffic-management/ingress/ingress-sni-passthrough/": "SNI Passthrough",
                # Egress
                "https://istio.io/latest/docs/tasks/traffic-management/egress/": "Egress",
                "https://istio.io/latest/docs/tasks/traffic-management/egress/egress-control/": "Egress Control",
                "https://istio.io/latest/docs/tasks/traffic-management/egress/egress-gateway/": "Egress Gateway",
                "https://istio.io/latest/docs/tasks/traffic-management/egress/egress-gateway-tls-origination/": "Egress TLS Origination",
                "https://istio.io/latest/docs/tasks/traffic-management/egress/egress-tls-origination/": "TLS Origination for Egress",
                "https://istio.io/latest/docs/tasks/traffic-management/egress/wildcard-egress-hosts/": "Wildcard Egress Hosts",
                # Locality
                "https://istio.io/latest/docs/tasks/traffic-management/locality-load-balancing/": "Locality Load Balancing",
                "https://istio.io/latest/docs/tasks/traffic-management/locality-load-balancing/failover/": "Locality Failover",
                "https://istio.io/latest/docs/tasks/traffic-management/locality-load-balancing/distribute/": "Locality Distribution",
                # Security
                "https://istio.io/latest/docs/tasks/security/": "Security Tasks",
                "https://istio.io/latest/docs/tasks/security/authentication/": "Authentication",
                "https://istio.io/latest/docs/tasks/security/authentication/authn-policy/": "Authentication Policy",
                "https://istio.io/latest/docs/tasks/security/authentication/mtls-migration/": "mTLS Migration",
                "https://istio.io/latest/docs/tasks/security/authorization/": "Authorization",
                "https://istio.io/latest/docs/tasks/security/authorization/authz-http-traffic/": "HTTP Authorization",
                "https://istio.io/latest/docs/tasks/security/authorization/authz-tcp-traffic/": "TCP Authorization",
                "https://istio.io/latest/docs/tasks/security/authorization/authz-deny/": "Deny Authorization",
                "https://istio.io/latest/docs/tasks/security/authorization/authz-jwt/": "JWT Authorization",
                "https://istio.io/latest/docs/tasks/security/authorization/authz-custom/": "Custom Authorization",
                "https://istio.io/latest/docs/tasks/security/authorization/authz-ingress/": "Ingress Authorization",
                "https://istio.io/latest/docs/tasks/security/authorization/authz-td-migration/": "Trust Domain Migration",
                "https://istio.io/latest/docs/tasks/security/cert-management/": "Certificate Management",
                "https://istio.io/latest/docs/tasks/security/cert-management/plugin-ca-cert/": "Plugin CA Certs",
                "https://istio.io/latest/docs/tasks/security/cert-management/dns-cert/": "DNS Certificate Management",
                # Observability
                "https://istio.io/latest/docs/tasks/observability/": "Observability Tasks",
                "https://istio.io/latest/docs/tasks/observability/metrics/": "Metrics",
                "https://istio.io/latest/docs/tasks/observability/metrics/querying-metrics/": "Querying Metrics",
                "https://istio.io/latest/docs/tasks/observability/metrics/customize-metrics/": "Customize Metrics",
                "https://istio.io/latest/docs/tasks/observability/metrics/using-istio-dashboard/": "Using Istio Dashboard",
                "https://istio.io/latest/docs/tasks/observability/metrics/classify-metrics/": "Classify Metrics",
                "https://istio.io/latest/docs/tasks/observability/distributed-tracing/": "Distributed Tracing",
                "https://istio.io/latest/docs/tasks/observability/distributed-tracing/overview/": "Tracing Overview",
                "https://istio.io/latest/docs/tasks/observability/distributed-tracing/jaeger/": "Jaeger",
                "https://istio.io/latest/docs/tasks/observability/distributed-tracing/zipkin/": "Zipkin",
                "https://istio.io/latest/docs/tasks/observability/distributed-tracing/lightstep/": "Lightstep",
                "https://istio.io/latest/docs/tasks/observability/distributed-tracing/opentelemetry/": "OpenTelemetry",
                "https://istio.io/latest/docs/tasks/observability/distributed-tracing/configurability/": "Tracing Configurability",
                "https://istio.io/latest/docs/tasks/observability/logs/": "Access Logging",
                "https://istio.io/latest/docs/tasks/observability/logs/access-log/": "Access Log",
                "https://istio.io/latest/docs/tasks/observability/logs/otel-provider/": "OpenTelemetry Log Provider",
                "https://istio.io/latest/docs/tasks/observability/kiali/": "Kiali",
                "https://istio.io/latest/docs/tasks/observability/gateways/": "Gateway Observability",
                # Extensibility
                "https://istio.io/latest/docs/tasks/extensibility/": "Extensibility",
                "https://istio.io/latest/docs/tasks/extensibility/wasm-module-distribution/": "Wasm Module Distribution",
                # Multi-cluster
                "https://istio.io/latest/docs/tasks/multicluster/": "Multi-Cluster Tasks",
                "https://istio.io/latest/docs/tasks/multicluster/verify/": "Verify Multi-Cluster",
                # Additional Traffic Management
                "https://istio.io/latest/docs/tasks/traffic-management/ingress/ingress-certmgr/": "Ingress with Cert-Manager",
                "https://istio.io/latest/docs/tasks/traffic-management/egress/egress-kubernetes-services/": "Egress to Kubernetes Services",
                "https://istio.io/latest/docs/tasks/traffic-management/locality-load-balancing/before-you-begin/": "Locality Before You Begin",
                # Additional Security
                "https://istio.io/latest/docs/tasks/security/cert-management/custom-ca-k8s/": "Custom CA with Kubernetes",
                "https://istio.io/latest/docs/tasks/security/authentication/claim-to-header/": "Claim to Header",
                "https://istio.io/latest/docs/tasks/security/authorization/authz-dry-run/": "Authorization Dry Run",
                # Additional Observability
                "https://istio.io/latest/docs/tasks/observability/metrics/tcp-metrics/": "TCP Metrics",
                "https://istio.io/latest/docs/tasks/observability/distributed-tracing/mesh-and-proxy-config/": "Mesh and Proxy Tracing Config",
                # Additional Tasks
                "https://istio.io/latest/docs/tasks/traffic-management/egress/http-proxy/": "Egress via HTTP Proxy",
                "https://istio.io/latest/docs/tasks/traffic-management/ingress/gateway-api/": "Gateway API Ingress",
                "https://istio.io/latest/docs/tasks/security/tls-configuration/workload-min-tls-version/": "Workload Min TLS Version",
                "https://istio.io/latest/docs/tasks/security/authorization/authz-td-migration/": "Trust Domain Migration",
                "https://istio.io/latest/docs/tasks/observability/logs/telemetry-api/": "Telemetry API Logging",
                "https://istio.io/latest/docs/tasks/traffic-management/tcp-traffic-shifting/": "TCP Traffic Shifting Detail",
            },
        },
        "ops": {
            "pages": {
                # Overview
                "https://istio.io/latest/docs/ops/": "Operations",
                # Deployment
                "https://istio.io/latest/docs/ops/deployment/": "Deployment Models",
                "https://istio.io/latest/docs/ops/deployment/deployment-models/": "Deployment Models Detail",
                "https://istio.io/latest/docs/ops/deployment/architecture/": "Architecture",
                "https://istio.io/latest/docs/ops/deployment/requirements/": "Requirements",
                "https://istio.io/latest/docs/ops/deployment/performance-and-scalability/": "Performance and Scalability",
                # Configuration - Traffic
                "https://istio.io/latest/docs/ops/configuration/": "Configuration",
                "https://istio.io/latest/docs/ops/configuration/traffic-management/": "Traffic Management Config",
                "https://istio.io/latest/docs/ops/configuration/traffic-management/network-topologies/": "Network Topologies",
                "https://istio.io/latest/docs/ops/configuration/traffic-management/dns-proxy/": "DNS Proxy",
                "https://istio.io/latest/docs/ops/configuration/traffic-management/protocol-selection/": "Protocol Selection",
                "https://istio.io/latest/docs/ops/configuration/traffic-management/multicluster/": "Multicluster Traffic Config",
                "https://istio.io/latest/docs/ops/configuration/traffic-management/locality-load-balancing/": "Locality Load Balancing Config",
                # Configuration - Mesh
                "https://istio.io/latest/docs/ops/configuration/mesh/": "Mesh Configuration",
                "https://istio.io/latest/docs/ops/configuration/mesh/app-health-check/": "App Health Check",
                "https://istio.io/latest/docs/ops/configuration/mesh/injection-concepts/": "Injection Concepts",
                "https://istio.io/latest/docs/ops/configuration/mesh/secret-creation/": "Secret Creation",
                "https://istio.io/latest/docs/ops/configuration/mesh/webhook/": "Webhook Configuration",
                # Configuration - Security & Other
                "https://istio.io/latest/docs/ops/configuration/security/": "Security Configuration",
                "https://istio.io/latest/docs/ops/configuration/security/root-transition/": "Root CA Transition",
                "https://istio.io/latest/docs/ops/configuration/security/harden-docker-images/": "Harden Docker Images",
                "https://istio.io/latest/docs/ops/configuration/extensibility/": "Extensibility Configuration",
                "https://istio.io/latest/docs/ops/configuration/extensibility/wasm-pull-policy/": "Wasm Pull Policy",
                "https://istio.io/latest/docs/ops/configuration/telemetry/": "Telemetry Configuration",
                "https://istio.io/latest/docs/ops/configuration/telemetry/envoy-stats/": "Envoy Stats",
                # Best Practices
                "https://istio.io/latest/docs/ops/best-practices/": "Best Practices",
                "https://istio.io/latest/docs/ops/best-practices/traffic-management/": "Traffic Management Best Practices",
                "https://istio.io/latest/docs/ops/best-practices/security/": "Security Best Practices",
                "https://istio.io/latest/docs/ops/best-practices/observability/": "Observability Best Practices",
                "https://istio.io/latest/docs/ops/best-practices/deployment/": "Deployment Best Practices",
                # Diagnostic Tools
                "https://istio.io/latest/docs/ops/diagnostic-tools/": "Diagnostic Tools",
                "https://istio.io/latest/docs/ops/diagnostic-tools/istioctl/": "istioctl",
                "https://istio.io/latest/docs/ops/diagnostic-tools/istioctl-analyze/": "istioctl analyze",
                "https://istio.io/latest/docs/ops/diagnostic-tools/istioctl-describe/": "istioctl describe",
                "https://istio.io/latest/docs/ops/diagnostic-tools/proxy-cmd/": "Proxy Commands",
                "https://istio.io/latest/docs/ops/diagnostic-tools/controlz/": "ControlZ",
                "https://istio.io/latest/docs/ops/diagnostic-tools/component-logging/": "Component Logging",
                "https://istio.io/latest/docs/ops/diagnostic-tools/virtual-machines/": "VM Diagnostics",
                # Common Problems
                "https://istio.io/latest/docs/ops/common-problems/": "Common Problems",
                "https://istio.io/latest/docs/ops/common-problems/network-issues/": "Network Issues",
                "https://istio.io/latest/docs/ops/common-problems/security-issues/": "Security Issues",
                "https://istio.io/latest/docs/ops/common-problems/observability-issues/": "Observability Issues",
                "https://istio.io/latest/docs/ops/common-problems/injection/": "Injection Issues",
                "https://istio.io/latest/docs/ops/common-problems/validation/": "Validation Issues",
                "https://istio.io/latest/docs/ops/common-problems/upgrades/": "Upgrade Issues",
                # Integrations
                "https://istio.io/latest/docs/ops/integrations/": "Integrations",
                "https://istio.io/latest/docs/ops/integrations/prometheus/": "Prometheus Integration",
                "https://istio.io/latest/docs/ops/integrations/grafana/": "Grafana Integration",
                "https://istio.io/latest/docs/ops/integrations/jaeger/": "Jaeger Integration",
                "https://istio.io/latest/docs/ops/integrations/kiali/": "Kiali Integration",
                "https://istio.io/latest/docs/ops/integrations/zipkin/": "Zipkin Integration",
                "https://istio.io/latest/docs/ops/integrations/certmanager/": "Cert-Manager Integration",
                "https://istio.io/latest/docs/ops/integrations/spire/": "SPIRE Integration",
                "https://istio.io/latest/docs/ops/integrations/skywalking/": "SkyWalking Integration",
                # Additional Operations
                "https://istio.io/latest/docs/ops/common-problems/config/": "Config Issues",
                "https://istio.io/latest/docs/ops/diagnostic-tools/check-inject/": "Check Inject",
                "https://istio.io/latest/docs/ops/ambient/": "Ambient Operations",
                "https://istio.io/latest/docs/ops/ambient/troubleshoot/": "Ambient Troubleshooting",
                "https://istio.io/latest/docs/ops/ambient/upgrade/": "Ambient Operations Upgrade",
                "https://istio.io/latest/docs/ops/configuration/traffic-management/tls-configuration/": "TLS Configuration",
                "https://istio.io/latest/docs/ops/faq/": "Operations FAQ",
                "https://istio.io/latest/docs/ops/integrations/application-protocols/": "Application Protocols",
                "https://istio.io/latest/docs/ops/configuration/mesh/config-resource-ready/": "Config Resource Ready",
                "https://istio.io/latest/docs/ops/configuration/traffic-management/request-classification/": "Request Classification",
                "https://istio.io/latest/docs/ops/best-practices/ambient/": "Ambient Best Practices",
                "https://istio.io/latest/docs/ops/diagnostic-tools/multicluster/": "Multicluster Diagnostics",
                "https://istio.io/latest/docs/ops/common-problems/health-check/": "Health Check Problems",
                "https://istio.io/latest/docs/ops/integrations/datadog/": "Datadog Integration",
            },
        },
        "reference": {
            "pages": {
                # Overview
                "https://istio.io/latest/docs/reference/": "Reference",
                "https://istio.io/latest/docs/reference/config/": "Configuration Reference",
                # Networking
                "https://istio.io/latest/docs/reference/config/networking/": "Networking Config",
                "https://istio.io/latest/docs/reference/config/networking/virtual-service/": "VirtualService",
                "https://istio.io/latest/docs/reference/config/networking/destination-rule/": "DestinationRule",
                "https://istio.io/latest/docs/reference/config/networking/gateway/": "Gateway",
                "https://istio.io/latest/docs/reference/config/networking/service-entry/": "ServiceEntry",
                "https://istio.io/latest/docs/reference/config/networking/sidecar/": "Sidecar",
                "https://istio.io/latest/docs/reference/config/networking/envoy-filter/": "EnvoyFilter",
                "https://istio.io/latest/docs/reference/config/networking/workload-entry/": "WorkloadEntry",
                "https://istio.io/latest/docs/reference/config/networking/workload-group/": "WorkloadGroup",
                "https://istio.io/latest/docs/reference/config/networking/proxy-config/": "ProxyConfig",
                # Security
                "https://istio.io/latest/docs/reference/config/security/": "Security Config",
                "https://istio.io/latest/docs/reference/config/security/authorization-policy/": "AuthorizationPolicy",
                "https://istio.io/latest/docs/reference/config/security/peer_authentication/": "PeerAuthentication",
                "https://istio.io/latest/docs/reference/config/security/request_authentication/": "RequestAuthentication",
                # Telemetry & Mesh
                "https://istio.io/latest/docs/reference/config/telemetry/": "Telemetry Config",
                "https://istio.io/latest/docs/reference/config/istio.mesh.v1alpha1/": "MeshConfig",
                "https://istio.io/latest/docs/reference/config/istio.operator.v1alpha1/": "IstioOperator",
                "https://istio.io/latest/docs/reference/config/analysis/": "Analysis Messages",
                "https://istio.io/latest/docs/reference/config/labels/": "Resource Labels",
                "https://istio.io/latest/docs/reference/config/annotations/": "Resource Annotations",
                "https://istio.io/latest/docs/reference/config/metrics/": "Standard Metrics",
                "https://istio.io/latest/docs/reference/config/type/object-meta/": "ObjectMeta",
                # Commands
                "https://istio.io/latest/docs/reference/commands/": "Commands Reference",
                "https://istio.io/latest/docs/reference/commands/istioctl/": "istioctl Reference",
                "https://istio.io/latest/docs/reference/commands/pilot-agent/": "pilot-agent",
                "https://istio.io/latest/docs/reference/commands/pilot-discovery/": "pilot-discovery",
                "https://istio.io/latest/docs/reference/commands/install-cni/": "install-cni",
                "https://istio.io/latest/docs/reference/commands/operator/": "operator",
                "https://istio.io/latest/docs/reference/commands/istio_ca/": "istio_ca",
                # Glossary
                "https://istio.io/latest/docs/reference/glossary/": "Glossary",
                # Additional Reference
                "https://istio.io/latest/docs/reference/config/networking/network/": "Network",
                "https://istio.io/latest/docs/reference/config/type/workload-selector/": "WorkloadSelector",
                "https://istio.io/latest/docs/reference/config/istio.networking.v1alpha3/": "Networking v1alpha3",
                "https://istio.io/latest/docs/reference/config/istio.networking.v1beta1/": "Networking v1beta1",
                "https://istio.io/latest/docs/reference/config/istio.security.v1beta1/": "Security v1beta1",
                "https://istio.io/latest/docs/reference/config/proxy_extensions/": "Proxy Extensions",
                "https://istio.io/latest/docs/reference/config/istio.extensions.v1alpha1/": "Extensions v1alpha1",
                "https://istio.io/latest/docs/reference/config/type/workload-selector/": "WorkloadSelector Reference",
                "https://istio.io/latest/docs/reference/config/analysis/ist0001/": "IST0001 Analysis Message",
                "https://istio.io/latest/docs/reference/config/analysis/ist0002/": "IST0002 Analysis Message",
                "https://istio.io/latest/docs/reference/config/analysis/ist0101/": "IST0101 Analysis Message",
                "https://istio.io/latest/docs/reference/config/analysis/ist0102/": "IST0102 Analysis Message",
                "https://istio.io/latest/docs/reference/config/analysis/ist0103/": "IST0103 Analysis Message",
                "https://istio.io/latest/docs/reference/commands/bug-report/": "bug-report",
                "https://istio.io/latest/docs/reference/commands/ztunnel/": "ztunnel",
            },
        },
        "examples": {
            "pages": {
                # Core Examples
                "https://istio.io/latest/docs/examples/": "Examples",
                "https://istio.io/latest/docs/examples/bookinfo/": "Bookinfo Application",
                "https://istio.io/latest/docs/examples/helloworld/": "Hello World",
                # Microservices Tutorial
                "https://istio.io/latest/docs/examples/microservices-istio/": "Microservices with Istio",
                "https://istio.io/latest/docs/examples/microservices-istio/setup-kubernetes-cluster/": "Setup Kubernetes Cluster",
                "https://istio.io/latest/docs/examples/microservices-istio/add-istio/": "Add Istio to Application",
                "https://istio.io/latest/docs/examples/microservices-istio/istio-ingress-gateway/": "Istio Ingress Gateway",
                "https://istio.io/latest/docs/examples/microservices-istio/add-new-microservice-version/": "Add New Microservice Version",
                "https://istio.io/latest/docs/examples/microservices-istio/production-testing/": "Production Testing",
                "https://istio.io/latest/docs/examples/microservices-istio/logs-istio/": "Logs with Istio",
                # Multi-cluster & VM
                "https://istio.io/latest/docs/examples/multicluster/": "Multicluster Examples",
                "https://istio.io/latest/docs/examples/virtual-machines/": "Virtual Machine Examples",
                "https://istio.io/latest/docs/examples/multicluster/gateways/": "Multicluster with Gateways",
                "https://istio.io/latest/docs/examples/microservices-istio/enable-istio-all-microservices/": "Enable Istio All Microservices",
                "https://istio.io/latest/docs/examples/microservices-istio/package-service/": "Package Service",
            },
        },
        "ambient": {
            "pages": {
                "https://istio.io/latest/docs/ambient/": "Ambient Mesh",
                "https://istio.io/latest/docs/ambient/overview/": "Ambient Overview",
                "https://istio.io/latest/docs/ambient/getting-started/": "Ambient Getting Started",
                "https://istio.io/latest/docs/ambient/install/": "Ambient Install",
                "https://istio.io/latest/docs/ambient/install/helm-installation/": "Ambient Helm Install",
                "https://istio.io/latest/docs/ambient/install/istioctl/": "Ambient istioctl Install",
                "https://istio.io/latest/docs/ambient/install/platform-prerequisites/": "Ambient Platform Prerequisites",
                "https://istio.io/latest/docs/ambient/usage/": "Ambient Usage",
                "https://istio.io/latest/docs/ambient/usage/add-workloads/": "Add Workloads to Ambient",
                "https://istio.io/latest/docs/ambient/usage/l7-features/": "L7 Features",
                "https://istio.io/latest/docs/ambient/usage/waypoint/": "Waypoint Proxy",
                "https://istio.io/latest/docs/ambient/usage/troubleshoot-ztunnel/": "Troubleshoot ztunnel",
                "https://istio.io/latest/docs/ambient/architecture/": "Ambient Architecture",
                "https://istio.io/latest/docs/ambient/architecture/control-plane/": "Ambient Control Plane",
                "https://istio.io/latest/docs/ambient/architecture/data-plane/": "Ambient Data Plane",
                "https://istio.io/latest/docs/ambient/upgrade/": "Ambient Upgrade",
                "https://istio.io/latest/docs/ambient/upgrade/helm-upgrade/": "Ambient Helm Upgrade",
                "https://istio.io/latest/docs/ambient/usage/extend-waypoint-wasm/": "Extend Waypoint with Wasm",
                "https://istio.io/latest/docs/ambient/usage/l4-policy/": "L4 Authorization Policy",
                "https://istio.io/latest/docs/ambient/usage/traffic-management/": "Ambient Traffic Management",
                "https://istio.io/latest/docs/ambient/usage/observability/": "Ambient Observability",
            },
        },
        "releases": {
            "pages": {
                "https://istio.io/latest/news/": "Istio News",
                "https://istio.io/latest/news/releases/": "Releases",
                "https://istio.io/latest/news/security/": "Security Bulletins",
                "https://istio.io/latest/docs/releases/": "Release Documentation",
                "https://istio.io/latest/docs/releases/supported-releases/": "Supported Releases",
                "https://istio.io/latest/docs/releases/bugs/": "Reporting Bugs",
                "https://istio.io/latest/docs/releases/feature-stages/": "Feature Stages",
                "https://istio.io/latest/about/community/": "Community",
                "https://istio.io/latest/get-involved/": "Get Involved",
                "https://istio.io/latest/blog/": "Istio Blog",
                "https://istio.io/latest/about/ecosystem/": "Ecosystem",
                "https://istio.io/latest/about/case-studies/": "Case Studies",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"istio-{source_key}" if source_key else "istio"
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
            for suffix in [' - Istio', ' | Istio']:
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
                        "category": f"istio-{source_key}",
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
            self.log.info(f"=== Scraping istio/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    IstioScraper(base, source_key).run()
