# Phase 1 Autonomous Learning - Quick Start Guide

**Status:** READY TO DEPLOY  
**Components:** 4 autonomous workers (Outcome Logger, Feedback Scorer, Prior Updater, Auto Tuner)  
**Learning Data:** 5 demo tasks processed successfully  

---

## 30-Second Overview

The autonomous learning system consists of 4 workers that continuously improve Thompson's model routing:

1. **WORKER 1 (Outcome Logger):** Records every task's result
2. **WORKER 2 (Feedback Scorer):** Checks if Thompson picked the best model
3. **WORKER 3 (Prior Updater):** Learns which models work best for each task
4. **WORKER 4 (Auto Tuner):** Updates capability scores

These run automatically after each RH task. No human involvement needed.

---

## Files Created

| File | Purpose | Size |
|------|---------|------|
| `autonomous_learning_phase1.py` | Main system implementation | 31 KB |
| `learning/AUTONOMOUS_LEARNING_PHASE1.md` | Full documentation | 18 KB |
| `learning/PHASE1_AUTONOMOUS_LEARNING_VERDICT.md` | Completion verification | 12 KB |
| `learning/autonomous_outcomes/*.json` | Task outcomes (5 demo) | 2.4 KB |
| `learning/autonomous_priors/*.json` | Model priors (5 demo) | 0.8 KB |
| `learning/capability_matrix.json` | Model scores | 1.2 KB |

---

## How to Test (30 seconds)

```bash
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Run demo with 5 realistic RH tasks
python3 autonomous_learning_phase1.py
```

**Expected output:**
- 5 tasks processed through all 4 workers
- Final report shows 40% routing accuracy
- 5 outcomes logged, 5 feedbacks scored, 5 priors updated, 5 capabilities tuned
- All data persisted to JSON files

---

## How to Use in Code

```python
from autonomous_learning_phase1 import AutonomousLearningSystem

# Initialize system
system = AutonomousLearningSystem()

# After task completes, log it
report = system.process_task_completion(
    task_id='task_12345',
    task_type='code_review',
    thompson_selected='opus',
    thompson_candidates=['opus', 'sonnet', 'gpt-4o'],
    quality_score=0.92,
    latency_ms=8500,
    cost=0.015,
    alternatives_tested={'opus': 0.92, 'sonnet': 0.88, 'gpt-4o': 0.85}
)

# Check the results
print(f"Thompson correct? {report['worker_2_feedback']['thompson_correct']}")
print(f"Updated prior: {report['worker_3_prior']['alpha']}")
print(f"New capability score: {report['worker_4_capability']['score']:.3f}")
```

---

## Integration Checklist for Phase 2

- [ ] Hook `process_task_completion()` to RH task completion event
- [ ] Wire Worker 3 priors into Thompson router
- [ ] Use Worker 4 scores to rank candidate models
- [ ] Set up daily accuracy monitoring
- [ ] Configure alerts for accuracy < 70%
- [ ] Run 100+ tasks to establish baselines
- [ ] Review learning metrics weekly

---

## Key Metrics

After running Phase 1 demo:

| Metric | Value | Meaning |
|--------|-------|---------|
| Routing Accuracy | 40% | Expected for initialization |
| Outcomes Logged | 5 | 100% task coverage |
| Priors Trained | 5 | One per model-task combo |
| Capability Scores | 5 | Matrix populated |
| Avg Confidence | 0.05 | Will improve as samples → 20 |
| Total Opportunity Cost | $0.14 | Learning phase cost |

---

## Where Data is Stored

