#!/bin/bash
# Claude Ensemble - Installation Script
#
# Usage (automatic download + install):
#   curl -fsSL https://raw.githubusercontent.com/FlossWare/claude-ensemble/main/install.sh | bash
#
# Or with custom path (for local development):
#   ./install.sh /path/to/claude-ensemble

set -e

REPO_PATH="${1:-.}"

# Auto-clone if repo doesn't exist
if [ ! -d "$REPO_PATH" ] || [ "$REPO_PATH" = "." ]; then
    REPO_PATH="${HOME}/Development/FlossWare/claude-ensemble"

    if [ ! -d "$REPO_PATH" ]; then
        echo "Cloning claude-ensemble repository..."
        mkdir -p "$(dirname "$REPO_PATH")"
        git clone https://github.com/FlossWare/claude-ensemble.git "$REPO_PATH"
    fi
fi

REPO_PATH="$(cd "$REPO_PATH" && pwd)"
CLAUDE_HOME="$HOME/.claude"
MEMORY_SERVICE_DIR="$REPO_PATH/memory-service"

echo "================================================"
echo "  Claude Ensemble Toolkit Installer"
echo "================================================"
echo ""
echo "Repository:  $REPO_PATH"
echo "Claude Home: $CLAUDE_HOME"
echo ""

# Step 1: Create ~/.claude directories
echo "1. Setting up ~/.claude directories..."
mkdir -p "$CLAUDE_HOME"/{hooks,projects/-home-sfloess/memory,cost_tracking}
echo "   ✓ Created directories"

