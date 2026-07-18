#!/usr/bin/env python3
"""Linux Kernel documentation scraper.

Covers:
  - Admin guide (kernel parameters, sysctl, modules, security, power management)
  - Process (coding style, submitting patches, license rules)
  - Networking (ip-sysctl, netfilter, bonding, bridging, VLANs, WiFi)
  - Filesystems (ext4, btrfs, XFS, NFS, FUSE, proc, sysfs, overlayfs)
  - Driver API (device model, USB, PCI, I2C, SPI, GPIO)
  - Security (LSM, SELinux, AppArmor, seccomp, IMA)
  - Core API (kobject, workqueue, timers, locking, memory allocation)
  - Tracing (ftrace, perf, eBPF, kprobes)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class KernelDocsScraper(BaseScraper):
    """Scrape Linux Kernel documentation from kernel.org."""

    SOURCES = {
        "admin-guide": {
            "pages": {
                # Kernel parameters and configuration
                "https://www.kernel.org/doc/html/latest/admin-guide/index.html": "Admin Guide Index",
                "https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html": "Kernel Parameters",
                "https://www.kernel.org/doc/html/latest/admin-guide/sysctl/index.html": "Sysctl Index",
                "https://www.kernel.org/doc/html/latest/admin-guide/sysctl/kernel.html": "Sysctl - Kernel",
                "https://www.kernel.org/doc/html/latest/admin-guide/sysctl/vm.html": "Sysctl - VM",
                "https://www.kernel.org/doc/html/latest/admin-guide/sysctl/net.html": "Sysctl - Net",
                "https://www.kernel.org/doc/html/latest/admin-guide/sysctl/fs.html": "Sysctl - FS",
                "https://www.kernel.org/doc/html/latest/admin-guide/sysctl/abi.html": "Sysctl - ABI",
                "https://www.kernel.org/doc/html/latest/admin-guide/module-signing.html": "Module Signing",
                "https://www.kernel.org/doc/html/latest/admin-guide/reporting-issues.html": "Reporting Issues",
                "https://www.kernel.org/doc/html/latest/admin-guide/security-bugs.html": "Security Bugs",
                "https://www.kernel.org/doc/html/latest/admin-guide/init.html": "Init",
                "https://www.kernel.org/doc/html/latest/admin-guide/initrd.html": "Initrd",
                "https://www.kernel.org/doc/html/latest/admin-guide/ramdisk.html": "Ramdisk",
                "https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v1/index.html": "Cgroup v1",
                "https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html": "Cgroup v2",
                "https://www.kernel.org/doc/html/latest/admin-guide/numa_memory_policy.html": "NUMA Memory Policy",
                "https://www.kernel.org/doc/html/latest/admin-guide/mm/index.html": "Memory Management",
                "https://www.kernel.org/doc/html/latest/admin-guide/mm/concepts.html": "MM Concepts",
                "https://www.kernel.org/doc/html/latest/admin-guide/mm/hugetlbpage.html": "HugeTLB Pages",
                "https://www.kernel.org/doc/html/latest/admin-guide/mm/ksm.html": "KSM (Kernel Samepage Merging)",
                "https://www.kernel.org/doc/html/latest/admin-guide/mm/transhuge.html": "Transparent Hugepages",
                "https://www.kernel.org/doc/html/latest/admin-guide/mm/zswap.html": "Zswap",
                "https://www.kernel.org/doc/html/latest/admin-guide/pm/index.html": "Power Management",
                "https://www.kernel.org/doc/html/latest/admin-guide/pm/cpufreq.html": "CPUFreq",
                "https://www.kernel.org/doc/html/latest/admin-guide/pm/cpuidle.html": "CPUIdle",
                "https://www.kernel.org/doc/html/latest/admin-guide/pm/sleep-states.html": "Sleep States",
                "https://www.kernel.org/doc/html/latest/admin-guide/pm/suspend-flows.html": "Suspend Flows",
                "https://www.kernel.org/doc/html/latest/power/pm_qos_interface.html": "PM QoS Interface",
                "https://www.kernel.org/doc/html/latest/admin-guide/devices.html": "Devices",
                "https://www.kernel.org/doc/html/latest/admin-guide/abi.html": "ABI",
                "https://www.kernel.org/doc/html/latest/admin-guide/bootconfig.html": "Boot Config",
                "https://www.kernel.org/doc/html/latest/admin-guide/kdump/kdump.html": "Kdump",
                "https://www.kernel.org/doc/html/latest/admin-guide/perf-security.html": "Perf Security",
                "https://www.kernel.org/doc/html/latest/admin-guide/dynamic-debug-howto.html": "Dynamic Debug",
                "https://www.kernel.org/doc/html/latest/admin-guide/bug-hunting.html": "Bug Hunting",
                "https://www.kernel.org/doc/html/latest/admin-guide/bug-bisect.html": "Bug Bisect",
                "https://www.kernel.org/doc/html/latest/admin-guide/tainted-kernels.html": "Tainted Kernels",
            },
        },
        "process": {
            "pages": {
                "https://www.kernel.org/doc/html/latest/process/index.html": "Process Index",
                "https://www.kernel.org/doc/html/latest/process/coding-style.html": "Coding Style",
                "https://www.kernel.org/doc/html/latest/process/submitting-patches.html": "Submitting Patches",
                "https://www.kernel.org/doc/html/latest/process/submit-checklist.html": "Submit Checklist",
                "https://www.kernel.org/doc/html/latest/process/license-rules.html": "License Rules",
                "https://www.kernel.org/doc/html/latest/process/management-style.html": "Management Style",
                "https://www.kernel.org/doc/html/latest/process/email-clients.html": "Email Clients",
                "https://www.kernel.org/doc/html/latest/process/howto.html": "HOWTO",
                "https://www.kernel.org/doc/html/latest/process/kernel-docs.html": "Kernel Docs",
                "https://www.kernel.org/doc/html/latest/process/development-process.html": "Development Process",
                "https://www.kernel.org/doc/html/latest/process/maintainer-pgp-guide.html": "Maintainer PGP Guide",
                "https://www.kernel.org/doc/html/latest/process/kernel-enforcement-statement.html": "Kernel Enforcement Statement",
                "https://www.kernel.org/doc/html/latest/process/stable-kernel-rules.html": "Stable Kernel Rules",
                "https://www.kernel.org/doc/html/latest/process/stable-api-nonsense.html": "Stable API Nonsense",
                "https://www.kernel.org/doc/html/latest/process/changes.html": "Minimal Requirements",
                "https://www.kernel.org/doc/html/latest/process/programming-language.html": "Programming Language",
            },
        },
        "networking": {
            "pages": {
                "https://www.kernel.org/doc/html/latest/networking/index.html": "Networking Index",
                "https://www.kernel.org/doc/html/latest/networking/ip-sysctl.html": "IP Sysctl",
                "https://www.kernel.org/doc/html/latest/networking/netfilter.html": "Netfilter",
                "https://www.kernel.org/doc/html/latest/networking/nf_conntrack-sysctl.html": "Conntrack Sysctl",
                "https://www.kernel.org/doc/html/latest/networking/bonding.html": "Bonding",
                "https://www.kernel.org/doc/html/latest/networking/bridge.html": "Bridge",
                "https://www.kernel.org/doc/html/latest/networking/vlan.html": "VLAN (802.1Q)",
                "https://www.kernel.org/doc/html/latest/networking/iptables.html": "Iptables",
                "https://www.kernel.org/doc/html/latest/networking/nf_flowtable.html": "Nf Flowtable",
                "https://www.kernel.org/doc/html/latest/networking/tc-actions-env-rules.html": "TC Actions",
                "https://www.kernel.org/doc/html/latest/networking/tuntap.html": "TUN/TAP",
                "https://www.kernel.org/doc/html/latest/networking/vxlan.html": "VXLAN",
                "https://www.kernel.org/doc/html/latest/networking/wireguard.html": "WireGuard",
                "https://www.kernel.org/doc/html/latest/networking/openvswitch.html": "Open vSwitch",
                "https://www.kernel.org/doc/html/latest/networking/ethtool-netlink.html": "Ethtool Netlink",
                "https://www.kernel.org/doc/html/latest/networking/af_xdp.html": "AF_XDP",
                "https://www.kernel.org/doc/html/latest/networking/xdp-rx-metadata.html": "XDP RX Metadata",
                "https://www.kernel.org/doc/html/latest/networking/filter.html": "BPF Filter",
                "https://www.kernel.org/doc/html/latest/networking/netdevices.html": "Net Devices",
                "https://www.kernel.org/doc/html/latest/networking/netdev-FAQ.html": "Netdev FAQ",
                "https://www.kernel.org/doc/html/latest/networking/scaling.html": "Scaling",
                "https://www.kernel.org/doc/html/latest/networking/segmentation-offloads.html": "Segmentation Offloads",
                "https://www.kernel.org/doc/html/latest/networking/multiqueue.html": "Multiqueue",
                "https://www.kernel.org/doc/html/latest/networking/timestamping.html": "Timestamping",
                "https://www.kernel.org/doc/html/latest/networking/kcm.html": "KCM",
                "https://www.kernel.org/doc/html/latest/networking/devlink/index.html": "Devlink",
                "https://www.kernel.org/doc/html/latest/networking/net_failover.html": "Net Failover",
                "https://www.kernel.org/doc/html/latest/networking/page_pool.html": "Page Pool",
                "https://www.kernel.org/doc/html/latest/networking/can.html": "CAN Bus",
                "https://www.kernel.org/doc/html/latest/networking/bluetooth.html": "Bluetooth",
                "https://www.kernel.org/doc/html/latest/networking/mac80211-injection.html": "WiFi Injection",
                "https://www.kernel.org/doc/html/latest/networking/regulatory.html": "Wireless Regulatory",
            },
        },
        "filesystems": {
            "pages": {
                "https://www.kernel.org/doc/html/latest/filesystems/index.html": "Filesystems Index",
                "https://www.kernel.org/doc/html/latest/filesystems/ext4/index.html": "ext4",
                "https://www.kernel.org/doc/html/latest/filesystems/ext4/overview.html": "ext4 Overview",
                "https://www.kernel.org/doc/html/latest/filesystems/ext4/blockgroup.html": "ext4 Block Groups",
                "https://www.kernel.org/doc/html/latest/filesystems/btrfs.html": "Btrfs",
                "https://www.kernel.org/doc/html/latest/filesystems/xfs/index.html": "XFS",
                "https://www.kernel.org/doc/html/latest/filesystems/xfs/xfs-delayed-logging-design.html": "XFS Delayed Logging",
                "https://www.kernel.org/doc/html/latest/filesystems/xfs/xfs-online-fsck-design.html": "XFS Online Fsck",
                "https://www.kernel.org/doc/html/latest/filesystems/nfs/index.html": "NFS",
                "https://www.kernel.org/doc/html/latest/filesystems/nfs/nfs.html": "NFS Client",
                "https://www.kernel.org/doc/html/latest/filesystems/nfs/nfsd.html": "NFS Server",
                "https://www.kernel.org/doc/html/latest/filesystems/nfs/pnfs.html": "pNFS",
                "https://www.kernel.org/doc/html/latest/filesystems/fuse.html": "FUSE",
                "https://www.kernel.org/doc/html/latest/filesystems/proc.html": "proc",
                "https://www.kernel.org/doc/html/latest/filesystems/sysfs.html": "sysfs",
                "https://www.kernel.org/doc/html/latest/filesystems/tmpfs.html": "tmpfs",
                "https://www.kernel.org/doc/html/latest/filesystems/overlayfs.html": "OverlayFS",
                "https://www.kernel.org/doc/html/latest/filesystems/squashfs.html": "SquashFS",
                "https://www.kernel.org/doc/html/latest/filesystems/vfat.html": "FAT/VFAT",
                "https://www.kernel.org/doc/html/latest/filesystems/ntfs3.html": "NTFS3",
                "https://www.kernel.org/doc/html/latest/filesystems/debugfs.html": "debugfs",
                "https://www.kernel.org/doc/html/latest/filesystems/cifs/cifsroot.html": "CIFS Root",
                "https://www.kernel.org/doc/html/latest/filesystems/9p.html": "9P",
                "https://www.kernel.org/doc/html/latest/filesystems/erofs.html": "EROFS",
                "https://www.kernel.org/doc/html/latest/filesystems/f2fs.html": "F2FS",
                "https://www.kernel.org/doc/html/latest/filesystems/bcachefs/index.html": "Bcachefs",
                "https://www.kernel.org/doc/html/latest/filesystems/autofs.html": "Autofs",
                "https://www.kernel.org/doc/html/latest/filesystems/path-lookup.html": "Path Lookup",
                "https://www.kernel.org/doc/html/latest/filesystems/vfs.html": "VFS",
            },
        },
        "driver-api": {
            "pages": {
                "https://www.kernel.org/doc/html/latest/driver-api/index.html": "Driver API Index",
                "https://www.kernel.org/doc/html/latest/driver-api/driver-model/index.html": "Driver Model",
                "https://www.kernel.org/doc/html/latest/driver-api/driver-model/overview.html": "Driver Model Overview",
                "https://www.kernel.org/doc/html/latest/driver-api/driver-model/binding.html": "Driver Binding",
                "https://www.kernel.org/doc/html/latest/driver-api/driver-model/bus.html": "Bus",
                "https://www.kernel.org/doc/html/latest/driver-api/driver-model/class.html": "Device Class",
                "https://www.kernel.org/doc/html/latest/driver-api/driver-model/device.html": "Device",
                "https://www.kernel.org/doc/html/latest/driver-api/driver-model/driver.html": "Driver",
                "https://www.kernel.org/doc/html/latest/driver-api/driver-model/platform.html": "Platform Devices",
                "https://www.kernel.org/doc/html/latest/driver-api/usb/index.html": "USB",
                "https://www.kernel.org/doc/html/latest/driver-api/usb/usb.html": "USB Core API",
                "https://www.kernel.org/doc/html/latest/driver-api/usb/gadget.html": "USB Gadget",
                "https://www.kernel.org/doc/html/latest/driver-api/pci/index.html": "PCI",
                "https://www.kernel.org/doc/html/latest/driver-api/pci/pci.html": "PCI Core",
                "https://www.kernel.org/doc/html/latest/driver-api/pci/msi-howto.html": "PCI MSI HOWTO",
                "https://www.kernel.org/doc/html/latest/driver-api/i2c.html": "I2C",
                "https://www.kernel.org/doc/html/latest/driver-api/spi.html": "SPI",
                "https://www.kernel.org/doc/html/latest/driver-api/gpio/index.html": "GPIO",
                "https://www.kernel.org/doc/html/latest/driver-api/gpio/intro.html": "GPIO Introduction",
                "https://www.kernel.org/doc/html/latest/driver-api/gpio/consumer.html": "GPIO Consumer",
                "https://www.kernel.org/doc/html/latest/driver-api/gpio/driver.html": "GPIO Driver",
                "https://www.kernel.org/doc/html/latest/driver-api/dma-buf.html": "DMA Buffer Sharing",
                "https://www.kernel.org/doc/html/latest/driver-api/dmaengine/index.html": "DMA Engine",
                "https://www.kernel.org/doc/html/latest/driver-api/clk.html": "Clock Framework",
                "https://www.kernel.org/doc/html/latest/driver-api/regulator.html": "Regulator",
                "https://www.kernel.org/doc/html/latest/driver-api/pwm.html": "PWM",
                "https://www.kernel.org/doc/html/latest/driver-api/iio/index.html": "IIO",
                "https://www.kernel.org/doc/html/latest/driver-api/input.html": "Input Subsystem",
                "https://www.kernel.org/doc/html/latest/driver-api/thermal/index.html": "Thermal",
                "https://www.kernel.org/doc/html/latest/driver-api/firmware/index.html": "Firmware",
                "https://www.kernel.org/doc/html/latest/driver-api/nvmem.html": "NVMEM",
            },
        },
        "security": {
            "pages": {
                "https://www.kernel.org/doc/html/latest/security/index.html": "Security Index",
                "https://www.kernel.org/doc/html/latest/security/lsm.html": "LSM Framework",
                "https://www.kernel.org/doc/html/latest/security/lsm-development.html": "LSM Development",
                "https://www.kernel.org/doc/html/latest/admin-guide/LSM/index.html": "LSM Admin Guide",
                "https://www.kernel.org/doc/html/latest/admin-guide/LSM/SELinux.html": "SELinux",
                "https://www.kernel.org/doc/html/latest/admin-guide/LSM/apparmor.html": "AppArmor",
                "https://www.kernel.org/doc/html/latest/admin-guide/LSM/Smack.html": "Smack",
                "https://www.kernel.org/doc/html/latest/admin-guide/LSM/tomoyo.html": "Tomoyo",
                "https://www.kernel.org/doc/html/latest/admin-guide/LSM/Yama.html": "Yama",
                "https://www.kernel.org/doc/html/latest/admin-guide/LSM/LoadPin.html": "LoadPin",
                "https://www.kernel.org/doc/html/latest/admin-guide/LSM/SafeSetID.html": "SafeSetID",
                "https://www.kernel.org/doc/html/latest/security/IMA-templates.html": "IMA Templates",
                "https://www.kernel.org/doc/html/latest/security/keys/index.html": "Keys",
                "https://www.kernel.org/doc/html/latest/security/keys/core.html": "Keys Core",
                "https://www.kernel.org/doc/html/latest/security/keys/trusted-encrypted.html": "Trusted/Encrypted Keys",
                "https://www.kernel.org/doc/html/latest/security/credentials.html": "Credentials",
                "https://www.kernel.org/doc/html/latest/userspace-api/seccomp_filter.html": "Seccomp Filter",
                "https://www.kernel.org/doc/html/latest/security/self-protection.html": "Self Protection",
                "https://www.kernel.org/doc/html/latest/security/landlock.html": "Landlock",
                "https://www.kernel.org/doc/html/latest/security/siphash.html": "SipHash",
            },
        },
        "core-api": {
            "pages": {
                "https://www.kernel.org/doc/html/latest/core-api/index.html": "Core API Index",
                "https://www.kernel.org/doc/html/latest/core-api/kobject.html": "Kobject",
                "https://www.kernel.org/doc/html/latest/core-api/kref.html": "Kref",
                "https://www.kernel.org/doc/html/latest/core-api/workqueue.html": "Workqueue",
                "https://www.kernel.org/doc/html/latest/core-api/kernel-api.html": "Kernel API",
                "https://www.kernel.org/doc/html/latest/core-api/timers.html": "Timers",
                "https://www.kernel.org/doc/html/latest/core-api/genericirq.html": "Generic IRQ",
                "https://www.kernel.org/doc/html/latest/core-api/irq/index.html": "IRQ",
                "https://www.kernel.org/doc/html/latest/locking/index.html": "Locking",
                "https://www.kernel.org/doc/html/latest/locking/mutex-design.html": "Mutex Design",
                "https://www.kernel.org/doc/html/latest/locking/spinlocks.html": "Spinlocks",
                "https://www.kernel.org/doc/html/latest/locking/rt-mutex-design.html": "RT Mutex",
                "https://www.kernel.org/doc/html/latest/locking/lockdep-design.html": "Lockdep",
                "https://www.kernel.org/doc/html/latest/locking/locktypes.html": "Lock Types",
                "https://www.kernel.org/doc/html/latest/core-api/memory-allocation.html": "Memory Allocation",
                "https://www.kernel.org/doc/html/latest/core-api/mm-api.html": "MM API",
                "https://www.kernel.org/doc/html/latest/core-api/dma-api.html": "DMA API",
                "https://www.kernel.org/doc/html/latest/core-api/dma-api-howto.html": "DMA API HOWTO",
                "https://www.kernel.org/doc/html/latest/core-api/genalloc.html": "Genalloc",
                "https://www.kernel.org/doc/html/latest/core-api/printk-basics.html": "Printk Basics",
                "https://www.kernel.org/doc/html/latest/core-api/printk-formats.html": "Printk Formats",
                "https://www.kernel.org/doc/html/latest/core-api/errseq.html": "Errseq",
                "https://www.kernel.org/doc/html/latest/core-api/rcu.html": "RCU",
                "https://www.kernel.org/doc/html/latest/RCU/index.html": "RCU Index",
                "https://www.kernel.org/doc/html/latest/RCU/whatisRCU.html": "What is RCU",
                "https://www.kernel.org/doc/html/latest/RCU/rcu.html": "RCU Concepts",
                "https://www.kernel.org/doc/html/latest/core-api/xarray.html": "XArray",
                "https://www.kernel.org/doc/html/latest/core-api/maple_tree.html": "Maple Tree",
            },
        },
        "tracing": {
            "pages": {
                "https://www.kernel.org/doc/html/latest/trace/index.html": "Tracing Index",
                "https://www.kernel.org/doc/html/latest/trace/ftrace.html": "Ftrace",
                "https://www.kernel.org/doc/html/latest/trace/ftrace-uses.html": "Ftrace Uses",
                "https://www.kernel.org/doc/html/latest/trace/events.html": "Trace Events",
                "https://www.kernel.org/doc/html/latest/trace/tracepoints.html": "Tracepoints",
                "https://www.kernel.org/doc/html/latest/trace/tracepoint-analysis.html": "Tracepoint Analysis",
                "https://www.kernel.org/doc/html/latest/trace/kprobes.html": "Kprobes",
                "https://www.kernel.org/doc/html/latest/trace/kprobetrace.html": "Kprobe Tracing",
                "https://www.kernel.org/doc/html/latest/trace/uprobetracer.html": "Uprobe Tracer",
                "https://www.kernel.org/doc/html/latest/trace/histogram.html": "Histogram Triggers",
                "https://www.kernel.org/doc/html/latest/trace/boottime-trace.html": "Boot-time Tracing",
                "https://www.kernel.org/doc/html/latest/trace/hwlat_detector.html": "HW Latency Detector",
                "https://www.kernel.org/doc/html/latest/trace/osnoise-tracer.html": "OS Noise Tracer",
                "https://www.kernel.org/doc/html/latest/trace/timerlat-tracer.html": "Timerlat Tracer",
                "https://www.kernel.org/doc/html/latest/trace/ring-buffer-design.html": "Ring Buffer Design",
                "https://www.kernel.org/doc/html/latest/bpf/index.html": "BPF Index",
                "https://www.kernel.org/doc/html/latest/bpf/libbpf/index.html": "libbpf",
                "https://www.kernel.org/doc/html/latest/bpf/maps.html": "BPF Maps",
                "https://www.kernel.org/doc/html/latest/bpf/btf.html": "BTF",
                "https://www.kernel.org/doc/html/latest/bpf/bpf_design_QA.html": "BPF Design QA",
                "https://www.kernel.org/doc/html/latest/bpf/instruction-set.html": "BPF Instruction Set",
                "https://www.kernel.org/doc/html/latest/bpf/helpers.html": "BPF Helpers",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"kernel-docs-{source_key}" if source_key else "kernel-docs"
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
            for suffix in [' — The Linux Kernel documentation',
                           ' - The Linux Kernel documentation',
                           ' — The Linux Kernel',
                           ' - The Linux Kernel']:
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
                        "category": "kernel-docs",
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
            self.log.info(f"=== Scraping kernel-docs/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    KernelDocsScraper(base, source_key).run()
