#!/bin/bash
# SCRAPER MONITOR & AUTO-RESTART
# Keeps scrapers running 24/7 to hit 1M examples

TARGET=1000000

# BIG MACHINES - UNLIMITED SCRAPERS ONLY (beast mode!)
declare -A UNLIMITED_TARGETS
UNLIMITED_TARGETS[laptop-01]=80
UNLIMITED_TARGETS[server-01]=40
UNLIMITED_TARGETS[server-02]=90
UNLIMITED_TARGETS[server-03]=90

BIG_MACHINES=(laptop-01 server-01 server-02 server-03)

# SMALL MACHINES - RATE-LIMITED SCRAPERS ONLY (slow APIs)
declare -A RATE_LIMITED_TARGETS
RATE_LIMITED_TARGETS[aio-01]=15
RATE_LIMITED_TARGETS[desktop-ap]=10
RATE_LIMITED_TARGETS[server-ap]=10
RATE_LIMITED_TARGETS[pi-01]=8
RATE_LIMITED_TARGETS[pi-02]=8

SMALL_MACHINES=(aio-01 desktop-ap server-ap pi-01 pi-02)

# UNLIMITED SCRAPERS (no rate limits - go beast mode!)
UNLIMITED_SCRAPERS=(
    "beast_mode_modern_languages.py"
    "beast_mode_ml_frameworks.py"
    "beast_mode_blockchain_cloud.py"
    "hackernews_scraper.py"
    "official_docs_scraper.py"
    "arxiv_scraper.py"
    "firmware_code_scraper.py"
    "database_languages_scraper.py"
    "os_code_docs_scraper.py"
)

# RATE-LIMITED SCRAPERS (slow down - only 1-2 per machine)
RATE_LIMITED_SCRAPERS=(
    "semantic_scholar_scraper.py"
    "stackexchange_scraper.py"
    "pubmed_scraper.py"
    "reddit_scraper.py"
    "wikipedia_scraper.py"
)

check_and_restart_unlimited() {
    local host=$1
    local target_count=$2

    current=$(ssh -o ConnectTimeout=3 claude@$host 'ps aux | grep python3 | grep tools | grep -v grep | wc -l' 2>/dev/null || echo 0)

    echo "[$host UNLIMITED] Current: $current scrapers, Target: $target_count"

    if [ $current -lt $target_count ]; then
        needed=$((target_count - current))
        echo "  🔥 Starting $needed BEAST MODE scrapers..."

        for i in $(seq 1 $needed); do
            scraper=${UNLIMITED_SCRAPERS[$RANDOM % ${#UNLIMITED_SCRAPERS[@]}]}
            log_name="${host}_unlimited_$(date +%s)_$i"

            ssh claude@$host "cd /mnt/aio-01/claude-orchestrator && nohup python3 tools/$scraper >/mnt/nas/web-scrape/logs/${log_name}.log 2>&1 &" 2>/dev/null &

            if [ $((i % 10)) -eq 0 ]; then sleep 1; fi
        done
    else
        echo "  ✅ OK"
    fi
}

check_and_restart_rate_limited() {
    local host=$1
    local target_count=$2

    current=$(ssh -o ConnectTimeout=3 claude@$host 'ps aux | grep python3 | grep tools | grep -v grep | wc -l' 2>/dev/null || echo 0)

    echo "[$host RATE-LIMITED] Current: $current scrapers, Target: $target_count"

    if [ $current -lt $target_count ]; then
        needed=$((target_count - current))
        echo "  ⚠️  Starting $needed rate-limited scrapers (slow)..."

        for i in $(seq 1 $needed); do
            scraper=${RATE_LIMITED_SCRAPERS[$RANDOM % ${#RATE_LIMITED_SCRAPERS[@]}]}
            log_name="${host}_ratelimit_$(date +%s)_$i"

            ssh claude@$host "cd /mnt/aio-01/claude-orchestrator && nohup python3 tools/$scraper >/mnt/nas/web-scrape/logs/${log_name}.log 2>&1 &" 2>/dev/null &

            # Extra delay between rate-limited scrapers
            if [ $((i % 3)) -eq 0 ]; then sleep 2; fi
        done
    else
        echo "  ✅ OK"
    fi
}

while true; do
    # Check current progress
    total_examples=$(wc -l /mnt/nas/web-scrape/synthetic-data/*.jsonl 2>/dev/null | tail -1 | awk '{print $1}')

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$(date): $total_examples / $TARGET examples"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [ $total_examples -ge $TARGET ]; then
        echo "🎉 TARGET REACHED! $total_examples examples!"
        break
    fi

    # Restart UNLIMITED scrapers on big machines
    for host in "${BIG_MACHINES[@]}"; do
        target=${UNLIMITED_TARGETS[$host]}
        check_and_restart_unlimited $host $target
    done

    # Restart RATE-LIMITED scrapers on small machines
    for host in "${SMALL_MACHINES[@]}"; do
        target=${RATE_LIMITED_TARGETS[$host]}
        check_and_restart_rate_limited $host $target
    done

    echo ""
    echo "Next check in 5 minutes..."
    sleep 300
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🏆 1 MILLION EXAMPLES ACHIEVED! 🏆"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
