#!/usr/bin/env bash
#
# FLEET-WIDE PARALLEL SCRAPING
# Distributes scraping across ALL fleet machines
# Each machine runs 5-10 scrapers in parallel
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$SCRIPT_DIR/../tools"
SHARED_DIR="$SCRIPT_DIR/../shared"

# Fleet machines (8 total)
FLEET_MACHINES=(
    "aio-01"      # orchestrator (local)
    "server-01"   # remote
    "server-02"   # remote
    "server-03"   # remote
    "laptop-01"   # remote
    "server-ap"   # remote
    "desktop-ap"  # remote
    "pi-01"       # remote (ARM - skip heavy tasks)
)

# Topics to scrape (60 total)
TOPICS=(
    # AI/ML (20)
    "transformers" "neural_nets" "deep_learning" "reinforcement_learning"
    "genetic_algorithms" "gan" "diffusion" "optimization"
    "computer_vision" "natural_language_processing" "robotics"
    "machine_learning" "convolutional_neural_networks" "recurrent_neural_networks"
    "transfer_learning" "meta_learning" "few_shot_learning" "self_supervised_learning"
    "contrastive_learning" "graph_neural_networks"

    # Core CS (15)
    "algorithms" "data_structures" "database_systems" "distributed_systems"
    "compilers" "operating_systems" "computer_networks" "cryptography"
    "software_engineering" "theory_of_computation" "parallel_computing"
    "cloud_computing" "edge_computing" "serverless" "microservices"

    # Math (10)
    "linear_algebra" "calculus" "differential_equations" "topology"
    "number_theory" "graph_theory" "combinatorics" "probability"
    "statistics" "numerical_analysis"

    # Physics (10)
    "quantum_mechanics" "quantum_computing" "quantum_information"
    "relativity" "astrophysics" "cosmology" "particle_physics"
    "condensed_matter" "statistical_mechanics" "thermodynamics"

    # Other (5)
    "bioinformatics" "computational_biology" "neuroscience"
    "quantum_chemistry" "materials_science"
)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 FLEET-WIDE PARALLEL SCRAPING"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Fleet machines: ${#FLEET_MACHINES[@]}"
echo "Topics to scrape: ${#TOPICS[@]}"
echo "Papers per topic: 100"
echo "Estimated total: $((${#TOPICS[@]} * 100)) papers = $((${#TOPICS[@]} * 200)) examples"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Distribute topics across fleet
machine_idx=0
launched=0

for topic in "${TOPICS[@]}"; do
    machine="${FLEET_MACHINES[$machine_idx]}"

    # Format topic for filename
    topic_clean=$(echo "$topic" | tr ' ' '_')

    if [ "$machine" = "aio-01" ]; then
        # Local machine
        echo "[$machine] Launching: $topic"
        (python3 "$TOOLS_DIR/arxiv_scraper_with_storage.py" "$topic" 100 \
            > "/mnt/nas/web-scrape/logs/scrape_${topic_clean}.log" 2>&1) &
    else
        # Remote machine
        echo "[$machine] Launching: $topic"
        ssh claude@$machine "cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && \
            python3 tools/arxiv_scraper_with_storage.py '$topic' 100 \
            > /mnt/nas/web-scrape/logs/scrape_${topic_clean}.log 2>&1" &
    fi

    ((launched++))

    # Rotate to next machine
    machine_idx=$(( (machine_idx + 1) % ${#FLEET_MACHINES[@]} ))

    # Small delay every 5 launches
    if [ $((launched % 5)) -eq 0 ]; then
        echo ""
        echo "  Launched $launched/$((${#TOPICS[@]})) scrapers..."
        sleep 2
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ LAUNCHED $launched SCRAPERS ACROSS ${#FLEET_MACHINES[@]} MACHINES!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Distribution:"
topics_per_machine=$((launched / ${#FLEET_MACHINES[@]}))
for machine in "${FLEET_MACHINES[@]}"; do
    echo "  $machine: ~$topics_per_machine scrapers"
done
echo ""
echo "Monitor:"
echo "  All logs: tail -f /mnt/nas/web-scrape/logs/scrape_*.log"
echo "  Progress: watch -n 10 'ls /mnt/nas/web-scrape/raw-papers/*.json | wc -l'"
echo ""
echo "Expected completion: 4-8 hours"
echo "Expected data: 12,000+ training examples"
