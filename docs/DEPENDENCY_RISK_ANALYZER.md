# Dependency Risk Analyzer

## Overview

Machine learning model that predicts risk levels for package dependencies across npm, PyPI, and Maven ecosystems.

**Algorithm:** Random Forest Classifier (200 trees, max depth 15)  
**Risk Categories:** LOW, MEDIUM, HIGH, CRITICAL  
**Features:** 25 features across security, maintenance, popularity, and ecosystem metrics  
**Accuracy:** 94.5% on test set (F1-macro: 0.745)

## Quick Start

### Train the Model

```bash
python3 tools/dependency_risk_analyzer_trainer.py
```

Output:
- Model: `learning/dependency_risk_analyzer.pkl` (1.2MB)
- Stats: `learning/dependency_risk_analyzer_stats.json`

### Predict Risk for Dependencies

**Scan package.json:**
```bash
python3 tools/predict_dependency_risk.py --scan package.json
```

**Single dependency (with defaults):**
```bash
python3 tools/predict_dependency_risk.py --name lodash --ecosystem npm
```

**From JSON file:**
```bash
python3 tools/predict_dependency_risk.py --json dependency.json --verbose
```

## Feature Set (25 Features)

### Security Indicators (5 features)
- `known_vulnerabilities` - Number of known security issues
- `cve_count` - CVE entries for this package
- `has_security_policy` - Binary flag for security.md presence

### Maintenance Metrics (5 features)
- `commits_last_year` - Commit activity (proxy for active development)
- `version_age_days` - Days since last version release
- `open_issues` - Current open issues count
- `open_prs` - Current open pull requests
- `closed_issues_last_month` - Issue resolution activity

### Popularity & Ecosystem Health (5 features)
- `log_downloads` - Log-transformed monthly downloads
- `log_stars` - Log-transformed GitHub stars
- `log_dependents` - Log-transformed dependent packages count
- `log_reverse_deps` - Log-transformed reverse dependencies
- `num_dependents` - Direct count of packages depending on this

### Version & Compatibility (4 features)
- `is_major_version_behind` - Binary flag: major version outdated
- `is_minor_version_behind` - Binary flag: minor version outdated
- `breaking_changes_in_latest` - Breaking changes count in latest version
- `version_age_days` - Age metric (also in maintenance)

### License Compatibility (2 features)
- `is_permissive_license` - MIT, Apache, BSD, ISC
- `is_copyleft_license` - GPL, AGPL, LGPL

### Dependency Depth (2 features)
- `transitive_depth` - Levels deep in dependency tree
- `total_transitive_deps` - Total transitive dependency count

### Package Type (2 features)
- `is_dev_dependency` - Development vs production dependency
- `is_optional` - Optional dependency flag
- `is_core_dependency` - Critical infrastructure flag

### Ecosystem (3 features)
- `is_npm` - JavaScript/Node ecosystem
- `is_pypi` - Python ecosystem
- `is_maven` - Java/Maven ecosystem

## Model Performance

### Training Results

```
Classifier:        RandomForest
Train Accuracy:    99.88%
Test Accuracy:     94.50%
Test F1 (macro):   0.745
Test F1 (weighted):0.940
CV F1 (5-fold):    0.667 ± 0.071
```

### Classification Report (Test Set)

```
              precision    recall  f1-score   support

    CRITICAL      0.957     0.985     0.971        68
        HIGH      0.588     0.714     0.645        14
         LOW      1.000     1.000     1.000       110
      MEDIUM      0.667     0.250     0.364         8

    accuracy                          0.945       200
```

### Confusion Matrix

```
              CRITICAL      HIGH       LOW    MEDIUM
CRITICAL            67         1         0         0
HIGH                 3        10         0         1
LOW                  0         0       110         0
MEDIUM               0         6         0         2
```

**Key Observations:**
- Perfect classification of LOW risk (100% precision/recall)
- Strong CRITICAL detection (95.7% precision, 98.5% recall)
- MEDIUM class harder to distinguish (only 8 test samples)
- HIGH has some confusion with CRITICAL (expected, adjacent categories)

## Top Features by Importance

```
1. commits_last_year              17.50%
2. version_age_days               15.89%
3. known_vulnerabilities          15.87%
4. log_downloads                  10.75%
5. closed_issues_last_month        7.97%
6. log_dependents                  5.51%
7. open_issues                     5.43%
8. log_reverse_deps                5.05%
9. total_transitive_deps           3.16%
10. cve_count                      2.93%
```

**Interpretation:**
- **Maintenance activity** (commits, closed issues) = strongest signal
- **Security vulnerabilities** = critical risk factor
- **Popularity metrics** (downloads, dependents) = proxy for ecosystem health
- **Age** = important but not decisive (some old packages are stable)

## Risk Level Definitions

### LOW (55% of training data)
- ✅ Active maintenance (100+ commits/year)
- ✅ Recent version (<90 days old)
- ✅ No known vulnerabilities
- ✅ Security policy present
- ✅ High popularity (500k+ downloads/month)
- ✅ Up-to-date with latest versions
- ✅ Permissive license

**Example:** `lodash` (50M downloads/month, 50k stars, actively maintained)

### MEDIUM (4% of training data)
- ⚠ Moderate maintenance (30-100 commits/year)
- ⚠ Somewhat outdated (90-365 days)
- ⚠ Minor version behind (1-2 versions)
- ⚠ Low-moderate issue resolution
- ⚠ Possible minor vulnerability (not critical)

