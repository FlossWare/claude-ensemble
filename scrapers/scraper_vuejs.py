#!/usr/bin/env python3
"""Vue.js documentation scraper.

Covers:
  - vuejs.org/guide essentials (creating-application, template-syntax, reactivity, etc.)
  - vuejs.org/guide components-in-depth (registration, props, events, slots, etc.)
  - vuejs.org/guide reusability (composables, custom-directives, plugins)
  - vuejs.org/guide scaling-up (single-file-components, tooling, routing, state-management, testing, ssr)
  - vuejs.org/api api-reference (global, composition, options, built-in)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class VueJSScraper(BaseScraper):
    """Scrape Vue.js documentation from vuejs.org."""

    SOURCES = {
        "essentials": {
            "pages": {
                # === Guide Landing ===
                "https://vuejs.org/guide/introduction.html": "Introduction",

                # === Essentials ===
                "https://vuejs.org/guide/essentials/application.html": "Creating a Vue Application",
                "https://vuejs.org/guide/essentials/template-syntax.html": "Template Syntax",
                "https://vuejs.org/guide/essentials/reactivity-fundamentals.html": "Reactivity Fundamentals",
                "https://vuejs.org/guide/essentials/computed.html": "Computed Properties",
                "https://vuejs.org/guide/essentials/class-and-style.html": "Class and Style Bindings",
                "https://vuejs.org/guide/essentials/conditional.html": "Conditional Rendering",
                "https://vuejs.org/guide/essentials/list.html": "List Rendering",
                "https://vuejs.org/guide/essentials/event-handling.html": "Event Handling",
                "https://vuejs.org/guide/essentials/forms.html": "Form Input Bindings",
                "https://vuejs.org/guide/essentials/lifecycle.html": "Lifecycle Hooks",
                "https://vuejs.org/guide/essentials/watchers.html": "Watchers",
                "https://vuejs.org/guide/essentials/template-refs.html": "Template Refs",
                "https://vuejs.org/guide/essentials/component-basics.html": "Components Basics",

                # === Quick Start ===
                "https://vuejs.org/guide/quick-start.html": "Quick Start",

                # === Best Practices ===
                "https://vuejs.org/guide/best-practices/production-deployment.html": "Production Deployment",
                "https://vuejs.org/guide/best-practices/performance.html": "Performance",
                "https://vuejs.org/guide/best-practices/accessibility.html": "Accessibility",
                "https://vuejs.org/guide/best-practices/security.html": "Security",

                # === TypeScript ===
                "https://vuejs.org/guide/typescript/overview.html": "Using Vue with TypeScript",
                "https://vuejs.org/guide/typescript/composition-api.html": "TypeScript with Composition API",
                "https://vuejs.org/guide/typescript/options-api.html": "TypeScript with Options API",

                # === Extra Topics ===
                "https://vuejs.org/guide/extras/ways-of-using-vue.html": "Ways of Using Vue",
                "https://vuejs.org/guide/extras/composition-api-faq.html": "Composition API FAQ",
                "https://vuejs.org/guide/extras/reactivity-in-depth.html": "Reactivity in Depth",
                "https://vuejs.org/guide/extras/rendering-mechanism.html": "Rendering Mechanism",
                "https://vuejs.org/guide/extras/render-function.html": "Render Functions & JSX",
                "https://vuejs.org/guide/extras/animation.html": "Animation Techniques",
                "https://vuejs.org/guide/extras/reactivity-transform.html": "Reactivity Transform",
                "https://vuejs.org/guide/extras/web-components.html": "Vue and Web Components",
            },
        },
        "components-in-depth": {
            "pages": {
                # === Component Registration ===
                "https://vuejs.org/guide/components/registration.html": "Component Registration",

                # === Props ===
                "https://vuejs.org/guide/components/props.html": "Props",

                # === Events ===
                "https://vuejs.org/guide/components/events.html": "Component Events",

                # === Component v-model ===
                "https://vuejs.org/guide/components/v-model.html": "Component v-model",

                # === Fallthrough Attributes ===
                "https://vuejs.org/guide/components/attrs.html": "Fallthrough Attributes",

                # === Slots ===
                "https://vuejs.org/guide/components/slots.html": "Slots",

                # === Provide / Inject ===
                "https://vuejs.org/guide/components/provide-inject.html": "Provide / Inject",

                # === Async Components ===
                "https://vuejs.org/guide/components/async.html": "Async Components",
            },
        },
        "reusability": {
            "pages": {
                # === Composables ===
                "https://vuejs.org/guide/reusability/composables.html": "Composables",

                # === Custom Directives ===
                "https://vuejs.org/guide/reusability/custom-directives.html": "Custom Directives",

                # === Plugins ===
                "https://vuejs.org/guide/reusability/plugins.html": "Plugins",
            },
        },
        "scaling-up": {
            "pages": {
                # === Single-File Components ===
                "https://vuejs.org/guide/scaling-up/sfc.html": "Single-File Components",

                # === Tooling ===
                "https://vuejs.org/guide/scaling-up/tooling.html": "Tooling",

                # === Routing ===
                "https://vuejs.org/guide/scaling-up/routing.html": "Routing",

                # === State Management ===
                "https://vuejs.org/guide/scaling-up/state-management.html": "State Management",

                # === Testing ===
                "https://vuejs.org/guide/scaling-up/testing.html": "Testing",

                # === Server-Side Rendering ===
                "https://vuejs.org/guide/scaling-up/ssr.html": "Server-Side Rendering (SSR)",

                # === Built-in Components ===
                "https://vuejs.org/guide/built-ins/transition.html": "Transition",
                "https://vuejs.org/guide/built-ins/transition-group.html": "TransitionGroup",
                "https://vuejs.org/guide/built-ins/keep-alive.html": "KeepAlive",
                "https://vuejs.org/guide/built-ins/teleport.html": "Teleport",
                "https://vuejs.org/guide/built-ins/suspense.html": "Suspense",
            },
        },
        "api-reference": {
            "pages": {
                # === API Index ===
                "https://vuejs.org/api/": "API Reference Index",

                # === Global API ===
                "https://vuejs.org/api/general.html": "General",
                "https://vuejs.org/api/application.html": "Application",

                # === Composition API ===
                "https://vuejs.org/api/composition-api-setup.html": "setup()",
                "https://vuejs.org/api/reactivity-core.html": "Reactivity: Core",
                "https://vuejs.org/api/reactivity-utilities.html": "Reactivity: Utilities",
                "https://vuejs.org/api/reactivity-advanced.html": "Reactivity: Advanced",
                "https://vuejs.org/api/composition-api-lifecycle.html": "Lifecycle Hooks",
                "https://vuejs.org/api/composition-api-dependency-injection.html": "Dependency Injection",
                "https://vuejs.org/api/composition-api-helpers.html": "Helpers",

                # === Options API ===
                "https://vuejs.org/api/options-state.html": "Options: State",
                "https://vuejs.org/api/options-rendering.html": "Options: Rendering",
                "https://vuejs.org/api/options-lifecycle.html": "Options: Lifecycle",
                "https://vuejs.org/api/options-composition.html": "Options: Composition",
                "https://vuejs.org/api/options-misc.html": "Options: Misc",
                "https://vuejs.org/api/component-instance.html": "Component Instance",

                # === Built-in ===
                "https://vuejs.org/api/built-in-directives.html": "Built-in Directives",
                "https://vuejs.org/api/built-in-components.html": "Built-in Components",
                "https://vuejs.org/api/built-in-special-elements.html": "Built-in Special Elements",
                "https://vuejs.org/api/built-in-special-attributes.html": "Built-in Special Attributes",

                # === SFC ===
                "https://vuejs.org/api/sfc-spec.html": "SFC Syntax Specification",
                "https://vuejs.org/api/sfc-script-setup.html": "<script setup>",
                "https://vuejs.org/api/sfc-css-features.html": "SFC CSS Features",

                # === Advanced APIs ===
                "https://vuejs.org/api/render-function.html": "Render Function",
                "https://vuejs.org/api/ssr.html": "Server-Side Rendering",
                "https://vuejs.org/api/custom-renderer.html": "Custom Renderer",
                "https://vuejs.org/api/compile-time-flags.html": "Compile-Time Flags",
                "https://vuejs.org/api/utility-types.html": "TypeScript Utility Types",

                # === Ecosystem / Style Guide ===
                "https://vuejs.org/style-guide/": "Style Guide",
                "https://vuejs.org/style-guide/rules-essential.html": "Priority A Rules: Essential",
                "https://vuejs.org/style-guide/rules-strongly-recommended.html": "Priority B Rules: Strongly Recommended",
                "https://vuejs.org/style-guide/rules-recommended.html": "Priority C Rules: Recommended",
                "https://vuejs.org/style-guide/rules-use-with-caution.html": "Priority D Rules: Use with Caution",

                # === Ecosystem ===
                "https://vuejs.org/ecosystem/partners.html": "Partners",
                "https://vuejs.org/ecosystem/themes.html": "Themes",

                # === Examples ===
                "https://vuejs.org/examples/": "Examples",

                # === Glossary ===
                "https://vuejs.org/glossary/": "Glossary",

                # === Error Reference ===
                "https://vuejs.org/error-reference/": "Error Reference",

                # === About ===
                "https://vuejs.org/about/faq.html": "FAQ",
                "https://vuejs.org/about/team.html": "Meet the Team",
                "https://vuejs.org/about/releases.html": "Releases",
                "https://vuejs.org/about/community-guide.html": "Community Guide",
                "https://vuejs.org/about/coc.html": "Code of Conduct",
                "https://vuejs.org/about/privacy.html": "Privacy Policy",

                # === Sponsor ===
                "https://vuejs.org/sponsor/": "Sponsor Vue.js",

                # === Vue Router docs (key pages) ===
                "https://router.vuejs.org/introduction.html": "Vue Router Introduction",
                "https://router.vuejs.org/guide/": "Vue Router Guide",
                "https://router.vuejs.org/guide/essentials/dynamic-matching.html": "Dynamic Route Matching",
                "https://router.vuejs.org/guide/essentials/route-matching-syntax.html": "Routes Matching Syntax",
                "https://router.vuejs.org/guide/essentials/nested-routes.html": "Nested Routes",
                "https://router.vuejs.org/guide/essentials/named-routes.html": "Named Routes",
                "https://router.vuejs.org/guide/essentials/named-views.html": "Named Views",
                "https://router.vuejs.org/guide/essentials/redirect-and-alias.html": "Redirect and Alias",
                "https://router.vuejs.org/guide/essentials/passing-props.html": "Passing Props to Route Components",
                "https://router.vuejs.org/guide/essentials/active-links.html": "Active Links",
                "https://router.vuejs.org/guide/essentials/history-mode.html": "Different History Modes",
                "https://router.vuejs.org/guide/advanced/navigation-guards.html": "Navigation Guards",
                "https://router.vuejs.org/guide/advanced/route-meta.html": "Route Meta Fields",
                "https://router.vuejs.org/guide/advanced/data-fetching.html": "Data Fetching",
                "https://router.vuejs.org/guide/advanced/composition-api.html": "Vue Router and Composition API",
                "https://router.vuejs.org/guide/advanced/transitions.html": "Transitions",
                "https://router.vuejs.org/guide/advanced/scroll-behavior.html": "Scroll Behavior",
                "https://router.vuejs.org/guide/advanced/lazy-loading.html": "Lazy Loading Routes",
                "https://router.vuejs.org/guide/advanced/typed-routes.html": "Typed Routes",
                "https://router.vuejs.org/guide/advanced/extending-router-link.html": "Extending RouterLink",
                "https://router.vuejs.org/guide/advanced/navigation-failures.html": "Waiting for Navigation Result",
                "https://router.vuejs.org/guide/advanced/dynamic-routing.html": "Dynamic Routing",
                "https://router.vuejs.org/guide/migration/": "Migrating from Vue 2",
                "https://router.vuejs.org/api/": "Vue Router API Reference",
                "https://router.vuejs.org/api/interfaces/RouteLocationNormalized.html": "RouteLocationNormalized",
                "https://router.vuejs.org/api/interfaces/Router.html": "Router Interface",
                "https://router.vuejs.org/api/interfaces/RouteRecordNormalized.html": "RouteRecordNormalized",

                # === Pinia docs (key pages) ===
                "https://pinia.vuejs.org/introduction.html": "Pinia Introduction",
                "https://pinia.vuejs.org/getting-started.html": "Pinia Getting Started",
                "https://pinia.vuejs.org/core-concepts/": "Pinia Core Concepts",
                "https://pinia.vuejs.org/core-concepts/state.html": "Pinia State",
                "https://pinia.vuejs.org/core-concepts/getters.html": "Pinia Getters",
                "https://pinia.vuejs.org/core-concepts/actions.html": "Pinia Actions",
                "https://pinia.vuejs.org/core-concepts/plugins.html": "Pinia Plugins",
                "https://pinia.vuejs.org/core-concepts/outside-component-usage.html": "Pinia Outside Components",
                "https://pinia.vuejs.org/cookbook/composing-stores.html": "Composing Stores",
                "https://pinia.vuejs.org/cookbook/migration-vuex.html": "Migrating from Vuex",
                "https://pinia.vuejs.org/cookbook/hot-module-replacement.html": "HMR (Hot Module Replacement)",
                "https://pinia.vuejs.org/cookbook/testing.html": "Testing Stores",
                "https://pinia.vuejs.org/ssr/": "Server-Side Rendering (SSR)",
                "https://pinia.vuejs.org/api/": "Pinia API Reference",

                # === Vite docs (key pages for Vue tooling) ===
                "https://vite.dev/guide/": "Vite Guide",
                "https://vite.dev/guide/features.html": "Vite Features",
                "https://vite.dev/guide/cli.html": "Vite CLI",
                "https://vite.dev/guide/using-plugins.html": "Using Plugins",
                "https://vite.dev/guide/dep-pre-bundling.html": "Dependency Pre-Bundling",
                "https://vite.dev/guide/static-deploy.html": "Deploying a Static Site",
                "https://vite.dev/guide/env-and-mode.html": "Env Variables and Modes",
                "https://vite.dev/guide/ssr.html": "Server-Side Rendering",
                "https://vite.dev/guide/build.html": "Building for Production",
                "https://vite.dev/config/": "Vite Config Reference",
                "https://vite.dev/config/shared-options.html": "Shared Options",
                "https://vite.dev/config/server-options.html": "Server Options",
                "https://vite.dev/config/build-options.html": "Build Options",
                "https://vite.dev/config/preview-options.html": "Preview Options",
                "https://vite.dev/config/dep-optimization-options.html": "Dep Optimization Options",
                "https://vite.dev/config/ssr-options.html": "SSR Options",
                "https://vite.dev/config/worker-options.html": "Worker Options",

                # === VueUse (popular composable library) ===
                "https://vueuse.org/guide/": "VueUse Guide",
                "https://vueuse.org/guide/config.html": "VueUse Configuration",
                "https://vueuse.org/guide/best-practice.html": "VueUse Best Practices",
                "https://vueuse.org/guide/components.html": "VueUse Components",

                # === Nuxt (Vue meta-framework, key pages) ===
                "https://nuxt.com/docs/getting-started/introduction": "Nuxt Introduction",
                "https://nuxt.com/docs/getting-started/installation": "Nuxt Installation",
                "https://nuxt.com/docs/getting-started/configuration": "Nuxt Configuration",
                "https://nuxt.com/docs/getting-started/views": "Nuxt Views",
                "https://nuxt.com/docs/getting-started/routing": "Nuxt Routing",
                "https://nuxt.com/docs/getting-started/data-fetching": "Nuxt Data Fetching",
                "https://nuxt.com/docs/getting-started/state-management": "Nuxt State Management",
                "https://nuxt.com/docs/getting-started/error-handling": "Nuxt Error Handling",
                "https://nuxt.com/docs/getting-started/server": "Nuxt Server",
                "https://nuxt.com/docs/getting-started/testing": "Nuxt Testing",
                "https://nuxt.com/docs/getting-started/deployment": "Nuxt Deployment",
                "https://nuxt.com/docs/guide/concepts/auto-imports": "Nuxt Auto-imports",
                "https://nuxt.com/docs/guide/concepts/rendering": "Nuxt Rendering Modes",
                "https://nuxt.com/docs/guide/directory-structure/app": "Nuxt app.vue",
                "https://nuxt.com/docs/guide/directory-structure/components": "Nuxt components/",
                "https://nuxt.com/docs/guide/directory-structure/composables": "Nuxt composables/",
                "https://nuxt.com/docs/guide/directory-structure/layouts": "Nuxt layouts/",
                "https://nuxt.com/docs/guide/directory-structure/middleware": "Nuxt middleware/",
                "https://nuxt.com/docs/guide/directory-structure/pages": "Nuxt pages/",
                "https://nuxt.com/docs/guide/directory-structure/plugins": "Nuxt plugins/",
                "https://nuxt.com/docs/guide/directory-structure/server": "Nuxt server/",
                "https://nuxt.com/docs/guide/directory-structure/utils": "Nuxt utils/",
                "https://nuxt.com/docs/api/configuration/nuxt-config": "Nuxt Config Reference",

                # === Additional Nuxt Pages ===
                "https://nuxt.com/docs/guide/concepts/esm": "Nuxt ES Modules",
                "https://nuxt.com/docs/guide/concepts/typescript": "Nuxt TypeScript",
                "https://nuxt.com/docs/guide/concepts/server-engine": "Nuxt Server Engine",
                "https://nuxt.com/docs/guide/concepts/modules": "Nuxt Modules",
                "https://nuxt.com/docs/guide/directory-structure/modules": "Nuxt modules/",
                "https://nuxt.com/docs/guide/directory-structure/public": "Nuxt public/",
                "https://nuxt.com/docs/guide/directory-structure/content": "Nuxt content/",
                "https://nuxt.com/docs/guide/going-further/experimental-features": "Nuxt Experimental Features",
                "https://nuxt.com/docs/guide/going-further/hooks": "Nuxt Hooks",
                "https://nuxt.com/docs/guide/going-further/internals": "Nuxt Internals",
                "https://nuxt.com/docs/guide/going-further/layers": "Nuxt Layers",
                "https://nuxt.com/docs/guide/going-further/modules": "Nuxt Module Author Guide",
                "https://nuxt.com/docs/guide/going-further/nightly-release-channel": "Nuxt Nightly Releases",
                "https://nuxt.com/docs/guide/going-further/runtime-config": "Nuxt Runtime Config",
                "https://nuxt.com/docs/api/composables/use-app-config": "useAppConfig",
                "https://nuxt.com/docs/api/composables/use-async-data": "useAsyncData",
                "https://nuxt.com/docs/api/composables/use-cookie": "useCookie",
                "https://nuxt.com/docs/api/composables/use-error": "useError",
                "https://nuxt.com/docs/api/composables/use-fetch": "useFetch",
                "https://nuxt.com/docs/api/composables/use-head": "useHead",
                "https://nuxt.com/docs/api/composables/use-lazy-async-data": "useLazyAsyncData",
                "https://nuxt.com/docs/api/composables/use-lazy-fetch": "useLazyFetch",
                "https://nuxt.com/docs/api/composables/use-nuxt-app": "useNuxtApp",
                "https://nuxt.com/docs/api/composables/use-request-event": "useRequestEvent",
                "https://nuxt.com/docs/api/composables/use-request-headers": "useRequestHeaders",
                "https://nuxt.com/docs/api/composables/use-route": "useRoute",
                "https://nuxt.com/docs/api/composables/use-router": "useRouter (Nuxt)",
                "https://nuxt.com/docs/api/composables/use-runtime-config": "useRuntimeConfig",
                "https://nuxt.com/docs/api/composables/use-seo-meta": "useSeoMeta",
                "https://nuxt.com/docs/api/composables/use-state": "useState (Nuxt)",
                "https://nuxt.com/docs/api/utils/define-nuxt-component": "defineNuxtComponent",
                "https://nuxt.com/docs/api/utils/define-page-meta": "definePageMeta",
                "https://nuxt.com/docs/api/utils/navigate-to": "navigateTo",
                "https://nuxt.com/docs/api/utils/abort-navigation": "abortNavigation",
                "https://nuxt.com/docs/api/utils/add-route-middleware": "addRouteMiddleware",
                "https://nuxt.com/docs/api/utils/clear-error": "clearError",
                "https://nuxt.com/docs/api/utils/clear-nuxt-data": "clearNuxtData",
                "https://nuxt.com/docs/api/utils/create-error": "createError",
                "https://nuxt.com/docs/api/utils/preload-components": "preloadComponents",
                "https://nuxt.com/docs/api/utils/prerender-routes": "prerenderRoutes",
                "https://nuxt.com/docs/api/utils/refresh-nuxt-data": "refreshNuxtData",
                "https://nuxt.com/docs/api/utils/reload-nuxt-app": "reloadNuxtApp",
                "https://nuxt.com/docs/api/utils/set-response-status": "setResponseStatus",
                "https://nuxt.com/docs/api/utils/show-error": "showError",
                "https://nuxt.com/docs/api/utils/update-app-config": "updateAppConfig",

                # === Additional Vue Router Pages ===
                "https://router.vuejs.org/guide/essentials/navigation.html": "Programmatic Navigation",
                "https://router.vuejs.org/guide/advanced/wait-for-result.html": "Wait for Result",

                # === Additional Pinia Pages ===
                "https://pinia.vuejs.org/core-concepts/state.html#accessing-the-state": "Accessing Pinia State",
                "https://pinia.vuejs.org/core-concepts/state.html#resetting-the-state": "Resetting Pinia State",
                "https://pinia.vuejs.org/core-concepts/getters.html#passing-arguments-to-getters": "Passing Arguments to Getters",
                "https://pinia.vuejs.org/core-concepts/actions.html#subscribing-to-actions": "Subscribing to Actions",

                # === Vue Test Utils ===
                "https://test-utils.vuejs.org/guide/": "Vue Test Utils Guide",
                "https://test-utils.vuejs.org/guide/essentials/a-crash-course.html": "Vue Test Utils: Crash Course",
                "https://test-utils.vuejs.org/guide/essentials/conditional-rendering.html": "Vue Test Utils: Conditional Rendering",
                "https://test-utils.vuejs.org/guide/essentials/event-handling.html": "Vue Test Utils: Event Handling",
                "https://test-utils.vuejs.org/guide/essentials/forms.html": "Vue Test Utils: Forms",
                "https://test-utils.vuejs.org/guide/essentials/passing-data.html": "Vue Test Utils: Passing Data",
                "https://test-utils.vuejs.org/guide/essentials/easy-testing-with-setup.html": "Vue Test Utils: Easy Testing with Setup",
                "https://test-utils.vuejs.org/guide/advanced/slots.html": "Vue Test Utils: Slots",
                "https://test-utils.vuejs.org/guide/advanced/async-suspense.html": "Vue Test Utils: Async Suspense",
                "https://test-utils.vuejs.org/guide/advanced/http-requests.html": "Vue Test Utils: HTTP Requests",
                "https://test-utils.vuejs.org/guide/advanced/transitions.html": "Vue Test Utils: Transitions",
                "https://test-utils.vuejs.org/guide/advanced/component-instance.html": "Vue Test Utils: Component Instance",
                "https://test-utils.vuejs.org/guide/advanced/reusability-composition.html": "Vue Test Utils: Reusability",
                "https://test-utils.vuejs.org/guide/advanced/stubs-shallow-mount.html": "Vue Test Utils: Stubs and Shallow Mount",
                "https://test-utils.vuejs.org/guide/advanced/teleport.html": "Vue Test Utils: Teleport",
                "https://test-utils.vuejs.org/guide/advanced/v-model.html": "Vue Test Utils: v-model",
                "https://test-utils.vuejs.org/guide/advanced/vue-router.html": "Vue Test Utils: Vue Router",
                "https://test-utils.vuejs.org/guide/advanced/vuex.html": "Vue Test Utils: Vuex",
                "https://test-utils.vuejs.org/api/": "Vue Test Utils API",

                # === Additional Vite Pages ===
                "https://vite.dev/guide/api-plugin.html": "Vite Plugin API",
                "https://vite.dev/guide/api-hmr.html": "Vite HMR API",
                "https://vite.dev/guide/api-javascript.html": "Vite JavaScript API",
                "https://vite.dev/guide/backend-integration.html": "Vite Backend Integration",
                "https://vite.dev/guide/comparisons.html": "Vite Comparisons",
                "https://vite.dev/guide/migration.html": "Vite Migration Guide",
                "https://vite.dev/guide/troubleshooting.html": "Vite Troubleshooting",
                "https://vite.dev/guide/performance.html": "Vite Performance",
                "https://vite.dev/guide/philosophy.html": "Vite Philosophy",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"vuejs-{source_key}" if source_key else "vuejs"
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
            for suffix in [' | Vue.js', ' - Vue.js', ' | Vue Router',
                           ' | Pinia', ' | Vite', ' | VueUse',
                           ' - Nuxt', ' | Nuxt']:
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
                        "category": f"vuejs-{source_key}",
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
            self.log.info(f"=== Scraping vuejs/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    VueJSScraper(base, source_key).run()
