#!/usr/bin/env python3
"""FastAPI documentation scraper.

Covers:
  - fastapi.tiangolo.com tutorial (first-steps through deployment)
  - fastapi.tiangolo.com advanced (additional-status-codes through generate-clients)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class FastAPIScraper(BaseScraper):
    """Scrape FastAPI documentation from fastapi.tiangolo.com."""

    SOURCES = {
        "tutorial": {
            "pages": {
                # === Tutorial Landing ===
                "https://fastapi.tiangolo.com/tutorial/": "FastAPI Tutorial",

                # === First Steps ===
                "https://fastapi.tiangolo.com/tutorial/first-steps/": "First Steps",

                # === Path Parameters ===
                "https://fastapi.tiangolo.com/tutorial/path-params/": "Path Parameters",

                # === Query Parameters ===
                "https://fastapi.tiangolo.com/tutorial/query-params/": "Query Parameters",
                "https://fastapi.tiangolo.com/tutorial/query-params-str-validations/": "Query Parameters and String Validations",

                # === Request Body ===
                "https://fastapi.tiangolo.com/tutorial/body/": "Request Body",
                "https://fastapi.tiangolo.com/tutorial/body-multiple-params/": "Body - Multiple Parameters",
                "https://fastapi.tiangolo.com/tutorial/body-fields/": "Body - Fields",
                "https://fastapi.tiangolo.com/tutorial/body-nested-models/": "Body - Nested Models",

                # === Header Parameters ===
                "https://fastapi.tiangolo.com/tutorial/header-params/": "Header Parameters",

                # === Cookie Parameters ===
                "https://fastapi.tiangolo.com/tutorial/cookie-params/": "Cookie Parameters",
                "https://fastapi.tiangolo.com/tutorial/cookie-param-models/": "Cookie Parameter Models",

                # === Response Model ===
                "https://fastapi.tiangolo.com/tutorial/response-model/": "Response Model",
                "https://fastapi.tiangolo.com/tutorial/response-status-code/": "Response Status Code",

                # === Form Data ===
                "https://fastapi.tiangolo.com/tutorial/request-forms/": "Form Data",
                "https://fastapi.tiangolo.com/tutorial/request-form-models/": "Form Models",
                "https://fastapi.tiangolo.com/tutorial/request-forms-and-files/": "Forms and Files",

                # === Request Files ===
                "https://fastapi.tiangolo.com/tutorial/request-files/": "Request Files",

                # === Handling Errors ===
                "https://fastapi.tiangolo.com/tutorial/handling-errors/": "Handling Errors",

                # === Path Operation Configuration ===
                "https://fastapi.tiangolo.com/tutorial/path-operation-configuration/": "Path Operation Configuration",

                # === JSON Compatible Encoder ===
                "https://fastapi.tiangolo.com/tutorial/encoder/": "JSON Compatible Encoder",

                # === Body Updates ===
                "https://fastapi.tiangolo.com/tutorial/body-updates/": "Body - Updates",

                # === Dependencies ===
                "https://fastapi.tiangolo.com/tutorial/dependencies/": "Dependencies",
                "https://fastapi.tiangolo.com/tutorial/dependencies/classes-as-dependencies/": "Classes as Dependencies",
                "https://fastapi.tiangolo.com/tutorial/dependencies/sub-dependencies/": "Sub-dependencies",
                "https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/": "Dependencies in Path Operation Decorators",
                "https://fastapi.tiangolo.com/tutorial/dependencies/global-dependencies/": "Global Dependencies",
                "https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/": "Dependencies with yield",

                # === Security ===
                "https://fastapi.tiangolo.com/tutorial/security/": "Security Intro",
                "https://fastapi.tiangolo.com/tutorial/security/first-steps/": "Security First Steps",
                "https://fastapi.tiangolo.com/tutorial/security/get-current-user/": "Get Current User",
                "https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/": "Simple OAuth2 with Password",
                "https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/": "OAuth2 with JWT Tokens",

                # === Middleware ===
                "https://fastapi.tiangolo.com/tutorial/middleware/": "Middleware",

                # === CORS ===
                "https://fastapi.tiangolo.com/tutorial/cors/": "CORS",

                # === SQL Databases ===
                "https://fastapi.tiangolo.com/tutorial/sql-databases/": "SQL (Relational) Databases",

                # === Bigger Applications ===
                "https://fastapi.tiangolo.com/tutorial/bigger-applications/": "Bigger Applications - Multiple Files",

                # === Background Tasks ===
                "https://fastapi.tiangolo.com/tutorial/background-tasks/": "Background Tasks",

                # === Metadata and Docs URLs ===
                "https://fastapi.tiangolo.com/tutorial/metadata/": "Metadata and Docs URLs",

                # === Static Files ===
                "https://fastapi.tiangolo.com/tutorial/static-files/": "Static Files",

                # === Testing ===
                "https://fastapi.tiangolo.com/tutorial/testing/": "Testing",

                # === Debugging ===
                "https://fastapi.tiangolo.com/tutorial/debugging/": "Debugging",

                # === Extra Data Types ===
                "https://fastapi.tiangolo.com/tutorial/extra-data-types/": "Extra Data Types",

                # === Extra Models ===
                "https://fastapi.tiangolo.com/tutorial/extra-models/": "Extra Models",

                # === Schema Extra Example ===
                "https://fastapi.tiangolo.com/tutorial/schema-extra-example/": "Declare Request Example Data",

                # === Path Params Numeric Validations ===
                "https://fastapi.tiangolo.com/tutorial/path-params-numeric-validations/": "Path Parameters and Numeric Validations",

                # === Header Param Models ===
                "https://fastapi.tiangolo.com/tutorial/header-param-models/": "Header Parameter Models",

                # === Deployment ===
                "https://fastapi.tiangolo.com/deployment/": "Deployment Overview",
                "https://fastapi.tiangolo.com/deployment/versions/": "About FastAPI Versions",
                "https://fastapi.tiangolo.com/deployment/https/": "About HTTPS",
                "https://fastapi.tiangolo.com/deployment/manually/": "Run a Server Manually - Uvicorn",
                "https://fastapi.tiangolo.com/deployment/concepts/": "Deployment Concepts",
                "https://fastapi.tiangolo.com/deployment/server-workers/": "Server Workers - Gunicorn with Uvicorn",
                "https://fastapi.tiangolo.com/deployment/docker/": "FastAPI in Containers - Docker",
            },
        },
        "advanced": {
            "pages": {
                # === Advanced Landing ===
                "https://fastapi.tiangolo.com/advanced/": "Advanced User Guide",

                # === Additional Status Codes ===
                "https://fastapi.tiangolo.com/advanced/additional-status-codes/": "Additional Status Codes",

                # === Return a Response Directly ===
                "https://fastapi.tiangolo.com/advanced/response-directly/": "Return a Response Directly",

                # === Custom Response ===
                "https://fastapi.tiangolo.com/advanced/custom-response/": "Custom Response - HTML, Stream, File, others",

                # === Additional Responses ===
                "https://fastapi.tiangolo.com/advanced/additional-responses/": "Additional Responses in OpenAPI",

                # === Response Cookies ===
                "https://fastapi.tiangolo.com/advanced/response-cookies/": "Response Cookies",

                # === Response Headers ===
                "https://fastapi.tiangolo.com/advanced/response-headers/": "Response Headers",

                # === Response - Change Status Code ===
                "https://fastapi.tiangolo.com/advanced/response-change-status-code/": "Response - Change Status Code",

                # === Advanced Dependencies ===
                "https://fastapi.tiangolo.com/advanced/advanced-dependencies/": "Advanced Dependencies",

                # === Advanced Security ===
                "https://fastapi.tiangolo.com/advanced/security/": "Advanced Security",
                "https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/": "OAuth2 Scopes",
                "https://fastapi.tiangolo.com/advanced/security/http-basic-auth/": "HTTP Basic Auth",

                # === Using the Request Directly ===
                "https://fastapi.tiangolo.com/advanced/using-request-directly/": "Using the Request Directly",

                # === Using Dataclasses ===
                "https://fastapi.tiangolo.com/advanced/dataclasses/": "Using Dataclasses",

                # === Advanced Middleware ===
                "https://fastapi.tiangolo.com/advanced/middleware/": "Advanced Middleware",

                # === SQL Databases with Peewee ===
                "https://fastapi.tiangolo.com/advanced/nosql-databases/": "NoSQL (Distributed / Big Data) Databases",

                # === Sub Applications ===
                "https://fastapi.tiangolo.com/advanced/sub-applications/": "Sub Applications - Mounts",

                # === Behind a Proxy ===
                "https://fastapi.tiangolo.com/advanced/behind-a-proxy/": "Behind a Proxy",

                # === Templates ===
                "https://fastapi.tiangolo.com/advanced/templates/": "Templates",

                # === WebSockets ===
                "https://fastapi.tiangolo.com/advanced/websockets/": "WebSockets",

                # === Lifespan Events ===
                "https://fastapi.tiangolo.com/advanced/events/": "Lifespan Events",

                # === Testing WebSockets ===
                "https://fastapi.tiangolo.com/advanced/testing-websockets/": "Testing WebSockets",

                # === Testing Events ===
                "https://fastapi.tiangolo.com/advanced/testing-events/": "Testing Events: startup - shutdown",

                # === Testing Dependencies ===
                "https://fastapi.tiangolo.com/advanced/testing-dependencies/": "Testing Dependencies with Overrides",

                # === Testing a Database ===
                "https://fastapi.tiangolo.com/advanced/testing-database/": "Testing a Database",

                # === Async Tests ===
                "https://fastapi.tiangolo.com/advanced/async-tests/": "Async Tests",

                # === Settings and Environment Variables ===
                "https://fastapi.tiangolo.com/advanced/settings/": "Settings and Environment Variables",

                # === OpenAPI Callbacks ===
                "https://fastapi.tiangolo.com/advanced/openapi-callbacks/": "OpenAPI Callbacks",

                # === OpenAPI Webhooks ===
                "https://fastapi.tiangolo.com/advanced/openapi-webhooks/": "OpenAPI Webhooks",

                # === Including WSGI ===
                "https://fastapi.tiangolo.com/advanced/wsgi/": "Including WSGI - Flask, Django, others",

                # === Generate Clients ===
                "https://fastapi.tiangolo.com/advanced/generate-clients/": "Generate Clients",

                # === Extending OpenAPI ===
                "https://fastapi.tiangolo.com/advanced/extending-openapi/": "Extending OpenAPI",

                # === OpenAPI-specific ===
                "https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/": "Path Operation Advanced Configuration",

                # === GraphQL ===
                "https://fastapi.tiangolo.com/advanced/graphql/": "GraphQL",

                # === Custom Request and APIRoute ===
                "https://fastapi.tiangolo.com/advanced/custom-request-and-route/": "Custom Request and APIRoute Class",

                # === Conditional OpenAPI ===
                "https://fastapi.tiangolo.com/advanced/conditional-openapi/": "Conditional OpenAPI",

                # === General / Index pages ===
                "https://fastapi.tiangolo.com/": "FastAPI Home",
                "https://fastapi.tiangolo.com/features/": "Features",
                "https://fastapi.tiangolo.com/python-types/": "Python Types Intro",
                "https://fastapi.tiangolo.com/async/": "Concurrency and async / await",
                "https://fastapi.tiangolo.com/benchmarks/": "Benchmarks",
                "https://fastapi.tiangolo.com/help-fastapi/": "Help FastAPI",
                "https://fastapi.tiangolo.com/contributing/": "Development - Contributing",
                "https://fastapi.tiangolo.com/history-design-future/": "History, Design and Future",
                "https://fastapi.tiangolo.com/alternatives/": "Alternatives, Inspiration and Comparisons",
                "https://fastapi.tiangolo.com/fastapi-cli/": "FastAPI CLI",
                "https://fastapi.tiangolo.com/external-links/": "External Links and Articles",
                "https://fastapi.tiangolo.com/newsletter/": "FastAPI Newsletter",
                "https://fastapi.tiangolo.com/release-notes/": "Release Notes",

                # === Reference ===
                "https://fastapi.tiangolo.com/reference/": "Reference Overview",
                "https://fastapi.tiangolo.com/reference/fastapi/": "FastAPI class",
                "https://fastapi.tiangolo.com/reference/apirouter/": "APIRouter class",
                "https://fastapi.tiangolo.com/reference/request/": "Request class",
                "https://fastapi.tiangolo.com/reference/response/": "Response class",
                "https://fastapi.tiangolo.com/reference/responses/": "Custom Response Classes",
                "https://fastapi.tiangolo.com/reference/parameters/": "Request Parameters",
                "https://fastapi.tiangolo.com/reference/status/": "Status Codes",
                "https://fastapi.tiangolo.com/reference/uploadfile/": "UploadFile class",
                "https://fastapi.tiangolo.com/reference/exceptions/": "Exceptions",
                "https://fastapi.tiangolo.com/reference/dependencies/": "Dependencies - Depends and Security",
                "https://fastapi.tiangolo.com/reference/security/": "Security utilities",
                "https://fastapi.tiangolo.com/reference/websockets/": "WebSockets",
                "https://fastapi.tiangolo.com/reference/httpconnection/": "HTTPConnection class",
                "https://fastapi.tiangolo.com/reference/middleware/": "Middleware",
                "https://fastapi.tiangolo.com/reference/openapi/": "OpenAPI",
                "https://fastapi.tiangolo.com/reference/encoders/": "Encoders - jsonable_encoder",
                "https://fastapi.tiangolo.com/reference/staticfiles/": "Static Files - StaticFiles",
                "https://fastapi.tiangolo.com/reference/templating/": "Templating - Jinja2Templates",
                "https://fastapi.tiangolo.com/reference/testclient/": "Test Client - TestClient",
                "https://fastapi.tiangolo.com/reference/background/": "Background Tasks - BackgroundTasks",

                # === How-To / Recipes ===
                "https://fastapi.tiangolo.com/how-to/": "How-To - Recipes",
                "https://fastapi.tiangolo.com/how-to/general/": "General - How To - Recipes",
                "https://fastapi.tiangolo.com/how-to/graphql/": "GraphQL How-To",
                "https://fastapi.tiangolo.com/how-to/custom-docs-ui-assets/": "Custom Docs UI Static Assets",
                "https://fastapi.tiangolo.com/how-to/configure-swagger-ui/": "Configure Swagger UI",
                "https://fastapi.tiangolo.com/how-to/separate-openapi-schemas/": "Separate OpenAPI Schemas for Input and Output or Not",
                "https://fastapi.tiangolo.com/how-to/custom-request-and-route/": "Custom Request and APIRoute class",
                "https://fastapi.tiangolo.com/how-to/conditional-openapi/": "Conditional OpenAPI",
                "https://fastapi.tiangolo.com/how-to/extending-openapi/": "Extending OpenAPI",

                # === Additional Tutorial and Advanced URLs ===
                "https://fastapi.tiangolo.com/tutorial/query-param-models/": "Query Parameter Models",
                "https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#dependencies-with-yield-and-httpexception": "Dependencies with yield and HTTPException",
                "https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/#about-jwt": "About JWT",
                "https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/#handle-jwt-tokens": "Handle JWT Tokens",
                "https://fastapi.tiangolo.com/tutorial/sql-databases/#create-the-database-models": "SQL: Create Database Models",
                "https://fastapi.tiangolo.com/tutorial/sql-databases/#create-the-pydantic-models": "SQL: Create Pydantic Models",
                "https://fastapi.tiangolo.com/tutorial/sql-databases/#crud-utils": "SQL: CRUD Utils",
                "https://fastapi.tiangolo.com/tutorial/sql-databases/#main-fastapi-app": "SQL: Main FastAPI App",
                "https://fastapi.tiangolo.com/tutorial/bigger-applications/#an-example-file-structure": "Bigger Apps: File Structure",
                "https://fastapi.tiangolo.com/tutorial/bigger-applications/#path-operations-with-apirouter": "Bigger Apps: APIRouter",
                "https://fastapi.tiangolo.com/advanced/settings/#environment-variables": "Settings: Environment Variables",
                "https://fastapi.tiangolo.com/advanced/settings/#reading-a-env-file": "Settings: Reading .env File",
                "https://fastapi.tiangolo.com/deployment/docker/#build-a-docker-image-for-fastapi": "Docker: Build Image",
                "https://fastapi.tiangolo.com/deployment/docker/#docker-image-with-poetry": "Docker: Image with Poetry",
                "https://fastapi.tiangolo.com/deployment/docker/#deployment-concepts": "Docker: Deployment Concepts",
                "https://fastapi.tiangolo.com/advanced/websockets/#handling-disconnections": "WebSockets: Handling Disconnections",
                "https://fastapi.tiangolo.com/advanced/websockets/#using-depends-and-others": "WebSockets: Using Depends",
                "https://fastapi.tiangolo.com/advanced/security/http-basic-auth/#simple-http-basic-auth": "HTTP Basic Auth: Simple",
                "https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/#about-oauth2-scopes": "OAuth2 Scopes: About",
                "https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/#global-view": "OAuth2 Scopes: Global View",
                "https://fastapi.tiangolo.com/advanced/custom-response/#html-response": "Custom Response: HTML",
                "https://fastapi.tiangolo.com/advanced/custom-response/#streaming-response": "Custom Response: Streaming",
                "https://fastapi.tiangolo.com/advanced/custom-response/#file-response": "Custom Response: File",
                "https://fastapi.tiangolo.com/advanced/custom-response/#redirectresponse": "Custom Response: Redirect",
                "https://fastapi.tiangolo.com/advanced/custom-response/#orjsonresponse": "Custom Response: ORJSONResponse",
                "https://fastapi.tiangolo.com/advanced/custom-response/#ujsonresponse": "Custom Response: UJSONResponse",
                "https://fastapi.tiangolo.com/advanced/middleware/#cors-middleware": "Advanced Middleware: CORS",
                "https://fastapi.tiangolo.com/advanced/middleware/#httpsredirectmiddleware": "Advanced Middleware: HTTPS Redirect",
                "https://fastapi.tiangolo.com/advanced/middleware/#trustedhostmiddleware": "Advanced Middleware: Trusted Host",
                "https://fastapi.tiangolo.com/advanced/middleware/#gzipmiddleware": "Advanced Middleware: GZip",
                "https://fastapi.tiangolo.com/tutorial/handling-errors/#use-httpexception": "Handling Errors: HTTPException",
                "https://fastapi.tiangolo.com/tutorial/handling-errors/#add-custom-headers": "Handling Errors: Custom Headers",
                "https://fastapi.tiangolo.com/tutorial/handling-errors/#install-custom-exception-handlers": "Handling Errors: Custom Exception Handlers",
                "https://fastapi.tiangolo.com/tutorial/handling-errors/#override-request-validation-exceptions": "Handling Errors: Override Validation",
                "https://fastapi.tiangolo.com/tutorial/cors/#cors-cross-origin-resource-sharing": "CORS: Cross-Origin Resource Sharing",
                "https://fastapi.tiangolo.com/tutorial/cors/#use-corsmiddleware": "CORS: Use CORSMiddleware",
                "https://fastapi.tiangolo.com/tutorial/cors/#allowed-origins": "CORS: Allowed Origins",
                "https://fastapi.tiangolo.com/tutorial/middleware/#create-a-middleware": "Middleware: Create a Middleware",
                "https://fastapi.tiangolo.com/tutorial/middleware/#before-and-after-the-response": "Middleware: Before and After Response",
                "https://fastapi.tiangolo.com/advanced/events/#startup-event": "Events: Startup",
                "https://fastapi.tiangolo.com/advanced/events/#shutdown-event": "Events: Shutdown",
                "https://fastapi.tiangolo.com/advanced/events/#lifespan": "Events: Lifespan",
                "https://fastapi.tiangolo.com/tutorial/body-nested-models/#list-fields": "Body: List Fields",
                "https://fastapi.tiangolo.com/tutorial/body-nested-models/#deeply-nested-models": "Body: Deeply Nested Models",
                "https://fastapi.tiangolo.com/tutorial/body/#use-the-model": "Body: Use the Model",
                "https://fastapi.tiangolo.com/tutorial/body/#request-body-path-parameters": "Body: Path Parameters",
                "https://fastapi.tiangolo.com/tutorial/body/#request-body-path-query-parameters": "Body: Path + Query Parameters",
                "https://fastapi.tiangolo.com/tutorial/path-params/#path-parameters-with-types": "Path Params: With Types",
                "https://fastapi.tiangolo.com/tutorial/path-params/#predefined-values": "Path Params: Predefined Values",
                "https://fastapi.tiangolo.com/tutorial/path-params/#path-parameters-containing-paths": "Path Params: Containing Paths",
                "https://fastapi.tiangolo.com/tutorial/query-params/#defaults": "Query Params: Defaults",
                "https://fastapi.tiangolo.com/tutorial/query-params/#optional-parameters": "Query Params: Optional Parameters",
                "https://fastapi.tiangolo.com/tutorial/query-params/#required-query-parameters": "Query Params: Required",
                "https://fastapi.tiangolo.com/tutorial/response-model/#response-model-return-type": "Response Model: Return Type",
                "https://fastapi.tiangolo.com/tutorial/response-model/#response-model-parameter": "Response Model: Parameter",
                "https://fastapi.tiangolo.com/tutorial/extra-models/#about-union-or-anyof": "Extra Models: Union or anyOf",
                "https://fastapi.tiangolo.com/tutorial/extra-models/#list-of-models": "Extra Models: List of Models",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"fastapi-{source_key}" if source_key else "fastapi"
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
            for suffix in [' - FastAPI', ' | FastAPI']:
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
                        "category": f"fastapi-{source_key}",
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
            self.log.info(f"=== Scraping fastapi/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    FastAPIScraper(base, source_key).run()
