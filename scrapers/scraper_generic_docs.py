#!/usr/bin/env python3
"""Generic sitemap-based documentation scraper.

Usage:
    python3 scraper_generic_docs.py --config CONFIG_NAME
    python3 scraper_generic_docs.py --sitemap URL --category NAME [--prefix URL_PREFIX]

Built-in configs: splunk, grafana, orientdb, solr, zookeeper, java, lisp,
    prolog, ruby, python, haskell, mvel, beanshell, rust, kafka, lucene,
    hadoop, maven, tomcat, httpd, javacc, antlr, tensorflow, keras, jax,
    fastai, deepspeed, onnx, spacy, nltk, opencv, xgboost, lightgbm,
    catboost, deap, optuna, stable-baselines3, gymnasium, vllm, litellm,
    anthropic, openai, google-ai, mlflow, wandb, ray, dvc, spark-mllib,
    d2l, nn-deep-learning, deep-learning-book, labml-nn, distill,
    paperswithcode, colossalai, jenetics, pygad, ecj, platypus, pymoo,
    neat-python, postgresql, redis, elasticsearch, mongodb, docker,
    kubernetes, nginx, prometheus, ansible, terraform, go, typescript,
    nodejs, flask, django, fastapi, spring, huggingface, langchain,
    llamaindex, pytorch, scikit-learn, numpy, pandas, owasp, nmap,
    wireshark, gentoo-wiki, freebsd, kernel

Examples:
    python3 scraper_generic_docs.py --config splunk
    python3 scraper_generic_docs.py --config all          # run ALL configs sequentially
    python3 scraper_generic_docs.py --sitemap https://example.com/sitemap.xml --category example
"""
import argparse
import re
import sys
import os
import time
import html as html_mod
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
from scraper_base import BaseScraper

UA = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"

