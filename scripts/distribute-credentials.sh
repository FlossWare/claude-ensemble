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
OPENAI_KEY=$(grep "^export OPENAI_API_KEY=" ~/.bashrc | cut -d"'" -f2)
GOOGLE_KEY=$(grep "^export GOOGLE_API_KEY=" ~/.bashrc | cut -d"'" -f2)
GROQ_KEY=$(grep "^export GROQ_API_KEY=" ~/.bashrc | cut -d'"' -f2)
COHERE_KEY=$(grep "^export COHERE_API_KEY=" ~/.bashrc | cut -d'"' -f2)
VERTEX_PROJECT=$(grep "^export ANTHROPIC_VERTEX_PROJECT_ID=" ~/.bashrc | awk -F'=' '{print $2}')
GCP_PROJECT=$(grep "^export GOOGLE_CLOUD_PROJECT=" ~/.bashrc | awk -F'=' '{print $2}')

echo "Found credentials:"
echo "  ✅ OPENAI_API_KEY: ${OPENAI_KEY:0:20}..."
echo "  ✅ GOOGLE_API_KEY: ${GOOGLE_KEY:0:20}..."
echo "  ✅ GROQ_API_KEY: ${GROQ_KEY:0:20}..."
echo "  ✅ COHERE_API_KEY: ${COHERE_KEY:0:20}..."
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
  ssh claude@$worker "sed -i '/^export OPENAI_API_KEY=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export OPENAI_TOKEN=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export GOOGLE_API_KEY=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export GROQ_API_KEY=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export COHERE_API_KEY=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export ANTHROPIC_VERTEX_PROJECT_ID=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export GOOGLE_GENAI_USE_VERTEXAI=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export GOOGLE_CLOUD_PROJECT=/d' ~/.bashrc"
  ssh claude@$worker "sed -i '/^export GOOGLE_CLOUD_LOCATION=/d' ~/.bashrc"

  # Add new API key exports
  ssh claude@$worker "cat >> ~/.bashrc << 'EOFCREDS'

# API Credentials (distributed from aio-01 on $(date))
export OPENAI_API_KEY='$OPENAI_KEY'
export OPENAI_TOKEN=\"\$OPENAI_API_KEY\"
export GOOGLE_API_KEY='$GOOGLE_KEY'
export GROQ_API_KEY=\"$GROQ_KEY\"
export COHERE_API_KEY=\"$COHERE_KEY\"
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
  if ssh claude@$worker "grep -q OPENAI_API_KEY ~/.bashrc"; then
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
echo "  for w in ${WORKERS[@]}; do ssh claude@\$w 'grep OPENAI_API_KEY ~/.bashrc | head -1'; done"
echo
echo "Workers can now make API calls using distributed credentials."
echo
echo "⚠️  SECURITY NOTE: API keys are now on 8 machines. Rotate keys if any worker is compromised."
