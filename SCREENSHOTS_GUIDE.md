# Screenshots Guide

**How to capture and add screenshots to documentation**

---

## Screenshots Needed

### Priority 1: Core Workflows

1. **Multi-AI Worker Selection**
   - File: Screenshot when workers are displayed
   - Command: `python-expert.sh review code.py --multi-ai`
   - Shows: Selected workers with 💻/☁️ icons
   - Capture: When "Selected Workers (4):" is displayed

2. **Arbiter/Worker Consensus**
   - File: Screenshot of consensus process
   - Command: Any workflow with `--multi-ai`
   - Shows: Workers proposing, arbiter deciding
   - Capture: Full consensus flow

3. **Web Learning Workflow**
   - File: Screenshot of web-learn in action
   - Command: `/web-learn {urls: ["..."]}`
   - Shows: Fetch → Extract → Validate → Store phases
   - Capture: Progress through all phases

### Priority 2: Universal AI Integration

4. **Vendor Selection Menu**
   - File: Screenshot of vendor browsing
   - Command: `./universal-ai` → `i` → `v`
   - Shows: List of vendors (Meta, Google, IBM, etc.)
   - Capture: Vendor selection screen

5. **Install All from Vendor**
   - File: Screenshot showing "a. Install ALL" option
   - Command: `./universal-ai` → `i` → `v` → `6` (IBM/Red Hat)
   - Shows: Option to install all vendor models
   - Capture: Installation menu

6. **Model Discovery Notification**
   - File: Screenshot of new model notification
   - Command: `./universal-ai` (after model-discovery runs)
   - Shows: "✨ 3 NEW MODELS AVAILABLE! ✨"
   - Capture: Startup notification

7. **Model Switching**
   - File: Screenshot of /model command
   - Command: In AI CLI, type `/model gpt4`
   - Shows: Model switching confirmation
   - Capture: Before and after switch

### Priority 3: Advanced Features

8. **Expert Domain Detection**
   - File: Screenshot during expert creation
   - Command: `expert-designer create fastapi-guru`
   - Shows: Domain detection and model recommendations
   - Capture: Domain detection output

9. **Multi-AI Configuration**
   - File: Screenshot of configure-multi-ai.sh
   - Command: `./configure-multi-ai.sh show`
   - Shows: Current configuration
   - Capture: Full configuration display

10. **Workflow Progress Tracking**
    - File: Screenshot of phase() output
    - Command: Any workflow in progress
    - Shows: Organized phase display
    - Capture: Multi-phase workflow in progress

---

## How to Capture Screenshots

### macOS

```bash
# Full screen
Cmd + Shift + 3

# Selected area
Cmd + Shift + 4

# Window
Cmd + Shift + 4, then Space, then click window
```

### Linux (GNOME)

```bash
# Full screen
PrtScn

# Selected area
Shift + PrtScn

# Window
Alt + PrtScn

# Or use gnome-screenshot
gnome-screenshot        # Full screen
gnome-screenshot -a     # Area
gnome-screenshot -w     # Window
```

### Linux (KDE)

```bash
# Use Spectacle
spectacle               # Opens screenshot tool
```

### Windows

```bash
# Full screen
PrtScn

# Active window
Alt + PrtScn

# Snipping tool
Win + Shift + S
```

---

## Screenshot Naming Convention

**Format:** `feature-name-description.png`

**Examples:**
- `multi-ai-worker-selection.png`
- `vendor-browsing-menu.png`
- `model-discovery-notification.png`
- `expert-domain-detection.png`
- `arbiter-consensus-process.png`

**Storage:** `~/.claude/repos/claude-global-skills/screenshots/`

---

## Adding to Documentation

### Markdown Format

```markdown
### Feature Name

![Feature Screenshot](screenshots/feature-name.png)

*Caption explaining what's shown*

**What you see:**
- Item 1 explained
- Item 2 explained
- Item 3 explained
```

### Example