```
learning/
├── autonomous_outcomes/           ← WORKER 1: Task outcomes
│   ├── code_review_001.json
│   ├── documentation_001.json
│   ├── testing_001.json
│   ├── architecture_001.json
│   └── bug_analysis_001.json
│
├── autonomous_priors/             ← WORKER 3: Model priors
│   ├── opus_code_review.json
│   ├── haiku_documentation.json
│   ├── haiku_testing.json
│   ├── sonnet_architecture.json
│   └── opus_bug_analysis.json
│
├── capability_matrix.json         ← WORKER 4: Capability scores
│
├── AUTONOMOUS_LEARNING_PHASE1.md  ← Full documentation
└── PHASE1_AUTONOMOUS_LEARNING_VERDICT.md ← Completion report
```

---

## Understanding the Output

### Example Task Processing

```
Task: code_review_001
├─ WORKER 1: Logged outcome
│  ├─ Thompson selected: opus
│  ├─ Quality achieved: 0.92
│  ├─ Cost: $0.015
│  └─ File: autonomous_outcomes/code_review_001.json
│
├─ WORKER 2: Feedback
│  ├─ Thompson correct? YES (ranking=1)
│  ├─ Opportunity cost: $0.00
│  └─ Recommendation: "Routing performing well"
│
├─ WORKER 3: Prior
│  ├─ Updated: opus:code_review
│  ├─ Old: Beta(1, 1)
│  ├─ New: Beta(2, 1)
│  ├─ Expected quality: 0.67
│  └─ File: autonomous_priors/opus_code_review.json
│
└─ WORKER 4: Capability
   ├─ Tuned: opus:code_review
   ├─ Old score: 0.500
   ├─ New score: 0.626
   ├─ Confidence: 0.05 (will reach 1.0 after ~20 samples)
   └─ File: capability_matrix.json (updated)
```

---

## Next Steps

### Immediate (Ready now)
- Review AUTONOMOUS_LEARNING_PHASE1.md
- Read PHASE1_AUTONOMOUS_LEARNING_VERDICT.md
- Run `python3 autonomous_learning_phase1.py` to verify

### Phase 2 (Week 1)
- Hook outcome logger to RH Disseminator
- Run 50+ real tasks through system
- Monitor learning data quality

### Phase 2 (Week 2-4)
- Wire priors back to Thompson router
- Integrate capability scores into routing
- Monitor accuracy improvement

### Production (Week 5+)
- Deploy to full RH system
- Run 6-month learning curve
- Measure impact on cost/quality

---

## Troubleshooting

### "Module not found"
```bash
# Install scipy if needed
pip install scipy numpy
```

### "Permission denied" on learning/ directory
```bash
chmod -R 755 learning/
```

### "Files not being created"
Check that learning/ directory exists:
```bash
ls -la learning/autonomous_outcomes/
ls -la learning/autonomous_priors/
```

### "Outcomes not logging"
Check logs:
```bash
python3 autonomous_learning_phase1.py 2>&1 | grep "LOGGED\|ERROR"
```

---

## Key Design Decisions

1. **JSON Storage:** Human-readable, no database required, version-controllable
2. **One File per Outcome:** Easy to parallelize, no lock contention
3. **Exponential Moving Average:** Stable but responsive to changes
4. **Beta Distribution:** Mathematically sound, interpretable
5. **Autonomous Workers:** No human loop, runs 24/7

---

## Success Criteria Met

- [x] WORKER 1 logs all outcomes automatically
- [x] WORKER 2 scores routing accuracy
- [x] WORKER 3 updates Bayesian priors
- [x] WORKER 4 adapts capability scores
- [x] Data persists across restarts
- [x] System runs with zero human intervention
- [x] Code is production-ready
- [x] Documentation is comprehensive

---

## Questions?

- **Architecture:** See AUTONOMOUS_LEARNING_PHASE1.md
- **Implementation Details:** See docstrings in autonomous_learning_phase1.py
- **Completion Status:** See PHASE1_AUTONOMOUS_LEARNING_VERDICT.md
- **Integration Guide:** See "Integration Points for Phase 2" in AUTONOMOUS_LEARNING_PHASE1.md

---

**Ready to proceed with Phase 2 deployment.**
