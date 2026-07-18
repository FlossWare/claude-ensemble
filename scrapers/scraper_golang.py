#!/usr/bin/env python3
"""Go documentation scraper.

Covers:
  - Documentation (go.dev/doc/)
  - Go Blog (go.dev/blog/)
  - Standard library packages (pkg.go.dev/std)
  - Language specification (go.dev/ref/spec)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class GolangScraper(BaseScraper):
    """Scrape Go documentation from go.dev and pkg.go.dev."""

    SOURCES = {
        "docs": {
            "pages": {
                # Getting started and tutorials
                "https://go.dev/doc/": "Documentation",
                "https://go.dev/doc/install": "Download and Install",
                "https://go.dev/doc/tutorial/getting-started": "Tutorial: Getting Started",
                "https://go.dev/doc/tutorial/create-module": "Tutorial: Create a Go Module",
                "https://go.dev/doc/tutorial/getting-started-multi-module": "Tutorial: Getting Started with Multi-module Workspaces",
                "https://go.dev/doc/tutorial/database-access": "Tutorial: Accessing a Relational Database",
                "https://go.dev/doc/tutorial/web-service-gin": "Tutorial: Developing a RESTful API with Go and Gin",
                "https://go.dev/doc/tutorial/generics": "Tutorial: Getting Started with Generics",
                "https://go.dev/doc/tutorial/fuzz": "Tutorial: Getting Started with Fuzzing",
                "https://go.dev/doc/tutorial/govulncheck": "Tutorial: Find and Fix Vulnerable Dependencies with govulncheck",
                # Core documentation
                "https://go.dev/doc/effective_go": "Effective Go",
                "https://go.dev/doc/faq": "Frequently Asked Questions",
                "https://go.dev/doc/code": "How to Write Go Code",
                "https://go.dev/doc/modules/gomod-ref": "go.mod File Reference",
                "https://go.dev/doc/modules/managing-dependencies": "Managing Dependencies",
                "https://go.dev/doc/modules/developing": "Developing and Publishing Modules",
                "https://go.dev/doc/modules/major-version": "Module Version Numbering",
                "https://go.dev/doc/modules/version-numbers": "Module Version Numbering Details",
                "https://go.dev/ref/mod": "Go Modules Reference",
                "https://go.dev/doc/devel/release": "Release History",
                "https://go.dev/doc/editors": "Editor Plugins and IDEs",
                # Diagnostics and tools
                "https://go.dev/doc/diagnostics": "Diagnostics",
                "https://go.dev/doc/gc-guide": "A Guide to the Go Garbage Collector",
                "https://go.dev/doc/pprof": "Profiling Go Programs",
                "https://go.dev/doc/articles/race_detector": "Data Race Detector",
                "https://go.dev/doc/security/best-practices": "Go Security Best Practices",
                "https://go.dev/doc/security/vuln/": "Go Vulnerability Management",
                # Commands
                "https://go.dev/doc/cmd": "Command Documentation",
                "https://go.dev/ref/spec": "The Go Programming Language Specification",
                "https://go.dev/ref/mem": "The Go Memory Model",
            },
        },
        "blog": {
            "pages": {
                # Go Blog posts - key topics
                "https://go.dev/blog/using-go-modules": "Using Go Modules",
                "https://go.dev/blog/v2-go-modules": "Go Modules: v2 and Beyond",
                "https://go.dev/blog/module-mirror-launch": "Module Mirror and Checksum Database Launched",
                "https://go.dev/blog/context": "Go Concurrency Patterns: Context",
                "https://go.dev/blog/intro-generics": "An Introduction to Generics",
                "https://go.dev/blog/when-generics": "When to Use Generics",
                "https://go.dev/blog/go1.18": "Go 1.18 is Released",
                "https://go.dev/blog/go1.19": "Go 1.19 is Released",
                "https://go.dev/blog/go1.20": "Go 1.20 is Released",
                "https://go.dev/blog/go1.21": "Go 1.21 is Released",
                "https://go.dev/blog/go1.22": "Go 1.22 is Released",
                "https://go.dev/blog/go1.23": "Go 1.23 is Released",
                "https://go.dev/blog/error-handling-and-go": "Error Handling and Go",
                "https://go.dev/blog/errors-are-values": "Errors Are Values",
                "https://go.dev/blog/go1.13-errors": "Working with Errors in Go 1.13",
                "https://go.dev/blog/json": "JSON and Go",
                "https://go.dev/blog/laws-of-reflection": "The Laws of Reflection",
                "https://go.dev/blog/pipelines": "Go Concurrency Patterns: Pipelines and Cancellation",
                "https://go.dev/blog/context-and-structs": "Contexts and Structs",
                "https://go.dev/blog/subtests": "Using Subtests and Sub-benchmarks",
                "https://go.dev/blog/cover": "The Cover Story",
                "https://go.dev/blog/pprof": "Profiling Go Programs",
                "https://go.dev/blog/slog": "Structured Logging with slog",
                "https://go.dev/blog/range-functions": "Range Over Function Types",
                "https://go.dev/blog/telemetry": "Transparent Telemetry for Open-Source Projects",
                "https://go.dev/blog/go-brand": "Go's New Brand",
                "https://go.dev/blog/strings": "Strings, bytes, runes and characters in Go",
                "https://go.dev/blog/slices-intro": "Go Slices: Usage and Internals",
                "https://go.dev/blog/slices": "Arrays, Slices (and Strings): The Mechanics of Append",
                "https://go.dev/blog/maps": "Go Maps in Action",
                "https://go.dev/blog/defer-panic-and-recover": "Defer, Panic, and Recover",
                "https://go.dev/blog/concurrency-is-not-parallelism": "Concurrency Is Not Parallelism",
                "https://go.dev/blog/race-detector": "Introducing the Go Race Detector",
                "https://go.dev/blog/share-memory-by-communicating": "Share Memory By Communicating",
                "https://go.dev/blog/codelab-share": "Share Your Workspace",
                "https://go.dev/blog/io2013-talk-concurrency": "Advanced Go Concurrency Patterns",
                "https://go.dev/blog/normalization": "Text Normalization in Go",
                "https://go.dev/blog/matchlang": "Language and Locale Matching in Go",
                "https://go.dev/blog/generate": "Generating Code",
                "https://go.dev/blog/gif-decoder": "A GIF Decoder: An Exercise in Go Interfaces",
                "https://go.dev/blog/gob": "Gobs of Data",
                "https://go.dev/blog/godoc": "Godoc: Documenting Go Code",
                "https://go.dev/blog/go-test-bench": "Using Go's Testing Package",
                "https://go.dev/blog/examples": "Testable Examples in Go",
                "https://go.dev/blog/table-driven-tests": "Table Driven Tests",
                "https://go.dev/blog/govulncheck": "Govulncheck v1.0.0 is Released",
                "https://go.dev/blog/wasm": "Go and WebAssembly",
                "https://go.dev/blog/survey2024-h1-results": "Go Developer Survey 2024 H1 Results",
                "https://go.dev/blog/routing-enhancements": "Routing Enhancements for Go 1.22",
                "https://go.dev/blog/execution-traces-2024": "More Powerful Go Execution Traces",
                "https://go.dev/blog/generic-slice-functions": "Robust Generic Functions on Slices",
            },
        },
        "stdlib": {
            "pages": {
                # Standard library - key packages
                "https://pkg.go.dev/fmt": "fmt",
                "https://pkg.go.dev/io": "io",
                "https://pkg.go.dev/os": "os",
                "https://pkg.go.dev/net": "net",
                "https://pkg.go.dev/net/http": "net/http",
                "https://pkg.go.dev/encoding/json": "encoding/json",
                "https://pkg.go.dev/sync": "sync",
                "https://pkg.go.dev/context": "context",
                "https://pkg.go.dev/errors": "errors",
                "https://pkg.go.dev/log": "log",
                "https://pkg.go.dev/log/slog": "log/slog",
                "https://pkg.go.dev/strings": "strings",
                "https://pkg.go.dev/bytes": "bytes",
                "https://pkg.go.dev/strconv": "strconv",
                "https://pkg.go.dev/sort": "sort",
                "https://pkg.go.dev/slices": "slices",
                "https://pkg.go.dev/maps": "maps",
                "https://pkg.go.dev/regexp": "regexp",
                "https://pkg.go.dev/path/filepath": "path/filepath",
                "https://pkg.go.dev/time": "time",
                "https://pkg.go.dev/math": "math",
                "https://pkg.go.dev/crypto": "crypto",
                "https://pkg.go.dev/database/sql": "database/sql",
                "https://pkg.go.dev/html/template": "html/template",
                "https://pkg.go.dev/text/template": "text/template",
                "https://pkg.go.dev/flag": "flag",
                "https://pkg.go.dev/testing": "testing",
                "https://pkg.go.dev/reflect": "reflect",
                "https://pkg.go.dev/unsafe": "unsafe",
                "https://pkg.go.dev/runtime": "runtime",
                "https://pkg.go.dev/syscall": "syscall",
                "https://pkg.go.dev/bufio": "bufio",
                "https://pkg.go.dev/archive/tar": "archive/tar",
                "https://pkg.go.dev/archive/zip": "archive/zip",
                "https://pkg.go.dev/compress/gzip": "compress/gzip",
                "https://pkg.go.dev/embed": "embed",
                "https://pkg.go.dev/go/ast": "go/ast",
                "https://pkg.go.dev/go/parser": "go/parser",
                "https://pkg.go.dev/go/format": "go/format",
                "https://pkg.go.dev/go/build": "go/build",
                "https://pkg.go.dev/go/types": "go/types",
                "https://pkg.go.dev/debug/dwarf": "debug/dwarf",
                "https://pkg.go.dev/debug/elf": "debug/elf",
                # Additional key packages
                "https://pkg.go.dev/encoding/xml": "encoding/xml",
                "https://pkg.go.dev/encoding/csv": "encoding/csv",
                "https://pkg.go.dev/encoding/binary": "encoding/binary",
                "https://pkg.go.dev/encoding/base64": "encoding/base64",
                "https://pkg.go.dev/encoding/hex": "encoding/hex",
                "https://pkg.go.dev/io/fs": "io/fs",
                "https://pkg.go.dev/os/exec": "os/exec",
                "https://pkg.go.dev/os/signal": "os/signal",
                "https://pkg.go.dev/net/url": "net/url",
                "https://pkg.go.dev/net/http/httptest": "net/http/httptest",
                "https://pkg.go.dev/crypto/tls": "crypto/tls",
                "https://pkg.go.dev/crypto/sha256": "crypto/sha256",
                "https://pkg.go.dev/crypto/rand": "crypto/rand",
                "https://pkg.go.dev/sync/atomic": "sync/atomic",
                "https://pkg.go.dev/math/rand/v2": "math/rand/v2",
                "https://pkg.go.dev/path": "path",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"golang-{source_key}" if source_key else "golang"
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
            for suffix in [
                ' - The Go Programming Language',
                ' - Go',
                ' - go.dev',
            ]:
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
                        "category": "golang-docs",
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
            self.log.info(f"=== Scraping golang/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    GolangScraper(base, source_key).run()
