#!/usr/bin/env python3
"""
arXiv Research Paper Scraper for LLM Training
Scrapes AI/ML papers and generates training data
"""

import json
import requests
import time
import os
from datetime import datetime
import xml.etree.ElementTree as ET
from pathlib import Path

OUTPUT_DIR = os.path.expanduser('~/.claude/ml-training/synthetic-data')

class ArxivPaperScraper:
    """Scrape arXiv papers and create training data"""

    def __init__(self):
        self.arxiv_api = 'https://export.arxiv.org/api/query'
        self.cloudflare_url = 'https://api.cloudflare.com/client/v4/accounts/c38a4493830b64dceec5f528043bd3ac/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast'

        # SECURITY FIX: Use environment variable for API key instead of hardcoded value
        self.cloudflare_key = os.environ.get('CLOUDFLARE_API_KEY')
        if not self.cloudflare_key:
            raise ValueError("CLOUDFLARE_API_KEY environment variable not set")

    def search_arxiv(self, query: str, max_results: int = 100):
        """
        Search arXiv for papers

        Popular AI/ML categories:
        - cs.AI: Artificial Intelligence
        - cs.LG: Machine Learning
        - cs.NE: Neural and Evolutionary Computing
        - stat.ML: Machine Learning (statistics)
        """

        params = {
            'search_query': query,
            'start': 0,
            'max_results': max_results,
            'sortBy': 'relevance',
            'sortOrder': 'descending'
        }

        try:
            response = requests.get(self.arxiv_api, params=params, timeout=30)

            if response.status_code == 200:
                return self.parse_arxiv_response(response.text)
        except Exception as e:
            print(f"Error searching arXiv: {e}")

        return []

    def parse_arxiv_response(self, xml_text: str):
        """Parse arXiv XML response"""
        papers = []

        root = ET.fromstring(xml_text)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        for entry in root.findall('atom:entry', ns):
            try:
                paper = {
                    'title': entry.find('atom:title', ns).text.strip(),
                    'summary': entry.find('atom:summary', ns).text.strip(),
                    'authors': [author.find('atom:name', ns).text
                               for author in entry.findall('atom:author', ns)],
                    'link': entry.find('atom:id', ns).text,
                    'published': entry.find('atom:published', ns).text[:10]
                }
                papers.append(paper)
            except Exception as e:
                print(f"Warning: Failed to parse paper entry: {e}")
                continue

        return papers

    def generate_with_cloudflare(self, prompt: str) -> str:
        """Generate completion using Cloudflare"""
        headers = {
            'Authorization': f'Bearer {self.cloudflare_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 512
        }

        try:
            response = requests.post(self.cloudflare_url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                return response.json()['result']['response']
        except Exception as e:
            print(f"Warning: Cloudflare API request failed: {e}")
        return None

    def create_training_examples(self, papers: list, output_file: str):
        """Create training examples from research papers"""

        print(f"\n📚 RESEARCH PAPER TRAINING DATA GENERATION")
        print(f"{'='*70}")
        print(f"Papers: {len(papers)}")
        print(f"Output: {output_file}")
        print(f"{'='*70}\n")

        dataset = []

        for i, paper in enumerate(papers):
            print(f"  [{i+1}/{len(papers)}] {paper['title'][:60]}...")

            # Strategy 1: Explain the paper
            prompt1 = f"""Explain this AI/ML research paper in simple terms:

Title: {paper['title']}
Authors: {', '.join(paper['authors'][:3])}

Abstract: {paper['summary'][:500]}

Provide a 2-3 sentence explanation for someone learning AI/ML:"""

            completion1 = self.generate_with_cloudflare(prompt1)
            if completion1:
                dataset.append({
                    'prompt': prompt1,
                    'completion': completion1,
                    'source': paper['link'],
                    'paper_title': paper['title'],
                    'type': 'paper_explanation'
                })

            # Strategy 2: Extract key concepts
            prompt2 = f"""What are the key concepts and techniques in this paper?

Title: {paper['title']}
Abstract: {paper['summary'][:400]}

List the main technical concepts:"""

            completion2 = self.generate_with_cloudflare(prompt2)
            if completion2:
                dataset.append({
                    'prompt': prompt2,
                    'completion': completion2,
                    'source': paper['link'],
                    'paper_title': paper['title'],
                    'type': 'key_concepts'
                })

            print(f"    ✓ Generated 2 examples")
            time.sleep(1)  # Rate limit

        # ATOMIC SAVE FIX: Use .tmp + rename pattern for output file
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        tmp_output = output_file + '.tmp'

        with open(tmp_output, 'w') as f:
            for ex in dataset:
                f.write(json.dumps(ex) + '\n')

        # Atomic rename
        Path(tmp_output).replace(output_file)

        print(f"\n✅ Generated {len(dataset)} examples from {len(papers)} papers")
        print(f"📁 Saved to: {output_file}")

        return output_file


# Research topics to scrape
RESEARCH_TOPICS = {
    'transformers': 'cat:cs.LG AND (transformer OR attention OR BERT OR GPT)',
    'neural_nets': 'cat:cs.LG AND (neural network OR deep learning OR CNN)',
    'genetic_algorithms': 'cat:cs.NE AND (genetic algorithm OR evolutionary)',
    'reinforcement_learning': 'cat:cs.LG AND (reinforcement learning OR RL OR DQN)',
    'gan': 'cat:cs.LG AND (GAN OR generative adversarial)',
    'diffusion': 'cat:cs.LG AND (diffusion model OR stable diffusion)',
    'optimization': 'cat:cs.LG AND (optimization OR gradient descent)',
    'mamba_ssm': 'cat:cs.LG AND (state space model OR Mamba OR SSM)',
}


if __name__ == '__main__':
    import sys

    scraper = ArxivPaperScraper()

    topic = sys.argv[1] if len(sys.argv) > 1 else 'transformers'
    num_papers = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    if topic in RESEARCH_TOPICS:
        query = RESEARCH_TOPICS[topic]
    else:
        query = f'cat:cs.LG AND {topic}'

    print(f"\n🔬 Searching arXiv for: {topic}")
    print(f"Query: {query}")
    print(f"Target: {num_papers} papers\n")

    papers = scraper.search_arxiv(query, max_results=num_papers)

    print(f"✓ Found {len(papers)} papers\n")

    if papers:
        # Show sample
        print("📄 Sample paper:")
        print(f"  Title: {papers[0]['title']}")
        print(f"  Authors: {', '.join(papers[0]['authors'][:3])}")
        print(f"  Link: {papers[0]['link']}")
        print()

        output_file = os.path.join(OUTPUT_DIR, f'arxiv_{topic}_{len(papers)}.jsonl')
        scraper.create_training_examples(papers, output_file)

        print("\n🎓 Your model will now be an expert in this research area!")
