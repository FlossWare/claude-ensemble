#!/usr/bin/env bash
#
# MONITOR ALL TRAINING & SCRAPING PROCESSES
# Shows live status of model training, books processing, and paper scraping
#

clear

while true; do
    clear
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🤖 LLM TRAINING & DATA COLLECTION - LIVE MONITOR"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    date
    echo ""

    # Storage status
    echo "📁 STORAGE (/mnt/nas/web-scrape/):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    du -sh /mnt/nas/web-scrape/* 2>/dev/null | column -t
    echo ""
    echo "Training examples: $(wc -l /mnt/nas/web-scrape/synthetic-data/*.jsonl 2>/dev/null | tail -1 | awk '{print $1}')"
    echo "Raw papers stored: $(ls /mnt/nas/web-scrape/raw-papers/*.json 2>/dev/null | wc -l)"
    echo ""

    # Model training
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🧠 MODEL TRAINING (Mamba 100M - 78.7M params):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if ps aux | grep -v grep | grep train_mamba_100M > /dev/null; then
        echo "Status: ✅ RUNNING"
        tail -3 /mnt/nas/web-scrape/logs/training.log 2>&1 | head -2
    else
        echo "Status: ❌ NOT RUNNING"
    fi
    echo ""

    # Books processing
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📚 BOOKS PROCESSING (849 PDFs → Training Data):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if ps aux | grep -v grep | grep books_to_training_data > /dev/null; then
        echo "Status: ✅ RUNNING"
        if [ -f /mnt/nas/web-scrape/processed_books.json ]; then
            processed=$(cat /mnt/nas/web-scrape/processed_books.json | jq -r '.count' 2>/dev/null || echo "0")
            echo "Books processed: $processed / 100"
        fi
        tail -2 /mnt/nas/web-scrape/logs/books_generation.log 2>&1
    else
        echo "Status: ⏸️  IDLE"
    fi
    echo ""

    # Paper scraping
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📄 PAPER SCRAPING (Multi-provider with storage):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    scrapers=$(ps aux | grep -v grep | grep arxiv_scraper_with_storage | wc -l)
    echo "Active scrapers: $scrapers"
    if [ -f /mnt/nas/web-scrape/processed_papers.json ]; then
        papers=$(cat /mnt/nas/web-scrape/processed_papers.json | jq -r '.count' 2>/dev/null || echo "0")
        echo "Papers processed: $papers"
    fi
    tail -2 /mnt/nas/web-scrape/logs/scrape_*.log 2>&1 | head -4
    echo ""

    # System resources
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "💻 SYSTEM RESOURCES:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "CPU: $(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1"%"}')"
    echo "RAM: $(free -h | grep Mem | awk '{print $3 "/" $2}')"
    echo ""
    echo "Press Ctrl+C to exit"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    sleep 10
done
