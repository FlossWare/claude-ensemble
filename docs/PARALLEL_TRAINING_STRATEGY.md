# 🚀 **PARALLEL TRAINING & SCRAPING STRATEGY**

## **CURRENT BOTTLENECK ANALYSIS:**

### **aio-01 (8 cores, 31GB RAM):**
```
Current usage:
├─ Training:  100% CPU (all 8 cores), ~6GB RAM
├─ Scraping:  ~5% CPU (I/O bound), ~500MB RAM
└─ TOTAL:     100% CPU, ~7GB RAM

Available:
└─ 24GB RAM still free! ✅
```

### **Other Fleet Machines: 99% IDLE! ❌**
```
server-01, server-02, server-03, laptop-01, 
server-ap, desktop-ap, pi-01
= 32+ cores, 76GB+ RAM doing NOTHING!
```

---

## **OPTIMAL STRATEGY:**

### **1️⃣ TRAINING (CPU-Bound):**

#### **Option A: Single Bigger Model (CURRENT - GOOD)**
```
✅ aio-01: Train 100M Mamba
   - Uses ALL 8 cores efficiently
   - Training time: 12-24 hours
   - Can't easily parallelize one model
```

#### **Option B: Multiple Models in Parallel (ADVANCED)**
```
✅ aio-01:    100M Mamba (CS + Math focus)
✅ laptop-01: 100M Mamba (Physics focus)  
✅ server-01: 100M Mamba (Biology focus)
   
Result: 3 specialized models trained simultaneously!
Later: Ensemble them or pick best
```

#### **Option C: Staged Training (RECOMMENDED)**
```
Phase 1 (NOW): 
  aio-01: Train 100M on current 2,594 examples
  
Phase 2 (Tomorrow):
  When Phase 1 done + more data collected:
  aio-01: Train 1B Mamba on ALL data (12,000+ examples)
```

---

### **2️⃣ SCRAPING (I/O-Bound - MASSIVELY Parallelize!):**

#### **Current: 4 scrapers on aio-01**
```
CPU: ~5% (waiting for API responses)
Bottleneck: API rate limits, not CPU!
```

#### **Optimal: 60 scrapers across 8 machines**
```
aio-01:     8 scrapers
server-01:  8 scrapers
server-02:  8 scrapers
server-03:  8 scrapers
laptop-01:  8 scrapers
server-ap:  8 scrapers
desktop-ap: 8 scrapers
pi-01:      4 scrapers (ARM, lighter load)
───────────────────────
TOTAL:     60 scrapers in parallel!

Result: 60× faster data collection!
        4-8 hours → ALL 12,000 examples!
```

---

## **PARALLELISM MATH:**

### **Scraping Parallelism:**
```
Single scraper:
├─ 100 papers × 2 examples = 200 examples
├─ 1 second per API call
├─ 200 seconds = 3.3 minutes
└─ With rate limits: ~10-15 minutes

60 scrapers in parallel:
├─ 60 topics × 100 papers = 6,000 papers
├─ 12,000 examples total
├─ Each scraper: 10-15 minutes
└─ Wall clock: 10-15 minutes total! 🔥

Speedup: 60× faster!
```

### **Training Parallelism:**
```
Single model training:
├─ 100M params
├─ 2,594 examples
├─ 3 epochs
└─ Time: 12-24 hours (can't parallelize internally)

Multiple models:
├─ Model 1 (aio-01):    CS focus     - 12h
├─ Model 2 (laptop-01): Physics      - 12h
├─ Model 3 (server-01): Biology      - 12h
└─ Wall clock: 12h for 3 models! ✅

Speedup: 3× models in same time!
```

---

## **RECOMMENDED APPROACH:**

### **Phase 1 (RIGHT NOW):**
```
✅ TRAINING:
   aio-01: Continue current 100M training
   (Don't interrupt - already in progress)

✅ SCRAPING:
   ALL 8 machines: Distribute 60 scrapers
   Result: Massive parallelism, 12,000 examples in 4-8h
```

### **Phase 2 (When training completes):**
```
✅ Test the 100M model
✅ Validate it works
✅ Then train bigger 1B model on full dataset
```

---

## **RESOURCE ALLOCATION:**

### **aio-01 (Main Orchestrator):**
```
├─ Training:      100% CPU, 6GB RAM   (1 process)
├─ Scraping:      5% CPU,  500MB RAM  (8 processes)
├─ Books:         5% CPU,  500MB RAM  (1 process)
└─ Available:     0% CPU,  24GB RAM
```

### **Other Machines (Currently Idle):**
```
Each can run:
├─ 8 scrapers simultaneously (I/O bound)
├─ OR 1 training process (CPU bound)
└─ Total across fleet: 48-56 parallel scrapers!
```

---

## **IMPLEMENTATION:**

### **Launch Fleet-Wide Scraping:**
```bash
bash scripts/fleet-parallel-scraper.sh
```

This will:
1. Distribute 60 topics across 8 machines
2. Each machine runs 7-8 scrapers
3. Uses multi-provider fallback (no rate limits!)
4. Stores papers locally on NAS
5. Completes in 4-8 hours
6. Generates 12,000+ examples

### **Current Training:**
```bash
# Already running - let it continue
tail -f /mnt/nas/web-scrape/logs/training.log
```

---

## **EXPECTED RESULTS:**

### **After 12-24 Hours:**
```
✅ Model trained:     100M Mamba (on 2,594 examples)
✅ Data collected:    12,000+ new examples
✅ Books processed:   849 PDFs (1,698 examples)
───────────────────────────────────────────────────
TOTAL DATA:          16,000+ training examples!

Next: Train 1B model on FULL dataset
```

---

## **WHY THIS IS OPTIMAL:**

### **1. Training Parallelism Limited:**
- Can't easily split ONE model across machines
- PyTorch distributed training is complex
- Better: Train MULTIPLE models sequentially

### **2. Scraping Parallelism UNLIMITED:**
- I/O bound (waiting for APIs)
- No shared state
- Perfect for massive parallelism
- 60 scrapers = 60× faster!

### **3. Resource Efficiency:**
```
Before:
├─ aio-01:  20% utilized
└─ Fleet:   1% utilized (IDLE!)

After:
├─ aio-01:  100% utilized
└─ Fleet:   80% utilized (scraping!)
```

---

## **LAUNCH COMMAND:**

```bash
# CURRENT: Keep training running
# (Already optimal - uses all 8 cores)

# NEW: Launch fleet-wide scraping
bash scripts/fleet-parallel-scraper.sh

# Result: 
# - Training continues on aio-01 (100% CPU)
# - Scraping happens on ALL machines (60 parallel)
# - 60× faster data collection!
```

**Want me to launch it?** 🚀
