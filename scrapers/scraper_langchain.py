#!/usr/bin/env python3
"""LangChain documentation scraper.

Covers:
  - python.langchain.com/docs/ get-started (installation, quickstart, LCEL)
  - python.langchain.com/docs/ concepts (chains, agents, tools, retrievers, etc.)
  - python.langchain.com/docs/ how-to (practical guides)
  - python.langchain.com/docs/ integrations (vector stores, chat models, embeddings)
  - python.langchain.com/docs/ api (core modules reference)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


BASE = "https://python.langchain.com/docs"


class LangChainScraper(BaseScraper):
    """Scrape LangChain documentation from python.langchain.com."""

    SOURCES = {
        "get-started": {
            "pages": {
                # === Introduction ===
                f"{BASE}/introduction/": "Introduction to LangChain",
                f"{BASE}/get_started/installation/": "Installation",
                f"{BASE}/get_started/quickstart/": "Quickstart",

                # === Tutorials ===
                f"{BASE}/tutorials/": "Tutorials Index",
                f"{BASE}/tutorials/llm_chain/": "Build a Simple LLM Application",
                f"{BASE}/tutorials/chatbot/": "Build a Chatbot",
                f"{BASE}/tutorials/rag/": "Build a RAG Application",
                f"{BASE}/tutorials/agents/": "Build an Agent",
                f"{BASE}/tutorials/qa_chat_history/": "QA with Chat History",
                f"{BASE}/tutorials/extraction/": "Build an Extraction Chain",
                f"{BASE}/tutorials/summarization/": "Summarize Text",
                f"{BASE}/tutorials/classification/": "Classify Text",
                f"{BASE}/tutorials/query_analysis/": "Build a Query Analysis System",
                f"{BASE}/tutorials/sql_qa/": "QA over SQL Data",
                f"{BASE}/tutorials/graph/": "QA over Graph Databases",
                f"{BASE}/tutorials/pdf_qa/": "QA over PDFs",
            },
        },
        "concepts": {
            "pages": {
                # === Core Concepts ===
                f"{BASE}/concepts/": "Conceptual Guide",
                f"{BASE}/concepts/lcel/": "LangChain Expression Language (LCEL)",
                f"{BASE}/concepts/runnables/": "Runnables",
                f"{BASE}/concepts/chat_models/": "Chat Models",
                f"{BASE}/concepts/llms/": "LLMs",
                f"{BASE}/concepts/messages/": "Messages",
                f"{BASE}/concepts/prompt_templates/": "Prompt Templates",
                f"{BASE}/concepts/output_parsers/": "Output Parsers",
                f"{BASE}/concepts/chat_history/": "Chat History",
                f"{BASE}/concepts/document_loaders/": "Document Loaders",
                f"{BASE}/concepts/text_splitters/": "Text Splitters",
                f"{BASE}/concepts/embedding_models/": "Embedding Models",
                f"{BASE}/concepts/vectorstores/": "Vector Stores",
                f"{BASE}/concepts/retrievers/": "Retrievers",
                f"{BASE}/concepts/rag/": "RAG (Retrieval Augmented Generation)",
                f"{BASE}/concepts/tools/": "Tools",
                f"{BASE}/concepts/agents/": "Agents",
                f"{BASE}/concepts/callbacks/": "Callbacks",
                f"{BASE}/concepts/streaming/": "Streaming",
                f"{BASE}/concepts/structured_outputs/": "Structured Outputs",
                f"{BASE}/concepts/few_shot_prompting/": "Few-Shot Prompting",
                f"{BASE}/concepts/evaluation/": "Evaluation",
                f"{BASE}/concepts/key_value_stores/": "Key-Value Stores",
                f"{BASE}/concepts/multimodality/": "Multimodality",
            },
        },
        "how-to": {
            "pages": {
                # === How-to Guides ===
                f"{BASE}/how_to/": "How-to Guides Index",

                # === Chat Models ===
                f"{BASE}/how_to/chat_models_universal_init/": "Init Any Chat Model",
                f"{BASE}/how_to/chat_model_caching/": "Cache Chat Model Responses",
                f"{BASE}/how_to/structured_output/": "Return Structured Output",
                f"{BASE}/how_to/tool_calling/": "Tool Calling",
                f"{BASE}/how_to/streaming/": "Stream Responses",
                f"{BASE}/how_to/function_calling/": "Function Calling",
                f"{BASE}/how_to/chat_token_usage_tracking/": "Track Token Usage",

                # === Prompts ===
                f"{BASE}/how_to/few_shot_examples_chat/": "Few-Shot Examples (Chat)",
                f"{BASE}/how_to/few_shot_examples/": "Few-Shot Examples",
                f"{BASE}/how_to/prompts_partial/": "Partial Prompt Templates",
                f"{BASE}/how_to/prompts_composition/": "Compose Prompts Together",

                # === Output Parsers ===
                f"{BASE}/how_to/output_parser_json/": "JSON Output Parser",
                f"{BASE}/how_to/output_parser_structured/": "Structured Output Parser",
                f"{BASE}/how_to/output_parser_xml/": "XML Output Parser",
                f"{BASE}/how_to/output_parser_custom/": "Custom Output Parser",

                # === Document Loaders & Splitting ===
                f"{BASE}/how_to/document_loader_pdf/": "Load PDFs",
                f"{BASE}/how_to/document_loader_csv/": "Load CSVs",
                f"{BASE}/how_to/document_loader_web/": "Load Web Pages",
                f"{BASE}/how_to/recursive_text_splitter/": "Recursive Text Splitter",
                f"{BASE}/how_to/character_text_splitter/": "Character Text Splitter",
                f"{BASE}/how_to/code_splitter/": "Code Splitter",
                f"{BASE}/how_to/markdown_header_metadata_splitter/": "Markdown Header Splitter",

                # === Retrievers & RAG ===
                f"{BASE}/how_to/vectorstore_retriever/": "Vector Store Retriever",
                f"{BASE}/how_to/ensemble_retriever/": "Ensemble Retriever",
                f"{BASE}/how_to/contextual_compression/": "Contextual Compression",
                f"{BASE}/how_to/multi_vector/": "Multi-Vector Retriever",
                f"{BASE}/how_to/parent_document_retriever/": "Parent Document Retriever",
                f"{BASE}/how_to/self_query/": "Self-Querying Retriever",
                f"{BASE}/how_to/time_weighted_vectorstore/": "Time-Weighted Retriever",

                # === Agents & Tools ===
                f"{BASE}/how_to/custom_tools/": "Define Custom Tools",
                f"{BASE}/how_to/tool_results_pass_to_model/": "Pass Tool Results to Model",
                f"{BASE}/how_to/tools_builtin/": "Use Built-in Tools",
                f"{BASE}/how_to/agent_executor/": "Use AgentExecutor (Legacy)",
                f"{BASE}/how_to/migrate_agent/": "Migrate from AgentExecutor to LangGraph",

                # === Chains / LCEL ===
                f"{BASE}/how_to/sequence/": "Chain Runnables",
                f"{BASE}/how_to/parallel/": "Invoke Runnables in Parallel",
                f"{BASE}/how_to/passthrough/": "Pass Through Arguments",
                f"{BASE}/how_to/binding/": "Bind Runtime Arguments",
                f"{BASE}/how_to/fallbacks/": "Add Fallbacks",

                # === Callbacks ===
                f"{BASE}/how_to/callbacks_attach/": "Attach Callbacks",
                f"{BASE}/how_to/callbacks_custom_events/": "Dispatch Custom Events",
                f"{BASE}/how_to/callbacks_async/": "Use Callbacks in Async",
            },
        },
        "integrations": {
            "pages": {
                # === Integrations Index ===
                f"{BASE}/integrations/platforms/": "Platforms",

                # === Chat Model Providers ===
                f"{BASE}/integrations/chat/openai/": "ChatOpenAI",
                f"{BASE}/integrations/chat/anthropic/": "ChatAnthropic",
                f"{BASE}/integrations/chat/google_generative_ai/": "ChatGoogleGenerativeAI",
                f"{BASE}/integrations/chat/groq/": "ChatGroq",
                f"{BASE}/integrations/chat/fireworks/": "ChatFireworks",
                f"{BASE}/integrations/chat/mistralai/": "ChatMistralAI",
                f"{BASE}/integrations/chat/ollama/": "ChatOllama",
                f"{BASE}/integrations/chat/together/": "ChatTogether",

                # === Vector Stores ===
                f"{BASE}/integrations/vectorstores/chroma/": "Chroma",
                f"{BASE}/integrations/vectorstores/faiss/": "FAISS",
                f"{BASE}/integrations/vectorstores/pgvector/": "PGVector",
                f"{BASE}/integrations/vectorstores/pinecone/": "Pinecone",
                f"{BASE}/integrations/vectorstores/qdrant/": "Qdrant",
                f"{BASE}/integrations/vectorstores/weaviate/": "Weaviate",
                f"{BASE}/integrations/vectorstores/milvus/": "Milvus",

                # === Embeddings ===
                f"{BASE}/integrations/text_embedding/openai/": "OpenAI Embeddings",
                f"{BASE}/integrations/text_embedding/huggingface/": "HuggingFace Embeddings",
                f"{BASE}/integrations/text_embedding/google_generative_ai/": "Google Generative AI Embeddings",
                f"{BASE}/integrations/text_embedding/ollama/": "Ollama Embeddings",

                # === Document Loaders ===
                f"{BASE}/integrations/document_loaders/": "Document Loaders Index",

                # === Tools ===
                f"{BASE}/integrations/tools/": "Tools Index",
            },
        },
        "api": {
            "pages": {
                # === API Reference (core modules) ===
                f"https://python.langchain.com/api_reference/": "API Reference Index",
                f"https://python.langchain.com/api_reference/core/index.html": "langchain-core",
                f"https://python.langchain.com/api_reference/core/runnables.html": "Core Runnables",
                f"https://python.langchain.com/api_reference/core/prompts.html": "Core Prompts",
                f"https://python.langchain.com/api_reference/core/output_parsers.html": "Core Output Parsers",
                f"https://python.langchain.com/api_reference/core/messages.html": "Core Messages",
                f"https://python.langchain.com/api_reference/core/documents.html": "Core Documents",
                f"https://python.langchain.com/api_reference/core/language_models.html": "Core Language Models",
                f"https://python.langchain.com/api_reference/core/embeddings.html": "Core Embeddings",
                f"https://python.langchain.com/api_reference/core/vectorstores.html": "Core Vector Stores",
                f"https://python.langchain.com/api_reference/core/retrievers.html": "Core Retrievers",
                f"https://python.langchain.com/api_reference/core/tools.html": "Core Tools",
                f"https://python.langchain.com/api_reference/core/callbacks.html": "Core Callbacks",
                f"https://python.langchain.com/api_reference/langchain/index.html": "langchain Package",
                f"https://python.langchain.com/api_reference/langchain/agents.html": "Agents Module",
                f"https://python.langchain.com/api_reference/langchain/chains.html": "Chains Module",
                f"https://python.langchain.com/api_reference/langchain/memory.html": "Memory Module",
                f"https://python.langchain.com/api_reference/community/index.html": "langchain-community",
                f"https://python.langchain.com/api_reference/text_splitters/index.html": "Text Splitters Package",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"langchain-{source_key}" if source_key else "langchain"
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
            for suffix in [' | LangChain', ' - LangChain',
                           ' | 🦜️🔗 LangChain',
                           ' — LangChain']:
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
                        "category": f"langchain-{source_key}",
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
            self.log.info(f"=== Scraping langchain/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    LangChainScraper(base, source_key).run()
