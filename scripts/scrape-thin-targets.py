#!/usr/bin/env python3
"""
Scrape targets that are thin in the knowledge base.
Zero external dependencies — runs on any fleet worker.

Usage:
    python3 scrape-thin-targets.py --group GROUP [--api URL] [--max-pages N]

Groups: ai-providers, math, physics, chemistry, biology, earth-science, engineering,
        computer-science, neuroscience, infra, dev, python, containers, databases,
        networking, linux, embedded, statistics, astronomy, history, economics,
        philosophy, security, cooking, medicine, electronics, psychology,
        sociology, environmental, linguistics, law
"""

import urllib.request
import urllib.parse
import json
import re
import html
import time
import sys
import hashlib
import os
import argparse
from collections import deque

API_URL = "http://aio-01:5000"
MAX_PAGES = 500
CRAWL_DELAY = 1.0
USER_AGENT = "fleet-scraper/2.0"

GROUPS = {
    "ai-providers": [
        {
            "name": "openrouter-docs",
            "start_urls": [
                "https://openrouter.ai/docs/",
                "https://openrouter.ai/docs/quickstart",
                "https://openrouter.ai/docs/api-reference",
                "https://openrouter.ai/docs/models",
            ],
            "allowed_prefix": "https://openrouter.ai/docs",
            "category": "docs-openrouter",
        },
        {
            "name": "anthropic-docs",
            "start_urls": [
                "https://docs.anthropic.com/en/docs/",
                "https://docs.anthropic.com/en/api/",
            ],
            "allowed_prefix": "https://docs.anthropic.com/en/",
            "category": "docs-anthropic",
        },
        {
            "name": "google-ai-docs",
            "start_urls": [
                "https://ai.google.dev/gemini-api/docs",
                "https://ai.google.dev/gemini-api/docs/models",
            ],
            "allowed_prefix": "https://ai.google.dev/gemini-api/",
            "category": "docs-google-ai",
        },
        {
            "name": "groq-docs",
            "start_urls": [
                "https://console.groq.com/docs/",
                "https://console.groq.com/docs/quickstart",
                "https://console.groq.com/docs/models",
            ],
            "allowed_prefix": "https://console.groq.com/docs",
            "category": "docs-groq",
        },
        {
            "name": "deepseek-docs",
            "start_urls": [
                "https://api-docs.deepseek.com/",
            ],
            "allowed_prefix": "https://api-docs.deepseek.com/",
            "category": "docs-deepseek",
        },
        {
            "name": "mistral-docs",
            "start_urls": [
                "https://docs.mistral.ai/",
                "https://docs.mistral.ai/getting-started/",
                "https://docs.mistral.ai/capabilities/",
                "https://docs.mistral.ai/api/",
            ],
            "allowed_prefix": "https://docs.mistral.ai/",
            "category": "docs-mistral",
        },
        {
            "name": "cohere-docs",
            "start_urls": [
                "https://docs.cohere.com/docs/",
                "https://docs.cohere.com/reference/",
            ],
            "allowed_prefix": "https://docs.cohere.com/",
            "category": "docs-cohere",
        },
        {
            "name": "nvidia-nim-docs",
            "start_urls": [
                "https://docs.api.nvidia.com/",
            ],
            "allowed_prefix": "https://docs.api.nvidia.com/",
            "category": "docs-nvidia-nim",
        },
        {
            "name": "voyage-docs",
            "start_urls": [
                "https://docs.voyageai.com/docs/",
                "https://docs.voyageai.com/reference/",
            ],
            "allowed_prefix": "https://docs.voyageai.com/",
            "category": "docs-voyage",
        },
        {
            "name": "jina-docs",
            "start_urls": [
                "https://docs.jina.ai/",
                "https://jina.ai/embeddings/",
                "https://jina.ai/reranker/",
            ],
            "allowed_prefix": "https://jina.ai/",
            "category": "docs-jina",
        },
        {
            "name": "cerebras-docs",
            "start_urls": [
                "https://inference-docs.cerebras.ai/",
            ],
            "allowed_prefix": "https://inference-docs.cerebras.ai/",
            "category": "docs-cerebras",
        },
        {
            "name": "huggingface-docs",
            "start_urls": [
                "https://huggingface.co/docs/hub/",
                "https://huggingface.co/docs/transformers/",
                "https://huggingface.co/docs/api-inference/",
            ],
            "allowed_prefix": "https://huggingface.co/docs/",
            "category": "docs-huggingface",
        },
    ],
    "math": [
        {
            "name": "mathworld",
            "start_urls": [
                "https://mathworld.wolfram.com/topics/Algebra.html",
                "https://mathworld.wolfram.com/topics/Analysis.html",
                "https://mathworld.wolfram.com/topics/Calculus.html",
                "https://mathworld.wolfram.com/topics/DiscreteMathematics.html",
                "https://mathworld.wolfram.com/topics/Geometry.html",
                "https://mathworld.wolfram.com/topics/NumberTheory.html",
                "https://mathworld.wolfram.com/topics/Probability.html",
                "https://mathworld.wolfram.com/topics/Statistics.html",
                "https://mathworld.wolfram.com/topics/Topology.html",
                "https://mathworld.wolfram.com/topics/LinearAlgebra.html",
            ],
            "allowed_prefix": "https://mathworld.wolfram.com/",
            "category": "wolfram-mathworld",
        },
        {
            "name": "libretexts-math",
            "start_urls": [
                "https://math.libretexts.org/Bookshelves",
                "https://math.libretexts.org/Bookshelves/Calculus",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra",
                "https://math.libretexts.org/Bookshelves/Differential_Equations",
                "https://math.libretexts.org/Bookshelves/Analysis",
                "https://math.libretexts.org/Bookshelves/Probability_and_Statistics",
            ],
            "allowed_prefix": "https://math.libretexts.org/",
            "category": "libretexts-math",
        },
        {
            "name": "brilliant-math",
            "start_urls": [
                "https://brilliant.org/wiki/algebra/",
                "https://brilliant.org/wiki/calculus/",
                "https://brilliant.org/wiki/geometry/",
                "https://brilliant.org/wiki/number-theory/",
                "https://brilliant.org/wiki/probability/",
                "https://brilliant.org/wiki/combinatorics/",
                "https://brilliant.org/wiki/linear-algebra/",
            ],
            "allowed_prefix": "https://brilliant.org/wiki/",
            "category": "brilliant-math",
        },
        {
            "name": "paul-math-notes",
            "start_urls": [
                "https://tutorial.math.lamar.edu/Classes/CalcI/CalcI.aspx",
                "https://tutorial.math.lamar.edu/Classes/CalcII/CalcII.aspx",
                "https://tutorial.math.lamar.edu/Classes/CalcIII/CalcIII.aspx",
                "https://tutorial.math.lamar.edu/Classes/DE/DE.aspx",
                "https://tutorial.math.lamar.edu/Classes/LinAlg/LinAlg.aspx",
            ],
            "allowed_prefix": "https://tutorial.math.lamar.edu/",
            "category": "lamar-math",
        },
    ],
    "physics": [
        {
            "name": "hyperphysics",
            "start_urls": [
                "http://hyperphysics.phy-astr.gsu.edu/hbase/hph.html",
                "http://hyperphysics.phy-astr.gsu.edu/hbase/hframe.html",
            ],
            "allowed_prefix": "http://hyperphysics.phy-astr.gsu.edu/hbase/",
            "category": "hyperphysics",
        },
        {
            "name": "libretexts-physics",
            "start_urls": [
                "https://phys.libretexts.org/Bookshelves",
                "https://phys.libretexts.org/Bookshelves/Classical_Mechanics",
                "https://phys.libretexts.org/Bookshelves/Electricity_and_Magnetism",
                "https://phys.libretexts.org/Bookshelves/Quantum_Mechanics",
                "https://phys.libretexts.org/Bookshelves/Thermodynamics_and_Statistical_Mechanics",
                "https://phys.libretexts.org/Bookshelves/Relativity",
                "https://phys.libretexts.org/Bookshelves/Nuclear_and_Particle_Physics",
            ],
            "allowed_prefix": "https://phys.libretexts.org/",
            "category": "libretexts-physics",
        },
        {
            "name": "feynman-lectures",
            "start_urls": [
                "https://www.feynmanlectures.caltech.edu/I_toc.html",
                "https://www.feynmanlectures.caltech.edu/II_toc.html",
                "https://www.feynmanlectures.caltech.edu/III_toc.html",
            ],
            "allowed_prefix": "https://www.feynmanlectures.caltech.edu/",
            "category": "feynman-lectures",
        },
        {
            "name": "physics-classroom",
            "start_urls": [
                "https://www.physicsclassroom.com/class",
            ],
            "allowed_prefix": "https://www.physicsclassroom.com/class",
            "category": "physics-classroom",
        },
        {
            "name": "brilliant-physics",
            "start_urls": [
                "https://brilliant.org/wiki/classical-mechanics/",
                "https://brilliant.org/wiki/electromagnetism/",
                "https://brilliant.org/wiki/quantum-mechanics/",
                "https://brilliant.org/wiki/thermodynamics/",
                "https://brilliant.org/wiki/special-relativity/",
                "https://brilliant.org/wiki/general-relativity/",
            ],
            "allowed_prefix": "https://brilliant.org/wiki/",
            "category": "brilliant-physics",
        },
    ],
    "chemistry": [
        {
            "name": "libretexts-chem",
            "start_urls": [
                "https://chem.libretexts.org/Bookshelves",
                "https://chem.libretexts.org/Bookshelves/General_Chemistry",
                "https://chem.libretexts.org/Bookshelves/Organic_Chemistry",
                "https://chem.libretexts.org/Bookshelves/Inorganic_Chemistry",
                "https://chem.libretexts.org/Bookshelves/Physical_and_Theoretical_Chemistry_Textbook_Maps",
                "https://chem.libretexts.org/Bookshelves/Biological_Chemistry",
                "https://chem.libretexts.org/Bookshelves/Analytical_Chemistry",
            ],
            "allowed_prefix": "https://chem.libretexts.org/",
            "category": "libretexts-chem",
        },
        {
            "name": "brilliant-chem",
            "start_urls": [
                "https://brilliant.org/wiki/chemistry/",
                "https://brilliant.org/wiki/organic-chemistry/",
                "https://brilliant.org/wiki/thermochemistry/",
            ],
            "allowed_prefix": "https://brilliant.org/wiki/",
            "category": "brilliant-chem",
        },
    ],
    "biology": [
        {
            "name": "libretexts-bio",
            "start_urls": [
                "https://bio.libretexts.org/Bookshelves",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology",
                "https://bio.libretexts.org/Bookshelves/Genetics",
                "https://bio.libretexts.org/Bookshelves/Microbiology",
                "https://bio.libretexts.org/Bookshelves/Ecology",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology",
                "https://bio.libretexts.org/Bookshelves/Evolutionary_Developmental_Biology",
            ],
            "allowed_prefix": "https://bio.libretexts.org/",
            "category": "libretexts-bio",
        },
        {
            "name": "nature-scitable",
            "start_urls": [
                "https://www.nature.com/scitable/topic/cell-biology-702/",
                "https://www.nature.com/scitable/topic/genetics-702/",
                "https://www.nature.com/scitable/topic/evolution-702/",
                "https://www.nature.com/scitable/topic/ecology-702/",
            ],
            "allowed_prefix": "https://www.nature.com/scitable/",
            "category": "nature-scitable",
        },
    ],
    "earth-science": [
        {
            "name": "libretexts-geo",
            "start_urls": [
                "https://geo.libretexts.org/Bookshelves",
                "https://geo.libretexts.org/Bookshelves/Geography_(Physical)",
                "https://geo.libretexts.org/Bookshelves/Geology",
                "https://geo.libretexts.org/Bookshelves/Oceanography",
                "https://geo.libretexts.org/Bookshelves/Meteorology_and_Climate_Science",
            ],
            "allowed_prefix": "https://geo.libretexts.org/",
            "category": "libretexts-geo",
        },
        {
            "name": "nasa-science",
            "start_urls": [
                "https://science.nasa.gov/earth/",
                "https://science.nasa.gov/solar-system/",
                "https://science.nasa.gov/astrophysics/",
                "https://science.nasa.gov/universe/",
            ],
            "allowed_prefix": "https://science.nasa.gov/",
            "category": "nasa-science",
        },
    ],
    "engineering": [
        {
            "name": "engineering-toolbox",
            "start_urls": [
                "https://www.engineeringtoolbox.com/",
            ],
            "allowed_prefix": "https://www.engineeringtoolbox.com/",
            "category": "engineering-toolbox",
        },
        {
            "name": "libretexts-eng",
            "start_urls": [
                "https://eng.libretexts.org/Bookshelves",
                "https://eng.libretexts.org/Bookshelves/Electrical_Engineering",
                "https://eng.libretexts.org/Bookshelves/Computer_Science",
                "https://eng.libretexts.org/Bookshelves/Materials_Science",
                "https://eng.libretexts.org/Bookshelves/Mechanical_Engineering",
            ],
            "allowed_prefix": "https://eng.libretexts.org/",
            "category": "libretexts-eng",
        },
    ],
    "computer-science": [
        {
            "name": "libretexts-cs",
            "start_urls": [
                "https://eng.libretexts.org/Bookshelves/Computer_Science",
                "https://eng.libretexts.org/Bookshelves/Computer_Science/Programming_Languages",
                "https://eng.libretexts.org/Bookshelves/Computer_Science/Algorithms",
                "https://eng.libretexts.org/Bookshelves/Computer_Science/Databases",
            ],
            "allowed_prefix": "https://eng.libretexts.org/Bookshelves/Computer_Science",
            "category": "libretexts-cs",
        },
        {
            "name": "geeksforgeeks-algo",
            "start_urls": [
                "https://www.geeksforgeeks.org/fundamentals-of-algorithms/",
                "https://www.geeksforgeeks.org/data-structures/",
                "https://www.geeksforgeeks.org/graph-data-structure-and-algorithms/",
                "https://www.geeksforgeeks.org/sorting-algorithms/",
            ],
            "allowed_prefix": "https://www.geeksforgeeks.org/",
            "category": "geeksforgeeks",
        },
        {
            "name": "brilliant-cs",
            "start_urls": [
                "https://brilliant.org/wiki/computer-science/",
                "https://brilliant.org/wiki/algorithm/",
                "https://brilliant.org/wiki/cryptography/",
            ],
            "allowed_prefix": "https://brilliant.org/wiki/",
            "category": "brilliant-cs",
        },
    ],
    "neuroscience": [
        {
            "name": "libretexts-neuro",
            "start_urls": [
                "https://med.libretexts.org/Bookshelves/Anatomy_and_Physiology",
                "https://bio.libretexts.org/Bookshelves/Neuroscience",
            ],
            "allowed_prefix": "https://med.libretexts.org/Bookshelves/",
            "category": "libretexts-neuro",
        },
        {
            "name": "neuroscience-online",
            "start_urls": [
                "https://nba.uth.tmc.edu/neuroscience/",
                "https://nba.uth.tmc.edu/neuroscience/toc.htm",
            ],
            "allowed_prefix": "https://nba.uth.tmc.edu/neuroscience/",
            "category": "neuroscience-online",
        },
        {
            "name": "brilliant-neuro",
            "start_urls": [
                "https://brilliant.org/wiki/neuroscience/",
                "https://brilliant.org/wiki/neural-networks/",
            ],
            "allowed_prefix": "https://brilliant.org/wiki/",
            "category": "brilliant-neuro",
        },
    ],
    "infra": [
        {
            "name": "systemd-docs",
            "start_urls": [
                "https://www.freedesktop.org/software/systemd/man/latest/",
                "https://systemd.io/",
            ],
            "allowed_prefix": "https://www.freedesktop.org/software/systemd/",
            "category": "systemd",
        },
        {
            "name": "gunicorn-docs",
            "start_urls": [
                "https://docs.gunicorn.org/en/stable/",
                "https://docs.gunicorn.org/en/stable/configure.html",
                "https://docs.gunicorn.org/en/stable/settings.html",
                "https://docs.gunicorn.org/en/stable/deploy.html",
            ],
            "allowed_prefix": "https://docs.gunicorn.org/en/stable/",
            "category": "gunicorn",
        },
        {
            "name": "flask-docs",
            "start_urls": [
                "https://flask.palletsprojects.com/en/stable/",
            ],
            "allowed_prefix": "https://flask.palletsprojects.com/en/stable/",
            "category": "flask",
        },
        {
            "name": "openssh-man",
            "start_urls": [
                "https://man.openbsd.org/ssh",
                "https://man.openbsd.org/sshd",
                "https://man.openbsd.org/ssh_config",
                "https://man.openbsd.org/sshd_config",
                "https://man.openbsd.org/ssh-keygen",
                "https://man.openbsd.org/ssh-agent",
                "https://man.openbsd.org/ssh-add",
                "https://man.openbsd.org/ssh-copy-id",
            ],
            "allowed_prefix": "https://man.openbsd.org/",
            "category": "openssh",
        },
        {
            "name": "nginx-docs",
            "start_urls": [
                "https://nginx.org/en/docs/",
            ],
            "allowed_prefix": "https://nginx.org/en/docs/",
            "category": "nginx-docs",
        },
    ],
    "dev": [
        {
            "name": "git-docs",
            "start_urls": [
                "https://git-scm.com/docs",
                "https://git-scm.com/book/en/v2",
            ],
            "allowed_prefix": "https://git-scm.com/",
            "category": "git",
        },
        {
            "name": "ansible-docs",
            "start_urls": [
                "https://docs.ansible.com/ansible/latest/getting_started/index.html",
                "https://docs.ansible.com/ansible/latest/playbook_guide/index.html",
                "https://docs.ansible.com/ansible/latest/inventory_guide/index.html",
                "https://docs.ansible.com/ansible/latest/module_plugin_guide/index.html",
            ],
            "allowed_prefix": "https://docs.ansible.com/ansible/latest/",
            "category": "ansible",
        },
        {
            "name": "tmux-wiki",
            "start_urls": [
                "https://github.com/tmux/tmux/wiki",
                "https://github.com/tmux/tmux/wiki/Getting-Started",
                "https://github.com/tmux/tmux/wiki/FAQ",
            ],
            "allowed_prefix": "https://github.com/tmux/tmux/wiki",
            "category": "tmux",
        },
    ],
    "python": [
        {
            "name": "python-docs",
            "start_urls": [
                "https://docs.python.org/3/library/index.html",
                "https://docs.python.org/3/reference/index.html",
                "https://docs.python.org/3/howto/index.html",
            ],
            "allowed_prefix": "https://docs.python.org/3/",
            "category": "docs-python",
        },
        {
            "name": "fastapi-docs",
            "start_urls": [
                "https://fastapi.tiangolo.com/",
                "https://fastapi.tiangolo.com/tutorial/",
                "https://fastapi.tiangolo.com/advanced/",
            ],
            "allowed_prefix": "https://fastapi.tiangolo.com/",
            "category": "fastapi",
        },
        {
            "name": "sentence-transformers",
            "start_urls": [
                "https://www.sbert.net/docs/",
                "https://www.sbert.net/docs/sentence_transformer/pretrained_models.html",
                "https://www.sbert.net/docs/package_reference/sentence_transformer/SentenceTransformer.html",
            ],
            "allowed_prefix": "https://www.sbert.net/",
            "category": "sentence-transformers",
        },
        {
            "name": "uvicorn-docs",
            "start_urls": [
                "https://www.uvicorn.org/",
                "https://www.uvicorn.org/deployment/",
                "https://www.uvicorn.org/settings/",
            ],
            "allowed_prefix": "https://www.uvicorn.org/",
            "category": "uvicorn",
        },
    ],
    "containers": [
        {
            "name": "podman-docs",
            "start_urls": [
                "https://docs.podman.io/en/stable/",
                "https://docs.podman.io/en/stable/Commands.html",
            ],
            "allowed_prefix": "https://docs.podman.io/en/stable/",
            "category": "podman",
        },
        {
            "name": "docker-docs",
            "start_urls": [
                "https://docs.docker.com/get-started/",
                "https://docs.docker.com/engine/",
                "https://docs.docker.com/compose/",
                "https://docs.docker.com/reference/dockerfile/",
            ],
            "allowed_prefix": "https://docs.docker.com/",
            "category": "docker-docs",
        },
        {
            "name": "kubernetes-docs",
            "start_urls": [
                "https://kubernetes.io/docs/concepts/",
                "https://kubernetes.io/docs/tasks/",
                "https://kubernetes.io/docs/reference/",
            ],
            "allowed_prefix": "https://kubernetes.io/docs/",
            "category": "kubernetes",
        },
    ],
    "databases": [
        {
            "name": "pgvector",
            "start_urls": [
                "https://github.com/pgvector/pgvector",
                "https://github.com/pgvector/pgvector/blob/master/README.md",
            ],
            "allowed_prefix": "https://github.com/pgvector/",
            "category": "pgvector",
        },
        {
            "name": "postgresql-docs",
            "start_urls": [
                "https://www.postgresql.org/docs/current/",
                "https://www.postgresql.org/docs/current/tutorial.html",
                "https://www.postgresql.org/docs/current/sql.html",
                "https://www.postgresql.org/docs/current/admin.html",
            ],
            "allowed_prefix": "https://www.postgresql.org/docs/current/",
            "category": "postgresql",
        },
        {
            "name": "redis-docs",
            "start_urls": [
                "https://redis.io/docs/latest/",
                "https://redis.io/docs/latest/commands/",
                "https://redis.io/docs/latest/operate/",
            ],
            "allowed_prefix": "https://redis.io/docs/",
            "category": "redis",
        },
        {
            "name": "orientdb-docs",
            "start_urls": [
                "https://orientdb.org/docs/3.2.x/",
            ],
            "allowed_prefix": "https://orientdb.org/docs/",
            "category": "orientdb",
        },
    ],
    "networking": [
        {
            "name": "openssh-cookbook",
            "start_urls": [
                "https://en.wikibooks.org/wiki/OpenSSH",
                "https://en.wikibooks.org/wiki/OpenSSH/Cookbook",
            ],
            "allowed_prefix": "https://en.wikibooks.org/wiki/OpenSSH",
            "category": "openssh",
        },
        {
            "name": "redis-sentinel",
            "start_urls": [
                "https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/",
            ],
            "allowed_prefix": "https://redis.io/docs/latest/operate/",
            "category": "redis-sentinel",
        },
    ],
    "linux": [
        {
            "name": "fedora-docs",
            "start_urls": [
                "https://docs.fedoraproject.org/en-US/fedora/latest/",
                "https://docs.fedoraproject.org/en-US/quick-docs/",
            ],
            "allowed_prefix": "https://docs.fedoraproject.org/en-US/",
            "category": "fedora",
        },
        {
            "name": "fedora-wiki",
            "start_urls": [
                "https://fedoraproject.org/wiki/Fedora_Project_Wiki",
            ],
            "allowed_prefix": "https://fedoraproject.org/wiki/",
            "category": "fedora-wiki",
        },
    ],
    "embedded": [
        {
            "name": "raspberrypi-docs",
            "start_urls": [
                "https://www.raspberrypi.com/documentation/",
                "https://www.raspberrypi.com/documentation/computers/",
                "https://www.raspberrypi.com/documentation/computers/configuration.html",
                "https://www.raspberrypi.com/documentation/computers/remote-access.html",
                "https://www.raspberrypi.com/documentation/computers/os.html",
            ],
            "allowed_prefix": "https://www.raspberrypi.com/documentation/",
            "category": "raspberrypi",
        },
    ],
    "statistics": [
        {
            "name": "libretexts-stats",
            "start_urls": [
                "https://stats.libretexts.org/Bookshelves",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics",
                "https://stats.libretexts.org/Bookshelves/Probability_Theory",
                "https://stats.libretexts.org/Bookshelves/Applied_Statistics",
            ],
            "allowed_prefix": "https://stats.libretexts.org/",
            "category": "libretexts-stats",
        },
        {
            "name": "nist-handbook",
            "start_urls": [
                "https://www.itl.nist.gov/div898/handbook/",
                "https://www.itl.nist.gov/div898/handbook/eda/eda.htm",
                "https://www.itl.nist.gov/div898/handbook/prc/prc.htm",
                "https://www.itl.nist.gov/div898/handbook/mpc/mpc.htm",
                "https://www.itl.nist.gov/div898/handbook/pmd/pmd.htm",
            ],
            "allowed_prefix": "https://www.itl.nist.gov/div898/handbook/",
            "category": "nist-statistics",
        },
        {
            "name": "stat-trek",
            "start_urls": [
                "https://stattrek.com/statistics/dictionary",
                "https://stattrek.com/probability/probability",
                "https://stattrek.com/hypothesis-test/hypothesis-testing",
                "https://stattrek.com/regression/regression",
            ],
            "allowed_prefix": "https://stattrek.com/",
            "category": "stattrek",
        },
    ],
    "astronomy": [
        {
            "name": "libretexts-astro",
            "start_urls": [
                "https://phys.libretexts.org/Bookshelves/Astronomy__Cosmology",
                "https://phys.libretexts.org/Bookshelves/Astronomy__Cosmology/Astronomy_(Fraknoi_et_al.)",
            ],
            "allowed_prefix": "https://phys.libretexts.org/Bookshelves/Astronomy",
            "category": "libretexts-astronomy",
        },
        {
            "name": "nasa-solar-system",
            "start_urls": [
                "https://solarsystem.nasa.gov/planets/overview/",
                "https://solarsystem.nasa.gov/moons/overview/",
                "https://solarsystem.nasa.gov/asteroids-comets-and-meteors/overview/",
            ],
            "allowed_prefix": "https://solarsystem.nasa.gov/",
            "category": "nasa-solar-system",
        },
        {
            "name": "simbad-astro",
            "start_urls": [
                "https://astronomy.swin.edu.au/cosmos/",
            ],
            "allowed_prefix": "https://astronomy.swin.edu.au/cosmos/",
            "category": "swin-cosmos",
        },
    ],
    "history": [
        {
            "name": "libretexts-history",
            "start_urls": [
                "https://human.libretexts.org/Bookshelves/History",
                "https://human.libretexts.org/Bookshelves/History/World_History",
                "https://human.libretexts.org/Bookshelves/History/United_States_History",
            ],
            "allowed_prefix": "https://human.libretexts.org/Bookshelves/History",
            "category": "libretexts-history",
        },
        {
            "name": "ehnet-encyclopedia",
            "start_urls": [
                "https://eh.net/encyclopedia/",
            ],
            "allowed_prefix": "https://eh.net/encyclopedia/",
            "category": "economic-history",
        },
        {
            "name": "ancient-history",
            "start_urls": [
                "https://www.worldhistory.org/article/",
                "https://www.worldhistory.org/collection/",
            ],
            "allowed_prefix": "https://www.worldhistory.org/",
            "category": "world-history",
        },
    ],
    "economics": [
        {
            "name": "libretexts-econ",
            "start_urls": [
                "https://socialsci.libretexts.org/Bookshelves/Economics",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Principles_of_Economics",
            ],
            "allowed_prefix": "https://socialsci.libretexts.org/Bookshelves/Economics",
            "category": "libretexts-economics",
        },
        {
            "name": "econlib",
            "start_urls": [
                "https://www.econlib.org/library/Enc/",
            ],
            "allowed_prefix": "https://www.econlib.org/library/",
            "category": "econlib",
        },
        {
            "name": "imf-glossary",
            "start_urls": [
                "https://www.imf.org/en/About/Factsheets",
            ],
            "allowed_prefix": "https://www.imf.org/en/About/Factsheets",
            "category": "imf-factsheets",
        },
    ],
    "philosophy": [
        {
            "name": "sep-expanded",
            "start_urls": [
                "https://plato.stanford.edu/contents.html",
                "https://plato.stanford.edu/entries/epistemology/",
                "https://plato.stanford.edu/entries/ethics-virtue/",
                "https://plato.stanford.edu/entries/logic-classical/",
                "https://plato.stanford.edu/entries/metaphysics/",
                "https://plato.stanford.edu/entries/philosophy-mind/",
                "https://plato.stanford.edu/entries/political-philosophy/",
                "https://plato.stanford.edu/entries/aesthetics/",
            ],
            "allowed_prefix": "https://plato.stanford.edu/entries/",
            "category": "sep",
        },
        {
            "name": "iep-expanded",
            "start_urls": [
                "https://iep.utm.edu/",
            ],
            "allowed_prefix": "https://iep.utm.edu/",
            "category": "iep",
        },
        {
            "name": "libretexts-philosophy",
            "start_urls": [
                "https://human.libretexts.org/Bookshelves/Philosophy",
            ],
            "allowed_prefix": "https://human.libretexts.org/Bookshelves/Philosophy",
            "category": "libretexts-philosophy",
        },
    ],
    "security": [
        {
            "name": "owasp-expanded",
            "start_urls": [
                "https://owasp.org/www-project-web-security-testing-guide/latest/",
                "https://owasp.org/www-project-application-security-verification-standard/",
                "https://owasp.org/www-project-top-ten/",
                "https://owasp.org/www-community/attacks/",
                "https://owasp.org/www-community/vulnerabilities/",
            ],
            "allowed_prefix": "https://owasp.org/",
            "category": "owasp",
        },
        {
            "name": "nist-csf",
            "start_urls": [
                "https://csrc.nist.gov/publications/sp800",
                "https://csrc.nist.gov/glossary",
            ],
            "allowed_prefix": "https://csrc.nist.gov/",
            "category": "nist-security",
        },
        {
            "name": "cwe-mitre",
            "start_urls": [
                "https://cwe.mitre.org/data/definitions/",
            ],
            "allowed_prefix": "https://cwe.mitre.org/",
            "category": "cwe-mitre",
        },
    ],
    "cooking": [
        {
            "name": "serious-eats",
            "start_urls": [
                "https://www.seriouseats.com/all-recipes-702",
                "https://www.seriouseats.com/food-science-702",
                "https://www.seriouseats.com/technique-702",
                "https://www.seriouseats.com/equipment-702",
            ],
            "allowed_prefix": "https://www.seriouseats.com/",
            "category": "serious-eats",
        },
        {
            "name": "cooking-for-engineers",
            "start_urls": [
                "https://www.cookingforengineers.com/",
            ],
            "allowed_prefix": "https://www.cookingforengineers.com/",
            "category": "cooking-for-engineers",
        },
        {
            "name": "food-science",
            "start_urls": [
                "https://www.scienceofcooking.com/",
            ],
            "allowed_prefix": "https://www.scienceofcooking.com/",
            "category": "science-of-cooking",
        },
    ],
    "medicine": [
        {
            "name": "medlineplus",
            "start_urls": [
                "https://medlineplus.gov/healthtopics.html",
                "https://medlineplus.gov/encyclopedia.html",
                "https://medlineplus.gov/druginfo/meds/",
            ],
            "allowed_prefix": "https://medlineplus.gov/",
            "category": "medlineplus",
        },
        {
            "name": "libretexts-medicine",
            "start_urls": [
                "https://med.libretexts.org/Bookshelves",
                "https://med.libretexts.org/Bookshelves/Anatomy_and_Physiology",
                "https://med.libretexts.org/Bookshelves/Pharmacology_and_Neuroscience",
                "https://med.libretexts.org/Bookshelves/Nursing",
            ],
            "allowed_prefix": "https://med.libretexts.org/",
            "category": "libretexts-medicine",
        },
        {
            "name": "cdc-topics",
            "start_urls": [
                "https://www.cdc.gov/health-topics.html",
            ],
            "allowed_prefix": "https://www.cdc.gov/",
            "category": "cdc",
        },
    ],
    "electronics": [
        {
            "name": "allaboutcircuits",
            "start_urls": [
                "https://www.allaboutcircuits.com/textbook/",
                "https://www.allaboutcircuits.com/textbook/direct-current/",
                "https://www.allaboutcircuits.com/textbook/alternating-current/",
                "https://www.allaboutcircuits.com/textbook/digital/",
                "https://www.allaboutcircuits.com/textbook/semiconductors/",
            ],
            "allowed_prefix": "https://www.allaboutcircuits.com/textbook/",
            "category": "allaboutcircuits",
        },
        {
            "name": "electronics-tutorials",
            "start_urls": [
                "https://www.electronics-tutorials.ws/",
            ],
            "allowed_prefix": "https://www.electronics-tutorials.ws/",
            "category": "electronics-tutorials",
        },
        {
            "name": "libretexts-ee",
            "start_urls": [
                "https://eng.libretexts.org/Bookshelves/Electrical_Engineering",
            ],
            "allowed_prefix": "https://eng.libretexts.org/Bookshelves/Electrical_Engineering",
            "category": "libretexts-ee",
        },
    ],
    "psychology": [
        {
            "name": "libretexts-psychology",
            "start_urls": [
                "https://socialsci.libretexts.org/Bookshelves/Psychology",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Cognitive_Psychology",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Developmental_Psychology",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Biological_Psychology",
            ],
            "allowed_prefix": "https://socialsci.libretexts.org/Bookshelves/Psychology",
            "category": "libretexts-psychology",
        },
        {
            "name": "simplypsychology",
            "start_urls": [
                "https://www.simplypsychology.org/",
            ],
            "allowed_prefix": "https://www.simplypsychology.org/",
            "category": "simplypsychology",
        },
    ],
    "sociology": [
        {
            "name": "libretexts-sociology",
            "start_urls": [
                "https://socialsci.libretexts.org/Bookshelves/Sociology",
            ],
            "allowed_prefix": "https://socialsci.libretexts.org/Bookshelves/Sociology",
            "category": "libretexts-sociology",
        },
    ],
    "environmental": [
        {
            "name": "libretexts-environmental",
            "start_urls": [
                "https://bio.libretexts.org/Bookshelves/Ecology",
                "https://geo.libretexts.org/Bookshelves/Meteorology_and_Climate_Science",
            ],
            "allowed_prefix": "https://bio.libretexts.org/Bookshelves/Ecology",
            "category": "libretexts-ecology",
        },
        {
            "name": "epa-topics",
            "start_urls": [
                "https://www.epa.gov/environmental-topics",
            ],
            "allowed_prefix": "https://www.epa.gov/",
            "category": "epa",
        },
    ],
    "linguistics": [
        {
            "name": "libretexts-linguistics",
            "start_urls": [
                "https://socialsci.libretexts.org/Bookshelves/Linguistics",
            ],
            "allowed_prefix": "https://socialsci.libretexts.org/Bookshelves/Linguistics",
            "category": "libretexts-linguistics",
        },
        {
            "name": "glottopedia",
            "start_urls": [
                "https://glottopedia.org/wiki/Main_Page",
            ],
            "allowed_prefix": "https://glottopedia.org/wiki/",
            "category": "glottopedia",
        },
    ],
    "law": [
        {
            "name": "cornell-law-expanded",
            "start_urls": [
                "https://www.law.cornell.edu/wex/",
                "https://www.law.cornell.edu/constitution/",
                "https://www.law.cornell.edu/ucc/",
            ],
            "allowed_prefix": "https://www.law.cornell.edu/",
            "category": "cornell-law",
        },
        {
            "name": "libretexts-law",
            "start_urls": [
                "https://biz.libretexts.org/Bookshelves/Law",
            ],
            "allowed_prefix": "https://biz.libretexts.org/Bookshelves/Law",
            "category": "libretexts-law",
        },
    ],
}


