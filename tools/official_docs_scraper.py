#!/usr/bin/env python3
"""
OFFICIAL DOCUMENTATION SCRAPER
Scrapes official language documentation (Python, Java/OpenJDK, etc.)
"""

import json
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-official-docs'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Official documentation sources
DOCS_SOURCES = [
    # Python
    {
        'name': 'Python 3 Tutorial',
        'urls': [
            'https://docs.python.org/3/tutorial/introduction.html',
            'https://docs.python.org/3/tutorial/controlflow.html',
            'https://docs.python.org/3/tutorial/datastructures.html',
            'https://docs.python.org/3/tutorial/modules.html',
            'https://docs.python.org/3/tutorial/classes.html',
            'https://docs.python.org/3/tutorial/errors.html',
            'https://docs.python.org/3/tutorial/stdlib.html',
        ]
    },

    # OpenJDK (Java SE docs)
    {
        'name': 'Java 8 Tutorials',
        'urls': [
            'https://docs.oracle.com/javase/tutorial/java/nutsandbolts/index.html',
            'https://docs.oracle.com/javase/tutorial/java/concepts/index.html',
            'https://docs.oracle.com/javase/tutorial/java/javaOO/index.html',
        ]
    },

    {
        'name': 'Java 11 Features',
        'urls': [
            'https://docs.oracle.com/en/java/javase/11/docs/api/index.html',
        ]
    },

    {
        'name': 'Java 17 Features',
        'urls': [
            'https://docs.oracle.com/en/java/javase/17/docs/api/index.html',
        ]
    },

    {
        'name': 'Java 21 Features',
        'urls': [
            'https://docs.oracle.com/en/java/javase/21/docs/api/index.html',
        ]
    },

    # Ruby
    {
        'name': 'Ruby Documentation',
        'urls': [
            'https://ruby-doc.org/core-3.0.0/doc/syntax_rdoc.html',
            'https://ruby-doc.org/core-3.0.0/Array.html',
            'https://ruby-doc.org/core-3.0.0/Hash.html',
            'https://ruby-doc.org/core-3.0.0/String.html',
            'https://ruby-doc.org/core-3.0.0/Enumerable.html',
        ]
    },

    # Prolog
    {
        'name': 'SWI-Prolog Documentation',
        'urls': [
            'https://www.swi-prolog.org/pldoc/man?section=quickstart',
            'https://www.swi-prolog.org/pldoc/man?section=lists',
            'https://www.swi-prolog.org/pldoc/man?section=builtin',
        ]
    },

    # Erlang
    {
        'name': 'Erlang Documentation',
        'urls': [
            'https://www.erlang.org/doc/getting_started/intro.html',
            'https://www.erlang.org/doc/getting_started/seq_prog.html',
            'https://www.erlang.org/doc/getting_started/conc_prog.html',
            'https://www.erlang.org/doc/reference_manual/data_types.html',
        ]
    },

    # Haskell
    {
        'name': 'Haskell Documentation',
        'urls': [
            'https://www.haskell.org/tutorial/goodies.html',
            'https://www.haskell.org/tutorial/functions.html',
            'https://www.haskell.org/tutorial/types.html',
        ]
    },

    # Lisp (Common Lisp)
    {
        'name': 'Common Lisp HyperSpec',
        'urls': [
            'http://www.lispworks.com/documentation/HyperSpec/Body/01_ab.htm',
            'http://www.lispworks.com/documentation/HyperSpec/Body/03_.htm',
            'http://www.lispworks.com/documentation/HyperSpec/Body/04_.htm',
        ]
    },

    # C# (.NET)
    {
        'name': 'C# Documentation',
        'urls': [
            'https://learn.microsoft.com/en-us/dotnet/csharp/tour-of-csharp/',
            'https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/types/',
            'https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/object-oriented/',
            'https://learn.microsoft.com/en-us/dotnet/csharp/asynchronous-programming/',
        ]
    },

    # Smalltalk
    {
        'name': 'Pharo Smalltalk',
        'urls': [
            'https://pharo.org/documentation',
        ]
    },

    # BeanShell
    {
        'name': 'BeanShell Documentation',
        'urls': [
            'https://www.beanshell.org/manual/bshmanual.html',
        ]
    },

    # MVEL
    {
        'name': 'MVEL Documentation',
        'urls': [
            'http://mvel.documentnode.com/',
        ]
    },

    # XSLT
    {
        'name': 'XSLT W3C Specification',
        'urls': [
            'https://www.w3.org/TR/xslt-30/',
            'https://www.w3.org/TR/xslt20/',
        ]
    },

    # XPath
    {
        'name': 'XPath W3C Specification',
        'urls': [
            'https://www.w3.org/TR/xpath-31/',
            'https://www.w3.org/TR/xpath-30/',
        ]
    },

    # XSD (XML Schema)
    {
        'name': 'XML Schema W3C',
        'urls': [
            'https://www.w3.org/TR/xmlschema11-1/',
            'https://www.w3.org/TR/xmlschema-0/',
        ]
    },

    # BPEL
    {
        'name': 'BPEL Specification',
        'urls': [
            'http://docs.oasis-open.org/wsbpel/2.0/wsbpel-v2.0.html',
        ]
    },

    # Ansible
    {
        'name': 'Ansible Documentation',
        'urls': [
            'https://docs.ansible.com/ansible/latest/getting_started/index.html',
            'https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_intro.html',
            'https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html',
            'https://docs.ansible.com/ansible/latest/collections/index.html',
        ]
    },

    # GitLab
    {
        'name': 'GitLab Documentation',
        'urls': [
            'https://docs.gitlab.com/ee/user/',
            'https://docs.gitlab.com/ee/ci/',
            'https://docs.gitlab.com/ee/administration/',
        ]
    },

    # Nexus Repository
    {
        'name': 'Nexus Repository Documentation',
        'urls': [
            'https://help.sonatype.com/repomanager3',
        ]
    },

    # Puppet
    {
        'name': 'Puppet Documentation',
        'urls': [
            'https://www.puppet.com/docs/puppet/latest/puppet_index.html',
            'https://www.puppet.com/docs/puppet/latest/lang_summary.html',
            'https://www.puppet.com/docs/puppet/latest/modules_fundamentals.html',
        ]
    },

    # Chef
    {
        'name': 'Chef Documentation',
        'urls': [
            'https://docs.chef.io/platform_overview/',
            'https://docs.chef.io/recipes/',
            'https://docs.chef.io/cookbooks/',
        ]
    },

    # Salt (SaltStack)
    {
        'name': 'SaltStack Documentation',
        'urls': [
            'https://docs.saltproject.io/en/latest/topics/index.html',
            'https://docs.saltproject.io/en/latest/topics/tutorials/walkthrough.html',
            'https://docs.saltproject.io/en/latest/ref/states/index.html',
        ]
    },

    # DD-WRT
    {
        'name': 'DD-WRT Documentation',
        'urls': [
            'https://wiki.dd-wrt.com/wiki/index.php/Main_Page',
            'https://wiki.dd-wrt.com/wiki/index.php/Installation',
            'https://wiki.dd-wrt.com/wiki/index.php/Tutorials',
        ]
    },

    # OpenWrt
    {
        'name': 'OpenWrt Documentation',
        'urls': [
            'https://openwrt.org/docs/start',
            'https://openwrt.org/docs/guide-user/start',
            'https://openwrt.org/docs/guide-developer/start',
        ]
    },
]

class OfficialDocsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Educational Research Bot 1.0'
        })

    def scrape_page(self, url, source_name):
        """Scrape a documentation page"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find main content (different sites use different tags)
            main = (
                soup.find('main') or
                soup.find('article') or
                soup.find('div', class_='document') or
                soup.find('div', id='content') or
                soup.find('body')
            )

            if not main:
                return None

            # Remove navigation, scripts, styles
            for tag in main(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()

            text = main.get_text(separator='\n', strip=True)
            return text[:3000]  # First 3000 chars

        except Exception as e:
            print(f"    ⚠️  Error: {e}")
            return None

    def scrape(self, max_sources=None):
        """Scrape official documentation"""
        print("="*70)
        print("OFFICIAL DOCS SCRAPER - LANGUAGE DOCUMENTATION")
        print("="*70)
        print(f"Sources: {len(DOCS_SOURCES)}")
        print("="*70)

        examples = []
        total_pages = 0

        for source in DOCS_SOURCES[:max_sources] if max_sources else DOCS_SOURCES:
            print(f"\n📚 {source['name']}")
            print(f"   Pages: {len(source['urls'])}")

            for i, url in enumerate(source['urls'], 1):
                print(f"   [{i}/{len(source['urls'])}] {url.split('/')[-1][:40]}...")

                content = self.scrape_page(url, source['name'])
                if not content:
                    continue

                example = {
                    'input': f"{source['name']}: {url.split('/')[-1].replace('.html', '').replace('index', 'overview')}",
                    'output': content,
                    'source': 'official_docs',
                    'category': 'programming_language',
                    'language': source['name'].split()[0].lower(),
                    'url': url
                }
                examples.append(example)
                total_pages += 1

                print(f"     ✅ {len(content)} chars")

                time.sleep(1)  # Rate limiting

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'official_docs_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {total_pages} documentation pages")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-sources', type=int, default=None, help='Max sources')

    args = parser.parse_args()

    scraper = OfficialDocsScraper()
    scraper.scrape(args.max_sources)

if __name__ == '__main__':
    main()
