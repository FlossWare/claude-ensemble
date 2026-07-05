#!/bin/bash
# CATEGORY-BASED SCRAPER MONITOR
# Target: 1M examples per category (7M total)

# Category targets
declare -A CATEGORY_TARGETS
CATEGORY_TARGETS[ai_ml_ga]=1000000
CATEGORY_TARGETS[computer_science]=1000000
CATEGORY_TARGETS[mathematics]=1000000
CATEGORY_TARGETS[science]=1000000
CATEGORY_TARGETS[electrical_engineering]=1000000
CATEGORY_TARGETS[philosophy]=1000000
CATEGORY_TARGETS[misc]=1000000

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

# CATEGORY SCRAPERS MAPPING
# AI/ML/GA
AI_ML_UNLIMITED=(
    "beast_mode_ml_frameworks.py --category ai_ml_ga"
    "hackernews_scraper.py --category ai_ml_ga --filter ml,ai,neural"
)

AI_ML_RATE_LIMITED=(
    "arxiv_scraper.py --category ai_ml_ga --arxiv-cats cs.AI,cs.LG,cs.NE,stat.ML"
    "semantic_scholar_scraper.py --category ai_ml_ga --topics 'machine learning,neural networks,deep learning'"
)

# Computer Science
CS_UNLIMITED=(
    "beast_mode_modern_languages.py --category computer_science"
    "beast_mode_blockchain_cloud.py --category computer_science"
    "database_languages_scraper.py --category computer_science"
    "os_code_docs_scraper.py --category computer_science"
    "firmware_code_scraper.py --category computer_science"
    "official_docs_scraper.py --category computer_science"
)

CS_RATE_LIMITED=(
    "stackexchange_scraper.py --category computer_science --sites stackoverflow,programmers,softwareengineering"
    "reddit_scraper.py --category computer_science --subreddits programming,coding,webdev,javascript,python"
)

# Mathematics
MATH_UNLIMITED=()

MATH_RATE_LIMITED=(
    "arxiv_scraper.py --category mathematics --arxiv-cats math.AG,math.AT,math.CA,math.CO,math.CT,math.DG,math.DS,math.FA,math.GM,math.GN,math.GT,math.HO,math.IT,math.KT,math.LO,math.MG,math.MP,math.NA,math.NT,math.OA,math.OC,math.PR,math.QA,math.RA,math.RT,math.SG,math.SP,math.ST"
    "stackexchange_scraper.py --category mathematics --sites math,mathoverflow"
    "wikipedia_scraper.py --category mathematics --topics 'Category:Mathematics,Category:Algebra,Category:Calculus,Category:Geometry,Category:Statistics'"
)

# Science
SCIENCE_UNLIMITED=()

SCIENCE_RATE_LIMITED=(
    "arxiv_scraper.py --category science --arxiv-cats physics.acc-ph,physics.ao-ph,physics.atom-ph,physics.bio-ph,physics.chem-ph,physics.class-ph,physics.comp-ph,physics.data-an,physics.ed-ph,physics.flu-dyn,physics.gen-ph,physics.geo-ph,physics.hist-ph,physics.ins-det,physics.med-ph,physics.optics,physics.plasm-ph,physics.pop-ph,physics.soc-ph,physics.space-ph"
    "pubmed_scraper.py --category science"
    "wikipedia_scraper.py --category science --topics 'Category:Physics,Category:Chemistry,Category:Biology,Category:Astronomy'"
    "semantic_scholar_scraper.py --category science --topics 'physics,chemistry,biology,astronomy'"
)

# Electrical/Computer Engineering
EE_UNLIMITED=()

EE_RATE_LIMITED=(
    "arxiv_scraper.py --category electrical_engineering --arxiv-cats cs.AR,eess.AS,eess.IV,eess.SP,eess.SY"
    "semantic_scholar_scraper.py --category electrical_engineering --topics 'computer architecture,circuits,VLSI,embedded systems,signal processing'"
    "wikipedia_scraper.py --category electrical_engineering --topics 'Category:Computer_architecture,Category:Electrical_circuits,Category:Digital_electronics'"
)

# Philosophy
PHIL_UNLIMITED=()

PHIL_RATE_LIMITED=(
    "stackexchange_scraper.py --category philosophy --sites philosophy"
    "wikipedia_scraper.py --category philosophy --topics 'Category:Philosophy,Category:Epistemology,Category:Logic,Category:Ethics'"
    "semantic_scholar_scraper.py --category philosophy --topics 'philosophy,ethics,epistemology,logic'"
)

