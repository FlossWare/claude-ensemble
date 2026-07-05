#!/usr/bin/env bash
#
# ULTIMATE MATHEMATICS & SCIENCE SCRAPER
# Scrapes ALL math/physics/chemistry/biology research from arXiv
#

cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔬 ULTIMATE MATHEMATICS & SCIENCE TRAINING DATA"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "MATHEMATICS (10 topics):"
echo "  ✓ Algebra"
echo "  ✓ Analysis & Calculus"
echo "  ✓ Geometry & Topology"
echo "  ✓ Number Theory"
echo "  ✓ Probability & Statistics"
echo "  ✓ Combinatorics"
echo "  ✓ Mathematical Physics"
echo "  ✓ Dynamical Systems"
echo "  ✓ Numerical Analysis"
echo "  ✓ Logic & Set Theory"
echo ""
echo "PHYSICS (15 topics):"
echo "  ✓ Quantum Mechanics"
echo "  ✓ Quantum Computing"
echo "  ✓ Quantum Information"
echo "  ✓ General Relativity"
echo "  ✓ Condensed Matter Physics"
echo "  ✓ Statistical Mechanics"
echo "  ✓ Astrophysics"
echo "  ✓ Cosmology"
echo "  ✓ Particle Physics"
echo "  ✓ Nuclear Physics"
echo "  ✓ Plasma Physics"
echo "  ✓ Optics"
echo "  ✓ Fluid Dynamics"
echo "  ✓ Thermodynamics"
echo "  ✓ Biophysics"
echo ""
echo "CHEMISTRY & BIOLOGY (5 topics):"
echo "  ✓ Quantum Chemistry"
echo "  ✓ Computational Chemistry"
echo "  ✓ Molecular Biology"
echo "  ✓ Genomics & Bioinformatics"
echo "  ✓ Neuroscience"
echo ""
echo "Target: 1,500 papers × 2 examples = 3,000 training examples"
echo "Total with CS: 5,000+ examples across ALL OF SCIENCE!"
echo "Cost: \$0.00 (still FREE!)"
echo "Time: ~6-8 hours"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# MATHEMATICS (50 papers each = 500 papers)
python3 tools/arxiv_paper_scraper.py "cat:math.AG" 50 > ~/.claude/logs/sci_algebra.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.CA" 50 > ~/.claude/logs/sci_analysis.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.DG" 50 > ~/.claude/logs/sci_geometry.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.NT" 50 > ~/.claude/logs/sci_number_theory.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.PR" 50 > ~/.claude/logs/sci_probability.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.CO" 50 > ~/.claude/logs/sci_combinatorics.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math-ph" 50 > ~/.claude/logs/sci_mathphys.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.DS" 50 > ~/.claude/logs/sci_dynamical.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.NA" 50 > ~/.claude/logs/sci_numerical.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:math.LO" 50 > ~/.claude/logs/sci_logic.log 2>&1 &

# PHYSICS (50 papers each = 750 papers)
python3 tools/arxiv_paper_scraper.py "cat:quant-ph" 50 > ~/.claude/logs/sci_quantum.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "quantum computing" 50 > ~/.claude/logs/sci_qcomp.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "quantum information" 50 > ~/.claude/logs/sci_qinfo.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:gr-qc" 50 > ~/.claude/logs/sci_relativity.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:cond-mat" 50 > ~/.claude/logs/sci_condmat.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "statistical mechanics" 50 > ~/.claude/logs/sci_statmech.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:astro-ph" 50 > ~/.claude/logs/sci_astro.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cosmology" 50 > ~/.claude/logs/sci_cosmo.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:hep-th" 50 > ~/.claude/logs/sci_particle.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:nucl-th" 50 > ~/.claude/logs/sci_nuclear.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "plasma physics" 50 > ~/.claude/logs/sci_plasma.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:physics.optics" 50 > ~/.claude/logs/sci_optics.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "fluid dynamics" 50 > ~/.claude/logs/sci_fluids.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "thermodynamics" 50 > ~/.claude/logs/sci_thermo.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "biophysics" 50 > ~/.claude/logs/sci_biophys.log 2>&1 &

# CHEMISTRY & BIOLOGY (50 papers each = 250 papers)
python3 tools/arxiv_paper_scraper.py "quantum chemistry" 50 > ~/.claude/logs/sci_qchem.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "computational chemistry" 50 > ~/.claude/logs/sci_compchem.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:q-bio.MN" 50 > ~/.claude/logs/sci_molbio.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:q-bio.GN" 50 > ~/.claude/logs/sci_genomics.log 2>&1 &
python3 tools/arxiv_paper_scraper.py "cat:q-bio.NC" 50 > ~/.claude/logs/sci_neuro.log 2>&1 &

echo ""
echo "✅ Launched 30 parallel science scraping jobs!"
echo ""
echo "Total workers running now: ~51 (20 CS + 30 Science + 1 coordinator)"
echo ""
echo "Monitor:"
echo "  tail -f ~/.claude/logs/sci_*.log"
echo ""
echo "Combined with CS scraping:"
echo "  - 1,000 CS papers"
echo "  - 1,500 Math/Science papers"
echo "  - 2,500 TOTAL papers"
echo "  - 5,000 training examples"
echo ""
echo "YOUR MODEL WILL KNOW:"
echo "  ✓ All of Computer Science"
echo "  ✓ All of Mathematics"
echo "  ✓ All of Physics (including Quantum Mechanics!)"
echo "  ✓ Chemistry & Biology"
echo "  ✓ + Your 843 curated PDFs"
echo "  ✓ + Web documentation"
echo ""
echo "= ULTIMATE MULTIDISCIPLINARY AI EXPERT! 🧠"
