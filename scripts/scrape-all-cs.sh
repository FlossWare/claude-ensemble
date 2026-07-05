#!/usr/bin/env bash
#
# ULTIMATE COMPUTER SCIENCE KNOWLEDGE SCRAPER
# Scrapes ALL CS research topics from arXiv for LLM training
#

cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 ULTIMATE COMPUTER SCIENCE TRAINING DATA GENERATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Scraping 20+ CS topics from arXiv:"
echo ""
echo "AI/ML (8 topics):"
echo "  ✓ Transformers & Attention"
echo "  ✓ Neural Networks"
echo "  ✓ Genetic Algorithms"
echo "  ✓ Reinforcement Learning"
echo "  ✓ GANs & Generative Models"
echo "  ✓ Diffusion Models"
echo "  ✓ Optimization"
echo "  ✓ State Space Models (Mamba)"
echo ""
echo "Core CS (12 topics):"
echo "  ✓ Algorithms & Data Structures"
echo "  ✓ Databases"
echo "  ✓ Distributed Systems"
echo "  ✓ Compilers & Programming Languages"
echo "  ✓ Operating Systems"
echo "  ✓ Networking"
echo "  ✓ Security & Cryptography"
echo "  ✓ Computer Vision"
echo "  ✓ NLP & Computational Linguistics"
echo "  ✓ Robotics"
echo "  ✓ Software Engineering"
echo "  ✓ Theory of Computation"
echo ""
echo "Target: 1,000 papers × 2 examples = 2,000 training examples"
echo "Cost: \$0.00 (Cloudflare FREE API)"
echo "Time: ~4-6 hours"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Starting in 3 seconds..."
sleep 3

# AI/ML Topics (50 papers each)
python3 tools/arxiv_paper_scraper.py transformers 50 > ~/.claude/logs/cs_transformers.log 2>&1 &
python3 tools/arxiv_paper_scraper.py neural_nets 50 > ~/.claude/logs/cs_neural.log 2>&1 &
python3 tools/arxiv_paper_scraper.py genetic_algorithms 50 > ~/.claude/logs/cs_genetic.log 2>&1 &
python3 tools/arxiv_paper_scraper.py reinforcement_learning 50 > ~/.claude/logs/cs_rl.log 2>&1 &
python3 tools/arxiv_paper_scraper.py gan 50 > ~/.claude/logs/cs_gan.log 2>&1 &
python3 tools/arxiv_paper_scraper.py diffusion 50 > ~/.claude/logs/cs_diffusion.log 2>&1 &
python3 tools/arxiv_paper_scraper.py optimization 50 > ~/.claude/logs/cs_optimization.log 2>&1 &
python3 tools/arxiv_paper_scraper.py mamba_ssm 50 > ~/.claude/logs/cs_mamba.log 2>&1 &

# Core CS Topics (50 papers each)
python3 tools/arxiv_paper_scraper.py "algorithms data structures" 50 > ~/.claude/logs/cs_algorithms.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "database systems" 50 > ~/.claude/logs/cs_databases.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "distributed systems" 50 > ~/.claude/logs/cs_distributed.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "compilers programming languages" 50 > ~/.claude/logs/cs_compilers.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "operating systems" 50 > ~/.claude/logs/cs_os.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "computer networks" 50 > ~/.claude/logs/cs_networks.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cryptography security" 50 > ~/.claude/logs/cs_security.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "computer vision" 50 > ~/.claude/logs/cs_vision.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "natural language processing" 50 > ~/.claude/logs/cs_nlp.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "robotics" 50 > ~/.claude/logs/cs_robotics.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "software engineering" 50 > ~/.claude/logs/cs_software.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "theory of computation" 50 > ~/.claude/logs/cs_theory.log 2>&1 &

echo ""
echo "✅ Launched 20 parallel scraping jobs!"
echo ""
echo "Monitor progress:"
echo "  tail -f ~/.claude/logs/cs_*.log"
echo ""
echo "Check running jobs:"
echo "  ps aux | grep arxiv_paper_scraper"
echo ""
echo "Estimated completion: 4-6 hours"
echo "You'll have 2,000 research paper training examples!"