CONFIGS = {
    "splunk": {
        "sitemap": None,
        "category": "splunk",
        "fallback_urls": [
            "https://docs.splunk.com/Documentation",
            "https://docs.splunk.com/Documentation/Splunk",
            "https://docs.splunk.com/Documentation/SplunkCloud",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.splunk.com/Documentation",
        "exclude": ["/ReleaseNotes/", "Special:", "Category:", "index.php"],
    },
    "grafana": {
        "sitemap": "https://grafana.com/docs/sitemap.xml",
        "category": "grafana",
        "prefix": "https://grafana.com/docs/",
        "fallback_urls": [
            "https://grafana.com/docs/grafana/latest/",
            "https://grafana.com/docs/loki/latest/",
            "https://grafana.com/docs/mimir/latest/",
        ],
        "crawl": True,
        "crawl_prefix": "https://grafana.com/docs/",
    },
    "orientdb": {
        "sitemap": None,
        "category": "orientdb",
        "fallback_urls": [
            "https://orientdb.org/docs/3.2.x/",
            "https://orientdb.org/docs/3.2.x/sql/",
            "https://orientdb.org/docs/3.2.x/java/",
            "https://orientdb.org/docs/3.2.x/admin/",
        ],
        "crawl": True,
        "crawl_prefix": "https://orientdb.org/docs/",
    },
    "solr": {
        "sitemap": "https://solr.apache.org/sitemap.xml",
        "category": "solr",
        "prefix": "https://solr.apache.org/",
        "fallback_urls": [
            "https://solr.apache.org/guide/solr/latest/",
        ],
        "crawl": True,
    },
    "zookeeper": {
        "sitemap": "https://zookeeper.apache.org/sitemap.xml",
        "category": "zookeeper",
        "prefix": "https://zookeeper.apache.org/doc/",
        "fallback_urls": [
            "https://zookeeper.apache.org/doc/current/",
        ],
        "crawl": True,
    },
    "kafka": {
        "sitemap": "https://kafka.apache.org/sitemap.xml",
        "category": "kafka",
        "prefix": "https://kafka.apache.org/documentation",
        "fallback_urls": [
            "https://kafka.apache.org/documentation/",
        ],
        "crawl": True,
    },
    "lucene": {
        "sitemap": "https://lucene.apache.org/sitemap.xml",
        "category": "lucene",
        "prefix": "https://lucene.apache.org/",
        "crawl": True,
    },
    "hadoop": {
        "sitemap": "https://hadoop.apache.org/sitemap.xml",
        "category": "hadoop",
        "prefix": "https://hadoop.apache.org/docs/",
        "fallback_urls": [
            "https://hadoop.apache.org/docs/stable/",
        ],
        "crawl": True,
    },
    "maven": {
        "sitemap": "https://maven.apache.org/sitemap.xml",
        "category": "maven",
        "prefix": "https://maven.apache.org/",
        "crawl": True,
    },
    "tomcat": {
        "sitemap": "https://tomcat.apache.org/sitemap.xml",
        "category": "tomcat",
        "prefix": "https://tomcat.apache.org/tomcat-",
        "fallback_urls": [
            "https://tomcat.apache.org/tomcat-10.1-doc/index.html",
        ],
        "crawl": True,
    },
    "httpd": {
        "sitemap": "https://httpd.apache.org/sitemap.xml",
        "category": "httpd",
        "prefix": "https://httpd.apache.org/docs/",
        "fallback_urls": [
            "https://httpd.apache.org/docs/2.4/",
        ],
        "crawl": True,
    },
    "java": {
        "sitemap": "https://dev.java/sitemap.xml",
        "category": "java",
        "prefix": "https://dev.java/",
        "fallback_urls": [
            "https://dev.java/learn/",
            "https://dev.java/playground/",
            "https://docs.oracle.com/javase/tutorial/",
        ],
        "crawl": True,
        "crawl_prefix": "https://dev.java/",
    },
    "lisp": {
        "sitemap": None,
        "category": "lisp",
        "fallback_urls": [
            "https://www.lispworks.com/documentation/HyperSpec/Front/Contents.htm",
            "https://lisp-lang.org/learn/",
            "https://lisp-lang.org/learn/getting-started/",
            "https://lisp-lang.org/learn/functions/",
            "https://lisp-lang.org/learn/variables/",
            "https://lisp-lang.org/learn/macros/",
            "https://lisp-lang.org/learn/data-types/",
            "https://lisp-lang.org/learn/error-handling/",
        ],
        "crawl": True,
    },
    "prolog": {
        "sitemap": None,
        "category": "prolog",
        "fallback_urls": [
            "https://www.swi-prolog.org/pldoc/doc_for?object=manual",
            "https://www.swi-prolog.org/pldoc/man?section=quickstart",
        ],
        "crawl": True,
        "crawl_prefix": "https://www.swi-prolog.org/pldoc/",
    },
    "ruby": {
        "sitemap": None,
        "category": "ruby",
        "fallback_urls": [
            "https://docs.ruby-lang.org/en/master/",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.ruby-lang.org/en/master/",
    },
    "python": {
        "sitemap": "https://docs.python.org/3/sitemap.xml",
        "category": "python",
        "prefix": "https://docs.python.org/3/",
    },
    "haskell": {
        "sitemap": None,
        "category": "haskell",
        "fallback_urls": [
            "https://www.haskell.org/documentation/",
            "https://wiki.haskell.org/Haskell",
        ],
        "crawl": True,
        "crawl_prefix": "https://wiki.haskell.org/",
    },
    "mvel": {
        "sitemap": None,
        "category": "mvel",
        "fallback_urls": [
            "http://mvel.documentnode.com/",
        ],
        "crawl": True,
        "crawl_prefix": "http://mvel.documentnode.com/",
    },
    "beanshell": {
        "sitemap": None,
        "category": "beanshell",
        "fallback_urls": [
            "https://beanshell.github.io/manual/bshmanual.html",
            "https://beanshell.github.io/manual/quickstart.html",
            "https://beanshell.github.io/manual/syntax.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://beanshell.github.io/",
    },
    "rust": {
        "sitemap": None,
        "category": "rust",
        "fallback_urls": [
            "https://doc.rust-lang.org/book/",
            "https://doc.rust-lang.org/std/",
            "https://doc.rust-lang.org/reference/",
        ],
        "crawl": True,
        "crawl_prefix": "https://doc.rust-lang.org/",
    },
    "javacc": {
        "sitemap": None,
        "category": "javacc",
        "fallback_urls": [
            "https://javacc.github.io/javacc/",
            "https://javacc.github.io/javacc/documentation/",
            "https://javacc.github.io/javacc/tutorials/",
        ],
        "crawl": True,
        "crawl_prefix": "https://javacc.github.io/javacc/",
    },
    "antlr": {
        "sitemap": None,
        "category": "antlr",
        "fallback_urls": [
            "https://www.antlr.org/",
            "https://github.com/antlr/antlr4/blob/master/doc/index.md",
            "https://github.com/antlr/antlr4/blob/master/doc/getting-started.md",
            "https://github.com/antlr/antlr4/blob/master/doc/grammars.md",
            "https://github.com/antlr/antlr4/blob/master/doc/lexer-rules.md",
            "https://github.com/antlr/antlr4/blob/master/doc/parser-rules.md",
            "https://github.com/antlr/antlr4/blob/master/doc/actions.md",
            "https://github.com/antlr/antlr4/blob/master/doc/listeners.md",
            "https://github.com/antlr/antlr4/blob/master/doc/visitors.md",
            "https://github.com/antlr/antlr4/blob/master/doc/tree-matching.md",
        ],
        "crawl": True,
        "crawl_prefix": "https://github.com/antlr/antlr4/blob/master/doc/",
    },
    # --- AI / ML / GA / Neural Net docs ---
    "tensorflow": {
        "sitemap": "https://www.tensorflow.org/sitemap.xml",
        "category": "tensorflow",
        "prefix": "https://www.tensorflow.org/",
        "fallback_urls": [
            "https://www.tensorflow.org/guide",
            "https://www.tensorflow.org/tutorials",
            "https://www.tensorflow.org/api_docs/python/tf",
        ],
        "crawl": True,
        "crawl_prefix": "https://www.tensorflow.org/",
        "exclude": ["/versions/", "/install/", "/js/", "/lite/"],
    },
    "keras": {
        "sitemap": None,
        "category": "keras",
        "fallback_urls": [
            "https://keras.io/api/",
            "https://keras.io/guides/",
            "https://keras.io/examples/",
            "https://keras.io/getting_started/",
        ],
        "crawl": True,
        "crawl_prefix": "https://keras.io/",
        "exclude": ["/keras_cv/", "/keras_nlp/"],
    },
    "jax": {
        "sitemap": None,
        "category": "jax",
        "fallback_urls": [
            "https://jax.readthedocs.io/en/latest/",
            "https://jax.readthedocs.io/en/latest/quickstart.html",
            "https://jax.readthedocs.io/en/latest/notebooks/quickstart.html",
            "https://jax.readthedocs.io/en/latest/jax-101/index.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://jax.readthedocs.io/en/latest/",
    },
    "fastai": {
        "sitemap": None,
        "category": "fastai",
        "fallback_urls": [
            "https://docs.fast.ai/",
            "https://docs.fast.ai/tutorial.vision.html",
            "https://docs.fast.ai/tutorial.text.html",
            "https://docs.fast.ai/tutorial.tabular.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.fast.ai/",
    },
    "deepspeed": {
        "sitemap": None,
        "category": "deepspeed",
        "fallback_urls": [
            "https://www.deepspeed.ai/getting-started/",
            "https://www.deepspeed.ai/tutorials/",
            "https://www.deepspeed.ai/docs/config-json/",
        ],
        "crawl": True,
        "crawl_prefix": "https://www.deepspeed.ai/",
    },
    "onnx": {
        "sitemap": None,
        "category": "onnx",
        "fallback_urls": [
            "https://onnx.ai/onnx/intro/",
            "https://onnxruntime.ai/docs/",
            "https://onnxruntime.ai/docs/get-started/",
        ],
        "crawl": True,
        "crawl_prefix": "https://onnxruntime.ai/docs/",
    },
    "spacy": {
        "sitemap": None,
        "category": "spacy",
        "fallback_urls": [
            "https://spacy.io/usage",
            "https://spacy.io/api",
            "https://spacy.io/usage/linguistic-features",
            "https://spacy.io/usage/training",
        ],
        "crawl": True,
        "crawl_prefix": "https://spacy.io/",
        "exclude": ["/models/", "/universe/"],
    },
    "nltk": {
        "sitemap": None,
        "category": "nltk",
        "fallback_urls": [
            "https://www.nltk.org/",
            "https://www.nltk.org/book/",
            "https://www.nltk.org/api/nltk.html",
            "https://www.nltk.org/howto.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://www.nltk.org/",
    },
    "opencv": {
        "sitemap": None,
        "category": "opencv",
        "fallback_urls": [
            "https://docs.opencv.org/4.x/",
            "https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html",
            "https://docs.opencv.org/4.x/d9/df8/tutorial_root.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.opencv.org/4.x/",
    },
    "xgboost": {
        "sitemap": None,
        "category": "xgboost",
        "fallback_urls": [
            "https://xgboost.readthedocs.io/en/stable/",
            "https://xgboost.readthedocs.io/en/stable/tutorials/index.html",
            "https://xgboost.readthedocs.io/en/stable/python/python_api.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://xgboost.readthedocs.io/en/stable/",
    },
    "lightgbm": {
        "sitemap": None,
        "category": "lightgbm",
        "fallback_urls": [
            "https://lightgbm.readthedocs.io/en/stable/",
            "https://lightgbm.readthedocs.io/en/stable/Quick-Start.html",
            "https://lightgbm.readthedocs.io/en/stable/Python-API.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://lightgbm.readthedocs.io/en/stable/",
    },
    "catboost": {
        "sitemap": None,
        "category": "catboost",
        "fallback_urls": [
            "https://catboost.ai/en/docs/",
            "https://catboost.ai/en/docs/concepts/python-quickstart",
            "https://catboost.ai/en/docs/concepts/python-reference_catboost",
        ],
        "crawl": True,
        "crawl_prefix": "https://catboost.ai/en/docs/",
    },
    "deap": {
        "sitemap": None,
        "category": "deap",
        "fallback_urls": [
            "https://deap.readthedocs.io/en/master/",
            "https://deap.readthedocs.io/en/master/overview.html",
            "https://deap.readthedocs.io/en/master/tutorials/basic/part1.html",
            "https://deap.readthedocs.io/en/master/api/algo.html",
            "https://deap.readthedocs.io/en/master/api/base.html",
            "https://deap.readthedocs.io/en/master/api/tools.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://deap.readthedocs.io/en/master/",
    },
    "optuna": {
        "sitemap": None,
        "category": "optuna",
        "fallback_urls": [
            "https://optuna.readthedocs.io/en/stable/",
            "https://optuna.readthedocs.io/en/stable/tutorial/index.html",
            "https://optuna.readthedocs.io/en/stable/reference/index.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://optuna.readthedocs.io/en/stable/",
    },
    "stable-baselines3": {
        "sitemap": None,
        "category": "stable-baselines3",
        "fallback_urls": [
            "https://stable-baselines3.readthedocs.io/en/master/",
            "https://stable-baselines3.readthedocs.io/en/master/guide/quickstart.html",
            "https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html",
            "https://stable-baselines3.readthedocs.io/en/master/modules/a2c.html",
            "https://stable-baselines3.readthedocs.io/en/master/modules/dqn.html",
            "https://stable-baselines3.readthedocs.io/en/master/modules/sac.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://stable-baselines3.readthedocs.io/en/master/",
    },
    "gymnasium": {
        "sitemap": None,
        "category": "gymnasium",
        "fallback_urls": [
            "https://gymnasium.farama.org/",
            "https://gymnasium.farama.org/introduction/basic_usage/",
            "https://gymnasium.farama.org/api/env/",
            "https://gymnasium.farama.org/environments/classic_control/",
        ],
        "crawl": True,
        "crawl_prefix": "https://gymnasium.farama.org/",
    },
    "vllm": {
        "sitemap": None,
        "category": "vllm",
        "fallback_urls": [
            "https://docs.vllm.ai/en/stable/",
            "https://docs.vllm.ai/en/stable/getting_started/quickstart.html",
            "https://docs.vllm.ai/en/stable/serving/openai_compatible_server.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.vllm.ai/en/stable/",
    },
    "litellm": {
        "sitemap": None,
        "category": "litellm",
        "fallback_urls": [
            "https://docs.litellm.ai/docs/",
            "https://docs.litellm.ai/docs/providers",
            "https://docs.litellm.ai/docs/completion/input",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.litellm.ai/docs/",
    },
    "anthropic": {
        "sitemap": None,
        "category": "anthropic",
        "fallback_urls": [
            "https://docs.anthropic.com/en/docs/",
            "https://docs.anthropic.com/en/docs/build-with-claude/",
            "https://docs.anthropic.com/en/api/",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.anthropic.com/en/",
    },
    "openai": {
        "sitemap": None,
        "category": "openai",
        "fallback_urls": [
            "https://platform.openai.com/docs/overview",
            "https://platform.openai.com/docs/guides",
            "https://platform.openai.com/docs/api-reference",
        ],
        "crawl": True,
        "crawl_prefix": "https://platform.openai.com/docs/",
    },
    "google-ai": {
        "sitemap": None,
        "category": "google-ai",
        "fallback_urls": [
            "https://ai.google.dev/gemini-api/docs",
            "https://ai.google.dev/gemini-api/docs/get-started",
            "https://ai.google.dev/gemini-api/docs/models",
        ],
        "crawl": True,
        "crawl_prefix": "https://ai.google.dev/",
    },
    "mlflow": {
        "sitemap": None,
        "category": "mlflow",
        "fallback_urls": [
            "https://mlflow.org/docs/latest/index.html",
            "https://mlflow.org/docs/latest/tracking.html",
            "https://mlflow.org/docs/latest/models.html",
            "https://mlflow.org/docs/latest/python_api/index.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://mlflow.org/docs/latest/",
    },
    "wandb": {
        "sitemap": None,
        "category": "wandb",
        "fallback_urls": [
            "https://docs.wandb.ai/guides",
            "https://docs.wandb.ai/guides/track",
            "https://docs.wandb.ai/guides/sweeps",
            "https://docs.wandb.ai/ref/python",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.wandb.ai/",
    },
    "ray": {
        "sitemap": None,
        "category": "ray",
        "fallback_urls": [
            "https://docs.ray.io/en/latest/",
            "https://docs.ray.io/en/latest/ray-overview/getting-started.html",
            "https://docs.ray.io/en/latest/train/train.html",
            "https://docs.ray.io/en/latest/serve/index.html",
            "https://docs.ray.io/en/latest/rllib/index.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.ray.io/en/latest/",
    },
    "dvc": {
        "sitemap": None,
        "category": "dvc",
        "fallback_urls": [
            "https://dvc.org/doc",
            "https://dvc.org/doc/start",
            "https://dvc.org/doc/user-guide",
            "https://dvc.org/doc/command-reference",
        ],
        "crawl": True,
        "crawl_prefix": "https://dvc.org/doc",
    },
    "spark-mllib": {
        "sitemap": None,
        "category": "spark-mllib",
        "fallback_urls": [
            "https://spark.apache.org/docs/latest/ml-guide.html",
            "https://spark.apache.org/docs/latest/ml-classification-regression.html",
            "https://spark.apache.org/docs/latest/ml-clustering.html",
            "https://spark.apache.org/docs/latest/ml-pipeline.html",
            "https://spark.apache.org/docs/latest/ml-tuning.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://spark.apache.org/docs/latest/ml-",
    },
    # --- Neural network theory / education ---
    "d2l": {
        "sitemap": None,
        "category": "d2l",
        "fallback_urls": [
            "https://d2l.ai/",
            "https://d2l.ai/chapter_introduction/index.html",
            "https://d2l.ai/chapter_preliminaries/index.html",
            "https://d2l.ai/chapter_linear-networks/index.html",
            "https://d2l.ai/chapter_multilayer-perceptrons/index.html",
            "https://d2l.ai/chapter_convolutional-neural-networks/index.html",
            "https://d2l.ai/chapter_recurrent-neural-networks/index.html",
            "https://d2l.ai/chapter_attention-mechanisms/index.html",
            "https://d2l.ai/chapter_optimization/index.html",
            "https://d2l.ai/chapter_generative-adversarial-networks/index.html",
            "https://d2l.ai/chapter_natural-language-processing-pretraining/index.html",
            "https://d2l.ai/chapter_natural-language-processing-applications/index.html",
            "https://d2l.ai/chapter_recommender-systems/index.html",
            "https://d2l.ai/chapter_gaussian-processes/index.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://d2l.ai/chapter_",
    },
    "nn-deep-learning": {
        "sitemap": None,
        "category": "nn-deep-learning",
        "fallback_urls": [
            "http://neuralnetworksanddeeplearning.com/index.html",
            "http://neuralnetworksanddeeplearning.com/chap1.html",
            "http://neuralnetworksanddeeplearning.com/chap2.html",
            "http://neuralnetworksanddeeplearning.com/chap3.html",
            "http://neuralnetworksanddeeplearning.com/chap4.html",
            "http://neuralnetworksanddeeplearning.com/chap5.html",
            "http://neuralnetworksanddeeplearning.com/chap6.html",
        ],
        "crawl": True,
        "crawl_prefix": "http://neuralnetworksanddeeplearning.com/",
    },
    "deep-learning-book": {
        "sitemap": None,
        "category": "deep-learning-book",
        "fallback_urls": [
            "https://www.deeplearningbook.org/",
            "https://www.deeplearningbook.org/contents/intro.html",
            "https://www.deeplearningbook.org/contents/linear_algebra.html",
            "https://www.deeplearningbook.org/contents/prob.html",
            "https://www.deeplearningbook.org/contents/numerical.html",
            "https://www.deeplearningbook.org/contents/ml.html",
            "https://www.deeplearningbook.org/contents/mlp.html",
            "https://www.deeplearningbook.org/contents/regularization.html",
            "https://www.deeplearningbook.org/contents/optimization.html",
            "https://www.deeplearningbook.org/contents/convnets.html",
            "https://www.deeplearningbook.org/contents/rnn.html",
            "https://www.deeplearningbook.org/contents/representation.html",
            "https://www.deeplearningbook.org/contents/generative_models.html",
            "https://www.deeplearningbook.org/contents/monte_carlo.html",
            "https://www.deeplearningbook.org/contents/autoencoders.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://www.deeplearningbook.org/",
    },
    "labml-nn": {
        "sitemap": None,
        "category": "labml-nn",
        "fallback_urls": [
            "https://nn.labml.ai/",
            "https://nn.labml.ai/transformers/index.html",
            "https://nn.labml.ai/transformers/mha.html",
            "https://nn.labml.ai/transformers/feed_forward.html",
            "https://nn.labml.ai/gan/index.html",
            "https://nn.labml.ai/diffusion/index.html",
            "https://nn.labml.ai/recurrent_highway_networks/index.html",
            "https://nn.labml.ai/lstm/index.html",
            "https://nn.labml.ai/capsule_networks/index.html",
            "https://nn.labml.ai/normalization/index.html",
            "https://nn.labml.ai/optimizers/index.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://nn.labml.ai/",
    },
    "distill": {
        "sitemap": None,
        "category": "distill",
        "fallback_urls": [
            "https://distill.pub/",
            "https://distill.pub/2017/momentum/",
            "https://distill.pub/2017/feature-visualization/",
            "https://distill.pub/2019/activation-atlas/",
            "https://distill.pub/2020/circuits/zoom-in/",
            "https://distill.pub/2021/gnn-intro/",
            "https://distill.pub/2021/understanding-gnns/",
            "https://distill.pub/2019/memorization-in-rnns/",
            "https://distill.pub/2020/growing-ca/",
            "https://distill.pub/2019/visual-exploration-gaussian-processes/",
            "https://distill.pub/2016/misread-tsne/",
            "https://distill.pub/2020/bayesian-optimization/",
        ],
        "crawl": True,
        "crawl_prefix": "https://distill.pub/",
    },
    "paperswithcode": {
        "sitemap": None,
        "category": "paperswithcode",
        "fallback_urls": [
            "https://paperswithcode.com/methods",
            "https://paperswithcode.com/methods/category/convolutional-neural-networks",
            "https://paperswithcode.com/methods/category/attention-mechanisms",
            "https://paperswithcode.com/methods/category/normalization",
            "https://paperswithcode.com/methods/category/activation-functions",
            "https://paperswithcode.com/methods/category/recurrent-neural-networks",
            "https://paperswithcode.com/methods/category/generative-adversarial-networks",
            "https://paperswithcode.com/methods/category/transformers",
            "https://paperswithcode.com/methods/category/object-detection-models",
            "https://paperswithcode.com/methods/category/language-models",
        ],
        "crawl": True,
        "crawl_prefix": "https://paperswithcode.com/method",
    },
    "colossalai": {
        "sitemap": None,
        "category": "colossalai",
        "fallback_urls": [
            "https://colossalai.org/docs/get_started/installation",
            "https://colossalai.org/docs/basics/launch_colossalai",
            "https://colossalai.org/docs/features/mixed_precision_training",
            "https://colossalai.org/docs/features/pipeline_parallel",
            "https://colossalai.org/docs/features/tensor_parallel",
        ],
        "crawl": True,
        "crawl_prefix": "https://colossalai.org/docs/",
    },
    # --- Genetic algorithms / evolutionary computation ---
    "jenetics": {
        "sitemap": None,
        "category": "jenetics",
        "fallback_urls": [
            "https://jenetics.io/",
            "https://jenetics.io/manual/manual-8.1.0.html",
            "https://jenetics.io/javadoc/jenetics/8.1/index.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://jenetics.io/",
    },
    "pygad": {
        "sitemap": None,
        "category": "pygad",
        "fallback_urls": [
            "https://pygad.readthedocs.io/en/latest/",
            "https://pygad.readthedocs.io/en/latest/pygad.html",
            "https://pygad.readthedocs.io/en/latest/pygad_more.html",
            "https://pygad.readthedocs.io/en/latest/nn.html",
            "https://pygad.readthedocs.io/en/latest/cnn.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://pygad.readthedocs.io/en/latest/",
    },
    "ecj": {
        "sitemap": None,
        "category": "ecj",
        "fallback_urls": [
            "https://cs.gmu.edu/~eclab/projects/ecj/",
            "https://cs.gmu.edu/~eclab/projects/ecj/docs/",
            "https://cs.gmu.edu/~eclab/projects/ecj/manual.pdf",
        ],
        "crawl": True,
        "crawl_prefix": "https://cs.gmu.edu/~eclab/projects/ecj/",
    },
    "platypus": {
        "sitemap": None,
        "category": "platypus",
        "fallback_urls": [
            "https://platypus.readthedocs.io/en/latest/",
            "https://platypus.readthedocs.io/en/latest/getting-started.html",
            "https://platypus.readthedocs.io/en/latest/algorithms.html",
            "https://platypus.readthedocs.io/en/latest/experimenter.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://platypus.readthedocs.io/en/latest/",
    },
    "pymoo": {
        "sitemap": None,
        "category": "pymoo",
        "fallback_urls": [
            "https://pymoo.org/",
            "https://pymoo.org/getting_started/index.html",
            "https://pymoo.org/algorithms/index.html",
            "https://pymoo.org/operators/index.html",
            "https://pymoo.org/problems/index.html",
            "https://pymoo.org/interface/index.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://pymoo.org/",
    },
    "neat-python": {
        "sitemap": None,
        "category": "neat-python",
        "fallback_urls": [
            "https://neat-python.readthedocs.io/en/latest/",
            "https://neat-python.readthedocs.io/en/latest/neat_overview.html",
            "https://neat-python.readthedocs.io/en/latest/config_file.html",
            "https://neat-python.readthedocs.io/en/latest/xor_example.html",
            "https://neat-python.readthedocs.io/en/latest/customization.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://neat-python.readthedocs.io/en/latest/",
    },
    # --- Database & Infrastructure ---
    "postgresql": {
        "sitemap": None,
        "category": "postgresql",
        "fallback_urls": [
            "https://www.postgresql.org/docs/current/",
            "https://www.postgresql.org/docs/current/tutorial.html",
            "https://www.postgresql.org/docs/current/sql.html",
            "https://www.postgresql.org/docs/current/admin.html",
            "https://www.postgresql.org/docs/current/internals.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://www.postgresql.org/docs/",
    },
    "redis": {
        "sitemap": None,
        "category": "redis",
        "fallback_urls": [
            "https://redis.io/docs/",
            "https://redis.io/docs/getting-started/",
            "https://redis.io/docs/data-types/",
            "https://redis.io/docs/management/",
            "https://redis.io/docs/connect/",
        ],
        "crawl": True,
        "crawl_prefix": "https://redis.io/docs/",
    },
    "elasticsearch": {
        "sitemap": None,
        "category": "elasticsearch",
        "fallback_urls": [
            "https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html",
            "https://www.elastic.co/guide/en/elasticsearch/reference/current/getting-started.html",
            "https://www.elastic.co/guide/en/elasticsearch/reference/current/rest-apis.html",
            "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://www.elastic.co/guide/",
    },
    "mongodb": {
        "sitemap": None,
        "category": "mongodb",
        "fallback_urls": [
            "https://www.mongodb.com/docs/manual/",
            "https://www.mongodb.com/docs/manual/introduction/",
            "https://www.mongodb.com/docs/manual/crud/",
            "https://www.mongodb.com/docs/manual/aggregation/",
            "https://www.mongodb.com/docs/manual/indexes/",
            "https://www.mongodb.com/docs/manual/administration/",
        ],
        "crawl": True,
        "crawl_prefix": "https://www.mongodb.com/docs/",
    },
    "docker": {
        "sitemap": None,
        "category": "docker",
        "fallback_urls": [
            "https://docs.docker.com/",
            "https://docs.docker.com/get-started/",
            "https://docs.docker.com/engine/",
            "https://docs.docker.com/compose/",
            "https://docs.docker.com/build/",
            "https://docs.docker.com/network/",
            "https://docs.docker.com/storage/",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.docker.com/",
        "exclude": ["/desktop/", "/scout/"],
    },
    "kubernetes": {
        "sitemap": None,
        "category": "kubernetes",
        "fallback_urls": [
            "https://kubernetes.io/docs/",
            "https://kubernetes.io/docs/concepts/",
            "https://kubernetes.io/docs/tasks/",
            "https://kubernetes.io/docs/tutorials/",
            "https://kubernetes.io/docs/reference/",
            "https://kubernetes.io/docs/setup/",
        ],
        "crawl": True,
        "crawl_prefix": "https://kubernetes.io/docs/",
    },
    "nginx": {
        "sitemap": None,
        "category": "nginx",
        "fallback_urls": [
            "https://nginx.org/en/docs/",
            "https://nginx.org/en/docs/beginners_guide.html",
            "https://nginx.org/en/docs/http/ngx_http_core_module.html",
            "https://nginx.org/en/docs/http/ngx_http_proxy_module.html",
            "https://nginx.org/en/docs/http/ngx_http_upstream_module.html",
            "https://nginx.org/en/docs/stream/ngx_stream_core_module.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://nginx.org/en/docs/",
    },
    "prometheus": {
        "sitemap": None,
        "category": "prometheus",
        "fallback_urls": [
            "https://prometheus.io/docs/introduction/overview/",
            "https://prometheus.io/docs/prometheus/latest/getting_started/",
            "https://prometheus.io/docs/prometheus/latest/configuration/configuration/",
            "https://prometheus.io/docs/prometheus/latest/querying/basics/",
            "https://prometheus.io/docs/alerting/latest/overview/",
        ],
        "crawl": True,
        "crawl_prefix": "https://prometheus.io/docs/",
    },
    "ansible": {
        "sitemap": None,
        "category": "ansible",
        "fallback_urls": [
            "https://docs.ansible.com/ansible/latest/index.html",
            "https://docs.ansible.com/ansible/latest/getting_started/index.html",
            "https://docs.ansible.com/ansible/latest/playbook_guide/index.html",
            "https://docs.ansible.com/ansible/latest/inventory_guide/index.html",
            "https://docs.ansible.com/ansible/latest/module_plugin_guide/index.html",
            "https://docs.ansible.com/ansible/latest/collections/index.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.ansible.com/ansible/latest/",
    },
    "terraform": {
        "sitemap": None,
        "category": "terraform",
        "fallback_urls": [
            "https://developer.hashicorp.com/terraform/docs",
            "https://developer.hashicorp.com/terraform/tutorials",
            "https://developer.hashicorp.com/terraform/language",
            "https://developer.hashicorp.com/terraform/cli",
            "https://developer.hashicorp.com/terraform/internals",
        ],
        "crawl": True,
        "crawl_prefix": "https://developer.hashicorp.com/terraform/",
    },
    # --- Programming Languages & Frameworks ---
    "go": {
        "sitemap": None,
        "category": "go",
        "fallback_urls": [
            "https://go.dev/doc/",
            "https://go.dev/doc/effective_go",
            "https://go.dev/doc/tutorial/getting-started",
            "https://go.dev/ref/spec",
            "https://go.dev/doc/modules/managing-dependencies",
        ],
        "crawl": True,
        "crawl_prefix": "https://go.dev/doc/",
    },
    "typescript": {
        "sitemap": None,
        "category": "typescript",
        "fallback_urls": [
            "https://www.typescriptlang.org/docs/",
            "https://www.typescriptlang.org/docs/handbook/intro.html",
            "https://www.typescriptlang.org/docs/handbook/2/basic-types.html",
            "https://www.typescriptlang.org/docs/handbook/2/everyday-types.html",
            "https://www.typescriptlang.org/docs/handbook/2/functions.html",
            "https://www.typescriptlang.org/docs/handbook/2/objects.html",
            "https://www.typescriptlang.org/docs/handbook/2/generics.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://www.typescriptlang.org/docs/",
    },
    "nodejs": {
        "sitemap": None,
        "category": "nodejs",
        "fallback_urls": [
            "https://nodejs.org/docs/latest/api/",
            "https://nodejs.org/docs/latest/api/synopsis.html",
            "https://nodejs.org/docs/latest/api/fs.html",
            "https://nodejs.org/docs/latest/api/http.html",
            "https://nodejs.org/docs/latest/api/path.html",
            "https://nodejs.org/docs/latest/api/stream.html",
            "https://nodejs.org/docs/latest/api/events.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://nodejs.org/docs/",
    },
    "flask": {
        "sitemap": None,
        "category": "flask",
        "fallback_urls": [
            "https://flask.palletsprojects.com/en/stable/",
            "https://flask.palletsprojects.com/en/stable/quickstart/",
            "https://flask.palletsprojects.com/en/stable/tutorial/",
            "https://flask.palletsprojects.com/en/stable/api/",
            "https://flask.palletsprojects.com/en/stable/patterns/",
        ],
        "crawl": True,
        "crawl_prefix": "https://flask.palletsprojects.com/en/stable/",
    },
    "django": {
        "sitemap": None,
        "category": "django",
        "fallback_urls": [
            "https://docs.djangoproject.com/en/stable/",
            "https://docs.djangoproject.com/en/stable/intro/tutorial01/",
            "https://docs.djangoproject.com/en/stable/topics/",
            "https://docs.djangoproject.com/en/stable/ref/",
            "https://docs.djangoproject.com/en/stable/howto/",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.djangoproject.com/en/stable/",
    },
    "fastapi": {
        "sitemap": None,
        "category": "fastapi",
        "fallback_urls": [
            "https://fastapi.tiangolo.com/",
            "https://fastapi.tiangolo.com/tutorial/",
            "https://fastapi.tiangolo.com/tutorial/first-steps/",
            "https://fastapi.tiangolo.com/tutorial/path-params/",
            "https://fastapi.tiangolo.com/tutorial/query-params/",
            "https://fastapi.tiangolo.com/advanced/",
            "https://fastapi.tiangolo.com/deployment/",
        ],
        "crawl": True,
        "crawl_prefix": "https://fastapi.tiangolo.com/",
    },
    "spring": {
        "sitemap": None,
        "category": "spring",
        "fallback_urls": [
            "https://docs.spring.io/spring-boot/reference/index.html",
            "https://docs.spring.io/spring-framework/reference/index.html",
            "https://docs.spring.io/spring-boot/getting-started/index.html",
            "https://docs.spring.io/spring-framework/reference/core.html",
            "https://docs.spring.io/spring-framework/reference/web.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.spring.io/",
    },
    # --- AI/ML additions ---
    "huggingface": {
        "sitemap": None,
        "category": "huggingface",
        "fallback_urls": [
            "https://huggingface.co/docs/transformers/index",
            "https://huggingface.co/docs/transformers/quicktour",
            "https://huggingface.co/docs/transformers/training",
            "https://huggingface.co/docs/transformers/pipeline_tutorial",
            "https://huggingface.co/docs/datasets/index",
            "https://huggingface.co/docs/tokenizers/index",
            "https://huggingface.co/docs/accelerate/index",
            "https://huggingface.co/docs/peft/index",
        ],
        "crawl": True,
        "crawl_prefix": "https://huggingface.co/docs/",
        "exclude": ["/model_doc/", "/internal/"],
    },
    "langchain": {
        "sitemap": None,
        "category": "langchain",
        "fallback_urls": [
            "https://python.langchain.com/docs/introduction/",
            "https://python.langchain.com/docs/tutorials/",
            "https://python.langchain.com/docs/how_to/",
            "https://python.langchain.com/docs/concepts/",
            "https://python.langchain.com/docs/integrations/",
        ],
        "crawl": True,
        "crawl_prefix": "https://python.langchain.com/docs/",
    },
    "llamaindex": {
        "sitemap": None,
        "category": "llamaindex",
        "fallback_urls": [
            "https://docs.llamaindex.ai/en/stable/",
            "https://docs.llamaindex.ai/en/stable/getting_started/",
            "https://docs.llamaindex.ai/en/stable/understanding/",
            "https://docs.llamaindex.ai/en/stable/use_cases/",
            "https://docs.llamaindex.ai/en/stable/module_guides/",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.llamaindex.ai/en/stable/",
    },
    "pytorch": {
        "sitemap": None,
        "category": "pytorch",
        "fallback_urls": [
            "https://pytorch.org/docs/stable/index.html",
            "https://pytorch.org/docs/stable/torch.html",
            "https://pytorch.org/docs/stable/nn.html",
            "https://pytorch.org/docs/stable/optim.html",
            "https://pytorch.org/docs/stable/autograd.html",
            "https://pytorch.org/tutorials/beginner/basics/intro.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://pytorch.org/docs/stable/",
    },
    "scikit-learn": {
        "sitemap": None,
        "category": "scikit-learn",
        "fallback_urls": [
            "https://scikit-learn.org/stable/user_guide.html",
            "https://scikit-learn.org/stable/tutorial/index.html",
            "https://scikit-learn.org/stable/modules/classes.html",
            "https://scikit-learn.org/stable/auto_examples/index.html",
            "https://scikit-learn.org/stable/developers/index.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://scikit-learn.org/stable/",
    },
    "numpy": {
        "sitemap": None,
        "category": "numpy",
        "fallback_urls": [
            "https://numpy.org/doc/stable/",
            "https://numpy.org/doc/stable/user/index.html",
            "https://numpy.org/doc/stable/reference/index.html",
            "https://numpy.org/doc/stable/user/absolute_beginners.html",
            "https://numpy.org/doc/stable/user/basics.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://numpy.org/doc/stable/",
    },
    "pandas": {
        "sitemap": None,
        "category": "pandas",
        "fallback_urls": [
            "https://pandas.pydata.org/docs/",
            "https://pandas.pydata.org/docs/getting_started/index.html",
            "https://pandas.pydata.org/docs/user_guide/index.html",
            "https://pandas.pydata.org/docs/reference/index.html",
            "https://pandas.pydata.org/docs/development/index.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://pandas.pydata.org/docs/",
    },
    # --- Security & Networking ---
    "owasp": {
        "sitemap": None,
        "category": "owasp",
        "fallback_urls": [
            "https://owasp.org/www-project-web-security-testing-guide/",
            "https://owasp.org/www-project-web-security-testing-guide/latest/",
            "https://owasp.org/www-project-top-ten/",
            "https://owasp.org/www-project-application-security-verification-standard/",
            "https://owasp.org/www-community/attacks/",
            "https://owasp.org/www-community/vulnerabilities/",
        ],
        "crawl": True,
        "crawl_prefix": "https://owasp.org/www-project-",
    },
    "nmap": {
        "sitemap": None,
        "category": "nmap",
        "fallback_urls": [
            "https://nmap.org/book/",
            "https://nmap.org/book/man.html",
            "https://nmap.org/book/man-port-scanning-techniques.html",
            "https://nmap.org/book/man-host-discovery.html",
            "https://nmap.org/book/man-os-detection.html",
            "https://nmap.org/book/nse.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://nmap.org/book/",
    },
    "wireshark": {
        "sitemap": None,
        "category": "wireshark",
        "fallback_urls": [
            "https://wiki.wireshark.org/",
            "https://wiki.wireshark.org/CaptureSetup",
            "https://wiki.wireshark.org/DisplayFilters",
            "https://wiki.wireshark.org/CaptureFilters",
            "https://wiki.wireshark.org/ProtocolReference",
            "https://wiki.wireshark.org/SampleCaptures",
        ],
        "crawl": True,
        "crawl_prefix": "https://wiki.wireshark.org/",
    },
    # --- Linux & Systems ---
    "gentoo-wiki": {
        "sitemap": None,
        "category": "gentoo-wiki",
        "fallback_urls": [
            "https://wiki.gentoo.org/wiki/Main_Page",
            "https://wiki.gentoo.org/wiki/Handbook:AMD64",
            "https://wiki.gentoo.org/wiki/Portage",
            "https://wiki.gentoo.org/wiki/Kernel",
            "https://wiki.gentoo.org/wiki/Networking",
            "https://wiki.gentoo.org/wiki/Security",
        ],
        "crawl": True,
        "crawl_prefix": "https://wiki.gentoo.org/wiki/",
        "exclude": ["Special:", "Talk:", "User:", "Category:"],
    },
    "freebsd": {
        "sitemap": None,
        "category": "freebsd",
        "fallback_urls": [
            "https://docs.freebsd.org/en/books/handbook/",
            "https://docs.freebsd.org/en/books/handbook/introduction/",
            "https://docs.freebsd.org/en/books/handbook/install/",
            "https://docs.freebsd.org/en/books/handbook/basics/",
            "https://docs.freebsd.org/en/books/handbook/network-servers/",
            "https://docs.freebsd.org/en/articles/",
        ],
        "crawl": True,
        "crawl_prefix": "https://docs.freebsd.org/en/",
    },
    "kernel": {
        "sitemap": None,
        "category": "kernel",
        "fallback_urls": [
            "https://www.kernel.org/doc/html/latest/",
            "https://www.kernel.org/doc/html/latest/admin-guide/index.html",
            "https://www.kernel.org/doc/html/latest/process/index.html",
            "https://www.kernel.org/doc/html/latest/driver-api/index.html",
            "https://www.kernel.org/doc/html/latest/networking/index.html",
            "https://www.kernel.org/doc/html/latest/filesystems/index.html",
        ],
        "crawl": True,
        "crawl_prefix": "https://www.kernel.org/doc/html/latest/",
    },
}


class GenericDocsScraper(BaseScraper):
    """Scrape documentation sites via sitemap or link crawling."""

    def __init__(self, base_dir, config):
        super().__init__(config["category"], base_dir, interval_seconds=0)
        self.config = config
        self.seen_urls = set()
        self.max_pages = config.get("max_pages", 10000)
        self.delay = config.get("delay", 0.5)

    def _fetch_sitemap_urls(self, sitemap_url):
        """Fetch URLs from a sitemap (handles sitemap index too)."""
        xml_content = self.fetch_url(sitemap_url, timeout=60)
        if not xml_content:
            return []

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            self.log.error(f"Sitemap parse failed: {e}")
            return []

        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = []

        sitemaps = root.findall("sm:sitemap", ns)
        if sitemaps:
            self.log.info(f"Sitemap index with {len(sitemaps)} sub-sitemaps")
            for sm in sitemaps:
                loc = sm.find("sm:loc", ns)
                if loc is not None and loc.text:
                    sub_urls = self._fetch_sitemap_urls(loc.text.strip())
                    urls.extend(sub_urls)
            return urls

        for url_elem in root.findall("sm:url", ns):
            loc = url_elem.find("sm:loc", ns)
            if loc is not None and loc.text:
                urls.append(loc.text.strip())

        return urls

    def _extract_links(self, html_content, base_url):
        """Extract links from HTML for crawling."""
        links = set()
        for match in re.finditer(r'href=["\']([^"\'#]+)', html_content):
            href = match.group(1).split('#')[0].split('?')[0]
            if href.startswith('/'):
                from urllib.parse import urljoin
                href = urljoin(base_url, href)
            if href.startswith('http'):
                links.add(href)
        return links

    def _strip_html(self, html_content):
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content):
        match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _should_include(self, url):
        prefix = self.config.get("prefix", "")
        if prefix and not url.startswith(prefix):
            return False
        excludes = self.config.get("exclude", [])
        for exc in excludes:
            if exc in url:
                return False
        return True

    def _scrape_url(self, url):
        """Scrape a single URL. Returns list of discovered links if crawling."""
        if url in self.seen_urls:
            return []
        self.seen_urls.add(url)

        item_id = self.make_id(url)
        existing = self.base_dir / f"{item_id}.json"
        if existing.exists():
            html = self.fetch_url(url) if self.config.get("crawl") else None
            if html and self.config.get("crawl"):
                return list(self._extract_links(html, url))
            return []

        html = self.fetch_url(url)
        if not html or len(html) < 500:
            return []

        new_links = []
        if self.config.get("crawl"):
            new_links = list(self._extract_links(html, url))

        text = self._strip_html(html)
        if len(text) < 100:
            return new_links

        title = self._extract_title(html) or url.split('/')[-1]
        section = ""
        prefix = self.config.get("prefix", "")
        if prefix and url.startswith(prefix):
            after = url[len(prefix):]
            section = after.split("/")[0] if "/" in after else after

        self.save_item(item_id, {
            "title": title,
            "content": text[:50000],
            "url": url,
            "category": self.config["category"],
            "section": section,
            "type": "documentation",
        })

        return new_links

    def scrape(self):
        urls = []

        sitemap = self.config.get("sitemap")
        if sitemap:
            self.log.info(f"Fetching sitemap: {sitemap}")
            all_urls = self._fetch_sitemap_urls(sitemap)
            urls = [u for u in all_urls if self._should_include(u)]
            self.log.info(f"Found {len(urls)} URLs from sitemap (filtered from {len(all_urls)})")

        fallbacks = self.config.get("fallback_urls", [])
        if not urls and fallbacks:
            self.log.info(f"Using {len(fallbacks)} fallback seed URLs")
            urls = list(fallbacks)
        elif fallbacks:
            for fb in fallbacks:
                if fb not in urls:
                    urls.append(fb)

        total = 0
        queue = list(urls)
        crawl_prefix = self.config.get("crawl_prefix", self.config.get("prefix", ""))

        while queue and total < self.max_pages:
            if not self.running:
                break

            url = queue.pop(0)
            if url in self.seen_urls:
                continue

            new_links = self._scrape_url(url)
            if self.stats["fetched"] > total:
                total = self.stats["fetched"]

            if self.config.get("crawl") and crawl_prefix:
                for link in new_links:
                    if (link.startswith(crawl_prefix) and
                            link not in self.seen_urls and
                            link not in queue):
                        queue.append(link)

            if len(self.seen_urls) % 50 == 0:
                self.log.info(
                    f"Progress: {len(self.seen_urls)} visited, "
                    f"{total} saved, queue: {len(queue)}"
                )

            time.sleep(self.delay)

        return total


if __name__ == "__main__":
    base = os.path.expanduser("~")

    # Support positional arg for fleet deployment (shlex.quote-safe)
    if len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
        config_name = sys.argv[1]
        if config_name == "all":
            for name, cfg in CONFIGS.items():
                print(f"\n{'='*60}\nStarting: {name}\n{'='*60}")
                GenericDocsScraper(base, cfg).run()
        elif config_name in CONFIGS:
            GenericDocsScraper(base, CONFIGS[config_name]).run()
        else:
            print(f"Unknown config: {config_name}")
            print(f"Available: {', '.join(sorted(CONFIGS.keys()))}")
            sys.exit(1)
        sys.exit(0)

    parser = argparse.ArgumentParser(description="Generic docs scraper")
    parser.add_argument("config_name", nargs="?", help="Built-in config name (or 'all')")
    parser.add_argument("--config", help="Built-in config name (or 'all')")
    parser.add_argument("--sitemap", help="Custom sitemap URL")
    parser.add_argument("--category", help="Category name")
    parser.add_argument("--prefix", help="URL prefix filter", default="")
    parser.add_argument("--crawl", action="store_true", help="Follow links")
    parser.add_argument("--max-pages", type=int, default=10000)
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()

    config = args.config or args.config_name

    if config:
        if config == "all":
            for name, cfg in CONFIGS.items():
                print(f"\n{'='*60}\nStarting: {name}\n{'='*60}")
                GenericDocsScraper(base, cfg).run()
        elif config in CONFIGS:
            GenericDocsScraper(base, CONFIGS[config]).run()
        else:
            print(f"Unknown config: {config}")
            print(f"Available: {', '.join(sorted(CONFIGS.keys()))}")
            sys.exit(1)
    elif args.sitemap or args.category:
        if not args.category:
            print("--category required with --sitemap")
            sys.exit(1)
        cfg = {
            "sitemap": args.sitemap,
            "category": args.category,
            "prefix": args.prefix,
            "crawl": args.crawl,
            "max_pages": args.max_pages,
            "delay": args.delay,
        }
        GenericDocsScraper(base, cfg).run()
    else:
        parser.print_help()