# Step 2: Symlink hooks
echo ""
echo "2. Installing hooks..."
if [ -d "$REPO_PATH/hooks" ]; then
    for hook_file in "$REPO_PATH/hooks"/*.js "$REPO_PATH/hooks"/*.sh; do
        if [ -f "$hook_file" ]; then
            hook_name=$(basename "$hook_file")
            hook_link="$CLAUDE_HOME/hooks/$hook_name"
            rm -f "$hook_link" 2>/dev/null || true
            ln -s "$hook_file" "$hook_link"
            echo "   ✓ Installed $hook_name"
        fi
    done
fi

# Step 3: Setup settings.json (NOT symlinked, user-customizable)
echo ""
echo "3. Setting up settings.json..."
SETTINGS_FILE="$CLAUDE_HOME/settings.json"
SETTINGS_DEFAULT="$REPO_PATH/settings.json.default"
if [ ! -f "$SETTINGS_FILE" ] && [ -f "$SETTINGS_DEFAULT" ]; then
    cp "$SETTINGS_DEFAULT" "$SETTINGS_FILE"
    echo "   ✓ Created $SETTINGS_FILE from template"
elif [ -f "$SETTINGS_FILE" ]; then
    echo "   ✓ $SETTINGS_FILE already exists (keeping existing)"
else
    echo "   ⚠ settings.json.default not found in repo"
fi

# Step 4: Symlink toolkit initialization script
echo ""
echo "4. Installing toolkit init script..."
INIT_LINK="$CLAUDE_HOME/ensemble-init.sh"
INIT_SOURCE="$REPO_PATH/scripts/ensemble-init.sh"
if [ -f "$INIT_SOURCE" ]; then
    rm -f "$INIT_LINK" 2>/dev/null || true
    ln -s "$INIT_SOURCE" "$INIT_LINK"
    echo "   ✓ Installed ensemble-init.sh"
fi

# Step 4b: Symlink config script
CONFIG_LINK="$CLAUDE_HOME/config.sh"
CONFIG_SOURCE="$REPO_PATH/scripts/config.sh"
if [ -f "$CONFIG_SOURCE" ]; then
    rm -f "$CONFIG_LINK" 2>/dev/null || true
    ln -s "$CONFIG_SOURCE" "$CONFIG_LINK"
    echo "   ✓ Installed config.sh"
fi

# Step 5: Symlink GA parameter evolution
echo ""
echo "5. Installing GA parameter evolution..."
GA_LINK="$CLAUDE_HOME/ga_parameter_evolution.md"
GA_SOURCE="$REPO_PATH/ga_tuning/parameter_evolution.md"
if [ -f "$GA_SOURCE" ]; then
    rm -f "$GA_LINK" 2>/dev/null || true
    ln -s "$GA_SOURCE" "$GA_LINK"
    echo "   ✓ Installed ga_parameter_evolution.md"
fi

# Step 6: Symlink memory service client
echo ""
echo "6. Installing memory service client..."
MEMORY_CLIENT="$CLAUDE_HOME/memory-client.py"
MEMORY_SOURCE="$MEMORY_SERVICE_DIR/memory_client.py"
if [ -f "$MEMORY_SOURCE" ]; then
    rm -f "$MEMORY_CLIENT" 2>/dev/null || true
    ln -s "$MEMORY_SOURCE" "$MEMORY_CLIENT"
    echo "   ✓ Installed memory-client.py"
fi

# Step 7: Install memory service (systemd daemon)
echo ""
echo "7. Installing memory service (systemd daemon)..."
if [ -x "$MEMORY_SERVICE_DIR/install.sh" ]; then
    bash "$MEMORY_SERVICE_DIR/install.sh"
else
    echo "   ⚠ Memory service install script not found"
fi

# Step 8: Setup .mcp.json if not exists
echo ""
echo "8. Setting up MCP configuration..."
MCP_CONFIG="$HOME/.mcp.json"
if [ ! -f "$MCP_CONFIG" ]; then
    cat > "$MCP_CONFIG" << 'EOF'
{
  "mcpServers": {
    "atlassian": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-atlassian"],
      "env": {
        "ATLASSIAN_URL": "https://issues.redhat.com",
        "ATLASSIAN_EMAIL": "YOUR_EMAIL@redhat.com",
        "ATLASSIAN_API_TOKEN": "${JIRA_API_TOKEN}"
      }
    },
    "gmail": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-gmail"],
      "env": {
        "GMAIL_ACCOUNT": "YOUR_EMAIL@redhat.com"
      }
    },
    "google-calendar": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-google-calendar"],
      "env": {
        "GOOGLE_CALENDAR_EMAIL": "YOUR_EMAIL@redhat.com"
      }
    }
  }
}
EOF
    echo "   ✓ Created .mcp.json (please edit with your Red Hat email)"
else
    echo "   ✓ .mcp.json already exists"
fi

# Step 9: Setup model configuration
echo ""
echo "9. Setting up model configuration..."
MODEL_CONFIG="$HOME/.claude/rh-toolkit-models.yaml"
if [ ! -f "$MODEL_CONFIG" ]; then
    if [ -f "$REPO_PATH/.rh-toolkit-models.yaml.default" ]; then
        cp "$REPO_PATH/.rh-toolkit-models.yaml.default" "$MODEL_CONFIG"
        echo "   ✓ Created $MODEL_CONFIG from template"
    else
        echo "   ⚠ Model config template not found in repo"
    fi
else
    echo "   ✓ $MODEL_CONFIG already exists"
fi

# Step 10: Check for credentials
echo ""
echo "10. Checking credentials..."
SECRETS_FILE="$HOME/.redhat/secrets.env"
if [ -f "$SECRETS_FILE" ]; then
    echo "   ✓ Found $SECRETS_FILE"
    echo "   ℹ Configure these in ~/.redhat/secrets.env:"
    echo "     - ANTHROPIC_API_KEY"
    echo "     - GOOGLE_API_KEY"
    echo "     - CURSOR_API_KEY"
    echo "     - JIRA_API_TOKEN"
    echo "     - GITLAB_TOKEN"
else
    echo "   ⚠ $SECRETS_FILE not found"
    echo "   ℹ Create it with your Red Hat credentials"
fi

# Step 11: Add tools to PATH (shell init)
echo ""
echo "11. Adding tools to PATH..."
SHELL_RC=""
if [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
elif [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
fi

if [ -n "$SHELL_RC" ]; then
    EXPORT_LINE="export PATH=\"$REPO_PATH/tools:\$PATH\""
    if ! grep -q "claude-global-skills/tools" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# RH Claude Global Skills Tools" >> "$SHELL_RC"
        echo "$EXPORT_LINE" >> "$SHELL_RC"
        echo "   ✓ Added tools to PATH in $SHELL_RC"
    else
        echo "   ✓ Tools already in PATH"
    fi
fi

echo ""
echo "================================================"
echo "  Configuration"
echo "================================================"
echo ""

# Ask if user wants to configure now
read -p "Would you like to configure which tools/features to enable? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    bash "$CONFIG_SOURCE"
else
    echo "   ℹ You can configure anytime by running: ~/.claude/config.sh"
fi

echo ""
echo "================================================"
echo "  Installation Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Edit ~/.mcp.json with your credentials"
echo "2. Ensure API tokens are set in environment"
echo "3. Exit and restart your terminal"
echo "4. Run: ensemble-init.sh (should be automatic at shell start)"
echo "5. To reconfigure tools/features: ~/.claude/config.sh"
echo ""
echo "Verify installation:"
echo "  cost-dashboard.py (view cost tracking)"
echo "  ga-tuning-dashboard.py (view GA parameters)"
echo ""
echo "Documentation: $REPO_PATH/README.md"
echo ""
