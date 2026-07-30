#!/usr/bin/env python3
"""Buildroot documentation scraper.

Covers:
  - user-manual: getting started, configuration (make menuconfig), package
    infrastructure (generic, cmake, autotools, python, luarocks), root filesystem,
    toolchain selection, boot and kernel, system configuration, tips and tricks
  - developer-guide: contributing, adding packages, package directory structure,
    patching, virtual packages, legal compliance, infrastructure internals
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


BR_MANUAL = "https://buildroot.org/downloads/manual/manual.html"


class BuildrootScraper(BaseScraper):
    """Scrape Buildroot official documentation."""

    SOURCES = {
        "user-manual": {
            "pages": {
                # Main manual (single-page, comprehensive)
                f"{BR_MANUAL}": "Buildroot User Manual",
                # Chunked manual sections
                "https://buildroot.org/downloads/manual/using-buildroot.html": "Using Buildroot",
                "https://buildroot.org/downloads/manual/getting-buildroot.html": "Getting Buildroot",
                "https://buildroot.org/downloads/manual/prerequisite.html": "System Requirements and Prerequisites",
                "https://buildroot.org/downloads/manual/starting-build.html": "Starting a Build",
                "https://buildroot.org/downloads/manual/configure.html": "Configuring Buildroot",
                "https://buildroot.org/downloads/manual/configure-other-components.html": "Configuring Other Components",
                "https://buildroot.org/downloads/manual/common-usage.html": "General Buildroot Usage",
                "https://buildroot.org/downloads/manual/make-tips.html": "Make Tips",
                "https://buildroot.org/downloads/manual/rebuild-pkg.html": "Understanding How to Rebuild Packages",
                "https://buildroot.org/downloads/manual/customize.html": "Project-specific Customization",
                "https://buildroot.org/downloads/manual/customize-rootfs.html": "Customizing the Generated Target Filesystem",
                "https://buildroot.org/downloads/manual/customize-store.html": "Storing the Buildroot Configuration",
                "https://buildroot.org/downloads/manual/customize-patches.html": "Customizing Packages",
                "https://buildroot.org/downloads/manual/customize-post-scripts.html": "Post-build and Post-image Scripts",
                # Toolchain
                "https://buildroot.org/downloads/manual/toolchain.html": "Toolchain",
                "https://buildroot.org/downloads/manual/ccache.html": "Using ccache in Buildroot",
                # Kernel and bootloaders
                "https://buildroot.org/downloads/manual/linux-kernel.html": "Linux Kernel",
                "https://buildroot.org/downloads/manual/uboot.html": "U-Boot Bootloader",
                "https://buildroot.org/downloads/manual/barebox.html": "Barebox Bootloader",
                # Filesystem images
                "https://buildroot.org/downloads/manual/rootfs-custom.html": "Root Filesystem Customization",
                # Additional docs page
                "https://buildroot.org/docs.html": "Buildroot Documentation Index",
                # FAQ and troubleshooting
                "https://buildroot.org/downloads/manual/faq-troubleshooting.html": "FAQ and Troubleshooting",
                # Resources
                "https://buildroot.org/downloads/manual/resources.html": "Resources",
            },
        },
        "developer-guide": {
            "pages": {
                # Package infrastructure
                "https://buildroot.org/downloads/manual/adding-packages.html": "Adding Packages",
                "https://buildroot.org/downloads/manual/adding-packages-directory.html": "Package Directory Structure",
                "https://buildroot.org/downloads/manual/adding-packages-generic.html": "Generic Package Infrastructure",
                "https://buildroot.org/downloads/manual/adding-packages-cmake.html": "CMake Package Infrastructure",
                "https://buildroot.org/downloads/manual/adding-packages-autotools.html": "Autotools Package Infrastructure",
                "https://buildroot.org/downloads/manual/adding-packages-python.html": "Python Package Infrastructure",
                "https://buildroot.org/downloads/manual/adding-packages-luarocks.html": "LuaRocks Package Infrastructure",
                "https://buildroot.org/downloads/manual/adding-packages-meson.html": "Meson Package Infrastructure",
                "https://buildroot.org/downloads/manual/adding-packages-waf.html": "Waf Package Infrastructure",
                "https://buildroot.org/downloads/manual/adding-packages-kconfig.html": "Kconfig Package Infrastructure",
                "https://buildroot.org/downloads/manual/adding-packages-virtual.html": "Virtual Packages",
                "https://buildroot.org/downloads/manual/adding-packages-gettext.html": "Gettext Integration and Interaction",
                "https://buildroot.org/downloads/manual/adding-packages-tips.html": "Tips and Tricks for Packages",
                # Contributing
                "https://buildroot.org/downloads/manual/contribute.html": "Contributing to Buildroot",
                "https://buildroot.org/downloads/manual/patch-policy.html": "Patch Policy",
                # Legal
                "https://buildroot.org/downloads/manual/legal-info.html": "Legal Notice and Licensing",
                # Beyond Buildroot
                "https://buildroot.org/downloads/manual/beyond-buildroot.html": "Beyond Buildroot",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"buildroot-{source_key}" if source_key else "buildroot"
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
            for suffix in [' - Buildroot', ' | Buildroot',
                           ' - The Buildroot User Manual',
                           ' :: Buildroot']:
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
                        "category": f"buildroot-{source_key}",
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
            self.log.info(f"=== Scraping buildroot/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    BuildrootScraper(base, source_key).run()
