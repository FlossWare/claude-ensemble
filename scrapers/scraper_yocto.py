#!/usr/bin/env python3
"""Yocto Project documentation scraper.

Covers:
  - overview: Yocto Project overview, what it is, concepts, release info
  - development: BitBake, recipes, layers, images, devtool, development tasks
  - reference: variables glossary, QA checks, classes, tasks, features
  - sdk: SDK manual, extensible SDK, standard SDK usage
  - bsp: BSP developer guide, BSP layers, hardware configuration
  - kernel: kernel development manual, kernel customization, defconfig, patches
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


YP = "https://docs.yoctoproject.org"


class YoctoScraper(BaseScraper):
    """Scrape Yocto Project official documentation."""

    SOURCES = {
        "overview": {
            "pages": {
                f"{YP}": "Yocto Project Documentation Index",
                f"{YP}/overview-manual/yp-intro.html": "Introducing the Yocto Project",
                f"{YP}/overview-manual/development-environment.html": "The Yocto Project Development Environment",
                f"{YP}/overview-manual/concepts.html": "Yocto Project Concepts",
                f"{YP}/brief-yoctoprojectqs/index.html": "Yocto Project Quick Build",
                f"{YP}/what-i-wish-id-known.html": "What I Wish I'd Known About Yocto",
                f"{YP}/transitioning-to-a-custom-environment.html": "Transitioning to a Custom Environment",
                f"{YP}/ref-manual/release-process.html": "Yocto Project Release and Versioning",
                f"{YP}/ref-manual/system-requirements.html": "System Requirements",
                f"{YP}/ref-manual/terms.html": "Yocto Project Terms",
            },
        },
        "development": {
            "pages": {
                # Development Tasks Manual
                f"{YP}/dev-manual/start.html": "Setting Up to Use the Yocto Project",
                f"{YP}/dev-manual/layers.html": "Understanding and Creating Layers",
                f"{YP}/dev-manual/customizing-images.html": "Customizing Images",
                f"{YP}/dev-manual/new-recipe.html": "Writing a New Recipe",
                f"{YP}/dev-manual/new-machine.html": "Adding a New Machine",
                f"{YP}/dev-manual/upgrading-recipes.html": "Upgrading Recipes",
                f"{YP}/dev-manual/temporary-source-code.html": "Finding Temporary Source Code",
                f"{YP}/dev-manual/quilt.html": "Using Quilt in Your Workflow",
                f"{YP}/dev-manual/devtool.html": "Using devtool in Your Workflow",
                f"{YP}/dev-manual/packages.html": "Working with Packages",
                f"{YP}/dev-manual/common-tasks.html": "Common Development Tasks",
                f"{YP}/dev-manual/debugging.html": "Debugging Tools and Techniques",
                f"{YP}/dev-manual/runtime-testing.html": "Performing Automated Runtime Testing",
                f"{YP}/dev-manual/speeding-up-build.html": "Speeding Up a Build",
                f"{YP}/dev-manual/read-only-rootfs.html": "Creating a Read-Only Root Filesystem",
                f"{YP}/dev-manual/wayland.html": "Using Wayland and Weston",
                f"{YP}/dev-manual/gobject-introspection.html": "Using GObject Introspection",
                f"{YP}/dev-manual/init-manager.html": "Selecting an Initialization Manager",
                f"{YP}/dev-manual/external-scm.html": "Working with Source Control Managers",
                # BitBake User Manual
                f"{YP}/bitbake-user-manual/bitbake-user-manual-intro.html": "BitBake User Manual Introduction",
                f"{YP}/bitbake-user-manual/bitbake-user-manual-execution.html": "BitBake Execution",
                f"{YP}/bitbake-user-manual/bitbake-user-manual-metadata.html": "BitBake Syntax and Operators",
                f"{YP}/bitbake-user-manual/bitbake-user-manual-fetching.html": "BitBake File Download Support",
                f"{YP}/bitbake-user-manual/bitbake-user-manual-ref-variables.html": "BitBake Variables Glossary",
                f"{YP}/bitbake-user-manual/bitbake-user-manual-hello.html": "BitBake Hello World Example",
            },
        },
        "reference": {
            "pages": {
                # Reference Manual
                f"{YP}/ref-manual/variables.html": "Variables Glossary",
                f"{YP}/ref-manual/tasks.html": "Tasks",
                f"{YP}/ref-manual/classes.html": "Classes",
                f"{YP}/ref-manual/devtool-reference.html": "devtool Quick Reference",
                f"{YP}/ref-manual/qa-checks.html": "QA Error and Warning Messages",
                f"{YP}/ref-manual/images.html": "Images",
                f"{YP}/ref-manual/features.html": "Features",
                f"{YP}/ref-manual/faq.html": "FAQ",
                f"{YP}/ref-manual/structure.html": "Source Directory Structure",
                f"{YP}/ref-manual/kickstart.html": "OpenEmbedded Kickstart (.wks) Reference",
                f"{YP}/ref-manual/resources.html": "Contributions and Additional Information",
                # Test Manual
                f"{YP}/test-manual/intro.html": "Yocto Project Test Environment Manual",
                f"{YP}/test-manual/test-process.html": "Project Testing and Release Process",
                f"{YP}/test-manual/understand-autobuilder.html": "Understanding the Yocto Project Autobuilder",
                f"{YP}/test-manual/reproducible-builds.html": "Reproducible Builds",
            },
        },
        "sdk": {
            "pages": {
                # SDK Manual
                f"{YP}/sdk-manual/intro.html": "SDK Manual Introduction",
                f"{YP}/sdk-manual/extensible.html": "Using the Extensible SDK",
                f"{YP}/sdk-manual/using.html": "Using the Standard SDK",
                f"{YP}/sdk-manual/working-projects.html": "Using the SDK Toolchain Directly",
                f"{YP}/sdk-manual/appendix-obtain.html": "Obtaining the SDK",
                f"{YP}/sdk-manual/appendix-customizing.html": "Customizing the Extensible SDK",
                f"{YP}/sdk-manual/appendix-customizing-standard.html": "Customizing the Standard SDK",
            },
        },
        "bsp": {
            "pages": {
                # BSP Developer Guide
                f"{YP}/bsp-guide/bsp.html": "Board Support Packages (BSP) Developer Guide",
                f"{YP}/bsp-guide/bsp-filelayout.html": "BSP File Layout",
                f"{YP}/bsp-guide/bsp-filelayout-kernel.html": "BSP Kernel-Related File Layout",
                f"{YP}/bsp-guide/bsp-filelayout-recipes.html": "BSP Recipes File Layout",
                f"{YP}/bsp-guide/bsp-filelayout-misc.html": "BSP Miscellaneous File Layout",
                # Profile and Tracing Manual
                f"{YP}/profile-manual/intro.html": "Yocto Project Profiling and Tracing Manual",
                f"{YP}/profile-manual/arch.html": "Overall Architecture of the Tracing and Profiling Tools",
                f"{YP}/profile-manual/usage.html": "Basic Usage of LTTng, perf, ftrace, and SystemTap",
            },
        },
        "kernel": {
            "pages": {
                # Kernel Development Manual
                f"{YP}/kernel-dev/intro.html": "Kernel Development Manual Introduction",
                f"{YP}/kernel-dev/common.html": "Common Tasks for Kernel Development",
                f"{YP}/kernel-dev/advanced.html": "Working with Advanced Metadata (Yocto Kernel Tools)",
                f"{YP}/kernel-dev/concepts-appx.html": "Kernel Concepts Appendix",
                f"{YP}/kernel-dev/maint-appx.html": "Kernel Maintenance Appendix",
                # Toaster Manual
                f"{YP}/toaster-manual/intro.html": "Toaster Manual Introduction",
                f"{YP}/toaster-manual/start.html": "Setting Up and Using Toaster",
                f"{YP}/toaster-manual/reference.html": "Toaster Manual Reference",
                # Migration Guides
                f"{YP}/migration-guides/index.html": "Migration Guides Index",
                f"{YP}/migration-guides/migration-general.html": "General Migration Information",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"yocto-{source_key}" if source_key else "yocto"
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
            for suffix in [' — The Yocto Project', ' - Yocto Project',
                           ' — Yocto Project Documentation',
                           ' - Yocto Project Documentation',
                           ' | Yocto Project']:
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
                        "category": f"yocto-{source_key}",
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
            self.log.info(f"=== Scraping yocto/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    YoctoScraper(base, source_key).run()
