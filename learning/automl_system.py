#!/usr/bin/env python3
"""
AutoML System - Automated Machine Learning Pipeline

Automatically selects models, engineers features, and composes ensembles
based on task characteristics and historical performance data.

Features:
1. Automatic model selection per task type
2. Feature engineering automation (scaling, encoding, interaction terms)
3. Ensemble composition (stacking, voting, boosting)
4. Hyperparameter optimization
5. Integration with PostgreSQL learning database

Usage:
    from automl_system import AutoMLSystem

    automl = AutoMLSystem()
    model = automl.train(X, y, task_type='classification')
    predictions = automl.predict(X_test)
"""

import json
import pickle
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
from collections import defaultdict

# Machine learning imports
from sklearn.ensemble import (
    RandomForestClassifier, RandomForestRegressor,
    GradientBoostingClassifier, GradientBoostingRegressor,
    VotingClassifier, VotingRegressor,
    StackingClassifier, StackingRegressor
)
from sklearn.linear_model import LogisticRegression, Ridge, Lasso
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.preprocessing import PolynomialFeatures, LabelEncoder, OneHotEncoder
from sklearn.feature_selection import SelectKBest, f_classif, f_regression, RFE
from sklearn.decomposition import PCA
from sklearn.model_selection import cross_val_score, GridSearchCV
from sklearn.metrics import accuracy_score, f1_score, mean_squared_error, r2_score

# PostgreSQL adapter
try:
    from postgres_adapter import get_db, get_execution_monitor
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False
    print("Warning: PostgreSQL adapter not available, using in-memory storage")


class FeatureEngineer:
    """Automated feature engineering pipeline"""

    def __init__(self):
        self.scalers = {
            'standard': StandardScaler(),
            'minmax': MinMaxScaler(),
            'robust': RobustScaler()
        }
        self.selected_scaler = None
        self.poly_features = None
        self.feature_selector = None
        self.pca = None
        self.label_encoders = {}

    def auto_engineer(self, X, y=None, task_type='classification'):
        """Automatically engineer features based on data characteristics"""
        X_transformed = X.copy()

        # 1. Handle missing values
        if np.any(np.isnan(X)):
            X_transformed = self._handle_missing(X_transformed)

        # 2. Detect and encode categorical features
        X_transformed = self._encode_categorical(X_transformed)

        # 3. Scale features (choose best scaler via cross-validation)
        X_transformed = self._auto_scale(X_transformed, y, task_type)

        # 4. Generate polynomial features for small datasets
        if X.shape[1] <= 10 and X.shape[0] > 100:
            X_transformed = self._add_polynomial_features(X_transformed)

        # 5. Feature selection (if too many features)
        if X_transformed.shape[1] > 50:
            X_transformed = self._select_features(X_transformed, y, task_type)

        # 6. Dimensionality reduction (if very high-dimensional)
        if X_transformed.shape[1] > 100:
            X_transformed = self._reduce_dimensions(X_transformed)

        return X_transformed

    def transform(self, X):
        """Apply learned transformations to new data"""
        X_transformed = X.copy()

        # Apply same transformations in same order
        if np.any(np.isnan(X)):
            X_transformed = self._handle_missing(X_transformed)

        X_transformed = self._encode_categorical(X_transformed, fit=False)

        if self.selected_scaler:
            X_transformed = self.selected_scaler.transform(X_transformed)

        if self.poly_features:
            X_transformed = self.poly_features.transform(X_transformed)

        if self.feature_selector:
            X_transformed = self.feature_selector.transform(X_transformed)

        if self.pca:
            X_transformed = self.pca.transform(X_transformed)

        return X_transformed

    def _handle_missing(self, X):
        """Handle missing values with median imputation"""
        from sklearn.impute import SimpleImputer
        imputer = SimpleImputer(strategy='median')
        return imputer.fit_transform(X)

    def _encode_categorical(self, X, fit=True):
        """Encode categorical features"""
        # For now, assume X is numeric
        # In production, detect categorical columns and encode them
        return X

    def _auto_scale(self, X, y, task_type):
        """Choose best scaler via cross-validation"""
        if y is None:
            # No labels, use standard scaler
            self.selected_scaler = self.scalers['standard']
            return self.selected_scaler.fit_transform(X)

        best_score = -np.inf
        best_scaler_name = 'standard'

        # Quick model for evaluation
        if task_type == 'classification':
            quick_model = LogisticRegression(max_iter=100)
            scorer = 'accuracy'
        else:
            quick_model = Ridge()
            scorer = 'r2'

        for scaler_name, scaler in self.scalers.items():
            X_scaled = scaler.fit_transform(X)
            try:
                score = cross_val_score(quick_model, X_scaled, y, cv=3, scoring=scorer).mean()
                if score > best_score:
                    best_score = score
                    best_scaler_name = scaler_name
            except:
                pass

        self.selected_scaler = self.scalers[best_scaler_name]
        return self.selected_scaler.fit_transform(X)

    def _add_polynomial_features(self, X):
        """Add polynomial interaction features"""
        self.poly_features = PolynomialFeatures(degree=2, include_bias=False)
        return self.poly_features.fit_transform(X)

    def _select_features(self, X, y, task_type):
        """Select most important features"""
        k = min(50, X.shape[1])
        score_func = f_classif if task_type == 'classification' else f_regression
        self.feature_selector = SelectKBest(score_func=score_func, k=k)
        return self.feature_selector.fit_transform(X, y)

    def _reduce_dimensions(self, X):
        """Apply PCA for dimensionality reduction"""
        n_components = min(50, X.shape[1], X.shape[0])
        self.pca = PCA(n_components=n_components, random_state=42)
        return self.pca.fit_transform(X)


