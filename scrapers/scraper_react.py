#!/usr/bin/env python3
"""React documentation scraper.

Covers:
  - react.dev learn section (describing-ui, adding-interactivity, managing-state, escape-hatches)
  - react.dev reference section (react, react-dom, hooks, components, apis)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class ReactScraper(BaseScraper):
    """Scrape React documentation from react.dev."""

    SOURCES = {
        "learn": {
            "pages": {
                # === Learn landing ===
                "https://react.dev/learn": "React Learn",

                # === Describing the UI ===
                "https://react.dev/learn/describing-the-ui": "Describing the UI",
                "https://react.dev/learn/your-first-component": "Your First Component",
                "https://react.dev/learn/importing-and-exporting-components": "Importing and Exporting Components",
                "https://react.dev/learn/writing-markup-with-jsx": "Writing Markup with JSX",
                "https://react.dev/learn/javascript-in-jsx-with-curly-braces": "JavaScript in JSX with Curly Braces",
                "https://react.dev/learn/passing-props-to-a-component": "Passing Props to a Component",
                "https://react.dev/learn/conditional-rendering": "Conditional Rendering",
                "https://react.dev/learn/rendering-lists": "Rendering Lists",
                "https://react.dev/learn/keeping-components-pure": "Keeping Components Pure",
                "https://react.dev/learn/understanding-your-ui-as-a-tree": "Understanding Your UI as a Tree",

                # === Adding Interactivity ===
                "https://react.dev/learn/adding-interactivity": "Adding Interactivity",
                "https://react.dev/learn/responding-to-events": "Responding to Events",
                "https://react.dev/learn/state-a-components-memory": "State: A Component's Memory",
                "https://react.dev/learn/render-and-commit": "Render and Commit",
                "https://react.dev/learn/state-as-a-snapshot": "State as a Snapshot",
                "https://react.dev/learn/queueing-a-series-of-state-updates": "Queueing a Series of State Updates",
                "https://react.dev/learn/updating-objects-in-state": "Updating Objects in State",
                "https://react.dev/learn/updating-arrays-in-state": "Updating Arrays in State",

                # === Managing State ===
                "https://react.dev/learn/managing-state": "Managing State",
                "https://react.dev/learn/reacting-to-input-with-state": "Reacting to Input with State",
                "https://react.dev/learn/choosing-the-state-structure": "Choosing the State Structure",
                "https://react.dev/learn/sharing-state-between-components": "Sharing State Between Components",
                "https://react.dev/learn/preserving-and-resetting-state": "Preserving and Resetting State",
                "https://react.dev/learn/extracting-state-logic-into-a-reducer": "Extracting State Logic into a Reducer",
                "https://react.dev/learn/passing-data-deeply-with-context": "Passing Data Deeply with Context",
                "https://react.dev/learn/scaling-up-with-reducer-and-context": "Scaling Up with Reducer and Context",

                # === Escape Hatches ===
                "https://react.dev/learn/escape-hatches": "Escape Hatches",
                "https://react.dev/learn/referencing-values-with-refs": "Referencing Values with Refs",
                "https://react.dev/learn/manipulating-the-dom-with-refs": "Manipulating the DOM with Refs",
                "https://react.dev/learn/synchronizing-with-effects": "Synchronizing with Effects",
                "https://react.dev/learn/you-might-not-need-an-effect": "You Might Not Need an Effect",
                "https://react.dev/learn/lifecycle-of-reactive-effects": "Lifecycle of Reactive Effects",
                "https://react.dev/learn/separating-events-from-effects": "Separating Events from Effects",
                "https://react.dev/learn/removing-effect-dependencies": "Removing Effect Dependencies",
                "https://react.dev/learn/reusing-logic-with-custom-hooks": "Reusing Logic with Custom Hooks",

                # === Quick Start / Installation ===
                "https://react.dev/learn/start-a-new-react-project": "Start a New React Project",
                "https://react.dev/learn/add-react-to-an-existing-project": "Add React to an Existing Project",
                "https://react.dev/learn/editor-setup": "Editor Setup",
                "https://react.dev/learn/react-developer-tools": "React Developer Tools",
                "https://react.dev/learn/installation": "Installation",
                "https://react.dev/learn/thinking-in-react": "Thinking in React",
                "https://react.dev/learn/tutorial-tic-tac-toe": "Tutorial: Tic-Tac-Toe",
                "https://react.dev/learn/typescript": "Using TypeScript",

                # === Additional Learn Topics ===
                "https://react.dev/learn/react-compiler": "React Compiler",
                "https://react.dev/learn/react-server-components": "React Server Components",

                # === Blog Posts ===
                "https://react.dev/blog/2024/12/05/react-19": "React 19 Announcement",
                "https://react.dev/blog/2024/04/25/react-19": "React 19 Beta",
                "https://react.dev/blog/2024/02/15/react-labs-what-we-have-been-working-on-february-2024": "React Labs Feb 2024",
                "https://react.dev/blog/2023/03/22/react-labs-what-we-have-been-working-on-march-2023": "React Labs Mar 2023",
                "https://react.dev/blog/2023/03/16/introducing-react-dev": "Introducing react.dev",
                "https://react.dev/blog/2022/06/15/react-labs-what-we-have-been-working-on-june-2022": "React Labs Jun 2022",
                "https://react.dev/blog/2022/03/29/react-v18": "React v18",
                "https://react.dev/blog/2022/03/08/react-18-upgrade-guide": "React 18 Upgrade Guide",
                "https://react.dev/blog/2021/12/17/react-conf-2021-recap": "React Conf 2021 Recap",
                "https://react.dev/blog/2021/06/08/the-plan-for-react-18": "The Plan for React 18",
                "https://react.dev/blog/2020/12/21/data-fetching-with-react-server-components": "Data Fetching with RSC",
                "https://react.dev/blog/2020/10/20/react-v17": "React v17",
                "https://react.dev/blog/2020/09/22/introducing-the-new-jsx-transform": "New JSX Transform",
                "https://react.dev/blog/2020/02/26/react-v16.13.0": "React v16.13.0",
                "https://react.dev/blog/2019/11/06/building-great-user-experiences-with-concurrent-mode-and-suspense": "Concurrent Mode and Suspense",
                "https://react.dev/blog/2019/08/08/react-v16.9.0": "React v16.9.0",
                "https://react.dev/blog/2019/02/06/react-v16.8.0": "React v16.8.0 (Hooks)",
                "https://react.dev/blog/2018/12/19/react-v-16-7": "React v16.7",
                "https://react.dev/blog/2018/11/27/react-16-roadmap": "React 16 Roadmap",
                "https://react.dev/blog/2018/10/23/react-v-16-6": "React v16.6",
                "https://react.dev/blog/2018/06/07/you-probably-dont-need-derived-state": "You Probably Dont Need Derived State",
                "https://react.dev/blog/2018/03/29/react-v-16-3": "React v16.3",
                "https://react.dev/blog/2018/03/27/update-on-async-rendering": "Update on Async Rendering",
                "https://react.dev/blog/2017/12/07/introducing-the-react-profiler": "Introducing the React Profiler",
                "https://react.dev/blog/2017/11/28/react-v16.2.0-fragment-support": "React v16.2 Fragment Support",
                "https://react.dev/blog/2017/09/26/react-v16.0": "React v16.0",
                "https://react.dev/blog/2017/09/08/dom-attributes-in-react-16": "DOM Attributes in React 16",
                "https://react.dev/blog/2017/07/26/error-handling-in-react-16": "Error Handling in React 16",
                "https://react.dev/blog/2017/04/07/react-v15.5.0": "React v15.5.0",
                "https://react.dev/blog/2016/07/22/create-apps-with-no-configuration": "Create Apps with No Configuration",

                # === Community ===
                "https://react.dev/community": "React Community",
                "https://react.dev/community/conferences": "React Conferences",
                "https://react.dev/community/meetups": "React Meetups",
                "https://react.dev/community/videos": "React Videos",
                "https://react.dev/community/team": "React Team",
                "https://react.dev/community/acknowledgements": "Acknowledgements",
                "https://react.dev/community/versioning-policy": "Versioning Policy",

                # === Warnings / Errors ===
                "https://react.dev/warnings/invalid-hook-call-warning": "Invalid Hook Call Warning",
                "https://react.dev/warnings/invalid-aria-prop": "Invalid ARIA Prop",
                "https://react.dev/errors/321": "Error 321",
                "https://react.dev/errors/418": "Error 418",
                "https://react.dev/errors/419": "Error 419",
                "https://react.dev/errors/422": "Error 422",
                "https://react.dev/errors/423": "Error 423",
                "https://react.dev/errors/425": "Error 425",
                "https://react.dev/errors/426": "Error 426",
                "https://react.dev/errors/310": "Error 310",
                "https://react.dev/errors/152": "Error 152",
                "https://react.dev/errors/185": "Error 185",
                "https://react.dev/errors/301": "Error 301",
                "https://react.dev/errors/300": "Error 300",
            },
        },
        "reference": {
            "pages": {
                # === React Core API ===
                "https://react.dev/reference/react": "React Reference Overview",
                "https://react.dev/reference/react/Component": "Component",
                "https://react.dev/reference/react/PureComponent": "PureComponent",
                "https://react.dev/reference/react/createElement": "createElement",
                "https://react.dev/reference/react/createContext": "createContext",
                "https://react.dev/reference/react/createRef": "createRef",
                "https://react.dev/reference/react/forwardRef": "forwardRef",
                "https://react.dev/reference/react/lazy": "lazy",
                "https://react.dev/reference/react/memo": "memo",
                "https://react.dev/reference/react/startTransition": "startTransition",
                "https://react.dev/reference/react/use": "use",
                "https://react.dev/reference/react/cache": "cache",
                "https://react.dev/reference/react/cloneElement": "cloneElement",
                "https://react.dev/reference/react/isValidElement": "isValidElement",
                "https://react.dev/reference/react/Children": "Children",

                # === React Built-in Components ===
                "https://react.dev/reference/react/Fragment": "Fragment",
                "https://react.dev/reference/react/Profiler": "Profiler",
                "https://react.dev/reference/react/StrictMode": "StrictMode",
                "https://react.dev/reference/react/Suspense": "Suspense",

                # === Hooks ===
                "https://react.dev/reference/react/hooks": "Hooks Overview",
                "https://react.dev/reference/react/useState": "useState",
                "https://react.dev/reference/react/useReducer": "useReducer",
                "https://react.dev/reference/react/useContext": "useContext",
                "https://react.dev/reference/react/useRef": "useRef",
                "https://react.dev/reference/react/useEffect": "useEffect",
                "https://react.dev/reference/react/useLayoutEffect": "useLayoutEffect",
                "https://react.dev/reference/react/useInsertionEffect": "useInsertionEffect",
                "https://react.dev/reference/react/useMemo": "useMemo",
                "https://react.dev/reference/react/useCallback": "useCallback",
                "https://react.dev/reference/react/useTransition": "useTransition",
                "https://react.dev/reference/react/useDeferredValue": "useDeferredValue",
                "https://react.dev/reference/react/useId": "useId",
                "https://react.dev/reference/react/useSyncExternalStore": "useSyncExternalStore",
                "https://react.dev/reference/react/useDebugValue": "useDebugValue",
                "https://react.dev/reference/react/useImperativeHandle": "useImperativeHandle",
                "https://react.dev/reference/react/useOptimistic": "useOptimistic",
                "https://react.dev/reference/react/useActionState": "useActionState",
                "https://react.dev/reference/react/useFormStatus": "useFormStatus",

                # === React DOM ===
                "https://react.dev/reference/react-dom": "React DOM Overview",
                "https://react.dev/reference/react-dom/createPortal": "createPortal",
                "https://react.dev/reference/react-dom/flushSync": "flushSync",
                "https://react.dev/reference/react-dom/findDOMNode": "findDOMNode",
                "https://react.dev/reference/react-dom/hydrate": "hydrate",
                "https://react.dev/reference/react-dom/render": "render",
                "https://react.dev/reference/react-dom/unmountComponentAtNode": "unmountComponentAtNode",
                "https://react.dev/reference/react-dom/preconnect": "preconnect",
                "https://react.dev/reference/react-dom/prefetchDNS": "prefetchDNS",
                "https://react.dev/reference/react-dom/preinit": "preinit",
                "https://react.dev/reference/react-dom/preinitModule": "preinitModule",
                "https://react.dev/reference/react-dom/preload": "preload",
                "https://react.dev/reference/react-dom/preloadModule": "preloadModule",

                # === React DOM Client ===
                "https://react.dev/reference/react-dom/client": "React DOM Client",
                "https://react.dev/reference/react-dom/client/createRoot": "createRoot",
                "https://react.dev/reference/react-dom/client/hydrateRoot": "hydrateRoot",

                # === React DOM Server ===
                "https://react.dev/reference/react-dom/server": "React DOM Server",
                "https://react.dev/reference/react-dom/server/renderToString": "renderToString",
                "https://react.dev/reference/react-dom/server/renderToStaticMarkup": "renderToStaticMarkup",
                "https://react.dev/reference/react-dom/server/renderToPipeableStream": "renderToPipeableStream",
                "https://react.dev/reference/react-dom/server/renderToReadableStream": "renderToReadableStream",
                "https://react.dev/reference/react-dom/server/renderToStaticNodeStream": "renderToStaticNodeStream",
                "https://react.dev/reference/react-dom/server/renderToNodeStream": "renderToNodeStream",

                # === React DOM Components ===
                "https://react.dev/reference/react-dom/components": "React DOM Components",
                "https://react.dev/reference/react-dom/components/common": "Common Components (DOM)",
                "https://react.dev/reference/react-dom/components/form": "form",
                "https://react.dev/reference/react-dom/components/input": "input",
                "https://react.dev/reference/react-dom/components/option": "option",
                "https://react.dev/reference/react-dom/components/progress": "progress",
                "https://react.dev/reference/react-dom/components/select": "select",
                "https://react.dev/reference/react-dom/components/textarea": "textarea",
                "https://react.dev/reference/react-dom/components/link": "link",
                "https://react.dev/reference/react-dom/components/meta": "meta",
                "https://react.dev/reference/react-dom/components/script": "script",
                "https://react.dev/reference/react-dom/components/style": "style",
                "https://react.dev/reference/react-dom/components/title": "title",

                # === React DOM Hooks ===
                "https://react.dev/reference/react-dom/hooks": "React DOM Hooks",
                "https://react.dev/reference/react-dom/hooks/useFormStatus": "useFormStatus (DOM)",

                # === React APIs ===
                "https://react.dev/reference/react/apis": "React APIs",
                "https://react.dev/reference/react/act": "act",

                # === Rules of React ===
                "https://react.dev/reference/rules": "Rules of React",
                "https://react.dev/reference/rules/react-calls-components-and-hooks": "React Calls Components and Hooks",
                "https://react.dev/reference/rules/rules-of-hooks": "Rules of Hooks",
                "https://react.dev/reference/rules/components-and-hooks-must-be-pure": "Components and Hooks Must Be Pure",

                # === RSC / Server Components ===
                "https://react.dev/reference/rsc/server-components": "Server Components",
                "https://react.dev/reference/rsc/server-actions": "Server Actions",
                "https://react.dev/reference/rsc/use-server": "'use server'",
                "https://react.dev/reference/rsc/use-client": "'use client'",
                "https://react.dev/reference/rsc/directives": "Directives",

                # === Additional Reference Pages ===
                "https://react.dev/reference/react/experimental_taintObjectReference": "taintObjectReference",
                "https://react.dev/reference/react/experimental_taintUniqueValue": "taintUniqueValue",

                # === React 19 APIs ===
                "https://react.dev/reference/react/useFormState": "useFormState",
                "https://react.dev/reference/react/experimental_useEffectEvent": "useEffectEvent (experimental)",

                # === Legacy APIs ===
                "https://react.dev/reference/react/legacy": "Legacy React APIs",

                # === Additional React DOM Components ===
                "https://react.dev/reference/react-dom/components/a": "a (anchor)",
                "https://react.dev/reference/react-dom/components/button": "button",
                "https://react.dev/reference/react-dom/components/datalist": "datalist",
                "https://react.dev/reference/react-dom/components/details": "details",
                "https://react.dev/reference/react-dom/components/dialog": "dialog",
                "https://react.dev/reference/react-dom/components/fieldset": "fieldset",
                "https://react.dev/reference/react-dom/components/img": "img",
                "https://react.dev/reference/react-dom/components/label": "label",
                "https://react.dev/reference/react-dom/components/nav": "nav (DOM)",
                "https://react.dev/reference/react-dom/components/output": "output",
                "https://react.dev/reference/react-dom/components/table": "table",
                "https://react.dev/reference/react-dom/components/video": "video",
                "https://react.dev/reference/react-dom/components/audio": "audio",
                "https://react.dev/reference/react-dom/components/canvas": "canvas",
                "https://react.dev/reference/react-dom/components/iframe": "iframe",
                "https://react.dev/reference/react-dom/components/source": "source",
                "https://react.dev/reference/react-dom/components/track": "track",
                "https://react.dev/reference/react-dom/components/picture": "picture",
                "https://react.dev/reference/react-dom/components/map": "map",
                "https://react.dev/reference/react-dom/components/area": "area",
                "https://react.dev/reference/react-dom/components/object": "object",
                "https://react.dev/reference/react-dom/components/embed": "embed",
                "https://react.dev/reference/react-dom/components/svg": "SVG elements",
                "https://react.dev/reference/react-dom/components/ol": "ol",
                "https://react.dev/reference/react-dom/components/ul": "ul",
                "https://react.dev/reference/react-dom/components/li": "li",
                "https://react.dev/reference/react-dom/components/div": "div",
                "https://react.dev/reference/react-dom/components/span": "span",
                "https://react.dev/reference/react-dom/components/section": "section",
                "https://react.dev/reference/react-dom/components/article": "article",
                "https://react.dev/reference/react-dom/components/header": "header",
                "https://react.dev/reference/react-dom/components/footer": "footer (DOM)",
                "https://react.dev/reference/react-dom/components/main": "main",
                "https://react.dev/reference/react-dom/components/aside": "aside",
                "https://react.dev/reference/react-dom/components/figure": "figure",
                "https://react.dev/reference/react-dom/components/figcaption": "figcaption",
                "https://react.dev/reference/react-dom/components/blockquote": "blockquote",
                "https://react.dev/reference/react-dom/components/pre": "pre",
                "https://react.dev/reference/react-dom/components/code": "code",
                "https://react.dev/reference/react-dom/components/h1": "h1",
                "https://react.dev/reference/react-dom/components/h2": "h2",
                "https://react.dev/reference/react-dom/components/h3": "h3",
                "https://react.dev/reference/react-dom/components/p": "p",
                "https://react.dev/reference/react-dom/components/strong": "strong",
                "https://react.dev/reference/react-dom/components/em": "em",
                "https://react.dev/reference/react-dom/components/br": "br",
                "https://react.dev/reference/react-dom/components/hr": "hr",
                "https://react.dev/reference/react-dom/components/small": "small",
                "https://react.dev/reference/react-dom/components/sub": "sub",
                "https://react.dev/reference/react-dom/components/sup": "sup",
                "https://react.dev/reference/react-dom/components/abbr": "abbr",
                "https://react.dev/reference/react-dom/components/cite": "cite",
                "https://react.dev/reference/react-dom/components/time": "time",
                "https://react.dev/reference/react-dom/components/mark": "mark",
                "https://react.dev/reference/react-dom/components/q": "q",

                # === Additional Error Boundaries ===
                "https://react.dev/reference/react/Component#catching-rendering-errors-with-an-error-boundary": "Error Boundary Pattern",
                "https://react.dev/reference/react/Component#static-getderivedstatefromprops": "getDerivedStateFromProps",
                "https://react.dev/reference/react/Component#static-getderivedstatefromerror": "getDerivedStateFromError",
                "https://react.dev/reference/react/Component#componentdidcatch": "componentDidCatch",
                "https://react.dev/reference/react/Component#componentdidmount": "componentDidMount",
                "https://react.dev/reference/react/Component#componentdidupdate": "componentDidUpdate",
                "https://react.dev/reference/react/Component#componentwillunmount": "componentWillUnmount",
                "https://react.dev/reference/react/Component#shouldcomponentupdate": "shouldComponentUpdate",
                "https://react.dev/reference/react/Component#getsnapshotbeforeupdate": "getSnapshotBeforeUpdate",
                "https://react.dev/reference/react/Component#render": "render method",
                "https://react.dev/reference/react/Component#constructor": "constructor",
                "https://react.dev/reference/react/Component#context": "context",
                "https://react.dev/reference/react/Component#props": "props",
                "https://react.dev/reference/react/Component#state": "state",
                "https://react.dev/reference/react/Component#setstate": "setState",
                "https://react.dev/reference/react/Component#forceupdate": "forceUpdate",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"react-{source_key}" if source_key else "react"
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
            for suffix in [' – React', ' - React', ' | React']:
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
                        "category": f"react-{source_key}",
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
            self.log.info(f"=== Scraping react/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    ReactScraper(base, source_key).run()
