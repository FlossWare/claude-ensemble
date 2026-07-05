#!/usr/bin/env python3
"""
CONVERSATION SCRAPER
Generates natural conversation examples for better dialogue capabilities
"""

import json
import time
import random
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'shared'))
from multi_provider_generator import MultiProviderGenerator

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Conversation topics
CONVERSATION_TOPICS = [
    # Everyday conversations
    "small talk about the weather and weekend plans",
    "discussing a recent movie you both watched",
    "catching up with a friend you haven't seen in months",
    "planning a vacation together",
    "discussing favorite books and reading habits",
    "talking about hobbies and interests",
    "debating the best pizza toppings",
    "discussing pets and funny animal stories",
    "talking about morning routines",
    "discussing favorite childhood memories",

    # Work/Professional
    "discussing a project deadline with a colleague",
    "asking for career advice from a mentor",
    "resolving a misunderstanding with a team member",
    "brainstorming ideas for a presentation",
    "discussing work-life balance",
    "giving constructive feedback to a peer",
    "negotiating a meeting time",
    "discussing professional development goals",
    "collaborating on problem-solving",
    "celebrating a team success",

    # Learning/Education
    "explaining a difficult concept to a friend",
    "asking clarifying questions in a lecture",
    "studying together for an exam",
    "discussing different learning strategies",
    "helping someone debug their code",
    "explaining why something went wrong",
    "discussing a interesting research paper",
    "teaching a skill you know well",
    "asking for help understanding a topic",
    "comparing different approaches to a problem",

    # Social situations
    "making plans to meet up",
    "declining an invitation politely",
    "introducing yourself at a party",
    "recommending a restaurant to a friend",
    "discussing gift ideas for someone",
    "planning a group outing",
    "sharing exciting news",
    "offering support to a friend",
    "asking someone about their day",
    "expressing gratitude",
]

class ConversationScraper:
    def __init__(self):
        self.generator = MultiProviderGenerator()

    def generate_conversation(self, topic):
        """Generate a natural conversation"""
        prompt = f"""Generate a natural, realistic conversation between two people about: {topic}

Make it authentic - include:
- Natural speech patterns (um, well, you know)
- Turn-taking
- Questions and answers
- Follow-up comments
- 8-12 exchanges

Format as:
Person A: [message]
Person B: [message]
..."""

        response = self.generator.generate(prompt, max_tokens=600, temperature=0.85)

        if not response:
            return None

        return {
            'input': f"Show me a conversation about {topic}",
            'output': response,
            'source': 'conversation_generation',
            'category': 'dialogue',
            'type': 'natural_conversation',
            'topic': topic
        }

    def generate_qa_from_conversation(self, topic):
        """Generate Q&A about conversation skills"""
        prompts = [
            f"How would you start a conversation about {topic}?",
            f"What questions could you ask when discussing {topic}?",
            f"How do you keep a conversation going about {topic}?",
        ]

        examples = []
        for p in prompts:
            response = self.generator.generate(p, max_tokens=200)
            if response:
                examples.append({
                    'input': p,
                    'output': response,
                    'source': 'conversation_qa',
                    'category': 'conversation_skills',
                    'topic': topic
                })

        return examples

def main():
    scraper = ConversationScraper()

    print("="*70)
    print("CONVERSATION SCRAPER")
    print("="*70)
    print(f"Topics: {len(CONVERSATION_TOPICS)}")
    print(f"Target: {len(CONVERSATION_TOPICS) * 4} examples (conv + 3 Q&A each)")
    print("="*70)

    total = 0
    all_examples = []

    for i, topic in enumerate(CONVERSATION_TOPICS, 1):
        print(f"\n[{i}/{len(CONVERSATION_TOPICS)}] Topic: {topic}")

        # Generate conversation
        conv = scraper.generate_conversation(topic)
        if conv:
            all_examples.append(conv)
            total += 1
            print(f"  ✅ Conversation generated")

        # Generate Q&A
        qas = scraper.generate_qa_from_conversation(topic)
        if qas:
            all_examples.extend(qas)
            total += len(qas)
            print(f"  ✅ {len(qas)} Q&A examples generated")

        # Save periodically
        if i % 10 == 0:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'conversations_batch_{i}_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in all_examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"  💾 Saved {len(all_examples)} examples")
            all_examples = []

        time.sleep(random.uniform(0.5, 1.0))

    # Save remaining
    if all_examples:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        data_file = DATA_DIR / f'conversations_final_{timestamp}.jsonl'

        with open(data_file, 'w') as f:
            for ex in all_examples:
                f.write(json.dumps(ex) + '\n')

        print(f"  💾 Saved {len(all_examples)} examples")

    print(f"\n{'='*70}")
    print(f"✅ COMPLETE! Generated {total} conversation examples")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
