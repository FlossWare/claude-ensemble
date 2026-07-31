#!/bin/bash
#
# Distribute API credentials to all fleet workers
# Copies API keys from aio-01 to workers' ~/.bashrc
#

set -e

WORKERS=(server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap)

echo "🔐 Distributing API credentials to fleet workers..."
echo "=================================================="
echo

# Extract API keys from current .bashrc
OPENAI_KEY=$(grep "^export PERSONAL_OPENAI_API_KEY=" ~/.bashrc | cut -d"'" -f2)
GOOGLE_KEY=$(grep "^export GOOGLE_API_KEY=" ~/.bashrc | cut -d"'" -f2)
GROQ_KEY=$(grep "^export PERSONAL_GROQ_API_KEY=" ~/.bashrc | cut -d'"' -f2)
COHERE_KEY=$(grep "^export PERSONAL_COHERE_API_KEY=" ~/.bashrc | cut -d'"' -f2)
VERTEX_PROJECT=$(grep "^export ANTHROPIC_VERTEX_PROJECT_ID=" ~/.bashrc | awk -F'=' '{print $2}')
GCP_PROJECT=$(grep "^export GOOGLE_CLOUD_PROJECT=" ~/.bashrc | awk -F'=' '{print $2}')

echo "Found credentials:"
echo "  ✅ PERSONAL_OPENAI_API_KEY: ${OPENAI_KEY:0:20}..."
echo "  ✅ GOOGLE_API_KEY: ${GOOGLE_KEY:0:20}..."
echo "  ✅ PERSONAL_GROQ_API_KEY: ${GROQ_KEY:0:20}..."
echo "  ✅ PERSONAL_COHERE_API_KEY: ${COHERE_KEY:0:20}..."
echo "  ✅ ANTHROPIC_VERTEX_PROJECT_ID: $VERTEX_PROJECT"
echo "  ✅ GOOGLE_CLOUD_PROJECT: $GCP_PROJECT"
echo

for worker in "${WORKERS[@]}"; do
  echo "📡 Configuring $worker..."

  # Check if online
  if ! ssh -o ConnectTimeout=2 claude@$worker echo ping &>/dev/null; then
    echo "   ❌ OFFLINE - skipping"
    echo
    continue
  fi

  # Backup existing .bashrc
  ssh claude@$worker "cp ~/.bashrc ~/.bashrc.backup-\$(date +%Y%m%d-%H%M%S) 2>/dev/null || true"

  # Remove old API key exports (if any)
  ssh claude@$worker "sed -i '/^export PERSONAL_OPENAI_API_KEY=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export OPENAI_TOKEN=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export GOOGLE_API_KEY=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export PERSONAL_GROQ_API_KEY=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export PERSONAL_COHERE_API_KEY=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export ANTHROPIC_VERTEX_PROJECT_ID=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export GOOGLE_GENAI_USE_VERTEXAI=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export GOOGLE_CLOUD_PROJECT=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export GOOGLE_CLOUD_LOCATION=/d' ~/.bashrc"

  # Add new API key exports
  ssh claude@$worker "cat >> ~/.bashrc << 'EOFCREDS'

# API Credentials (distributed from aio-01 on $(date))
export PERSONAL_OPENAI_API_KEY='$OPENAI_KEY'
export OPENAI_TOKEN=\"\$PERSONAL_OPENAI_API_KEY\"
export GOOGLE_API_KEY='$GOOGLE_KEY'
export PERSONAL_GROQ_API_KEY=\"$GROQ_KEY\"
export PERSONAL_COHERE_API_KEY=\"$COHERE_KEY\"
export ANTHROPIC_VERTEX_PROJECT_ID=$VERTEX_PROJECT
export GOOGLE_GENAI_USE_VERTEXAI=True
export GOOGLE_CLOUD_PROJECT=$GCP_PROJECT
export GOOGLE_CLOUD_LOCATION=global
EOFCREDS
"

  # Also create ~/.claude/credentials.json for programs that read it
  ssh claude@$worker "mkdir -p ~/.claude"
  ssh claude@$worker "cat > ~/.claude/credentials.json << 'EOFJSON'
{
  \"openai\": \"$OPENAI_KEY\",
  \"google\": \"$GOOGLE_KEY\",
  \"groq\": \"$GROQ_KEY\",
  \"cohere\": \"$COHERE_KEY\",
  \"anthropic_vertex_project_id\": \"$VERTEX_PROJECT\",
  \"google_cloud_project\": \"$GCP_PROJECT\"
}
EOFJSON
"

  ssh claude@$worker "chmod 600 ~/.claude/credentials.json"

  # Verify
  if ssh claude@$worker "grep -q PERSONAL_OPENAI_API_KEY ~/.bashrc"; then
    echo "   ✅ Credentials configured"
  else
    echo "   ❌ Failed to configure"
  fi

  echo
