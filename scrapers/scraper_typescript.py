#!/usr/bin/env python3
"""TypeScript documentation scraper.

Covers:
  - TypeScript Handbook (basics, types, narrowing, functions, etc.)
  - TypeScript Reference (utility types, decorators, enums, modules, etc.)
  - Declaration Files (authoring, publishing, consuming)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class TypeScriptScraper(BaseScraper):
    """Scrape TypeScript documentation from typescriptlang.org."""

    SOURCES = {
        "handbook": {
            "pages": {
                # Getting Started
                "https://www.typescriptlang.org/docs/handbook/typescript-from-scratch.html": "TypeScript for the New Programmer",
                "https://www.typescriptlang.org/docs/handbook/typescript-in-5-minutes.html": "TypeScript in 5 Minutes",
                "https://www.typescriptlang.org/docs/handbook/typescript-in-5-minutes-oop.html": "TypeScript for Java/C# Programmers",
                "https://www.typescriptlang.org/docs/handbook/typescript-in-5-minutes-func.html": "TypeScript for Functional Programmers",
                "https://www.typescriptlang.org/docs/handbook/typescript-tooling-in-5-minutes.html": "TypeScript Tooling in 5 Minutes",
                # Handbook - The Basics
                "https://www.typescriptlang.org/docs/handbook/2/basic-types.html": "TypeScript The Basics",
                "https://www.typescriptlang.org/docs/handbook/2/everyday-types.html": "TypeScript Everyday Types",
                "https://www.typescriptlang.org/docs/handbook/2/narrowing.html": "TypeScript Narrowing",
                "https://www.typescriptlang.org/docs/handbook/2/functions.html": "TypeScript More on Functions",
                "https://www.typescriptlang.org/docs/handbook/2/objects.html": "TypeScript Object Types",
                # Handbook - Type Manipulation
                "https://www.typescriptlang.org/docs/handbook/2/types-from-types.html": "TypeScript Creating Types from Types",
                "https://www.typescriptlang.org/docs/handbook/2/generics.html": "TypeScript Generics",
                "https://www.typescriptlang.org/docs/handbook/2/keyof-types.html": "TypeScript Keyof Type Operator",
                "https://www.typescriptlang.org/docs/handbook/2/typeof-types.html": "TypeScript Typeof Type Operator",
                "https://www.typescriptlang.org/docs/handbook/2/indexed-access-types.html": "TypeScript Indexed Access Types",
                "https://www.typescriptlang.org/docs/handbook/2/conditional-types.html": "TypeScript Conditional Types",
                "https://www.typescriptlang.org/docs/handbook/2/mapped-types.html": "TypeScript Mapped Types",
                "https://www.typescriptlang.org/docs/handbook/2/template-literal-types.html": "TypeScript Template Literal Types",
                # Handbook - Classes
                "https://www.typescriptlang.org/docs/handbook/2/classes.html": "TypeScript Classes",
                # Handbook - Modules
                "https://www.typescriptlang.org/docs/handbook/2/modules.html": "TypeScript Modules",
                # Handbook - Additional
                "https://www.typescriptlang.org/docs/handbook/type-compatibility.html": "TypeScript Type Compatibility",
                "https://www.typescriptlang.org/docs/handbook/type-inference.html": "TypeScript Type Inference",
                "https://www.typescriptlang.org/docs/handbook/variable-declarations.html": "TypeScript Variable Declarations",
                "https://www.typescriptlang.org/docs/handbook/interfaces.html": "TypeScript Interfaces",
                "https://www.typescriptlang.org/docs/handbook/unions-and-intersections.html": "TypeScript Unions and Intersections",
                "https://www.typescriptlang.org/docs/handbook/literal-types.html": "TypeScript Literal Types",
                "https://www.typescriptlang.org/docs/handbook/advanced-types.html": "TypeScript Advanced Types",
                "https://www.typescriptlang.org/docs/handbook/type-checking-javascript-files.html": "TypeScript Type Checking JavaScript Files",
                "https://www.typescriptlang.org/docs/handbook/jsdoc-supported-types.html": "TypeScript JSDoc Reference",
                "https://www.typescriptlang.org/docs/handbook/dom-manipulation.html": "TypeScript DOM Manipulation",
                "https://www.typescriptlang.org/docs/handbook/migrating-from-javascript.html": "TypeScript Migrating from JavaScript",
            },
        },
        "reference": {
            "pages": {
                # Utility Types
                "https://www.typescriptlang.org/docs/handbook/utility-types.html": "TypeScript Utility Types",
                # Decorators
                "https://www.typescriptlang.org/docs/handbook/decorators.html": "TypeScript Decorators",
                # Declaration Files
                "https://www.typescriptlang.org/docs/handbook/declaration-files/introduction.html": "TypeScript Declaration Files Introduction",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/by-example.html": "TypeScript Declaration Files By Example",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/library-structures.html": "TypeScript Library Structures",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/templates.html": "TypeScript Declaration Templates",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/do-s-and-don-ts.html": "TypeScript Declaration Do's and Don'ts",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/deep-dive.html": "TypeScript Declaration Deep Dive",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/publishing.html": "TypeScript Declaration Publishing",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/consumption.html": "TypeScript Declaration Consumption",
                # Enums
                "https://www.typescriptlang.org/docs/handbook/enums.html": "TypeScript Enums",
                # Modules
                "https://www.typescriptlang.org/docs/handbook/modules.html": "TypeScript Modules (Reference)",
                "https://www.typescriptlang.org/docs/handbook/module-resolution.html": "TypeScript Module Resolution",
                "https://www.typescriptlang.org/docs/handbook/modules/introduction.html": "TypeScript Modules Introduction",
                "https://www.typescriptlang.org/docs/handbook/modules/theory.html": "TypeScript Modules Theory",
                "https://www.typescriptlang.org/docs/handbook/modules/guides/choosing-compiler-options.html": "TypeScript Choosing Compiler Options",
                "https://www.typescriptlang.org/docs/handbook/modules/reference.html": "TypeScript Module Reference",
                # Namespaces
                "https://www.typescriptlang.org/docs/handbook/namespaces.html": "TypeScript Namespaces",
                "https://www.typescriptlang.org/docs/handbook/namespaces-and-modules.html": "TypeScript Namespaces and Modules",
                # Symbols
                "https://www.typescriptlang.org/docs/handbook/symbols.html": "TypeScript Symbols",
                # Type Compatibility
                "https://www.typescriptlang.org/docs/handbook/type-compatibility.html": "TypeScript Type Compatibility (Reference)",
                # JSX
                "https://www.typescriptlang.org/docs/handbook/jsx.html": "TypeScript JSX",
                # Iterators and Generators
                "https://www.typescriptlang.org/docs/handbook/iterators-and-generators.html": "TypeScript Iterators and Generators",
                # Mixins
                "https://www.typescriptlang.org/docs/handbook/mixins.html": "TypeScript Mixins",
                # Triple-Slash Directives
                "https://www.typescriptlang.org/docs/handbook/triple-slash-directives.html": "TypeScript Triple-Slash Directives",
                # Project Configuration
                "https://www.typescriptlang.org/docs/handbook/tsconfig-json.html": "TypeScript tsconfig.json",
                "https://www.typescriptlang.org/docs/handbook/compiler-options.html": "TypeScript Compiler Options",
                "https://www.typescriptlang.org/docs/handbook/project-references.html": "TypeScript Project References",
                "https://www.typescriptlang.org/docs/handbook/compiler-options-in-msbuild.html": "TypeScript Compiler Options in MSBuild",
                "https://www.typescriptlang.org/docs/handbook/integrating-with-build-tools.html": "TypeScript Integrating with Build Tools",
                "https://www.typescriptlang.org/docs/handbook/configuring-watch.html": "TypeScript Configuring Watch Mode",
                "https://www.typescriptlang.org/docs/handbook/nightly-builds.html": "TypeScript Nightly Builds",
                # What's New
                "https://www.typescriptlang.org/docs/handbook/release-notes/overview.html": "TypeScript Release Notes Overview",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-0.html": "TypeScript 5.0 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-1.html": "TypeScript 5.1 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-2.html": "TypeScript 5.2 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-3.html": "TypeScript 5.3 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-4.html": "TypeScript 5.4 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-5.html": "TypeScript 5.5 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-6.html": "TypeScript 5.6 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-9.html": "TypeScript 4.9 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-8.html": "TypeScript 4.8 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-7.html": "TypeScript 4.7 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-6.html": "TypeScript 4.6 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-5.html": "TypeScript 4.5 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-4.html": "TypeScript 4.4 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-3.html": "TypeScript 4.3 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-2.html": "TypeScript 4.2 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-1.html": "TypeScript 4.1 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-0.html": "TypeScript 4.0 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-3-9.html": "TypeScript 3.9 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-3-8.html": "TypeScript 3.8 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-3-7.html": "TypeScript 3.7 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-3-6.html": "TypeScript 3.6 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-3-5.html": "TypeScript 3.5 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-3-4.html": "TypeScript 3.4 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-3-3.html": "TypeScript 3.3 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-3-2.html": "TypeScript 3.2 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-3-1.html": "TypeScript 3.1 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-3-0.html": "TypeScript 3.0 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-2-9.html": "TypeScript 2.9 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-2-8.html": "TypeScript 2.8 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-2-7.html": "TypeScript 2.7 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-2-6.html": "TypeScript 2.6 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-2-5.html": "TypeScript 2.5 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-2-4.html": "TypeScript 2.4 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-2-3.html": "TypeScript 2.3 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-2-2.html": "TypeScript 2.2 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-2-1.html": "TypeScript 2.1 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-2-0.html": "TypeScript 2.0 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-1-8.html": "TypeScript 1.8 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-1-7.html": "TypeScript 1.7 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-1-6.html": "TypeScript 1.6 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-1-5.html": "TypeScript 1.5 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-1-4.html": "TypeScript 1.4 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-1-3.html": "TypeScript 1.3 Release Notes",
                "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-1-1.html": "TypeScript 1.1 Release Notes",
            },
        },
        "declaration-files": {
            "pages": {
                "https://www.typescriptlang.org/docs/handbook/declaration-files/introduction.html": "Declaration Files Introduction",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/by-example.html": "Declaration Files By Example",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/library-structures.html": "Declaration Files Library Structures",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/templates.html": "Declaration Files Templates",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/do-s-and-don-ts.html": "Declaration Files Do's and Don'ts",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/deep-dive.html": "Declaration Files Deep Dive",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/publishing.html": "Declaration Files Publishing",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/consumption.html": "Declaration Files Consumption",
                "https://www.typescriptlang.org/docs/handbook/declaration-files/dts-from-js.html": "Declaration Files .d.ts from .js",
                # Cheat sheets
                "https://www.typescriptlang.org/cheatsheets": "TypeScript Cheat Sheets",
                # Playground
                "https://www.typescriptlang.org/docs/handbook/babel-with-typescript.html": "TypeScript with Babel",
                # Reference pages
                "https://www.typescriptlang.org/tsconfig": "TypeScript TSConfig Reference",
                # Additional handbook pages
                "https://www.typescriptlang.org/docs/handbook/2/type-declarations.html": "TypeScript Type Declarations",
                "https://www.typescriptlang.org/docs/handbook/2/typeof-types.html": "TypeScript Typeof Types",
                # More reference topics
                "https://www.typescriptlang.org/docs/handbook/asp-net-core.html": "TypeScript ASP.NET Core",
                "https://www.typescriptlang.org/docs/handbook/gulp.html": "TypeScript with Gulp",
                "https://www.typescriptlang.org/docs/handbook/react.html": "TypeScript with React",
                "https://www.typescriptlang.org/docs/handbook/declaration-merging.html": "TypeScript Declaration Merging",
                "https://www.typescriptlang.org/docs/handbook/2/types-from-extraction.html": "TypeScript Types from Extraction",
                # Config reference pages
                "https://www.typescriptlang.org/docs/handbook/compiler-options.html": "TypeScript All Compiler Options",
                # Additional everyday types
                "https://www.typescriptlang.org/docs/handbook/2/more-on-functions.html": "TypeScript More on Functions (v2)",
                "https://www.typescriptlang.org/docs/handbook/2/narrowing.html": "TypeScript Narrowing (v2)",
                # Performance
                "https://www.typescriptlang.org/docs/handbook/performance.html": "TypeScript Performance",
                # TSConfig options (individual pages)
                "https://www.typescriptlang.org/tsconfig#target": "TypeScript TSConfig target",
                "https://www.typescriptlang.org/tsconfig#module": "TypeScript TSConfig module",
                "https://www.typescriptlang.org/tsconfig#lib": "TypeScript TSConfig lib",
                "https://www.typescriptlang.org/tsconfig#outDir": "TypeScript TSConfig outDir",
                "https://www.typescriptlang.org/tsconfig#rootDir": "TypeScript TSConfig rootDir",
                "https://www.typescriptlang.org/tsconfig#strict": "TypeScript TSConfig strict",
                "https://www.typescriptlang.org/tsconfig#esModuleInterop": "TypeScript TSConfig esModuleInterop",
                "https://www.typescriptlang.org/tsconfig#moduleResolution": "TypeScript TSConfig moduleResolution",
                "https://www.typescriptlang.org/tsconfig#resolveJsonModule": "TypeScript TSConfig resolveJsonModule",
                "https://www.typescriptlang.org/tsconfig#declaration": "TypeScript TSConfig declaration",
                "https://www.typescriptlang.org/tsconfig#declarationMap": "TypeScript TSConfig declarationMap",
                "https://www.typescriptlang.org/tsconfig#sourceMap": "TypeScript TSConfig sourceMap",
                "https://www.typescriptlang.org/tsconfig#noEmit": "TypeScript TSConfig noEmit",
                "https://www.typescriptlang.org/tsconfig#jsx": "TypeScript TSConfig jsx",
                "https://www.typescriptlang.org/tsconfig#allowJs": "TypeScript TSConfig allowJs",
                "https://www.typescriptlang.org/tsconfig#checkJs": "TypeScript TSConfig checkJs",
                "https://www.typescriptlang.org/tsconfig#noImplicitAny": "TypeScript TSConfig noImplicitAny",
                "https://www.typescriptlang.org/tsconfig#noImplicitThis": "TypeScript TSConfig noImplicitThis",
                "https://www.typescriptlang.org/tsconfig#strictNullChecks": "TypeScript TSConfig strictNullChecks",
                "https://www.typescriptlang.org/tsconfig#strictFunctionTypes": "TypeScript TSConfig strictFunctionTypes",
                "https://www.typescriptlang.org/tsconfig#strictBindCallApply": "TypeScript TSConfig strictBindCallApply",
                "https://www.typescriptlang.org/tsconfig#strictPropertyInitialization": "TypeScript TSConfig strictPropertyInitialization",
                "https://www.typescriptlang.org/tsconfig#noUnusedLocals": "TypeScript TSConfig noUnusedLocals",
                "https://www.typescriptlang.org/tsconfig#noUnusedParameters": "TypeScript TSConfig noUnusedParameters",
                "https://www.typescriptlang.org/tsconfig#noImplicitReturns": "TypeScript TSConfig noImplicitReturns",
                "https://www.typescriptlang.org/tsconfig#noFallthroughCasesInSwitch": "TypeScript TSConfig noFallthroughCasesInSwitch",
                "https://www.typescriptlang.org/tsconfig#skipLibCheck": "TypeScript TSConfig skipLibCheck",
                "https://www.typescriptlang.org/tsconfig#forceConsistentCasingInFileNames": "TypeScript TSConfig forceConsistentCasingInFileNames",
                "https://www.typescriptlang.org/tsconfig#paths": "TypeScript TSConfig paths",
                "https://www.typescriptlang.org/tsconfig#baseUrl": "TypeScript TSConfig baseUrl",
                "https://www.typescriptlang.org/tsconfig#typeRoots": "TypeScript TSConfig typeRoots",
                "https://www.typescriptlang.org/tsconfig#types": "TypeScript TSConfig types",
                "https://www.typescriptlang.org/tsconfig#incremental": "TypeScript TSConfig incremental",
                "https://www.typescriptlang.org/tsconfig#composite": "TypeScript TSConfig composite",
                "https://www.typescriptlang.org/tsconfig#tsBuildInfoFile": "TypeScript TSConfig tsBuildInfoFile",
                "https://www.typescriptlang.org/tsconfig#isolatedModules": "TypeScript TSConfig isolatedModules",
                "https://www.typescriptlang.org/tsconfig#verbatimModuleSyntax": "TypeScript TSConfig verbatimModuleSyntax",
                "https://www.typescriptlang.org/tsconfig#downlevelIteration": "TypeScript TSConfig downlevelIteration",
                "https://www.typescriptlang.org/tsconfig#importHelpers": "TypeScript TSConfig importHelpers",
                "https://www.typescriptlang.org/tsconfig#emitDecoratorMetadata": "TypeScript TSConfig emitDecoratorMetadata",
                "https://www.typescriptlang.org/tsconfig#experimentalDecorators": "TypeScript TSConfig experimentalDecorators",
                "https://www.typescriptlang.org/tsconfig#allowSyntheticDefaultImports": "TypeScript TSConfig allowSyntheticDefaultImports",
                "https://www.typescriptlang.org/tsconfig#noEmitOnError": "TypeScript TSConfig noEmitOnError",
                "https://www.typescriptlang.org/tsconfig#preserveConstEnums": "TypeScript TSConfig preserveConstEnums",
                "https://www.typescriptlang.org/tsconfig#removeComments": "TypeScript TSConfig removeComments",
                "https://www.typescriptlang.org/tsconfig#outFile": "TypeScript TSConfig outFile",
                "https://www.typescriptlang.org/tsconfig#noResolve": "TypeScript TSConfig noResolve",
                "https://www.typescriptlang.org/tsconfig#allowUmdGlobalAccess": "TypeScript TSConfig allowUmdGlobalAccess",
                "https://www.typescriptlang.org/tsconfig#moduleSuffixes": "TypeScript TSConfig moduleSuffixes",
                "https://www.typescriptlang.org/tsconfig#allowImportingTsExtensions": "TypeScript TSConfig allowImportingTsExtensions",
                "https://www.typescriptlang.org/tsconfig#customConditions": "TypeScript TSConfig customConditions",
                "https://www.typescriptlang.org/tsconfig#useDefineForClassFields": "TypeScript TSConfig useDefineForClassFields",
                "https://www.typescriptlang.org/tsconfig#exactOptionalPropertyTypes": "TypeScript TSConfig exactOptionalPropertyTypes",
                "https://www.typescriptlang.org/tsconfig#noUncheckedIndexedAccess": "TypeScript TSConfig noUncheckedIndexedAccess",
                "https://www.typescriptlang.org/tsconfig#noPropertyAccessFromIndexSignature": "TypeScript TSConfig noPropertyAccessFromIndexSignature",
                # Docs landing pages
                "https://www.typescriptlang.org/docs/": "TypeScript Documentation",
                "https://www.typescriptlang.org/docs/handbook/": "TypeScript Handbook Index",
                "https://www.typescriptlang.org/docs/handbook/intro.html": "TypeScript Handbook Introduction",
                "https://www.typescriptlang.org/download": "TypeScript Download",
                "https://www.typescriptlang.org/tools": "TypeScript Tools",
                "https://www.typescriptlang.org/play": "TypeScript Playground",
                "https://www.typescriptlang.org/dt/search": "TypeScript DefinitelyTyped Search",
                # More Handbook v2 pages
                "https://www.typescriptlang.org/docs/handbook/2/template-literal-types.html": "TypeScript Template Literal Types (v2)",
                "https://www.typescriptlang.org/docs/handbook/2/conditional-types.html": "TypeScript Conditional Types (v2)",
                "https://www.typescriptlang.org/docs/handbook/2/mapped-types.html": "TypeScript Mapped Types (v2)",
                "https://www.typescriptlang.org/docs/handbook/2/keyof-types.html": "TypeScript Keyof Types (v2)",
                "https://www.typescriptlang.org/docs/handbook/2/indexed-access-types.html": "TypeScript Indexed Access Types (v2)",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"typescript-{source_key}" if source_key else "typescript"
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
            for suffix in [' | TypeScript', ' - TypeScript', ' | TypeScript Documentation',
                           ' - TypeScript Documentation', ' | TypeScript Handbook']:
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
                        "category": f"typescript-{source_key}",
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
            self.log.info(f"=== Scraping typescript/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    TypeScriptScraper(base, source_key).run()
