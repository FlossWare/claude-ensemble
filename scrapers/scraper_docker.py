#!/usr/bin/env python3
"""Docker documentation scraper.

Covers:
  - Getting started (overview, installation)
  - Guides (tutorials, development best practices, language-specific)
  - Manuals (Engine, Compose, Build, Hub)
  - Reference (Dockerfile, CLI)
  - Security (content trust, secrets, rootless, seccomp, AppArmor)
  - Networking (bridge, host, overlay, macvlan, DNS)
  - Storage (volumes, bind mounts, tmpfs, storage drivers)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class DockerScraper(BaseScraper):
    """Scrape Docker documentation from docs.docker.com."""

    SOURCES = {
        "getting-started": {
            "pages": {
                "https://docs.docker.com/get-started/": "Get Started",
                "https://docs.docker.com/get-started/overview/": "Docker Overview",
                "https://docs.docker.com/get-started/introduction/": "Introduction",
                "https://docs.docker.com/engine/install/": "Install Docker Engine",
                "https://docs.docker.com/engine/install/ubuntu/": "Install on Ubuntu",
                "https://docs.docker.com/engine/install/debian/": "Install on Debian",
                "https://docs.docker.com/engine/install/fedora/": "Install on Fedora",
                "https://docs.docker.com/engine/install/centos/": "Install on CentOS",
                "https://docs.docker.com/engine/install/rhel/": "Install on RHEL",
                "https://docs.docker.com/desktop/install/mac-install/": "Install on Mac",
                "https://docs.docker.com/desktop/install/windows-install/": "Install on Windows",
                "https://docs.docker.com/desktop/install/linux/": "Docker Desktop for Linux",
            },
        },
        "guides": {
            "pages": {
                "https://docs.docker.com/get-started/workshop/": "Workshop",
                "https://docs.docker.com/get-started/workshop/02_our_app/": "Our Application",
                "https://docs.docker.com/get-started/workshop/03_updating_app/": "Updating the App",
                "https://docs.docker.com/get-started/workshop/04_sharing_app/": "Sharing the App",
                "https://docs.docker.com/get-started/workshop/05_persisting_data/": "Persisting Data",
                "https://docs.docker.com/get-started/workshop/06_bind_mounts/": "Bind Mounts",
                "https://docs.docker.com/get-started/workshop/07_multi_container/": "Multi-Container Apps",
                "https://docs.docker.com/get-started/workshop/08_using_compose/": "Using Compose",
                "https://docs.docker.com/get-started/workshop/09_image_best/": "Image Building Best Practices",
                "https://docs.docker.com/get-started/workshop/10_what_next/": "What Next",
                "https://docs.docker.com/develop/": "Develop with Docker",
                "https://docs.docker.com/develop/dev-best-practices/": "Development Best Practices",
                "https://docs.docker.com/language/python/": "Python Guide",
                "https://docs.docker.com/language/nodejs/": "Node.js Guide",
                "https://docs.docker.com/language/golang/": "Go Guide",
                "https://docs.docker.com/language/java/": "Java Guide",
                "https://docs.docker.com/language/rust/": "Rust Guide",
                "https://docs.docker.com/language/dotnet/": ".NET Guide",
                "https://docs.docker.com/language/php/": "PHP Guide",
            },
        },
        "engine": {
            "pages": {
                "https://docs.docker.com/engine/": "Docker Engine Overview",
                "https://docs.docker.com/config/daemon/": "Configure the Docker Daemon",
                "https://docs.docker.com/config/daemon/start/": "Start the Daemon",
                "https://docs.docker.com/config/daemon/logs/": "Daemon Logs",
                "https://docs.docker.com/config/daemon/remote-access/": "Remote Access",
                "https://docs.docker.com/config/containers/start-containers-automatically/": "Start Containers Automatically",
                "https://docs.docker.com/config/containers/resource_constraints/": "Resource Constraints",
                "https://docs.docker.com/config/containers/logging/configure/": "Configure Logging",
                "https://docs.docker.com/config/containers/logging/dual-logging/": "Dual Logging",
                "https://docs.docker.com/config/containers/logging/log_tags/": "Log Tags",
                "https://docs.docker.com/config/containers/logging/plugins/": "Logging Plugins",
                "https://docs.docker.com/config/containers/multi-service_container/": "Multi-Service Container",
                "https://docs.docker.com/config/containers/runmetrics/": "Runtime Metrics",
                "https://docs.docker.com/engine/daemon/prometheus/": "Prometheus Metrics",
                "https://docs.docker.com/config/labels-custom-metadata/": "Labels and Custom Metadata",
                "https://docs.docker.com/config/pruning/": "Prune Unused Objects",
            },
        },
        "compose": {
            "pages": {
                "https://docs.docker.com/compose/": "Docker Compose Overview",
                "https://docs.docker.com/compose/install/": "Install Compose",
                "https://docs.docker.com/compose/gettingstarted/": "Getting Started with Compose",
                "https://docs.docker.com/compose/features-uses/": "Features and Uses",
                "https://docs.docker.com/compose/how-tos/environment-variables/": "Environment Variables",
                "https://docs.docker.com/compose/how-tos/networking/": "Networking in Compose",
                "https://docs.docker.com/compose/how-tos/volumes/": "Volumes in Compose",
                "https://docs.docker.com/compose/how-tos/profiles/": "Profiles",
                "https://docs.docker.com/compose/how-tos/startup-order/": "Startup Order",
                "https://docs.docker.com/compose/how-tos/gpu-support/": "GPU Support",
                "https://docs.docker.com/compose/how-tos/production/": "Use Compose in Production",
                "https://docs.docker.com/compose/how-tos/project-name/": "Project Name",
                "https://docs.docker.com/compose/compose-file/": "Compose File Reference",
                "https://docs.docker.com/compose/compose-file/05-services/": "Services",
                "https://docs.docker.com/compose/compose-file/06-networks/": "Networks",
                "https://docs.docker.com/compose/compose-file/07-volumes/": "Volumes",
                "https://docs.docker.com/compose/compose-file/08-configs/": "Configs",
                "https://docs.docker.com/compose/compose-file/09-secrets/": "Secrets",
                "https://docs.docker.com/compose/compose-file/build/": "Build",
                "https://docs.docker.com/compose/compose-file/deploy/": "Deploy",
            },
        },
        "build": {
            "pages": {
                "https://docs.docker.com/build/": "Docker Build Overview",
                "https://docs.docker.com/build/concepts/overview/": "Build Concepts Overview",
                "https://docs.docker.com/build/concepts/dockerfile/": "Dockerfile Concepts",
                "https://docs.docker.com/build/concepts/context/": "Build Context",
                "https://docs.docker.com/build/building/multi-stage/": "Multi-Stage Builds",
                "https://docs.docker.com/build/building/multi-platform/": "Multi-Platform Builds",
                "https://docs.docker.com/build/building/variables/": "Build Variables",
                "https://docs.docker.com/build/building/secrets/": "Build Secrets",
                "https://docs.docker.com/build/building/best-practices/": "Build Best Practices",
                "https://docs.docker.com/build/cache/": "Build Cache",
                "https://docs.docker.com/build/cache/invalidation/": "Cache Invalidation",
                "https://docs.docker.com/build/cache/backends/": "Cache Backends",
                "https://docs.docker.com/build/buildkit/": "BuildKit",
                "https://docs.docker.com/build/builders/": "Builders",
                "https://docs.docker.com/build/exporters/": "Exporters",
                "https://docs.docker.com/build/bake/": "Bake",
                "https://docs.docker.com/reference/dockerfile/": "Dockerfile Reference",
            },
        },
        "hub": {
            "pages": {
                "https://docs.docker.com/docker-hub/": "Docker Hub Overview",
                "https://docs.docker.com/docker-hub/repos/": "Repositories",
                "https://docs.docker.com/docker-hub/repos/create/": "Create Repositories",
                "https://docs.docker.com/docker-hub/repos/manage/": "Manage Repositories",
                "https://docs.docker.com/docker-hub/builds/": "Automated Builds",
                "https://docs.docker.com/security/for-developers/access-tokens/": "Access Tokens",
                "https://docs.docker.com/docker-hub/official_images/": "Official Images",
                "https://docs.docker.com/docker-hub/download-rate-limit/": "Download Rate Limit",
            },
        },
        "cli-reference": {
            "pages": {
                "https://docs.docker.com/reference/cli/docker/": "Docker CLI Reference",
                "https://docs.docker.com/reference/cli/docker/container/run/": "docker run",
                "https://docs.docker.com/reference/cli/docker/image/build/": "docker build",
                "https://docs.docker.com/reference/cli/docker/image/push/": "docker push",
                "https://docs.docker.com/reference/cli/docker/image/pull/": "docker pull",
                "https://docs.docker.com/reference/cli/docker/container/exec/": "docker exec",
                "https://docs.docker.com/reference/cli/docker/container/ps/": "docker ps",
                "https://docs.docker.com/reference/cli/docker/container/logs/": "docker logs",
                "https://docs.docker.com/reference/cli/docker/inspect/": "docker inspect",
                "https://docs.docker.com/reference/cli/docker/container/stop/": "docker stop",
                "https://docs.docker.com/reference/cli/docker/container/rm/": "docker rm",
                "https://docs.docker.com/reference/cli/docker/container/start/": "docker start",
                "https://docs.docker.com/reference/cli/docker/container/create/": "docker create",
                "https://docs.docker.com/reference/cli/docker/container/cp/": "docker cp",
                "https://docs.docker.com/reference/cli/docker/container/commit/": "docker commit",
                "https://docs.docker.com/reference/cli/docker/container/attach/": "docker attach",
                "https://docs.docker.com/reference/cli/docker/image/ls/": "docker images",
                "https://docs.docker.com/reference/cli/docker/image/rm/": "docker rmi",
                "https://docs.docker.com/reference/cli/docker/image/tag/": "docker tag",
                "https://docs.docker.com/reference/cli/docker/image/history/": "docker history",
                "https://docs.docker.com/reference/cli/docker/network/": "docker network",
                "https://docs.docker.com/reference/cli/docker/network/create/": "docker network create",
                "https://docs.docker.com/reference/cli/docker/network/ls/": "docker network ls",
                "https://docs.docker.com/reference/cli/docker/network/connect/": "docker network connect",
                "https://docs.docker.com/reference/cli/docker/network/inspect/": "docker network inspect",
                "https://docs.docker.com/reference/cli/docker/volume/": "docker volume",
                "https://docs.docker.com/reference/cli/docker/volume/create/": "docker volume create",
                "https://docs.docker.com/reference/cli/docker/volume/ls/": "docker volume ls",
                "https://docs.docker.com/reference/cli/docker/volume/inspect/": "docker volume inspect",
                "https://docs.docker.com/reference/cli/docker/compose/": "docker compose",
                "https://docs.docker.com/reference/cli/docker/compose/up/": "docker compose up",
                "https://docs.docker.com/reference/cli/docker/compose/down/": "docker compose down",
                "https://docs.docker.com/reference/cli/docker/compose/build/": "docker compose build",
                "https://docs.docker.com/reference/cli/docker/compose/ps/": "docker compose ps",
                "https://docs.docker.com/reference/cli/docker/compose/logs/": "docker compose logs",
                "https://docs.docker.com/reference/cli/docker/system/prune/": "docker system prune",
                "https://docs.docker.com/reference/cli/docker/system/df/": "docker system df",
                "https://docs.docker.com/reference/cli/docker/system/info/": "docker system info",
                "https://docs.docker.com/reference/cli/docker/buildx/": "docker buildx",
                "https://docs.docker.com/reference/cli/docker/buildx/build/": "docker buildx build",
            },
        },
        "security": {
            "pages": {
                "https://docs.docker.com/engine/security/": "Security Overview",
                "https://docs.docker.com/engine/security/trust/": "Content Trust",
                "https://docs.docker.com/engine/security/certificates/": "Certificates",
                "https://docs.docker.com/engine/security/protect-access/": "Protect Docker Daemon Socket",
                "https://docs.docker.com/engine/security/rootless/": "Rootless Mode",
                "https://docs.docker.com/engine/security/userns-remap/": "User Namespace Remapping",
                "https://docs.docker.com/engine/security/seccomp/": "Seccomp Security Profiles",
                "https://docs.docker.com/engine/security/apparmor/": "AppArmor Security Profiles",
                "https://docs.docker.com/engine/swarm/secrets/": "Manage Secrets",
                "https://docs.docker.com/scout/": "Docker Scout",
                "https://docs.docker.com/scout/quickstart/": "Scout Quickstart",
            },
        },
        "networking": {
            "pages": {
                "https://docs.docker.com/engine/network/": "Networking Overview",
                "https://docs.docker.com/engine/network/drivers/": "Network Drivers",
                "https://docs.docker.com/engine/network/drivers/bridge/": "Bridge Network",
                "https://docs.docker.com/engine/network/drivers/host/": "Host Network",
                "https://docs.docker.com/engine/network/drivers/overlay/": "Overlay Network",
                "https://docs.docker.com/engine/network/drivers/macvlan/": "Macvlan Network",
                "https://docs.docker.com/engine/network/drivers/ipvlan/": "IPvlan Network",
                "https://docs.docker.com/engine/network/drivers/none/": "None Network",
                "https://docs.docker.com/engine/network/packet-filtering-firewalls/": "Packet Filtering and Firewalls",
                "https://docs.docker.com/engine/network/proxy/": "Configure Docker to Use a Proxy",
            },
        },
        "storage": {
            "pages": {
                "https://docs.docker.com/engine/storage/": "Storage Overview",
                "https://docs.docker.com/engine/storage/volumes/": "Volumes",
                "https://docs.docker.com/engine/storage/bind-mounts/": "Bind Mounts",
                "https://docs.docker.com/engine/storage/tmpfs/": "tmpfs Mounts",
                "https://docs.docker.com/engine/storage/storagedriver/": "Storage Drivers",
                "https://docs.docker.com/engine/storage/storagedriver/select-storage-driver/": "Select a Storage Driver",
                "https://docs.docker.com/engine/storage/storagedriver/overlayfs-driver/": "OverlayFS Driver",
                "https://docs.docker.com/engine/storage/storagedriver/btrfs-driver/": "Btrfs Driver",
                "https://docs.docker.com/engine/storage/storagedriver/zfs-driver/": "ZFS Driver",
                "https://docs.docker.com/engine/storage/storagedriver/device-mapper-driver/": "Device Mapper Driver",
                "https://docs.docker.com/engine/storage/troubleshoot/": "Troubleshoot Storage",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"docker-docs-{source_key}" if source_key else "docker-docs"
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
            for suffix in [' | Docker Docs', ' | Docker Documentation',
                           ' | Docker', ' - Docker Docs',
                           ' - Docker Documentation']:
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
                        "category": "docker-docs",
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
            self.log.info(f"=== Scraping docker-docs/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    DockerScraper(base, source_key).run()
