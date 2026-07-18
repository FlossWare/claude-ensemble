#!/usr/bin/env python3
"""systemd documentation scraper.

Covers:
  - Man pages (www.freedesktop.org/software/systemd/man/latest/)
  - Design documents (systemd.io)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class SystemdScraper(BaseScraper):
    """Scrape systemd documentation from freedesktop.org and systemd.io."""

    SOURCES = {
        "manpages": {
            "pages": {
                # Core
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.html": "systemd",
                "https://www.freedesktop.org/software/systemd/man/latest/systemctl.html": "systemctl",
                "https://www.freedesktop.org/software/systemd/man/latest/journalctl.html": "journalctl",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-analyze.html": "systemd-analyze",
                # Unit types
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html": "systemd.unit",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html": "systemd.service",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.socket.html": "systemd.socket",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html": "systemd.timer",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.target.html": "systemd.target",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.mount.html": "systemd.mount",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.automount.html": "systemd.automount",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.swap.html": "systemd.swap",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.device.html": "systemd.device",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.path.html": "systemd.path",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.slice.html": "systemd.slice",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.scope.html": "systemd.scope",
                # Networking
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.network.html": "systemd.network",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.netdev.html": "systemd.netdev",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.link.html": "systemd.link",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-networkd.html": "systemd-networkd",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-resolved.html": "systemd-resolved",
                # System services
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-journald.html": "systemd-journald",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-logind.html": "systemd-logind",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-tmpfiles.html": "systemd-tmpfiles",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-sysctl.html": "systemd-sysctl",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-modules-load.html": "systemd-modules-load",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-boot.html": "systemd-boot",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-nspawn.html": "systemd-nspawn",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html": "systemd-run",
                # Control commands
                "https://www.freedesktop.org/software/systemd/man/latest/loginctl.html": "loginctl",
                "https://www.freedesktop.org/software/systemd/man/latest/timedatectl.html": "timedatectl",
                "https://www.freedesktop.org/software/systemd/man/latest/hostnamectl.html": "hostnamectl",
                "https://www.freedesktop.org/software/systemd/man/latest/localectl.html": "localectl",
                "https://www.freedesktop.org/software/systemd/man/latest/machinectl.html": "machinectl",
                "https://www.freedesktop.org/software/systemd/man/latest/busctl.html": "busctl",
                "https://www.freedesktop.org/software/systemd/man/latest/coredumpctl.html": "coredumpctl",
                "https://www.freedesktop.org/software/systemd/man/latest/resolvectl.html": "resolvectl",
                "https://www.freedesktop.org/software/systemd/man/latest/networkctl.html": "networkctl",
                # Execution environment
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html": "systemd.exec",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html": "systemd.resource-control",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.kill.html": "systemd.kill",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-notify.html": "systemd-notify",
                # Programming APIs
                "https://www.freedesktop.org/software/systemd/man/latest/sd-bus.html": "sd-bus",
                "https://www.freedesktop.org/software/systemd/man/latest/sd-event.html": "sd-event",
                "https://www.freedesktop.org/software/systemd/man/latest/sd-journal.html": "sd-journal",
                "https://www.freedesktop.org/software/systemd/man/latest/sd-daemon.html": "sd-daemon",
                # Newer services
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-homed.html": "systemd-homed",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-userdbd.html": "systemd-userdbd",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-oomd.html": "systemd-oomd",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-creds.html": "systemd-creds",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-sysext.html": "systemd-sysext",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-repart.html": "systemd-repart",
                # Additional commonly used
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.special.html": "systemd.special",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.generator.html": "systemd.generator",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.environment-generator.html": "systemd.environment-generator",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.preset.html": "systemd.preset",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-firstboot.html": "systemd-firstboot",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-machine-id-setup.html": "systemd-machine-id-setup",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-cryptsetup.html": "systemd-cryptsetup",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-ask-password.html": "systemd-ask-password",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-inhibit.html": "systemd-inhibit",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-cgls.html": "systemd-cgls",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-cgtop.html": "systemd-cgtop",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-escape.html": "systemd-escape",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-cat.html": "systemd-cat",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-delta.html": "systemd-delta",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-detect-virt.html": "systemd-detect-virt",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-id128.html": "systemd-id128",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-path.html": "systemd-path",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-socket-activate.html": "systemd-socket-activate",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd-stdio-bridge.html": "systemd-stdio-bridge",
                "https://www.freedesktop.org/software/systemd/man/latest/kernel-command-line.html": "kernel-command-line",
                "https://www.freedesktop.org/software/systemd/man/latest/bootctl.html": "bootctl",
                "https://www.freedesktop.org/software/systemd/man/latest/portablectl.html": "portablectl",
                "https://www.freedesktop.org/software/systemd/man/latest/userdbctl.html": "userdbctl",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.dnssd.html": "systemd.dnssd",
                "https://www.freedesktop.org/software/systemd/man/latest/systemd.nspawn.html": "systemd.nspawn",
                "https://www.freedesktop.org/software/systemd/man/latest/tmpfiles.d.html": "tmpfiles.d",
                "https://www.freedesktop.org/software/systemd/man/latest/sysctl.d.html": "sysctl.d",
                "https://www.freedesktop.org/software/systemd/man/latest/modules-load.d.html": "modules-load.d",
                "https://www.freedesktop.org/software/systemd/man/latest/sysusers.d.html": "sysusers.d",
                "https://www.freedesktop.org/software/systemd/man/latest/os-release.html": "os-release",
                "https://www.freedesktop.org/software/systemd/man/latest/machine-id.html": "machine-id",
                "https://www.freedesktop.org/software/systemd/man/latest/hostname.html": "hostname",
                "https://www.freedesktop.org/software/systemd/man/latest/locale.conf.html": "locale.conf",
                "https://www.freedesktop.org/software/systemd/man/latest/vconsole.conf.html": "vconsole.conf",
                "https://www.freedesktop.org/software/systemd/man/latest/timesyncd.conf.html": "timesyncd.conf",
                "https://www.freedesktop.org/software/systemd/man/latest/resolved.conf.html": "resolved.conf",
                "https://www.freedesktop.org/software/systemd/man/latest/journald.conf.html": "journald.conf",
                "https://www.freedesktop.org/software/systemd/man/latest/logind.conf.html": "logind.conf",
                "https://www.freedesktop.org/software/systemd/man/latest/networkd.conf.html": "networkd.conf",
                "https://www.freedesktop.org/software/systemd/man/latest/oomd.conf.html": "oomd.conf",
                "https://www.freedesktop.org/software/systemd/man/latest/homed.conf.html": "homed.conf",
                "https://www.freedesktop.org/software/systemd/man/latest/coredump.conf.html": "coredump.conf",
                "https://www.freedesktop.org/software/systemd/man/latest/sleep.conf.html": "sleep.conf",
                "https://www.freedesktop.org/software/systemd/man/latest/system.conf.html": "system.conf",
                "https://www.freedesktop.org/software/systemd/man/latest/user.conf.html": "user.conf",
            },
        },
        "design": {
            "pages": {
                # Design documents on systemd.io
                "https://systemd.io/": "systemd System and Service Manager",
                "https://systemd.io/THE_CASE_FOR_THE_USR_MERGE": "The Case for the /usr Merge",
                "https://systemd.io/RETHINKING_PID1": "Rethinking PID 1",
                "https://systemd.io/PREDICTABLE_INTERFACE_NAMES": "Predictable Network Interface Names",
                "https://systemd.io/CONTAINER_INTERFACE": "Container Interface",
                "https://systemd.io/JOURNAL_FILE_FORMAT": "Journal File Format",
                "https://systemd.io/INHIBITOR_LOCKS": "Inhibitor Locks",
                "https://systemd.io/CGROUP_DELEGATION": "Control Group APIs and Delegation",
                "https://systemd.io/PASSWORD_AGENTS": "Password Agents",
                "https://systemd.io/HOME_DIRECTORY": "Home Directories",
                "https://systemd.io/CREDENTIALS": "Credentials",
                "https://systemd.io/PORTABLE_SERVICES": "Portable Services",
                "https://systemd.io/BOOT_LOADER_SPECIFICATION": "Boot Loader Specification",
                "https://systemd.io/BOOT_LOADER_INTERFACE": "Boot Loader Interface",
                "https://systemd.io/DISCOVERABLE_PARTITIONS": "Discoverable Partitions Specification",
                "https://systemd.io/AUTOMATIC_BOOT_ASSESSMENT": "Automatic Boot Assessment",
                "https://systemd.io/TEMPORARY_DIRECTORIES": "Using /tmp/ and /var/tmp/ Safely",
                "https://systemd.io/UIDS-GIDS": "Users, Groups, UIDs and GIDs on systemd Systems",
                "https://systemd.io/USER_RECORD": "JSON User Records",
                "https://systemd.io/GROUP_RECORD": "JSON Group Records",
                "https://systemd.io/USER_NAMES": "User/Group Name Syntax",
                "https://systemd.io/DESKTOP_ENVIRONMENTS": "Desktop Environments",
                "https://systemd.io/NETWORK_ONLINE": "Network Configuration Synchronization Points",
                "https://systemd.io/SYSLOG": "syslog Interface",
                "https://systemd.io/WRITING_NETWORK_CONFIGURATION_MANAGERS": "Writing Network Configuration Managers",
                "https://systemd.io/WRITING_DISPLAY_MANAGERS": "Writing Display Managers",
                "https://systemd.io/WRITING_RESOLVER_CLIENTS": "Writing Resolver Clients",
                "https://systemd.io/CONVERTING_TO_SYSTEMD": "Converting Existing Users to systemd",
                "https://systemd.io/ENVIRONMENT": "Known Environment Variables",
                "https://systemd.io/CATALOG": "Message Catalog Entries",
                "https://systemd.io/BUILDING_IMAGES": "Safely Building Images",
                "https://systemd.io/FILE_DESCRIPTOR_STORE": "The File Descriptor Store",
                "https://systemd.io/OPTIMIZATIONS": "systemd Optimizations",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"systemd-{source_key}" if source_key else "systemd"
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
            for suffix in [
                ' — systemd',
                ' - freedesktop.org',
                ' - systemd.io',
            ]:
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
                        "category": "systemd-docs",
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
            self.log.info(f"=== Scraping systemd/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    SystemdScraper(base, source_key).run()
