#!/usr/bin/env bash
# Rotate personal API keys: updates orchestrator DB, settings.json, and .bashrc
# Usage: rotate-keys.sh
# Interactive — prompts for each new key value, skips if blank.
set -euo pipefail

PSQL_CMD='psql -U claude -d learning -h localhost -p 5433 -tAc'

update_secret() {
    local key="$1" value="$2" desc="$3"
    ssh -o ConnectTimeout=5 aio-01 "$PSQL_CMD \"
        INSERT INTO auth.secrets (key, value, description)
        VALUES ('$key', '$value', '$desc')
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, description = EXCLUDED.description;
    \"" 2>/dev/null
    echo "  Updated orchestrator: $key"
}

update_bashrc() {
    local varname="$1" value="$2"
    if grep -q "^export ${varname}=" ~/.bashrc 2>/dev/null; then
        sed -i "s|^export ${varname}=.*|export ${varname}='${value}'|" ~/.bashrc
        echo "  Updated .bashrc: $varname"
    else
        echo "export ${varname}='${value}'" >> ~/.bashrc
        echo "  Added to .bashrc: $varname"
    fi
}

update_settings_json() {
    local old_val="$1" new_val="$2" file="$3"
    if [ -f "$file" ] && grep -q "$old_val" "$file" 2>/dev/null; then
        sed -i "s|${old_val}|${new_val}|g" "$file"
        echo "  Updated settings.json"
    fi
}

echo "=== Personal API Key Rotation ==="
echo "Paste new key for each service, or press Enter to skip."
echo ""

# --- GitHub PAT ---
echo "1. PERSONAL_GITHUB_TOKEN"
echo "   Generate at: https://github.com/settings/tokens?type=beta"
read -rp "   New key: " NEW_GITHUB
if [ -n "$NEW_GITHUB" ]; then
    OLD=$(ssh -o ConnectTimeout=5 aio-01 "curl -s http://localhost:5000/secrets/PERSONAL_GITHUB_TOKEN" | python3 -c "import sys,json;print(json.loads(sys.stdin.read())['value'])")
    update_secret "PERSONAL_GITHUB_TOKEN" "$NEW_GITHUB" "GitHub Personal Access Token (rotated $(date +%Y-%m-%d))"
    update_bashrc "PERSONAL_GITHUB_TOKEN" "$NEW_GITHUB"
    # Update the GitHub MCP server config
    CLAUDE_JSON="$HOME/.claude.json"
    if [ -f "$CLAUDE_JSON" ]; then
        update_settings_json "$OLD" "$NEW_GITHUB" "$CLAUDE_JSON"
    fi
    echo "  Done"
fi
echo ""

# --- Google Personal API Key ---
echo "2. PERSONAL_GOOGLE_API_KEY"
echo "   Generate at: https://aistudio.google.com/apikey"
read -rp "   New key: " NEW_GOOGLE_API
if [ -n "$NEW_GOOGLE_API" ]; then
    update_secret "PERSONAL_GOOGLE_API_KEY" "$NEW_GOOGLE_API" "Personal Google AI Studio Gemini API Key (rotated $(date +%Y-%m-%d))"
    update_bashrc "PERSONAL_GOOGLE_API_KEY" "$NEW_GOOGLE_API"
    echo "  Done"
fi
echo ""

# --- Google OAuth Client ID ---
echo "3. PERSONAL_GOOGLE_CLIENT_ID"
echo "   Generate at: https://console.cloud.google.com/apis/credentials"
read -rp "   New Client ID: " NEW_GCID
if [ -n "$NEW_GCID" ]; then
    OLD=$(ssh -o ConnectTimeout=5 aio-01 "curl -s http://localhost:5000/secrets/PERSONAL_GOOGLE_CLIENT_ID" | python3 -c "import sys,json;print(json.loads(sys.stdin.read())['value'])")
    update_secret "PERSONAL_GOOGLE_CLIENT_ID" "$NEW_GCID" "Personal Google OAuth client ID (rotated $(date +%Y-%m-%d))"
    update_settings_json "$OLD" "$NEW_GCID" "$HOME/.claude/settings.json"
    echo "  Done"
fi
echo ""

# --- Google OAuth Client Secret ---
echo "4. PERSONAL_GOOGLE_CLIENT_SECRET"
echo "   (same credentials page as Client ID)"
read -rp "   New Client Secret: " NEW_GCSEC
if [ -n "$NEW_GCSEC" ]; then
    OLD=$(ssh -o ConnectTimeout=5 aio-01 "curl -s http://localhost:5000/secrets/PERSONAL_GOOGLE_CLIENT_SECRET" | python3 -c "import sys,json;print(json.loads(sys.stdin.read())['value'])")
    update_secret "PERSONAL_GOOGLE_CLIENT_SECRET" "$NEW_GCSEC" "Personal Google OAuth client secret (rotated $(date +%Y-%m-%d))"
    update_settings_json "$OLD" "$NEW_GCSEC" "$HOME/.claude/settings.json"
    echo "  Done"
fi
echo ""

