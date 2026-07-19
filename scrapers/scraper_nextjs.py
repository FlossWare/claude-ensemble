#!/usr/bin/env python3
"""Next.js documentation scraper.

Covers:
  - nextjs.org/docs getting-started
  - nextjs.org/docs routing (defining-routes, pages, layouts, loading-ui, error-handling, etc.)
  - nextjs.org/docs data-fetching, rendering, caching, styling, optimizing, configuring, deploying
  - nextjs.org/docs api-reference
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


BASE = "https://nextjs.org/docs"


class NextJSScraper(BaseScraper):
    """Scrape Next.js documentation from nextjs.org/docs."""

    SOURCES = {
        "getting-started": {
            "pages": {
                f"{BASE}": "Next.js Documentation",
                f"{BASE}/getting-started": "Getting Started",
                f"{BASE}/getting-started/installation": "Installation",
                f"{BASE}/getting-started/project-structure": "Project Structure",

                # === Upgrading ===
                f"{BASE}/getting-started/upgrading": "Upgrading",

                # === Additional top-level pages ===
                f"{BASE}/community": "Community",
                f"{BASE}/architecture": "Architecture",
                f"{BASE}/architecture/accessibility": "Accessibility",
                f"{BASE}/architecture/fast-refresh": "Fast Refresh",
                f"{BASE}/architecture/nextjs-compiler": "Next.js Compiler",
                f"{BASE}/architecture/supported-browsers": "Supported Browsers",
                f"{BASE}/architecture/turbopack": "Turbopack",
            },
        },
        "routing": {
            "pages": {
                # === Routing ===
                f"{BASE}/app/building-your-application/routing": "Routing Fundamentals",
                f"{BASE}/app/building-your-application/routing/defining-routes": "Defining Routes",
                f"{BASE}/app/building-your-application/routing/pages": "Pages",
                f"{BASE}/app/building-your-application/routing/layouts-and-templates": "Layouts and Templates",
                f"{BASE}/app/building-your-application/routing/linking-and-navigating": "Linking and Navigating",
                f"{BASE}/app/building-your-application/routing/loading-ui-and-streaming": "Loading UI and Streaming",
                f"{BASE}/app/building-your-application/routing/error-handling": "Error Handling",
                f"{BASE}/app/building-your-application/routing/redirecting": "Redirecting",
                f"{BASE}/app/building-your-application/routing/route-groups": "Route Groups",
                f"{BASE}/app/building-your-application/routing/dynamic-routes": "Dynamic Routes",
                f"{BASE}/app/building-your-application/routing/parallel-routes": "Parallel Routes",
                f"{BASE}/app/building-your-application/routing/intercepting-routes": "Intercepting Routes",
                f"{BASE}/app/building-your-application/routing/middleware": "Middleware",
                f"{BASE}/app/building-your-application/routing/internationalization": "Internationalization",

                # === Pages Router equivalents ===
                f"{BASE}/pages/building-your-application/routing": "Pages Router: Routing",
                f"{BASE}/pages/building-your-application/routing/pages-and-layouts": "Pages Router: Pages and Layouts",
                f"{BASE}/pages/building-your-application/routing/dynamic-routes": "Pages Router: Dynamic Routes",
                f"{BASE}/pages/building-your-application/routing/linking-and-navigating": "Pages Router: Linking and Navigating",
                f"{BASE}/pages/building-your-application/routing/redirecting": "Pages Router: Redirecting",
                f"{BASE}/pages/building-your-application/routing/custom-app": "Pages Router: Custom App",
                f"{BASE}/pages/building-your-application/routing/custom-document": "Pages Router: Custom Document",
                f"{BASE}/pages/building-your-application/routing/custom-error": "Pages Router: Custom Error",
                f"{BASE}/pages/building-your-application/routing/api-routes": "Pages Router: API Routes",
                f"{BASE}/pages/building-your-application/routing/internationalization": "Pages Router: Internationalization",
                f"{BASE}/pages/building-your-application/routing/middleware": "Pages Router: Middleware",
            },
        },
        "data-fetching": {
            "pages": {
                # === App Router Data Fetching ===
                f"{BASE}/app/building-your-application/data-fetching": "Data Fetching Overview",
                f"{BASE}/app/building-your-application/data-fetching/fetching": "Data Fetching and Caching",
                f"{BASE}/app/building-your-application/data-fetching/server-actions-and-mutations": "Server Actions and Mutations",
                f"{BASE}/app/building-your-application/data-fetching/incremental-static-regeneration": "Incremental Static Regeneration",

                # === Pages Router Data Fetching ===
                f"{BASE}/pages/building-your-application/data-fetching": "Pages Router: Data Fetching",
                f"{BASE}/pages/building-your-application/data-fetching/get-static-props": "getStaticProps",
                f"{BASE}/pages/building-your-application/data-fetching/get-static-paths": "getStaticPaths",
                f"{BASE}/pages/building-your-application/data-fetching/get-server-side-props": "getServerSideProps",
                f"{BASE}/pages/building-your-application/data-fetching/client-side": "Client-side Fetching",
                f"{BASE}/pages/building-your-application/data-fetching/incremental-static-regeneration": "Pages Router: ISR",
            },
        },
        "rendering": {
            "pages": {
                # === App Router Rendering ===
                f"{BASE}/app/building-your-application/rendering": "Rendering Overview",
                f"{BASE}/app/building-your-application/rendering/server-components": "Server Components",
                f"{BASE}/app/building-your-application/rendering/client-components": "Client Components",
                f"{BASE}/app/building-your-application/rendering/composition-patterns": "Composition Patterns",
                f"{BASE}/app/building-your-application/rendering/partial-prerendering": "Partial Prerendering",
                f"{BASE}/app/building-your-application/rendering/edge-and-nodejs-runtimes": "Edge and Node.js Runtimes",

                # === Pages Router Rendering ===
                f"{BASE}/pages/building-your-application/rendering": "Pages Router: Rendering",
                f"{BASE}/pages/building-your-application/rendering/server-side-rendering": "Server-side Rendering",
                f"{BASE}/pages/building-your-application/rendering/static-site-generation": "Static Site Generation",
                f"{BASE}/pages/building-your-application/rendering/automatic-static-optimization": "Automatic Static Optimization",
                f"{BASE}/pages/building-your-application/rendering/client-side-rendering": "Client-side Rendering",
                f"{BASE}/pages/building-your-application/rendering/edge-and-nodejs-runtimes": "Pages Router: Edge and Node.js Runtimes",
            },
        },
        "caching": {
            "pages": {
                f"{BASE}/app/building-your-application/caching": "Caching in Next.js",
            },
        },
        "styling": {
            "pages": {
                f"{BASE}/app/building-your-application/styling": "Styling Overview",
                f"{BASE}/app/building-your-application/styling/css": "CSS",
                f"{BASE}/app/building-your-application/styling/css-modules": "CSS Modules",
                f"{BASE}/app/building-your-application/styling/tailwind-css": "Tailwind CSS",
                f"{BASE}/app/building-your-application/styling/sass": "Sass",
                f"{BASE}/app/building-your-application/styling/css-in-js": "CSS-in-JS",

                # === Pages Router Styling ===
                f"{BASE}/pages/building-your-application/styling": "Pages Router: Styling",
                f"{BASE}/pages/building-your-application/styling/css-modules": "Pages Router: CSS Modules",
                f"{BASE}/pages/building-your-application/styling/tailwind-css": "Pages Router: Tailwind CSS",
                f"{BASE}/pages/building-your-application/styling/css-in-js": "Pages Router: CSS-in-JS",
                f"{BASE}/pages/building-your-application/styling/sass": "Pages Router: Sass",
            },
        },
        "optimizing": {
            "pages": {
                f"{BASE}/app/building-your-application/optimizing": "Optimizations Overview",
                f"{BASE}/app/building-your-application/optimizing/images": "Image Optimization",
                f"{BASE}/app/building-your-application/optimizing/fonts": "Font Optimization",
                f"{BASE}/app/building-your-application/optimizing/scripts": "Script Optimization",
                f"{BASE}/app/building-your-application/optimizing/metadata": "Metadata",
                f"{BASE}/app/building-your-application/optimizing/static-assets": "Static Assets",
                f"{BASE}/app/building-your-application/optimizing/analytics": "Analytics",
                f"{BASE}/app/building-your-application/optimizing/lazy-loading": "Lazy Loading",
                f"{BASE}/app/building-your-application/optimizing/videos": "Video Optimization",
                f"{BASE}/app/building-your-application/optimizing/bundle-analyzer": "Bundle Analyzer",
                f"{BASE}/app/building-your-application/optimizing/package-bundling": "Package Bundling",
                f"{BASE}/app/building-your-application/optimizing/instrumentation": "Instrumentation",
                f"{BASE}/app/building-your-application/optimizing/open-telemetry": "OpenTelemetry",
                f"{BASE}/app/building-your-application/optimizing/third-party-libraries": "Third Party Libraries",
                f"{BASE}/app/building-your-application/optimizing/memory-usage": "Memory Usage",

                # === Pages Router Optimizing ===
                f"{BASE}/pages/building-your-application/optimizing": "Pages Router: Optimizing",
                f"{BASE}/pages/building-your-application/optimizing/images": "Pages Router: Images",
                f"{BASE}/pages/building-your-application/optimizing/fonts": "Pages Router: Fonts",
                f"{BASE}/pages/building-your-application/optimizing/scripts": "Pages Router: Scripts",
                f"{BASE}/pages/building-your-application/optimizing/static-assets": "Pages Router: Static Assets",
                f"{BASE}/pages/building-your-application/optimizing/analytics": "Pages Router: Analytics",
                f"{BASE}/pages/building-your-application/optimizing/lazy-loading": "Pages Router: Lazy Loading",
                f"{BASE}/pages/building-your-application/optimizing/instrumentation": "Pages Router: Instrumentation",
                f"{BASE}/pages/building-your-application/optimizing/open-telemetry": "Pages Router: OpenTelemetry",
                f"{BASE}/pages/building-your-application/optimizing/third-party-libraries": "Pages Router: Third Party Libraries",
            },
        },
        "configuring": {
            "pages": {
                f"{BASE}/app/building-your-application/configuring": "Configuring Overview",
                f"{BASE}/app/building-your-application/configuring/typescript": "TypeScript",
                f"{BASE}/app/building-your-application/configuring/eslint": "ESLint",
                f"{BASE}/app/building-your-application/configuring/environment-variables": "Environment Variables",
                f"{BASE}/app/building-your-application/configuring/absolute-imports-and-module-aliases": "Absolute Imports and Module Aliases",
                f"{BASE}/app/building-your-application/configuring/mdx": "MDX",
                f"{BASE}/app/building-your-application/configuring/src-directory": "src Directory",
                f"{BASE}/app/building-your-application/configuring/draft-mode": "Draft Mode",
                f"{BASE}/app/building-your-application/configuring/content-security-policy": "Content Security Policy",
                f"{BASE}/app/building-your-application/configuring/debugging": "Debugging",
                f"{BASE}/app/building-your-application/configuring/progressive-web-apps": "Progressive Web Apps",
                f"{BASE}/app/building-your-application/configuring/custom-server": "Custom Server",

                # === Pages Router Configuring ===
                f"{BASE}/pages/building-your-application/configuring": "Pages Router: Configuring",
                f"{BASE}/pages/building-your-application/configuring/typescript": "Pages Router: TypeScript",
                f"{BASE}/pages/building-your-application/configuring/eslint": "Pages Router: ESLint",
                f"{BASE}/pages/building-your-application/configuring/environment-variables": "Pages Router: Environment Variables",
                f"{BASE}/pages/building-your-application/configuring/absolute-imports-and-module-aliases": "Pages Router: Absolute Imports",
                f"{BASE}/pages/building-your-application/configuring/mdx": "Pages Router: MDX",
                f"{BASE}/pages/building-your-application/configuring/amp": "Pages Router: AMP",
                f"{BASE}/pages/building-your-application/configuring/babel": "Pages Router: Babel",
                f"{BASE}/pages/building-your-application/configuring/post-css": "Pages Router: PostCSS",
                f"{BASE}/pages/building-your-application/configuring/src-directory": "Pages Router: src Directory",
                f"{BASE}/pages/building-your-application/configuring/draft-mode": "Pages Router: Draft Mode",
                f"{BASE}/pages/building-your-application/configuring/custom-server": "Pages Router: Custom Server",
                f"{BASE}/pages/building-your-application/configuring/preview-mode": "Pages Router: Preview Mode",
                f"{BASE}/pages/building-your-application/configuring/content-security-policy": "Pages Router: CSP",
                f"{BASE}/pages/building-your-application/configuring/debugging": "Pages Router: Debugging",
            },
        },
        "deploying": {
            "pages": {
                f"{BASE}/app/building-your-application/deploying": "Deploying",
                f"{BASE}/app/building-your-application/deploying/production-checklist": "Production Checklist",
                f"{BASE}/app/building-your-application/deploying/static-exports": "Static Exports",
                f"{BASE}/app/building-your-application/deploying/multi-zones": "Multi-Zones",
                f"{BASE}/app/building-your-application/deploying/ci-build-caching": "CI Build Caching",

                # === Pages Router Deploying ===
                f"{BASE}/pages/building-your-application/deploying": "Pages Router: Deploying",
                f"{BASE}/pages/building-your-application/deploying/static-exports": "Pages Router: Static Exports",
                f"{BASE}/pages/building-your-application/deploying/multi-zones": "Pages Router: Multi-Zones",
                f"{BASE}/pages/building-your-application/deploying/ci-build-caching": "Pages Router: CI Build Caching",
            },
        },
        "testing": {
            "pages": {
                f"{BASE}/app/building-your-application/testing": "Testing Overview",
                f"{BASE}/app/building-your-application/testing/vitest": "Vitest",
                f"{BASE}/app/building-your-application/testing/jest": "Jest",
                f"{BASE}/app/building-your-application/testing/playwright": "Playwright",
                f"{BASE}/app/building-your-application/testing/cypress": "Cypress",

                # === Pages Router Testing ===
                f"{BASE}/pages/building-your-application/testing": "Pages Router: Testing",
                f"{BASE}/pages/building-your-application/testing/vitest": "Pages Router: Vitest",
                f"{BASE}/pages/building-your-application/testing/jest": "Pages Router: Jest",
                f"{BASE}/pages/building-your-application/testing/playwright": "Pages Router: Playwright",
                f"{BASE}/pages/building-your-application/testing/cypress": "Pages Router: Cypress",
            },
        },
        "api-reference": {
            "pages": {
                # === App Router API Reference ===
                f"{BASE}/app/api-reference": "API Reference",
                f"{BASE}/app/api-reference/directives": "Directives",
                f"{BASE}/app/api-reference/directives/use-client": "'use client'",
                f"{BASE}/app/api-reference/directives/use-server": "'use server'",
                f"{BASE}/app/api-reference/directives/use-cache": "'use cache'",

                # === Components ===
                f"{BASE}/app/api-reference/components": "Components",
                f"{BASE}/app/api-reference/components/font": "Font",
                f"{BASE}/app/api-reference/components/form": "Form",
                f"{BASE}/app/api-reference/components/image": "Image",
                f"{BASE}/app/api-reference/components/link": "Link",
                f"{BASE}/app/api-reference/components/script": "Script",

                # === File Conventions ===
                f"{BASE}/app/api-reference/file-conventions": "File Conventions",
                f"{BASE}/app/api-reference/file-conventions/default": "default.js",
                f"{BASE}/app/api-reference/file-conventions/error": "error.js",
                f"{BASE}/app/api-reference/file-conventions/instrumentation": "instrumentation.js",
                f"{BASE}/app/api-reference/file-conventions/layout": "layout.js",
                f"{BASE}/app/api-reference/file-conventions/loading": "loading.js",
                f"{BASE}/app/api-reference/file-conventions/mdx-components": "mdx-components.js",
                f"{BASE}/app/api-reference/file-conventions/middleware": "middleware.js",
                f"{BASE}/app/api-reference/file-conventions/not-found": "not-found.js",
                f"{BASE}/app/api-reference/file-conventions/page": "page.js",
                f"{BASE}/app/api-reference/file-conventions/route": "route.js",
                f"{BASE}/app/api-reference/file-conventions/route-segment-config": "Route Segment Config",
                f"{BASE}/app/api-reference/file-conventions/template": "template.js",
                f"{BASE}/app/api-reference/file-conventions/metadata": "Metadata Files",
                f"{BASE}/app/api-reference/file-conventions/metadata/app-icons": "favicon, icon, apple-icon",
                f"{BASE}/app/api-reference/file-conventions/metadata/manifest": "manifest.json",
                f"{BASE}/app/api-reference/file-conventions/metadata/opengraph-image": "opengraph-image and twitter-image",
                f"{BASE}/app/api-reference/file-conventions/metadata/robots": "robots.txt",
                f"{BASE}/app/api-reference/file-conventions/metadata/sitemap": "sitemap.xml",

                # === Functions ===
                f"{BASE}/app/api-reference/functions": "Functions",
                f"{BASE}/app/api-reference/functions/after": "after",
                f"{BASE}/app/api-reference/functions/cacheLife": "cacheLife",
                f"{BASE}/app/api-reference/functions/cacheTag": "cacheTag",
                f"{BASE}/app/api-reference/functions/connection": "connection",
                f"{BASE}/app/api-reference/functions/cookies": "cookies",
                f"{BASE}/app/api-reference/functions/draft-mode": "draftMode",
                f"{BASE}/app/api-reference/functions/fetch": "fetch",
                f"{BASE}/app/api-reference/functions/forbidden": "forbidden",
                f"{BASE}/app/api-reference/functions/generate-image-metadata": "generateImageMetadata",
                f"{BASE}/app/api-reference/functions/generate-metadata": "generateMetadata",
                f"{BASE}/app/api-reference/functions/generate-sitemaps": "generateSitemaps",
                f"{BASE}/app/api-reference/functions/generate-static-params": "generateStaticParams",
                f"{BASE}/app/api-reference/functions/generate-viewport": "generateViewport",
                f"{BASE}/app/api-reference/functions/headers": "headers",
                f"{BASE}/app/api-reference/functions/image-response": "ImageResponse",
                f"{BASE}/app/api-reference/functions/next-request": "NextRequest",
                f"{BASE}/app/api-reference/functions/next-response": "NextResponse",
                f"{BASE}/app/api-reference/functions/not-found": "notFound",
                f"{BASE}/app/api-reference/functions/permanentRedirect": "permanentRedirect",
                f"{BASE}/app/api-reference/functions/redirect": "redirect",
                f"{BASE}/app/api-reference/functions/revalidatePath": "revalidatePath",
                f"{BASE}/app/api-reference/functions/revalidateTag": "revalidateTag",
                f"{BASE}/app/api-reference/functions/unauthorized": "unauthorized",
                f"{BASE}/app/api-reference/functions/unstable_cache": "unstable_cache",
                f"{BASE}/app/api-reference/functions/use-params": "useParams",
                f"{BASE}/app/api-reference/functions/use-pathname": "usePathname",
                f"{BASE}/app/api-reference/functions/use-report-web-vitals": "useReportWebVitals",
                f"{BASE}/app/api-reference/functions/use-router": "useRouter",
                f"{BASE}/app/api-reference/functions/use-search-params": "useSearchParams",
                f"{BASE}/app/api-reference/functions/use-selected-layout-segment": "useSelectedLayoutSegment",
                f"{BASE}/app/api-reference/functions/use-selected-layout-segments": "useSelectedLayoutSegments",

                # === next.config.js ===
                f"{BASE}/app/api-reference/config/next-config-js": "next.config.js Options",
                f"{BASE}/app/api-reference/config/next-config-js/appDir": "appDir",
                f"{BASE}/app/api-reference/config/next-config-js/assetPrefix": "assetPrefix",
                f"{BASE}/app/api-reference/config/next-config-js/basePath": "basePath",
                f"{BASE}/app/api-reference/config/next-config-js/cacheLife": "cacheLife",
                f"{BASE}/app/api-reference/config/next-config-js/compress": "compress",
                f"{BASE}/app/api-reference/config/next-config-js/crossOrigin": "crossOrigin",
                f"{BASE}/app/api-reference/config/next-config-js/devIndicators": "devIndicators",
                f"{BASE}/app/api-reference/config/next-config-js/distDir": "distDir",
                f"{BASE}/app/api-reference/config/next-config-js/env": "env",
                f"{BASE}/app/api-reference/config/next-config-js/eslint": "eslint",
                f"{BASE}/app/api-reference/config/next-config-js/expireTime": "expireTime",
                f"{BASE}/app/api-reference/config/next-config-js/exportPathMap": "exportPathMap",
                f"{BASE}/app/api-reference/config/next-config-js/generateBuildId": "generateBuildId",
                f"{BASE}/app/api-reference/config/next-config-js/generateEtags": "generateEtags",
                f"{BASE}/app/api-reference/config/next-config-js/headers": "headers",
                f"{BASE}/app/api-reference/config/next-config-js/httpAgentOptions": "httpAgentOptions",
                f"{BASE}/app/api-reference/config/next-config-js/images": "images",
                f"{BASE}/app/api-reference/config/next-config-js/logging": "logging",
                f"{BASE}/app/api-reference/config/next-config-js/mdxRs": "mdxRs",
                f"{BASE}/app/api-reference/config/next-config-js/onDemandEntries": "onDemandEntries",
                f"{BASE}/app/api-reference/config/next-config-js/output": "output",
                f"{BASE}/app/api-reference/config/next-config-js/pageExtensions": "pageExtensions",
                f"{BASE}/app/api-reference/config/next-config-js/poweredByHeader": "poweredByHeader",
                f"{BASE}/app/api-reference/config/next-config-js/productionBrowserSourceMaps": "productionBrowserSourceMaps",
                f"{BASE}/app/api-reference/config/next-config-js/reactStrictMode": "reactStrictMode",
                f"{BASE}/app/api-reference/config/next-config-js/redirects": "redirects",
                f"{BASE}/app/api-reference/config/next-config-js/rewrites": "rewrites",
                f"{BASE}/app/api-reference/config/next-config-js/sassOptions": "sassOptions",
                f"{BASE}/app/api-reference/config/next-config-js/serverActions": "serverActions",
                f"{BASE}/app/api-reference/config/next-config-js/serverExternalPackages": "serverExternalPackages",
                f"{BASE}/app/api-reference/config/next-config-js/staleTimes": "staleTimes",
                f"{BASE}/app/api-reference/config/next-config-js/trailingSlash": "trailingSlash",
                f"{BASE}/app/api-reference/config/next-config-js/transpilePackages": "transpilePackages",
                f"{BASE}/app/api-reference/config/next-config-js/turbo": "turbo",
                f"{BASE}/app/api-reference/config/next-config-js/typescript": "typescript",
                f"{BASE}/app/api-reference/config/next-config-js/urlImports": "urlImports",
                f"{BASE}/app/api-reference/config/next-config-js/webpack": "webpack",

                # === CLI ===
                f"{BASE}/app/api-reference/cli/next": "Next.js CLI",
                f"{BASE}/app/api-reference/cli/create-next-app": "create-next-app",

                # === Edge Runtime ===
                f"{BASE}/app/api-reference/edge": "Edge Runtime",

                # === Pages Router API ===
                f"{BASE}/pages/api-reference": "Pages Router API Reference",
                f"{BASE}/pages/api-reference/components/head": "Head",
                f"{BASE}/pages/api-reference/components/image-legacy": "Image (Legacy)",
                f"{BASE}/pages/api-reference/components/link": "Pages Router: Link",
                f"{BASE}/pages/api-reference/components/script": "Pages Router: Script",
                f"{BASE}/pages/api-reference/functions/get-initial-props": "getInitialProps",
                f"{BASE}/pages/api-reference/functions/get-server-side-props": "getServerSideProps",
                f"{BASE}/pages/api-reference/functions/get-static-paths": "getStaticPaths",
                f"{BASE}/pages/api-reference/functions/get-static-props": "getStaticProps",
                f"{BASE}/pages/api-reference/functions/next-request": "Pages Router: NextRequest",
                f"{BASE}/pages/api-reference/functions/next-response": "Pages Router: NextResponse",
                f"{BASE}/pages/api-reference/functions/use-amp": "useAmp",
                f"{BASE}/pages/api-reference/functions/use-report-web-vitals": "Pages Router: useReportWebVitals",
                f"{BASE}/pages/api-reference/functions/use-router": "Pages Router: useRouter",
                f"{BASE}/pages/api-reference/config/next-config-js": "Pages Router: next.config.js",

                # === Additional App Router API Functions ===
                f"{BASE}/app/api-reference/functions/use-form-state": "useFormState",
                f"{BASE}/app/api-reference/functions/use-form-status": "useFormStatus",

                # === Turbopack ===
                f"{BASE}/app/api-reference/turbopack": "Turbopack API",

                # === Additional next.config.js options ===
                f"{BASE}/app/api-reference/config/next-config-js/allowedDevOrigins": "allowedDevOrigins",
                f"{BASE}/app/api-reference/config/next-config-js/bundlePagesRouterDependencies": "bundlePagesRouterDependencies",
                f"{BASE}/app/api-reference/config/next-config-js/cacheHandler": "cacheHandler",
                f"{BASE}/app/api-reference/config/next-config-js/dynamicIO": "dynamicIO",
                f"{BASE}/app/api-reference/config/next-config-js/optimizePackageImports": "optimizePackageImports",
                f"{BASE}/app/api-reference/config/next-config-js/ppr": "ppr",
                f"{BASE}/app/api-reference/config/next-config-js/serverComponentsHmrCache": "serverComponentsHmrCache",
                f"{BASE}/app/api-reference/config/next-config-js/useFileSystemPublicRoutes": "useFileSystemPublicRoutes",
                f"{BASE}/app/api-reference/config/next-config-js/webVitalsAttribution": "webVitalsAttribution",
                f"{BASE}/app/api-reference/config/next-config-js/serverSourceMap": "serverSourceMap",

                # === Pages Router additional ===
                f"{BASE}/pages/building-your-application/upgrading": "Pages Router: Upgrading",
                f"{BASE}/pages/building-your-application/upgrading/app-router-migration": "App Router Migration Guide",
                f"{BASE}/pages/building-your-application/upgrading/version-14": "Upgrading to Version 14",
                f"{BASE}/pages/building-your-application/upgrading/version-13": "Upgrading to Version 13",
                f"{BASE}/pages/building-your-application/upgrading/version-12": "Upgrading to Version 12",
                f"{BASE}/pages/building-your-application/upgrading/version-11": "Upgrading to Version 11",
                f"{BASE}/pages/building-your-application/upgrading/version-10": "Upgrading to Version 10",
                f"{BASE}/pages/building-your-application/upgrading/version-9": "Upgrading to Version 9",
                f"{BASE}/pages/building-your-application/upgrading/codemods": "Codemods",

                # === Additional Pages Router pages ===
                f"{BASE}/pages/building-your-application/authentication": "Pages Router: Authentication",
                f"{BASE}/app/building-your-application/authentication": "App Router: Authentication",
                f"{BASE}/app/building-your-application/upgrading": "App Router: Upgrading",
                f"{BASE}/app/building-your-application/upgrading/codemods": "App Router: Codemods",

                # === Error Handling Detail Pages ===
                f"{BASE}/messages/app-dir-dynamic-href": "Error: App Dir Dynamic Href",
                f"{BASE}/messages/css-global": "Error: CSS Global",
                f"{BASE}/messages/install-sass": "Error: Install Sass",
                f"{BASE}/messages/install-sharp": "Error: Install Sharp",
                f"{BASE}/messages/invalid-images-config": "Error: Invalid Images Config",
                f"{BASE}/messages/large-page-data": "Error: Large Page Data",
                f"{BASE}/messages/link-no-children": "Error: Link No Children",
                f"{BASE}/messages/max-custom-routes-reached": "Error: Max Custom Routes",
                f"{BASE}/messages/missing-document-component": "Error: Missing Document Component",
                f"{BASE}/messages/next-image-unconfigured-host": "Error: Next Image Unconfigured Host",
                f"{BASE}/messages/no-cache": "Error: No Cache",
                f"{BASE}/messages/no-css-tags": "Error: No CSS Tags",
                f"{BASE}/messages/no-document-import-in-page": "Error: No Document Import in Page",
                f"{BASE}/messages/no-head-import-in-document": "Error: No Head Import in Document",
                f"{BASE}/messages/no-html-link-for-pages": "Error: No HTML Link for Pages",
                f"{BASE}/messages/no-page-custom-font": "Error: No Page Custom Font",
                f"{BASE}/messages/no-stylesheets-in-head-component": "Error: No Stylesheets in Head",
                f"{BASE}/messages/react-hydration-error": "Error: React Hydration Error",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"nextjs-{source_key}" if source_key else "nextjs"
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
            for suffix in [' | Next.js', ' - Next.js', ' – Next.js',
                           ' | Next.js by Vercel']:
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
                        "category": f"nextjs-{source_key}",
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
            self.log.info(f"=== Scraping nextjs/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    NextJSScraper(base, source_key).run()