class ModelSelector:
    """Automatic model selection based on task characteristics"""

    def __init__(self):
        self.classification_models = {
            'random_forest': RandomForestClassifier(n_estimators=100, random_state=42),
            'gradient_boosting': GradientBoostingClassifier(n_estimators=100, random_state=42),
            'logistic_regression': LogisticRegression(max_iter=1000, random_state=42),
            'svm': SVC(kernel='rbf', probability=True, random_state=42),
            'decision_tree': DecisionTreeClassifier(random_state=42),
            'naive_bayes': GaussianNB(),
            'knn': KNeighborsClassifier(n_neighbors=5)
        }

        self.regression_models = {
            'random_forest': RandomForestRegressor(n_estimators=100, random_state=42),
            'gradient_boosting': GradientBoostingRegressor(n_estimators=100, random_state=42),
            'ridge': Ridge(random_state=42),
            'lasso': Lasso(random_state=42),
            'decision_tree': DecisionTreeRegressor(random_state=42),
            'svr': SVR(kernel='rbf'),
            'knn': KNeighborsRegressor(n_neighbors=5)
        }

        self.task_type_models = {}  # Learn which models work best for which tasks

    def select_models(self, X, y, task_type='classification', problem_type=None):
        """Select best models for this task via cross-validation"""
        models = self.classification_models if task_type == 'classification' else self.regression_models

        # If we have history for this problem type, use it
        if problem_type and problem_type in self.task_type_models:
            preferred = self.task_type_models[problem_type]
            return {name: models[name] for name in preferred[:3]}

        # Otherwise, evaluate all models
        model_scores = {}
        scorer = 'accuracy' if task_type == 'classification' else 'r2'

        for name, model in models.items():
            try:
                scores = cross_val_score(model, X, y, cv=3, scoring=scorer)
                model_scores[name] = scores.mean()
            except Exception as e:
                print(f"Error evaluating {name}: {e}")
                model_scores[name] = -np.inf

        # Select top 3 models
        sorted_models = sorted(model_scores.items(), key=lambda x: x[1], reverse=True)
        top_models = {name: models[name] for name, score in sorted_models[:3]}

        # Record this for future use
        if problem_type:
            self.task_type_models[problem_type] = [name for name, _ in sorted_models[:3]]

        return top_models

    def optimize_hyperparameters(self, model, X, y, task_type='classification'):
        """Optimize hyperparameters for a model"""
        param_grids = {
            'random_forest': {
                'n_estimators': [50, 100, 200],
                'max_depth': [None, 10, 20],
                'min_samples_split': [2, 5, 10]
            },
            'gradient_boosting': {
                'n_estimators': [50, 100, 200],
                'learning_rate': [0.01, 0.1, 0.5],
                'max_depth': [3, 5, 7]
            },
            'logistic_regression': {
                'C': [0.1, 1.0, 10.0],
                'penalty': ['l2']
            },
            'ridge': {
                'alpha': [0.1, 1.0, 10.0]
            },
            'lasso': {
                'alpha': [0.1, 1.0, 10.0]
            }
        }

        model_name = type(model).__name__.lower()
        for key in param_grids:
            if key in model_name:
                param_grid = param_grids[key]
                break
        else:
            return model  # No hyperparameters to optimize

        scorer = 'accuracy' if task_type == 'classification' else 'r2'
        grid_search = GridSearchCV(model, param_grid, cv=3, scoring=scorer, n_jobs=-1)
        grid_search.fit(X, y)

        return grid_search.best_estimator_


