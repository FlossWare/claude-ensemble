#!/usr/bin/env python3
"""Python documentation scraper.

Covers:
  - Tutorial: all sections (introduction, control flow, data structures, modules, etc.)
  - Library reference: key stdlib modules (os, sys, json, re, pathlib, asyncio, etc.)
  - Language reference: data model, expressions, statements, import system
  - HOWTOs: logging, regex, sockets, sorting, unicode, argparse, enum, functional
  - FAQ: general, programming, design, library, extending
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class PythonScraper(BaseScraper):
    """Scrape Python official documentation."""

    SOURCES = {
        "tutorial": {
            "pages": {
                # The Python Tutorial
                "https://docs.python.org/3/tutorial/index.html": "The Python Tutorial",
                "https://docs.python.org/3/tutorial/appetite.html": "Whetting Your Appetite",
                "https://docs.python.org/3/tutorial/interpreter.html": "Using the Python Interpreter",
                "https://docs.python.org/3/tutorial/introduction.html": "An Informal Introduction to Python",
                "https://docs.python.org/3/tutorial/controlflow.html": "More Control Flow Tools",
                "https://docs.python.org/3/tutorial/datastructures.html": "Data Structures",
                "https://docs.python.org/3/tutorial/modules.html": "Modules",
                "https://docs.python.org/3/tutorial/inputoutput.html": "Input and Output",
                "https://docs.python.org/3/tutorial/errors.html": "Errors and Exceptions",
                "https://docs.python.org/3/tutorial/classes.html": "Classes",
                "https://docs.python.org/3/tutorial/stdlib.html": "Brief Tour of the Standard Library",
                "https://docs.python.org/3/tutorial/stdlib2.html": "Brief Tour of the Standard Library - Part II",
                "https://docs.python.org/3/tutorial/venv.html": "Virtual Environments and Packages",
                "https://docs.python.org/3/tutorial/whatnow.html": "What Now?",
                "https://docs.python.org/3/tutorial/interactive.html": "Interactive Input Editing and History Substitution",
                "https://docs.python.org/3/tutorial/floatingpoint.html": "Floating-Point Arithmetic: Issues and Limitations",
                "https://docs.python.org/3/tutorial/appendix.html": "Appendix",
            },
        },
        "library-core": {
            "pages": {
                # Built-in Functions, Types, Exceptions
                "https://docs.python.org/3/library/index.html": "The Python Standard Library",
                "https://docs.python.org/3/library/functions.html": "Built-in Functions",
                "https://docs.python.org/3/library/constants.html": "Built-in Constants",
                "https://docs.python.org/3/library/stdtypes.html": "Built-in Types",
                "https://docs.python.org/3/library/exceptions.html": "Built-in Exceptions",
                # Text Processing
                "https://docs.python.org/3/library/string.html": "string - Common string operations",
                "https://docs.python.org/3/library/re.html": "re - Regular expression operations",
                "https://docs.python.org/3/library/difflib.html": "difflib - Helpers for computing deltas",
                "https://docs.python.org/3/library/textwrap.html": "textwrap - Text wrapping and filling",
                # Data Types
                "https://docs.python.org/3/library/datetime.html": "datetime - Basic date and time types",
                "https://docs.python.org/3/library/calendar.html": "calendar - General calendar-related functions",
                "https://docs.python.org/3/library/collections.html": "collections - Container datatypes",
                "https://docs.python.org/3/library/collections.abc.html": "collections.abc - Abstract Base Classes for Containers",
                "https://docs.python.org/3/library/copy.html": "copy - Shallow and deep copy operations",
                "https://docs.python.org/3/library/pprint.html": "pprint - Data pretty printer",
                "https://docs.python.org/3/library/enum.html": "enum - Support for enumerations",
                "https://docs.python.org/3/library/dataclasses.html": "dataclasses - Data Classes",
                "https://docs.python.org/3/library/typing.html": "typing - Support for type hints",
                # Numeric and Mathematical
                "https://docs.python.org/3/library/math.html": "math - Mathematical functions",
                "https://docs.python.org/3/library/decimal.html": "decimal - Decimal fixed point and floating point arithmetic",
                "https://docs.python.org/3/library/fractions.html": "fractions - Rational numbers",
                "https://docs.python.org/3/library/random.html": "random - Generate pseudo-random numbers",
                "https://docs.python.org/3/library/statistics.html": "statistics - Mathematical statistics functions",
                # Functional Programming
                "https://docs.python.org/3/library/itertools.html": "itertools - Functions creating iterators",
                "https://docs.python.org/3/library/functools.html": "functools - Higher-order functions and operations on callable objects",
                "https://docs.python.org/3/library/operator.html": "operator - Standard operators as functions",
            },
        },
        "library-fileio": {
            "pages": {
                # File and Directory Access
                "https://docs.python.org/3/library/pathlib.html": "pathlib - Object-oriented filesystem paths",
                "https://docs.python.org/3/library/os.path.html": "os.path - Common pathname manipulations",
                "https://docs.python.org/3/library/fileinput.html": "fileinput - Iterate over lines from multiple input streams",
                "https://docs.python.org/3/library/tempfile.html": "tempfile - Generate temporary files and directories",
                "https://docs.python.org/3/library/glob.html": "glob - Unix style pathname pattern expansion",
                "https://docs.python.org/3/library/fnmatch.html": "fnmatch - Unix filename pattern matching",
                "https://docs.python.org/3/library/shutil.html": "shutil - High-level file operations",
                # Data Persistence
                "https://docs.python.org/3/library/pickle.html": "pickle - Python object serialization",
                "https://docs.python.org/3/library/shelve.html": "shelve - Python object persistence",
                "https://docs.python.org/3/library/dbm.html": "dbm - Interfaces to Unix databases",
                "https://docs.python.org/3/library/sqlite3.html": "sqlite3 - DB-API 2.0 interface for SQLite databases",
                # Data Compression
                "https://docs.python.org/3/library/gzip.html": "gzip - Support for gzip files",
                "https://docs.python.org/3/library/zipfile.html": "zipfile - Work with ZIP archives",
                "https://docs.python.org/3/library/tarfile.html": "tarfile - Read and write tar archive files",
                # File Formats
                "https://docs.python.org/3/library/csv.html": "csv - CSV File Reading and Writing",
                "https://docs.python.org/3/library/configparser.html": "configparser - Configuration file parser",
                # IO
                "https://docs.python.org/3/library/io.html": "io - Core tools for working with streams",
            },
        },
        "library-os": {
            "pages": {
                # OS Services
                "https://docs.python.org/3/library/os.html": "os - Miscellaneous operating system interfaces",
                "https://docs.python.org/3/library/time.html": "time - Time access and conversions",
                "https://docs.python.org/3/library/argparse.html": "argparse - Parser for command-line options",
                "https://docs.python.org/3/library/logging.html": "logging - Logging facility for Python",
                "https://docs.python.org/3/library/logging.config.html": "logging.config - Logging configuration",
                "https://docs.python.org/3/library/logging.handlers.html": "logging.handlers - Logging handlers",
                "https://docs.python.org/3/library/sys.html": "sys - System-specific parameters and functions",
                "https://docs.python.org/3/library/subprocess.html": "subprocess - Subprocess management",
                "https://docs.python.org/3/library/signal.html": "signal - Set handlers for asynchronous events",
                "https://docs.python.org/3/library/contextlib.html": "contextlib - Utilities for with-statement contexts",
                "https://docs.python.org/3/library/abc.html": "abc - Abstract Base Classes",
                "https://docs.python.org/3/library/struct.html": "struct - Interpret bytes as packed binary data",
            },
        },
        "library-network": {
            "pages": {
                # Networking and Interprocess Communication
                "https://docs.python.org/3/library/socket.html": "socket - Low-level networking interface",
                "https://docs.python.org/3/library/ssl.html": "ssl - TLS/SSL wrapper for socket objects",
                "https://docs.python.org/3/library/asyncio.html": "asyncio - Asynchronous I/O",
                "https://docs.python.org/3/library/asyncio-task.html": "asyncio - Coroutines and Tasks",
                "https://docs.python.org/3/library/asyncio-stream.html": "asyncio - Streams",
                "https://docs.python.org/3/library/asyncio-subprocess.html": "asyncio - Subprocesses",
                "https://docs.python.org/3/library/asyncio-sync.html": "asyncio - Synchronization Primitives",
                "https://docs.python.org/3/library/asyncio-queue.html": "asyncio - Queues",
                "https://docs.python.org/3/library/asyncio-eventloop.html": "asyncio - Event Loop",
                # Internet Protocols
                "https://docs.python.org/3/library/http.html": "http - HTTP modules",
                "https://docs.python.org/3/library/http.client.html": "http.client - HTTP protocol client",
                "https://docs.python.org/3/library/http.server.html": "http.server - HTTP servers",
                "https://docs.python.org/3/library/urllib.html": "urllib - URL handling modules",
                "https://docs.python.org/3/library/urllib.request.html": "urllib.request - Extensible library for opening URLs",
                "https://docs.python.org/3/library/urllib.parse.html": "urllib.parse - Parse URLs into components",
                "https://docs.python.org/3/library/urllib.error.html": "urllib.error - Exception classes raised by urllib.request",
                "https://docs.python.org/3/library/email.html": "email - An email and MIME handling package",
                "https://docs.python.org/3/library/json.html": "json - JSON encoder and decoder",
                # HTML/XML
                "https://docs.python.org/3/library/html.html": "html - HyperText Markup Language support",
                "https://docs.python.org/3/library/html.parser.html": "html.parser - Simple HTML and XHTML parser",
                "https://docs.python.org/3/library/xml.html": "xml - XML Processing Modules",
                "https://docs.python.org/3/library/xml.etree.elementtree.html": "xml.etree.ElementTree - The ElementTree XML API",
            },
        },
        "library-concurrent": {
            "pages": {
                # Concurrent Execution
                "https://docs.python.org/3/library/threading.html": "threading - Thread-based parallelism",
                "https://docs.python.org/3/library/multiprocessing.html": "multiprocessing - Process-based parallelism",
                "https://docs.python.org/3/library/multiprocessing.shared_memory.html": "multiprocessing.shared_memory - Shared memory",
                "https://docs.python.org/3/library/concurrent.html": "concurrent - Concurrent package",
                "https://docs.python.org/3/library/concurrent.futures.html": "concurrent.futures - Launching parallel tasks",
                "https://docs.python.org/3/library/queue.html": "queue - A synchronized queue class",
                # Cryptographic
                "https://docs.python.org/3/library/hashlib.html": "hashlib - Secure hashes and message digests",
                "https://docs.python.org/3/library/hmac.html": "hmac - Keyed-Hashing for Message Authentication",
                "https://docs.python.org/3/library/secrets.html": "secrets - Generate secure random numbers",
                # Testing
                "https://docs.python.org/3/library/unittest.html": "unittest - Unit testing framework",
                "https://docs.python.org/3/library/unittest.mock.html": "unittest.mock - mock object library",
                "https://docs.python.org/3/library/doctest.html": "doctest - Test interactive Python examples",
            },
        },
        "language-reference": {
            "pages": {
                # The Python Language Reference
                "https://docs.python.org/3/reference/index.html": "The Python Language Reference",
                "https://docs.python.org/3/reference/introduction.html": "Introduction",
                "https://docs.python.org/3/reference/lexical_analysis.html": "Lexical Analysis",
                "https://docs.python.org/3/reference/datamodel.html": "Data Model",
                "https://docs.python.org/3/reference/executionmodel.html": "Execution Model",
                "https://docs.python.org/3/reference/import.html": "The Import System",
                "https://docs.python.org/3/reference/expressions.html": "Expressions",
                "https://docs.python.org/3/reference/simple_stmts.html": "Simple Statements",
                "https://docs.python.org/3/reference/compound_stmts.html": "Compound Statements",
                "https://docs.python.org/3/reference/toplevel_components.html": "Top-level Components",
                "https://docs.python.org/3/reference/grammar.html": "Full Grammar Specification",
            },
        },
        "howtos": {
            "pages": {
                # HOWTOs
                "https://docs.python.org/3/howto/index.html": "Python HOWTOs",
                "https://docs.python.org/3/howto/logging.html": "Logging HOWTO",
                "https://docs.python.org/3/howto/logging-cookbook.html": "Logging Cookbook",
                "https://docs.python.org/3/howto/regex.html": "Regular Expression HOWTO",
                "https://docs.python.org/3/howto/sockets.html": "Socket Programming HOWTO",
                "https://docs.python.org/3/howto/sorting.html": "Sorting Techniques",
                "https://docs.python.org/3/howto/unicode.html": "Unicode HOWTO",
                "https://docs.python.org/3/howto/argparse.html": "Argparse Tutorial",
                "https://docs.python.org/3/howto/enum.html": "Enum HOWTO",
                "https://docs.python.org/3/howto/functional.html": "Functional Programming HOWTO",
                "https://docs.python.org/3/howto/descriptor.html": "Descriptor Guide",
                "https://docs.python.org/3/howto/annotations.html": "Annotations Best Practices",
                "https://docs.python.org/3/howto/ipaddress.html": "An introduction to the ipaddress module",
                "https://docs.python.org/3/howto/urllib2.html": "HOWTO Fetch Internet Resources Using urllib",
            },
        },
        "faq": {
            "pages": {
                # FAQ
                "https://docs.python.org/3/faq/index.html": "Python FAQ",
                "https://docs.python.org/3/faq/general.html": "General Python FAQ",
                "https://docs.python.org/3/faq/programming.html": "Programming FAQ",
                "https://docs.python.org/3/faq/design.html": "Design and History FAQ",
                "https://docs.python.org/3/faq/library.html": "Library and Extension FAQ",
                "https://docs.python.org/3/faq/extending.html": "Extending/Embedding FAQ",
                "https://docs.python.org/3/faq/windows.html": "Python on Windows FAQ",
                "https://docs.python.org/3/faq/installed.html": "Why is Python Installed on my Computer? FAQ",
                # What's New
                "https://docs.python.org/3/whatsnew/index.html": "What's New in Python",
                "https://docs.python.org/3/whatsnew/3.12.html": "What's New In Python 3.12",
                "https://docs.python.org/3/whatsnew/3.13.html": "What's New In Python 3.13",
                # Glossary
                "https://docs.python.org/3/glossary.html": "Glossary",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"python-{source_key}" if source_key else "python"
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
            # Clean common suffixes - handle versioned suffix like " — Python 3.12.0 documentation"
            title = re.sub(r'\s*—\s*Python 3\.\d+.*', '', title)
            for suffix in [' — Python documentation', ' - Python documentation']:
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
                        "category": f"python-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.0)

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
            self.log.info(f"=== Scraping python/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    PythonScraper(base, source_key).run()
