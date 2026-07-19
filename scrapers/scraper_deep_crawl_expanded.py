#!/usr/bin/env python3
"""
Deep recursive Wikipedia crawler. Given seed URLs, follows internal links
to depth 2, scraping hundreds of pages per topic instead of 8-15.

Usage:
  python3 scraper_deep_crawl.py <topic_key>

Topics: quantum, strings, biology, math, physics, chemistry, ee, cs,
        philosophy, economics, medicine, engineering, psychology, linguistics,
        security, networking, astronomy, ecology, neuroscience, robotics,
        thermodynamics, optics, genetics, immunology, virology, evolution,
        pharmacology, organic-chem, materials-science, fluid-dynamics,
        relativity, particle-physics, nuclear, semiconductors, algorithms,
        databases, distributed-systems, operating-systems, compilers,
        cryptography, information-theory, ai-ml, data-science, statistics
"""
import re, time, html as html_mod, os, sys, hashlib, json, logging
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote, quote

try:
    from scraper_base import BaseScraper
except ImportError:
    sys.path.insert(0, os.path.expanduser("~/scrapers"))
    from scraper_base import BaseScraper


SKIP_PREFIXES = (
    '/wiki/File:', '/wiki/Template:', '/wiki/Category:', '/wiki/Help:',
    '/wiki/Wikipedia:', '/wiki/Special:', '/wiki/Talk:', '/wiki/User:',
    '/wiki/Portal:', '/wiki/Draft:', '/wiki/Module:', '/wiki/MediaWiki:',
    '/wiki/Main_Page', '/wiki/Book:', '/wiki/TimedText:', '/wiki/MOS:',
)

SKIP_PATTERNS = re.compile(
    r'(disambiguation|identifier|\.jpg|\.png|\.svg|\.gif|\.pdf|\.ogg|action=|oldid=|printable=|#|%23)',
    re.IGNORECASE
)