class EnsembleComposer:
    """Automatic ensemble composition"""

    def __init__(self):
        self.ensemble_method = None

    def create_ensemble(self, models, X, y, task_type='classification', method='auto'):
        """Create ensemble from multiple models"""
        if method == 'auto':
            # Choose ensemble method based on data size
            if X.shape[0] < 1000:
                method = 'voting'  # Faster
            else:
                method = 'stacking'  # Better performance

        self.ensemble_method = method

        if method == 'voting':
            return self._create_voting_ensemble(models, task_type)
        elif method == 'stacking':
            return self._create_stacking_ensemble(models, X, y, task_type)
        else:
            raise ValueError(f"Unknown ensemble method: {method}")

    def _create_voting_ensemble(self, models, task_type):
        """Create voting ensemble"""
        estimators = [(name, model) for name, model in models.items()]

        if task_type == 'classification':
            return VotingClassifier(estimators=estimators, voting='soft')
        else:
            return VotingRegressor(estimators=estimators)

    def _create_stacking_ensemble(self, models, X, y, task_type):
        """Create stacking ensemble with meta-learner"""
        estimators = [(name, model) for name, model in models.items()]

        if task_type == 'classification':
            final_estimator = LogisticRegression(max_iter=1000, random_state=42)
            return StackingClassifier(estimators=estimators, final_estimator=final_estimator)
        else:
            final_estimator = Ridge(random_state=42)
            return StackingRegressor(estimators=estimators, final_estimator=final_estimator)


class AutoMLSystem:
    """Complete AutoML pipeline"""

    def __init__(self, save_path=None):
        self.feature_engineer = FeatureEngineer()
        self.model_selector = ModelSelector()
        self.ensemble_composer = EnsembleComposer()

        self.model = None
        self.task_type = None
        self.problem_type = None
        self.training_history = []

        self.save_path = save_path or Path.home() / '.claude' / 'learning' / 'automl_system.pkl'

        # PostgreSQL integration
        self.db = get_db() if HAS_POSTGRES else None
        self.monitor = get_execution_monitor() if HAS_POSTGRES else None

    def train(self, X, y, task_type='auto', problem_type=None, ensemble=True, optimize_hp=True):
        """
        Automatically train best model for the task

        Args:
            X: Training features (numpy array or list)
            y: Training labels (numpy array or list)
            task_type: 'classification', 'regression', or 'auto' (auto-detect)
            problem_type: Optional task identifier (e.g., 'code_review', 'cost_prediction')
            ensemble: Whether to create ensemble (default True)
            optimize_hp: Whether to optimize hyperparameters (default True)

        Returns:
            Trained model
        """
        start_time = datetime.now()

        # Convert to numpy
        X = np.array(X) if not isinstance(X, np.ndarray) else X
        y = np.array(y) if not isinstance(y, np.ndarray) else y

        # Auto-detect task type
        if task_type == 'auto':
            task_type = self._detect_task_type(y)

        self.task_type = task_type
        self.problem_type = problem_type

        print(f"AutoML Training Pipeline")
        print(f"Task type: {task_type}")
        print(f"Problem type: {problem_type or 'generic'}")
        print(f"Data shape: {X.shape}")

        # Step 1: Feature engineering
        print("\n1. Feature Engineering...")
        X_transformed = self.feature_engineer.auto_engineer(X, y, task_type)
        print(f"   Transformed shape: {X_transformed.shape}")

        # Step 2: Model selection
        print("\n2. Model Selection...")
        candidate_models = self.model_selector.select_models(
            X_transformed, y, task_type, problem_type
        )
        print(f"   Selected models: {list(candidate_models.keys())}")

        # Step 3: Hyperparameter optimization
        if optimize_hp:
            print("\n3. Hyperparameter Optimization...")
            optimized_models = {}
            for name, model in candidate_models.items():
                print(f"   Optimizing {name}...")
                optimized_models[name] = self.model_selector.optimize_hyperparameters(
                    model, X_transformed, y, task_type
                )
            candidate_models = optimized_models

        # Step 4: Ensemble composition
        if ensemble and len(candidate_models) > 1:
            print("\n4. Ensemble Composition...")
            self.model = self.ensemble_composer.create_ensemble(
                candidate_models, X_transformed, y, task_type
            )
            print(f"   Ensemble method: {self.ensemble_composer.ensemble_method}")
        else:
            # Use best single model
            self.model = list(candidate_models.values())[0]
            print("\n4. Using single best model")

        # Step 5: Final training
        print("\n5. Final Training...")
        self.model.fit(X_transformed, y)

        # Evaluate
        y_pred = self.model.predict(X_transformed)
        if task_type == 'classification':
            score = accuracy_score(y, y_pred)
            metric = 'accuracy'
        else:
            score = r2_score(y, y_pred)
            metric = 'r2'

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        print(f"\n✓ Training complete!")
        print(f"   {metric}: {score:.4f}")
        print(f"   Duration: {duration_ms}ms")

        # Log to database
        self._log_training(score, duration_ms, metric)

        # Record in history
        self.training_history.append({
            'timestamp': datetime.now().isoformat(),
            'task_type': task_type,
            'problem_type': problem_type,
            'n_samples': X.shape[0],
            'n_features': X.shape[1],
            'score': score,
            'metric': metric,
            'duration_ms': duration_ms
        })

        return self.model

    def predict(self, X):
        """Make predictions on new data"""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        X = np.array(X) if not isinstance(X, np.ndarray) else X
        X_transformed = self.feature_engineer.transform(X)
        return self.model.predict(X_transformed)

    def predict_proba(self, X):
        """Get prediction probabilities (classification only)"""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        if self.task_type != 'classification':
            raise ValueError("predict_proba only available for classification tasks")

        X = np.array(X) if not isinstance(X, np.ndarray) else X
        X_transformed = self.feature_engineer.transform(X)
        return self.model.predict_proba(X_transformed)

    def save(self, path=None):
        """Save trained model to disk"""
        save_path = Path(path) if path else self.save_path
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, 'wb') as f:
            pickle.dump(self, f)

        print(f"Model saved to {save_path}")
        return save_path

    @classmethod
    def load(cls, path):
        """Load trained model from disk"""
        with open(path, 'rb') as f:
            return pickle.load(f)

    def _detect_task_type(self, y):
        """Auto-detect if classification or regression"""
        unique_values = len(np.unique(y))
        n_samples = len(y)

        # If < 10% unique values, likely classification
        if unique_values / n_samples < 0.1:
            return 'classification'

        # If all integers and few unique values, classification
        if np.all(y == y.astype(int)) and unique_values < 20:
            return 'classification'

        return 'regression'

    def _log_training(self, score, duration_ms, metric):
        """Log training to PostgreSQL"""
        if not self.monitor:
            return

        try:
            self.monitor.log_execution({
                'model': 'automl',
                'workflow': 'automl_training',
                'task_type': self.problem_type or 'generic',
                'quality_score': score,
                'duration_ms': duration_ms,
                'outcome': 'success'
            })
        except Exception as e:
            print(f"Warning: Failed to log to database: {e}")

    def get_feature_importance(self, top_n=10):
        """Get feature importance if available"""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        # Try to extract feature importance
        try:
            if hasattr(self.model, 'feature_importances_'):
                importances = self.model.feature_importances_
            elif hasattr(self.model, 'coef_'):
                importances = np.abs(self.model.coef_)
                if len(importances.shape) > 1:
                    importances = np.mean(importances, axis=0)
            else:
                return None

            # Get top N
            top_indices = np.argsort(importances)[-top_n:][::-1]
            return [(i, importances[i]) for i in top_indices]
        except:
            return None


