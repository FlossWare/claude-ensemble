#!/usr/bin/env bash
# altf-expert - Alt-F NAS Firmware Expert
set -euo pipefail

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_DIR="$SCRIPT_DIR/cli"

EXPERT_SYSTEM_PROMPT="You are an Alt-F expert with deep knowledge of:
- Alt-F firmware for NAS devices (DNS-323, DNS-320, etc.)
- Web interface configuration
- Package management (ipkg/opkg)
- Samba, NFS, and file sharing
- RAID configuration and disk management
- User and permission management
- Transmission, rsync, and services
- Alt-F specific scripts and customization
Always backup data before firmware updates and RAID changes."
show_help() {
    echo "altf-expert - Alt-F NAS Firmware (granite4.1:8b)"
    echo "COMMANDS: install, raid, shares, packages, services, backup, ask"
}
main() { show_help; }
main "$@"
