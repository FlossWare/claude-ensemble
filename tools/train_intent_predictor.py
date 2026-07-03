#!/usr/bin/env python3
"""
User Intent Predictor Training Script

Trains a multi-label intent classifier from Claude conversation history.
Uses sklearn with TF-IDF vectorization and multi-label classification.

Intent Categories:
- code_generation: Write/create code
- code_review: Review/analyze existing code
- research: Deep research, PDF analysis
- system_ops: DevOps, infrastructure, configuration
- debugging: Fix bugs, troubleshoot issues
- data_analysis: Analyze data, generate insights
- documentation: Write docs, explain concepts
- workflow_automation: Create workflows, orchestration
- learning: Train models, ML tasks
"""

import json
import glob
import os
import re
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
import joblib
import numpy as np
import scipy.special

# ML imports
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, hamming_loss, accuracy_score
from sklearn.preprocessing import MultiLabelBinarizer


# Intent detection patterns
INTENT_PATTERNS = {
    'code_generation': [
        r'\b(write|create|generate|implement|build|add)\b.*\b(code|function|class|script|program|module)\b',
        r'\b(scaffold|boilerplate|template)\b',
        r'\bmake\s+(?:a|an|the)?\s*(?:new)?\s*(?:function|class|script)\b',
    ],
    'code_review': [
        r'\b(review|analyze|check|inspect|audit|examine)\b.*\b(code|implementation|changes|diff)\b',
        r'\b(lint|validate|verify)\b',
        r'\bcode\s+quality\b',
        r'\b(refactor|improve|optimize)\s+(?:the|this)?\s*code\b',
    ],
    'research': [
        r'\b(research|investigate|explore|study|learn about)\b',
        r'\b(pdf|paper|article|documentation)\b.*\b(analyze|summarize|extract)\b',
        r'\bdeep[- ]research\b',
        r'\bwhat\s+(?:is|are)\b.*\?',
        r'\b(explain|describe|tell me about)\b',
    ],
    'system_ops': [
        r'\b(deploy|install|configure|setup|provision)\b',
        r'\b(docker|kubernetes|k8s|terraform|ansible)\b',
        r'\b(server|infrastructure|fleet|cluster|node)\b',
        r'\b(backup|restore|migrate)\b',
        r'\b(ssh|scp|rsync)\b',
    ],
    'debugging': [
        r'\b(debug|fix|troubleshoot|diagnose|solve)\b',
        r'\b(error|bug|issue|problem|broken|failing)\b',
        r'\b(why\s+(?:is|does|did|doesn\'t|isn\'t|won\'t))\b',
        r'\bnot\s+working\b',
        r'\b(stack trace|exception|crash)\b',
    ],
    'data_analysis': [
        r'\b(analyze|process|parse|extract|aggregate)\b.*\b(data|dataset|logs|metrics)\b',
        r'\b(statistics|metrics|trends|patterns)\b',
        r'\b(dashboard|visualization|chart|graph|plot)\b',
        r'\b(sql|query|database|postgres|postgresql)\b',
    ],
    'documentation': [
        r'\b(document|write|create)\b.*\b(readme|docs|documentation|guide)\b',
        r'\b(explain|describe)\s+(?:how|what|why)\b',
        r'\b(tutorial|walkthrough|instructions)\b',
    ],
    'workflow_automation': [
        r'\b(workflow|pipeline|orchestration|automation)\b',
        r'\b(cron|schedule|periodic|recurring)\b',
        r'\b(parallel|distributed|fleet)\b.*\b(execution|processing|task)\b',
        r'\b(worker|agent|executor)\b',
    ],
    'learning': [
        r'\b(train|fine-?tune|learn)\b.*\b(model|network|classifier|predictor)\b',
        r'\b(machine learning|ml|ai|neural network)\b',
        r'\b(dataset|training data|embeddings)\b',
        r'\b(sklearn|pytorch|tensorflow|transformers)\b',
    ],
}


def extract_user_messages(conversation_dir: str) -> list[dict]:
    """Extract user messages from conversation JSONL files."""
    messages = []

    # Search all project subdirectories
    jsonl_files = glob.glob(f"{conversation_dir}/*.jsonl")
    jsonl_files += glob.glob(f"{conversation_dir}/*/*.jsonl")
    print(f"Found {len(jsonl_files)} conversation files")

    for filepath in jsonl_files:
        session_id = Path(filepath).stem

        with open(filepath, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)

                    # Extract user messages
                    if data.get('type') == 'user':
                        message_content = data.get('message', {})

                        # Handle different message formats
                        text = None
                        if isinstance(message_content, dict):
                            content = message_content.get('content', [])
                            if isinstance(content, list):
                                # Extract text from content blocks
                                text_blocks = [
                                    block.get('text', '')
                                    for block in content
                                    if isinstance(block, dict) and block.get('type') == 'text'
                                ]
                                text = ' '.join(text_blocks).strip()
                            elif isinstance(content, str):
                                text = content.strip()
                        elif isinstance(message_content, str):
                            text = message_content.strip()

                        if text and len(text) > 10:  # Skip very short messages
                            messages.append({
                                'text': text,
                                'timestamp': data.get('timestamp'),
                                'session_id': session_id,
                                'cwd': data.get('cwd', ''),
                            })

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    # Skip malformed entries
                    continue

    print(f"Extracted {len(messages)} user messages")
    return messages


