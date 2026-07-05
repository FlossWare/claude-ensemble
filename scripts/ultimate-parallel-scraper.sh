#!/usr/bin/env bash
#
# ULTIMATE PARALLEL DATA SCRAPER
# Launches ALL sources in parallel with priority ordering
#

cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 ULTIMATE PARALLEL DATA COLLECTION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "PRIORITY ORDER:"
echo "  1️⃣  AI, ML, GA, Computer Science (FIRST)"
echo "  2️⃣  Mathematics (SECOND)"
echo "  3️⃣  Science: Physics, Chemistry, Biology (THIRD)"
echo "  4️⃣  Medical (FINALLY)"
echo ""
echo "SOURCES PER CATEGORY:"
echo "  📚 arXiv (research papers)"
echo "  🐙 GitHub (code repositories)"
echo "  💻 Stack Overflow (Q&A)"
echo "  📖 Wikipedia (encyclopedic)"
echo "  🏥 PubMed (medical only)"
echo "  📋 RFCs (internet protocols)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

mkdir -p ~/.claude/logs

# ============================================================================
# PRIORITY 1: AI, ML, GA, COMPUTER SCIENCE (LAUNCH IMMEDIATELY)
# ============================================================================

echo "🔥 PRIORITY 1: AI, ML, GA, COMPUTER SCIENCE (Launching Now!)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# arXiv: AI/ML Topics (8 topics × 100 papers = 800 papers)
python3 tools/arxiv_paper_scraper.py "transformers" 100 > ~/.claude/logs/p1_transformers.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "neural_nets" 100 > ~/.claude/logs/p1_neural.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "genetic_algorithms" 100 > ~/.claude/logs/p1_genetic.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "reinforcement_learning" 100 > ~/.claude/logs/p1_rl.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "gan" 100 > ~/.claude/logs/p1_gan.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "diffusion" 100 > ~/.claude/logs/p1_diffusion.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "optimization" 100 > ~/.claude/logs/p1_optimization.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "mamba_ssm" 100 > ~/.claude/logs/p1_mamba.log 2>&1 &

# arXiv: Core CS (12 topics × 100 papers = 1,200 papers)
python3 tools/arxiv_paper_scraper.py "algorithms data structures" 100 > ~/.claude/logs/p1_algorithms.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "database systems" 100 > ~/.claude/logs/p1_databases.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "distributed systems" 100 > ~/.claude/logs/p1_distributed.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "compilers programming languages" 100 > ~/.claude/logs/p1_compilers.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "operating systems" 100 > ~/.claude/logs/p1_os.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "computer networks" 100 > ~/.claude/logs/p1_networks.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cryptography security" 100 > ~/.claude/logs/p1_security.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "computer vision" 100 > ~/.claude/logs/p1_vision.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "natural language processing" 100 > ~/.claude/logs/p1_nlp.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "robotics" 100 > ~/.claude/logs/p1_robotics.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "software engineering" 100 > ~/.claude/logs/p1_software.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "theory of computation" 100 > ~/.claude/logs/p1_theory.log 2>&1 &

# GitHub: Top CS projects
python3 tools/github_code_scraper.py kubernetes/kubernetes > ~/.claude/logs/p1_gh_k8s.log 2>&1 &
python3 tools/github_code_scraper.py docker/moby > ~/.claude/logs/p1_gh_docker.log 2>&1 &
python3 tools/github_code_scraper.py pytorch/pytorch > ~/.claude/logs/p1_gh_pytorch.log 2>&1 &
python3 tools/github_code_scraper.py tensorflow/tensorflow > ~/.claude/logs/p1_gh_tf.log 2>&1 &
python3 tools/github_code_scraper.py facebook/react > ~/.claude/logs/p1_gh_react.log 2>&1 &

# Stack Overflow: CS tags
python3 -c "
from tools.ultimate_data_scraper import UltimateDataScraper
scraper = UltimateDataScraper()
data = scraper.scrape_stackoverflow('python', 100)
data.extend(scraper.scrape_stackoverflow('javascript', 100))
data.extend(scraper.scrape_stackoverflow('machine-learning', 100))
scraper.save_dataset(data, 'stackoverflow_cs.jsonl')
" > ~/.claude/logs/p1_stackoverflow.log 2>&1 &

# RFCs: Internet protocols
python3 tools/ultimate_data_scraper.py rfc > ~/.claude/logs/p1_rfc.log 2>&1 &

echo "  ✅ Launched 28 CS workers!"
echo ""

# ============================================================================
# PRIORITY 2: MATHEMATICS (LAUNCH AFTER 30 SEC DELAY)
# ============================================================================

(
sleep 30
echo ""
echo "🔢 PRIORITY 2: MATHEMATICS (Launching Now!)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# arXiv: Math topics (10 topics × 100 papers = 1,000 papers)
python3 tools/arxiv_paper_scraper.py "cat:math.AG" 100 > ~/.claude/logs/p2_algebra.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.CA" 100 > ~/.claude/logs/p2_analysis.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.DG" 100 > ~/.claude/logs/p2_geometry.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.NT" 100 > ~/.claude/logs/p2_number_theory.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.PR" 100 > ~/.claude/logs/p2_probability.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.CO" 100 > ~/.claude/logs/p2_combinatorics.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math-ph" 100 > ~/.claude/logs/p2_mathphys.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.DS" 100 > ~/.claude/logs/p2_dynamical.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.NA" 100 > ~/.claude/logs/p2_numerical.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.LO" 100 > ~/.claude/logs/p2_logic.log 2>&1 &

echo "  ✅ Launched 10 Math workers!"
) &