SEEDS = {
    "quantum": {
        "category": "deep-quantum",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Quantum_mechanics",
            "https://en.wikipedia.org/wiki/Quantum_field_theory",
            "https://en.wikipedia.org/wiki/Quantum_electrodynamics",
            "https://en.wikipedia.org/wiki/Quantum_chromodynamics",
            "https://en.wikipedia.org/wiki/Quantum_computing",
            "https://en.wikipedia.org/wiki/Quantum_entanglement",
            "https://en.wikipedia.org/wiki/Quantum_optics",
            "https://en.wikipedia.org/wiki/Quantum_information",
        ],
    },
    "strings": {
        "category": "deep-strings",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/String_theory",
            "https://en.wikipedia.org/wiki/M-theory",
            "https://en.wikipedia.org/wiki/Supersymmetry",
            "https://en.wikipedia.org/wiki/AdS/CFT_correspondence",
            "https://en.wikipedia.org/wiki/Quantum_gravity",
            "https://en.wikipedia.org/wiki/Theory_of_everything",
        ],
    },
    "biology": {
        "category": "deep-biology",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Biology",
            "https://en.wikipedia.org/wiki/Cell_(biology)",
            "https://en.wikipedia.org/wiki/Genetics",
            "https://en.wikipedia.org/wiki/Evolution",
            "https://en.wikipedia.org/wiki/Molecular_biology",
            "https://en.wikipedia.org/wiki/Immune_system",
            "https://en.wikipedia.org/wiki/Ecology",
            "https://en.wikipedia.org/wiki/Microbiology",
        ],
    },
    "math": {
        "category": "deep-math",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Mathematics",
            "https://en.wikipedia.org/wiki/Linear_algebra",
            "https://en.wikipedia.org/wiki/Calculus",
            "https://en.wikipedia.org/wiki/Statistics",
            "https://en.wikipedia.org/wiki/Probability_theory",
            "https://en.wikipedia.org/wiki/Number_theory",
            "https://en.wikipedia.org/wiki/Topology",
            "https://en.wikipedia.org/wiki/Abstract_algebra",
        ],
    },
    "physics": {
        "category": "deep-physics",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Physics",
            "https://en.wikipedia.org/wiki/Classical_mechanics",
            "https://en.wikipedia.org/wiki/Electromagnetism",
            "https://en.wikipedia.org/wiki/Thermodynamics",
            "https://en.wikipedia.org/wiki/Optics",
            "https://en.wikipedia.org/wiki/Nuclear_physics",
            "https://en.wikipedia.org/wiki/Particle_physics",
            "https://en.wikipedia.org/wiki/Condensed_matter_physics",
        ],
    },
    "chemistry": {
        "category": "deep-chemistry",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Chemistry",
            "https://en.wikipedia.org/wiki/Organic_chemistry",
            "https://en.wikipedia.org/wiki/Biochemistry",
            "https://en.wikipedia.org/wiki/Physical_chemistry",
            "https://en.wikipedia.org/wiki/Electrochemistry",
            "https://en.wikipedia.org/wiki/Materials_science",
        ],
    },
    "ee": {
        "category": "deep-ee",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Electrical_engineering",
            "https://en.wikipedia.org/wiki/Digital_electronics",
            "https://en.wikipedia.org/wiki/Signal_processing",
            "https://en.wikipedia.org/wiki/Control_theory",
            "https://en.wikipedia.org/wiki/Semiconductor_device",
            "https://en.wikipedia.org/wiki/Embedded_system",
        ],
    },
    "cs": {
        "category": "deep-cs",
        "max_pages": 2000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Computer_science",
            "https://en.wikipedia.org/wiki/Algorithm",
            "https://en.wikipedia.org/wiki/Data_structure",
            "https://en.wikipedia.org/wiki/Operating_system",
            "https://en.wikipedia.org/wiki/Compiler",
            "https://en.wikipedia.org/wiki/Distributed_computing",
            "https://en.wikipedia.org/wiki/Database",
            "https://en.wikipedia.org/wiki/Computational_complexity_theory",
        ],
    },
    "ai-ml": {
        "category": "deep-ai-ml",
        "max_pages": 2000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "https://en.wikipedia.org/wiki/Machine_learning",
            "https://en.wikipedia.org/wiki/Deep_learning",
            "https://en.wikipedia.org/wiki/Natural_language_processing",
            "https://en.wikipedia.org/wiki/Computer_vision",
            "https://en.wikipedia.org/wiki/Reinforcement_learning",
            "https://en.wikipedia.org/wiki/Large_language_model",
            "https://en.wikipedia.org/wiki/Generative_artificial_intelligence",
        ],
    },
    "philosophy": {
        "category": "deep-philosophy",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Philosophy",
            "https://en.wikipedia.org/wiki/Epistemology",
            "https://en.wikipedia.org/wiki/Metaphysics",
            "https://en.wikipedia.org/wiki/Ethics",
            "https://en.wikipedia.org/wiki/Logic",
            "https://en.wikipedia.org/wiki/Philosophy_of_mind",
        ],
    },
    "economics": {
        "category": "deep-economics",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Economics",
            "https://en.wikipedia.org/wiki/Microeconomics",
            "https://en.wikipedia.org/wiki/Macroeconomics",
            "https://en.wikipedia.org/wiki/Game_theory",
            "https://en.wikipedia.org/wiki/Behavioral_economics",
            "https://en.wikipedia.org/wiki/Finance",
        ],
    },
    "medicine": {
        "category": "deep-medicine",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Medicine",
            "https://en.wikipedia.org/wiki/Pharmacology",
            "https://en.wikipedia.org/wiki/Epidemiology",
            "https://en.wikipedia.org/wiki/Pathology",
            "https://en.wikipedia.org/wiki/Surgery",
            "https://en.wikipedia.org/wiki/Psychiatry",
            "https://en.wikipedia.org/wiki/Immunology",
            "https://en.wikipedia.org/wiki/Neurology",
        ],
    },
    "engineering": {
        "category": "deep-engineering",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Engineering",
            "https://en.wikipedia.org/wiki/Mechanical_engineering",
            "https://en.wikipedia.org/wiki/Civil_engineering",
            "https://en.wikipedia.org/wiki/Aerospace_engineering",
            "https://en.wikipedia.org/wiki/Chemical_engineering",
            "https://en.wikipedia.org/wiki/Robotics",
        ],
    },
    "psychology": {
        "category": "deep-psychology",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Psychology",
            "https://en.wikipedia.org/wiki/Cognitive_psychology",
            "https://en.wikipedia.org/wiki/Neuroscience",
            "https://en.wikipedia.org/wiki/Developmental_psychology",
            "https://en.wikipedia.org/wiki/Social_psychology",
            "https://en.wikipedia.org/wiki/Behaviorism",
        ],
    },
    "linguistics": {
        "category": "deep-linguistics",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Linguistics",
            "https://en.wikipedia.org/wiki/Natural_language_processing",
            "https://en.wikipedia.org/wiki/Phonology",
            "https://en.wikipedia.org/wiki/Syntax",
            "https://en.wikipedia.org/wiki/Semantics",
        ],
    },
    "security": {
        "category": "deep-security",
        "max_pages": 2000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Computer_security",
            "https://en.wikipedia.org/wiki/Cryptography",
            "https://en.wikipedia.org/wiki/Network_security",
            "https://en.wikipedia.org/wiki/Information_security",
            "https://en.wikipedia.org/wiki/Malware",
            "https://en.wikipedia.org/wiki/Vulnerability_(computing)",
        ],
    },
    "networking": {
        "category": "deep-networking",
        "max_pages": 2000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Computer_network",
            "https://en.wikipedia.org/wiki/Internet_protocol_suite",
            "https://en.wikipedia.org/wiki/Routing",
            "https://en.wikipedia.org/wiki/Domain_Name_System",
            "https://en.wikipedia.org/wiki/Transport_Layer_Security",
            "https://en.wikipedia.org/wiki/Software-defined_networking",
        ],
    },
    "astronomy": {
        "category": "deep-astronomy",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Astronomy",
            "https://en.wikipedia.org/wiki/Astrophysics",
            "https://en.wikipedia.org/wiki/Cosmology",
            "https://en.wikipedia.org/wiki/Solar_System",
            "https://en.wikipedia.org/wiki/Galaxy",
            "https://en.wikipedia.org/wiki/Black_hole",
        ],
    },
    "neuroscience": {
        "category": "deep-neuroscience",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Neuroscience",
            "https://en.wikipedia.org/wiki/Neuron",
            "https://en.wikipedia.org/wiki/Human_brain",
            "https://en.wikipedia.org/wiki/Cognitive_neuroscience",
            "https://en.wikipedia.org/wiki/Neuroplasticity",
            "https://en.wikipedia.org/wiki/Connectome",
        ],
    },
    "ecology": {
        "category": "deep-ecology",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Ecology",
            "https://en.wikipedia.org/wiki/Ecosystem",
            "https://en.wikipedia.org/wiki/Climate_change",
            "https://en.wikipedia.org/wiki/Biodiversity",
            "https://en.wikipedia.org/wiki/Conservation_biology",
        ],
    },
    "data-science": {
        "category": "deep-data-science",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Data_science",
            "https://en.wikipedia.org/wiki/Big_data",
            "https://en.wikipedia.org/wiki/Data_mining",
            "https://en.wikipedia.org/wiki/Statistical_learning_theory",
            "https://en.wikipedia.org/wiki/Bayesian_statistics",
            "https://en.wikipedia.org/wiki/Time_series",
        ],
    },
    "relativity": {
        "category": "deep-relativity",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/General_relativity",
            "https://en.wikipedia.org/wiki/Special_relativity",
            "https://en.wikipedia.org/wiki/Spacetime",
            "https://en.wikipedia.org/wiki/Gravitational_wave",
            "https://en.wikipedia.org/wiki/Black_hole",
        ],
    },
    "genetics": {
        "category": "deep-genetics",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Genetics",
            "https://en.wikipedia.org/wiki/Genomics",
            "https://en.wikipedia.org/wiki/CRISPR_gene_editing",
            "https://en.wikipedia.org/wiki/Epigenetics",
            "https://en.wikipedia.org/wiki/Human_Genome_Project",
            "https://en.wikipedia.org/wiki/Genetic_engineering",
        ],
    },
    "information-theory": {
        "category": "deep-info-theory",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Information_theory",
            "https://en.wikipedia.org/wiki/Entropy_(information_theory)",
            "https://en.wikipedia.org/wiki/Coding_theory",
            "https://en.wikipedia.org/wiki/Data_compression",
            "https://en.wikipedia.org/wiki/Error_detection_and_correction",
        ],
    },
    "cryptography": {
        "category": "deep-crypto",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Cryptography",
            "https://en.wikipedia.org/wiki/Public-key_cryptography",
            "https://en.wikipedia.org/wiki/Symmetric-key_algorithm",
            "https://en.wikipedia.org/wiki/Hash_function",
            "https://en.wikipedia.org/wiki/Post-quantum_cryptography",
        ],
    },
    "patents": {
        "category": "deep-patents",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Patent",
            "https://en.wikipedia.org/wiki/United_States_Patent_and_Trademark_Office",
            "https://en.wikipedia.org/wiki/Intellectual_property",
            "https://en.wikipedia.org/wiki/Patent_law_of_the_United_States",
            "https://en.wikipedia.org/wiki/Software_patent",
            "https://en.wikipedia.org/wiki/Smartphone_patent_wars",
            "https://en.wikipedia.org/wiki/Patent_Cooperation_Treaty",
        ],
    },
    "history": {
        "category": "deep-history",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/History_of_science",
            "https://en.wikipedia.org/wiki/History_of_technology",
            "https://en.wikipedia.org/wiki/Industrial_Revolution",
            "https://en.wikipedia.org/wiki/Scientific_Revolution",
            "https://en.wikipedia.org/wiki/History_of_computing",
            "https://en.wikipedia.org/wiki/History_of_the_Internet",
            "https://en.wikipedia.org/wiki/Space_exploration",
            "https://en.wikipedia.org/wiki/History_of_medicine",
        ],
    },
    "programming": {
        "category": "deep-programming",
        "max_pages": 2000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Programming_language",
            "https://en.wikipedia.org/wiki/Software_engineering",
            "https://en.wikipedia.org/wiki/Software_design_pattern",
            "https://en.wikipedia.org/wiki/Version_control",
            "https://en.wikipedia.org/wiki/DevOps",
            "https://en.wikipedia.org/wiki/Agile_software_development",
            "https://en.wikipedia.org/wiki/Open-source_software",
            "https://en.wikipedia.org/wiki/Linux",
        ],
    },
    "electronics": {
        "category": "deep-electronics",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Electronics",
            "https://en.wikipedia.org/wiki/Integrated_circuit",
            "https://en.wikipedia.org/wiki/Microprocessor",
            "https://en.wikipedia.org/wiki/Field-programmable_gate_array",
            "https://en.wikipedia.org/wiki/Printed_circuit_board",
            "https://en.wikipedia.org/wiki/Semiconductor_device",
        ],
    },
    "mathematics-advanced": {
        "category": "deep-math-advanced",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Category_theory",
            "https://en.wikipedia.org/wiki/Group_theory",
            "https://en.wikipedia.org/wiki/Differential_geometry",
            "https://en.wikipedia.org/wiki/Functional_analysis",
            "https://en.wikipedia.org/wiki/Algebraic_topology",
            "https://en.wikipedia.org/wiki/Graph_theory",
        ],
    },
    "climate": {
        "category": "deep-climate",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Climate_change",
            "https://en.wikipedia.org/wiki/Greenhouse_effect",
            "https://en.wikipedia.org/wiki/Renewable_energy",
            "https://en.wikipedia.org/wiki/Carbon_dioxide_in_Earth%27s_atmosphere",
            "https://en.wikipedia.org/wiki/Paris_Agreement",
            "https://en.wikipedia.org/wiki/Sustainability",
        ],
    },
    "materials": {
        "category": "deep-materials",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Materials_science",
            "https://en.wikipedia.org/wiki/Nanotechnology",
            "https://en.wikipedia.org/wiki/Superconductivity",
            "https://en.wikipedia.org/wiki/Graphene",
            "https://en.wikipedia.org/wiki/Metamaterial",
            "https://en.wikipedia.org/wiki/Polymer",
        ],
    },
    "law": {
        "category": "deep-law",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Law",
            "https://en.wikipedia.org/wiki/Constitutional_law",
            "https://en.wikipedia.org/wiki/International_law",
            "https://en.wikipedia.org/wiki/Criminal_law",
            "https://en.wikipedia.org/wiki/Contract",
            "https://en.wikipedia.org/wiki/Human_rights",
        ],
    },
    "sociology": {
        "category": "deep-sociology",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Sociology",
            "https://en.wikipedia.org/wiki/Social_structure",
            "https://en.wikipedia.org/wiki/Political_science",
            "https://en.wikipedia.org/wiki/Anthropology",
            "https://en.wikipedia.org/wiki/Demographics",
        ],
    },
    "web-development": {
        "category": "deep-webdev",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Web_framework",
            "https://en.wikipedia.org/wiki/JavaScript",
            "https://en.wikipedia.org/wiki/Python_(programming_language)",
            "https://en.wikipedia.org/wiki/TypeScript",
            "https://en.wikipedia.org/wiki/React_(software)",
            "https://en.wikipedia.org/wiki/Node.js",
            "https://en.wikipedia.org/wiki/REST",
            "https://en.wikipedia.org/wiki/GraphQL",
        ],
    },
    "databases": {
        "category": "deep-databases",
        "max_pages": 2000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Database",
            "https://en.wikipedia.org/wiki/SQL",
            "https://en.wikipedia.org/wiki/NoSQL",
            "https://en.wikipedia.org/wiki/PostgreSQL",
            "https://en.wikipedia.org/wiki/Redis",
            "https://en.wikipedia.org/wiki/MongoDB",
            "https://en.wikipedia.org/wiki/Graph_database",
        ],
    },
    "devops": {
        "category": "deep-devops",
        "max_pages": 2000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/DevOps",
            "https://en.wikipedia.org/wiki/Kubernetes",
            "https://en.wikipedia.org/wiki/Docker_(software)",
            "https://en.wikipedia.org/wiki/Continuous_integration",
            "https://en.wikipedia.org/wiki/Infrastructure_as_code",
            "https://en.wikipedia.org/wiki/Ansible_(software)",
        ],
    },
    "jvm": {
        "category": "deep-jvm",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Java_(programming_language)",
            "https://en.wikipedia.org/wiki/Java_virtual_machine",
            "https://en.wikipedia.org/wiki/Spring_Framework",
            "https://en.wikipedia.org/wiki/Kotlin_(programming_language)",
            "https://en.wikipedia.org/wiki/Scala_(programming_language)",
            "https://en.wikipedia.org/wiki/Apache_Maven",
        ],
    },
    "messaging": {
        "category": "deep-messaging",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Message_broker",
            "https://en.wikipedia.org/wiki/Apache_Kafka",
            "https://en.wikipedia.org/wiki/RabbitMQ",
            "https://en.wikipedia.org/wiki/Message_queue",
            "https://en.wikipedia.org/wiki/Publish%E2%80%93subscribe_pattern",
        ],
    },
    "testing": {
        "category": "deep-testing",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Software_testing",
            "https://en.wikipedia.org/wiki/Test-driven_development",
            "https://en.wikipedia.org/wiki/Unit_testing",
            "https://en.wikipedia.org/wiki/Integration_testing",
            "https://en.wikipedia.org/wiki/Mutation_testing",
            "https://en.wikipedia.org/wiki/Chaos_engineering",
        ],
    },
    "operating-systems": {
        "category": "deep-os",
        "max_pages": 2000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Operating_system",
            "https://en.wikipedia.org/wiki/Linux_kernel",
            "https://en.wikipedia.org/wiki/Unix",
            "https://en.wikipedia.org/wiki/Windows_NT",
            "https://en.wikipedia.org/wiki/Process_(computing)",
            "https://en.wikipedia.org/wiki/File_system",
            "https://en.wikipedia.org/wiki/Memory_management",
            "https://en.wikipedia.org/wiki/Virtualization",
        ],
    },
    "statistics": {
        "category": "deep-statistics",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Statistics",
            "https://en.wikipedia.org/wiki/Bayesian_statistics",
            "https://en.wikipedia.org/wiki/Regression_analysis",
            "https://en.wikipedia.org/wiki/Hypothesis_testing",
            "https://en.wikipedia.org/wiki/Monte_Carlo_method",
            "https://en.wikipedia.org/wiki/Markov_chain",
        ],
    },
    "energy": {
        "category": "deep-energy",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Energy",
            "https://en.wikipedia.org/wiki/Nuclear_power",
            "https://en.wikipedia.org/wiki/Wind_power",
            "https://en.wikipedia.org/wiki/Solar_power",
            "https://en.wikipedia.org/wiki/Hydrogen_economy",
            "https://en.wikipedia.org/wiki/Nuclear_fusion",
        ],
    },
    "geography": {
        "category": "deep-geography",
        "max_pages": 1000,
        "depth": 3,
        "seeds": [
            "https://en.wikipedia.org/wiki/Geography",
            "https://en.wikipedia.org/wiki/Geopolitics",
            "https://en.wikipedia.org/wiki/Oceanography",
            "https://en.wikipedia.org/wiki/Plate_tectonics",
            "https://en.wikipedia.org/wiki/Atmosphere_of_Earth",
        ],
    },
}


