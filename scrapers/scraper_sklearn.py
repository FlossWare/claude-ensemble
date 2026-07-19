#!/usr/bin/env python3
"""scikit-learn documentation scraper.

Covers:
  - scikit-learn user guide (supervised, unsupervised, model selection, transforms)
  - scikit-learn API reference (classes, functions, modules)
  - scikit-learn tutorials and examples
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class SklearnScraper(BaseScraper):
    """Scrape scikit-learn documentation, API reference, and tutorials."""

    SOURCES = {
        "supervised-learning": {
            "pages": {
                "https://scikit-learn.org/stable/supervised_learning.html": "Supervised Learning",
                "https://scikit-learn.org/stable/modules/linear_model.html": "Linear Models",
                "https://scikit-learn.org/stable/modules/lda_qda.html": "Linear and Quadratic Discriminant Analysis",
                "https://scikit-learn.org/stable/modules/kernel_ridge.html": "Kernel Ridge Regression",
                "https://scikit-learn.org/stable/modules/svm.html": "Support Vector Machines",
                "https://scikit-learn.org/stable/modules/sgd.html": "Stochastic Gradient Descent",
                "https://scikit-learn.org/stable/modules/neighbors.html": "Nearest Neighbors",
                "https://scikit-learn.org/stable/modules/gaussian_process.html": "Gaussian Processes",
                "https://scikit-learn.org/stable/modules/cross_decomposition.html": "Cross Decomposition",
                "https://scikit-learn.org/stable/modules/naive_bayes.html": "Naive Bayes",
                "https://scikit-learn.org/stable/modules/tree.html": "Decision Trees",
                "https://scikit-learn.org/stable/modules/ensemble.html": "Ensemble Methods",
                "https://scikit-learn.org/stable/modules/multiclass.html": "Multiclass and Multioutput",
                "https://scikit-learn.org/stable/modules/feature_selection.html": "Feature Selection",
                "https://scikit-learn.org/stable/modules/semi_supervised.html": "Semi-Supervised Learning",
                "https://scikit-learn.org/stable/modules/isotonic.html": "Isotonic Regression",
                "https://scikit-learn.org/stable/modules/calibration.html": "Probability Calibration",
                "https://scikit-learn.org/stable/modules/neural_networks_supervised.html": "Neural Network Models (supervised)",
            },
        },
        "unsupervised-learning": {
            "pages": {
                "https://scikit-learn.org/stable/unsupervised_learning.html": "Unsupervised Learning",
                "https://scikit-learn.org/stable/modules/mixture.html": "Gaussian Mixture Models",
                "https://scikit-learn.org/stable/modules/manifold.html": "Manifold Learning",
                "https://scikit-learn.org/stable/modules/clustering.html": "Clustering",
                "https://scikit-learn.org/stable/modules/biclustering.html": "Biclustering",
                "https://scikit-learn.org/stable/modules/decomposition.html": "Decomposition (PCA, NMF, etc.)",
                "https://scikit-learn.org/stable/modules/covariance.html": "Covariance Estimation",
                "https://scikit-learn.org/stable/modules/outlier_detection.html": "Novelty and Outlier Detection",
                "https://scikit-learn.org/stable/modules/density.html": "Density Estimation",
                "https://scikit-learn.org/stable/modules/neural_networks_unsupervised.html": "Neural Network Models (unsupervised)",
            },
        },
        "model-selection": {
            "pages": {
                "https://scikit-learn.org/stable/model_selection.html": "Model Selection and Evaluation",
                "https://scikit-learn.org/stable/modules/cross_validation.html": "Cross-Validation",
                "https://scikit-learn.org/stable/modules/grid_search.html": "Tuning Hyper-Parameters",
                "https://scikit-learn.org/stable/modules/model_evaluation.html": "Metrics and Scoring",
                "https://scikit-learn.org/stable/modules/learning_curve.html": "Validation Curves",
                "https://scikit-learn.org/stable/modules/model_persistence.html": "Model Persistence",
            },
        },
        "data-transforms": {
            "pages": {
                "https://scikit-learn.org/stable/data_transforms.html": "Dataset Transformations",
                "https://scikit-learn.org/stable/modules/preprocessing.html": "Preprocessing Data",
                "https://scikit-learn.org/stable/modules/impute.html": "Imputation of Missing Values",
                "https://scikit-learn.org/stable/modules/unsupervised_reduction.html": "Unsupervised Dimensionality Reduction",
                "https://scikit-learn.org/stable/modules/random_projection.html": "Random Projection",
                "https://scikit-learn.org/stable/modules/kernel_approximation.html": "Kernel Approximation",
                "https://scikit-learn.org/stable/modules/metrics.html": "Pairwise Metrics",
                "https://scikit-learn.org/stable/modules/feature_extraction.html": "Feature Extraction",
                "https://scikit-learn.org/stable/modules/compose.html": "Column Transformer",
                "https://scikit-learn.org/stable/modules/pipeline.html": "Pipelines and Composite Estimators",
            },
        },
        "inspection": {
            "pages": {
                "https://scikit-learn.org/stable/inspection.html": "Inspection",
                "https://scikit-learn.org/stable/modules/partial_dependence.html": "Partial Dependence and ICE Plots",
                "https://scikit-learn.org/stable/modules/permutation_importance.html": "Permutation Feature Importance",
            },
        },
        "visualization": {
            "pages": {
                "https://scikit-learn.org/stable/visualizations.html": "Visualizations",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.ConfusionMatrixDisplay.html": "ConfusionMatrixDisplay",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.RocCurveDisplay.html": "RocCurveDisplay",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.PrecisionRecallDisplay.html": "PrecisionRecallDisplay",
                "https://scikit-learn.org/stable/modules/generated/sklearn.calibration.CalibrationDisplay.html": "CalibrationDisplay",
                "https://scikit-learn.org/stable/modules/generated/sklearn.inspection.DecisionBoundaryDisplay.html": "DecisionBoundaryDisplay",
                "https://scikit-learn.org/stable/modules/generated/sklearn.inspection.PartialDependenceDisplay.html": "PartialDependenceDisplay",
            },
        },
        "dataset-loading": {
            "pages": {
                "https://scikit-learn.org/stable/datasets.html": "Dataset Loading Utilities",
                "https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_iris.html": "load_iris",
                "https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_digits.html": "load_digits",
                "https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_wine.html": "load_wine",
                "https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_breast_cancer.html": "load_breast_cancer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_diabetes.html": "load_diabetes",
                "https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_boston.html": "load_boston",
                "https://scikit-learn.org/stable/modules/generated/sklearn.datasets.fetch_20newsgroups.html": "fetch_20newsgroups",
                "https://scikit-learn.org/stable/modules/generated/sklearn.datasets.fetch_openml.html": "fetch_openml",
                "https://scikit-learn.org/stable/modules/generated/sklearn.datasets.make_classification.html": "make_classification",
                "https://scikit-learn.org/stable/modules/generated/sklearn.datasets.make_regression.html": "make_regression",
                "https://scikit-learn.org/stable/modules/generated/sklearn.datasets.make_blobs.html": "make_blobs",
                "https://scikit-learn.org/stable/modules/generated/sklearn.datasets.make_moons.html": "make_moons",
                "https://scikit-learn.org/stable/modules/generated/sklearn.datasets.make_circles.html": "make_circles",
            },
        },
        "computing": {
            "pages": {
                "https://scikit-learn.org/stable/computing.html": "Computing",
                "https://scikit-learn.org/stable/modules/computing.html": "Computational Performance",
                "https://scikit-learn.org/stable/developers/performance.html": "Performance Tips",
            },
        },
        "dispatching": {
            "pages": {
                "https://scikit-learn.org/stable/modules/array_api.html": "Array API Support",
            },
        },
        "tutorial-basic": {
            "pages": {
                "https://scikit-learn.org/stable/tutorial/index.html": "Tutorials Index",
                "https://scikit-learn.org/stable/tutorial/basic/tutorial.html": "An Introduction to ML with scikit-learn",
                "https://scikit-learn.org/stable/tutorial/machine_learning_map/index.html": "Choosing the Right Estimator",
            },
        },
        "tutorial-text-analytics": {
            "pages": {
                "https://scikit-learn.org/stable/tutorial/text_analytics/working_with_text_data.html": "Working with Text Data",
            },
        },
        "tutorial-statistical-inference": {
            "pages": {
                "https://scikit-learn.org/stable/tutorial/statistical_inference/index.html": "Statistical Learning Tutorial",
                "https://scikit-learn.org/stable/tutorial/statistical_inference/settings.html": "Statistical Learning Settings",
                "https://scikit-learn.org/stable/tutorial/statistical_inference/supervised_learning.html": "Supervised Learning (Tutorial)",
                "https://scikit-learn.org/stable/tutorial/statistical_inference/model_selection.html": "Model Selection (Tutorial)",
                "https://scikit-learn.org/stable/tutorial/statistical_inference/unsupervised_learning.html": "Unsupervised Learning (Tutorial)",
                "https://scikit-learn.org/stable/tutorial/statistical_inference/putting_together.html": "Putting It All Together",
            },
        },
        "modules-linear-model": {
            "pages": {
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LinearRegression.html": "LinearRegression",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html": "Ridge",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.RidgeCV.html": "RidgeCV",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Lasso.html": "Lasso",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LassoCV.html": "LassoCV",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.ElasticNet.html": "ElasticNet",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.ElasticNetCV.html": "ElasticNetCV",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html": "LogisticRegression",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegressionCV.html": "LogisticRegressionCV",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.SGDClassifier.html": "SGDClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.SGDRegressor.html": "SGDRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Perceptron.html": "Perceptron",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.PassiveAggressiveClassifier.html": "PassiveAggressiveClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.BayesianRidge.html": "BayesianRidge",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.HuberRegressor.html": "HuberRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.RANSACRegressor.html": "RANSACRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.TheilSenRegressor.html": "TheilSenRegressor",
            },
        },
        "modules-svm": {
            "pages": {
                "https://scikit-learn.org/stable/modules/generated/sklearn.svm.SVC.html": "SVC",
                "https://scikit-learn.org/stable/modules/generated/sklearn.svm.SVR.html": "SVR",
                "https://scikit-learn.org/stable/modules/generated/sklearn.svm.LinearSVC.html": "LinearSVC",
                "https://scikit-learn.org/stable/modules/generated/sklearn.svm.LinearSVR.html": "LinearSVR",
                "https://scikit-learn.org/stable/modules/generated/sklearn.svm.NuSVC.html": "NuSVC",
                "https://scikit-learn.org/stable/modules/generated/sklearn.svm.NuSVR.html": "NuSVR",
                "https://scikit-learn.org/stable/modules/generated/sklearn.svm.OneClassSVM.html": "OneClassSVM",
            },
        },
        "modules-neighbors": {
            "pages": {
                "https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.KNeighborsClassifier.html": "KNeighborsClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.KNeighborsRegressor.html": "KNeighborsRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.RadiusNeighborsClassifier.html": "RadiusNeighborsClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.RadiusNeighborsRegressor.html": "RadiusNeighborsRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.NearestNeighbors.html": "NearestNeighbors",
                "https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.NearestCentroid.html": "NearestCentroid",
                "https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.BallTree.html": "BallTree",
                "https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.KDTree.html": "KDTree",
                "https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.LocalOutlierFactor.html": "LocalOutlierFactor",
            },
        },
        "modules-tree": {
            "pages": {
                "https://scikit-learn.org/stable/modules/generated/sklearn.tree.DecisionTreeClassifier.html": "DecisionTreeClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.tree.DecisionTreeRegressor.html": "DecisionTreeRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.tree.ExtraTreeClassifier.html": "ExtraTreeClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.tree.ExtraTreeRegressor.html": "ExtraTreeRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.tree.export_graphviz.html": "export_graphviz",
                "https://scikit-learn.org/stable/modules/generated/sklearn.tree.export_text.html": "export_text",
                "https://scikit-learn.org/stable/modules/generated/sklearn.tree.plot_tree.html": "plot_tree",
            },
        },
        "modules-ensemble": {
            "pages": {
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html": "RandomForestClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html": "RandomForestRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.ExtraTreesClassifier.html": "ExtraTreesClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.ExtraTreesRegressor.html": "ExtraTreesRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.GradientBoostingClassifier.html": "GradientBoostingClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.GradientBoostingRegressor.html": "GradientBoostingRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html": "HistGradientBoostingClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html": "HistGradientBoostingRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.AdaBoostClassifier.html": "AdaBoostClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.AdaBoostRegressor.html": "AdaBoostRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.BaggingClassifier.html": "BaggingClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.BaggingRegressor.html": "BaggingRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.VotingClassifier.html": "VotingClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.VotingRegressor.html": "VotingRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.StackingClassifier.html": "StackingClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.StackingRegressor.html": "StackingRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html": "IsolationForest",
            },
        },
        "modules-neural-network": {
            "pages": {
                "https://scikit-learn.org/stable/modules/generated/sklearn.neural_network.MLPClassifier.html": "MLPClassifier",
                "https://scikit-learn.org/stable/modules/generated/sklearn.neural_network.MLPRegressor.html": "MLPRegressor",
                "https://scikit-learn.org/stable/modules/generated/sklearn.neural_network.BernoulliRBM.html": "BernoulliRBM",
            },
        },
        "modules-cluster": {
            "pages": {
                "https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html": "KMeans",
                "https://scikit-learn.org/stable/modules/generated/sklearn.cluster.MiniBatchKMeans.html": "MiniBatchKMeans",
                "https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html": "DBSCAN",
                "https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html": "HDBSCAN",
                "https://scikit-learn.org/stable/modules/generated/sklearn.cluster.OPTICS.html": "OPTICS",
                "https://scikit-learn.org/stable/modules/generated/sklearn.cluster.AgglomerativeClustering.html": "AgglomerativeClustering",
                "https://scikit-learn.org/stable/modules/generated/sklearn.cluster.SpectralClustering.html": "SpectralClustering",
                "https://scikit-learn.org/stable/modules/generated/sklearn.cluster.Birch.html": "Birch",
                "https://scikit-learn.org/stable/modules/generated/sklearn.cluster.MeanShift.html": "MeanShift",
                "https://scikit-learn.org/stable/modules/generated/sklearn.cluster.AffinityPropagation.html": "AffinityPropagation",
                "https://scikit-learn.org/stable/modules/generated/sklearn.cluster.BisectingKMeans.html": "BisectingKMeans",
            },
        },
        "modules-decomposition": {
            "pages": {
                "https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html": "PCA",
                "https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.IncrementalPCA.html": "IncrementalPCA",
                "https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.KernelPCA.html": "KernelPCA",
                "https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.SparsePCA.html": "SparsePCA",
                "https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.TruncatedSVD.html": "TruncatedSVD",
                "https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.FastICA.html": "FastICA",
                "https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.NMF.html": "NMF",
                "https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.LatentDirichletAllocation.html": "LatentDirichletAllocation",
                "https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.FactorAnalysis.html": "FactorAnalysis",
                "https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.DictionaryLearning.html": "DictionaryLearning",
            },
        },
        "modules-preprocessing": {
            "pages": {
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html": "StandardScaler",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.MinMaxScaler.html": "MinMaxScaler",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.MaxAbsScaler.html": "MaxAbsScaler",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.RobustScaler.html": "RobustScaler",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.Normalizer.html": "Normalizer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.Binarizer.html": "Binarizer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.PolynomialFeatures.html": "PolynomialFeatures",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.SplineTransformer.html": "SplineTransformer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.KBinsDiscretizer.html": "KBinsDiscretizer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.OneHotEncoder.html": "OneHotEncoder",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.OrdinalEncoder.html": "OrdinalEncoder",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.LabelEncoder.html": "LabelEncoder",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.LabelBinarizer.html": "LabelBinarizer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.FunctionTransformer.html": "FunctionTransformer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.PowerTransformer.html": "PowerTransformer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.QuantileTransformer.html": "QuantileTransformer",
            },
        },
        "modules-feature-extraction": {
            "pages": {
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.CountVectorizer.html": "CountVectorizer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html": "TfidfVectorizer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfTransformer.html": "TfidfTransformer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.HashingVectorizer.html": "HashingVectorizer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.DictVectorizer.html": "DictVectorizer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.image.extract_patches_2d.html": "extract_patches_2d",
            },
        },
        "modules-feature-selection": {
            "pages": {
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.SelectKBest.html": "SelectKBest",
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.SelectPercentile.html": "SelectPercentile",
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.RFE.html": "RFE",
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.RFECV.html": "RFECV",
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.SelectFromModel.html": "SelectFromModel",
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.SequentialFeatureSelector.html": "SequentialFeatureSelector",
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.VarianceThreshold.html": "VarianceThreshold",
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.f_classif.html": "f_classif",
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.mutual_info_classif.html": "mutual_info_classif",
                "https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.chi2.html": "chi2",
            },
        },
        "modules-metrics": {
            "pages": {
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.accuracy_score.html": "accuracy_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_score.html": "precision_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.recall_score.html": "recall_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.f1_score.html": "f1_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_auc_score.html": "roc_auc_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_curve.html": "roc_curve",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_curve.html": "precision_recall_curve",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.confusion_matrix.html": "confusion_matrix",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.classification_report.html": "classification_report",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.log_loss.html": "log_loss",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.mean_squared_error.html": "mean_squared_error",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.mean_absolute_error.html": "mean_absolute_error",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.r2_score.html": "r2_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html": "silhouette_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.calinski_harabasz_score.html": "calinski_harabasz_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.davies_bouldin_score.html": "davies_bouldin_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.adjusted_rand_score.html": "adjusted_rand_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.adjusted_mutual_info_score.html": "adjusted_mutual_info_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise_distances.html": "pairwise_distances",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.make_scorer.html": "make_scorer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html": "average_precision_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.balanced_accuracy_score.html": "balanced_accuracy_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.cohen_kappa_score.html": "cohen_kappa_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.matthews_corrcoef.html": "matthews_corrcoef",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.explained_variance_score.html": "explained_variance_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.max_error.html": "max_error",
                "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.mean_absolute_percentage_error.html": "mean_absolute_percentage_error",
            },
        },
        "modules-pipeline": {
            "pages": {
                "https://scikit-learn.org/stable/modules/generated/sklearn.pipeline.Pipeline.html": "Pipeline",
                "https://scikit-learn.org/stable/modules/generated/sklearn.pipeline.make_pipeline.html": "make_pipeline",
                "https://scikit-learn.org/stable/modules/generated/sklearn.pipeline.FeatureUnion.html": "FeatureUnion",
                "https://scikit-learn.org/stable/modules/generated/sklearn.pipeline.make_union.html": "make_union",
                "https://scikit-learn.org/stable/modules/generated/sklearn.compose.ColumnTransformer.html": "ColumnTransformer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.compose.make_column_transformer.html": "make_column_transformer",
                "https://scikit-learn.org/stable/modules/generated/sklearn.compose.make_column_selector.html": "make_column_selector",
            },
        },
        "modules-model-selection": {
            "pages": {
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.train_test_split.html": "train_test_split",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.cross_val_score.html": "cross_val_score",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.cross_validate.html": "cross_validate",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.cross_val_predict.html": "cross_val_predict",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GridSearchCV.html": "GridSearchCV",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.RandomizedSearchCV.html": "RandomizedSearchCV",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.HalvingGridSearchCV.html": "HalvingGridSearchCV",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.KFold.html": "KFold",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedKFold.html": "StratifiedKFold",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html": "GroupKFold",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.LeaveOneOut.html": "LeaveOneOut",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html": "TimeSeriesSplit",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.ShuffleSplit.html": "ShuffleSplit",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedShuffleSplit.html": "StratifiedShuffleSplit",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.RepeatedKFold.html": "RepeatedKFold",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.RepeatedStratifiedKFold.html": "RepeatedStratifiedKFold",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.learning_curve.html": "learning_curve",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.validation_curve.html": "validation_curve",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.permutation_test_score.html": "permutation_test_score",
            },
        },
        "modules-datasets": {
            "pages": {
                "https://scikit-learn.org/stable/modules/classes.html": "API Reference Index",
                "https://scikit-learn.org/stable/auto_examples/index.html": "Examples Gallery",
                "https://scikit-learn.org/stable/auto_examples/classification/plot_digits_classification.html": "Digits Classification Example",
                "https://scikit-learn.org/stable/auto_examples/cluster/plot_kmeans_digits.html": "K-Means Clustering Digits",
                "https://scikit-learn.org/stable/auto_examples/decomposition/plot_pca_iris.html": "PCA on Iris Dataset",
                "https://scikit-learn.org/stable/auto_examples/ensemble/plot_forest_importances.html": "Feature Importances with Forest",
                "https://scikit-learn.org/stable/auto_examples/model_selection/plot_grid_search_digits.html": "Grid Search on Digits",
                "https://scikit-learn.org/stable/auto_examples/text/plot_document_classification_20newsgroups.html": "Document Classification",
                "https://scikit-learn.org/stable/auto_examples/neural_networks/plot_mnist_filters.html": "MNIST Filters Visualization",
                "https://scikit-learn.org/stable/auto_examples/svm/plot_iris_svc.html": "SVM on Iris",
                "https://scikit-learn.org/stable/glossary.html": "Glossary",
                "https://scikit-learn.org/stable/developers/index.html": "Developer Guide",
                "https://scikit-learn.org/stable/developers/contributing.html": "Contributing",
                "https://scikit-learn.org/stable/whats_new.html": "Release History",
                "https://scikit-learn.org/stable/install.html": "Installation Guide",
                "https://scikit-learn.org/stable/faq.html": "FAQ",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"sklearn-{source_key}" if source_key else "sklearn"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Clean common suffixes
            for suffix in [' - scikit-learn', ' scikit-learn',
                           ' | scikit-learn', ' -- scikit-learn documentation']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})

        for url, title in pages.items():
            if not self.running:
                break

            item_id = self.make_id(url)
            content = self.fetch_url(url)

            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)

                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"sklearn-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)

        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0

        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(
                    f"Unknown source key: {self.source_key}. "
                    f"Available: {list(self.SOURCES.keys())}"
                )
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES

        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping sklearn/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    SklearnScraper(base, source_key).run()
