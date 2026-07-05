#!/usr/bin/env python3
"""
RFC SCRAPER
Scrapes IETF RFCs (Internet standards, protocols, specifications)
NO API calls - just download and chunk text!
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-rfcs'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Important RFCs to scrape
IMPORTANT_RFCS = [
    # Core Internet
    791,   # IP
    792,   # ICMP
    793,   # TCP
    826,   # ARP
    768,   # UDP
    2460,  # IPv6

    # HTTP
    7230,  # HTTP/1.1 Message Syntax
    7231,  # HTTP/1.1 Semantics
    7540,  # HTTP/2
    9114,  # HTTP/3

    # DNS
    1034,  # DNS Concepts
    1035,  # DNS Implementation

    # Email
    5321,  # SMTP
    3501,  # IMAP
    1939,  # POP3

    # Security
    8446,  # TLS 1.3
    6749,  # OAuth 2.0
    7519,  # JWT
    8252,  # OAuth for Native Apps

    # Web
    6455,  # WebSocket
    7469,  # HPKP
    6797,  # HSTS

    # More protocols
    959,   # FTP
    854,   # Telnet
    1945,  # SSH
    2616,  # HTTP/1.1 (old but important)
]

class RFCScraper:
    def __init__(self):
        self.session = requests.Session()

    def get_rfc(self, rfc_num):
        """Download RFC text"""
        url = f"https://www.rfc-editor.org/rfc/rfc{rfc_num}.txt"

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None

    def chunk_rfc(self, text, chunk_size=1000):
        """Split RFC into chunks"""
        lines = text.split('\n')

        # Skip header (first ~50 lines usually)
        content_start = 0
        for i, line in enumerate(lines):
            if 'Abstract' in line or 'Introduction' in line:
                content_start = i
                break

        content = '\n'.join(lines[content_start:])

        words = content.split()
        chunks = []

        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            if len(chunk) > 300:
                chunks.append(chunk)

        return chunks

    def scrape_rfc(self, rfc_num):
        """Scrape a single RFC"""
        print(f"\n[RFC {rfc_num}]")

        # Download
        text = self.get_rfc(rfc_num)
        if not text:
            return 0

        print(f"  ✅ Downloaded ({len(text)} chars)")

        # Save raw
        raw_file = RAW_DIR / f"rfc{rfc_num}.txt"
        with open(raw_file, 'w') as f:
            f.write(text)
        print(f"  💾 Saved raw: {raw_file.name}")

        # Chunk
        chunks = self.chunk_rfc(text)
        print(f"  🔪 Created {len(chunks)} chunks")

        # Create training examples (NO API calls!)
        examples = []
        for i, chunk in enumerate(chunks[:15], 1):  # Max 15 chunks per RFC
            example = {
                'input': f"Explain RFC {rfc_num} section:",
                'output': chunk,
                'source': 'rfc',
                'category': 'internet_standards',
                'rfc_number': rfc_num,
                'chunk_num': i
            }
            examples.append(example)

        # Save
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        data_file = DATA_DIR / f'rfc_{rfc_num}_{timestamp}.jsonl'

        with open(data_file, 'w') as f:
            for ex in examples:
                f.write(json.dumps(ex) + '\n')

        print(f"  ✅ Saved {len(examples)} examples")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-rfcs', type=int, default=50, help='Max RFCs to scrape')

    args = parser.parse_args()

    scraper = RFCScraper()

    print("="*70)
    print("RFC SCRAPER - INTERNET STANDARDS")
    print("="*70)
    print(f"RFCs to scrape: {len(IMPORTANT_RFCS)}")
    print(f"Max: {args.max_rfcs}")
    print("NO API calls - just download and chunk!")
    print("="*70)

    total = 0

    for rfc_num in IMPORTANT_RFCS[:args.max_rfcs]:
        count = scraper.scrape_rfc(rfc_num)
        total += count
        time.sleep(1)  # Be nice to server

    print(f"\n{'='*70}")
    print(f"✅ COMPLETE! Scraped {min(len(IMPORTANT_RFCS), args.max_rfcs)} RFCs")
    print(f"Generated {total} training examples")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