done

echo
echo "✅ Credential distribution complete!"
echo
echo "To verify:"
echo "  for w in ${WORKERS[@]}; do ssh claude@\$w 'grep PERSONAL_OPENAI_API_KEY ~/.bashrc | head -1'; done"
echo
echo "Workers can now make API calls using distributed credentials."
echo
echo "⚠️  SECURITY NOTE: API keys are now on 8 machines. Rotate keys if any worker is compromised."

# Additional API keys (appending to existing script)
echo
echo "Adding additional API credentials..."

DEEPSEEK_KEY=$(grep "^export PERSONAL_DEEPSEEK_API_KEY=" ~/.bashrc | cut -d"'" -f2)
CEREBRAS_KEY=$(grep "^export PERSONAL_CEREBRAS_API_KEY=" ~/.bashrc | cut -d"'" -f2)
CLOUDFLARE_KEY=$(grep "^export PERSONAL_CLOUDFLARE_API_KEY=" ~/.bashrc | cut -d"'" -f2)
OPENROUTER_KEY=$(grep "^export PERSONAL_OPENROUTER_API_KEY=" ~/.bashrc | cut -d"'" -f2)

echo "  ✅ PERSONAL_DEEPSEEK_API_KEY: ${DEEPSEEK_KEY:0:20}..."
echo "  ✅ PERSONAL_CEREBRAS_API_KEY: ${CEREBRAS_KEY:0:20}..."
echo "  ✅ PERSONAL_CLOUDFLARE_API_KEY: ${CLOUDFLARE_KEY:0:20}..."
echo "  ✅ PERSONAL_OPENROUTER_API_KEY: ${OPENROUTER_KEY:0:20}..."

for worker in "${WORKERS[@]}"; do
  if ! ssh -o ConnectTimeout=2 claude@$worker echo ping &>/dev/null; then
    continue
  fi
  
  ssh claude@$worker "sed -i '/^export PERSONAL_DEEPSEEK_API_KEY=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export PERSONAL_CEREBRAS_API_KEY=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export PERSONAL_CLOUDFLARE_API_KEY=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export PERSONAL_OPENROUTER_API_KEY=/d' ~/.bashrc"
  
  ssh claude@$worker "cat >> ~/.bashrc << 'EOFMORE'
export PERSONAL_DEEPSEEK_API_KEY='$DEEPSEEK_KEY'
export PERSONAL_CEREBRAS_API_KEY='$CEREBRAS_KEY'
export PERSONAL_CLOUDFLARE_API_KEY='$CLOUDFLARE_KEY'
export PERSONAL_OPENROUTER_API_KEY='$OPENROUTER_KEY'
EOFMORE
"
  
  # Update credentials.json
  ssh claude@$worker "cat > ~/.claude/credentials.json << 'EOFJSON2'
{
  \"openai\": \"$OPENAI_KEY\",
  \"google\": \"$GOOGLE_KEY\",
  \"groq\": \"$GROQ_KEY\",
  \"cohere\": \"$COHERE_KEY\",
  \"deepseek\": \"$DEEPSEEK_KEY\",
  \"cerebras\": \"$CEREBRAS_KEY\",
  \"cloudflare\": \"$CLOUDFLARE_KEY\",
  \"openrouter\": \"$OPENROUTER_KEY\",
  \"anthropic_vertex_project_id\": \"$VERTEX_PROJECT\",
  \"google_cloud_project\": \"$GCP_PROJECT\"
}
EOFJSON2
"
done

echo "✅ Additional APIs distributed!"