class DeepCrawlScraper(BaseScraper):

    def __init__(self, base_dir, topic_key):
        config = SEEDS[topic_key]
        name = config["category"]
        super().__init__(name, base_dir, interval_seconds=3600)
        self.topic_key = topic_key
        self.config = config
        self.max_pages = config.get("max_pages", 400)
        self.max_depth = config.get("depth", 2)
        self.visited = set()
        self.scraped_count = 0

    def _strip_html(self, c):
        c = re.sub(r'<script[^>]*>.*?</script>', '', c, flags=re.DOTALL)
        c = re.sub(r'<style[^>]*>.*?</style>', '', c, flags=re.DOTALL)
        c = re.sub(r'<[^>]+>', ' ', c)
        c = html_mod.unescape(c)
        return re.sub(r'\s+', ' ', c).strip()

    def _extract_wiki_links(self, html_content, base_url):
        """Extract Wikipedia article links from page content area."""
        body_start = html_content.find('mw-content-text')
        nav_start = html_content.find('id="catlinks"')
        if body_start >= 0 and nav_start > body_start:
            search_text = html_content[body_start:nav_start]
        elif body_start >= 0:
            search_text = html_content[body_start:]
        else:
            search_text = html_content

        links = []
        for m in re.finditer(r'href="(?://en\.wikipedia\.org)?(/wiki/[^"#]+)"', search_text):
            path = m.group(1)
            if any(path.startswith(p) for p in SKIP_PREFIXES):
                continue
            if SKIP_PATTERNS.search(path):
                continue
            safe_path = quote(path, safe='/:@!$&\'()*+,;=-._~')
            full_url = f"https://en.wikipedia.org{safe_path}"
            if full_url not in self.visited:
                links.append(full_url)

        return list(dict.fromkeys(links))

    def _scrape_page(self, url, depth):
        """Scrape a single page and optionally follow links."""
        if not self.running or self.scraped_count >= self.max_pages:
            return
        if url in self.visited:
            return

        self.visited.add(url)

        content = self.fetch_url(url)
        if not content or len(content) < 500:
            return

        text = self._strip_html(content)
        if len(text) < 200:
            return

        title = ""
        m = re.search(r'<title>([^<]+)</title>', content)
        if m:
            title = m.group(1).strip().replace(' - Wikipedia', '')

        saved = self.save_item(
            self.make_id(url),
            {
                "title": title,
                "content": text[:50000],
                "url": url,
                "category": self.config["category"],
                "type": "documentation",
                "depth": depth,
                "topic": self.topic_key,
            }
        )

        if saved:
            self.scraped_count += 1
            if self.scraped_count % 25 == 0:
                self.log.info(f"  [{self.scraped_count}/{self.max_pages}] {title[:60]}")
            elif self.scraped_count <= 10 or self.scraped_count % 50 == 0:
                self.log.info(f"  [{self.scraped_count}/{self.max_pages}] {title[:60]}")

        time.sleep(2.0)

        if depth < self.max_depth and self.scraped_count < self.max_pages:
            child_links = self._extract_wiki_links(content, url)
            if depth == 0:
                self.log.info(f"    Found {len(child_links)} links from {title[:40]}")
            for link in child_links:
                if not self.running or self.scraped_count >= self.max_pages:
                    break
                self._scrape_page(link, depth + 1)

    def scrape(self):
        self.log.info(f"=== Deep crawl: {self.topic_key} (max {self.max_pages} pages, depth {self.max_depth}) ===")

        for seed_url in self.config["seeds"]:
            if not self.running or self.scraped_count >= self.max_pages:
                break
            self.log.info(f"--- Seed: {seed_url} ---")
            self._scrape_page(seed_url, 0)

        self.log.info(f"=== Done: {self.scraped_count} pages scraped for {self.topic_key} ===")
        return self.scraped_count


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <topic_key>")
        print(f"Topics: {', '.join(sorted(SEEDS.keys()))}")
        sys.exit(1)

    topic = sys.argv[1]
    if topic not in SEEDS:
        print(f"Unknown topic: {topic}")
        print(f"Available: {', '.join(sorted(SEEDS.keys()))}")
        sys.exit(1)

    DeepCrawlScraper(os.path.expanduser("~"), topic).run()
