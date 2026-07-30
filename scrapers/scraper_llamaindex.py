#!/usr/bin/env python3
"""LlamaIndex documentation scraper.

Covers:
  - docs.llamaindex.ai getting-started (installation, starter tutorial, concepts)
  - docs.llamaindex.ai understanding (core concepts, loading, indexing, querying, tracing)
  - docs.llamaindex.ai optimizing (fine-tuning, embeddings, RAG evaluation)
  - docs.llamaindex.ai module guides (data connectors, indexes, query engines, agents, etc.)
  - docs.llamaindex.ai use-cases (QA, chatbots, agents, structured data, knowledge graphs)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


BASE = "https://docs.llamaindex.ai/en/stable"


class LlamaIndexScraper(BaseScraper):
    """Scrape LlamaIndex documentation from docs.llamaindex.ai."""

    SOURCES = {
        "getting-started": {
            "pages": {
                # === Getting Started ===
                f"{BASE}/": "LlamaIndex Documentation Home",
                f"{BASE}/getting_started/installation/": "Installation",
                f"{BASE}/getting_started/starter_example/": "Starter Tutorial",
                f"{BASE}/getting_started/concepts/": "High-Level Concepts",
                f"{BASE}/getting_started/customization/": "Customization Tutorial",
                f"{BASE}/getting_started/discover_llamaindex/": "Discover LlamaIndex",
            },
        },
        "concepts": {
            "pages": {
                # === Understanding LlamaIndex ===
                f"{BASE}/understanding/": "Understanding LlamaIndex",
                f"{BASE}/understanding/using_llms/": "Using LLMs",
                f"{BASE}/understanding/loading/": "Loading & Ingestion",
                f"{BASE}/understanding/loading/loading/": "Loading Data",
                f"{BASE}/understanding/loading/documents_and_nodes/": "Documents and Nodes",
                f"{BASE}/understanding/indexing/": "Indexing",
                f"{BASE}/understanding/indexing/indexing/": "How Indexing Works",
                f"{BASE}/understanding/storing/": "Storing",
                f"{BASE}/understanding/storing/storing/": "How Storing Works",
                f"{BASE}/understanding/querying/": "Querying",
                f"{BASE}/understanding/querying/querying/": "How Querying Works",
                f"{BASE}/understanding/putting_it_all_together/": "Putting It All Together",
                f"{BASE}/understanding/tracing_and_debugging/": "Tracing and Debugging",
                f"{BASE}/understanding/evaluating/": "Evaluating",

                # === Core concepts deep-dives ===
                f"{BASE}/understanding/rag/": "RAG Overview",
                f"{BASE}/understanding/agent/": "Agents Overview",
                f"{BASE}/understanding/workflows/": "Workflows",
            },
        },
        "guides": {
            "pages": {
                # === Optimizing ===
                f"{BASE}/optimizing/": "Optimizing Overview",
                f"{BASE}/optimizing/production_rag/": "Building Performant RAG",
                f"{BASE}/optimizing/basic_strategies/": "Basic Strategies",
                f"{BASE}/optimizing/advanced_retrieval/": "Advanced Retrieval Strategies",
                f"{BASE}/optimizing/agentic_strategies/": "Agentic Strategies",
                f"{BASE}/optimizing/fine_tuning/": "Fine-Tuning",
                f"{BASE}/optimizing/evaluation/": "Evaluation",
                f"{BASE}/optimizing/building_rag_from_scratch/": "Building RAG from Scratch",

                # === Use Cases ===
                f"{BASE}/use_cases/": "Use Cases Overview",
                f"{BASE}/use_cases/q_and_a/": "Question Answering (QA)",
                f"{BASE}/use_cases/chatbots/": "Chatbots",
                f"{BASE}/use_cases/agents/": "Agents",
                f"{BASE}/use_cases/extraction/": "Structured Data Extraction",
                f"{BASE}/use_cases/multi_modal/": "Multi-Modal Applications",

                # === Examples / Tutorials ===
                f"{BASE}/examples/": "Examples Index",
                f"{BASE}/examples/discover_llamaindex/": "Discover LlamaIndex Examples",
                f"{BASE}/examples/pipeline/": "Ingestion Pipeline Examples",
            },
        },
        "components": {
            "pages": {
                # === Data Connectors (Readers) ===
                f"{BASE}/module_guides/loading/": "Loading Overview",
                f"{BASE}/module_guides/loading/simpledirectoryreader/": "SimpleDirectoryReader",
                f"{BASE}/module_guides/loading/connector/": "Data Connectors (Readers)",
                f"{BASE}/module_guides/loading/documents_and_nodes/": "Documents and Nodes",
                f"{BASE}/module_guides/loading/node_parsers/": "Node Parsers / Text Splitters",
                f"{BASE}/module_guides/loading/ingestion_pipeline/": "Ingestion Pipeline",

                # === Indexes ===
                f"{BASE}/module_guides/indexing/": "Indexing Overview",
                f"{BASE}/module_guides/indexing/vector_store_index/": "Vector Store Index",
                f"{BASE}/module_guides/indexing/summary_index/": "Summary Index",
                f"{BASE}/module_guides/indexing/tree_index/": "Tree Index",
                f"{BASE}/module_guides/indexing/keyword_table_index/": "Keyword Table Index",
                f"{BASE}/module_guides/indexing/document_management/": "Document Management",
                f"{BASE}/module_guides/indexing/lpg_index_guide/": "Property Graph Index",

                # === Storing ===
                f"{BASE}/module_guides/storing/": "Storing Overview",
                f"{BASE}/module_guides/storing/vector_stores/": "Vector Stores",
                f"{BASE}/module_guides/storing/docstores/": "Document Stores",
                f"{BASE}/module_guides/storing/index_stores/": "Index Stores",
                f"{BASE}/module_guides/storing/chat_stores/": "Chat Stores",

                # === Query Engines ===
                f"{BASE}/module_guides/querying/": "Querying Overview",
                f"{BASE}/module_guides/querying/query_engine/": "Query Engine",
                f"{BASE}/module_guides/querying/chat_engines/": "Chat Engines",
                f"{BASE}/module_guides/querying/router/": "Router Query Engine",
                f"{BASE}/module_guides/querying/retriever/": "Retrievers",
                f"{BASE}/module_guides/querying/response_synthesizers/": "Response Synthesizers",
                f"{BASE}/module_guides/querying/node_postprocessors/": "Node Postprocessors",
                f"{BASE}/module_guides/querying/structured_outputs/": "Structured Outputs",

                # === Embeddings ===
                f"{BASE}/module_guides/models/embeddings/": "Embeddings",

                # === LLMs ===
                f"{BASE}/module_guides/models/llms/": "LLMs",
                f"{BASE}/module_guides/models/llms/usage_custom/": "Using Custom LLMs",

                # === Agents ===
                f"{BASE}/module_guides/deploying/agents/": "Agents Overview",
                f"{BASE}/module_guides/deploying/agents/tools/": "Agent Tools",
                f"{BASE}/module_guides/deploying/agents/agent_runner/": "Agent Runner",

                # === Evaluation ===
                f"{BASE}/module_guides/evaluating/": "Evaluation Overview",
                f"{BASE}/module_guides/evaluating/usage_pattern/": "Evaluation Usage Pattern",

                # === Observability ===
                f"{BASE}/module_guides/observability/": "Observability",

                # === Prompts ===
                f"{BASE}/module_guides/models/prompts/": "Prompts",

                # === Callbacks ===
                f"{BASE}/module_guides/observability/callbacks/": "Callbacks",
            },
        },
        "use-cases": {
            "pages": {
                # === Full-stack / deployment ===
                f"{BASE}/use_cases/q_and_a/": "Question Answering",
                f"{BASE}/use_cases/chatbots/": "Chatbots",
                f"{BASE}/use_cases/agents/": "Agents Use Case",
                f"{BASE}/use_cases/extraction/": "Data Extraction",
                f"{BASE}/use_cases/multi_modal/": "Multi-Modal",

                # === Community / ecosystem ===
                f"{BASE}/community/": "Community Resources",
                f"{BASE}/community/integrations/": "Community Integrations",
                f"{BASE}/community/llama_packs/": "LlamaPacks",

                # === API Reference landing ===
                f"{BASE}/api_reference/": "API Reference Index",
                f"{BASE}/api_reference/llms/": "LLMs API Reference",
                f"{BASE}/api_reference/embeddings/": "Embeddings API Reference",
                f"{BASE}/api_reference/query/": "Query API Reference",
                f"{BASE}/api_reference/indices/": "Indices API Reference",
                f"{BASE}/api_reference/node/": "Node API Reference",
                f"{BASE}/api_reference/readers/": "Readers API Reference",
                f"{BASE}/api_reference/storage/": "Storage API Reference",
                f"{BASE}/api_reference/evaluation/": "Evaluation API Reference",
                f"{BASE}/api_reference/agent/": "Agent API Reference",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"llamaindex-{source_key}" if source_key else "llamaindex"
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
            for suffix in [' - LlamaIndex', ' | LlamaIndex',
                           ' — LlamaIndex', ' - LlamaIndex Documentation']:
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
                        "category": f"llamaindex-{source_key}",
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
            self.log.info(f"=== Scraping llamaindex/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    LlamaIndexScraper(base, source_key).run()
