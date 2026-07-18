#!/usr/bin/env python3
"""Git documentation scraper.

Covers:
  - Git reference pages (git-scm.com/docs/)
  - Pro Git book chapters (git-scm.com/book/en/v2/)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class GitScraper(BaseScraper):
    """Scrape Git reference docs and Pro Git book."""

    SOURCES = {
        "reference": {
            "pages": {
                # Core commands
                "https://git-scm.com/docs/git": "git",
                "https://git-scm.com/docs/git-add": "git-add",
                "https://git-scm.com/docs/git-am": "git-am",
                "https://git-scm.com/docs/git-apply": "git-apply",
                "https://git-scm.com/docs/git-archive": "git-archive",
                "https://git-scm.com/docs/git-bisect": "git-bisect",
                "https://git-scm.com/docs/git-blame": "git-blame",
                "https://git-scm.com/docs/git-branch": "git-branch",
                "https://git-scm.com/docs/git-bundle": "git-bundle",
                "https://git-scm.com/docs/git-cat-file": "git-cat-file",
                "https://git-scm.com/docs/git-checkout": "git-checkout",
                "https://git-scm.com/docs/git-cherry-pick": "git-cherry-pick",
                "https://git-scm.com/docs/git-clean": "git-clean",
                "https://git-scm.com/docs/git-clone": "git-clone",
                "https://git-scm.com/docs/git-commit": "git-commit",
                "https://git-scm.com/docs/git-config": "git-config",
                "https://git-scm.com/docs/git-describe": "git-describe",
                "https://git-scm.com/docs/git-diff": "git-diff",
                "https://git-scm.com/docs/git-fetch": "git-fetch",
                "https://git-scm.com/docs/git-filter-branch": "git-filter-branch",
                "https://git-scm.com/docs/git-format-patch": "git-format-patch",
                "https://git-scm.com/docs/git-fsck": "git-fsck",
                "https://git-scm.com/docs/git-gc": "git-gc",
                "https://git-scm.com/docs/git-grep": "git-grep",
                "https://git-scm.com/docs/git-init": "git-init",
                "https://git-scm.com/docs/git-log": "git-log",
                "https://git-scm.com/docs/git-merge": "git-merge",
                "https://git-scm.com/docs/git-mv": "git-mv",
                "https://git-scm.com/docs/git-notes": "git-notes",
                "https://git-scm.com/docs/git-pack-objects": "git-pack-objects",
                "https://git-scm.com/docs/git-pull": "git-pull",
                "https://git-scm.com/docs/git-push": "git-push",
                "https://git-scm.com/docs/git-range-diff": "git-range-diff",
                "https://git-scm.com/docs/git-rebase": "git-rebase",
                "https://git-scm.com/docs/git-reflog": "git-reflog",
                "https://git-scm.com/docs/git-remote": "git-remote",
                "https://git-scm.com/docs/git-rerere": "git-rerere",
                "https://git-scm.com/docs/git-reset": "git-reset",
                "https://git-scm.com/docs/git-restore": "git-restore",
                "https://git-scm.com/docs/git-revert": "git-revert",
                "https://git-scm.com/docs/git-rev-parse": "git-rev-parse",
                "https://git-scm.com/docs/git-rm": "git-rm",
                "https://git-scm.com/docs/git-send-email": "git-send-email",
                "https://git-scm.com/docs/git-shortlog": "git-shortlog",
                "https://git-scm.com/docs/git-show": "git-show",
                "https://git-scm.com/docs/git-sparse-checkout": "git-sparse-checkout",
                "https://git-scm.com/docs/git-stash": "git-stash",
                "https://git-scm.com/docs/git-status": "git-status",
                "https://git-scm.com/docs/git-submodule": "git-submodule",
                "https://git-scm.com/docs/git-switch": "git-switch",
                "https://git-scm.com/docs/git-tag": "git-tag",
                "https://git-scm.com/docs/git-worktree": "git-worktree",
                # Special reference pages
                "https://git-scm.com/docs/gitattributes": "gitattributes",
                "https://git-scm.com/docs/gitignore": "gitignore",
                "https://git-scm.com/docs/gitmodules": "gitmodules",
                "https://git-scm.com/docs/gitrevisions": "gitrevisions",
                "https://git-scm.com/docs/githooks": "githooks",
                "https://git-scm.com/docs/gitcredentials": "gitcredentials",
            },
        },
        "book": {
            "pages": {
                # Ch1 - Getting Started
                "https://git-scm.com/book/en/v2/Getting-Started-About-Version-Control": "Getting Started - About Version Control",
                "https://git-scm.com/book/en/v2/Getting-Started-A-Short-History-of-Git": "Getting Started - A Short History of Git",
                "https://git-scm.com/book/en/v2/Getting-Started-What-is-Git%3F": "Getting Started - What is Git?",
                "https://git-scm.com/book/en/v2/Getting-Started-The-Command-Line": "Getting Started - The Command Line",
                "https://git-scm.com/book/en/v2/Getting-Started-Installing-Git": "Getting Started - Installing Git",
                "https://git-scm.com/book/en/v2/Getting-Started-First-Time-Git-Setup": "Getting Started - First-Time Git Setup",
                "https://git-scm.com/book/en/v2/Getting-Started-Getting-Help": "Getting Started - Getting Help",
                # Ch2 - Git Basics
                "https://git-scm.com/book/en/v2/Git-Basics-Getting-a-Git-Repository": "Git Basics - Getting a Git Repository",
                "https://git-scm.com/book/en/v2/Git-Basics-Recording-Changes-to-the-Repository": "Git Basics - Recording Changes",
                "https://git-scm.com/book/en/v2/Git-Basics-Viewing-the-Commit-History": "Git Basics - Viewing Commit History",
                "https://git-scm.com/book/en/v2/Git-Basics-Undoing-Things": "Git Basics - Undoing Things",
                "https://git-scm.com/book/en/v2/Git-Basics-Working-with-Remotes": "Git Basics - Working with Remotes",
                "https://git-scm.com/book/en/v2/Git-Basics-Tagging": "Git Basics - Tagging",
                "https://git-scm.com/book/en/v2/Git-Basics-Git-Aliases": "Git Basics - Git Aliases",
                # Ch3 - Git Branching
                "https://git-scm.com/book/en/v2/Git-Branching-Branches-in-a-Nutshell": "Git Branching - Branches in a Nutshell",
                "https://git-scm.com/book/en/v2/Git-Branching-Basic-Branching-and-Merging": "Git Branching - Basic Branching and Merging",
                "https://git-scm.com/book/en/v2/Git-Branching-Branch-Management": "Git Branching - Branch Management",
                "https://git-scm.com/book/en/v2/Git-Branching-Branching-Workflows": "Git Branching - Branching Workflows",
                "https://git-scm.com/book/en/v2/Git-Branching-Remote-Branches": "Git Branching - Remote Branches",
                "https://git-scm.com/book/en/v2/Git-Branching-Rebasing": "Git Branching - Rebasing",
                # Ch4 - Git on the Server
                "https://git-scm.com/book/en/v2/Git-on-the-Server-The-Protocols": "Git on the Server - The Protocols",
                "https://git-scm.com/book/en/v2/Git-on-the-Server-Getting-Git-on-a-Server": "Git on the Server - Getting Git on a Server",
                "https://git-scm.com/book/en/v2/Git-on-the-Server-Generating-Your-SSH-Public-Key": "Git on the Server - SSH Public Key",
                "https://git-scm.com/book/en/v2/Git-on-the-Server-Setting-Up-the-Server": "Git on the Server - Setting Up the Server",
                "https://git-scm.com/book/en/v2/Git-on-the-Server-Git-Daemon": "Git on the Server - Git Daemon",
                "https://git-scm.com/book/en/v2/Git-on-the-Server-Smart-HTTP": "Git on the Server - Smart HTTP",
                "https://git-scm.com/book/en/v2/Git-on-the-Server-GitWeb": "Git on the Server - GitWeb",
                "https://git-scm.com/book/en/v2/Git-on-the-Server-GitLab": "Git on the Server - GitLab",
                # Ch5 - Distributed Git
                "https://git-scm.com/book/en/v2/Distributed-Git-Distributed-Workflows": "Distributed Git - Distributed Workflows",
                "https://git-scm.com/book/en/v2/Distributed-Git-Contributing-to-a-Project": "Distributed Git - Contributing to a Project",
                "https://git-scm.com/book/en/v2/Distributed-Git-Maintaining-a-Project": "Distributed Git - Maintaining a Project",
                # Ch6 - GitHub
                "https://git-scm.com/book/en/v2/GitHub-Account-Setup-and-Configuration": "GitHub - Account Setup and Configuration",
                "https://git-scm.com/book/en/v2/GitHub-Contributing-to-a-Project": "GitHub - Contributing to a Project",
                "https://git-scm.com/book/en/v2/GitHub-Maintaining-a-Project": "GitHub - Maintaining a Project",
                "https://git-scm.com/book/en/v2/GitHub-Managing-an-organization": "GitHub - Managing an Organization",
                "https://git-scm.com/book/en/v2/GitHub-Scripting-GitHub": "GitHub - Scripting GitHub",
                # Ch7 - Git Tools
                "https://git-scm.com/book/en/v2/Git-Tools-Revision-Selection": "Git Tools - Revision Selection",
                "https://git-scm.com/book/en/v2/Git-Tools-Interactive-Staging": "Git Tools - Interactive Staging",
                "https://git-scm.com/book/en/v2/Git-Tools-Stashing-and-Cleaning": "Git Tools - Stashing and Cleaning",
                "https://git-scm.com/book/en/v2/Git-Tools-Signing-Your-Work": "Git Tools - Signing Your Work",
                "https://git-scm.com/book/en/v2/Git-Tools-Searching": "Git Tools - Searching",
                "https://git-scm.com/book/en/v2/Git-Tools-Rewriting-History": "Git Tools - Rewriting History",
                "https://git-scm.com/book/en/v2/Git-Tools-Reset-Demystified": "Git Tools - Reset Demystified",
                "https://git-scm.com/book/en/v2/Git-Tools-Advanced-Merging": "Git Tools - Advanced Merging",
                "https://git-scm.com/book/en/v2/Git-Tools-Rerere": "Git Tools - Rerere",
                "https://git-scm.com/book/en/v2/Git-Tools-Debugging-with-Git": "Git Tools - Debugging with Git",
                "https://git-scm.com/book/en/v2/Git-Tools-Submodules": "Git Tools - Submodules",
                "https://git-scm.com/book/en/v2/Git-Tools-Bundling": "Git Tools - Bundling",
                "https://git-scm.com/book/en/v2/Git-Tools-Replace": "Git Tools - Replace",
                "https://git-scm.com/book/en/v2/Git-Tools-Credential-Storage": "Git Tools - Credential Storage",
                # Ch8 - Customizing Git
                "https://git-scm.com/book/en/v2/Customizing-Git-Git-Configuration": "Customizing Git - Git Configuration",
                "https://git-scm.com/book/en/v2/Customizing-Git-Git-Attributes": "Customizing Git - Git Attributes",
                "https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks": "Customizing Git - Git Hooks",
                "https://git-scm.com/book/en/v2/Customizing-Git-An-Example-Git-Enforced-Policy": "Customizing Git - An Example Git-Enforced Policy",
                # Ch9 - Git and Other Systems
                "https://git-scm.com/book/en/v2/Git-and-Other-Systems-Git-as-a-Client": "Git and Other Systems - Git as a Client",
                "https://git-scm.com/book/en/v2/Git-and-Other-Systems-Migrating-to-Git": "Git and Other Systems - Migrating to Git",
                # Ch10 - Git Internals
                "https://git-scm.com/book/en/v2/Git-Internals-Plumbing-and-Porcelain": "Git Internals - Plumbing and Porcelain",
                "https://git-scm.com/book/en/v2/Git-Internals-Git-Objects": "Git Internals - Git Objects",
                "https://git-scm.com/book/en/v2/Git-Internals-Git-References": "Git Internals - Git References",
                "https://git-scm.com/book/en/v2/Git-Internals-Packfiles": "Git Internals - Packfiles",
                "https://git-scm.com/book/en/v2/Git-Internals-The-Refspec": "Git Internals - The Refspec",
                "https://git-scm.com/book/en/v2/Git-Internals-Transfer-Protocols": "Git Internals - Transfer Protocols",
                "https://git-scm.com/book/en/v2/Git-Internals-Maintenance-and-Data-Recovery": "Git Internals - Maintenance and Data Recovery",
                "https://git-scm.com/book/en/v2/Git-Internals-Environment-Variables": "Git Internals - Environment Variables",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"git-{source_key}" if source_key else "git"
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
            for suffix in [' - Git', ' :: Git Documentation',
                           ' | Git', ' - git-scm.com']:
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
                        "category": "git-docs",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.0)  # Respectful rate limit

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
            self.log.info(f"=== Scraping git/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    GitScraper(base, source_key).run()
