#!/usr/bin/env python3
"""FreeBSD documentation scraper.

Covers:
  - FreeBSD Handbook (installation, configuration, administration)
  - FreeBSD FAQ and articles
  - Porter's Handbook, Developer's Handbook, Architecture Handbook
  - FreeBSD system documentation (security, networking, storage)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class FreeBSDScraper(BaseScraper):
    """FreeBSD documentation scraper. Handbook, FAQ, porter's handbook, and system documentation."""

    SOURCES = {
        "introduction": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/": "FreeBSD Handbook",
                "https://docs.freebsd.org/en/books/handbook/introduction/": "Introduction to FreeBSD",
                "https://docs.freebsd.org/en/books/handbook/preface/": "FreeBSD Handbook Preface",
                "https://www.freebsd.org/about/": "About FreeBSD",
                "https://www.freebsd.org/features/": "FreeBSD Features",
                "https://www.freebsd.org/projects/": "FreeBSD Projects",
                "https://www.freebsd.org/doc/en/articles/explaining-bsd/": "Explaining BSD",
                "https://www.freebsd.org/doc/en/articles/linux-comparison/": "FreeBSD vs Linux",
                "https://www.freebsd.org/releases/": "FreeBSD Releases",
                "https://www.freebsd.org/releases/14.0R/relnotes/": "FreeBSD 14.0 Release Notes",
                "https://docs.freebsd.org/en/books/faq/": "FreeBSD FAQ",
                "https://docs.freebsd.org/en/books/handbook/history/": "FreeBSD History",
                "https://www.freebsd.org/advocacy/": "FreeBSD Advocacy",
                "https://www.freebsd.org/doc/en/articles/new-users/": "FreeBSD for Linux/Unix Users",
                "https://www.freebsd.org/copyright/": "FreeBSD Copyright",
            },
        },
        "bsdinstall": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/bsdinstall/": "Installing FreeBSD",
                "https://docs.freebsd.org/en/books/handbook/bsdinstall/#bsdinstall-pre": "Pre-Installation Tasks",
                "https://docs.freebsd.org/en/books/handbook/bsdinstall/#bsdinstall-start": "Starting the Installation",
                "https://docs.freebsd.org/en/books/handbook/bsdinstall/#using-bsdinstall": "Using bsdinstall",
                "https://docs.freebsd.org/en/books/handbook/bsdinstall/#bsdinstall-partitioning": "Disk Partitioning",
                "https://docs.freebsd.org/en/books/handbook/bsdinstall/#bsdinstall-post": "Post-Installation",
                "https://www.freebsd.org/where/": "Getting FreeBSD",
                "https://docs.freebsd.org/en/books/handbook/mirrors/": "FreeBSD Mirrors",
                "https://docs.freebsd.org/en/articles/installation-guide/": "Installation Guide",
                "https://www.freebsd.org/platforms/": "FreeBSD Platforms",
                "https://www.freebsd.org/platforms/amd64/": "FreeBSD on AMD64",
                "https://www.freebsd.org/platforms/arm/": "FreeBSD on ARM",
                "https://www.freebsd.org/platforms/i386/": "FreeBSD on i386",
                "https://www.freebsd.org/platforms/ppc/": "FreeBSD on PowerPC",
                "https://www.freebsd.org/platforms/riscv/": "FreeBSD on RISC-V",
            },
        },
        "basics": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/basics/": "FreeBSD Basics",
                "https://docs.freebsd.org/en/books/handbook/basics/#basics-users": "Users and Basic Account Management",
                "https://docs.freebsd.org/en/books/handbook/basics/#basics-processes": "Processes and Daemons",
                "https://docs.freebsd.org/en/books/handbook/basics/#permissions": "Permissions",
                "https://docs.freebsd.org/en/books/handbook/basics/#dirstructure": "Directory Structure",
                "https://docs.freebsd.org/en/books/handbook/basics/#disk-organization": "Disk Organization",
                "https://docs.freebsd.org/en/books/handbook/basics/#shells": "Shells",
                "https://docs.freebsd.org/en/books/handbook/basics/#editors": "Text Editors",
                "https://docs.freebsd.org/en/books/handbook/basics/#basics-devices": "Devices and Device Nodes",
                "https://docs.freebsd.org/en/books/handbook/config/": "Configuration and Tuning",
                "https://docs.freebsd.org/en/books/handbook/config/#config-synopsis": "Configuration Synopsis",
                "https://docs.freebsd.org/en/books/handbook/config/#configtuning-sysctl": "Using sysctl",
                "https://docs.freebsd.org/en/books/handbook/config/#config-cron": "Configuring cron",
                "https://docs.freebsd.org/en/books/handbook/config/#config-syslog": "Configuring syslog",
                "https://docs.freebsd.org/en/books/handbook/config/#configtuning-disk": "Disk Tuning",
                "https://docs.freebsd.org/en/books/handbook/config/#configtuning-kernel-limits": "Kernel Limits",
                "https://docs.freebsd.org/en/books/handbook/boot/": "FreeBSD Booting Process",
                "https://docs.freebsd.org/en/books/handbook/boot/#boot-synopsis": "Boot Synopsis",
                "https://docs.freebsd.org/en/books/handbook/boot/#boot-blocks": "Boot Blocks",
                "https://docs.freebsd.org/en/books/handbook/users/": "Users and Basic Account Management",
            },
        },
        "ports": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/ports/": "Installing Applications: Packages and Ports",
                "https://docs.freebsd.org/en/books/handbook/ports/#pkgng-intro": "Overview of Software Installation",
                "https://docs.freebsd.org/en/books/handbook/ports/#packages-finding": "Finding Software",
                "https://docs.freebsd.org/en/books/handbook/ports/#pkg-info": "Using pkg for Binary Package Management",
                "https://docs.freebsd.org/en/books/handbook/ports/#ports-using": "Using the Ports Collection",
                "https://docs.freebsd.org/en/books/handbook/ports/#ports-finding-applications": "Finding Applications",
                "https://docs.freebsd.org/en/books/handbook/ports/#ports-building": "Building Ports",
                "https://docs.freebsd.org/en/books/handbook/ports/#ports-poudriere": "Building Packages with Poudriere",
                "https://docs.freebsd.org/en/books/porters-handbook/": "Porter's Handbook",
                "https://docs.freebsd.org/en/books/porters-handbook/quick-porting/": "Quick Porting",
                "https://docs.freebsd.org/en/books/porters-handbook/makefiles/": "Makefile Basics",
                "https://docs.freebsd.org/en/books/porters-handbook/flavors/": "Flavors",
                "https://docs.freebsd.org/en/books/porters-handbook/testing/": "Testing",
                "https://docs.freebsd.org/en/books/porters-handbook/upgrading/": "Upgrading a Port",
                "https://docs.freebsd.org/en/books/porters-handbook/porting-dads/": "Dos and Don'ts",
                "https://docs.freebsd.org/en/books/porters-handbook/pkg-files/": "pkg-* Files",
                "https://docs.freebsd.org/en/books/porters-handbook/plist/": "Advanced pkg-plist Practices",
                "https://www.freebsd.org/ports/": "FreeBSD Ports",
                "https://www.freshports.org/": "FreshPorts",
                "https://docs.freebsd.org/en/books/porters-handbook/order/": "Port Build Order",
            },
        },
        "x11": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/x11/": "The X Window System",
                "https://docs.freebsd.org/en/books/handbook/x11/#x-understanding": "Understanding X",
                "https://docs.freebsd.org/en/books/handbook/x11/#x-install": "Installing X11",
                "https://docs.freebsd.org/en/books/handbook/x11/#x-config": "X11 Configuration",
                "https://docs.freebsd.org/en/books/handbook/x11/#x11-wm": "Window Managers",
                "https://docs.freebsd.org/en/books/handbook/wayland/": "Wayland",
                "https://docs.freebsd.org/en/books/handbook/wayland/#wayland-synopsis": "Wayland Synopsis",
                "https://docs.freebsd.org/en/books/handbook/wayland/#wayfire": "Wayfire",
                "https://docs.freebsd.org/en/books/handbook/wayland/#hikari": "Hikari",
                "https://docs.freebsd.org/en/books/handbook/wayland/#sway": "Sway",
                "https://docs.freebsd.org/en/books/handbook/x11/#x-fonts": "Fonts",
                "https://docs.freebsd.org/en/books/handbook/x11/#x-xdm": "XDM Display Manager",
            },
        },
        "desktop": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/desktop/": "Desktop Environments",
                "https://docs.freebsd.org/en/books/handbook/desktop/#desktop-synopsis": "Desktop Synopsis",
                "https://docs.freebsd.org/en/books/handbook/desktop/#desktop-browsers": "Web Browsers",
                "https://docs.freebsd.org/en/books/handbook/desktop/#desktop-productivity": "Productivity",
                "https://docs.freebsd.org/en/books/handbook/desktop/#desktop-viewers": "Document Viewers",
                "https://docs.freebsd.org/en/books/handbook/desktop/#desktop-finance": "Finance",
                "https://docs.freebsd.org/en/books/handbook/desktop/#desktop-kde": "KDE Plasma",
                "https://docs.freebsd.org/en/books/handbook/desktop/#desktop-gnome": "GNOME",
                "https://docs.freebsd.org/en/books/handbook/desktop/#desktop-xfce": "XFCE",
                "https://docs.freebsd.org/en/books/handbook/desktop/#desktop-mate": "MATE",
                "https://docs.freebsd.org/en/books/handbook/desktop/#desktop-cinnamon": "Cinnamon",
                "https://docs.freebsd.org/en/books/handbook/desktop/#desktop-lumina": "Lumina",
                "https://docs.freebsd.org/en/books/handbook/desktop/#desktop-editors": "Text Editors",
                "https://docs.freebsd.org/en/books/handbook/desktop/#desktop-communication": "Communication",
                "https://docs.freebsd.org/en/books/handbook/desktop/#desktop-install": "Desktop Installation",
            },
        },
        "multimedia": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/multimedia/": "Multimedia",
                "https://docs.freebsd.org/en/books/handbook/multimedia/#sound-setup": "Setting Up Sound",
                "https://docs.freebsd.org/en/books/handbook/multimedia/#sound-mp3": "MP3 Audio",
                "https://docs.freebsd.org/en/books/handbook/multimedia/#video-playback": "Video Playback",
                "https://docs.freebsd.org/en/books/handbook/multimedia/#tvcard": "TV Cards",
                "https://docs.freebsd.org/en/books/handbook/multimedia/#scanners": "Image Scanners",
                "https://docs.freebsd.org/en/books/handbook/multimedia/#multimedia-audio-mixers": "Audio Mixers",
                "https://docs.freebsd.org/en/books/handbook/multimedia/#multimedia-video-editing": "Video Editing",
                "https://docs.freebsd.org/en/books/handbook/multimedia/#multimedia-image-editing": "Image Editing",
                "https://docs.freebsd.org/en/books/handbook/multimedia/#multimedia-cd-dvd": "CD/DVD Creation",
                "https://docs.freebsd.org/en/books/handbook/multimedia/#multimedia-bluetooth": "Bluetooth Audio",
                "https://docs.freebsd.org/en/books/handbook/multimedia/#multimedia-pulseaudio": "PulseAudio",
            },
        },
        "kernel": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/kernelconfig/": "Configuring the FreeBSD Kernel",
                "https://docs.freebsd.org/en/books/handbook/kernelconfig/#kernelconfig-synopsis": "Kernel Config Synopsis",
                "https://docs.freebsd.org/en/books/handbook/kernelconfig/#kernelconfig-custom-kernel": "Why Build a Custom Kernel",
                "https://docs.freebsd.org/en/books/handbook/kernelconfig/#kernelconfig-building": "Building a Custom Kernel",
                "https://docs.freebsd.org/en/books/handbook/kernelconfig/#kernelconfig-config": "The Configuration File",
                "https://docs.freebsd.org/en/books/handbook/kernelconfig/#kernelconfig-modules": "Kernel Modules",
                "https://docs.freebsd.org/en/books/handbook/cutting-edge/": "Updating and Upgrading FreeBSD",
                "https://docs.freebsd.org/en/books/handbook/cutting-edge/#updating-upgrading-freebsdupdate": "FreeBSD Update",
                "https://docs.freebsd.org/en/books/handbook/cutting-edge/#updating-upgrading-portsnap": "Portsnap",
                "https://docs.freebsd.org/en/books/handbook/cutting-edge/#makeworld": "Building from Source",
                "https://docs.freebsd.org/en/books/handbook/cutting-edge/#updating-upgrading-documentation": "Updating Documentation",
                "https://docs.freebsd.org/en/books/developers-handbook/": "Developer's Handbook",
                "https://docs.freebsd.org/en/books/developers-handbook/tools/": "Programming Tools",
                "https://docs.freebsd.org/en/books/developers-handbook/kerneldebug/": "Kernel Debugging",
                "https://docs.freebsd.org/en/books/arch-handbook/": "Architecture Handbook",
            },
        },
        "printing": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/printing/": "Printing",
                "https://docs.freebsd.org/en/books/handbook/printing/#printing-synopsis": "Printing Synopsis",
                "https://docs.freebsd.org/en/books/handbook/printing/#printing-connections": "Printer Connections",
                "https://docs.freebsd.org/en/books/handbook/printing/#printing-pdls": "Page Description Languages",
                "https://docs.freebsd.org/en/books/handbook/printing/#printing-direct": "Direct Printing",
                "https://docs.freebsd.org/en/books/handbook/printing/#printing-lpd": "LPD",
                "https://docs.freebsd.org/en/books/handbook/printing/#printing-cups": "CUPS",
                "https://docs.freebsd.org/en/books/handbook/printing/#printing-hplip": "HPLIP",
            },
        },
        "linux-compat": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/linuxemu/": "Linux Binary Compatibility",
                "https://docs.freebsd.org/en/books/handbook/linuxemu/#linuxemu-synopsis": "Linux Compat Synopsis",
                "https://docs.freebsd.org/en/books/handbook/linuxemu/#linuxemu-lbc-install": "Configuring Linux Compatibility",
                "https://docs.freebsd.org/en/books/handbook/linuxemu/#linuxemu-advanced": "Advanced Linux Compatibility",
                "https://docs.freebsd.org/en/books/handbook/linuxemu/#linuxemu-libs-manually": "Manual Library Installation",
                "https://docs.freebsd.org/en/books/handbook/linuxemu/#linuxemu-brandelf": "Branding",
                "https://docs.freebsd.org/en/books/handbook/linuxemu/#linuxemu-debootstrap": "Debootstrap",
                "https://docs.freebsd.org/en/books/handbook/linuxemu/#linuxemu-systemcalls": "System Calls",
                "https://docs.freebsd.org/en/articles/linux-users/": "FreeBSD Quickstart Guide for Linux Users",
                "https://docs.freebsd.org/en/articles/explaining-bsd/": "Explaining BSD for Linux Users",
            },
        },
        "wine": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/wine/": "Wine on FreeBSD",
                "https://docs.freebsd.org/en/books/handbook/wine/#wine-synopsis": "Wine Synopsis",
                "https://docs.freebsd.org/en/books/handbook/wine/#wine-overview": "Wine Overview",
                "https://docs.freebsd.org/en/books/handbook/wine/#wine-installing": "Installing Wine",
                "https://docs.freebsd.org/en/books/handbook/wine/#wine-configuration": "Configuring Wine",
                "https://docs.freebsd.org/en/books/handbook/wine/#wine-running": "Running Windows Applications",
                "https://docs.freebsd.org/en/books/handbook/wine/#wine-management": "Wine Management",
                "https://docs.freebsd.org/en/books/handbook/wine/#wine-troubleshooting": "Wine Troubleshooting",
            },
        },
        "security": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/security/": "Security",
                "https://docs.freebsd.org/en/books/handbook/security/#security-synopsis": "Security Synopsis",
                "https://docs.freebsd.org/en/books/handbook/security/#security-intro": "Introduction to Security",
                "https://docs.freebsd.org/en/books/handbook/security/#one-time-passwords": "One-Time Passwords",
                "https://docs.freebsd.org/en/books/handbook/security/#kerberos5": "Kerberos",
                "https://docs.freebsd.org/en/books/handbook/security/#openssl": "OpenSSL",
                "https://docs.freebsd.org/en/books/handbook/security/#ipsec": "IPsec",
                "https://docs.freebsd.org/en/books/handbook/security/#openssh": "OpenSSH",
                "https://docs.freebsd.org/en/books/handbook/security/#security-accounting": "File System Access Control Lists",
                "https://docs.freebsd.org/en/books/handbook/security/#security-portaudit": "Monitoring Third Party Security Issues",
                "https://docs.freebsd.org/en/books/handbook/security/#security-advisories": "FreeBSD Security Advisories",
                "https://docs.freebsd.org/en/books/handbook/security/#security-sudo": "Sudo",
                "https://docs.freebsd.org/en/books/handbook/security/#security-doas": "Doas",
                "https://docs.freebsd.org/en/books/handbook/security/#security-pkg-audit": "Binary Package Audit",
                "https://www.freebsd.org/security/": "FreeBSD Security Information",
                "https://www.freebsd.org/security/advisories/": "Security Advisories",
                "https://docs.freebsd.org/en/books/handbook/security/#tcpwrappers": "TCP Wrappers",
                "https://docs.freebsd.org/en/books/handbook/security/#security-resourcelimits": "Resource Limits",
                "https://docs.freebsd.org/en/articles/freebsd-security/": "FreeBSD Security Article",
                "https://docs.freebsd.org/en/books/handbook/security/#security-certbot": "Certbot and Let's Encrypt",
            },
        },
        "jails": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/jails/": "Jails",
                "https://docs.freebsd.org/en/books/handbook/jails/#jails-synopsis": "Jails Synopsis",
                "https://docs.freebsd.org/en/books/handbook/jails/#jails-terms": "Jail Terms",
                "https://docs.freebsd.org/en/books/handbook/jails/#jails-build": "Creating a Jail",
                "https://docs.freebsd.org/en/books/handbook/jails/#jails-host": "Host Configuration",
                "https://docs.freebsd.org/en/books/handbook/jails/#jails-ezjail": "Ezjail",
                "https://docs.freebsd.org/en/books/handbook/jails/#jails-application": "Application Jails",
                "https://docs.freebsd.org/en/books/handbook/jails/#jails-iocage": "Iocage",
                "https://docs.freebsd.org/en/books/handbook/jails/#jails-bastille": "Bastille",
                "https://docs.freebsd.org/en/books/handbook/jails/#jails-cbsd": "CBSD",
                "https://docs.freebsd.org/en/books/handbook/jails/#jails-updating": "Updating Jails",
                "https://docs.freebsd.org/en/books/handbook/jails/#jails-networking": "Jail Networking",
                "https://docs.freebsd.org/en/books/handbook/jails/#jails-tuning": "Jail Tuning",
                "https://docs.freebsd.org/en/articles/rc-scripting/": "RC Scripting in FreeBSD",
                "https://docs.freebsd.org/en/books/handbook/jails/#jails-vnet": "VNET Jails",
            },
        },
        "mac": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/mac/": "Mandatory Access Control",
                "https://docs.freebsd.org/en/books/handbook/mac/#mac-synopsis": "MAC Synopsis",
                "https://docs.freebsd.org/en/books/handbook/mac/#mac-understandlabel": "Understanding MAC Labels",
                "https://docs.freebsd.org/en/books/handbook/mac/#mac-modules": "MAC Modules",
                "https://docs.freebsd.org/en/books/handbook/mac/#mac-bsdextended": "MAC BSD Extended",
                "https://docs.freebsd.org/en/books/handbook/mac/#mac-ifoff": "MAC ifoff",
                "https://docs.freebsd.org/en/books/handbook/mac/#mac-portacl": "MAC portacl",
                "https://docs.freebsd.org/en/books/handbook/mac/#mac-partition": "MAC partition",
                "https://docs.freebsd.org/en/books/handbook/mac/#mac-mls": "MAC Multi-Level Security",
                "https://docs.freebsd.org/en/books/handbook/mac/#mac-biba": "MAC Biba Integrity",
            },
        },
        "audit": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/audit/": "Security Event Auditing",
                "https://docs.freebsd.org/en/books/handbook/audit/#audit-synopsis": "Audit Synopsis",
                "https://docs.freebsd.org/en/books/handbook/audit/#audit-inline-glossary": "Audit Terminology",
                "https://docs.freebsd.org/en/books/handbook/audit/#audit-install": "Installing Audit Support",
                "https://docs.freebsd.org/en/books/handbook/audit/#audit-config": "Audit Configuration",
                "https://docs.freebsd.org/en/books/handbook/audit/#audit-administration": "Working with Audit Trails",
                "https://docs.freebsd.org/en/books/handbook/audit/#audit-auditreduce": "Audit Reduction",
                "https://docs.freebsd.org/en/books/handbook/audit/#audit-praudit": "Printing Audit Records",
            },
        },
        "storage": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/disks/": "Storage",
                "https://docs.freebsd.org/en/books/handbook/disks/#disks-synopsis": "Storage Synopsis",
                "https://docs.freebsd.org/en/books/handbook/disks/#disks-adding": "Adding Disks",
                "https://docs.freebsd.org/en/books/handbook/disks/#disks-naming": "Device Naming",
                "https://docs.freebsd.org/en/books/handbook/disks/#disks-virtual": "Virtual Disks",
                "https://docs.freebsd.org/en/books/handbook/disks/#usb-disks": "USB Storage Devices",
                "https://docs.freebsd.org/en/books/handbook/disks/#disks-cd": "Creating and Using CDs",
                "https://docs.freebsd.org/en/books/handbook/disks/#disks-dvd": "Creating and Using DVDs",
                "https://docs.freebsd.org/en/books/handbook/disks/#creating-cds": "CD/DVD Burning",
                "https://docs.freebsd.org/en/books/handbook/disks/#disks-floppy": "Floppy Disks",
                "https://docs.freebsd.org/en/books/handbook/disks/#backup-basics": "Backup Basics",
                "https://docs.freebsd.org/en/books/handbook/disks/#disks-hast": "High Availability Storage",
                "https://docs.freebsd.org/en/books/handbook/disks/#quotas": "Disk Quotas",
                "https://docs.freebsd.org/en/books/handbook/disks/#disks-encrypting": "Encrypting Disk Partitions",
                "https://docs.freebsd.org/en/books/handbook/disks/#swap-encrypting": "Encrypting Swap",
            },
        },
        "geom": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/geom/": "GEOM: Modular Disk Transformation Framework",
                "https://docs.freebsd.org/en/books/handbook/geom/#geom-synopsis": "GEOM Synopsis",
                "https://docs.freebsd.org/en/books/handbook/geom/#geom-striping": "RAID0 - Striping",
                "https://docs.freebsd.org/en/books/handbook/geom/#geom-mirror": "RAID1 - Mirroring",
                "https://docs.freebsd.org/en/books/handbook/geom/#geom-raid3": "RAID3 - Byte-level Striping with Dedicated Parity",
                "https://docs.freebsd.org/en/books/handbook/geom/#geom-graid": "Software RAID Devices",
                "https://docs.freebsd.org/en/books/handbook/geom/#geom-ggate": "GEOM Gate Network",
                "https://docs.freebsd.org/en/books/handbook/geom/#geom-glabel": "Labeling Disk Devices",
                "https://docs.freebsd.org/en/books/handbook/geom/#geom-gjournal": "UFS Journaling Through GEOM",
                "https://docs.freebsd.org/en/books/handbook/geom/#geom-eli": "GELI Disk Encryption",
                "https://docs.freebsd.org/en/books/handbook/geom/#geom-geli-suspend": "GELI Suspend/Resume",
                "https://docs.freebsd.org/en/books/handbook/geom/#geom-concat": "Concatenating Providers",
            },
        },
        "zfs": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/zfs/": "The Z File System (ZFS)",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-synopsis": "ZFS Synopsis",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-quickstart": "ZFS Quick Start",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-term": "ZFS Terminology",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-pools": "zpool Administration",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-zpool-create": "Creating a Pool",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-zpool-status": "Pool Status",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-zfs": "zfs Administration",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-zfs-create": "Creating Datasets",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-zfs-snapshot": "Snapshots",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-zfs-clone": "Clones",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-zfs-send": "Send and Receive",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-zfs-compression": "Compression",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-zfs-dedup": "Deduplication",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-zfs-encryption": "Native ZFS Encryption",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-zfs-quota": "Quotas",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-zfs-reservation": "Reservations",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-advanced": "Advanced ZFS",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-be": "Boot Environments",
                "https://docs.freebsd.org/en/books/handbook/zfs/#zfs-troubleshooting": "ZFS Troubleshooting",
            },
        },
        "dtrace": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/dtrace/": "DTrace",
                "https://docs.freebsd.org/en/books/handbook/dtrace/#dtrace-synopsis": "DTrace Synopsis",
                "https://docs.freebsd.org/en/books/handbook/dtrace/#dtrace-implementation": "DTrace Implementation",
                "https://docs.freebsd.org/en/books/handbook/dtrace/#dtrace-enable": "Enabling DTrace",
                "https://docs.freebsd.org/en/books/handbook/dtrace/#dtrace-using": "Using DTrace",
                "https://docs.freebsd.org/en/books/handbook/dtrace/#dtrace-language": "The D Language",
                "https://docs.freebsd.org/en/books/handbook/dtrace/#dtrace-examples": "DTrace Examples",
                "https://docs.freebsd.org/en/books/handbook/dtrace/#dtrace-one-liners": "DTrace One-Liners",
                "https://docs.freebsd.org/en/books/handbook/dtrace/#dtrace-compatibility": "DTrace Compatibility",
                "https://docs.freebsd.org/en/books/handbook/dtrace/#dtrace-further": "Further Reading DTrace",
            },
        },
        "serialcomms": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/serialcomms/": "Serial Communications",
                "https://docs.freebsd.org/en/books/handbook/serialcomms/#serial-synopsis": "Serial Synopsis",
                "https://docs.freebsd.org/en/books/handbook/serialcomms/#serial": "Serial Terminology",
                "https://docs.freebsd.org/en/books/handbook/serialcomms/#term": "Terminals",
                "https://docs.freebsd.org/en/books/handbook/serialcomms/#dialup": "Dial-in Service",
                "https://docs.freebsd.org/en/books/handbook/serialcomms/#dialout": "Dial-out Service",
                "https://docs.freebsd.org/en/books/handbook/serialcomms/#serialconsole": "Setting Up the Serial Console",
                "https://docs.freebsd.org/en/books/handbook/serialcomms/#serial-usb": "USB Serial Devices",
                "https://docs.freebsd.org/en/books/handbook/usb-device-mode/": "USB Device Mode",
                "https://docs.freebsd.org/en/books/handbook/usb-device-mode/#usb-device-mode-serial": "USB Serial Console",
            },
        },
        "ppp": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/ppp-and-slip/": "PPP",
                "https://docs.freebsd.org/en/books/handbook/ppp-and-slip/#userppp": "User PPP",
                "https://docs.freebsd.org/en/books/handbook/ppp-and-slip/#ppp-troubleshoot": "PPP Troubleshooting",
                "https://docs.freebsd.org/en/books/handbook/ppp-and-slip/#pppoe": "PPPoE",
                "https://docs.freebsd.org/en/books/handbook/ppp-and-slip/#ppp-over-atm": "PPP over ATM",
                "https://docs.freebsd.org/en/books/handbook/ppp-and-slip/#ppp-mpd": "MPD",
                "https://docs.freebsd.org/en/books/handbook/ppp-and-slip/#ppp-nat": "PPP and NAT",
                "https://docs.freebsd.org/en/books/handbook/ppp-and-slip/#ppp-overview": "PPP Overview",
            },
        },
        "electronic-mail": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/mail/": "Electronic Mail",
                "https://docs.freebsd.org/en/books/handbook/mail/#mail-synopsis": "Mail Synopsis",
                "https://docs.freebsd.org/en/books/handbook/mail/#mail-using": "Using Electronic Mail",
                "https://docs.freebsd.org/en/books/handbook/mail/#sendmail": "Sendmail",
                "https://docs.freebsd.org/en/books/handbook/mail/#mail-changingmta": "Changing the MTA",
                "https://docs.freebsd.org/en/books/handbook/mail/#mail-trouble": "Mail Troubleshooting",
                "https://docs.freebsd.org/en/books/handbook/mail/#postfix": "Postfix",
                "https://docs.freebsd.org/en/books/handbook/mail/#mail-dovecot": "Dovecot",
                "https://docs.freebsd.org/en/books/handbook/mail/#mail-fetchmail": "Fetchmail",
                "https://docs.freebsd.org/en/books/handbook/mail/#mail-procmail": "Procmail",
                "https://docs.freebsd.org/en/books/handbook/mail/#mail-spam": "Spam Filtering",
                "https://docs.freebsd.org/en/books/handbook/mail/#outgoing-only": "Outgoing Only Mail",
            },
        },
        "network-servers": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/network-servers/": "Network Servers",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-inetd": "inetd Super-Server",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-nfs": "NFS",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-nis": "NIS",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-ldap": "LDAP",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-dhcp": "DHCP",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-dns": "DNS",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-bind": "BIND",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-unbound": "Unbound",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-apache": "Apache HTTP Server",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-nginx": "Nginx",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-ftp": "FTP",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-samba": "Samba (CIFS)",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-ntpd": "NTP",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-iscsi": "iSCSI",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-isns": "iSNS",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-rsync": "rsync",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-mysql": "MySQL",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-postgresql": "PostgreSQL",
                "https://docs.freebsd.org/en/books/handbook/network-servers/#network-snmp": "SNMP",
            },
        },
        "firewalls": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/firewalls/": "Firewalls",
                "https://docs.freebsd.org/en/books/handbook/firewalls/#firewalls-synopsis": "Firewalls Synopsis",
                "https://docs.freebsd.org/en/books/handbook/firewalls/#firewalls-concepts": "Firewall Concepts",
                "https://docs.freebsd.org/en/books/handbook/firewalls/#firewalls-pf": "PF",
                "https://docs.freebsd.org/en/books/handbook/firewalls/#firewalls-pf-config": "PF Configuration",
                "https://docs.freebsd.org/en/books/handbook/firewalls/#firewalls-pf-tables": "PF Tables",
                "https://docs.freebsd.org/en/books/handbook/firewalls/#firewalls-pf-rulesets": "PF Rulesets",
                "https://docs.freebsd.org/en/books/handbook/firewalls/#firewalls-pf-nat": "PF NAT",
                "https://docs.freebsd.org/en/books/handbook/firewalls/#firewalls-pf-altq": "ALTQ",
                "https://docs.freebsd.org/en/books/handbook/firewalls/#firewalls-ipfw": "IPFW",
                "https://docs.freebsd.org/en/books/handbook/firewalls/#firewalls-ipfw-nat": "IPFW NAT",
                "https://docs.freebsd.org/en/books/handbook/firewalls/#firewalls-ipf": "IPFILTER (IPF)",
                "https://docs.freebsd.org/en/books/handbook/firewalls/#firewalls-ipf-rules": "IPF Rules",
                "https://docs.freebsd.org/en/books/handbook/firewalls/#firewalls-ipf-nat": "IPF NAT",
                "https://docs.freebsd.org/en/books/handbook/firewalls/#firewalls-blacklistd": "Blacklistd",
            },
        },
        "advanced-networking": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/": "Advanced Networking",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-aggregation": "Link Aggregation and Failover",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-wireless": "Wireless Networking",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-wireless-quick-start": "Wireless Quick Start",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-usb-tethering": "USB Tethering",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-bluetooth": "Bluetooth",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-bridging": "Bridging",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-vlans": "VLANs",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-routing": "Routing",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-static-routes": "Static Routes",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-multipath": "Multipath Routing",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-ipv6": "IPv6",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#carp": "CARP",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-diskless": "Diskless Operation",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-pxe-nfs": "PXE Boot",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-isdn": "ISDN",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-natd": "natd",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-plip": "PLIP",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-infiniband": "InfiniBand",
                "https://docs.freebsd.org/en/books/handbook/advanced-networking/#network-netgraph": "Netgraph",
            },
        },
        "virtualization": {
            "pages": {
                "https://docs.freebsd.org/en/books/handbook/virtualization/": "Virtualization",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-synopsis": "Virtualization Synopsis",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-guest-virtualbox": "FreeBSD as a VirtualBox Guest",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-host-virtualbox": "FreeBSD as a VirtualBox Host",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-guest-vmware": "FreeBSD as a VMware Guest",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-host-bhyve": "bhyve",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-host-bhyve-configuration": "bhyve Configuration",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-host-bhyve-zfs": "bhyve with ZFS",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-host-bhyve-uefi": "UEFI Guests in bhyve",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-guest-xen": "FreeBSD as a Xen Guest",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-host-xen": "FreeBSD as a Xen Host",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-guest-kvm": "FreeBSD as KVM Guest",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-guest-hyper-v": "FreeBSD as Hyper-V Guest",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-containers": "Container Virtualization",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-pot": "Pot Framework",
                # Additional virtualization
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-host-bhyve-networking": "bhyve Networking",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-host-bhyve-windows": "Windows Guests in bhyve",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-host-bhyve-linux": "Linux Guests in bhyve",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-cloud": "Cloud Platforms",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-aws": "FreeBSD on AWS",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-azure": "FreeBSD on Azure",
                "https://docs.freebsd.org/en/books/handbook/virtualization/#virtualization-gce": "FreeBSD on GCE",
            },
        },
    }

    # Additional FreeBSD documentation and man pages
    SOURCES["introduction"]["pages"].update({
        "https://www.freebsd.org/community/": "FreeBSD Community",
        "https://www.freebsd.org/community/mailinglists/": "FreeBSD Mailing Lists",
        "https://www.freebsd.org/support/": "FreeBSD Support",
        "https://docs.freebsd.org/en/articles/freebsd-questions/": "How to Get Best Results from FreeBSD-Questions",
        "https://docs.freebsd.org/en/articles/contributing/": "Contributing to FreeBSD",
        "https://docs.freebsd.org/en/articles/committers-guide/": "Committer's Guide",
        "https://docs.freebsd.org/en/articles/problem-reports/": "Writing FreeBSD Problem Reports",
        "https://docs.freebsd.org/en/articles/leap-seconds/": "FreeBSD Support for Leap Seconds",
        "https://docs.freebsd.org/en/articles/nanobsd/": "NanoBSD",
        "https://docs.freebsd.org/en/articles/freebsd-releng/": "FreeBSD Release Engineering",
        "https://www.freebsd.org/doc/en/articles/building-products/": "Building Products with FreeBSD",
        "https://docs.freebsd.org/en/articles/ipsec-must/": "IPsec Must Do's",
        "https://docs.freebsd.org/en/articles/pam/": "PAM",
        "https://docs.freebsd.org/en/articles/serial-uart/": "Serial and UART",
        "https://docs.freebsd.org/en/articles/cups/": "CUPS on FreeBSD",
        "https://docs.freebsd.org/en/articles/ldap-auth/": "LDAP Authentication",
        "https://docs.freebsd.org/en/articles/linux-emulation/": "Linux Emulation",
        "https://docs.freebsd.org/en/articles/mailing-list-faq/": "Mailing List FAQ",
        "https://docs.freebsd.org/en/articles/remote-install/": "Remote Installation",
        "https://docs.freebsd.org/en/articles/solid-state/": "Solid State Devices",
        "https://docs.freebsd.org/en/articles/vinum/": "Vinum Volume Manager",
        "https://docs.freebsd.org/en/articles/vm-design/": "FreeBSD VM Design",
        "https://docs.freebsd.org/en/articles/hubs/": "Mirroring FreeBSD",
        "https://docs.freebsd.org/en/articles/port-mentor-guidelines/": "Port Mentor Guidelines",
        "https://docs.freebsd.org/en/articles/filtering-bridges/": "Filtering Bridges",
        "https://docs.freebsd.org/en/articles/fonts/": "Fonts and FreeBSD",
        "https://docs.freebsd.org/en/articles/geom-class/": "Writing a GEOM Class",
        "https://docs.freebsd.org/en/books/design-44bsd/": "Design of the 4.4BSD Operating System",
        "https://docs.freebsd.org/en/books/developers-handbook/introduction/": "Developer's Handbook Introduction",
        "https://docs.freebsd.org/en/books/developers-handbook/sockets/": "Sockets Programming",
        "https://docs.freebsd.org/en/books/developers-handbook/ipv6/": "IPv6 Internals",
        "https://docs.freebsd.org/en/books/developers-handbook/policies/": "Source Tree Policies",
        "https://docs.freebsd.org/en/books/developers-handbook/testing/": "Testing",
        "https://docs.freebsd.org/en/books/developers-handbook/l10n/": "Localization and Internationalization",
        "https://docs.freebsd.org/en/books/arch-handbook/jail/": "Architecture Handbook - Jails",
        "https://docs.freebsd.org/en/books/arch-handbook/sysinit/": "Architecture - SYSINIT Framework",
        "https://docs.freebsd.org/en/books/arch-handbook/driverbasics/": "Architecture - Device Drivers",
        "https://docs.freebsd.org/en/books/arch-handbook/newbus/": "Architecture - Newbus",
        "https://docs.freebsd.org/en/books/arch-handbook/vm/": "Architecture - Virtual Memory",
        "https://docs.freebsd.org/en/books/arch-handbook/smp/": "Architecture - SMP",
    })

    def __init__(self, base_dir, source_key=None):
        name = f"freebsd-{source_key}" if source_key else "freebsd"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles, nav, header, footer, aside and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL)
        text = re.sub(r'<aside[^>]*>.*?</aside>', '', text, flags=re.DOTALL)
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
            for suffix in [
                ' | FreeBSD Documentation',
                ' - FreeBSD Handbook',
                ' | FreeBSD Wiki',
                ' - FreeBSD',
                ' | FreeBSD',
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
                        "category": f"freebsd-{source_key}",
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
            self.log.info(f"=== Scraping freebsd/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    FreeBSDScraper(base, source_key).run()
