#!/usr/bin/env python3
"""POSIX / Open Group Base Specifications scraper.

Covers:
  - Base Definitions: general concepts, terminology, locale, environment
  - System Interfaces: POSIX system calls and library functions
  - Shell & Utilities: shell command language, standard utilities
  - Headers: standard C/POSIX header files
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class PosixScraper(BaseScraper):
    """Scrape POSIX/Open Group Base Specifications."""

    SOURCES = {
        "base-definitions": {
            "pages": {
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap01.html": "Introduction",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap02.html": "Conformance",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap03.html": "Definitions",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap04.html": "General Concepts",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap05.html": "File Format Notation",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap06.html": "Character Set",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap07.html": "Locale",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap08.html": "Environment Variables",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap09.html": "Regular Expressions",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap10.html": "Directory Structure and Devices",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap11.html": "General Terminal Interface",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap12.html": "Utility Conventions",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap13.html": "Headers",
            },
        },
        "system-interfaces": {
            "pages": {
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/open.html": "open() - Open File",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/close.html": "close() - Close File Descriptor",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/read.html": "read() - Read from File",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/write.html": "write() - Write to File",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/lseek.html": "lseek() - Seek in File",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/fork.html": "fork() - Create Process",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/exec.html": "exec - Execute Program",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/execve.html": "execve() - Execute Program",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/wait.html": "wait() - Wait for Process",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/waitpid.html": "waitpid() - Wait for Specific Process",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/pipe.html": "pipe() - Create Pipe",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/dup.html": "dup() - Duplicate File Descriptor",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/dup2.html": "dup2() - Duplicate File Descriptor",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/stat.html": "stat() - File Status",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/fstat.html": "fstat() - File Status by Descriptor",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/mmap.html": "mmap() - Memory Map",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/munmap.html": "munmap() - Unmap Memory",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/select.html": "select() - Synchronous I/O Multiplexing",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/poll.html": "poll() - I/O Multiplexing",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/socket.html": "socket() - Create Socket",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/bind.html": "bind() - Bind Socket",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/listen.html": "listen() - Listen on Socket",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/accept.html": "accept() - Accept Connection",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/connect.html": "connect() - Connect Socket",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/send.html": "send() - Send on Socket",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/recv.html": "recv() - Receive on Socket",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/pthread_create.html": "pthread_create() - Create Thread",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/pthread_join.html": "pthread_join() - Join Thread",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/pthread_mutex_init.html": "pthread_mutex_init() - Initialize Mutex",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/pthread_mutex_lock.html": "pthread_mutex_lock() - Lock Mutex",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/pthread_cond_wait.html": "pthread_cond_wait() - Condition Wait",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/pthread_cond_signal.html": "pthread_cond_signal() - Signal Condition",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/signal.html": "signal() - Signal Management",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/sigaction.html": "sigaction() - Examine/Change Signal Action",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/kill.html": "kill() - Send Signal",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/malloc.html": "malloc() - Allocate Memory",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/free.html": "free() - Free Memory",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/getenv.html": "getenv() - Get Environment Variable",
                "https://pubs.opengroup.org/onlinepubs/9699919799/functions/setenv.html": "setenv() - Set Environment Variable",
            },
        },
        "shell-utilities": {
            "pages": {
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html": "Shell Command Language",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/awk.html": "awk - Pattern Processing",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/sed.html": "sed - Stream Editor",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/grep.html": "grep - File Pattern Search",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/find.html": "find - Find Files",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/make.html": "make - Build Utility",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/sh.html": "sh - Shell",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/test.html": "test - Evaluate Expression",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/sort.html": "sort - Sort Lines",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/cut.html": "cut - Cut Fields",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/tr.html": "tr - Translate Characters",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/xargs.html": "xargs - Construct Argument Lists",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/cp.html": "cp - Copy Files",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/mv.html": "mv - Move Files",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/rm.html": "rm - Remove Files",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/ls.html": "ls - List Directory",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/chmod.html": "chmod - Change File Modes",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/chown.html": "chown - Change File Owner",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/ps.html": "ps - Report Process Status",
                "https://pubs.opengroup.org/onlinepubs/9699919799/utilities/kill.html": "kill - Send Signal to Process",
            },
        },
        "headers": {
            "pages": {
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/stdio.h.html": "stdio.h - Standard I/O",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/stdlib.h.html": "stdlib.h - Standard Library",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/unistd.h.html": "unistd.h - POSIX API",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/pthread.h.html": "pthread.h - Threads",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/signal.h.html": "signal.h - Signals",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/fcntl.h.html": "fcntl.h - File Control",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/sys_types.h.html": "sys/types.h - Data Types",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/sys_stat.h.html": "sys/stat.h - File Status",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/sys_socket.h.html": "sys/socket.h - Sockets",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/sys_mman.h.html": "sys/mman.h - Memory Management",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/sys_wait.h.html": "sys/wait.h - Process Wait",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/string.h.html": "string.h - String Operations",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/errno.h.html": "errno.h - Error Numbers",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/netinet_in.h.html": "netinet/in.h - Internet Protocol",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/arpa_inet.h.html": "arpa/inet.h - Internet Operations",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/dirent.h.html": "dirent.h - Directory Entries",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/semaphore.h.html": "semaphore.h - Semaphores",
                "https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/time.h.html": "time.h - Time Types",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"posix-{source_key}" if source_key else "posix"
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
            for suffix in [' - The Open Group Base Specifications',
                           ' - IEEE Std 1003.1', ' | POSIX']:
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
                        "category": f"posix-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)  # Rate limit

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
            self.log.info(f"=== Scraping posix/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    PosixScraper(base, source_key).run()