**Example:** `moderately-outdated` (100k downloads/month, 1-2 minor versions behind)

### HIGH (7% of training data)
- 🟠 Low maintenance (5-30 commits/year)
- 🟠 Outdated (1-2 years)
- 🟠 Some known vulnerabilities (1-3)
- 🟠 Major version behind
- 🟠 High open issues, low resolution rate

**Example:** Package with 1-2 year old version, some security issues

### CRITICAL (34% of training data)
- 🔴 Abandoned (0-5 commits/year)
- 🔴 Very outdated (>2 years)
- 🔴 Multiple vulnerabilities (2+)
- 🔴 No security policy
- 🔴 Low popularity (<10k downloads/month)
- 🔴 Multiple major versions behind

**Example:** `old-vulnerable-package` (5 CVEs, 5 years old, 2 commits/year)

## Integration Examples

### JavaScript/Node.js

```javascript
const { execSync } = require('child_process');

// Scan package.json
const result = execSync('python3 tools/predict_dependency_risk.py --scan package.json', {
  encoding: 'utf-8'
});

console.log(result);

// Parse results and fail build on HIGH/CRITICAL
if (result.includes('🔴 CRITICAL') || result.includes('🟠 HIGH')) {
  console.error('High-risk dependencies detected!');
  process.exit(1);
}
```

### Python

```python
import subprocess
import json

# Analyze a dependency
dep_info = {
    'name': 'requests',
    'version_age_days': 45,
    'commits_last_year': 150,
    'known_vulnerabilities': 0,
    'downloads_per_month': 5000000,
    # ... other fields
}

# Save to JSON
with open('/tmp/dep.json', 'w') as f:
    json.dump(dep_info, f)

# Predict
result = subprocess.run(
    ['python3', 'tools/predict_dependency_risk.py', '--json', '/tmp/dep.json'],
    capture_output=True,
    text=True
)

print(result.stdout)
```

### CI/CD Pipeline (GitHub Actions)

```yaml
- name: Analyze Dependency Risks
  run: |
    python3 tools/predict_dependency_risk.py --scan package.json > risk_report.txt
    cat risk_report.txt
    
    # Fail if critical dependencies found
    if grep -q "🔴 CRITICAL" risk_report.txt; then
      echo "::error::Critical risk dependencies detected"
      exit 1
    fi
```

## Training Data Distribution

**Synthetic Dataset (1000 samples):**
- CRITICAL: 20% (200 samples) - Abandoned, vulnerable packages
- HIGH: 25% (250 samples) - Outdated, some vulnerabilities
- MEDIUM: 30% (300 samples) - Somewhat outdated, minor issues
- LOW: 25% (250 samples) - Actively maintained, secure

**Split:**
- Training: 800 samples (80%)
- Test: 200 samples (20%)
- Stratified split to maintain class balance

## Future Enhancements

### 1. Real-Time Registry Integration
- Fetch live data from npm registry, PyPI, Maven Central
- Use GitHub API for stars, commits, issues
- Check vulnerability databases (Snyk, OSV, GitHub Advisory)

### 2. Retrain on Real Audit Data
- Replace synthetic data with actual dependency audit results
- Use `npm audit`, `pip-audit`, OWASP Dependency-Check output
- Incorporate historical vulnerability disclosures

### 3. Expanded Feature Set
- Contributor diversity (bus factor)
- Time-to-fix vulnerabilities (mean response time)
- Semantic versioning compliance
- Test coverage metrics
- Documentation quality

### 4. Multi-Model Ensemble
- Combine Random Forest with XGBoost, LightGBM
- Use stacking or voting ensemble
- Separate models for each ecosystem

### 5. Risk Score Explanation
- SHAP values for feature importance per prediction
- Generate human-readable risk reports
- Suggest remediation actions

## Usage Patterns

### Development Workflow
1. **Pre-commit:** Scan `package.json` changes
2. **CI/CD:** Automated risk analysis on every PR
3. **Scheduled:** Weekly dependency audit
4. **Alerts:** Notify on new CRITICAL risks

### Recommended Thresholds
- **Block merge:** CRITICAL risk dependencies
- **Require review:** HIGH risk dependencies
- **Monitor:** MEDIUM risk (upgrade within 30 days)
- **Accept:** LOW risk

## Files

```
tools/
├── dependency_risk_analyzer_trainer.py    # Training script (19KB)
└── predict_dependency_risk.py             # Prediction script (6KB)

learning/
├── dependency_risk_analyzer.pkl           # Trained model (1.2MB)
└── dependency_risk_analyzer_stats.json    # Training metrics (2.4KB)

docs/
└── DEPENDENCY_RISK_ANALYZER.md            # This file
```

## Dependencies

**Required:**
- `scikit-learn` - Random Forest classifier
- `numpy` - Numerical operations
- `pickle` - Model serialization

**Optional:**
- `xgboost` - Alternative classifier (better performance)
- `psycopg2` - Database integration (future)

**Install:**
```bash
pip3 install scikit-learn numpy xgboost
```

## License & Attribution

Part of the claude-global-skills distributed LLM orchestration framework.

**Training Data:** Synthetic (based on npm, PyPI, Maven ecosystem patterns)  
**Model:** Random Forest (scikit-learn)  
**Risk Scoring:** Multi-factor heuristic (security + maintenance + popularity)

**Co-Architect:** Claude Sonnet 4.5 (Anthropic)  
**Date:** 2026-07-03
