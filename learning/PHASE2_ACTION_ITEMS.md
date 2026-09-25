# Phase 2 ACTION ITEMS - Model Performance Dashboard Enhancements

**Phase 1 Verdict:** WORKING SYSTEM READY FOR PHASE 2  
**Phase 2 Start Date:** 2026-09-26  
**Goal:** Optimize learning dynamics, add anomaly detection, enable forecasting

---

## High-Priority Actions (Week 1)

### 1. Regression Detection (Issue #251) - IN PROGRESS ✓
**Status:** Partially complete (exists in code)  
**Missing:** Automated triggering and alerting

#### Task
- Enable `schema-ml-models-monitoring.sql` views for drift detection
- Wire up regression detection to alert system (webhook-notifier.cjs)
- Set thresholds for quality degradation (trigger alert if quality drops > 5%)
- Test with simulated model failure

#### Files to Update
- `/monitoring/webhook-notifier.cjs` - Add regression alerts
- `/shared/learning-metrics.js` - Add regression confidence intervals
- Database trigger in `schema-ml-models-monitoring.sql`

#### Success Criteria
- Alert fires when model quality drops > 5%
- Dashboard shows regression with confidence interval
- Alert integrates with RH notification system

---

### 2. Task Type Classifier - NEW
**Status:** Not yet started  
**Priority:** HIGH (required for task-specific routing)

#### Task
- Build ML classifier to categorize tasks automatically
- Categories: code_review, testing, documentation, refactoring, research, architecture
- Use task embeddings + existing labels to train
- Integrate into dashboard for task breakdown accuracy

#### Implementation Plan
- **Step 1:** Extract 336 historical tasks from learning logs
- **Step 2:** Manually label 50-100 tasks (stratified sample)
- **Step 3:** Train classifier (LLM-based: use Sonnet to classify)
- **Step 4:** Apply to all 336 historical tasks
- **Step 5:** Integrate classifier into cost tracking pipeline

#### Files to Create
- `/tools/task_classifier.py` - Training + inference
- `/shared/task_embeddings.jsonl` - Pre-computed embeddings
- Integration into `/cost_tracking/integration.py`

#### Success Criteria
- 85%+ accuracy on labeled tasks
- Classifier ready for online use (real-time classification)

---

### 3. Thompson Exploration Tuning - IMPROVEMENT
**Status:** Working but suboptimal  
**Current Issue:** Haiku underutilized (2% vs potential 50%)

