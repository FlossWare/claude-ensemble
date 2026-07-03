#!/usr/bin/env python3
"""
AutoML System - Usage Examples and Integration Guide

Demonstrates how to use the AutoML system in various scenarios.
"""

from automl_system import AutoMLSystem
import numpy as np


def example_1_quick_training():
    """Quick training with automatic configuration"""
    print("=" * 60)
    print("Example 1: Quick Training")
    print("=" * 60)

    # Generate sample data
    X = np.random.randn(200, 10)
    y = (X[:, 0] + X[:, 1] > 0).astype(int)

    # Train with all defaults (auto-detect task type, auto feature engineering, auto ensemble)
    automl = AutoMLSystem()
    automl.train(X, y)

    # Make predictions
    predictions = automl.predict(X[:5])
    print(f"\nPredictions: {predictions}")

    # Save for later use
    automl.save()


def example_2_regression():
    """Regression task with custom settings"""
    print("\n" + "=" * 60)
    print("Example 2: Regression Task")
    print("=" * 60)

    # Generate regression data
    X = np.random.randn(300, 8)
    y = 3 * X[:, 0] + 2 * X[:, 1] - X[:, 2] + np.random.randn(300) * 0.5

    # Train regression model
    automl = AutoMLSystem()
    automl.train(
        X, y,
        task_type='regression',
        problem_type='cost_prediction',
        ensemble=True,
        optimize_hp=True
    )

    # Make predictions
    test_X = np.random.randn(10, 8)
    predictions = automl.predict(test_X)
    print(f"\nSample predictions: {predictions[:5]}")

    # Get feature importance
    importance = automl.get_feature_importance(top_n=3)
    if importance:
        print("\nTop 3 important features:")
        for idx, imp in importance:
            print(f"   Feature {idx}: {imp:.4f}")


def example_3_model_persistence():
    """Save and load models"""
    print("\n" + "=" * 60)
    print("Example 3: Model Persistence")
    print("=" * 60)

    # Train a model
    X = np.random.randn(150, 5)
    y = (X[:, 0] + X[:, 1] + X[:, 2] > 0).astype(int)

    automl = AutoMLSystem()
    automl.train(X, y, problem_type='demo_classification')

    # Save to custom location
    custom_path = '/tmp/my_automl_model.pkl'
    automl.save(custom_path)
    print(f"\nModel saved to: {custom_path}")

    # Load and use
    loaded_automl = AutoMLSystem.load(custom_path)
    predictions = loaded_automl.predict(X[:3])
    print(f"Predictions from loaded model: {predictions}")


def example_4_integration_with_postgres():
    """Integration with PostgreSQL learning database"""
    print("\n" + "=" * 60)
    print("Example 4: PostgreSQL Integration")
    print("=" * 60)

    # When you train with problem_type, metrics are logged to PostgreSQL
    X = np.random.randn(100, 6)
    y = np.random.randint(0, 3, 100)

    automl = AutoMLSystem()
    automl.train(
        X, y,
        task_type='classification',
        problem_type='multi_class_demo'  # This gets logged to monitoring.execution_summary
    )

    # Training history is also tracked locally
    print("\nTraining history:")
    for record in automl.training_history:
        print(f"   {record['timestamp'][:19]} | {record['metric']}: {record['score']:.4f}")


def example_5_classification_probabilities():
    """Get prediction probabilities for classification"""
    print("\n" + "=" * 60)
    print("Example 5: Prediction Probabilities")
    print("=" * 60)

    X = np.random.randn(150, 4)
    y = (X[:, 0] + 2 * X[:, 1] > 0.5).astype(int)

    automl = AutoMLSystem()
    automl.train(X, y, task_type='classification')

    # Get probabilities
    test_X = X[:5]
    probabilities = automl.predict_proba(test_X)

    print("\nPrediction probabilities:")
    for i, probs in enumerate(probabilities):
        print(f"   Sample {i}: Class 0 = {probs[0]:.3f}, Class 1 = {probs[1]:.3f}")


