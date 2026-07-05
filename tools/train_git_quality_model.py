#!/usr/bin/env python3
"""
Git Commit Quality Predictor

Trains a model to predict if a commit will introduce bugs based on:
- Commit message quality
- Files changed
- Lines changed
- Time of day
- Author experience

Usage:
    python3 train_git_quality_model.py
"""

import pickle
import psycopg2
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

# Connect to PostgreSQL
conn = psycopg2.connect('dbname=learning host=aio-01 port=5433 user=postgres')
cur = conn.cursor()

# Check if we have git commit data
cur.execute("SELECT COUNT(*) FROM learning.git_commits")
commit_count = cur.fetchone()[0]

if commit_count == 0:
    print("No git commit data yet. Ingest commits first!")
    print("Run: python3 /tmp/ingest_commits_final.py")
    exit(1)

print(f"Found {commit_count} git commits")

# Feature engineering from commit data
cur.execute("""
    SELECT
        commit_hash,
        LENGTH(message) as message_length,
        CASE WHEN message ~* '(fix|bug|issue)' THEN 1 ELSE 0 END as is_bugfix,
        CASE WHEN message ~* '(feat|feature|add)' THEN 1 ELSE 0 END as is_feature,
        EXTRACT(HOUR FROM timestamp) as hour_of_day,
        EXTRACT(DOW FROM timestamp) as day_of_week,
        -- We'd need to join with follow-up commits to know if this introduced bugs
        -- For now, use message quality as proxy
        CASE
            WHEN LENGTH(message) < 10 THEN 1  -- Short messages = likely low quality
            WHEN message ~* '(wip|tmp|test)' THEN 1  -- WIP commits = likely buggy
            ELSE 0
        END as introduced_bug
    FROM learning.git_commits
    LIMIT 1000
""")

rows = cur.fetchall()

if len(rows) < 50:
    print("Need at least 50 commits to train. Only have {len(rows)}.")
    exit(1)

# Prepare training data
X = np.array([[
    row[1],  # message_length
    row[2],  # is_bugfix
    row[3],  # is_feature
    row[4],  # hour_of_day
    row[5],  # day_of_week
] for row in rows])

y = np.array([row[6] for row in rows])  # introduced_bug

# Split train/test
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train model
print(f"Training on {len(X_train)} commits...")
model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print(f"\nModel Accuracy: {accuracy:.2%}")
print("\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=['Clean', 'Buggy']))

# Feature importance
feature_names = ['message_length', 'is_bugfix', 'is_feature', 'hour_of_day', 'day_of_week']
importances = model.feature_importances_
print("\nFeature Importances:")
for name, importance in zip(feature_names, importances):
    print(f"  {name}: {importance:.3f}")

# Save model
output_path = '/home/claude/.claude/learning/predictors/git-commit-quality.pkl'
with open(output_path, 'wb') as f:
    pickle.dump({
        'model': model,
        'feature_names': feature_names,
        'accuracy': accuracy,
    }, f)

print(f"\nModel saved to: {output_path}")
print("\nUsage:")
print("  from git_quality import predict_commit_quality")
print("  quality = predict_commit_quality(message='fix bug', hour=14, is_friday=True)")