```markdown
### Multi-AI Worker Selection

![Worker Selection](screenshots/multi-ai-worker-selection.png)

*The system automatically selects the best AI models for your task*

**What you see:**
- 💻 Local models (free, via Ollama)
- ☁️ Cloud models (API costs)
- Model names and providers
- Total workers selected
```

---

## Files to Update

### USER_GUIDE.md

Add screenshots to:
- Getting Started section (vendor browsing)
- Multi-AI Mode section (worker selection)
- Model Discovery section (notifications)
- Expert Domain Detection section

### Universal AI USER_GUIDE.md

Add screenshots to:
- Installation section (vendor menu)
- Advanced Features section (model switching)
- Expert System section (domain detection)

### README.md

Add screenshots to:
- Features Overview section
- Quick Start section

---

## Quick Script to Capture All

```bash
#!/bin/bash
# capture-screenshots.sh - Helper script to guide screenshot capture

SCREENSHOTS_DIR="$HOME/.claude/repos/claude-global-skills/screenshots"
mkdir -p "$SCREENSHOTS_DIR"

echo "Screenshot Capture Guide"
echo "========================"
echo ""
echo "Screenshots will be saved to: $SCREENSHOTS_DIR"
echo ""

# List of screenshots needed
declare -a screenshots=(
  "multi-ai-worker-selection:python-expert.sh review code.py --multi-ai"
  "arbiter-consensus:Any workflow with --multi-ai"
  "web-learn-phases:/web-learn in Claude Code"
  "vendor-menu:./universal-ai → i → v"
  "install-all-vendor:./universal-ai → i → v → 6"
  "model-discovery:./universal-ai (after discovery)"
  "model-switching:/model gpt4 in AI CLI"
  "expert-domain:expert-designer create fastapi-guru"
  "multi-ai-config:./configure-multi-ai.sh show"
  "workflow-progress:Any workflow showing phases"
)

for item in "${screenshots[@]}"; do
  name="${item%%:*}"
  command="${item#*:}"
  
  echo "Screenshot: $name"
  echo "  Command: $command"
  echo "  Save as: $SCREENSHOTS_DIR/$name.png"
  echo ""
  read -p "Press Enter when screenshot captured..."
  echo ""
done

echo "✅ All screenshots captured!"
echo ""
echo "Next steps:"
echo "  1. Review screenshots in $SCREENSHOTS_DIR"
echo "  2. Add to documentation (see SCREENSHOTS_GUIDE.md)"
echo "  3. Commit with: git add screenshots/ && git commit -m 'Add screenshots'"
```

---

## Estimated Time

**Total time:** 1-2 hours

**Breakdown:**
- Capture 10 screenshots: 30-45 minutes
- Add to documentation: 30-45 minutes
- Review and commit: 15-30 minutes

---

## Checklist

- [ ] Create screenshots directory
- [ ] Capture Priority 1 screenshots (core workflows)
- [ ] Capture Priority 2 screenshots (Universal AI)
- [ ] Capture Priority 3 screenshots (advanced features)
- [ ] Add to USER_GUIDE.md
- [ ] Add to Universal AI USER_GUIDE.md
- [ ] Add to README.md
- [ ] Review all screenshots for quality
- [ ] Commit to git

---

## Notes

**Quality tips:**
- Use high resolution (at least 1920x1080)
- Capture full terminal output (no truncation)
- Use clear, readable font size
- Include enough context (command + output)
- Crop unnecessary chrome/borders

**Don't screenshot:**
- Sensitive information (API keys, tokens)
- Personal file paths (use generic examples)
- Error messages (unless intentional)

**Do screenshot:**
- Success states
- Clear examples
- Visual progress indicators
- Before/after comparisons

---

## Summary

Screenshots enhance documentation by:
- ✅ Improving visual learning
- ✅ Clarifying complex features
- ✅ Reducing onboarding time
- ✅ Providing concrete examples

**Ready to capture? Use the checklist above!**
