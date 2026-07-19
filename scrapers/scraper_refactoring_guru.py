#!/usr/bin/env python3
"""Refactoring Guru documentation scraper.

Covers:
  - Design patterns (creational, structural, behavioral)
  - Refactoring techniques (composing methods, organizing data, etc.)
  - Code smells (bloaters, OO abusers, change preventers, dispensables, couplers)
  - SOLID principles
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class RefactoringGuruScraper(BaseScraper):
    """Scrape Refactoring Guru design patterns, refactoring, code smells, and SOLID."""

    SOURCES = {
        "design-patterns": {
            "pages": {
                # Introduction
                "https://refactoring.guru/design-patterns": "Design Patterns",
                "https://refactoring.guru/design-patterns/what-is-pattern": "What is a Design Pattern?",
                "https://refactoring.guru/design-patterns/history": "History of Patterns",
                "https://refactoring.guru/design-patterns/why-learn-patterns": "Why Learn Design Patterns?",
                "https://refactoring.guru/design-patterns/criticism": "Criticism of Patterns",
                "https://refactoring.guru/design-patterns/classification": "Classification of Patterns",
                # Creational Patterns
                "https://refactoring.guru/design-patterns/creational-patterns": "Creational Design Patterns",
                "https://refactoring.guru/design-patterns/factory-method": "Factory Method",
                "https://refactoring.guru/design-patterns/abstract-factory": "Abstract Factory",
                "https://refactoring.guru/design-patterns/builder": "Builder",
                "https://refactoring.guru/design-patterns/prototype": "Prototype",
                "https://refactoring.guru/design-patterns/singleton": "Singleton",
                # Structural Patterns
                "https://refactoring.guru/design-patterns/structural-patterns": "Structural Design Patterns",
                "https://refactoring.guru/design-patterns/adapter": "Adapter",
                "https://refactoring.guru/design-patterns/bridge": "Bridge",
                "https://refactoring.guru/design-patterns/composite": "Composite",
                "https://refactoring.guru/design-patterns/decorator": "Decorator",
                "https://refactoring.guru/design-patterns/facade": "Facade",
                "https://refactoring.guru/design-patterns/flyweight": "Flyweight",
                "https://refactoring.guru/design-patterns/proxy": "Proxy",
                # Behavioral Patterns
                "https://refactoring.guru/design-patterns/behavioral-patterns": "Behavioral Design Patterns",
                "https://refactoring.guru/design-patterns/chain-of-responsibility": "Chain of Responsibility",
                "https://refactoring.guru/design-patterns/command": "Command",
                "https://refactoring.guru/design-patterns/iterator": "Iterator",
                "https://refactoring.guru/design-patterns/mediator": "Mediator",
                "https://refactoring.guru/design-patterns/memento": "Memento",
                "https://refactoring.guru/design-patterns/observer": "Observer",
                "https://refactoring.guru/design-patterns/state": "State",
                "https://refactoring.guru/design-patterns/strategy": "Strategy",
                "https://refactoring.guru/design-patterns/template-method": "Template Method",
                "https://refactoring.guru/design-patterns/visitor": "Visitor",
            },
        },
        "refactoring": {
            "pages": {
                # Introduction
                "https://refactoring.guru/refactoring": "What is Refactoring?",
                "https://refactoring.guru/refactoring/what-is-refactoring": "What is Refactoring? (Detailed)",
                "https://refactoring.guru/refactoring/clean-code": "Clean Code",
                "https://refactoring.guru/refactoring/technical-debt": "Technical Debt",
                "https://refactoring.guru/refactoring/when": "When to Refactor",
                "https://refactoring.guru/refactoring/how-to": "How to Refactor",
            },
        },
        "code-smells": {
            "pages": {
                "https://refactoring.guru/refactoring/smells": "Code Smells",
                # Bloaters
                "https://refactoring.guru/refactoring/smells/bloaters": "Bloaters",
                "https://refactoring.guru/smells/long-method": "Long Method",
                "https://refactoring.guru/smells/large-class": "Large Class",
                "https://refactoring.guru/smells/primitive-obsession": "Primitive Obsession",
                "https://refactoring.guru/smells/long-parameter-list": "Long Parameter List",
                "https://refactoring.guru/smells/data-clumps": "Data Clumps",
                # Object-Orientation Abusers
                "https://refactoring.guru/refactoring/smells/oo-abusers": "Object-Orientation Abusers",
                "https://refactoring.guru/smells/switch-statements": "Switch Statements",
                "https://refactoring.guru/smells/temporary-field": "Temporary Field",
                "https://refactoring.guru/smells/refused-bequest": "Refused Bequest",
                "https://refactoring.guru/smells/alternative-classes-with-different-interfaces": "Alternative Classes with Different Interfaces",
                # Change Preventers
                "https://refactoring.guru/refactoring/smells/change-preventers": "Change Preventers",
                "https://refactoring.guru/smells/divergent-change": "Divergent Change",
                "https://refactoring.guru/smells/shotgun-surgery": "Shotgun Surgery",
                "https://refactoring.guru/smells/parallel-inheritance-hierarchies": "Parallel Inheritance Hierarchies",
                # Dispensables
                "https://refactoring.guru/refactoring/smells/dispensables": "Dispensables",
                "https://refactoring.guru/smells/comments": "Comments",
                "https://refactoring.guru/smells/duplicate-code": "Duplicate Code",
                "https://refactoring.guru/smells/lazy-class": "Lazy Class",
                "https://refactoring.guru/smells/data-class": "Data Class",
                "https://refactoring.guru/smells/dead-code": "Dead Code",
                "https://refactoring.guru/smells/speculative-generality": "Speculative Generality",
                # Couplers
                "https://refactoring.guru/refactoring/smells/couplers": "Couplers",
                "https://refactoring.guru/smells/feature-envy": "Feature Envy",
                "https://refactoring.guru/smells/inappropriate-intimacy": "Inappropriate Intimacy",
                "https://refactoring.guru/smells/message-chains": "Message Chains",
                "https://refactoring.guru/smells/middle-man": "Middle Man",
                "https://refactoring.guru/smells/incomplete-library-class": "Incomplete Library Class",
            },
        },
        "refactoring-techniques": {
            "pages": {
                "https://refactoring.guru/refactoring/techniques": "Refactoring Techniques",
                # Composing Methods
                "https://refactoring.guru/refactoring/techniques/composing-methods": "Composing Methods",
                "https://refactoring.guru/extract-method": "Extract Method",
                "https://refactoring.guru/inline-method": "Inline Method",
                "https://refactoring.guru/extract-variable": "Extract Variable",
                "https://refactoring.guru/inline-temp": "Inline Temp",
                "https://refactoring.guru/replace-temp-with-query": "Replace Temp with Query",
                "https://refactoring.guru/split-temporary-variable": "Split Temporary Variable",
                "https://refactoring.guru/remove-assignments-to-parameters": "Remove Assignments to Parameters",
                "https://refactoring.guru/replace-method-with-method-object": "Replace Method with Method Object",
                "https://refactoring.guru/substitute-algorithm": "Substitute Algorithm",
                # Moving Features between Objects
                "https://refactoring.guru/refactoring/techniques/moving-features-between-objects": "Moving Features between Objects",
                "https://refactoring.guru/move-method": "Move Method",
                "https://refactoring.guru/move-field": "Move Field",
                "https://refactoring.guru/extract-class": "Extract Class",
                "https://refactoring.guru/inline-class": "Inline Class",
                "https://refactoring.guru/hide-delegate": "Hide Delegate",
                "https://refactoring.guru/remove-middle-man": "Remove Middle Man",
                "https://refactoring.guru/introduce-foreign-method": "Introduce Foreign Method",
                "https://refactoring.guru/introduce-local-extension": "Introduce Local Extension",
                # Organizing Data
                "https://refactoring.guru/refactoring/techniques/organizing-data": "Organizing Data",
                "https://refactoring.guru/self-encapsulate-field": "Self Encapsulate Field",
                "https://refactoring.guru/replace-data-value-with-object": "Replace Data Value with Object",
                "https://refactoring.guru/change-value-to-reference": "Change Value to Reference",
                "https://refactoring.guru/change-reference-to-value": "Change Reference to Value",
                "https://refactoring.guru/replace-array-with-object": "Replace Array with Object",
                "https://refactoring.guru/duplicate-observed-data": "Duplicate Observed Data",
                "https://refactoring.guru/change-unidirectional-association-to-bidirectional": "Change Unidirectional Association to Bidirectional",
                "https://refactoring.guru/change-bidirectional-association-to-unidirectional": "Change Bidirectional Association to Unidirectional",
                "https://refactoring.guru/replace-magic-number-with-symbolic-constant": "Replace Magic Number with Symbolic Constant",
                "https://refactoring.guru/encapsulate-field": "Encapsulate Field",
                "https://refactoring.guru/encapsulate-collection": "Encapsulate Collection",
                "https://refactoring.guru/replace-type-code-with-class": "Replace Type Code with Class",
                "https://refactoring.guru/replace-type-code-with-subclasses": "Replace Type Code with Subclasses",
                "https://refactoring.guru/replace-type-code-with-state-strategy": "Replace Type Code with State/Strategy",
                "https://refactoring.guru/replace-subclass-with-fields": "Replace Subclass with Fields",
                # Simplifying Conditional Expressions
                "https://refactoring.guru/refactoring/techniques/simplifying-conditional-expressions": "Simplifying Conditional Expressions",
                "https://refactoring.guru/decompose-conditional": "Decompose Conditional",
                "https://refactoring.guru/consolidate-conditional-expression": "Consolidate Conditional Expression",
                "https://refactoring.guru/consolidate-duplicate-conditional-fragments": "Consolidate Duplicate Conditional Fragments",
                "https://refactoring.guru/remove-control-flag": "Remove Control Flag",
                "https://refactoring.guru/replace-nested-conditional-with-guard-clauses": "Replace Nested Conditional with Guard Clauses",
                "https://refactoring.guru/replace-conditional-with-polymorphism": "Replace Conditional with Polymorphism",
                "https://refactoring.guru/introduce-null-object": "Introduce Null Object",
                "https://refactoring.guru/introduce-assertion": "Introduce Assertion",
                # Simplifying Method Calls
                "https://refactoring.guru/refactoring/techniques/simplifying-method-calls": "Simplifying Method Calls",
                "https://refactoring.guru/rename-method": "Rename Method",
                "https://refactoring.guru/add-parameter": "Add Parameter",
                "https://refactoring.guru/remove-parameter": "Remove Parameter",
                "https://refactoring.guru/separate-query-from-modifier": "Separate Query from Modifier",
                "https://refactoring.guru/parameterize-method": "Parameterize Method",
                "https://refactoring.guru/replace-parameter-with-explicit-methods": "Replace Parameter with Explicit Methods",
                "https://refactoring.guru/preserve-whole-object": "Preserve Whole Object",
                "https://refactoring.guru/replace-parameter-with-method-call": "Replace Parameter with Method Call",
                "https://refactoring.guru/introduce-parameter-object": "Introduce Parameter Object",
                "https://refactoring.guru/remove-setting-method": "Remove Setting Method",
                "https://refactoring.guru/hide-method": "Hide Method",
                "https://refactoring.guru/replace-constructor-with-factory-method": "Replace Constructor with Factory Method",
                "https://refactoring.guru/replace-error-code-with-exception": "Replace Error Code with Exception",
                "https://refactoring.guru/replace-exception-with-test": "Replace Exception with Test",
                # Dealing with Generalization
                "https://refactoring.guru/refactoring/techniques/dealing-with-generalization": "Dealing with Generalization",
                "https://refactoring.guru/pull-up-field": "Pull Up Field",
                "https://refactoring.guru/pull-up-method": "Pull Up Method",
                "https://refactoring.guru/pull-up-constructor-body": "Pull Up Constructor Body",
                "https://refactoring.guru/push-down-method": "Push Down Method",
                "https://refactoring.guru/push-down-field": "Push Down Field",
                "https://refactoring.guru/extract-subclass": "Extract Subclass",
                "https://refactoring.guru/extract-superclass": "Extract Superclass",
                "https://refactoring.guru/extract-interface": "Extract Interface",
                "https://refactoring.guru/collapse-hierarchy": "Collapse Hierarchy",
                "https://refactoring.guru/form-template-method": "Form Template Method",
                "https://refactoring.guru/replace-inheritance-with-delegation": "Replace Inheritance with Delegation",
                "https://refactoring.guru/replace-delegation-with-inheritance": "Replace Delegation with Inheritance",
            },
        },
        "solid": {
            "pages": {
                "https://refactoring.guru/didp/principles": "SOLID Principles",
                "https://refactoring.guru/didp/principles/single-responsibility": "Single Responsibility Principle",
                "https://refactoring.guru/didp/principles/open-closed": "Open/Closed Principle",
                "https://refactoring.guru/didp/principles/liskov-substitution": "Liskov Substitution Principle",
                "https://refactoring.guru/didp/principles/interface-segregation": "Interface Segregation Principle",
                "https://refactoring.guru/didp/principles/dependency-inversion": "Dependency Inversion Principle",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"refactoring-guru-{source_key}" if source_key else "refactoring-guru"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [' - Refactoring Guru', ' / Refactoring Guru']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})
        for url, title in pages.items():
            if not self.running:
                break
            item_id = self.make_id(url)
            content = self.fetch_url(url)
            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)
                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"refactoring-guru-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")
            time.sleep(1.5)
        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0
        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(
                    f"Unknown source key: {self.source_key}. "
                    f"Available: {list(self.SOURCES.keys())}"
                )
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES
        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping refactoring-guru/{key} ===")
            total += self._scrape_source(key, config)
        return total


if __name__ == "__main__":
    import os
    import sys
    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    RefactoringGuruScraper(base, source_key).run()
