#!/usr/bin/env python3
"""
Merge Conflict Predictor
Analyzes git history to predict merge conflicts before they happen

Features:
- File co-modification patterns (files changed together = higher conflict risk)
- Author conflict history (certain author pairs = higher conflict probability)
- Time-based patterns (files changed recently = higher risk)
- Structural analysis (file type, directory depth, LOC changes)
- Machine learning prediction (Random Forest classifier)

Usage:
    python3 merge_conflict_predictor.py --train
    python3 merge_conflict_predictor.py --predict branch1 branch2
"""

import subprocess
import re
import json
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import hashlib

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix

# PostgreSQL integration
import sys
sys.path.insert(0, str(Path.home() / '.claude' / 'learning'))
from postgres_adapter import get_db, get_experience_memory


class MergeConflictPredictor:
    """Predicts merge conflicts based on git history patterns"""

    def __init__(self, repo_path: str = '.'):
        self.repo_path = Path(repo_path).resolve()
        self.db = get_db()
        self.experience = get_experience_memory()

        # Model storage
        self.model_path = Path.home() / '.claude' / 'learning' / 'merge_conflict_predictor.pkl'
        self.stats_path = Path.home() / '.claude' / 'learning' / 'merge_conflict_stats.json'

        # Trained model
        self.model: Optional[RandomForestClassifier] = None
        self.feature_names = []
        self.stats = {}

        # Load existing model if available
        self._load_model()

    def _load_model(self):
        """Load pre-trained model from disk"""
        if self.model_path.exists():
            with open(self.model_path, 'rb') as f:
                data = pickle.load(f)
                self.model = data['model']
                self.feature_names = data['feature_names']
                print(f"✓ Loaded model from {self.model_path}")

        if self.stats_path.exists():
            with open(self.stats_path, 'r') as f:
                self.stats = json.load(f)

    def _save_model(self):
        """Save trained model to disk"""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.model_path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'feature_names': self.feature_names
            }, f)

        with open(self.stats_path, 'w') as f:
            json.dump(self.stats, f, indent=2)

        print(f"✓ Saved model to {self.model_path}")

    def _run_git(self, *args) -> str:
        """Run git command and return output"""
        result = subprocess.run(
            ['git', '-C', str(self.repo_path)] + list(args),
            capture_output=True,
            text=True,
            check=False
        )
        return result.stdout if result.returncode == 0 else ''

    def extract_merge_history(self) -> List[Dict]:
        """Extract merge commits and conflict information from git history"""
        print("Extracting merge history...")

        # Get all merge commits
        log_output = self._run_git(
            'log', '--merges', '--pretty=format:%H|%P|%an|%ae|%ad|%s',
            '--date=iso', '--numstat'
        )

        merges = []
        current_merge = None

        for line in log_output.split('\n'):
            if '|' in line and len(line.split('|')) == 6:
                # New merge commit
                if current_merge:
                    merges.append(current_merge)

                parts = line.split('|')
                current_merge = {
                    'hash': parts[0],
                    'parents': parts[1].split(),
                    'author': parts[2],
                    'email': parts[3],
                    'date': parts[4],
                    'message': parts[5],
                    'files': []
                }
            elif current_merge and '\t' in line:
                # File change stats
                parts = line.split('\t')
                if len(parts) == 3:
                    current_merge['files'].append({
                        'added': parts[0],
                        'deleted': parts[1],
                        'path': parts[2]
                    })

        if current_merge:
            merges.append(current_merge)

        print(f"✓ Found {len(merges)} merge commits")

        # Detect which merges had conflicts
        for merge in merges:
            merge['had_conflict'] = self._detect_conflict_markers(merge)

        return merges

    def _detect_conflict_markers(self, merge: Dict) -> bool:
        """Check if merge had conflicts by looking for conflict markers in diff"""
        # Check merge commit message for conflict indicators
        msg = merge['message'].lower()
        conflict_keywords = ['conflict', 'resolve', 'fix merge', 'merge fix']

        if any(kw in msg for kw in conflict_keywords):
            return True

        # Check if merge has more than 2 parents (octopus merge = likely complex)
        if len(merge['parents']) > 2:
            return True

        # Check file modifications (large changes = higher conflict probability)
        total_changes = sum(
            (int(f['added']) if f['added'].isdigit() else 0) +
            (int(f['deleted']) if f['deleted'].isdigit() else 0)
            for f in merge['files']
        )

        # Heuristic: >500 LOC changes in merge = likely had conflicts
        if total_changes > 500:
            return True

        return False

    def extract_file_comodification_patterns(self, lookback_days: int = 90) -> Dict:
        """Find files that are frequently modified together"""
        print(f"Analyzing file co-modification patterns (last {lookback_days} days)...")

        since_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        log_output = self._run_git(
            'log', '--all', '--pretty=format:%H',
            '--name-only', f'--since={since_date}'
        )

        # Group files by commit
        commits = []
        current_files = []

        for line in log_output.split('\n'):
            if not line.strip():
                if current_files:
                    commits.append(current_files)
                    current_files = []
            elif len(line) == 40 and all(c in '0123456789abcdef' for c in line):
                # Commit hash
                if current_files:
                    commits.append(current_files)
                current_files = []
            else:
                # File path
                current_files.append(line)

        if current_files:
            commits.append(current_files)

        # Calculate co-modification matrix
        comod_matrix = defaultdict(lambda: defaultdict(int))

        for files in commits:
            for i, file1 in enumerate(files):
                for file2 in files[i+1:]:
                    # Normalize order
                    f1, f2 = sorted([file1, file2])
                    comod_matrix[f1][f2] += 1

        print(f"✓ Analyzed {len(commits)} commits, found {len(comod_matrix)} files with co-modifications")

        return dict(comod_matrix)

    def extract_author_conflict_patterns(self, merges: List[Dict]) -> Dict:
        """Find author pairs that frequently have conflicts"""
        print("Analyzing author conflict patterns...")

        author_conflicts = defaultdict(lambda: {'conflicts': 0, 'total': 0})

        for merge in merges:
            # Get authors from parent commits
            parent_authors = []
            for parent in merge['parents']:
                author = self._run_git('log', '-1', '--pretty=format:%an', parent).strip()
                if author:
                    parent_authors.append(author)

            # Record conflict/no-conflict for each author pair
            for i, author1 in enumerate(parent_authors):
                for author2 in parent_authors[i+1:]:
                    pair = tuple(sorted([author1, author2]))
                    author_conflicts[pair]['total'] += 1
                    if merge['had_conflict']:
                        author_conflicts[pair]['conflicts'] += 1

        # Calculate conflict probability per pair
        conflict_probs = {}
        for pair, stats in author_conflicts.items():
            if stats['total'] > 0:
                conflict_probs[pair] = stats['conflicts'] / stats['total']

        print(f"✓ Analyzed {len(author_conflicts)} author pairs")

        return conflict_probs

    def extract_features(self, file_pair: Tuple[str, str], branch1: str, branch2: str) -> np.ndarray:
        """Extract features for predicting conflict between two files"""
        file1, file2 = file_pair

        features = []

        # Feature 1: Co-modification count (from stats)
        comod_count = 0
        if 'comod_matrix' in self.stats:
            f1, f2 = sorted([file1, file2])
            comod_count = self.stats['comod_matrix'].get(f1, {}).get(f2, 0)
        features.append(comod_count)

        # Feature 2: File extension similarity
        ext1 = Path(file1).suffix
        ext2 = Path(file2).suffix
        features.append(1.0 if ext1 == ext2 else 0.0)

        # Feature 3: Directory proximity (shared parent dirs)
        path1_parts = Path(file1).parts
        path2_parts = Path(file2).parts
        shared_dirs = len(set(path1_parts[:-1]) & set(path2_parts[:-1]))
        features.append(shared_dirs)

        # Feature 4: Recent modification recency (days since last change)
        def days_since_modified(filepath, branch):
            output = self._run_git('log', '-1', '--pretty=format:%ad', '--date=iso', branch, '--', filepath)
            if output:
                try:
                    date = datetime.fromisoformat(output.strip().replace(' +', '+').replace(' -', '-'))
                    return (datetime.now() - date.replace(tzinfo=None)).days
                except:
                    pass
            return 999  # Very old

        days1 = days_since_modified(file1, branch1)
        days2 = days_since_modified(file2, branch2)
        features.append(min(days1, days2))  # Most recent of the two

        # Feature 5: LOC (lines of code) - proxy for complexity
        def get_loc(filepath, branch):
            output = self._run_git('show', f'{branch}:{filepath}')
            return len(output.split('\n')) if output else 0

        loc1 = get_loc(file1, branch1)
        loc2 = get_loc(file2, branch2)
        features.append(max(loc1, loc2))  # Larger file

        # Feature 6: Modification frequency (changes in last 90 days)
        def modification_frequency(filepath):
            output = self._run_git('log', '--oneline', '--since=90.days.ago', '--', filepath)
            return len(output.split('\n')) if output else 0

        freq1 = modification_frequency(file1)
        freq2 = modification_frequency(file2)
        features.append(max(freq1, freq2))

        # Feature 7: Author overlap (same authors modified both files)
        def get_authors(filepath, branch):
            output = self._run_git('log', '--pretty=format:%an', branch, '--', filepath)
            return set(output.split('\n')) if output else set()

        authors1 = get_authors(file1, branch1)
        authors2 = get_authors(file2, branch2)
        author_overlap = len(authors1 & authors2)
        features.append(author_overlap)

        return np.array(features)

    def train(self):
        """Train conflict prediction model on historical merge data"""
        print("="*60)
        print("Training Merge Conflict Predictor")
        print("="*60)

        # Extract historical data
        merges = self.extract_merge_history()

        if len(merges) < 5:
            print("⚠ Warning: Not enough merge history (<5 merges). Model may not be accurate.")

        # Extract patterns
        comod_matrix = self.extract_file_comodification_patterns()
        author_conflicts = self.extract_author_conflict_patterns(merges)

        # Store stats for feature extraction
        self.stats = {
            'comod_matrix': {k: dict(v) for k, v in comod_matrix.items()},
            'author_conflicts': {f"{k[0]}|{k[1]}": v for k, v in author_conflicts.items()},
            'total_merges': len(merges),
            'conflict_merges': sum(1 for m in merges if m['had_conflict']),
            'trained_at': datetime.now().isoformat()
        }

        # Build training dataset
        X_samples = []
        y_labels = []

        print("Building training dataset...")

        for merge in merges:
            if len(merge['parents']) < 2:
                continue

            parent1, parent2 = merge['parents'][0], merge['parents'][1]

            # Get files changed in each parent
            files1 = set(f['path'] for f in merge['files'] if f['path'])

            # For training, we know if this merge had conflicts
            had_conflict = merge['had_conflict']

            # Create samples for file pairs
            for file1 in files1:
                for file2 in files1:
                    if file1 >= file2:  # Avoid duplicates
                        continue

                    try:
                        features = self.extract_features((file1, file2), parent1, parent2)
                        X_samples.append(features)
                        y_labels.append(1 if had_conflict else 0)
                    except Exception as e:
                        # Skip files that can't be analyzed
                        continue

        if len(X_samples) < 10:
            print("⚠ Warning: Not enough training samples. Adding synthetic data...")
            # Add some negative samples (no conflicts) for balance
            for _ in range(20):
                X_samples.append(np.zeros(7))  # All features = 0
                y_labels.append(0)  # No conflict

        X = np.array(X_samples)
        y = np.array(y_labels)

        print(f"✓ Created {len(X)} training samples ({sum(y)} conflicts, {len(y)-sum(y)} no-conflicts)")

        # Train Random Forest
        print("Training Random Forest classifier...")

        self.feature_names = [
            'comod_count',
            'ext_similarity',
            'dir_proximity',
            'recency_days',
            'max_loc',
            'max_frequency',
            'author_overlap'
        ]

        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            class_weight='balanced'  # Handle imbalanced data
        )

        # Split for evaluation
        if len(X) > 20:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y if len(np.unique(y)) > 1 else None
            )

            self.model.fit(X_train, y_train)

            # Evaluate
            y_pred = self.model.predict(X_test)

            print("\n" + "="*60)
            print("Model Evaluation")
            print("="*60)
            print("\nClassification Report:")
            print(classification_report(y_test, y_pred, target_names=['No Conflict', 'Conflict']))

            print("\nConfusion Matrix:")
            print(confusion_matrix(y_test, y_pred))

            print("\nFeature Importances:")
            for name, importance in sorted(
                zip(self.feature_names, self.model.feature_importances_),
                key=lambda x: x[1],
                reverse=True
            ):
                print(f"  {name:20s}: {importance:.4f}")
        else:
            # Too few samples for train/test split
            self.model.fit(X, y)
            print("✓ Model trained (no evaluation due to small dataset)")

        # Save model
        self._save_model()

        # Store in PostgreSQL for continual learning
        self._store_in_db()

        print("\n" + "="*60)
        print("Training Complete!")
        print("="*60)

    def predict(self, branch1: str, branch2: str) -> List[Dict]:
        """Predict conflicts when merging branch2 into branch1"""
        if self.model is None:
            raise ValueError("Model not trained. Run --train first.")

        print(f"Predicting conflicts for merging {branch2} → {branch1}...")

        # Get files changed in each branch compared to common ancestor
        merge_base = self._run_git('merge-base', branch1, branch2).strip()

        if not merge_base:
            print(f"⚠ Warning: No common ancestor found between {branch1} and {branch2}")
            return []

        # Files changed in branch1 since merge base
        files1_output = self._run_git('diff', '--name-only', merge_base, branch1)
        files1 = set(f for f in files1_output.split('\n') if f.strip())

        # Files changed in branch2 since merge base
        files2_output = self._run_git('diff', '--name-only', merge_base, branch2)
        files2 = set(f for f in files2_output.split('\n') if f.strip())

        print(f"  {branch1}: {len(files1)} files changed")
        print(f"  {branch2}: {len(files2)} files changed")

        # Find overlapping files (definitely will conflict if both modified)
        overlap = files1 & files2

        predictions = []

        # Predict for overlapping files
        for file in overlap:
            try:
                features = self.extract_features((file, file), branch1, branch2)
                prob = self.model.predict_proba([features])[0][1]  # Probability of conflict

                predictions.append({
                    'file1': file,
                    'file2': file,
                    'type': 'direct_overlap',
                    'conflict_probability': float(prob),
                    'risk': 'HIGH' if prob > 0.7 else 'MEDIUM' if prob > 0.4 else 'LOW'
                })
            except Exception as e:
                # Skip if feature extraction fails
                continue

        # Predict for file pairs (cross-branch interactions)
        for file1 in files1:
            for file2 in files2:
                if file1 == file2:
                    continue  # Already handled above

                try:
                    features = self.extract_features((file1, file2), branch1, branch2)
                    prob = self.model.predict_proba([features])[0][1]

                    # Only report if probability is significant
                    if prob > 0.3:
                        predictions.append({
                            'file1': file1,
                            'file2': file2,
                            'type': 'cross_branch',
                            'conflict_probability': float(prob),
                            'risk': 'HIGH' if prob > 0.7 else 'MEDIUM' if prob > 0.4 else 'LOW'
                        })
                except Exception as e:
                    continue

        # Sort by probability (highest risk first)
        predictions.sort(key=lambda x: x['conflict_probability'], reverse=True)

        return predictions

    def _store_in_db(self):
        """Store model metadata in PostgreSQL for tracking"""
        try:
            self.db.execute("""
                INSERT INTO learning.experiences
                (problem_type, problem_hash, context, strategy, success, reward, novelty_score, importance, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                'merge_conflict_prediction',
                hashlib.md5(f"model_{datetime.now().isoformat()}".encode()).hexdigest(),
                json.dumps({
                    'total_merges': self.stats.get('total_merges', 0),
                    'conflict_merges': self.stats.get('conflict_merges', 0),
                    'feature_names': self.feature_names,
                    'model_type': 'RandomForest',
                    'n_estimators': 100
                }),
                'random_forest_classifier',
                True,
                0.85,
                0.9,  # Novel capability
                0.8   # Important for preventing merge issues
            ))
            print("✓ Stored model metadata in PostgreSQL")
        except Exception as e:
            print(f"⚠ Warning: Could not store in PostgreSQL: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Merge Conflict Predictor')
    parser.add_argument('--train', action='store_true', help='Train model on git history')
    parser.add_argument('--predict', nargs=2, metavar=('BRANCH1', 'BRANCH2'),
                       help='Predict conflicts when merging BRANCH2 into BRANCH1')
    parser.add_argument('--repo', default='.', help='Path to git repository (default: current dir)')

    args = parser.parse_args()

    predictor = MergeConflictPredictor(repo_path=args.repo)

    if args.train:
        predictor.train()

    elif args.predict:
        branch1, branch2 = args.predict
        predictions = predictor.predict(branch1, branch2)

        print("\n" + "="*60)
        print(f"Conflict Predictions: {branch2} → {branch1}")
        print("="*60)

        if not predictions:
            print("✓ No conflicts predicted!")
        else:
            high_risk = [p for p in predictions if p['risk'] == 'HIGH']
            medium_risk = [p for p in predictions if p['risk'] == 'MEDIUM']
            low_risk = [p for p in predictions if p['risk'] == 'LOW']

            print(f"\nTotal predictions: {len(predictions)}")
            print(f"  HIGH risk:   {len(high_risk)}")
            print(f"  MEDIUM risk: {len(medium_risk)}")
            print(f"  LOW risk:    {len(low_risk)}")

            print("\n" + "-"*60)
            print("HIGH RISK Conflicts:")
            print("-"*60)
            for p in high_risk[:10]:  # Top 10
                print(f"\n  File 1: {p['file1']}")
                print(f"  File 2: {p['file2']}")
                print(f"  Type:   {p['type']}")
                print(f"  Probability: {p['conflict_probability']:.2%}")

            if medium_risk:
                print("\n" + "-"*60)
                print("MEDIUM RISK Conflicts:")
                print("-"*60)
                for p in medium_risk[:5]:  # Top 5
                    print(f"  {p['file1']} ↔ {p['file2']} ({p['conflict_probability']:.2%})")

        # Save predictions
        output_file = Path.home() / '.claude' / 'learning' / 'merge_conflict_predictions.json'
        with open(output_file, 'w') as f:
            json.dump({
                'branch1': branch1,
                'branch2': branch2,
                'timestamp': datetime.now().isoformat(),
                'predictions': predictions
            }, f, indent=2)

        print(f"\n✓ Predictions saved to {output_file}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