def detect_intents(text: str) -> list[str]:
    """Detect intents in text using regex patterns."""
    text_lower = text.lower()
    detected = set()

    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                detected.add(intent)
                break  # One match per intent is enough

    return list(detected) if detected else ['other']


def prepare_training_data(messages: list[dict]) -> tuple:
    """Prepare training data with intent labels."""
    texts = []
    labels = []

    for msg in messages:
        text = msg['text']
        intents = detect_intents(text)

        texts.append(text)
        labels.append(intents)

    return texts, labels


def train_intent_predictor(texts: list[str], labels: list[list[str]]) -> dict:
    """Train multi-label intent classifier."""

    # Binarize labels
    mlb = MultiLabelBinarizer()
    y = mlb.fit_transform(labels)

    print(f"\nIntent distribution:")
    intent_counts = Counter()
    for label_set in labels:
        intent_counts.update(label_set)
    for intent, count in intent_counts.most_common():
        print(f"  {intent}: {count}")

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        texts, y, test_size=0.2, random_state=42
    )

    # TF-IDF vectorization
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 3),
        min_df=2,
        max_df=0.8,
        strip_accents='unicode',
        lowercase=True,
    )

    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    # Train multi-label classifier with class weight balancing
    print(f"\nTraining on {len(X_train)} samples...")
    classifier = OneVsRestClassifier(
        LogisticRegression(
            max_iter=1000,
            random_state=42,
            C=1.0,
            class_weight='balanced'  # Handle class imbalance
        )
    )
    classifier.fit(X_train_vec, y_train)

    # Evaluate
    y_pred = classifier.predict(X_test_vec)

    print(f"\nEvaluation Results:")
    print(f"Hamming Loss: {hamming_loss(y_test, y_pred):.4f}")
    print(f"Exact Match Accuracy: {accuracy_score(y_test, y_pred):.4f}")

    print(f"\nPer-Intent Classification Report:")
    print(classification_report(
        y_test, y_pred,
        target_names=mlb.classes_,
        zero_division=0
    ))

    return {
        'vectorizer': vectorizer,
        'classifier': classifier,
        'label_binarizer': mlb,
        'intent_classes': list(mlb.classes_),
        'training_samples': len(texts),
        'training_date': datetime.now().isoformat(),
    }


def predict_intent(model: dict, text: str, threshold: float = 0.3) -> list[tuple[str, float]]:
    """Predict intents for new text with confidence scores."""
    vectorizer = model['vectorizer']
    classifier = model['classifier']
    mlb = model['label_binarizer']

    # Vectorize
    X = vectorizer.transform([text])

    # Get decision scores for all classifiers
    decision_scores = []
    for estimator in classifier.estimators_:
        scores = estimator.decision_function(X)
        decision_scores.append(scores[0] if hasattr(scores, '__iter__') else scores)

    # Apply sigmoid to convert to probabilities
    import scipy.special
    probas = scipy.special.expit(decision_scores)

    # Get intents above threshold
    intents = []
    for idx, proba in enumerate(probas):
        if proba >= threshold:
            intent = mlb.classes_[idx]
            # Exclude 'other' unless it's the only high-confidence prediction
            if intent != 'other' or len(intents) == 0:
                intents.append((intent, float(proba)))

    # Sort by confidence
    intents.sort(key=lambda x: x[1], reverse=True)

    # If only 'other' is found, check if there are any predictions above a lower threshold
    if len(intents) == 1 and intents[0][0] == 'other':
        lower_threshold = threshold * 0.5
        for idx, proba in enumerate(probas):
            if proba >= lower_threshold and mlb.classes_[idx] != 'other':
                intents.insert(0, (mlb.classes_[idx], float(proba)))

    return intents if intents else [('other', 1.0)]


def save_model(model: dict, output_path: str):
    """Save trained model to disk."""
    joblib.dump(model, output_path)
    print(f"\nModel saved to: {output_path}")

    # Save human-readable stats
    stats_path = output_path.replace('.pkl', '_stats.json')
    stats = {
        'intent_classes': model['intent_classes'],
        'training_samples': model['training_samples'],
        'training_date': model['training_date'],
        'model_type': 'TF-IDF + OneVsRest LogisticRegression',
        'features': model['vectorizer'].get_feature_names_out().shape[0],
    }
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"Stats saved to: {stats_path}")


def main():
    """Main training pipeline."""
    # Paths
    conversation_dir = os.path.expanduser('~/.claude/projects')
    output_path = os.path.expanduser('~/.claude/learning/intent_predictor.pkl')

    print("User Intent Predictor Training")
    print("=" * 50)

    # Extract messages
    messages = extract_user_messages(conversation_dir)

    if len(messages) < 10:
        print("Not enough training data. Need at least 10 messages.")
        return

    # Prepare data
    texts, labels = prepare_training_data(messages)

    # Train model
    model = train_intent_predictor(texts, labels)

    # Save model
    save_model(model, output_path)

    # Test predictions
    print("\n" + "=" * 50)
    print("Sample Predictions:")
    print("=" * 50)

    test_cases = [
        "Write a Python script to parse JSON logs",
        "Debug this code that's throwing an error",
        "Research the latest Kubernetes best practices",
        "Deploy the application to production",
        "Train a classifier on this dataset",
        "Create a workflow to process files in parallel",
    ]

    for text in test_cases:
        intents = predict_intent(model, text)
        print(f"\nInput: {text}")
        print(f"Predicted intents: {intents}")


if __name__ == '__main__':
    main()