# Misc (whatever else)
MISC_UNLIMITED=(
    "hackernews_scraper.py --category misc"
)

MISC_RATE_LIMITED=(
    "reddit_scraper.py --category misc --subreddits science,technology,engineering,askscience"
    "wikipedia_scraper.py --category misc --topics 'Category:Technology,Category:Engineering'"
)

check_category_progress() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 CATEGORY PROGRESS (1M each = 7M total)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    total_all=0

    for category in ai_ml_ga computer_science mathematics science electrical_engineering philosophy misc; do
        count=$(wc -l /mnt/nas/web-scrape/categories/${category}/*.jsonl 2>/dev/null | tail -1 | awk '{print $1}')
        count=${count:-0}
        target=${CATEGORY_TARGETS[$category]}
        pct=$(echo "scale=1; ($count / $target) * 100" | bc)

        printf "  %-25s: %8d / %8d (%5.1f%%)\n" "$category" "$count" "$target" "$pct"
        total_all=$((total_all + count))
    done

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    total_pct=$(echo "scale=1; ($total_all / 7000000) * 100" | bc)
    printf "  %-25s: %8d / %8d (%5.1f%%)\n" "TOTAL" "$total_all" "7000000" "$total_pct"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

get_priority_category() {
    # Return category with lowest progress
    min_pct=100
    min_cat=""

    for category in ai_ml_ga computer_science mathematics science electrical_engineering philosophy misc; do
        count=$(wc -l /mnt/nas/web-scrape/categories/${category}/*.jsonl 2>/dev/null | tail -1 | awk '{print $1}')
        count=${count:-0}
        target=${CATEGORY_TARGETS[$category]}
        pct=$(echo "scale=2; ($count / $target) * 100" | bc)

        if (( $(echo "$pct < $min_pct" | bc -l) )); then
            min_pct=$pct
            min_cat=$category
        fi
    done

    echo $min_cat
}

start_scrapers_for_category() {
    local category=$1
    local machine=$2
    local count=$3
    local is_big_machine=$4

    # Select scraper list based on category and machine type
    declare -n scrapers

    if [ "$is_big_machine" = "true" ]; then
        case $category in
            ai_ml_ga) scrapers=AI_ML_UNLIMITED ;;
            computer_science) scrapers=CS_UNLIMITED ;;
            mathematics) scrapers=MATH_UNLIMITED ;;
            science) scrapers=SCIENCE_UNLIMITED ;;
            electrical_engineering) scrapers=EE_UNLIMITED ;;
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

        ssh claude@$machine "cd /mnt/aio-01/claude-orchestrator && nohup python3 tools/$scraper_cmd >/mnt/nas/web-scrape/logs/${log_name}.log 2>&1 &" 2>/dev/null &

        if [ $((i % 10)) -eq 0 ]; then sleep 1; fi
    done
}

check_and_balance() {
    echo ""
    echo "🎯 PRIORITY: $(get_priority_category)"
    echo ""

    # Big machines - unlimited scrapers
    for host in "${BIG_MACHINES[@]}"; do
        current=$(ssh -o ConnectTimeout=3 claude@$host 'ps aux | grep python3 | grep tools | grep -v grep | wc -l' 2>/dev/null || echo 0)
        target=${UNLIMITED_MACHINES[$host]}

        echo "[$host UNLIMITED] Current: $current, Target: $target"

        if [ $current -lt $target ]; then
            needed=$((target - current))
            priority_cat=$(get_priority_category)
            echo "  🔥 Starting $needed scrapers for $priority_cat"
            start_scrapers_for_category $priority_cat $host $needed true
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
            priority_cat=$(get_priority_category)
            echo "  ⚠️  Starting $needed scrapers for $priority_cat"
            start_scrapers_for_category $priority_cat $host $needed false
        else
            echo "  ✅ OK"
        fi
    done
}

# Create category directories
for category in ai_ml_ga computer_science mathematics science electrical_engineering philosophy misc; do
    mkdir -p /mnt/nas/web-scrape/categories/${category}
done

while true; do
    echo ""
    echo "$(date)"
    check_category_progress
    check_and_balance

    echo ""
    echo "Next check in 5 minutes..."
    sleep 300
done
