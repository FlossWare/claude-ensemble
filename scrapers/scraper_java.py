#!/usr/bin/env python3
"""Java / OpenJDK documentation scraper.

Covers:
  - dev.java guides (language features, getting started, pattern matching, records, sealed classes)
  - docs.oracle.com JDK 21 API overviews, JVM tuning, tools, security, concurrency, networking, collections
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


DEV = "https://dev.java"
ORA = "https://docs.oracle.com/en/java/javase/21/docs"
ORA_CORE = "https://docs.oracle.com/en/java/javase/21"
SPECS = "https://docs.oracle.com/javase/specs/jls/se21/html"


class JavaScraper(BaseScraper):
    """Scrape Java / OpenJDK documentation from dev.java and docs.oracle.com."""

    SOURCES = {
        "language": {
            "pages": {
                # === dev.java language guides ===
                f"{DEV}/learn/": "Learn Java",
                f"{DEV}/learn/getting-started/": "Getting Started with Java",
                f"{DEV}/learn/getting-started-with-java/": "Getting Started with Java (alt)",
                f"{DEV}/learn/language-basics/": "Language Basics",
                f"{DEV}/learn/oop/": "Object-Oriented Programming Concepts",
                f"{DEV}/learn/classes-objects/": "Classes and Objects",
                f"{DEV}/learn/inheritance/": "Inheritance",
                f"{DEV}/learn/interfaces/": "Interfaces",
                f"{DEV}/learn/lambdas/": "Lambda Expressions",
                f"{DEV}/learn/records/": "Records",
                f"{DEV}/learn/sealed-classes/": "Sealed Classes",
                f"{DEV}/learn/pattern-matching/": "Pattern Matching",
                f"{DEV}/learn/switch-expression/": "Switch Expressions",
                f"{DEV}/learn/text-blocks/": "Text Blocks",
                f"{DEV}/learn/generics/": "Generics",
                f"{DEV}/learn/annotations/": "Annotations",
                f"{DEV}/learn/exceptions/": "Exceptions",
                f"{DEV}/learn/numbers-strings/": "Numbers and Strings",
                f"{DEV}/learn/strings/": "Strings",
                f"{DEV}/learn/enums/": "Enum Types",

                # === JLS highlights ===
                f"{SPECS}/jls-4.html": "JLS: Types, Values, and Variables",
                f"{SPECS}/jls-8.html": "JLS: Classes",
                f"{SPECS}/jls-9.html": "JLS: Interfaces",
                f"{SPECS}/jls-14.html": "JLS: Blocks, Statements, and Patterns",
                f"{SPECS}/jls-15.html": "JLS: Expressions",
            },
        },
        "api": {
            "pages": {
                # === JDK 21 API overview ===
                f"{ORA}/api/index.html": "JDK 21 API Index",
                f"{ORA}/api/java.base/module-summary.html": "java.base Module Summary",
                f"{ORA}/api/java.base/java/lang/package-summary.html": "java.lang Package",
                f"{ORA}/api/java.base/java/lang/String.html": "java.lang.String",
                f"{ORA}/api/java.base/java/lang/Object.html": "java.lang.Object",
                f"{ORA}/api/java.base/java/lang/Thread.html": "java.lang.Thread",
                f"{ORA}/api/java.base/java/lang/System.html": "java.lang.System",
                f"{ORA}/api/java.base/java/io/package-summary.html": "java.io Package",
                f"{ORA}/api/java.base/java/nio/package-summary.html": "java.nio Package",
                f"{ORA}/api/java.base/java/nio/file/package-summary.html": "java.nio.file Package",
                f"{ORA}/api/java.base/java/nio/file/Path.html": "java.nio.file.Path",
                f"{ORA}/api/java.base/java/nio/file/Files.html": "java.nio.file.Files",
                f"{ORA}/api/java.base/java/math/package-summary.html": "java.math Package",
                f"{ORA}/api/java.base/java/time/package-summary.html": "java.time Package",
                f"{ORA}/api/java.base/java/text/package-summary.html": "java.text Package",
                f"{ORA}/api/java.base/java/util/regex/package-summary.html": "java.util.regex Package",
            },
        },
        "jvm": {
            "pages": {
                # === JVM tuning and diagnostics ===
                f"{ORA_CORE}/docs/specs/man/java.html": "java Launcher Reference",
                f"{DEV}/learn/jvm/": "Understanding the JVM",
                f"{DEV}/learn/jvm/tool/": "JVM Diagnostic Tools",

                # === Garbage Collection ===
                f"https://docs.oracle.com/en/java/javase/21/gctuning/introduction-garbage-collection-tuning.html": "GC Tuning: Introduction",
                f"https://docs.oracle.com/en/java/javase/21/gctuning/ergonomics.html": "GC Tuning: Ergonomics",
                f"https://docs.oracle.com/en/java/javase/21/gctuning/garbage-collector-implementation.html": "GC Tuning: GC Implementation",
                f"https://docs.oracle.com/en/java/javase/21/gctuning/available-collectors.html": "GC Tuning: Available Collectors",
                f"https://docs.oracle.com/en/java/javase/21/gctuning/parallel-collector1.html": "GC Tuning: Parallel Collector",
                f"https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-g1-garbage-collector1.html": "GC Tuning: G1 Garbage Collector",
                f"https://docs.oracle.com/en/java/javase/21/gctuning/z-garbage-collector.html": "GC Tuning: ZGC",
                f"https://docs.oracle.com/en/java/javase/21/gctuning/other-considerations.html": "GC Tuning: Other Considerations",

                # === JFR / Monitoring ===
                f"https://docs.oracle.com/en/java/javase/21/jfapi/why-use-jfr-api.html": "JFR API: Overview",
                f"https://docs.oracle.com/en/java/javase/21/troubleshoot/diagnostic-tools.html": "Troubleshooting: Diagnostic Tools",
                f"https://docs.oracle.com/en/java/javase/21/troubleshoot/general-java-troubleshooting.html": "Troubleshooting: General",

                # === Shenandoah (OpenJDK wiki) ===
                f"https://wiki.openjdk.org/display/shenandoah/Main": "Shenandoah GC Wiki",
            },
        },
        "tools": {
            "pages": {
                # === JDK tools ===
                f"{ORA_CORE}/docs/specs/man/javac.html": "javac - Java Compiler",
                f"{ORA_CORE}/docs/specs/man/javadoc.html": "javadoc - API Documentation Generator",
                f"{ORA_CORE}/docs/specs/man/jar.html": "jar - Archive Tool",
                f"{ORA_CORE}/docs/specs/man/jlink.html": "jlink - Module Linker",
                f"{ORA_CORE}/docs/specs/man/jpackage.html": "jpackage - Packaging Tool",
                f"{ORA_CORE}/docs/specs/man/jcmd.html": "jcmd - Diagnostic Command Tool",
                f"{ORA_CORE}/docs/specs/man/jstack.html": "jstack - Stack Trace Tool",
                f"{ORA_CORE}/docs/specs/man/jmap.html": "jmap - Memory Map Tool",
                f"{ORA_CORE}/docs/specs/man/jstat.html": "jstat - Statistics Monitoring",
                f"{ORA_CORE}/docs/specs/man/jinfo.html": "jinfo - Configuration Info",
                f"{ORA_CORE}/docs/specs/man/jps.html": "jps - JVM Process Status",
                f"{ORA_CORE}/docs/specs/man/jfr.html": "jfr - Flight Recorder Tool",
                f"{ORA_CORE}/docs/specs/man/jdeps.html": "jdeps - Dependency Analyzer",
                f"{ORA_CORE}/docs/specs/man/jshell.html": "jshell - Interactive REPL",

                # === JPMS ===
                f"{DEV}/learn/modules/": "Java Platform Module System",
                f"{DEV}/learn/modules/intro/": "Introduction to Modules",
            },
        },
        "security": {
            "pages": {
                # === Security guides ===
                f"https://docs.oracle.com/en/java/javase/21/security/java-security-overview1.html": "Java Security Overview",
                f"https://docs.oracle.com/en/java/javase/21/security/java-cryptography-architecture-jca-reference-guide.html": "JCA Reference Guide",
                f"https://docs.oracle.com/en/java/javase/21/security/java-secure-socket-extension-jsse-reference-guide.html": "JSSE Reference Guide",
                f"https://docs.oracle.com/en/java/javase/21/security/java-authentication-and-authorization-service-jaas-reference-guide.html": "JAAS Reference Guide",
                f"https://docs.oracle.com/en/java/javase/21/security/java-pki-programmers-guide.html": "Java PKI Programmer's Guide",

                # === keytool ===
                f"{ORA_CORE}/docs/specs/man/keytool.html": "keytool - Key and Certificate Management",

                # === Security API ===
                f"{ORA}/api/java.base/java/security/package-summary.html": "java.security Package",
                f"{ORA}/api/java.base/javax/crypto/package-summary.html": "javax.crypto Package",
                f"{ORA}/api/java.base/javax/net/ssl/package-summary.html": "javax.net.ssl Package",
            },
        },
        "concurrency": {
            "pages": {
                # === Virtual Threads ===
                f"{DEV}/learn/virtual-threads/": "Virtual Threads",
                f"{DEV}/learn/structured-concurrency/": "Structured Concurrency",
                f"{DEV}/learn/scoped-values/": "Scoped Values",

                # === Classic concurrency ===
                f"{DEV}/learn/concurrency/": "Concurrency in Java",
                f"{DEV}/learn/threads/": "Threads",
                f"{DEV}/learn/synchronization/": "Synchronization",

                # === java.util.concurrent API ===
                f"{ORA}/api/java.base/java/util/concurrent/package-summary.html": "java.util.concurrent Package",
                f"{ORA}/api/java.base/java/util/concurrent/CompletableFuture.html": "CompletableFuture",
                f"{ORA}/api/java.base/java/util/concurrent/ExecutorService.html": "ExecutorService",
                f"{ORA}/api/java.base/java/util/concurrent/Executors.html": "Executors",
                f"{ORA}/api/java.base/java/util/concurrent/ConcurrentHashMap.html": "ConcurrentHashMap",
                f"{ORA}/api/java.base/java/util/concurrent/locks/package-summary.html": "java.util.concurrent.locks Package",
                f"{ORA}/api/java.base/java/util/concurrent/atomic/package-summary.html": "java.util.concurrent.atomic Package",
                f"{ORA}/api/java.base/java/util/concurrent/ForkJoinPool.html": "ForkJoinPool",
            },
        },
        "networking": {
            "pages": {
                # === Networking guides ===
                f"{DEV}/learn/networking/": "Networking in Java",

                # === HTTP Client ===
                f"{ORA}/api/java.net.http/java/net/http/HttpClient.html": "HttpClient",
                f"{ORA}/api/java.net.http/java/net/http/HttpRequest.html": "HttpRequest",
                f"{ORA}/api/java.net.http/java/net/http/HttpResponse.html": "HttpResponse",
                f"{ORA}/api/java.net.http/module-summary.html": "java.net.http Module",

                # === Core networking ===
                f"{ORA}/api/java.base/java/net/package-summary.html": "java.net Package",
                f"{ORA}/api/java.base/java/net/URL.html": "java.net.URL",
                f"{ORA}/api/java.base/java/net/URI.html": "java.net.URI",
                f"{ORA}/api/java.base/java/net/Socket.html": "java.net.Socket",
                f"{ORA}/api/java.base/java/net/ServerSocket.html": "java.net.ServerSocket",
            },
        },
        "collections": {
            "pages": {
                # === Collections framework ===
                f"{DEV}/learn/api/collections-framework/": "Collections Framework",
                f"{DEV}/learn/api/collections-framework/lists/": "Lists",
                f"{DEV}/learn/api/collections-framework/sets/": "Sets",
                f"{DEV}/learn/api/collections-framework/maps/": "Maps",
                f"{DEV}/learn/api/collections-framework/queues-deques/": "Queues and Deques",

                # === Stream API ===
                f"{DEV}/learn/api/streams/": "Stream API",
                f"{DEV}/learn/api/streams/map-filter-reduce/": "Map, Filter, Reduce",
                f"{DEV}/learn/api/streams/parallel-streams/": "Parallel Streams",
                f"{DEV}/learn/api/streams/optionals/": "Optionals",
                f"{DEV}/learn/api/streams/collectors/": "Collectors",

                # === Collections API ===
                f"{ORA}/api/java.base/java/util/package-summary.html": "java.util Package",
                f"{ORA}/api/java.base/java/util/List.html": "java.util.List",
                f"{ORA}/api/java.base/java/util/Map.html": "java.util.Map",
                f"{ORA}/api/java.base/java/util/Set.html": "java.util.Set",
                f"{ORA}/api/java.base/java/util/Optional.html": "java.util.Optional",
                f"{ORA}/api/java.base/java/util/Collections.html": "java.util.Collections",
                f"{ORA}/api/java.base/java/util/stream/package-summary.html": "java.util.stream Package",
                f"{ORA}/api/java.base/java/util/stream/Stream.html": "java.util.stream.Stream",
                f"{ORA}/api/java.base/java/util/stream/Collectors.html": "java.util.stream.Collectors",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"java-{source_key}" if source_key else "java"
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
            for suffix in [' - Dev.java', ' | Dev.java', ' - Oracle',
                           ' | Oracle Help Center', ' (Java SE 21)',
                           ' (Java SE 21 & JDK 21)']:
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
                        "category": f"java-{source_key}",
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
            self.log.info(f"=== Scraping java/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    JavaScraper(base, source_key).run()
