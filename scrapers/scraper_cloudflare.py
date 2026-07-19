#!/usr/bin/env python3
"""Cloudflare developer documentation scraper.

Covers:
  - Workers (serverless compute, runtime APIs, Wrangler CLI)
  - Pages (static site hosting, framework guides, functions)
  - R2 (object storage, S3 API compatibility)
  - D1 (serverless SQL database)
  - DNS (record management, zone setups, DNSSEC)
  - WAF (managed rules, custom rules, rate limiting)
  - SSL/TLS (edge certificates, origin configuration)
  - Load Balancing (pools, monitors, traffic steering)
  - Zero Trust / Cloudflare One (Access, Gateway, Tunnel, WARP)
  - API Shield (schema validation, JWT, mTLS)
  - Stream (video upload, playback, live streaming)
  - Images (upload, transform, manage)
  - Workers AI (inference, models, bindings)
  - Vectorize (vector database, indexes, embeddings)
  - Queues (message queues, producers, consumers)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class CloudflareScraper(BaseScraper):
    """Scrape Cloudflare developer documentation across all product areas."""

    SOURCES = {
        "workers": {
            "pages": {
                # Getting started
                "https://developers.cloudflare.com/workers/": "Cloudflare Workers Overview",
                "https://developers.cloudflare.com/workers/get-started/guide/": "Workers Get Started Guide",
                "https://developers.cloudflare.com/workers/get-started/quickstarts/": "Workers Quickstarts",
                # Runtime APIs
                "https://developers.cloudflare.com/workers/runtime-apis/": "Workers Runtime APIs",
                "https://developers.cloudflare.com/workers/runtime-apis/fetch/": "Workers Fetch API",
                "https://developers.cloudflare.com/workers/runtime-apis/kv/": "Workers KV Runtime API",
                "https://developers.cloudflare.com/workers/runtime-apis/cache/": "Workers Cache API",
                "https://developers.cloudflare.com/workers/runtime-apis/durable-objects/": "Workers Durable Objects API",
                "https://developers.cloudflare.com/workers/runtime-apis/web-standards/": "Workers Web Standards",
                "https://developers.cloudflare.com/workers/runtime-apis/scheduled-event/": "Workers Scheduled Event",
                "https://developers.cloudflare.com/workers/runtime-apis/websockets/": "Workers WebSockets API",
                "https://developers.cloudflare.com/workers/runtime-apis/streams/": "Workers Streams API",
                # Configuration
                "https://developers.cloudflare.com/workers/configuration/": "Workers Configuration",
                "https://developers.cloudflare.com/workers/configuration/routing/": "Workers Routing",
                "https://developers.cloudflare.com/workers/configuration/bindings/": "Workers Bindings",
                "https://developers.cloudflare.com/workers/configuration/environment-variables/": "Workers Environment Variables",
                "https://developers.cloudflare.com/workers/configuration/secrets/": "Workers Secrets",
                "https://developers.cloudflare.com/workers/configuration/cron-triggers/": "Workers Cron Triggers",
                # Observability
                "https://developers.cloudflare.com/workers/observability/": "Workers Observability",
                "https://developers.cloudflare.com/workers/observability/logging/": "Workers Logging",
                # Wrangler CLI
                "https://developers.cloudflare.com/workers/wrangler/": "Wrangler CLI Overview",
                "https://developers.cloudflare.com/workers/wrangler/install-and-update/": "Wrangler Install and Update",
                "https://developers.cloudflare.com/workers/wrangler/commands/": "Wrangler Commands",
                # Platform
                "https://developers.cloudflare.com/workers/platform/pricing/": "Workers Pricing",
                "https://developers.cloudflare.com/workers/platform/limits/": "Workers Limits",
                # Examples and tutorials
                "https://developers.cloudflare.com/workers/examples/": "Workers Examples",
                "https://developers.cloudflare.com/workers/tutorials/": "Workers Tutorials",
            },
        },
        "pages": {
            "pages": {
                # Getting started
                "https://developers.cloudflare.com/pages/": "Cloudflare Pages Overview",
                "https://developers.cloudflare.com/pages/get-started/guide/": "Pages Get Started Guide",
                "https://developers.cloudflare.com/pages/get-started/direct-upload/": "Pages Direct Upload",
                # Configuration
                "https://developers.cloudflare.com/pages/configuration/build-configuration/": "Pages Build Configuration",
                "https://developers.cloudflare.com/pages/configuration/build-watch-paths/": "Pages Build Watch Paths",
                "https://developers.cloudflare.com/pages/configuration/custom-domains/": "Pages Custom Domains",
                "https://developers.cloudflare.com/pages/configuration/redirects/": "Pages Redirects",
                "https://developers.cloudflare.com/pages/configuration/headers/": "Pages Headers",
                "https://developers.cloudflare.com/pages/configuration/preview-deployments/": "Pages Preview Deployments",
                # Framework guides
                "https://developers.cloudflare.com/pages/framework-guides/": "Pages Framework Guides",
                "https://developers.cloudflare.com/pages/framework-guides/deploy-a-nextjs-site/": "Pages Deploy Next.js",
                "https://developers.cloudflare.com/pages/framework-guides/deploy-a-react-site/": "Pages Deploy React",
                "https://developers.cloudflare.com/pages/framework-guides/deploy-a-hugo-site/": "Pages Deploy Hugo",
                "https://developers.cloudflare.com/pages/framework-guides/deploy-an-astro-site/": "Pages Deploy Astro",
                "https://developers.cloudflare.com/pages/framework-guides/deploy-a-svelte-site/": "Pages Deploy Svelte",
                "https://developers.cloudflare.com/pages/framework-guides/deploy-an-angular-site/": "Pages Deploy Angular",
                "https://developers.cloudflare.com/pages/framework-guides/deploy-a-gatsby-site/": "Pages Deploy Gatsby",
                "https://developers.cloudflare.com/pages/framework-guides/deploy-a-remix-site/": "Pages Deploy Remix",
                # Functions and bindings
                "https://developers.cloudflare.com/pages/functions/": "Pages Functions",
                "https://developers.cloudflare.com/pages/functions/bindings/": "Pages Function Bindings",
                # Platform
                "https://developers.cloudflare.com/pages/platform/git-integration/": "Pages Git Integration",
                "https://developers.cloudflare.com/pages/platform/branch-build-controls/": "Pages Branch Build Controls",
            },
        },
        "r2": {
            "pages": {
                # Getting started
                "https://developers.cloudflare.com/r2/": "Cloudflare R2 Overview",
                "https://developers.cloudflare.com/r2/get-started/": "R2 Get Started",
                # API access
                "https://developers.cloudflare.com/r2/api/": "R2 API Overview",
                "https://developers.cloudflare.com/r2/api/s3/": "R2 S3 API Compatibility",
                "https://developers.cloudflare.com/r2/api/workers/": "R2 Workers API",
                "https://developers.cloudflare.com/r2/api/s3/presigned-urls/": "R2 Presigned URLs",
                # Buckets
                "https://developers.cloudflare.com/r2/buckets/": "R2 Buckets",
                "https://developers.cloudflare.com/r2/buckets/public-buckets/": "R2 Public Buckets",
                "https://developers.cloudflare.com/r2/buckets/cors/": "R2 CORS Configuration",
                "https://developers.cloudflare.com/r2/buckets/lifecycle-rules/": "R2 Lifecycle Rules",
                "https://developers.cloudflare.com/r2/buckets/event-notifications/": "R2 Event Notifications",
                # Data access
                "https://developers.cloudflare.com/r2/data-access/": "R2 Data Access",
                # Pricing and examples
                "https://developers.cloudflare.com/r2/pricing/": "R2 Pricing",
                "https://developers.cloudflare.com/r2/examples/": "R2 Examples",
                "https://developers.cloudflare.com/r2/reference/": "R2 Reference",
            },
        },
        "d1": {
            "pages": {
                # Getting started
                "https://developers.cloudflare.com/d1/": "Cloudflare D1 Overview",
                "https://developers.cloudflare.com/d1/get-started/": "D1 Get Started",
                # Build with D1
                "https://developers.cloudflare.com/d1/build-with-d1/": "Build with D1",
                "https://developers.cloudflare.com/d1/build-with-d1/d1-client-api/": "D1 Client API",
                "https://developers.cloudflare.com/d1/build-with-d1/query-json/": "D1 Query JSON",
                "https://developers.cloudflare.com/d1/build-with-d1/import-export/": "D1 Import and Export",
                "https://developers.cloudflare.com/d1/build-with-d1/batch-api/": "D1 Batch API",
                # Configuration
                "https://developers.cloudflare.com/d1/configuration/": "D1 Configuration",
                "https://developers.cloudflare.com/d1/configuration/backups/": "D1 Backups",
                "https://developers.cloudflare.com/d1/configuration/data-location/": "D1 Data Location",
                # Platform
                "https://developers.cloudflare.com/d1/observability/": "D1 Observability",
                "https://developers.cloudflare.com/d1/platform/pricing/": "D1 Pricing",
            },
        },
        "dns": {
            "pages": {
                # Overview
                "https://developers.cloudflare.com/dns/": "Cloudflare DNS Overview",
                # Managing records
                "https://developers.cloudflare.com/dns/manage-dns-records/": "DNS Manage Records",
                "https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/": "DNS Create Records",
                "https://developers.cloudflare.com/dns/manage-dns-records/how-to/import-and-export/": "DNS Import and Export",
                "https://developers.cloudflare.com/dns/manage-dns-records/reference/proxied-dns-records/": "DNS Proxied Records",
                # Zone setups
                "https://developers.cloudflare.com/dns/zone-setups/": "DNS Zone Setups",
                "https://developers.cloudflare.com/dns/zone-setups/full-setup/": "DNS Full Setup",
                "https://developers.cloudflare.com/dns/zone-setups/partial-setup/": "DNS Partial Setup",
                "https://developers.cloudflare.com/dns/zone-setups/zone-transfers/": "DNS Zone Transfers",
                # Additional options
                "https://developers.cloudflare.com/dns/additional-options/dnssec/": "DNS DNSSEC",
                "https://developers.cloudflare.com/dns/additional-options/custom-nameservers/": "DNS Custom Nameservers",
                # CNAME flattening
                "https://developers.cloudflare.com/dns/cname-flattening/": "DNS CNAME Flattening",
                # Secondary DNS
                "https://developers.cloudflare.com/dns/zone-setups/zone-transfers/cloudflare-as-secondary/": "DNS Secondary Setup",
                "https://developers.cloudflare.com/dns/dns-firewall/": "DNS Firewall",
                "https://developers.cloudflare.com/dns/reference/analytics/": "DNS Analytics",
            },
        },
        "waf": {
            "pages": {
                # Overview
                "https://developers.cloudflare.com/waf/": "Cloudflare WAF Overview",
                # Managed rules
                "https://developers.cloudflare.com/waf/managed-rules/": "WAF Managed Rules",
                "https://developers.cloudflare.com/waf/managed-rules/deploy-zone-dashboard/": "WAF Deploy Managed Rules",
                # Custom rules
                "https://developers.cloudflare.com/waf/custom-rules/": "WAF Custom Rules",
                "https://developers.cloudflare.com/waf/custom-rules/create-dashboard/": "WAF Create Custom Rules",
                # Rate limiting
                "https://developers.cloudflare.com/waf/rate-limiting-rules/": "WAF Rate Limiting Rules",
                "https://developers.cloudflare.com/waf/rate-limiting-rules/create-dashboard/": "WAF Create Rate Limit",
                # Tools and analytics
                "https://developers.cloudflare.com/waf/tools/": "WAF Tools",
                "https://developers.cloudflare.com/waf/tools/ip-access-rules/": "WAF IP Access Rules",
                "https://developers.cloudflare.com/waf/analytics/": "WAF Analytics",
                "https://developers.cloudflare.com/waf/change-log/": "WAF Change Log",
                "https://developers.cloudflare.com/waf/reference/": "WAF Reference",
            },
        },
        "ssl-tls": {
            "pages": {
                # Overview
                "https://developers.cloudflare.com/ssl/": "Cloudflare SSL/TLS Overview",
                "https://developers.cloudflare.com/ssl/get-started/": "SSL/TLS Get Started",
                # Edge certificates
                "https://developers.cloudflare.com/ssl/edge-certificates/": "SSL Edge Certificates",
                "https://developers.cloudflare.com/ssl/edge-certificates/encryption-modes/": "SSL Encryption Modes",
                "https://developers.cloudflare.com/ssl/edge-certificates/universal-ssl/": "SSL Universal SSL",
                "https://developers.cloudflare.com/ssl/edge-certificates/advanced-certificate-manager/": "SSL Advanced Certificate Manager",
                "https://developers.cloudflare.com/ssl/edge-certificates/custom-certificates/": "SSL Custom Certificates",
                "https://developers.cloudflare.com/ssl/edge-certificates/additional-options/": "SSL Additional Options",
                # Origin configuration
                "https://developers.cloudflare.com/ssl/origin-configuration/": "SSL Origin Configuration",
                "https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/": "SSL Origin CA",
                "https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/": "SSL Authenticated Origin Pull",
                # Client certificates
                "https://developers.cloudflare.com/ssl/client-certificates/": "SSL Client Certificates",
                # Other
                "https://developers.cloudflare.com/ssl/keyless-ssl/": "SSL Keyless SSL",
                "https://developers.cloudflare.com/ssl/reference/": "SSL/TLS Reference",
                "https://developers.cloudflare.com/ssl/troubleshooting/": "SSL Troubleshooting",
            },
        },
        "load-balancing": {
            "pages": {
                # Overview
                "https://developers.cloudflare.com/load-balancing/": "Cloudflare Load Balancing Overview",
                "https://developers.cloudflare.com/load-balancing/get-started/": "Load Balancing Get Started",
                # Core concepts
                "https://developers.cloudflare.com/load-balancing/pools/": "Load Balancing Pools",
                "https://developers.cloudflare.com/load-balancing/monitors/": "Load Balancing Monitors",
                "https://developers.cloudflare.com/load-balancing/load-balancers/": "Load Balancers",
                # Traffic steering
                "https://developers.cloudflare.com/load-balancing/understand-basics/traffic-steering/": "Load Balancing Traffic Steering",
                "https://developers.cloudflare.com/load-balancing/understand-basics/traffic-steering/steering-policies/": "Load Balancing Steering Policies",
                "https://developers.cloudflare.com/load-balancing/understand-basics/health-details/": "Load Balancing Health Details",
                # Additional features
                "https://developers.cloudflare.com/load-balancing/session-affinity/": "Load Balancing Session Affinity",
                "https://developers.cloudflare.com/load-balancing/additional-options/load-balancing-rules/": "Load Balancing Rules",
                "https://developers.cloudflare.com/load-balancing/reference/": "Load Balancing Reference",
                "https://developers.cloudflare.com/load-balancing/troubleshooting/": "Load Balancing Troubleshooting",
            },
        },
        "zero-trust": {
            "pages": {
                # Overview
                "https://developers.cloudflare.com/cloudflare-one/": "Cloudflare One Overview",
                "https://developers.cloudflare.com/cloudflare-one/setup/": "Cloudflare One Setup",
                # Network connections
                "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/": "Zero Trust Connect Networks",
                "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/": "Zero Trust Connect Networks Get Started",
                "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/private-net/": "Zero Trust Private Networks",
                # Device connections
                "https://developers.cloudflare.com/cloudflare-one/connections/connect-devices/": "Zero Trust Connect Devices",
                "https://developers.cloudflare.com/cloudflare-one/connections/connect-devices/warp/": "Zero Trust WARP Client",
                "https://developers.cloudflare.com/cloudflare-one/connections/connect-devices/warp/deployment/": "Zero Trust WARP Deployment",
                # Policies
                "https://developers.cloudflare.com/cloudflare-one/policies/access/": "Zero Trust Access Policies",
                "https://developers.cloudflare.com/cloudflare-one/policies/gateway/": "Zero Trust Gateway Policies",
                "https://developers.cloudflare.com/cloudflare-one/policies/gateway/dns-policies/": "Zero Trust DNS Policies",
                "https://developers.cloudflare.com/cloudflare-one/policies/gateway/http-policies/": "Zero Trust HTTP Policies",
                # Identity
                "https://developers.cloudflare.com/cloudflare-one/identity/": "Zero Trust Identity",
                "https://developers.cloudflare.com/cloudflare-one/identity/idp-integration/": "Zero Trust IdP Integration",
                # Applications
                "https://developers.cloudflare.com/cloudflare-one/applications/": "Zero Trust Applications",
                "https://developers.cloudflare.com/cloudflare-one/applications/configure-apps/": "Zero Trust Configure Apps",
                # Tunnels
                "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-remote-tunnel/": "Zero Trust Create Tunnel",
                # Browser isolation, DLP, CASB
                "https://developers.cloudflare.com/cloudflare-one/policies/browser-isolation/": "Zero Trust Browser Isolation",
                "https://developers.cloudflare.com/cloudflare-one/policies/data-loss-prevention/": "Zero Trust DLP",
                # Analytics
                "https://developers.cloudflare.com/cloudflare-one/analytics/": "Zero Trust Analytics",
                "https://developers.cloudflare.com/cloudflare-one/analytics/logs/": "Zero Trust Logs",
            },
        },
        "api-shield": {
            "pages": {
                # Overview
                "https://developers.cloudflare.com/api-shield/": "Cloudflare API Shield Overview",
                "https://developers.cloudflare.com/api-shield/get-started/": "API Shield Get Started",
                # Security
                "https://developers.cloudflare.com/api-shield/security/": "API Shield Security",
                "https://developers.cloudflare.com/api-shield/security/schema-validation/": "API Shield Schema Validation",
                "https://developers.cloudflare.com/api-shield/security/jwt-validation/": "API Shield JWT Validation",
                "https://developers.cloudflare.com/api-shield/security/mtls/": "API Shield mTLS",
                "https://developers.cloudflare.com/api-shield/security/sequence-analytics/": "API Shield Sequence Analytics",
                # Management
                "https://developers.cloudflare.com/api-shield/management-and-monitoring/": "API Shield Management",
                "https://developers.cloudflare.com/api-shield/management-and-monitoring/api-discovery/": "API Shield API Discovery",
                "https://developers.cloudflare.com/api-shield/reference/": "API Shield Reference",
            },
        },
        "stream": {
            "pages": {
                # Overview
                "https://developers.cloudflare.com/stream/": "Cloudflare Stream Overview",
                "https://developers.cloudflare.com/stream/get-started/": "Stream Get Started",
                # Uploading
                "https://developers.cloudflare.com/stream/uploading-videos/": "Stream Uploading Videos",
                "https://developers.cloudflare.com/stream/uploading-videos/direct-creator-uploads/": "Stream Direct Creator Uploads",
                "https://developers.cloudflare.com/stream/uploading-videos/upload-via-link/": "Stream Upload via Link",
                # Viewing
                "https://developers.cloudflare.com/stream/viewing-videos/": "Stream Viewing Videos",
                "https://developers.cloudflare.com/stream/viewing-videos/using-the-player-api/": "Stream Player API",
                "https://developers.cloudflare.com/stream/viewing-videos/using-the-stream-player/": "Stream Player",
                # Live streaming
                "https://developers.cloudflare.com/stream/stream-live/": "Stream Live Streaming",
                "https://developers.cloudflare.com/stream/stream-live/start-stream-live/": "Stream Start Live",
                # Editing and analytics
                "https://developers.cloudflare.com/stream/edit-videos/": "Stream Edit Videos",
                "https://developers.cloudflare.com/stream/edit-videos/adding-captions/": "Stream Captions",
                "https://developers.cloudflare.com/stream/analytics/": "Stream Analytics",
                "https://developers.cloudflare.com/stream/webhooks/": "Stream Webhooks",
            },
        },
        "images": {
            "pages": {
                # Overview
                "https://developers.cloudflare.com/images/": "Cloudflare Images Overview",
                # Upload
                "https://developers.cloudflare.com/images/upload-images/": "Images Upload",
                "https://developers.cloudflare.com/images/upload-images/formats-limitations/": "Images Formats and Limitations",
                # Transform
                "https://developers.cloudflare.com/images/transform-images/": "Images Transform",
                "https://developers.cloudflare.com/images/transform-images/transform-via-url/": "Images Transform via URL",
                "https://developers.cloudflare.com/images/transform-images/transform-via-workers/": "Images Transform via Workers",
                # Manage
                "https://developers.cloudflare.com/images/manage-images/": "Images Manage",
                "https://developers.cloudflare.com/images/manage-images/serve-images/": "Images Serve",
                "https://developers.cloudflare.com/images/manage-images/create-variants/": "Images Create Variants",
                # Pricing and Polish
                "https://developers.cloudflare.com/images/pricing/": "Images Pricing",
                "https://developers.cloudflare.com/images/polish/": "Images Polish",
            },
        },
        "ai": {
            "pages": {
                # Overview
                "https://developers.cloudflare.com/workers-ai/": "Cloudflare Workers AI Overview",
                "https://developers.cloudflare.com/workers-ai/get-started/": "Workers AI Get Started",
                # Models
                "https://developers.cloudflare.com/workers-ai/models/": "Workers AI Models",
                "https://developers.cloudflare.com/workers-ai/models/text-generation/": "Workers AI Text Generation",
                "https://developers.cloudflare.com/workers-ai/models/text-embeddings/": "Workers AI Text Embeddings",
                "https://developers.cloudflare.com/workers-ai/models/image-classification/": "Workers AI Image Classification",
                "https://developers.cloudflare.com/workers-ai/models/text-to-image/": "Workers AI Text to Image",
                "https://developers.cloudflare.com/workers-ai/models/speech-recognition/": "Workers AI Speech Recognition",
                "https://developers.cloudflare.com/workers-ai/models/translation/": "Workers AI Translation",
                # Configuration
                "https://developers.cloudflare.com/workers-ai/configuration/bindings/": "Workers AI Bindings",
                # Tutorials and pricing
                "https://developers.cloudflare.com/workers-ai/tutorials/": "Workers AI Tutorials",
                "https://developers.cloudflare.com/workers-ai/platform/pricing/": "Workers AI Pricing",
            },
        },
        "vectorize": {
            "pages": {
                # Overview
                "https://developers.cloudflare.com/vectorize/": "Cloudflare Vectorize Overview",
                "https://developers.cloudflare.com/vectorize/get-started/": "Vectorize Get Started",
                # Best practices
                "https://developers.cloudflare.com/vectorize/best-practices/": "Vectorize Best Practices",
                "https://developers.cloudflare.com/vectorize/best-practices/insert-vectors/": "Vectorize Insert Vectors",
                "https://developers.cloudflare.com/vectorize/best-practices/query-vectors/": "Vectorize Query Vectors",
                # Reference
                "https://developers.cloudflare.com/vectorize/reference/": "Vectorize Reference",
                "https://developers.cloudflare.com/vectorize/reference/client-api/": "Vectorize Client API",
                "https://developers.cloudflare.com/vectorize/reference/metadata-filtering/": "Vectorize Metadata Filtering",
                # Platform
                "https://developers.cloudflare.com/vectorize/platform/pricing/": "Vectorize Pricing",
                "https://developers.cloudflare.com/vectorize/platform/limits/": "Vectorize Limits",
            },
        },
        "queues": {
            "pages": {
                # Overview
                "https://developers.cloudflare.com/queues/": "Cloudflare Queues Overview",
                "https://developers.cloudflare.com/queues/get-started/": "Queues Get Started",
                # Configuration
                "https://developers.cloudflare.com/queues/configuration/": "Queues Configuration",
                "https://developers.cloudflare.com/queues/configuration/configure-queues/": "Queues Configure",
                "https://developers.cloudflare.com/queues/configuration/batching-retries/": "Queues Batching and Retries",
                "https://developers.cloudflare.com/queues/configuration/dead-letter-queues/": "Queues Dead Letter Queues",
                # Reference
                "https://developers.cloudflare.com/queues/reference/": "Queues Reference",
                "https://developers.cloudflare.com/queues/reference/javascript-apis/": "Queues JavaScript APIs",
                # Examples and platform
                "https://developers.cloudflare.com/queues/examples/": "Queues Examples",
                "https://developers.cloudflare.com/queues/platform/pricing/": "Queues Pricing",
            },
        },
        "network": {
            "pages": {
                # Network services
                "https://developers.cloudflare.com/network/": "Cloudflare Network Overview",
                "https://developers.cloudflare.com/network/websockets/": "Network WebSockets",
                "https://developers.cloudflare.com/network/grpc-connections/": "Network gRPC Connections",
                "https://developers.cloudflare.com/network/ip-addresses/": "Network IP Addresses",
                # Spectrum
                "https://developers.cloudflare.com/spectrum/": "Cloudflare Spectrum Overview",
                "https://developers.cloudflare.com/spectrum/get-started/": "Spectrum Get Started",
                "https://developers.cloudflare.com/spectrum/about/": "Spectrum About",
                "https://developers.cloudflare.com/spectrum/reference/": "Spectrum Reference",
                # Argo Smart Routing
                "https://developers.cloudflare.com/argo-smart-routing/": "Argo Smart Routing Overview",
                "https://developers.cloudflare.com/argo-smart-routing/get-started/": "Argo Smart Routing Get Started",
                "https://developers.cloudflare.com/argo-smart-routing/analytics/": "Argo Smart Routing Analytics",
                # China Network
                "https://developers.cloudflare.com/china-network/": "China Network Overview",
            },
        },
        "cache": {
            "pages": {
                # Cache
                "https://developers.cloudflare.com/cache/": "Cloudflare Cache Overview",
                "https://developers.cloudflare.com/cache/get-started/": "Cache Get Started",
                "https://developers.cloudflare.com/cache/how-to/purge-cache/": "Cache Purge",
                "https://developers.cloudflare.com/cache/how-to/cache-rules/": "Cache Rules",
                "https://developers.cloudflare.com/cache/how-to/tiered-cache/": "Tiered Cache",
                "https://developers.cloudflare.com/cache/how-to/cache-keys/": "Cache Keys",
                "https://developers.cloudflare.com/cache/reference/cache-behavior/": "Cache Behavior Reference",
                "https://developers.cloudflare.com/cache/reference/default-cache-behavior/": "Default Cache Behavior",
                "https://developers.cloudflare.com/cache/troubleshooting/": "Cache Troubleshooting",
                "https://developers.cloudflare.com/cache/concepts/cache-control/": "Cache Control Headers",
                "https://developers.cloudflare.com/cache/concepts/default-cache-behavior/": "Cache Default Behavior Concepts",
                "https://developers.cloudflare.com/cache/advanced-configuration/": "Cache Advanced Configuration",
            },
        },
        "rules": {
            "pages": {
                # Rules engine
                "https://developers.cloudflare.com/rules/": "Cloudflare Rules Overview",
                "https://developers.cloudflare.com/rules/transform/": "Transform Rules",
                "https://developers.cloudflare.com/rules/transform/url-rewrite/": "URL Rewrite Rules",
                "https://developers.cloudflare.com/rules/transform/request-header-modification/": "Request Header Modification",
                "https://developers.cloudflare.com/rules/transform/response-header-modification/": "Response Header Modification",
                "https://developers.cloudflare.com/rules/origin-rules/": "Origin Rules",
                "https://developers.cloudflare.com/rules/page-rules/": "Page Rules",
                "https://developers.cloudflare.com/rules/configuration-rules/": "Configuration Rules",
                "https://developers.cloudflare.com/rules/redirect-rules/": "Redirect Rules",
                "https://developers.cloudflare.com/rules/snippets/": "Cloudflare Snippets",
                "https://developers.cloudflare.com/rules/reference/": "Rules Reference",
            },
        },
        "analytics": {
            "pages": {
                # Analytics and logs
                "https://developers.cloudflare.com/analytics/": "Cloudflare Analytics Overview",
                "https://developers.cloudflare.com/analytics/web-analytics/": "Web Analytics",
                "https://developers.cloudflare.com/analytics/graphql-api/": "Analytics GraphQL API",
                "https://developers.cloudflare.com/analytics/graphql-api/getting-started/": "GraphQL API Getting Started",
                "https://developers.cloudflare.com/analytics/account-and-zone-analytics/": "Account and Zone Analytics",
                # Logs
                "https://developers.cloudflare.com/logs/": "Cloudflare Logs Overview",
                "https://developers.cloudflare.com/logs/get-started/": "Logs Get Started",
                "https://developers.cloudflare.com/logs/logpush/": "Logpush",
                "https://developers.cloudflare.com/logs/logpull/": "Logpull",
                "https://developers.cloudflare.com/logs/reference/log-fields/": "Log Fields Reference",
                "https://developers.cloudflare.com/logs/logpush/logpush-configuration-api/": "Logpush Configuration API",
            },
        },
        "api": {
            "pages": {
                # Cloudflare API
                "https://developers.cloudflare.com/fundamentals/api/": "Cloudflare API Overview",
                "https://developers.cloudflare.com/fundamentals/api/get-started/": "API Get Started",
                "https://developers.cloudflare.com/fundamentals/api/how-to/create-via-api/": "API Create Resources",
                "https://developers.cloudflare.com/fundamentals/api/reference/": "API Reference",
                "https://developers.cloudflare.com/fundamentals/api/how-to/make-api-calls/": "API Make Calls",
                # Terraform
                "https://developers.cloudflare.com/terraform/": "Cloudflare Terraform Provider",
                "https://developers.cloudflare.com/terraform/installing/": "Terraform Installing",
                "https://developers.cloudflare.com/terraform/tutorial/": "Terraform Tutorial",
                # Pulumi
                "https://developers.cloudflare.com/pulumi/": "Cloudflare Pulumi Provider",
                "https://developers.cloudflare.com/pulumi/installing/": "Pulumi Installing",
                "https://developers.cloudflare.com/pulumi/tutorial/": "Pulumi Tutorial",
            },
        },
        "email": {
            "pages": {
                # Email routing
                "https://developers.cloudflare.com/email-routing/": "Cloudflare Email Routing Overview",
                "https://developers.cloudflare.com/email-routing/get-started/": "Email Routing Get Started",
                "https://developers.cloudflare.com/email-routing/setup/": "Email Routing Setup",
                "https://developers.cloudflare.com/email-routing/email-workers/": "Email Workers",
                "https://developers.cloudflare.com/email-routing/postmaster/": "Email Routing Postmaster",
                # Email Security (Area 1)
                "https://developers.cloudflare.com/email-security/": "Cloudflare Email Security",
                "https://developers.cloudflare.com/email-security/deployment/": "Email Security Deployment",
                "https://developers.cloudflare.com/email-security/detection-settings/": "Email Security Detection Settings",
                # DMARC Management
                "https://developers.cloudflare.com/dmarc-management/": "DMARC Management Overview",
                "https://developers.cloudflare.com/dmarc-management/get-started/": "DMARC Get Started",
            },
        },
        "durable-objects": {
            "pages": {
                # Durable Objects
                "https://developers.cloudflare.com/durable-objects/": "Durable Objects Overview",
                "https://developers.cloudflare.com/durable-objects/get-started/": "Durable Objects Get Started",
                "https://developers.cloudflare.com/durable-objects/api/": "Durable Objects API",
                "https://developers.cloudflare.com/durable-objects/api/state/": "Durable Objects State API",
                "https://developers.cloudflare.com/durable-objects/api/alarms/": "Durable Objects Alarms",
                "https://developers.cloudflare.com/durable-objects/api/websockets/": "Durable Objects WebSockets",
                "https://developers.cloudflare.com/durable-objects/best-practices/": "Durable Objects Best Practices",
                "https://developers.cloudflare.com/durable-objects/examples/": "Durable Objects Examples",
                "https://developers.cloudflare.com/durable-objects/reference/": "Durable Objects Reference",
                "https://developers.cloudflare.com/durable-objects/platform/pricing/": "Durable Objects Pricing",
            },
        },
        "kv": {
            "pages": {
                # Workers KV
                "https://developers.cloudflare.com/kv/": "Cloudflare KV Overview",
                "https://developers.cloudflare.com/kv/get-started/": "KV Get Started",
                "https://developers.cloudflare.com/kv/api/": "KV API",
                "https://developers.cloudflare.com/kv/api/read-key-value-pairs/": "KV Read Values",
                "https://developers.cloudflare.com/kv/api/write-key-value-pairs/": "KV Write Values",
                "https://developers.cloudflare.com/kv/api/list-keys/": "KV List Keys",
                "https://developers.cloudflare.com/kv/api/delete-key-value-pairs/": "KV Delete Values",
                "https://developers.cloudflare.com/kv/reference/": "KV Reference",
                "https://developers.cloudflare.com/kv/reference/kv-namespaces/": "KV Namespaces",
                "https://developers.cloudflare.com/kv/platform/pricing/": "KV Pricing",
                "https://developers.cloudflare.com/kv/platform/limits/": "KV Limits",
            },
        },
        "hyperdrive": {
            "pages": {
                # Hyperdrive
                "https://developers.cloudflare.com/hyperdrive/": "Cloudflare Hyperdrive Overview",
                "https://developers.cloudflare.com/hyperdrive/get-started/": "Hyperdrive Get Started",
                "https://developers.cloudflare.com/hyperdrive/configuration/": "Hyperdrive Configuration",
                "https://developers.cloudflare.com/hyperdrive/configuration/connect-to-postgres/": "Hyperdrive Connect to PostgreSQL",
                "https://developers.cloudflare.com/hyperdrive/configuration/connect-to-mysql/": "Hyperdrive Connect to MySQL",
                "https://developers.cloudflare.com/hyperdrive/examples/": "Hyperdrive Examples",
                "https://developers.cloudflare.com/hyperdrive/reference/": "Hyperdrive Reference",
                "https://developers.cloudflare.com/hyperdrive/platform/pricing/": "Hyperdrive Pricing",
            },
        },
        "turnstile": {
            "pages": {
                # Turnstile (CAPTCHA alternative)
                "https://developers.cloudflare.com/turnstile/": "Cloudflare Turnstile Overview",
                "https://developers.cloudflare.com/turnstile/get-started/": "Turnstile Get Started",
                "https://developers.cloudflare.com/turnstile/get-started/client-side-rendering/": "Turnstile Client Side Rendering",
                "https://developers.cloudflare.com/turnstile/get-started/server-side-validation/": "Turnstile Server Side Validation",
                "https://developers.cloudflare.com/turnstile/reference/": "Turnstile Reference",
                "https://developers.cloudflare.com/turnstile/troubleshooting/": "Turnstile Troubleshooting",
                "https://developers.cloudflare.com/turnstile/migration/": "Turnstile Migration",
            },
        },
        "waiting-room": {
            "pages": {
                # Waiting Room
                "https://developers.cloudflare.com/waiting-room/": "Cloudflare Waiting Room Overview",
                "https://developers.cloudflare.com/waiting-room/get-started/": "Waiting Room Get Started",
                "https://developers.cloudflare.com/waiting-room/how-to/create-waiting-room/": "Create Waiting Room",
                "https://developers.cloudflare.com/waiting-room/how-to/customize-waiting-room/": "Customize Waiting Room",
                "https://developers.cloudflare.com/waiting-room/reference/": "Waiting Room Reference",
                "https://developers.cloudflare.com/waiting-room/additional-options/": "Waiting Room Additional Options",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"cloudflare-{source_key}" if source_key else "cloudflare"
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
            # Clean common suffixes
            for suffix in [' | Cloudflare Docs', ' - Cloudflare Docs', ' | Cloudflare']:
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
                        "category": f"cloudflare-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)  # Respectful rate limit for Cloudflare docs

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
            self.log.info(f"=== Scraping cloudflare/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    CloudflareScraper(base, source_key).run()
