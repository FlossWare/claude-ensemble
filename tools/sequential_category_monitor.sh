#!/bin/bash
# SEQUENTIAL CATEGORY SCRAPER MONITOR
# One category at a time, 1M each

# Category order

# VARIABLE ALLOCATION (Option 3)
declare -A CATEGORY_TARGETS
CATEGORY_TARGETS[ai_ml_ga]=2000000
CATEGORY_TARGETS[computer_science]=2000000
CATEGORY_TARGETS[mathematics]=2000000
CATEGORY_TARGETS[science]=2000000

# Important topics (1.5M each)
CATEGORY_TARGETS[electrical_engineering]=1500000
CATEGORY_TARGETS[computer_engineering]=1500000
CATEGORY_TARGETS[mechanical_engineering]=1500000
CATEGORY_TARGETS[civil_engineering]=1500000
CATEGORY_TARGETS[chemical_engineering]=1500000
CATEGORY_TARGETS[medicine]=1500000
CATEGORY_TARGETS[legal]=1500000
CATEGORY_TARGETS[economics]=1500000

# Standard topics (1M each)
CATEGORY_TARGETS[social_sciences]=1000000
CATEGORY_TARGETS[philosophy]=1000000
CATEGORY_TARGETS[history]=1000000
CATEGORY_TARGETS[game_theory]=1000000
CATEGORY_TARGETS[misc]=1000000
CATEGORY_TARGETS[textbooks]=1000000
CATEGORY_TARGETS[educational_explanations]=1000000
CATEGORY_TARGETS[problem_sets]=1000000
CATEGORY_TARGETS[beginner_programming]=1000000
CATEGORY_TARGETS[worked_examples]=1000000
CATEGORY_TARGETS[chain_of_thought]=1000000
CATEGORY_TARGETS[reasoning_chains]=1000000
CATEGORY_TARGETS[problem_decomposition]=1000000
CATEGORY_TARGETS[conversation]=1000000
CATEGORY_TARGETS[news]=1000000
CATEGORY_TARGETS[creative_writing]=1000000
CATEGORY_TARGETS[multilingual]=1000000
CATEGORY_TARGETS[practical_howto]=1000000
CATEGORY_TARGETS[safety_ethics]=500000
CATEGORY_TARGETS[common_sense]=500000
CATEGORIES=(
    "ai_ml_ga"
    "computer_science"
    "mathematics"
    "science"
    "electrical_engineering"
    "computer_engineering"
    "philosophy"
    "misc"
)

# Variable allocation - see below

# BIG MACHINES - UNLIMITED SCRAPERS
declare -A UNLIMITED_MACHINES
UNLIMITED_MACHINES[laptop-01]=80
UNLIMITED_MACHINES[server-01]=40
UNLIMITED_MACHINES[server-02]=90
UNLIMITED_MACHINES[server-03]=90

BIG_MACHINES=(laptop-01 server-01 server-02 server-03)

# SMALL MACHINES - RATE-LIMITED SCRAPERS
declare -A RATE_LIMITED_MACHINES
RATE_LIMITED_MACHINES[aio-01]=15
RATE_LIMITED_MACHINES[desktop-ap]=10
RATE_LIMITED_MACHINES[server-ap]=10
RATE_LIMITED_MACHINES[pi-01]=8
RATE_LIMITED_MACHINES[pi-02]=8

SMALL_MACHINES=(aio-01 desktop-ap server-ap pi-01 pi-02)

# CATEGORY SCRAPERS
# AI/ML/GA
AI_ML_UNLIMITED=(
    "beast_mode_ml_frameworks.py"
)

AI_ML_RATE_LIMITED=(
    "arxiv_scraper.py --arxiv-cats cs.AI,cs.LG,cs.NE,stat.ML"
    "semantic_scholar_scraper.py --topics 'machine learning,neural networks,deep learning,genetic algorithms'"
    "hackernews_scraper.py --filter ml,ai,neural"
)

# Computer Science
CS_UNLIMITED=(
    "beast_mode_modern_languages.py"
    "beast_mode_blockchain_cloud.py"
    "database_languages_scraper.py"
    "os_code_docs_scraper.py"
    "firmware_code_scraper.py"
    "official_docs_scraper.py"
)

CS_RATE_LIMITED=(
    "stackexchange_scraper.py --sites stackoverflow,programmers,softwareengineering"
    "reddit_scraper.py --subreddits programming,coding,webdev,javascript,python,golang,rust"
    "arxiv_scraper.py --arxiv-cats cs.PL,cs.SE,cs.DC,cs.DB,cs.DS"
)