#### Task
- Analyze Thompson posterior distribution (per Issue #251)
- Add epsilon-greedy exploration: 10% random model selection
- Track exploration impact on learning speed
- Compare: Standard Thompson vs Thompson + epsilon-greedy

#### Implementation
- Update `/shared/thompson-sampling-helper.js`:
  ```js
  // Current: Pure exploitation
  selectedModel = argmax(posterior)
  
  // New: Epsilon-greedy
  if (random() < 0.1) {
    selectedModel = randomModel()  // Explore
  } else {
    selectedModel = argmax(posterior)  // Exploit
  }
  ```

#### Metrics to Track
- Learning speed: % improvement in 50-task window
- Haiku utilization: % increase from 2% baseline
- Quality impact: Does exploration hurt quality?

---

### 4. Confidence Intervals on Metrics - NEW
**Status:** Not yet started  
**Priority:** MEDIUM (needed for statistical rigor)

#### Task
- Add 95% confidence intervals to quality metrics
- Use bootstrap method (1000 resamples)
- Display on dashboard with upper/lower bounds
- Mark metrics as "uncertain" if CI width > 10%

#### Files to Create
- `/tools/metric_confidence_intervals.py` - CI calculation
- Update `/tools/performance_dashboard.py` - Display CI on dashboard
- Update Grafana dashboards with CI bands

#### Calculation Method
```
For each metric (e.g., model accuracy):
1. Draw N samples from historical data
2. Compute metric for each sample
3. Sort results
4. CI = [percentile(2.5), percentile(97.5)]
```

#### Success Criteria
- Dashboard shows CI ranges
- "Uncertain" metrics marked (sample count < 10)
- Statistical power increased

---

## Medium-Priority Actions (Week 2)

### 5. Forecast Model - NEW
**Status:** Not yet started  
**Priority:** MEDIUM

#### Task
- Build ARIMA/Prophet model for cost forecasting
- Predict next 30 days of costs based on trends
- Include seasonality (peak hours, day of week)
- Dashboard integration

#### Implementation
- Use `/cost_tracking/api_costs.jsonl` as training data
- Fit separate models for: total_cost, tokens, model_utilization
- Evaluate RMSE on validation set

#### Files to Create
- `/tools/cost_forecast_model.py` - Training + prediction
- Integration into `/tools/performance_dashboard.py`

---

### 6. Anomaly Detection - NEW
**Status:** Not yet started  
**Priority:** MEDIUM

#### Task
- Detect unusual model performance using isolation forest
- Flag when model deviates > 2σ from baseline
- Use features: latency, success_rate, quality, cost
- Alert on anomalies

#### Implementation
- Train isolation forest on historical data
- Set contamination rate = 0.05 (expect 5% anomalies)
- Run inference on daily metrics

#### Files to Create
- `/tools/anomaly_detector.py` - Detection logic
- Integration into `/monitoring/webhook-notifier.cjs`

---

### 7. Dashboard Enhancements - ITERATION
**Status:** Partially complete  
**Tasks:**

#### 7a. Add Model Comparison Feature
- Side-by-side quality/cost plots
- Select 2-3 models to compare
- Time-series comparison (trend over time)

#### 7b. Add Cost Breakdown by Task Type
- Stacked bar chart: cost by model × task type
- Identify high-cost task types
- Recommend cheaper alternatives

#### 7c. Add "What-If" Simulator
- "If Sonnet quality improves 5%, how much do we save?"
- "If we use Haiku for 30% of tasks, what's the impact?"
- Cost/quality tradeoff visualization

#### Files to Update
- `/tools/performance_dashboard.py` - Add new queries
- `/monitoring/grafana-ml-models-dashboard.json` - New panels
- Create `/tools/dashboard_simulator.py` - What-if engine

---

## Low-Priority Actions (Week 3+)

### 8. Multi-Model Consensus Learning - FUTURE
**Status:** Design phase  
**Description:** Learn which models work well together in 2/3/4-worker consensus

#### Research Questions
- When does adding a 2nd model improve consensus quality?
- Which model pairs have highest consensus accuracy?
- Can we predict consensus quality before running it?

---

### 9. Task Routing Recommender - FUTURE
**Status:** Design phase  
**Description:** Use dashboard data to recommend optimal model for new task

#### Implementation
- Task classifier → Task type
- Task type → Best model (from dashboard history)
- Explain: "Use Sonnet for this type of task (0.89 quality at $0.05)"

---

## Verification Checklist

### Before Deploying Phase 2
- [ ] Regression detection wired to alerts
- [ ] Task classifier trained and integrated
- [ ] Thompson exploration tuned and A/B tested
- [ ] Confidence intervals computed and displayed
- [ ] All new files have unit tests (>80% coverage)
- [ ] Dashboard tested with Phase 2 data (100+ new calls)

### Before Phase 2 Production
- [ ] 7-day monitoring period (no regressions)
- [ ] Learning speed acceptable (>15% improvement in 50 tasks)
- [ ] Cost savings sustained (>45% vs baseline)
- [ ] Quality maintained (>0.85 average)
- [ ] Anomaly detection produces <5% false positives

---

## Dependency Graph

```
Phase 1 COMPLETE: Thompson logs + Cost tracking + Dashboard
    ↓
Phase 2.1 (Week 1):
    ├─ Regression Detection (critical path) → Anomaly Detection
    ├─ Task Classifier (enables task-specific routing)
    └─ Thompson Tuning (improves learning speed)
    
Phase 2.2 (Week 2):
    ├─ Confidence Intervals (needed for statistical rigor)
    ├─ Forecast Model (cost prediction)
    └─ Dashboard Enhancements (enables "what-if" analysis)
    
Phase 3 (Week 3+):
    ├─ Task Routing Recommender
    └─ Multi-Model Consensus Learning
```

---

## Success Metrics for Phase 2

| Metric | Target | Current | Path to Target |
|--------|--------|---------|----------------|
| Learning Speed | 20% improvement/50 tasks | 11% | Thompson + epsilon-greedy |
| Model Utilization Balance | Haiku 50%, Sonnet 40%, Opus 8% | 2%, 82%, 12% | Increase exploration |
| Forecast Accuracy | RMSE < 5% | N/A | Build ARIMA model |
| Anomaly Detection | <5% false positive rate | N/A | Train isolation forest |
| Quality Regression Detected | <1 hour latency | N/A | Wire alerts |
| Cost Savings Maintained | >45% vs baseline | 47.3% | Monitor & tune |

---

## Files to Create/Modify Summary

### New Files (Phase 2)
1. `/tools/task_classifier.py` (200 lines)
2. `/tools/task_embeddings.jsonl` (depends on data)
3. `/tools/metric_confidence_intervals.py` (150 lines)
4. `/tools/cost_forecast_model.py` (200 lines)
5. `/tools/anomaly_detector.py` (150 lines)
6. `/tools/dashboard_simulator.py` (250 lines)

### Modified Files
1. `/shared/thompson-sampling-helper.js` - Add epsilon-greedy
2. `/shared/learning-metrics.js` - Add confidence intervals
3. `/tools/performance_dashboard.py` - Add new queries
4. `/monitoring/webhook-notifier.cjs` - Add regression alerts
5. `/monitoring/grafana-ml-models-dashboard.json` - New panels

### Database
1. Create views for regression detection (schema-ml-models-monitoring.sql)
2. Add forecast table (`learning.model_forecasts`)
3. Add anomalies table (`learning.model_anomalies`)

---

**Next Steps:** Assign workers to Phase 2.1 (Week 1) priority items  
**Phase 2 Start:** 2026-09-26  
**Target Completion:** 2026-10-10
