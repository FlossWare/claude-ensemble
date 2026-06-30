#!/usr/bin/env python3
"""
Migrate JavaScript files to use postgres-adapter.js instead of old database adapters
Uses regex-based pattern matching with backup and dry-run mode
"""

import os
import re
import shutil
from pathlib import Path
from typing import List, Tuple

class PostgresAdapterMigrator:
    def __init__(self, dry_run: bool = True):
        """
        Initialize migrator

        Args:
            dry_run: If True, only show changes without modifying files
        """
        self.dry_run = dry_run
        self.changes = []

        # Patterns to replace
        self.patterns = [
            # Old SQLite adapter
            (
                r'const\s+{\s*getDB\s*}\s*=\s*require\([\'"].*?sqlite-adapter(?:\.js)?[\'"]\)',
                'const { getDB } = require(\'./postgres-adapter.js\')'
            ),
            # Old ChromaDB adapter
            (
                r'const\s+{\s*getVectorStore\s*}\s*=\s*require\([\'"].*?chroma-adapter(?:\.js)?[\'"]\)',
                'const { getDB } = require(\'./postgres-adapter.js\')'
            ),
            # Direct SQLite imports
            (
                r'const\s+sqlite3\s*=\s*require\([\'"]sqlite3[\'"]\)',
                'const { getDB } = require(\'./postgres-adapter.js\')'
            ),
            # Direct ChromaDB imports
            (
                r'const\s+{\s*ChromaClient\s*}\s*=\s*require\([\'"]chromadb[\'"]\)',
                'const { getDB } = require(\'./postgres-adapter.js\')'
            ),
        ]

    def find_js_files(self, root_dir: str) -> List[Path]:
        """Find all JavaScript files in directory tree"""
        js_files = []
        root_path = Path(root_dir).expanduser()

        for path in root_path.rglob('*.js'):
            # Skip node_modules and hidden directories
            if 'node_modules' in path.parts or any(p.startswith('.') for p in path.parts[:-1]):
                continue
            js_files.append(path)

        return js_files

    def check_file_needs_migration(self, file_path: Path) -> bool:
        """Check if file contains patterns that need migration"""
        try:
            content = file_path.read_text()
            for pattern, _ in self.patterns:
                if re.search(pattern, content):
                    return True
            return False
        except Exception as e:
            print(f"⚠ Warning: Could not read {file_path}: {e}")
            return False

    def migrate_file(self, file_path: Path) -> Tuple[bool, int]:
        """
        Migrate a single file

        Returns:
            (success, num_replacements)
        """
        try:
            content = file_path.read_text()
            original_content = content
            num_replacements = 0

            # Apply all patterns
            for pattern, replacement in self.patterns:
                content, count = re.subn(pattern, replacement, content)
                num_replacements += count

            # If changes were made
            if content != original_content:
                if not self.dry_run:
                    # Create backup
                    backup_path = file_path.with_suffix('.js.bak')
                    shutil.copy2(file_path, backup_path)

                    # Write updated content
                    file_path.write_text(content)

                self.changes.append({
                    'file': str(file_path),
                    'replacements': num_replacements,
                    'dry_run': self.dry_run
                })

                return True, num_replacements

            return False, 0

        except Exception as e:
            print(f"❌ Error migrating {file_path}: {e}")
            return False, 0

    def migrate_directory(self, root_dir: str) -> None:
        """Migrate all JavaScript files in directory"""
        print(f"{'🔍' if self.dry_run else '🔧'} {'DRY RUN: Scanning' if self.dry_run else 'Migrating'} {root_dir}")
        print()

        js_files = self.find_js_files(root_dir)
        print(f"Found {len(js_files)} JavaScript files")

        # Filter files that need migration
        files_to_migrate = [f for f in js_files if self.check_file_needs_migration(f)]
        print(f"Files needing migration: {len(files_to_migrate)}")
        print()

        if not files_to_migrate:
            print("✅ No files need migration!")
            return

        # Migrate each file
        total_replacements = 0
        for file_path in files_to_migrate:
            success, replacements = self.migrate_file(file_path)
            if success:
                status = "📋 Would replace" if self.dry_run else "✅ Replaced"
                print(f"{status} {replacements} pattern(s) in {file_path}")
                total_replacements += replacements

        print()
        print(f"{'=' * 60}")
        print(f"Total files modified: {len(self.changes)}")
        print(f"Total replacements: {total_replacements}")

        if self.dry_run:
            print()
            print("⚠ DRY RUN MODE - No files were modified")
            print("Run with --execute to apply changes")
        else:
            print()
            print("✅ Migration complete!")
            print("Backup files created with .bak extension")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Migrate JS files to postgres-adapter.js")
    parser.add_argument('directory', help='Root directory to scan')
    parser.add_argument('--execute', action='store_true', help='Execute migration (default is dry-run)')
    args = parser.parse_args()

    migrator = PostgresAdapterMigrator(dry_run=not args.execute)
    migrator.migrate_directory(args.directory)

    # Print list of files that would be changed
    if migrator.changes:
        print()
        print("Files affected:")
        for change in migrator.changes:
            print(f"  - {change['file']} ({change['replacements']} replacements)")


if __name__ == "__main__":
    main()