# Mathematics
MATH_UNLIMITED=()

MATH_RATE_LIMITED=(
    "arxiv_scraper.py --arxiv-cats math.AG,math.AT,math.CA,math.CO,math.CT,math.DG,math.DS,math.FA,math.GM,math.GN,math.GT,math.HO,math.IT,math.KT,math.LO,math.MG,math.MP,math.NA,math.NT,math.OA,math.OC,math.PR,math.QA,math.RA,math.RT,math.SG,math.SP,math.ST"
    "stackexchange_scraper.py --sites math,mathoverflow"
    "wikipedia_scraper.py --topics 'Category:Mathematics,Category:Algebra,Category:Calculus,Category:Geometry,Category:Statistics'"
)

# Science
SCIENCE_UNLIMITED=()

SCIENCE_RATE_LIMITED=(
    "arxiv_scraper.py --arxiv-cats physics.acc-ph,physics.ao-ph,physics.atom-ph,physics.bio-ph,physics.chem-ph,physics.class-ph,physics.comp-ph,physics.data-an,physics.flu-dyn,physics.gen-ph,physics.geo-ph,physics.optics,physics.plasm-ph,physics.space-ph"
    "pubmed_scraper.py"
    "wikipedia_scraper.py --topics 'Category:Physics,Category:Chemistry,Category:Biology,Category:Astronomy'"
    "semantic_scholar_scraper.py --topics 'physics,chemistry,biology,astronomy'"
)

# Electrical Engineering
EE_UNLIMITED=()

EE_RATE_LIMITED=(
    "arxiv_scraper.py --arxiv-cats eess.AS,eess.IV,eess.SP,eess.SY"
    "semantic_scholar_scraper.py --topics 'circuits,VLSI,signal processing,control systems'"
    "wikipedia_scraper.py --topics 'Category:Electrical_circuits,Category:Digital_electronics,Category:Signal_processing'"
)

# Computer Engineering
CE_UNLIMITED=()

CE_RATE_LIMITED=(
    "arxiv_scraper.py --arxiv-cats cs.AR"
    "semantic_scholar_scraper.py --topics 'computer architecture,embedded systems,hardware design,FPGA'"
    "wikipedia_scraper.py --topics 'Category:Computer_architecture,Category:Embedded_systems'"
    "stackexchange_scraper.py --sites electronics,arduino,raspberrypi"
)

# Philosophy
PHIL_UNLIMITED=()

PHIL_RATE_LIMITED=(
    "stackexchange_scraper.py --sites philosophy"
    "wikipedia_scraper.py --topics 'Category:Philosophy,Category:Epistemology,Category:Logic,Category:Ethics,Category:Metaphysics'"
    "semantic_scholar_scraper.py --topics 'philosophy,ethics,epistemology,logic,consciousness'"
)

# Misc
MISC_UNLIMITED=(
    "hackernews_scraper.py"
)

MISC_RATE_LIMITED=(
    "reddit_scraper.py --subreddits science,technology,engineering,askscience"
    "wikipedia_scraper.py --topics 'Category:Technology,Category:Engineering'"
)

