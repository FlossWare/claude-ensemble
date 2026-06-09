---
name: project-de-converter
description: de-converter project - Desktop environment configuration converter (GitHub repository)
metadata: 
  node_type: memory
  type: project
  originSessionId: 97e2ffe0-6678-42c0-bb00-b637160800ac
---

# de-converter Project

**Repository:** https://github.com/FlossWare/de-converter (GitHub)
**Location:** `~/Development/github/FlossWare/de-converter/`
**Purpose:** Convert desktop environment configurations to lightweight window manager configurations

## Overview

Desktop environment configuration converter. Migrate from LXDE/XFCE/KDE to fvwm/jwm/i3 while preserving your settings, keybindings, and workflows.

**Tagline:** *Your desktop environment, on any window manager.*

## Current Support

### LXDE ✅ Complete
**Converters:**
- `converters/lxde/lxde-extract.py` - Extract LXDE configs to JSON
- `converters/lxde/lxde-to-fvwm.py` - Generate fvwm modular configs
- `converters/lxde/lxde-to-jwm.py` - Generate jwm XML config

**What Gets Converted:**
- Desktop names and layout (e.g., "Amanda", "Scot")
- Keybindings and mouse bindings
- Application launchers (organized by category)
- Panel/tray configuration (position, autohide, height)
- Window manager behavior (focus model, placement)
- Autostart applications
- GTK theme and font settings

**Usage:**
```bash
python3 converters/lxde/lxde-extract.py ~/.config -o config.json -p
python3 converters/lxde/lxde-to-fvwm.py config.json -o ~/fvwm-config
python3 converters/lxde/lxde-to-jwm.py config.json -o ~/.jwmrc
```

## Planned Converters

### Desktop Environments
- [ ] XFCE - Placeholder in `converters/xfce/`
- [ ] KDE Plasma - Placeholder in `converters/kde/`
- [ ] MATE
- [ ] Cinnamon

### Window Managers (Output Formats)
- [x] fvwm (modular: .fvwm2rc, styles, keybindings, menus, functions)
- [x] jwm (single XML file)
- [ ] i3/sway
- [ ] awesome
- [ ] dwm
- [ ] bspwm

## Project Structure

```
de-converter/
├── converters/
│   ├── lxde/           # LXDE converters (complete)
│   ├── xfce/           # Placeholder
│   └── kde/            # Placeholder
├── docs/
│   ├── config-mapping.md           # LXDE→fvwm/jwm mappings
│   └── freebsd-compatibility.md
├── examples/
│   ├── lxde/           # Extracted JSON
│   ├── fvwm/           # Generated configs
│   └── jwm/            # Generated configs
└── tests/
    ├── validate-configs.sh
    └── freebsd-adjust-paths.sh
```

## Key Mappings (LXDE/OpenBox → fvwm/jwm)

| Feature | OpenBox | fvwm | jwm |
|---------|---------|------|-----|
| Desktop switch | `C-A-Left` | `Key Left A CM GotoDesk -1 0` | `<Key mask="CA" key="Left">ldesktop</Key>` |
| Close window | `A-F4` | `Key F4 A M Close` | `<Key mask="A" key="F4">close</Key>` |
| Focus model | `followMouse=yes` | `SloppyFocus` | `<FocusModel>sloppy</FocusModel>` |

## FreeBSD Compatibility

All converters work on FreeBSD with path adjustments:
- Use `tests/freebsd-adjust-paths.sh` to convert paths
- `/usr/share` → `/usr/local/share`
- `/usr/bin` → `/usr/local/bin`

## How to Apply

When working on desktop environment conversion tasks:
- Use this project for migrating DE configs to window managers
- Follow the modular pattern from LXDE converters
- Extract to JSON intermediate format
- Support multiple output formats (fvwm, jwm, etc.)
- Include validation tools
- Document config mappings
- Support FreeBSD
