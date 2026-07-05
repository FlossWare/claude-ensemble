#!/usr/bin/env python3
"""
MIT OPENCOURSEWARE SCRAPER
Scrapes course materials from MIT OCW
Uses web scraping (publicly available educational content)
"""

import json
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-mit-ocw'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Popular courses (course URLs)
MIT_COURSES = [
    # CS
    ('6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016', 'Intro to CS (Python)'),
    ('6-006-introduction-to-algorithms-fall-2011', 'Algorithms'),
    ('6-046j-design-and-analysis-of-algorithms-spring-2015', 'Algorithm Design'),

    # Math
    ('18-01sc-single-variable-calculus-fall-2010', 'Calculus'),
    ('18-06-linear-algebra-spring-2010', 'Linear Algebra'),
    ('6-041-probabilistic-systems-analysis-and-applied-probability-fall-2010', 'Probability'),

    # AI/ML
    ('6-034-artificial-intelligence-fall-2010', 'Artificial Intelligence'),
    ('6-867-machine-learning-fall-2006', 'Machine Learning'),

    # Other
    ('14-01sc-principles-of-microeconomics-fall-2011', 'Microeconomics'),
    ('8-01sc-classical-mechanics-fall-2016', 'Classical Mechanics'),
]

class MITOCWScraper:
    def __init__(self):
        self.base_url = 'https://ocw.mit.edu/courses'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Educational Research Bot 1.0'
        })

    def scrape_course(self, course_url, course_name):
        """Scrape a single course"""
        url = f'{self.base_url}/{course_url}/'

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find course description
            description = soup.find('div', class_='course-description')
            if not description:
                # Try alternative selectors
                description = soup.find('section', id='course-description')

            if not description:
                return None

            # Extract text
            for script in description(['script', 'style']):
                script.decompose()

            text = description.get_text(separator='\n', strip=True)

            return text[:2000]  # First 2000 chars

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None

    def scrape(self, max_courses=10):
        """Scrape MIT OCW courses"""
        print("="*70)
        print("MIT OPENCOURSEWARE SCRAPER - UNIVERSITY COURSES")
        print("="*70)
        print(f"Courses: {min(len(MIT_COURSES), max_courses)}")
        print("="*70)

        examples = []

        for i, (course_url, course_name) in enumerate(MIT_COURSES[:max_courses], 1):
            print(f"\n[{i}/{min(len(MIT_COURSES), max_courses)}] {course_name}")

            content = self.scrape_course(course_url, course_name)
            if not content:
                continue

            example = {
                'input': f"What is covered in MIT's {course_name} course?",
                'output': content,
                'source': 'mit_ocw',
                'category': 'university_course',
                'course': course_name
            }
            examples.append(example)

            print(f"  ✅ Scraped {len(content)} chars")

            time.sleep(3)  # Be very polite to MIT servers

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'mit_ocw_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} courses")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-courses', type=int, default=10, help='Max courses to scrape')

    args = parser.parse_args()

    scraper = MITOCWScraper()
    scraper.scrape(args.max_courses)

if __name__ == '__main__':
    main()