get_current_category() {
    # Find first category that hasn't hit target
    for category in "${CATEGORIES[@]}"; do
        count=$(wc -l /mnt/nas/web-scrape/categories/${category}/*.jsonl 2>/dev/null | tail -1 | awk '{print $1}')
        count=${count:-0}

        if [ $count -lt ${CATEGORY_TARGETS[$category]:-1000000} ]; then
            echo $category
            return
        fi
    done

    # All done!
    echo "COMPLETE"
}

check_progress() {
    current_cat=$(get_current_category)

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 SEQUENTIAL CATEGORY PROGRESS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    total_all=0

    for category in "${CATEGORIES[@]}"; do
        count=$(wc -l /mnt/nas/web-scrape/categories/${category}/*.jsonl 2>/dev/null | tail -1 | awk '{print $1}')
        count=${count:-0}
        pct=$(echo "scale=1; ($count / $TARGET_PER_CATEGORY) * 100" | bc)

        status="⏸️"
        if [ "$category" = "$current_cat" ]; then
            status="🔥"
        elif [ $count -ge $TARGET_PER_CATEGORY ]; then
            status="✅"
        fi

        printf "  %s %-25s: %8d / %8d (%5.1f%%)\n" "$status" "$category" "$count" "$TARGET_PER_CATEGORY" "$pct"
        total_all=$((total_all + count))
    done

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    total_pct=$(echo "scale=1; ($total_all / 8000000) * 100" | bc)
    printf "  %-27s: %8d / %8d (%5.1f%%)\n" "TOTAL" "$total_all" "8000000" "$total_pct"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

start_scrapers_for_category() {
    local category=$1
    local machine=$2
    local count=$3
    local is_big_machine=$4

    declare -n scrapers

    if [ "$is_big_machine" = "true" ]; then
        case $category in
            ai_ml_ga) scrapers=AI_ML_UNLIMITED ;;
            computer_science) scrapers=CS_UNLIMITED ;;
            mathematics) scrapers=MATH_UNLIMITED ;;
            science) scrapers=SCIENCE_UNLIMITED ;;
            electrical_engineering) scrapers=EE_UNLIMITED ;;
            computer_engineering) scrapers=CE_UNLIMITED ;;
            philosophy) scrapers=PHIL_UNLIMITED ;;
            misc) scrapers=MISC_UNLIMITED ;;
        esac
    else
        case $category in
            ai_ml_ga) scrapers=AI_ML_RATE_LIMITED ;;
            computer_science) scrapers=CS_RATE_LIMITED ;;
            mathematics) scrapers=MATH_RATE_LIMITED ;;
            science) scrapers=SCIENCE_RATE_LIMITED ;;
            electrical_engineering) scrapers=EE_RATE_LIMITED ;;
            computer_engineering) scrapers=CE_RATE_LIMITED ;;
            philosophy) scrapers=PHIL_RATE_LIMITED ;;
            misc) scrapers=MISC_RATE_LIMITED ;;
        esac
    fi

    if [ ${#scrapers[@]} -eq 0 ]; then
        return
    fi

    for i in $(seq 1 $count); do
        scraper_cmd=${scrapers[$RANDOM % ${#scrapers[@]}]}
        log_name="${machine}_${category}_$(date +%s)_$i"

        ssh claude@$machine "cd /mnt/aio-01/claude-orchestrator && nohup python3 tools/$scraper_cmd --category $category >/mnt/nas/web-scrape/logs/${log_name}.log 2>&1 &" 2>/dev/null &

        if [ $((i % 10)) -eq 0 ]; then sleep 1; fi
    done
}

check_and_restart() {
    current_cat=$(get_current_category)

    if [ "$current_cat" = "COMPLETE" ]; then
        echo ""
        echo "🏆 ALL 8 CATEGORIES COMPLETE! 8M EXAMPLES! 🏆"
        exit 0
    fi

    echo ""
    echo "🎯 CURRENT FOCUS: $current_cat"
    echo ""

    # Big machines - unlimited scrapers
    for host in "${BIG_MACHINES[@]}"; do
        current=$(ssh -o ConnectTimeout=3 claude@$host 'ps aux | grep python3 | grep tools | grep -v grep | wc -l' 2>/dev/null || echo 0)
        target=${UNLIMITED_MACHINES[$host]}

        echo "[$host UNLIMITED] Current: $current, Target: $target"

        if [ $current -lt $target ]; then
            needed=$((target - current))
            echo "  🔥 Starting $needed scrapers for $current_cat"
            start_scrapers_for_category $current_cat $host $needed true
        else
            echo "  ✅ OK"
        fi
    done

    # Small machines - rate-limited scrapers
    for host in "${SMALL_MACHINES[@]}"; do
        current=$(ssh -o ConnectTimeout=3 claude@$host 'ps aux | grep python3 | grep tools | grep -v grep | wc -l' 2>/dev/null || echo 0)
        target=${RATE_LIMITED_MACHINES[$host]}

        echo "[$host RATE-LIMITED] Current: $current, Target: $target"

        if [ $current -lt $target ]; then
            needed=$((target - current))
            echo "  ⚠️  Starting $needed scrapers for $current_cat"
            start_scrapers_for_category $current_cat $host $needed false
        else
            echo "  ✅ OK"
        fi
    done
}

# Create category directories
for category in "${CATEGORIES[@]}"; do
    mkdir -p /mnt/nas/web-scrape/categories/${category}
done

# Move existing 34K examples to computer_science
echo "Moving existing 34K examples to computer_science..."
mv /mnt/nas/web-scrape/synthetic-data/*.jsonl /mnt/nas/web-scrape/categories/computer_science/ 2>/dev/null || true

while true; do
    echo ""
    echo "$(date)"
    check_progress
    check_and_restart

    echo ""
    echo "Next check in 5 minutes..."
    sleep 300
done
