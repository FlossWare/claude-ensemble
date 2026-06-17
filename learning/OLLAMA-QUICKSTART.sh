#!/bin/bash

################################################################################
# Ollama Fleet Quick Start
#
# This script provides a guided deployment of the Ollama distributed fleet
################################################################################

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

DEPLOY_SCRIPT="$HOME/.claude/learning/ollama-fleet-deploy.sh"
ROUTER_SCRIPT="$HOME/.claude/learning/ollama-fleet-router.js"

echo -e "${BLUE}"
cat << 'EOF'
╔═══════════════════════════════════════════════════════════════╗
║           OLLAMA DISTRIBUTED FLEET QUICK START                ║
║                                                               ║
║   Deploys 27 Ollama models across 5 nodes                    ║
║   Frees ~100GB disk space on localhost                       ║
║   Smart routing with health checks & failover                ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo ""
echo -e "${GREEN}Current Fleet Plan:${NC}"
echo -e "  • localhost:  36.9 GB (9 models)  - High-frequency coding models"
echo -e "  • server-03:  45.0 GB (3 models)  - Heavy models (22b, 32b params)"
echo -e "  • server-02:  45.5 GB (7 models)  - General-purpose + vision"
echo -e "  • server-01:  21.0 GB (5 models)  - Smaller general models"
echo -e "  • aio-01:      7.0 GB (3 models)  - Tiny fallback models"
echo ""

# Menu
PS3=$'\n'"${YELLOW}Select deployment option:${NC} "
options=(
    "Full Deployment (install Ollama + migrate all models)"
    "Install Ollama Only (on all remote nodes)"
    "Migrate Models Only (assumes Ollama already installed)"
    "Verify Deployment"
    "Test Router"
    "View Fleet Status"
    "Show Detailed Plan"
    "Exit"
)

select opt in "${options[@]}"; do
    case $opt in
        "Full Deployment (install Ollama + migrate all models)")
            echo -e "${GREEN}Starting full fleet deployment...${NC}"
            echo ""
            echo -e "${YELLOW}This will:${NC}"
            echo "  1. Install Ollama on server-01, server-02, server-03, aio-01"
            echo "  2. Export models from localhost"
            echo "  3. Transfer models to target nodes (no re-download)"
            echo "  4. Import models on target nodes"
            echo ""
            read -p "Continue? (y/N) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                "$DEPLOY_SCRIPT" deploy-all
                echo ""
                echo -e "${GREEN}✓ Deployment complete!${NC}"
                echo ""
                echo "Next steps:"
                echo "  • Run option 4 to verify deployment"
                echo "  • Run option 5 to test the router"
            fi
            ;;

        "Install Ollama Only (on all remote nodes)")
            echo -e "${GREEN}Installing Ollama on remote nodes...${NC}"
            echo ""

            for node in server-01 server-02 server-03 aio-01; do
                echo -e "${BLUE}Installing on $node...${NC}"
                "$DEPLOY_SCRIPT" install-ollama "$node" || echo -e "${RED}Failed on $node${NC}"
            done

            echo ""
            echo -e "${GREEN}✓ Installation complete!${NC}"
            echo ""
            echo "Next steps:"
            echo "  • Run option 3 to migrate models"
            ;;

        "Migrate Models Only (assumes Ollama already installed)")
            echo -e "${GREEN}Migrating models to nodes...${NC}"
            echo ""
            echo -e "${YELLOW}This assumes Ollama is already installed on all nodes.${NC}"
            echo ""
            read -p "Continue? (y/N) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                # Extract migrations from registry
                "$DEPLOY_SCRIPT" deploy-all
                echo ""
                echo -e "${GREEN}✓ Migration complete!${NC}"
            fi
            ;;

        "Verify Deployment")
            echo -e "${GREEN}Verifying fleet deployment...${NC}"
            echo ""
            "$DEPLOY_SCRIPT" verify
            ;;

        "Test Router")
            echo -e "${GREEN}Testing Ollama Fleet Router...${NC}"
            echo ""

            if [[ ! -f "$ROUTER_SCRIPT" ]]; then
                echo -e "${RED}Router script not found: $ROUTER_SCRIPT${NC}"
                continue
            fi

            echo -e "${BLUE}1. Routing qwen2.5-coder:7b (should be localhost)${NC}"
            node "$ROUTER_SCRIPT" route "qwen2.5-coder:7b"
            echo ""

            echo -e "${BLUE}2. Routing codestral:22b (should be server-03)${NC}"
            node "$ROUTER_SCRIPT" route "codestral:22b"
            echo ""

            echo -e "${BLUE}3. Recommend best coding model${NC}"
            node "$ROUTER_SCRIPT" recommend coding
            echo ""

            echo -e "${GREEN}✓ Router tests complete${NC}"
            ;;

        "View Fleet Status")
            echo -e "${GREEN}Fleet Status:${NC}"
            echo ""

            if [[ ! -f "$ROUTER_SCRIPT" ]]; then
                echo -e "${RED}Router script not found: $ROUTER_SCRIPT${NC}"
                continue
            fi

            node "$ROUTER_SCRIPT" status
            ;;

        "Show Detailed Plan")
            SUMMARY="$HOME/.claude/learning/ollama-fleet-summary.txt"
            if [[ -f "$SUMMARY" ]]; then
                less "$SUMMARY"
            else
                echo -e "${RED}Summary file not found: $SUMMARY${NC}"
            fi
            ;;

        "Exit")
            echo -e "${GREEN}Exiting...${NC}"
            break
            ;;

        *)
            echo -e "${RED}Invalid option${NC}"
            ;;
    esac
done

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Ollama Fleet Resources:${NC}"
echo ""
echo -e "  Registry:       ${YELLOW}~/.claude/learning/ollama-fleet-distribution.json${NC}"
echo -e "  Router:         ${YELLOW}~/.claude/learning/ollama-fleet-router.js${NC}"
echo -e "  Deploy Script:  ${YELLOW}~/.claude/learning/ollama-fleet-deploy.sh${NC}"
echo -e "  Documentation:  ${YELLOW}~/.claude/learning/OLLAMA-FLEET-DEPLOYMENT.md${NC}"
echo -e "  Summary:        ${YELLOW}~/.claude/learning/ollama-fleet-summary.txt${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