def example_6_task_specific_optimization():
    """Optimize for specific task types"""
    print("\n" + "=" * 60)
    print("Example 6: Task-Specific Optimization")
    print("=" * 60)

    # Code complexity estimation (regression)
    X_complexity = np.random.randn(200, 12)  # 12 code features
    y_complexity = 50 + 10 * X_complexity[:, 0] + np.random.randn(200) * 5

    automl_complexity = AutoMLSystem()
    automl_complexity.train(
        X_complexity,
        y_complexity,
        task_type='regression',
        problem_type='complexity_estimation',
        ensemble=True
    )

    # Error recovery classification
    X_error = np.random.randn(200, 8)  # 8 error features
    y_error = (X_error[:, 0] + X_error[:, 1] - X_error[:, 2] > 0).astype(int)

    automl_error = AutoMLSystem()
    automl_error.train(
        X_error,
        y_error,
        task_type='classification',
        problem_type='error_recovery',
        ensemble=True
    )

    print("\nTrained 2 task-specific models:")
    print("   1. Complexity estimation (regression)")
    print("   2. Error recovery (classification)")


def example_7_no_ensemble_single_model():
    """Use single best model instead of ensemble"""
    print("\n" + "=" * 60)
    print("Example 7: Single Model (No Ensemble)")
    print("=" * 60)

    X = np.random.randn(100, 5)
    y = np.random.randn(100)

    # Disable ensemble for faster training
    automl = AutoMLSystem()
    automl.train(
        X, y,
        task_type='regression',
        ensemble=False,  # Use single best model
        optimize_hp=False  # Also skip hyperparameter optimization for speed
    )

    print("Trained single model (fast mode)")


def example_8_feature_engineering_showcase():
    """Showcase automatic feature engineering"""
    print("\n" + "=" * 60)
    print("Example 8: Automatic Feature Engineering")
    print("=" * 60)

    # Small dataset with few features -> will add polynomial features
    X_small = np.random.randn(200, 5)
    y_small = (X_small[:, 0] * X_small[:, 1] + X_small[:, 2]**2 > 0).astype(int)

    automl_small = AutoMLSystem()
    print("\nTraining with 5 features (will add polynomial features)...")
    automl_small.train(X_small, y_small)

    # Large dataset with many features -> will apply feature selection
    X_large = np.random.randn(500, 120)
    y_large = (np.sum(X_large[:, :10], axis=1) > 0).astype(int)

    automl_large = AutoMLSystem()
    print("\nTraining with 120 features (will apply feature selection)...")
    automl_large.train(X_large, y_large)


def integration_example_workflow():
    """
    Example: Integrate AutoML into a workflow

    Use case: Train model to predict optimal number of workers for a task
    """
    print("\n" + "=" * 60)
    print("Integration Example: Worker Prediction")
    print("=" * 60)

    # Simulate historical execution data
    # Features: [task_complexity, file_count, avg_file_size, git_changes, dependencies]
    X_history = np.array([
        [50, 100, 5000, 20, 5],
        [80, 200, 8000, 50, 12],
        [30, 50, 3000, 10, 3],
        [90, 300, 10000, 80, 20],
        [60, 150, 6000, 30, 8],
        [70, 180, 7000, 40, 10],
        [40, 80, 4000, 15, 4],
        [85, 250, 9000, 60, 15],
    ] * 20)  # Repeat for more samples

    # Labels: optimal number of workers
    y_history = np.array([2, 4, 1, 6, 3, 3, 2, 5] * 20)

    # Train AutoML model
    automl = AutoMLSystem()
    automl.train(
        X_history,
        y_history,
        task_type='regression',
        problem_type='worker_optimization',
        ensemble=True
    )

    # Save for production use
    automl.save('/home/sfloess/.claude/learning/worker_predictor.pkl')

    # Predict for new task
    new_task = np.array([[75, 220, 8500, 55, 14]])
    optimal_workers = int(round(automl.predict(new_task)[0]))

    print(f"\nNew task features: {new_task[0]}")
    print(f"Predicted optimal workers: {optimal_workers}")


if __name__ == '__main__':
    # Run all examples
    example_1_quick_training()
    example_2_regression()
    example_3_model_persistence()
    example_4_integration_with_postgres()
    example_5_classification_probabilities()
    example_6_task_specific_optimization()
    example_7_no_ensemble_single_model()
    example_8_feature_engineering_showcase()
    integration_example_workflow()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)
