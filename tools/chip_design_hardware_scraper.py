#!/usr/bin/env python3
"""
CHIP DESIGN & HARDWARE SCRAPER
Scrapes VLSI, chip design, hardware architecture content
- Wikipedia VLSI/hardware topics
- arXiv hardware papers
- ChipVerify tutorials (if accessible)
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-chip-design'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Hardware/VLSI topics
HARDWARE_TOPICS = [
    'VLSI', 'ASIC', 'FPGA', 'Verilog', 'VHDL', 'SystemVerilog',
    'RTL design', 'Logic synthesis', 'Place and route',
    'Static timing analysis', 'Clock domain crossing',
    'Flip-flop', 'Latch', 'Multiplexer', 'Decoder', 'Encoder',
    'Adder', 'Multiplier', 'ALU', 'Memory (computer)',
    'SRAM', 'DRAM', 'Flash memory', 'ROM',
    'CPU architecture', 'GPU architecture', 'RISC', 'CISC',
    'Pipelining', 'Cache coherence', 'Memory hierarchy',
    'Bus (computing)', 'I2C', 'SPI', 'UART', 'PCIe',
    'ARM architecture', 'x86 architecture', 'RISC-V',
    'SystemC', 'UVM', 'Verification', 'DFT', 'BIST',
]

# arXiv hardware categories
ARXIV_HW_CATEGORIES = [
    'cs.AR',  # Hardware Architecture
]

class ChipDesignScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Educational Research Bot 1.0'
        })

    def scrape_wikipedia_topic(self, topic):
        """Scrape Wikipedia article"""
        url = f'https://en.wikipedia.org/api/rest_v1/page/summary/{topic}'

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            extract = data.get('extract', '')
            if len(extract) < 100:
                return None

            return extract
        except:
            return None

    def scrape_arxiv(self, category, max_results=100):
        """Search arXiv for hardware papers"""
        base_url = 'http://export.arxiv.org/api/query'

        params = {
            'search_query': f'cat:{category}',
            'start': 0,
            'max_results': max_results,
            'sortBy': 'relevance',
            'sortOrder': 'descending'
        }

        try:
            response = self.session.get(base_url, params=params, timeout=30)
            response.raise_for_status()

            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)

            papers = []
            for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
                summary_elem = entry.find('{http://www.w3.org/2005/Atom}summary')

                if title_elem is not None and summary_elem is not None:
                    papers.append({
                        'title': title_elem.text.strip(),
                        'abstract': summary_elem.text.strip()
                    })

            return papers
        except Exception as e:
            print(f"  ❌ arXiv Error: {e}")
            return []

    def scrape(self, max_wiki_topics=40, max_arxiv=100):
        """Scrape chip design content"""
        print("="*70)
        print("CHIP DESIGN & HARDWARE ARCHITECTURE SCRAPER")
        print("="*70)
        print(f"Wikipedia topics: {min(len(HARDWARE_TOPICS), max_wiki_topics)}")
        print(f"arXiv papers: {max_arxiv}")
        print("="*70)

        examples = []

        # Wikipedia
        print("\n🔬 Wikipedia Hardware Topics:")
        for i, topic in enumerate(HARDWARE_TOPICS[:max_wiki_topics], 1):
            if i % 10 == 0:
                print(f"  [{i}/{min(len(HARDWARE_TOPICS), max_wiki_topics)}] Progress...")

            content = self.scrape_wikipedia_topic(topic)
            if not content:
                continue

            example = {
                'input': f"Explain {topic} in chip design and hardware",
                'output': content,
                'source': 'wikipedia_hardware',
                'category': 'chip_design',
                'topic': topic
            }
            examples.append(example)

            time.sleep(1)

        print(f"  ✅ Scraped {len(examples)} topics")

        # arXiv
        print("\n📄 arXiv Hardware Architecture Papers:")
        papers = self.scrape_arxiv('cs.AR', max_arxiv)
        print(f"  ✅ {len(papers)} papers")

        for paper in papers:
            example = {
                'input': f"Research paper: {paper['title']}",
                'output': paper['abstract'][:2000],
                'source': 'arxiv_hardware',
                'category': 'hardware_research'
            }
            examples.append(example)

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'chip_design_hardware_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} hardware examples")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-wiki-topics', type=int, default=40, help='Max Wikipedia topics')
    parser.add_argument('--max-arxiv', type=int, default=100, help='Max arXiv papers')

    args = parser.parse_args()

    scraper = ChipDesignScraper()
    scraper.scrape(args.max_wiki_topics, args.max_arxiv)

if __name__ == '__main__':
    main()
