#!/usr/bin/env python3
"""
ULTIMATE TRAINING DATA SCRAPER
Scrapes from EVERY major free source of knowledge

Sources:
1. arXiv (research papers) - DONE
2. PubMed Central (medical papers) - NEW
3. Stack Overflow (Q&A) - NEW
4. GitHub (READMEs, docs) - NEW
5. Wikipedia (encyclopedic knowledge) - NEW
6. OpenStax (textbooks) - NEW
7. MIT OpenCourseWare - NEW
"""

import os
import json
import requests
import time
from datetime import datetime
from bs4 import BeautifulSoup

OUTPUT_DIR = os.path.expanduser('~/.claude/ml-training/synthetic-data')
CLOUDFLARE_URL = f"https://api.cloudflare.com/client/v4/accounts/{os.getenv('PERSONAL_CLOUDFLARE_ACCOUNT_ID', '')}/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast"
CLOUDFLARE_KEY = os.getenv('PERSONAL_CLOUDFLARE_API_KEY', '')

class UltimateDataScraper:
    """Scrape ALL major knowledge sources"""

    def __init__(self):
        self.stats = {'total': 0, 'by_source': {}}

    def generate_completion(self, prompt):
        """Generate with Cloudflare"""
        try:
            r = requests.post(
                CLOUDFLARE_URL,
                headers={'Authorization': f'Bearer {CLOUDFLARE_KEY}', 'Content-Type': 'application/json'},
                json={'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 512},
                timeout=30
            )
            if r.status_code == 200:
                return r.json()['result']['response']
        except:
            pass
        return None

    def scrape_pubmed(self, query, max_results=100):
        """
        Scrape PubMed Central (10M+ free medical papers!)

        API: https://www.ncbi.nlm.nih.gov/pmc/tools/developers/
        """
        print(f"\n🏥 Scraping PubMed Central: {query}")

        # Search PMC
        search_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
        params = {
            'db': 'pmc',
            'term': query,
            'retmax': max_results,
            'retmode': 'json'
        }

        try:
            response = requests.get(search_url, params=params, timeout=10)
            data = response.json()
            pmc_ids = data.get('esearchresult', {}).get('idlist', [])

            print(f"  Found {len(pmc_ids)} articles")

            dataset = []
            for i, pmc_id in enumerate(pmc_ids[:20]):  # Limit to 20 for speed
                # Fetch abstract
                fetch_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
                params = {
                    'db': 'pmc',
                    'id': pmc_id,
                    'retmode': 'xml'
                }

                response = requests.get(fetch_url, params=params, timeout=10)

                # Parse XML for title and abstract
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.find('article-title')
                abstract = soup.find('abstract')

                if title and abstract:
                    title_text = title.get_text()
                    abstract_text = abstract.get_text()[:500]

                    prompt = f"Explain this medical research in simple terms:\n\nTitle: {title_text}\n\n{abstract_text}"
                    completion = self.generate_completion(prompt)

                    if completion:
                        dataset.append({
                            'prompt': prompt,
                            'completion': completion,
                            'source': 'PubMed Central',
                            'pmc_id': pmc_id,
                            'title': title_text
                        })

                if (i + 1) % 5 == 0:
                    print(f"    Progress: {i+1}/20")

                time.sleep(0.5)  # Rate limit

            return dataset

        except Exception as e:
            print(f"  Error: {e}")
            return []

    def scrape_stackoverflow(self, tag, max_questions=50):
        """
        Scrape Stack Overflow Q&A

        API: https://api.stackexchange.com/docs
        """
        print(f"\n💻 Scraping Stack Overflow: {tag}")

        url = 'https://api.stackexchange.com/2.3/questions'
        params = {
            'order': 'desc',
            'sort': 'votes',
            'tagged': tag,
            'site': 'stackoverflow',
            'pagesize': max_questions,
            'filter': 'withbody'
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            questions = data.get('items', [])

            print(f"  Found {len(questions)} questions")

            dataset = []
            for i, q in enumerate(questions[:20]):  # Limit to 20
                title = q.get('title', '')
                body = BeautifulSoup(q.get('body', ''), 'html.parser').get_text()[:400]

                prompt = f"Answer this programming question:\n\nQ: {title}\n\nDetails: {body}"
                completion = self.generate_completion(prompt)

                if completion:
                    dataset.append({
                        'prompt': prompt,
                        'completion': completion,
                        'source': 'Stack Overflow',
                        'tag': tag,
                        'votes': q.get('score', 0)
                    })

                if (i + 1) % 5 == 0:
                    print(f"    Progress: {i+1}/20")

                time.sleep(1)  # Respect rate limits

            return dataset

        except Exception as e:
            print(f"  Error: {e}")
            return []

    def scrape_wikipedia(self, topics, articles_per_topic=10):
        """
        Scrape Wikipedia articles

        API: https://en.wikipedia.org/w/api.php
        """
        print(f"\n📖 Scraping Wikipedia: {topics}")

        dataset = []

        for topic in topics:
            # Search Wikipedia
            search_url = 'https://en.wikipedia.org/w/api.php'
            params = {
                'action': 'opensearch',
                'search': topic,
                'limit': articles_per_topic,
                'format': 'json'
            }

            try:
                response = requests.get(search_url, params=params, timeout=10)
                data = response.json()
                titles = data[1] if len(data) > 1 else []

                for title in titles[:5]:  # Limit to 5
                    # Get article content
                    params = {
                        'action': 'query',
                        'prop': 'extracts',
                        'exintro': True,
                        'explaintext': True,
                        'titles': title,
                        'format': 'json'
                    }

                    response = requests.get(search_url, params=params, timeout=10)
                    data = response.json()
                    pages = data.get('query', {}).get('pages', {})

                    for page_id, page_data in pages.items():
                        extract = page_data.get('extract', '')[:500]

                        if extract:
                            prompt = f"Explain this concept from Wikipedia:\n\n{title}\n\n{extract}"
                            completion = self.generate_completion(prompt)

                            if completion:
                                dataset.append({
                                    'prompt': prompt,
                                    'completion': completion,
                                    'source': 'Wikipedia',
                                    'topic': topic,
                                    'title': title
                                })

                    time.sleep(0.3)

                print(f"  ✓ {topic}: {len([d for d in dataset if d['topic'] == topic])} articles")

            except Exception as e:
                print(f"  Error on {topic}: {e}")

        return dataset

    def save_dataset(self, dataset, filename):
        """Save dataset to JSONL"""
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        filepath = os.path.join(OUTPUT_DIR, filename)

        with open(filepath, 'w') as f:
            for item in dataset:
                f.write(json.dumps(item) + '\n')

        print(f"\n✅ Saved {len(dataset)} examples to {filepath}")
        return filepath


    def scrape_rfc(self, rfc_numbers):
        """
        Scrape RFCs (Request for Comments)

        RFCs are the OFFICIAL internet specifications!
        - TCP/IP (RFC 793, 791)
        - HTTP (RFC 2616, 7540)
        - DNS (RFC 1035)
        - etc.

        Source: https://www.rfc-editor.org/
        """
        print(f"\n📋 Scraping RFCs (Internet Standards)")

        dataset = []

        for rfc_num in rfc_numbers:
            try:
                # Fetch RFC text
                url = f'https://www.rfc-editor.org/rfc/rfc{rfc_num}.txt'
                response = requests.get(url, timeout=10)

                if response.status_code == 200:
                    text = response.text[:2000]  # First 2000 chars

                    prompt = f"Explain RFC {rfc_num} - what internet standard does it define and why is it important?\n\n{text}"
                    completion = self.generate_completion(prompt)

                    if completion:
                        dataset.append({
                            'prompt': prompt,
                            'completion': completion,
                            'source': 'RFC',
                            'rfc_number': rfc_num,
                            'url': url
                        })

                        print(f"  ✓ RFC {rfc_num}")

                time.sleep(0.5)

            except Exception as e:
                print(f"  Error on RFC {rfc_num}: {e}")

        return dataset

    def scrape_github_readmes(self, repos):
        """
        Scrape GitHub README files

        repos: list of 'owner/repo' strings
        """
        print(f"\n🐙 Scraping GitHub READMEs")

        dataset = []

        for repo in repos:
            try:
                # GitHub API
                url = f'https://api.github.com/repos/{repo}/readme'
                headers = {'Accept': 'application/vnd.github.v3.raw'}

                response = requests.get(url, headers=headers, timeout=10)

                if response.status_code == 200:
                    readme = response.text[:1500]

                    prompt = f"Explain this open-source project:\n\nRepository: {repo}\n\n{readme}"
                    completion = self.generate_completion(prompt)

                    if completion:
                        dataset.append({
                            'prompt': prompt,
                            'completion': completion,
                            'source': 'GitHub',
                            'repo': repo
                        })

                        print(f"  ✓ {repo}")

                time.sleep(1)  # Rate limit

            except Exception as e:
                print(f"  Error on {repo}: {e}")

        return dataset


# Predefined topics for each source
PUBMED_QUERIES = [
    'covid-19 treatment',
    'cancer immunotherapy',
    'alzheimer disease',
    'diabetes treatment',
    'cardiac surgery'
]

STACKOVERFLOW_TAGS = [
    'python',
    'javascript',
    'machine-learning',
    'kubernetes',
    'postgresql'
]

WIKIPEDIA_TOPICS = [
    'artificial intelligence',
    'quantum mechanics',
    'general relativity',
    'molecular biology',
    'computer architecture'
]

# Important RFCs (Internet Standards)
RFC_NUMBERS = [
    793,   # TCP
    791,   # IP
    2616,  # HTTP/1.1
    7540,  # HTTP/2
    1035,  # DNS
    5321,  # SMTP
    8446,  # TLS 1.3
    6749,  # OAuth 2.0
    8259,  # JSON
    6455,  # WebSocket
    7231,  # HTTP Semantics
    3986,  # URI
    2818,  # HTTPS
    5246,  # TLS 1.2
    4627,  # SSH
]

# Popular GitHub repos
GITHUB_REPOS = [
    'kubernetes/kubernetes',
    'docker/docker',
    'pytorch/pytorch',
    'tensorflow/tensorflow',
    'facebook/react',
    'nodejs/node',
    'microsoft/vscode',
    'golang/go',
    'rust-lang/rust',
    'python/cpython'
]


if __name__ == '__main__':
    import sys

    scraper = UltimateDataScraper()

    source = sys.argv[1] if len(sys.argv) > 1 else 'all'

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🌟 ULTIMATE DATA SCRAPER")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    all_data = []

    if source in ['pubmed', 'all']:
        for query in PUBMED_QUERIES:
            data = scraper.scrape_pubmed(query, 50)
            all_data.extend(data)

    if source in ['stackoverflow', 'all']:
        for tag in STACKOVERFLOW_TAGS:
            data = scraper.scrape_stackoverflow(tag, 50)
            all_data.extend(data)

    if source in ['wikipedia', 'all']:
        data = scraper.scrape_wikipedia(WIKIPEDIA_TOPICS, 10)
        all_data.extend(data)

    if source in ['rfc', 'all']:
        data = scraper.scrape_rfc(RFC_NUMBERS)
        all_data.extend(data)

    if source in ['github', 'all']:
        data = scraper.scrape_github_readmes(GITHUB_REPOS)
        all_data.extend(data)

    if all_data:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        scraper.save_dataset(all_data, f'ultimate_{source}_{len(all_data)}_{timestamp}.jsonl')

    print("\n🎉 ULTIMATE DATA COLLECTION COMPLETE!")
    print(f"Total examples: {len(all_data)}")