# ============================================================================
# PRIORITY 3: SCIENCE (Physics, Chemistry, Biology) (LAUNCH AFTER 60 SEC)
# ============================================================================

(
sleep 60
echo ""
echo "🔬 PRIORITY 3: SCIENCE (Physics, Chemistry, Biology) (Launching Now!)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# arXiv: Physics (15 topics × 100 papers = 1,500 papers)
python3 tools/arxiv_paper_scraper.py "cat:quant-ph" 100 > ~/.claude/logs/p3_quantum.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "quantum computing" 100 > ~/.claude/logs/p3_qcomp.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "quantum information" 100 > ~/.claude/logs/p3_qinfo.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:gr-qc" 100 > ~/.claude/logs/p3_relativity.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:cond-mat" 100 > ~/.claude/logs/p3_condmat.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "statistical mechanics" 100 > ~/.claude/logs/p3_statmech.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:astro-ph" 100 > ~/.claude/logs/p3_astro.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cosmology" 100 > ~/.claude/logs/p3_cosmo.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:hep-th" 100 > ~/.claude/logs/p3_particle.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:nucl-th" 100 > ~/.claude/logs/p3_nuclear.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "plasma physics" 100 > ~/.claude/logs/p3_plasma.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:physics.optics" 100 > ~/.claude/logs/p3_optics.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "fluid dynamics" 100 > ~/.claude/logs/p3_fluids.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "thermodynamics" 100 > ~/.claude/logs/p3_thermo.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "biophysics" 100 > ~/.claude/logs/p3_biophys.log 2>&1 &

# arXiv: Chemistry & Biology (5 topics × 100 papers = 500 papers)
python3 tools/arxiv_paper_scraper.py "quantum chemistry" 100 > ~/.claude/logs/p3_qchem.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "computational chemistry" 100 > ~/.claude/logs/p3_compchem.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:q-bio.MN" 100 > ~/.claude/logs/p3_molbio.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:q-bio.GN" 100 > ~/.claude/logs/p3_genomics.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:q-bio.NC" 100 > ~/.claude/logs/p3_neuro.log 2>&1 &

echo "  ✅ Launched 20 Science workers!"
) &

# ============================================================================
# PRIORITY 4: MEDICAL (LAUNCH AFTER 90 SEC)
# ============================================================================

(
sleep 90
echo ""
echo "🏥 PRIORITY 4: MEDICAL (Launching Now!)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# PubMed: Medical research (10 topics × 50 papers = 500 papers)
python3 -c "
from tools.ultimate_data_scraper import UltimateDataScraper
scraper = UltimateDataScraper()
queries = [
    'covid-19 treatment',
    'cancer immunotherapy',
    'alzheimer disease',
    'diabetes treatment',
    'cardiac surgery',
    'gene therapy',
    'vaccine development',
    'infectious disease',
    'neurodegenerative disease',
    'precision medicine'
]
all_data = []
for q in queries:
    data = scraper.scrape_pubmed(q, 50)
    all_data.extend(data)
scraper.save_dataset(all_data, 'pubmed_medical_all.jsonl')
" > ~/.claude/logs/p4_pubmed.log 2>&1 &

# arXiv: Medical topics
python3 tools/arxiv_paper_scraper.py "medical imaging" 50 > ~/.claude/logs/p4_imaging.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "drug discovery" 50 > ~/.claude/logs/p4_drugs.log 2>&1 &

echo "  ✅ Launched 3 Medical workers!"
) &

# ============================================================================
# MONITORING
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "TOTAL WORKERS LAUNCHING: ~61"
echo "  Priority 1 (CS):      28 workers (NOW)"
echo "  Priority 2 (Math):    10 workers (+30s)"
echo "  Priority 3 (Science): 20 workers (+60s)"
echo "  Priority 4 (Medical):  3 workers (+90s)"
echo ""
echo "TARGET PAPERS: ~5,500+"
echo "  CS:       2,000 papers × 2 = 4,000 examples"
echo "  Math:     1,000 papers × 2 = 2,000 examples"
echo "  Science:  2,000 papers × 2 = 4,000 examples"
echo "  Medical:    600 papers × 2 = 1,200 examples"
echo "  ════════════════════════════════════════"
echo "  TOTAL:    5,600 papers = 11,200+ examples!"
echo ""
echo "SOURCES:"
echo "  📚 arXiv: 5,000+ papers"
echo "  🐙 GitHub: 5+ repos"
echo "  💻 Stack Overflow: 300+ Q&A"
echo "  📋 RFCs: 15 protocols"
echo "  🏥 PubMed: 500+ medical papers"
echo ""
echo "COST: \$0.00 (100% FREE APIs)"
echo "TIME: 8-12 hours"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "MONITOR:"
echo "  tail -f ~/.claude/logs/p1_*.log  # Priority 1: CS"
echo "  tail -f ~/.claude/logs/p2_*.log  # Priority 2: Math"
echo "  tail -f ~/.claude/logs/p3_*.log  # Priority 3: Science"
echo "  tail -f ~/.claude/logs/p4_*.log  # Priority 4: Medical"
echo ""
echo "CHECK PROGRESS:"
echo "  watch -n 60 'ls -lh ~/.claude/ml-training/synthetic-data/*.jsonl | wc -l'"
echo ""
echo "ALL WORKERS LAUNCHED! 🚀🚀🚀"