def main():
    """Example usage and testing"""
    print("AutoML System - Example Usage\n")

    # Example 1: Classification
    print("=" * 60)
    print("Example 1: Classification Task")
    print("=" * 60)

    from sklearn.datasets import make_classification
    X_cls, y_cls = make_classification(
        n_samples=500,
        n_features=20,
        n_informative=15,
        n_redundant=5,
        random_state=42
    )

    automl_cls = AutoMLSystem()
    automl_cls.train(X_cls, y_cls, problem_type='test_classification')

    # Test prediction
    y_pred = automl_cls.predict(X_cls[:10])
    print(f"\nSample predictions: {y_pred}")

    # Feature importance
    importance = automl_cls.get_feature_importance(top_n=5)
    if importance:
        print("\nTop 5 features:")
        for idx, imp in importance:
            print(f"   Feature {idx}: {imp:.4f}")

    # Save
    automl_cls.save()

    # Example 2: Regression
    print("\n" + "=" * 60)
    print("Example 2: Regression Task")
    print("=" * 60)

    from sklearn.datasets import make_regression
    X_reg, y_reg = make_regression(
        n_samples=500,
        n_features=15,
        n_informative=10,
        random_state=42
    )

    automl_reg = AutoMLSystem()
    automl_reg.train(X_reg, y_reg, task_type='regression', problem_type='test_regression')

    # Test prediction
    y_pred = automl_reg.predict(X_reg[:5])
    print(f"\nSample predictions: {y_pred}")
    print(f"Actual values:      {y_reg[:5]}")

    # Show training history
    print("\n" + "=" * 60)
    print("Training History")
    print("=" * 60)
    for record in automl_cls.training_history + automl_reg.training_history:
        print(f"{record['timestamp'][:19]} | {record['problem_type']:20s} | "
              f"{record['metric']:8s} = {record['score']:.4f} | "
              f"{record['duration_ms']}ms")


if __name__ == '__main__':
    main()
