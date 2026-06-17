# Perpetual AI Expert - Quick Start Guide

**Mission:** Become expert at EVERYTHING in AI  
**Time to first research:** 2 minutes

---

## 1-Minute Setup

```bash
cd ~/.claude/learning
bash setup-perpetual-ai-expert.sh
```

✅ Creates directories  
✅ Checks dependencies  
✅ Initializes databases  
✅ Validates scripts

---

## Run Your First Deep Research

```bash
bash activate-perpetual-ai-expert.sh --deep-dive
```

**What happens:**
- Thompson Sampling selects 15 best queries from 70 total
- Researches ArXiv papers, GitHub code, Stack Overflow, Hacker News
- Extracts algorithms, key concepts, mathematical foundations
- Stores learnings in knowledge base + vector embeddings
- Identifies techniques ready to implement
- **Duration:** 10-15 minutes

---

## Check Status

```bash
bash activate-perpetual-ai-expert.sh --status
```

**Shows:**
- Expertise levels (0-100%) by category
- Papers read, implementations found
- Techniques ready to implement
- Thompson Sampling performance
- Knowledge base statistics

---

## Generate Implementations

```bash
bash activate-perpetual-ai-expert.sh --implement
```

**Generates:**
```
~/Development/ai-implementations/{category}/{technique}/
├── implementation.py       # Algorithm code
├── test_implementation.py  # Tests
├── benchmark.py            # Benchmarks
└── README.md               # Docs + math + references
```

---

## Set Up Continuous Research (Optional)

```bash
sudo cp ~/.claude/learning/perpetual-ai-expert.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable perpetual-ai-expert.timer
sudo systemctl start perpetual-ai-expert.timer
```

**Result:** Runs automatically every 6 hours, forever.

---

## Monitor Everything

```bash
# Unified dashboard (all learning systems)
bash unified-ai-learning-dashboard.sh

# Watch mode (refresh every 30s)
watch -n 30 unified-ai-learning-dashboard.sh

# Logs
tail -f ~/.claude/learning/logs/perpetual-ai-expert.log
```

---

## Research Scope: 70 Queries Across 10 Categories

1. **Advanced Reasoning** - CoT, ToT, process supervision, RLHF
2. **Multi-Agent Orchestration** - debate, swarm, hierarchical
3. **Meta-Learning & AutoML** - MAML, NAS, continual learning
4. **Efficient Inference** - speculative decoding, quantization, MoE
5. **RAG & Knowledge** - ColBERT, dense retrieval, knowledge graphs
6. **Training & Fine-tuning** - LoRA, RLHF, DPO, constitutional AI
7. **Mathematical Foundations** - transformers, attention, optimization
8. **Systems & Infrastructure** - distributed training, inference
9. **Evaluation & Robustness** - benchmarks, adversarial, calibration
10. **Domain-Specific AI** - code, math, science, medical, legal

---

## All Commands

```bash
# Research
activate-perpetual-ai-expert.sh                 # Normal (5 queries)
activate-perpetual-ai-expert.sh --deep-dive     # Deep (15 queries)
activate-perpetual-ai-expert.sh --dry-run       # Preview

# Monitor
activate-perpetual-ai-expert.sh --status        # Status dashboard
unified-ai-learning-dashboard.sh                # All systems
node perpetual-ai-expert-status.js --coverage   # Topic coverage
node perpetual-ai-expert-status.js --watch      # Watch mode

# Implement
activate-perpetual-ai-expert.sh --implement     # Generate next
node ai-implementation-generator.js --list      # List ready
node ai-implementation-generator.js --category=RAG  # Specific

# Systemd
sudo systemctl status perpetual-ai-expert.timer  # Status
sudo journalctl -u perpetual-ai-expert -f        # Logs
```

---

## Files & Locations

```
~/.claude/learning/
├── activate-perpetual-ai-expert.sh          # Main script
├── perpetual-ai-expert.js                   # Research engine
├── perpetual-ai-expert-status.js            # Status dashboard
├── ai-implementation-generator.js           # Code generator
├── unified-ai-learning-dashboard.sh         # Unified dashboard
├── research/
│   ├── ai-expert-knowledge.jsonl            # All learnings
│   ├── ai-expert-vectors.jsonl              # Embeddings
│   └── ai-implementation-queue.jsonl        # Ready to implement
└── logs/
    └── perpetual-ai-expert.log              # Execution log

~/Development/ai-implementations/
└── {category}/{technique}/                   # Generated code
```

---

## Strategy: Investigate → Learn → DO

1. **Investigate:** Thompson Sampling selects best queries
2. **Learn:** Read papers, extract algorithms, understand deeply
3. **DO:** Generate implementations when ready

**No stopping conditions. Perpetual learning.**

---

## Documentation

- **Full Guide:** `~/.claude/learning/PERPETUAL_AI_EXPERT.md`
- **Delivery Summary:** `~/.claude/learning/PERPETUAL_AI_EXPERT_DELIVERY.md`
- **This Guide:** `~/.claude/learning/QUICKSTART_AI_EXPERT.md`

---

## Support

**Logs:**
```bash
tail -f ~/.claude/learning/logs/perpetual-ai-expert.log
```

**State:**
```bash
cat ~/.claude/learning/research/perpetual-ai-expert-state.json | jq .
```

**Help:**
```bash
activate-perpetual-ai-expert.sh --help
node perpetual-ai-expert.js --help
node ai-implementation-generator.js --help
```

---

**Status:** READY  
**Action:** `bash activate-perpetual-ai-expert.sh --deep-dive`  
**Goal:** Become expert at EVERYTHING
