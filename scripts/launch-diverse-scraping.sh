#!/usr/bin/env bash
#
# LAUNCH DIVERSE SCRAPING - ALL SOURCES IN PARALLEL!
# Scrapes Wikipedia, creative writing, conversations, and more
# Target: 50,000+ diverse examples

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 DIVERSE SCRAPING - MAXIMUM PARALLELIZATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This will launch scrapers across ALL 8 machines:"
echo "  - Wikipedia (general knowledge)"
echo "  - Creative writing (stories, poetry, etc.)"
echo "  - Conversations (natural dialogue)"
echo "  - arXiv (continued technical scraping)"
echo ""
echo "Target: 50,000+ diverse training examples"
echo "Time: 6-12 hours"
echo ""

read -p "Proceed with massive parallel scraping? [y/N]: " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Cancelled"
    exit 0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 LAUNCHING SCRAPERS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Base directory
BASE_DIR="$HOME/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills"
LOG_DIR="/mnt/nas/web-scrape/logs"
mkdir -p "$LOG_DIR"

# Wikipedia categories (7 categories × 8 machines = 56 workers)
WIKI_CATEGORIES=("history" "geography" "culture" "science" "people" "current" "everyday")

# Machine arrays
LOW_RAM_MACHINES=("server-03" "desktop-ap" "pi-01" "pi-02")
HIGH_RAM_MACHINES=("aio-01" "laptop-01" "server-01" "server-02")
ALL_MACHINES=("${HIGH_RAM_MACHINES[@]}" "${LOW_RAM_MACHINES[@]}")

worker_id=0

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📚 WIKIPEDIA SCRAPING (7 categories × 8 machines = 56 workers)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Distribute Wikipedia categories across all machines
for category in "${WIKI_CATEGORIES[@]}"; do
    for machine in "${ALL_MACHINES[@]}"; do
        ((worker_id++))

        echo "[$worker_id] Wikipedia [$category] on $machine"

        ssh claude@$machine "
            cd $BASE_DIR && \
            python3 tools/wikipedia_scraper.py \
                --category $category \
                --max-per-category 20 \
                > $LOG_DIR/wiki_${category}_${machine}.log 2>&1
        " &

        sleep 0.2
    done
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✍️ CREATIVE WRITING (6 categories × 4 machines = 24 workers)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

CREATIVE_CATEGORIES=("stories" "dialogue" "descriptions" "poetry" "explanations" "how_to")

# Distribute creative writing across low-RAM machines (less intensive)
for category in "${CREATIVE_CATEGORIES[@]}"; do
    for machine in "${LOW_RAM_MACHINES[@]}"; do
        ((worker_id++))

        echo "[$worker_id] Creative [$category] on $machine"

        ssh claude@$machine "
            cd $BASE_DIR && \
            python3 tools/creative_scraper.py \
                --category $category \
                > $LOG_DIR/creative_${category}_${machine}.log 2>&1
        " &

        sleep 0.2
    done
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💬 CONVERSATIONS (8 machines)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# One conversation scraper per machine
for machine in "${ALL_MACHINES[@]}"; do
    ((worker_id++))

    echo "[$worker_id] Conversations on $machine"

    ssh claude@$machine "
        cd $BASE_DIR && \
        python3 tools/conversation_scraper.py \
            > $LOG_DIR/conversations_${machine}.log 2>&1
    " &

    sleep 0.2
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔬 CONTINUE arXiv SCRAPING (32 workers on remaining topics)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Additional arXiv topics (broader coverage)
ARXIV_EXTRA=(
    "economics" "linguistics" "sociology" "psychology"
    "environmental science" "materials science" "engineering"
    "information theory" "optimization" "robotics"
    "signal processing" "control theory" "systems biology"
    "neuroscience" "genetics" "biochemistry" "pharmacology"
    "astrophysics" "cosmology" "particle physics" "optics"
    "condensed matter" "quantum information" "topology"
    "number theory" "combinatorics" "graph theory"
    "logic" "category theory" "differential geometry"
    "functional analysis" "probability theory" "statistics"
    "game theory"
)

# Distribute arXiv topics across all machines
topic_idx=0
for topic in "${ARXIV_EXTRA[@]}"; do
    machine_idx=$((topic_idx % 8))
    machine="${ALL_MACHINES[$machine_idx]}"
    ((worker_id++))

    echo "[$worker_id] arXiv [$topic] on $machine"

    ssh claude@$machine "
        cd $BASE_DIR && \
        python3 tools/arxiv_scraper_with_storage.py \
            --query '$topic' \
            --max-papers 200 \
            > $LOG_DIR/arxiv_${topic// /_}_${machine}.log 2>&1
    " &

    ((topic_idx++))
    sleep 0.2
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ ALL SCRAPERS LAUNCHED!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Total workers: $worker_id"
echo ""
echo "Breakdown:"
echo "  - Wikipedia: 56 workers (7 categories × 8 machines)"
echo "  - Creative: 24 workers (6 categories × 4 machines)"
echo "  - Conversations: 8 workers (1 per machine)"
echo "  - arXiv Extra: 32 workers (additional topics)"
echo ""
echo "Expected output:"
echo "  - Wikipedia: ~8,400 examples (56 workers × 20 topics × 3 examples)"
echo "  - Creative: ~1,440 examples (24 workers × 10 prompts × 6 categories)"
echo "  - Conversations: ~320 examples (8 workers × 40 topics)"
echo "  - arXiv Extra: ~6,400 examples (32 topics × 200 papers)"
echo "  - TOTAL: ~16,560 NEW examples!"
echo "  - PLUS existing: ~2,600 from current arXiv scraping"
echo "  - GRAND TOTAL: ~19,000+ examples"
echo ""
echo "Estimated time: 6-12 hours"
echo ""
echo "Monitor progress:"
echo "  Watch all:     tail -f $LOG_DIR/*.log"
echo "  Wikipedia:     tail -f $LOG_DIR/wiki_*.log"
echo "  Creative:      tail -f $LOG_DIR/creative_*.log"
echo "  Conversations: tail -f $LOG_DIR/conversations_*.log"
echo "  arXiv:         tail -f $LOG_DIR/arxiv_*.log"
echo ""
echo "Check dataset size:"
echo "  ls -lh /mnt/nas/web-scrape/synthetic-data/ | wc -l"
echo "  du -sh /mnt/nas/web-scrape/synthetic-data/"
echo ""
echo "🚀 SCRAPING HARD! 🚀"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
