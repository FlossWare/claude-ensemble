#!/usr/bin/env python3
"""Grafana documentation scraper.

Covers:
  - Grafana dashboards, panels, visualizations
  - Alerting, data sources, administration
  - Setup, installation, configuration
  - Variables, transformations, annotations
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class GrafanaScraper(BaseScraper):
    """Scrape Grafana documentation across all sections."""

    SOURCES = {
        "getting-started": {
            "pages": {
                "https://grafana.com/docs/grafana/latest/getting-started/": "Grafana Getting Started",
                "https://grafana.com/docs/grafana/latest/getting-started/build-first-dashboard/": "Build Your First Dashboard",
                "https://grafana.com/docs/grafana/latest/getting-started/getting-started-prometheus/": "Getting Started with Prometheus",
                "https://grafana.com/docs/grafana/latest/getting-started/getting-started-influxdb/": "Getting Started with InfluxDB",
                "https://grafana.com/docs/grafana/latest/getting-started/getting-started-sql/": "Getting Started with SQL",
                "https://grafana.com/docs/grafana/latest/getting-started/what-is-grafana/": "What Is Grafana",
                "https://grafana.com/docs/grafana/latest/introduction/": "Introduction to Grafana",
                "https://grafana.com/docs/grafana/latest/fundamentals/": "Grafana Fundamentals",
                "https://grafana.com/docs/grafana/latest/fundamentals/timeseries/": "Time Series Basics",
                "https://grafana.com/docs/grafana/latest/fundamentals/exemplars/": "Exemplars",
                "https://grafana.com/docs/grafana/latest/fundamentals/annotation-label/": "Annotations and Labels",
                "https://grafana.com/docs/grafana/latest/whatsnew/": "What's New in Grafana",
                "https://grafana.com/docs/grafana/latest/getting-started/strategies/": "Strategies",
                "https://grafana.com/docs/grafana/latest/getting-started/roles/": "Roles and Getting Started",
                "https://grafana.com/docs/grafana/latest/fundamentals/data-source-basics/": "Data Source Basics",
                "https://grafana.com/docs/grafana/latest/fundamentals/dashboards-overview/": "Dashboards Overview Fundamentals",
                "https://grafana.com/docs/grafana/latest/fundamentals/explore-metrics/": "Explore Metrics",
                "https://grafana.com/docs/grafana/latest/fundamentals/intro-histograms/": "Intro to Histograms",
                "https://grafana.com/docs/grafana/latest/getting-started/getting-started-kubernetes/": "Getting Started with Kubernetes",
                "https://grafana.com/docs/grafana/latest/getting-started/get-started-grafana-ms-sql-server/": "Getting Started with MS SQL",
            },
        },
        "dashboards": {
            "pages": {
                "https://grafana.com/docs/grafana/latest/dashboards/": "Dashboards Overview",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/": "Build Dashboards",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/create-dashboard/": "Create a Dashboard",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/manage-dashboard-links/": "Dashboard Links",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/manage-library-panels/": "Library Panels",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/import-dashboards/": "Import Dashboards",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/": "Dashboard Best Practices",
                "https://grafana.com/docs/grafana/latest/dashboards/manage-dashboards/": "Manage Dashboards",
                "https://grafana.com/docs/grafana/latest/dashboards/export-import/": "Export Import Dashboards",
                "https://grafana.com/docs/grafana/latest/dashboards/json-model/": "Dashboard JSON Model",
                "https://grafana.com/docs/grafana/latest/dashboards/playlist/": "Playlists",
                "https://grafana.com/docs/grafana/latest/dashboards/search/": "Dashboard Search",
                "https://grafana.com/docs/grafana/latest/dashboards/share-dashboards-panels/": "Share Dashboards",
                "https://grafana.com/docs/grafana/latest/dashboards/assess-dashboard-usage/": "Dashboard Usage",
                "https://grafana.com/docs/grafana/latest/dashboards/create-reports/": "Dashboard Reports",
                "https://grafana.com/docs/grafana/latest/dashboards/dashboard-public/": "Public Dashboards",
                "https://grafana.com/docs/grafana/latest/dashboards/use-dashboards/": "Use Dashboards",
                "https://grafana.com/docs/grafana/latest/dashboards/variables/": "Dashboard Variables",
                "https://grafana.com/docs/grafana/latest/dashboards/variables/add-template-variables/": "Template Variables",
                "https://grafana.com/docs/grafana/latest/dashboards/variables/variable-syntax/": "Variable Syntax",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/view-dashboard-json-model/": "View Dashboard JSON",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/modify-dashboard-settings/": "Modify Dashboard Settings",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/create-dashboard-url-variables/": "Dashboard URL Variables",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/add-organize-panels/": "Add and Organize Panels",
                "https://grafana.com/docs/grafana/latest/dashboards/manage-dashboards/dashboard-folders/": "Dashboard Folders",
                "https://grafana.com/docs/grafana/latest/dashboards/manage-dashboards/dashboard-permissions/": "Dashboard Permissions",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/annotate-visualizations/": "Annotate Visualizations",
                "https://grafana.com/docs/grafana/latest/dashboards/share-dashboards-panels/share-a-panel/": "Share a Panel",
                "https://grafana.com/docs/grafana/latest/dashboards/share-dashboards-panels/share-a-dashboard/": "Share a Dashboard",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/create-dashboard-scene/": "Create Dashboard Scene",
            },
        },
        "panels-visualizations": {
            "pages": {
                "https://grafana.com/docs/grafana/latest/panels-visualizations/": "Panels and Visualizations",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/configure-panel-options/": "Panel Options",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/configure-data-links/": "Data Links",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/configure-overrides/": "Overrides",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/configure-thresholds/": "Thresholds",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/configure-value-mappings/": "Value Mappings",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/": "Visualizations",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/time-series/": "Time Series Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/bar-chart/": "Bar Chart Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/bar-gauge/": "Bar Gauge Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/candlestick/": "Candlestick Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/canvas/": "Canvas Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/gauge/": "Gauge Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/geomap/": "Geomap Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/heatmap/": "Heatmap Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/histogram/": "Histogram Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/logs/": "Logs Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/news/": "News Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/node-graph/": "Node Graph Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/pie-chart/": "Pie Chart Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/stat/": "Stat Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/state-timeline/": "State Timeline Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/status-history/": "Status History Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/table/": "Table Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/text/": "Text Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/traces/": "Traces Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/trend/": "Trend Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/xy-chart/": "XY Chart Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/": "Query and Transform Data",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/": "Transform Data",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/alert-list/": "Alert List Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/dashboard-list/": "Dashboard List Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/flame-graph/": "Flame Graph Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/datagrid/": "Datagrid Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/configure-standard-options/": "Standard Options",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/configure-legend/": "Configure Legend",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/configure-tooltips/": "Configure Tooltips",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/panel-inspector/": "Panel Inspector",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/expression-queries/": "Expression Queries",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/navigate-query-tab/": "Navigate Query Tab",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/annotationlist/": "Annotation List Panel",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/configure-field-values/": "Configure Field Values",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/share-query/": "Share Query Results",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/mixed-datasources/": "Mixed Data Sources",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/logs/logs-navigation/": "Logs Navigation",
            },
        },
        "explore": {
            "pages": {
                "https://grafana.com/docs/grafana/latest/explore/": "Explore",
                "https://grafana.com/docs/grafana/latest/explore/query-management/": "Query Management",
                "https://grafana.com/docs/grafana/latest/explore/logs-integration/": "Logs in Explore",
                "https://grafana.com/docs/grafana/latest/explore/trace-integration/": "Traces in Explore",
                "https://grafana.com/docs/grafana/latest/explore/query-inspector/": "Query Inspector",
                "https://grafana.com/docs/grafana/latest/explore/explore-inspector/": "Explore Inspector",
                "https://grafana.com/docs/grafana/latest/explore/correlations-editor-in-explore/": "Correlations in Explore",
                "https://grafana.com/docs/grafana/latest/explore/simplified-exploration/": "Simplified Exploration",
                "https://grafana.com/docs/grafana/latest/explore/explore-metrics/": "Explore Metrics",
                "https://grafana.com/docs/grafana/latest/explore/explore-logs/": "Explore Logs",
                "https://grafana.com/docs/grafana/latest/explore/explore-traces/": "Explore Traces",
                "https://grafana.com/docs/grafana/latest/explore/explore-profiles/": "Explore Profiles",
            },
        },
        "alerting": {
            "pages": {
                "https://grafana.com/docs/grafana/latest/alerting/": "Alerting",
                "https://grafana.com/docs/grafana/latest/alerting/fundamentals/": "Alerting Fundamentals",
                "https://grafana.com/docs/grafana/latest/alerting/fundamentals/alert-rules/": "Alert Rules",
                "https://grafana.com/docs/grafana/latest/alerting/fundamentals/alert-rules/alert-rule-types/": "Alert Rule Types",
                "https://grafana.com/docs/grafana/latest/alerting/fundamentals/notifications/": "Alert Notifications",
                "https://grafana.com/docs/grafana/latest/alerting/fundamentals/notifications/contact-points/": "Contact Points",
                "https://grafana.com/docs/grafana/latest/alerting/fundamentals/notifications/notification-policies/": "Notification Policies",
                "https://grafana.com/docs/grafana/latest/alerting/fundamentals/notifications/templates/": "Notification Templates",
                "https://grafana.com/docs/grafana/latest/alerting/manage-notifications/": "Manage Notifications",
                "https://grafana.com/docs/grafana/latest/alerting/manage-notifications/create-contact-point/": "Create Contact Point",
                "https://grafana.com/docs/grafana/latest/alerting/manage-notifications/create-notification-policy/": "Create Notification Policy",
                "https://grafana.com/docs/grafana/latest/alerting/manage-notifications/create-silence/": "Create Silence",
                "https://grafana.com/docs/grafana/latest/alerting/manage-notifications/create-mute-timing/": "Create Mute Timing",
                "https://grafana.com/docs/grafana/latest/alerting/alerting-rules/create-grafana-managed-rule/": "Create Grafana Managed Rule",
                "https://grafana.com/docs/grafana/latest/alerting/alerting-rules/create-mimir-loki-managed-rule/": "Create Mimir/Loki Rule",
                "https://grafana.com/docs/grafana/latest/alerting/set-up/": "Alerting Setup",
                "https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/": "Provision Alerting Resources",
                "https://grafana.com/docs/grafana/latest/alerting/set-up/migrating-alerts/": "Migrating Alerts",
                "https://grafana.com/docs/grafana/latest/alerting/alerting-rules/": "Alerting Rules",
                "https://grafana.com/docs/grafana/latest/alerting/alerting-rules/create-recording-rules/": "Create Recording Rules",
                "https://grafana.com/docs/grafana/latest/alerting/fundamentals/alert-rules/queries-conditions/": "Queries and Conditions",
                "https://grafana.com/docs/grafana/latest/alerting/fundamentals/alert-rules/state-and-health/": "Alert State and Health",
                "https://grafana.com/docs/grafana/latest/alerting/fundamentals/alert-rules/organising-alerts/": "Organising Alerts",
                "https://grafana.com/docs/grafana/latest/alerting/fundamentals/annotation-label/": "Alert Annotations and Labels",
                "https://grafana.com/docs/grafana/latest/alerting/manage-notifications/view-state-health/": "View State and Health",
                "https://grafana.com/docs/grafana/latest/alerting/manage-notifications/images-in-notifications/": "Images in Notifications",
                "https://grafana.com/docs/grafana/latest/alerting/set-up/configure-alertmanager/": "Configure Alertmanager",
                "https://grafana.com/docs/grafana/latest/alerting/set-up/performance-limitations/": "Performance and Limitations",
                "https://grafana.com/docs/grafana/latest/alerting/monitor/": "Monitor Alerting",
                "https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/": "Manage Contact Points",
                "https://grafana.com/docs/grafana/latest/alerting/fundamentals/data-source-alerting/": "Data Source Alerting",
                "https://grafana.com/docs/grafana/latest/alerting/fundamentals/alert-rules/recording-rules/": "Recording Rules",
                "https://grafana.com/docs/grafana/latest/alerting/manage-notifications/declare-fixed-response/": "Declare Fixed Response",
                "https://grafana.com/docs/grafana/latest/alerting/alerting-rules/manage-alerting-rules/": "Manage Alerting Rules",
                "https://grafana.com/docs/grafana/latest/alerting/set-up/configure-high-availability/": "Configure High Availability",
            },
        },
        "data-sources": {
            "pages": {
                "https://grafana.com/docs/grafana/latest/datasources/": "Data Sources",
                "https://grafana.com/docs/grafana/latest/datasources/add-a-data-source/": "Add a Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/prometheus/": "Prometheus Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/prometheus/configure-prometheus-data-source/": "Configure Prometheus",
                "https://grafana.com/docs/grafana/latest/datasources/loki/": "Loki Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/loki/configure-loki-data-source/": "Configure Loki",
                "https://grafana.com/docs/grafana/latest/datasources/influxdb/": "InfluxDB Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/elasticsearch/": "Elasticsearch Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/mysql/": "MySQL Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/postgres/": "PostgreSQL Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/graphite/": "Graphite Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/cloudwatch/": "CloudWatch Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/jaeger/": "Jaeger Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/tempo/": "Tempo Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/zipkin/": "Zipkin Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/testdata/": "TestData Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/mssql/": "MSSQL Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/opentsdb/": "OpenTSDB Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/azure-monitor/": "Azure Monitor Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/google-cloud-monitoring/": "Google Cloud Monitoring",
                "https://grafana.com/docs/grafana/latest/datasources/alertmanager/": "Alertmanager Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/prometheus/query-editor/": "Prometheus Query Editor",
                "https://grafana.com/docs/grafana/latest/datasources/loki/query-editor/": "Loki Query Editor",
                "https://grafana.com/docs/grafana/latest/datasources/elasticsearch/query-editor/": "Elasticsearch Query Editor",
                "https://grafana.com/docs/grafana/latest/datasources/influxdb/query-editor/": "InfluxDB Query Editor",
                "https://grafana.com/docs/grafana/latest/datasources/mysql/query-editor/": "MySQL Query Editor",
                "https://grafana.com/docs/grafana/latest/datasources/postgres/query-editor/": "PostgreSQL Query Editor",
                "https://grafana.com/docs/grafana/latest/datasources/phlare/": "Phlare Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/pyroscope/": "Pyroscope Data Source",
                "https://grafana.com/docs/grafana/latest/datasources/tempo/configure-tempo-data-source/": "Configure Tempo",
                "https://grafana.com/docs/grafana/latest/datasources/graphite/query-editor/": "Graphite Query Editor",
                "https://grafana.com/docs/grafana/latest/datasources/cloudwatch/query-editor/": "CloudWatch Query Editor",
                "https://grafana.com/docs/grafana/latest/datasources/mssql/query-editor/": "MSSQL Query Editor",
                "https://grafana.com/docs/grafana/latest/datasources/azure-monitor/query-editor/": "Azure Monitor Query Editor",
                "https://grafana.com/docs/grafana/latest/datasources/tempo/query-editor/": "Tempo Query Editor",
                "https://grafana.com/docs/grafana/latest/datasources/jaeger/query-editor/": "Jaeger Query Editor",
                "https://grafana.com/docs/grafana/latest/datasources/influxdb/influxdb-flux/": "InfluxDB Flux",
                "https://grafana.com/docs/grafana/latest/datasources/google-cloud-monitoring/query-editor/": "Google Cloud Monitoring Query Editor",
                "https://grafana.com/docs/grafana/latest/datasources/prometheus/template-variables/": "Prometheus Template Variables",
                "https://grafana.com/docs/grafana/latest/datasources/loki/template-variables/": "Loki Template Variables",
            },
        },
        "administration": {
            "pages": {
                "https://grafana.com/docs/grafana/latest/administration/": "Administration",
                "https://grafana.com/docs/grafana/latest/administration/user-management/": "User Management",
                "https://grafana.com/docs/grafana/latest/administration/organization-management/": "Organization Management",
                "https://grafana.com/docs/grafana/latest/administration/roles-and-permissions/": "Roles and Permissions",
                "https://grafana.com/docs/grafana/latest/administration/roles-and-permissions/access-control/": "Access Control",
                "https://grafana.com/docs/grafana/latest/administration/team-management/": "Team Management",
                "https://grafana.com/docs/grafana/latest/administration/service-accounts/": "Service Accounts",
                "https://grafana.com/docs/grafana/latest/administration/api-keys/": "API Keys",
                "https://grafana.com/docs/grafana/latest/administration/plugin-management/": "Plugin Management",
                "https://grafana.com/docs/grafana/latest/administration/data-source-management/": "Data Source Management",
                "https://grafana.com/docs/grafana/latest/administration/correlations/": "Correlations",
                "https://grafana.com/docs/grafana/latest/administration/provisioning/": "Provisioning",
                "https://grafana.com/docs/grafana/latest/administration/configuration/": "Configuration",
                "https://grafana.com/docs/grafana/latest/administration/user-management/manage-org-users/": "Manage Org Users",
                "https://grafana.com/docs/grafana/latest/administration/user-management/server-user-management/": "Server User Management",
                "https://grafana.com/docs/grafana/latest/administration/roles-and-permissions/access-control/assign-rbac-roles/": "Assign RBAC Roles",
                "https://grafana.com/docs/grafana/latest/administration/roles-and-permissions/access-control/custom-role-actions-scopes/": "Custom RBAC Roles",
                "https://grafana.com/docs/grafana/latest/administration/roles-and-permissions/access-control/plan-rbac-rollout-strategy/": "RBAC Rollout Strategy",
                "https://grafana.com/docs/grafana/latest/administration/stats-and-license/": "Stats and License",
                "https://grafana.com/docs/grafana/latest/administration/recorded-queries/": "Recorded Queries",
                "https://grafana.com/docs/grafana/latest/administration/enterprise-licensing/": "Enterprise Licensing",
                "https://grafana.com/docs/grafana/latest/administration/manage-users-and-permissions/": "Manage Users and Permissions",
                "https://grafana.com/docs/grafana/latest/administration/api-keys/create-api-key/": "Create API Key",
                "https://grafana.com/docs/grafana/latest/administration/provisioning/provisioning-dashboards/": "Provisioning Dashboards",
                "https://grafana.com/docs/grafana/latest/administration/provisioning/provisioning-data-sources/": "Provisioning Data Sources",
            },
        },
        "setup": {
            "pages": {
                "https://grafana.com/docs/grafana/latest/setup-grafana/": "Setup Grafana",
                "https://grafana.com/docs/grafana/latest/setup-grafana/installation/": "Installation",
                "https://grafana.com/docs/grafana/latest/setup-grafana/installation/debian/": "Install on Debian/Ubuntu",
                "https://grafana.com/docs/grafana/latest/setup-grafana/installation/redhat-rhel-fedora/": "Install on RHEL/Fedora",
                "https://grafana.com/docs/grafana/latest/setup-grafana/installation/docker/": "Install with Docker",
                "https://grafana.com/docs/grafana/latest/setup-grafana/installation/kubernetes/": "Install on Kubernetes",
                "https://grafana.com/docs/grafana/latest/setup-grafana/installation/windows/": "Install on Windows",
                "https://grafana.com/docs/grafana/latest/setup-grafana/installation/mac/": "Install on macOS",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/": "Configure Grafana",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/": "Configure Security",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/": "Configure Authentication",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/ldap/": "LDAP Authentication",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/generic-oauth/": "OAuth Authentication",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/saml/": "SAML Authentication",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/github/": "GitHub Authentication",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/google/": "Google Authentication",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/enterprise-configuration/": "Enterprise Configuration",
                "https://grafana.com/docs/grafana/latest/setup-grafana/upgrade-grafana/": "Upgrade Grafana",
                "https://grafana.com/docs/grafana/latest/setup-grafana/start-restart-grafana/": "Start/Restart Grafana",
                "https://grafana.com/docs/grafana/latest/setup-grafana/installation/suse-opensuse/": "Install on SUSE/openSUSE",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/keycloak/": "Keycloak Authentication",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/azuread/": "Azure AD Authentication",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/gitlab/": "GitLab Authentication",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/okta/": "Okta Authentication",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/jwt/": "JWT Authentication",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-database-encryption/": "Database Encryption",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/settings-updates-at-runtime/": "Settings Updates at Runtime",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/feature-toggles/": "Feature Toggles",
                "https://grafana.com/docs/grafana/latest/setup-grafana/image-rendering/": "Image Rendering",
                "https://grafana.com/docs/grafana/latest/setup-grafana/set-up-https/": "Set Up HTTPS",
                "https://grafana.com/docs/grafana/latest/setup-grafana/set-up-grafana-live/": "Set Up Grafana Live",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/auth-proxy/": "Auth Proxy Authentication",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/proxy/": "Configure Proxy",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/log-config/": "Log Configuration",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/smtp/": "SMTP Configuration",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/database/": "Database Configuration",
                "https://grafana.com/docs/grafana/latest/setup-grafana/installation/helm/": "Install with Helm",
                "https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/caching/": "Caching Configuration",
                "https://grafana.com/docs/grafana/latest/setup-grafana/set-up-grafana-monitoring/": "Set Up Monitoring",
            },
        },
        "variables": {
            "pages": {
                "https://grafana.com/docs/grafana/latest/dashboards/variables/": "Variables Overview",
                "https://grafana.com/docs/grafana/latest/dashboards/variables/add-template-variables/": "Add Template Variables",
                "https://grafana.com/docs/grafana/latest/dashboards/variables/variable-syntax/": "Variable Syntax",
                "https://grafana.com/docs/grafana/latest/dashboards/variables/inspect-variable/": "Inspect Variables",
                "https://grafana.com/docs/grafana/latest/dashboards/variables/manage-variable/": "Manage Variables",
                "https://grafana.com/docs/grafana/latest/dashboards/variables/variable-selection-options/": "Variable Selection Options",
                "https://grafana.com/docs/grafana/latest/dashboards/variables/add-template-variables/add-query-variable/": "Query Variable",
                "https://grafana.com/docs/grafana/latest/dashboards/variables/add-template-variables/add-custom-variable/": "Custom Variable",
                "https://grafana.com/docs/grafana/latest/dashboards/variables/add-template-variables/add-interval-variable/": "Interval Variable",
                "https://grafana.com/docs/grafana/latest/dashboards/variables/add-template-variables/add-ad-hoc-filters/": "Ad Hoc Filters",
            },
        },
        "transformations": {
            "pages": {
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/": "Transformations Overview",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/config-from-query/": "Config from Query",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/merge/": "Merge Transform",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/filter-by-name/": "Filter by Name",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/reduce/": "Reduce Transform",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/organize-fields/": "Organize Fields",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/join-by-field/": "Join by Field",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/calculate-field/": "Calculate Field",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/group-by/": "Group By",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/series-to-rows/": "Series to Rows",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/concatenate-fields/": "Concatenate Fields",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/filter-by-value/": "Filter by Value",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/rename-by-regex/": "Rename by Regex",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/sort-by/": "Sort By",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/add-field-from-calculation/": "Add Field from Calculation",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/labels-to-fields/": "Labels to Fields",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/rows-to-fields/": "Rows to Fields",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/extract-fields/": "Extract Fields",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/create-heatmap/": "Create Heatmap",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/histogram/": "Histogram Transform",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/partition-by-values/": "Partition by Values",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/regression/": "Regression Transform",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/convert-field-type/": "Convert Field Type",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/format-string/": "Format String",
                "https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/transform-data/limit/": "Limit Transform",
            },
        },
        "annotations": {
            "pages": {
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/annotate-visualizations/": "Annotate Visualizations",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/manage-dashboard-links/": "Manage Dashboard Links",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/create-dashboard/": "Create Dashboard for Annotations",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/": "Best Practices for Annotations",
                "https://grafana.com/docs/grafana/latest/administration/correlations/": "Correlations and Annotations",
                "https://grafana.com/docs/grafana/latest/fundamentals/annotation-label/": "Annotation and Label Fundamentals",
                "https://grafana.com/docs/grafana/latest/explore/logs-integration/": "Logs Integration with Annotations",
                "https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/manage-library-panels/": "Library Panels and Annotations",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"grafana-{source_key}" if source_key else "grafana"
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
            for suffix in [' | Grafana documentation', ' | Grafana Labs', ' - Grafana']:
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
                        "category": f"grafana-{source_key}",
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
            self.log.info(f"=== Scraping grafana/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    GrafanaScraper(base, source_key).run()
