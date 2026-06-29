#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Ollama Integration Test"
echo "=========================================="
echo ""

# Test 1: Check if Ollama is running
echo -n "Test 1: Checking if Ollama is running... "
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PASS${NC}"
    OLLAMA_RUNNING=true
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "Ollama is not accessible at http://localhost:11434"
    echo "Please ensure Ollama is running: ollama serve"
    exit 1
fi

echo ""

# Test 2: List available models
echo "Test 2: Listing available models..."
MODELS=$(curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | cut -d'"' -f4)

if [ -z "$MODELS" ]; then
    echo -e "${YELLOW}⚠ WARNING: No models found${NC}"
    echo "Install a model with: ollama pull llama3"
    echo ""
else
    echo -e "${GREEN}Available models:${NC}"
    echo "$MODELS" | while read -r model; do
        echo "  - $model"
    done
    echo ""
fi

# Test 3: Run a simple test prompt if llama3 is available
echo "Test 3: Testing model execution..."
if echo "$MODELS" | grep -q "llama3"; then
    echo "Running test prompt with ollama:llama3..."
    RESPONSE=$(curl -s http://localhost:11434/api/generate \
        -d '{
            "model": "llama3",
            "prompt": "Say hello in one word",
            "stream": false
        }' | grep -o '"response":"[^"]*"' | cut -d'"' -f4)

    if [ -n "$RESPONSE" ]; then
        echo -e "${GREEN}✓ PASS${NC}"
        echo "Model response: $RESPONSE"
    else
        echo -e "${RED}✗ FAIL${NC}"
        echo "Model did not return a response"
    fi
else
    echo -e "${YELLOW}⚠ SKIPPED: llama3 model not found${NC}"
    echo "Install with: ollama pull llama3"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Integration test complete!${NC}"
echo "=========================================="