def fetch_page(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            ct = resp.headers.get("Content-Type", "")
            if "text/html" not in ct and "text/plain" not in ct:
                return None
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  FETCH FAIL: {url} — {e}")
        return None


def extract_title(raw_html):
    m = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.DOTALL | re.IGNORECASE)
    return html.unescape(m.group(1).strip()) if m else "Untitled"


def extract_text(raw_html):
    text = re.sub(r"<script[^>]*>.*?</script>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<nav[^>]*>.*?</nav>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<header[^>]*>.*?</header>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_links(raw_html, base_url, allowed_prefix):
    links = []
    for m in re.finditer(r'href=["\']([^"\']+)["\']', raw_html, re.IGNORECASE):
        href = m.group(1)
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        full = urllib.parse.urljoin(base_url, href).split("#")[0].split("?")[0]
        if full.startswith(allowed_prefix):
            links.append(full)
    return links


def store_page(url, title, content, category, source, api_url, output_dir=None):
    if output_dir:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        cat_dir = os.path.join(output_dir, category)
        os.makedirs(cat_dir, exist_ok=True)
        fpath = os.path.join(cat_dir, f"{url_hash}.json")
        if os.path.exists(fpath):
            return True
        try:
            with open(fpath, "w") as f:
                json.dump({
                    "url": url,
                    "title": title,
                    "category": category,
                    "content": f"{title}\n\n{content}",
                    "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }, f)
            return True
        except Exception as e:
            print(f"  FILE SAVE FAIL {url}: {e}")
            return False

    data = json.dumps({
        "documents": [{
            "url": url,
            "category": category,
            "content": f"{title}\n\n{content}",
        }],
        "skip_embeddings": True,
    }).encode()
    req = urllib.request.Request(
        f"{api_url}/pipeline/process", data=data,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read())
        return result.get("success", False)
    except Exception as e:
        print(f"  STORE FAIL {url}: {e}")
        return False


def crawl_site(site_config, api_url, max_pages, delay=1.0, output_dir=None):
    name = site_config["name"]
    prefix = site_config["allowed_prefix"]
    category = site_config["category"]

    queue = deque(site_config["start_urls"])
    visited = set()
    stored = 0

    mode = f"files → {output_dir}" if output_dir else f"API → {api_url}"
    print(f"\n{'='*60}")
    print(f"Crawling: {name} (category: {category})")
    print(f"Prefix:   {prefix}")
    print(f"Max:      {max_pages} pages | Mode: {mode}")
    print(f"{'='*60}")

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        raw = fetch_page(url)
        if not raw:
            continue

        title = extract_title(raw)
        text = extract_text(raw)

        if len(text) < 100:
            continue

        if store_page(url, title, text, category, name, api_url, output_dir):
            stored += 1
            if stored % 10 == 0 or stored < 5:
                print(f"  [{stored}/{len(visited)}] {title[:60]} ({len(text)} chars)")

        for link in extract_links(raw, url, prefix):
            if link not in visited:
                queue.append(link)

        time.sleep(delay)

    print(f"  DONE: {name} — {stored} stored, {len(visited)} visited")
    return stored


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", required=True, help=f"Site group: {', '.join(GROUPS.keys())}")
    parser.add_argument("--api", default=API_URL)
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES)
    parser.add_argument("--delay", type=float, default=CRAWL_DELAY)
    parser.add_argument("--output-dir", default=None,
                        help="Save JSON files locally instead of POSTing to API")
    args = parser.parse_args()

    crawl_delay = args.delay

    if args.group not in GROUPS:
        print(f"Unknown group: {args.group}")
        print(f"Available: {', '.join(GROUPS.keys())}")
        sys.exit(1)

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    sites = GROUPS[args.group]
    total = 0
    for site in sites:
        total += crawl_site(site, args.api, args.max_pages, crawl_delay, args.output_dir)

    print(f"\n{'='*60}")
    print(f"GROUP {args.group} COMPLETE: {total} pages stored")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