# --- Notion ---
echo "5. PERSONAL_NOTION_TOKEN"
echo "   Generate at: https://www.notion.so/my-integrations"
read -rp "   New key: " NEW_NOTION
if [ -n "$NEW_NOTION" ]; then
    OLD=$(ssh -o ConnectTimeout=5 aio-01 "curl -s http://localhost:5000/secrets/PERSONAL_NOTION_TOKEN" | python3 -c "import sys,json;print(json.loads(sys.stdin.read())['value'])")
    update_secret "PERSONAL_NOTION_TOKEN" "$NEW_NOTION" "Personal Notion integration token (rotated $(date +%Y-%m-%d))"
    update_bashrc "PERSONAL_NOTION_TOKEN" "$NEW_NOTION"
    update_settings_json "$OLD" "$NEW_NOTION" "$HOME/.claude/settings.json"
    echo "  Done"
fi
echo ""

# --- Mistral ---
echo "6. PERSONAL_MISTRAL_API_KEY"
echo "   Generate at: https://console.mistral.ai/api-keys"
read -rp "   New key: " NEW_MISTRAL
if [ -n "$NEW_MISTRAL" ]; then
    update_secret "PERSONAL_MISTRAL_API_KEY" "$NEW_MISTRAL" "Personal Mistral API key (rotated $(date +%Y-%m-%d))"
    update_bashrc "PERSONAL_MISTRAL_API_KEY" "$NEW_MISTRAL"
    echo "  Done"
fi
echo ""

# --- HuggingFace ---
echo "7. PERSONAL_HUGGINGFACE_API_KEY"
echo "   Generate at: https://huggingface.co/settings/tokens"
read -rp "   New key: " NEW_HF
if [ -n "$NEW_HF" ]; then
    update_secret "PERSONAL_HUGGINGFACE_API_KEY" "$NEW_HF" "Personal HuggingFace API token (rotated $(date +%Y-%m-%d))"
    update_bashrc "PERSONAL_HUGGINGFACE_API_KEY" "$NEW_HF"
    echo "  Done"
fi
echo ""

# --- DeepInfra ---
echo "8. PERSONAL_DEEPINFRA_API_KEY"
echo "   Generate at: https://deepinfra.com/dash/api_keys"
read -rp "   New key: " NEW_DI
if [ -n "$NEW_DI" ]; then
    update_secret "PERSONAL_DEEPINFRA_API_KEY" "$NEW_DI" "Personal DeepInfra API key (rotated $(date +%Y-%m-%d))"
    update_bashrc "PERSONAL_DEEPINFRA_API_KEY" "$NEW_DI"
    echo "  Done"
fi
echo ""

# --- Trello ---
echo "9. PERSONAL_TRELLO_API_KEY"
echo "   Generate at: https://trello.com/app-key"
read -rp "   New API key: " NEW_TRELLO_KEY
if [ -n "$NEW_TRELLO_KEY" ]; then
    OLD=$(ssh -o ConnectTimeout=5 aio-01 "curl -s http://localhost:5000/secrets/PERSONAL_TRELLO_API_KEY" | python3 -c "import sys,json;print(json.loads(sys.stdin.read())['value'])")
    update_secret "PERSONAL_TRELLO_API_KEY" "$NEW_TRELLO_KEY" "Personal Trello API key (rotated $(date +%Y-%m-%d))"
    update_bashrc "PERSONAL_TRELLO_API_KEY" "$NEW_TRELLO_KEY"
    update_settings_json "$OLD" "$NEW_TRELLO_KEY" "$HOME/.claude/settings.json"
    echo "  Done"
fi
echo ""

echo "10. PERSONAL_TRELLO_TOKEN"
echo "    (OAuth token from Trello — link shown after generating API key above)"
read -rp "   New token: " NEW_TRELLO_TOK
if [ -n "$NEW_TRELLO_TOK" ]; then
    OLD=$(ssh -o ConnectTimeout=5 aio-01 "curl -s http://localhost:5000/secrets/PERSONAL_TRELLO_TOKEN" | python3 -c "import sys,json;print(json.loads(sys.stdin.read())['value'])")
    update_secret "PERSONAL_TRELLO_TOKEN" "$NEW_TRELLO_TOK" "Personal Trello auth token (rotated $(date +%Y-%m-%d))"
    update_bashrc "PERSONAL_TRELLO_TOKEN" "$NEW_TRELLO_TOK"
    update_settings_json "$OLD" "$NEW_TRELLO_TOK" "$HOME/.claude/settings.json"
    echo "  Done"
fi
echo ""

# --- Unstructured ---
echo "11. PERSONAL_UNSTRUCTURED_API_KEY"
echo "    Generate at: https://app.unstructured.io"
read -rp "   New key: " NEW_UNSTR
if [ -n "$NEW_UNSTR" ]; then
    update_secret "PERSONAL_UNSTRUCTURED_API_KEY" "$NEW_UNSTR" "Personal Unstructured.io API key (rotated $(date +%Y-%m-%d))"
    update_bashrc "PERSONAL_UNSTRUCTURED_API_KEY" "$NEW_UNSTR"
    echo "  Done"
fi
echo ""

echo "=== Rotation complete ==="
echo "Run 'source ~/.bashrc' to load updated keys in this shell."
