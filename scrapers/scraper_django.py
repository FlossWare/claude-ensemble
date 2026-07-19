#!/usr/bin/env python3
"""Django documentation scraper.

Covers:
  - docs.djangoproject.com/en/5.0 intro (tutorial, overview, install)
  - docs.djangoproject.com/en/5.0 topics (models, views, templates, forms, admin, security, testing, cache, logging, signals, serialization, i18n, performance)
  - docs.djangoproject.com/en/5.0 howto (deployment, custom-management, static-files, writing-views, outputting-csv-pdf)
  - docs.djangoproject.com/en/5.0 ref (models, views, forms, templates, settings, urls, middleware, validators, exceptions)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


BASE = "https://docs.djangoproject.com/en/5.0"


class DjangoScraper(BaseScraper):
    """Scrape Django documentation from docs.djangoproject.com."""

    SOURCES = {
        "intro": {
            "pages": {
                # === Tutorial ===
                f"{BASE}/intro/": "Django Intro",
                f"{BASE}/intro/tutorial01/": "Tutorial Part 1: Requests and Responses",
                f"{BASE}/intro/tutorial02/": "Tutorial Part 2: Models and Admin",
                f"{BASE}/intro/tutorial03/": "Tutorial Part 3: Views and Templates",
                f"{BASE}/intro/tutorial04/": "Tutorial Part 4: Forms and Generic Views",
                f"{BASE}/intro/tutorial05/": "Tutorial Part 5: Testing",
                f"{BASE}/intro/tutorial06/": "Tutorial Part 6: Static Files",
                f"{BASE}/intro/tutorial07/": "Tutorial Part 7: Customizing Admin",
                f"{BASE}/intro/tutorial08/": "Tutorial Part 8: Third-Party Packages",
                f"{BASE}/intro/reusable-apps/": "Advanced Tutorial: Reusable Apps",
                f"{BASE}/intro/contributing/": "Writing Your First Patch for Django",

                # === Overview ===
                f"{BASE}/intro/overview/": "Django at a Glance",

                # === Install ===
                f"{BASE}/intro/install/": "Quick Install Guide",

                # === General ===
                f"{BASE}/": "Django Documentation Index",
                f"{BASE}/faq/": "Django FAQ",
                f"{BASE}/faq/general/": "FAQ: General",
                f"{BASE}/faq/install/": "FAQ: Installation",
                f"{BASE}/faq/usage/": "FAQ: Using Django",
                f"{BASE}/faq/help/": "FAQ: Getting Help",
                f"{BASE}/faq/models/": "FAQ: Databases and Models",
                f"{BASE}/faq/admin/": "FAQ: The Admin",
                f"{BASE}/faq/contributing/": "FAQ: Contributing",
                f"{BASE}/faq/troubleshooting/": "FAQ: Troubleshooting",
                f"{BASE}/glossary/": "Glossary",
                f"{BASE}/releases/": "Release Notes Index",
                f"{BASE}/releases/5.0/": "Django 5.0 Release Notes",
                f"{BASE}/releases/5.0.1/": "Django 5.0.1 Release Notes",
                f"{BASE}/releases/5.0.2/": "Django 5.0.2 Release Notes",
                f"{BASE}/releases/5.0.3/": "Django 5.0.3 Release Notes",
                f"{BASE}/releases/5.0.4/": "Django 5.0.4 Release Notes",
                f"{BASE}/releases/5.0.5/": "Django 5.0.5 Release Notes",
                f"{BASE}/releases/5.0.6/": "Django 5.0.6 Release Notes",
                f"{BASE}/releases/5.0.7/": "Django 5.0.7 Release Notes",
                f"{BASE}/releases/5.0.8/": "Django 5.0.8 Release Notes",
                f"{BASE}/releases/5.0.9/": "Django 5.0.9 Release Notes",
                f"{BASE}/releases/4.2/": "Django 4.2 Release Notes",
                f"{BASE}/releases/4.1/": "Django 4.1 Release Notes",
                f"{BASE}/releases/4.0/": "Django 4.0 Release Notes",
                f"{BASE}/releases/3.2/": "Django 3.2 Release Notes",
                f"{BASE}/misc/api-stability/": "API Stability",
                f"{BASE}/misc/design-philosophies/": "Design Philosophies",
                f"{BASE}/misc/distributions/": "Third-party Distributions of Django",
                f"{BASE}/internals/": "Django Internals",
                f"{BASE}/internals/contributing/": "Contributing to Django",
                f"{BASE}/internals/contributing/writing-code/": "Writing Code",
                f"{BASE}/internals/contributing/writing-code/coding-style/": "Coding Style",
                f"{BASE}/internals/contributing/writing-code/unit-tests/": "Unit Tests",
                f"{BASE}/internals/contributing/writing-documentation/": "Writing Documentation",
                f"{BASE}/internals/contributing/triaging-tickets/": "Triaging Tickets",
                f"{BASE}/internals/deprecation/": "Django Deprecation Timeline",
                f"{BASE}/internals/git/": "The Django Source Code Repository",
                f"{BASE}/internals/organization/": "Organization of the Django Project",
                f"{BASE}/internals/security/": "Django's Security Policies",
            },
        },
        "topics": {
            "pages": {
                # === Models ===
                f"{BASE}/topics/db/": "Models and Databases",
                f"{BASE}/topics/db/models/": "Models",
                f"{BASE}/topics/db/queries/": "Making Queries",
                f"{BASE}/topics/db/aggregation/": "Aggregation",
                f"{BASE}/topics/db/search/": "Search",
                f"{BASE}/topics/db/managers/": "Managers",
                f"{BASE}/topics/db/sql/": "Performing Raw SQL Queries",
                f"{BASE}/topics/db/transactions/": "Database Transactions",
                f"{BASE}/topics/db/multi-db/": "Multiple Databases",
                f"{BASE}/topics/db/tablespaces/": "Tablespaces",
                f"{BASE}/topics/db/optimization/": "Database Access Optimization",
                f"{BASE}/topics/db/instrumentation/": "Database Instrumentation",
                f"{BASE}/topics/db/fixtures/": "Fixtures",
                f"{BASE}/topics/db/examples/": "Examples of Model Relationship API Usage",
                f"{BASE}/topics/db/examples/many_to_many/": "Many-to-Many Relationships",
                f"{BASE}/topics/db/examples/many_to_one/": "Many-to-One Relationships",
                f"{BASE}/topics/db/examples/one_to_one/": "One-to-One Relationships",

                # === Views ===
                f"{BASE}/topics/http/": "Handling HTTP Requests",
                f"{BASE}/topics/http/urls/": "URL Dispatcher",
                f"{BASE}/topics/http/views/": "Writing Views",
                f"{BASE}/topics/http/decorators/": "View Decorators",
                f"{BASE}/topics/http/file-uploads/": "File Uploads",
                f"{BASE}/topics/http/shortcuts/": "Django Shortcut Functions",
                f"{BASE}/topics/http/middleware/": "Middleware",
                f"{BASE}/topics/http/sessions/": "How to Use Sessions",
                f"{BASE}/topics/class-based-views/": "Class-based Views",
                f"{BASE}/topics/class-based-views/intro/": "Introduction to Class-based Views",
                f"{BASE}/topics/class-based-views/generic-display/": "Built-in Class-based Generic Views",
                f"{BASE}/topics/class-based-views/generic-editing/": "Form Handling with Class-based Views",
                f"{BASE}/topics/class-based-views/mixins/": "Using Mixins with Class-based Views",

                # === Templates ===
                f"{BASE}/topics/templates/": "Templates",

                # === Forms ===
                f"{BASE}/topics/forms/": "Working with Forms",
                f"{BASE}/topics/forms/formsets/": "Formsets",
                f"{BASE}/topics/forms/modelforms/": "Creating Forms from Models",
                f"{BASE}/topics/forms/media/": "Form Assets (Media class)",

                # === Admin ===
                f"{BASE}/topics/auth/": "User Authentication",
                f"{BASE}/topics/auth/default/": "Using the Authentication System",
                f"{BASE}/topics/auth/passwords/": "Password Management",
                f"{BASE}/topics/auth/customizing/": "Customizing Authentication",

                # === Security ===
                f"{BASE}/topics/security/": "Security in Django",

                # === Testing ===
                f"{BASE}/topics/testing/": "Testing in Django",
                f"{BASE}/topics/testing/overview/": "Writing and Running Tests",
                f"{BASE}/topics/testing/tools/": "Testing Tools",
                f"{BASE}/topics/testing/advanced/": "Advanced Testing Topics",

                # === Cache ===
                f"{BASE}/topics/cache/": "Django's Cache Framework",

                # === Logging ===
                f"{BASE}/topics/logging/": "Logging",

                # === Signals ===
                f"{BASE}/topics/signals/": "Signals",

                # === Serialization ===
                f"{BASE}/topics/serialization/": "Serializing Django Objects",

                # === Internationalization ===
                f"{BASE}/topics/i18n/": "Internationalization and Localization",
                f"{BASE}/topics/i18n/translation/": "Translation",
                f"{BASE}/topics/i18n/formatting/": "Format Localization",
                f"{BASE}/topics/i18n/timezones/": "Time Zones",

                # === Performance ===
                f"{BASE}/topics/performance/": "Performance and Optimization",

                # === Additional Topics ===
                f"{BASE}/topics/settings/": "Django Settings",
                f"{BASE}/topics/email/": "Sending Email",
                f"{BASE}/topics/files/": "Managing Files",
                f"{BASE}/topics/migrations/": "Migrations",
                f"{BASE}/topics/pagination/": "Pagination",
                f"{BASE}/topics/conditional-view-processing/": "Conditional View Processing",
                f"{BASE}/topics/signing/": "Cryptographic Signing",
                f"{BASE}/topics/async/": "Asynchronous Support",
                f"{BASE}/topics/checks/": "System Check Framework",
                f"{BASE}/topics/external-packages/": "External Packages",
                f"{BASE}/topics/install/": "How to Install Django",
                f"{BASE}/topics/composite-primary-key/": "Composite Primary Key",

                # === Additional Topics ===
                f"{BASE}/topics/http/generic-views/": "Generic Views (old)",
                f"{BASE}/topics/class-based-views/flattened-index/": "Flattened Index of CBVs",
                f"{BASE}/topics/i18n/translation/#how-to-create-language-files": "Creating Language Files",
                f"{BASE}/topics/i18n/translation/#implementation-notes": "Translation Implementation Notes",
                f"{BASE}/topics/auth/default/#authentication-views": "Authentication Views",
                f"{BASE}/topics/auth/default/#all-authentication-views": "All Authentication Views",
                f"{BASE}/topics/auth/default/#built-in-forms": "Built-in Auth Forms",
                f"{BASE}/topics/auth/default/#authentication-data-in-templates": "Auth Data in Templates",
                f"{BASE}/topics/testing/overview/#the-test-client": "The Test Client",
                f"{BASE}/topics/testing/overview/#provided-test-case-classes": "Provided Test Case Classes",
                f"{BASE}/topics/testing/tools/#the-test-client": "Test Client (Tools)",
                f"{BASE}/topics/testing/tools/#email-services": "Testing Email Services",
                f"{BASE}/topics/testing/advanced/#request-factory": "RequestFactory",
                f"{BASE}/topics/testing/advanced/#django-testcase-subclasses": "TestCase Subclasses",
                f"{BASE}/topics/cache/#the-per-site-cache": "The Per-Site Cache",
                f"{BASE}/topics/cache/#template-fragment-caching": "Template Fragment Caching",
                f"{BASE}/topics/cache/#the-low-level-cache-api": "Low-Level Cache API",
                f"{BASE}/topics/db/models/#field-types": "Field Types",
                f"{BASE}/topics/db/models/#relationships": "Relationships",
                f"{BASE}/topics/db/models/#meta-options": "Meta Options",
                f"{BASE}/topics/db/models/#model-methods": "Model Methods",
                f"{BASE}/topics/db/models/#model-inheritance": "Model Inheritance",
                f"{BASE}/topics/db/queries/#creating-objects": "Creating Objects",
                f"{BASE}/topics/db/queries/#retrieving-objects": "Retrieving Objects",
                f"{BASE}/topics/db/queries/#field-lookups": "Field Lookups",
                f"{BASE}/topics/db/queries/#complex-lookups-with-q-objects": "Complex Lookups with Q Objects",
                f"{BASE}/topics/db/queries/#deleting-objects": "Deleting Objects",
                f"{BASE}/topics/db/queries/#updating-multiple-objects-at-once": "Updating Multiple Objects",
                f"{BASE}/topics/forms/#the-form-class": "The Form Class",
                f"{BASE}/topics/forms/#building-a-form": "Building a Form",
                f"{BASE}/topics/forms/#more-on-fields": "More on Fields",
                f"{BASE}/topics/forms/#working-with-form-templates": "Working with Form Templates",
                f"{BASE}/topics/templates/#the-django-template-language": "The Django Template Language",
                f"{BASE}/topics/templates/#support-for-template-engines": "Support for Template Engines",
            },
        },
        "howto": {
            "pages": {
                # === How-to Guides Landing ===
                f"{BASE}/howto/": "How-to Guides",

                # === Deployment ===
                f"{BASE}/howto/deployment/": "Deployment Overview",
                f"{BASE}/howto/deployment/wsgi/": "How to Deploy with WSGI",
                f"{BASE}/howto/deployment/wsgi/gunicorn/": "How to Use Django with Gunicorn",
                f"{BASE}/howto/deployment/wsgi/uwsgi/": "How to Use Django with uWSGI",
                f"{BASE}/howto/deployment/wsgi/modwsgi/": "How to Use Django with Apache and mod_wsgi",
                f"{BASE}/howto/deployment/asgi/": "How to Deploy with ASGI",
                f"{BASE}/howto/deployment/asgi/daphne/": "How to Use Django with Daphne",
                f"{BASE}/howto/deployment/asgi/hypercorn/": "How to Use Django with Hypercorn",
                f"{BASE}/howto/deployment/asgi/uvicorn/": "How to Use Django with Uvicorn",
                f"{BASE}/howto/deployment/checklist/": "Deployment Checklist",

                # === Custom Management Commands ===
                f"{BASE}/howto/custom-management-commands/": "Writing Custom django-admin Commands",

                # === Static Files ===
                f"{BASE}/howto/static-files/": "How to Manage Static Files",
                f"{BASE}/howto/static-files/deployment/": "Deploying Static Files",

                # === Writing Views ===
                f"{BASE}/howto/outputting-csv/": "How to Create CSV Output",
                f"{BASE}/howto/outputting-pdf/": "How to Create PDF Files",

                # === Additional How-tos ===
                f"{BASE}/howto/auth-remote-user/": "Authentication Using REMOTE_USER",
                f"{BASE}/howto/csrf/": "How to Use Django's CSRF Protection",
                f"{BASE}/howto/custom-model-fields/": "How to Create Custom Model Fields",
                f"{BASE}/howto/custom-lookups/": "Custom Lookups",
                f"{BASE}/howto/custom-template-backend/": "Custom Template Backend",
                f"{BASE}/howto/custom-template-tags/": "Custom Template Tags and Filters",
                f"{BASE}/howto/custom-file-storage/": "How to Write a Custom Storage Backend",
                f"{BASE}/howto/error-reporting/": "Error Reporting",
                f"{BASE}/howto/initial-data/": "How to Provide Initial Data for Models",
                f"{BASE}/howto/legacy-databases/": "Integrating Django with Legacy Databases",
                f"{BASE}/howto/logging/": "How to Configure and Use Logging",
                f"{BASE}/howto/overriding-templates/": "How to Override Templates",
                f"{BASE}/howto/upgrade-version/": "How to Upgrade Django to a Newer Version",
                f"{BASE}/howto/windows/": "How to Install Django on Windows",
                f"{BASE}/howto/writing-migrations/": "How to Write Database Migrations",
                f"{BASE}/howto/delete-app/": "How to Delete a Django Application",

                # === Additional How-tos ===
                f"{BASE}/howto/custom-management-commands/#accepting-optional-arguments": "Custom Commands: Optional Arguments",
                f"{BASE}/howto/deployment/checklist/#critical-settings": "Deployment Checklist: Critical Settings",
                f"{BASE}/howto/deployment/checklist/#environment-specific-settings": "Deployment Checklist: Environment Settings",
                f"{BASE}/howto/deployment/wsgi/modwsgi/#basic-configuration": "mod_wsgi Basic Configuration",
                f"{BASE}/howto/deployment/wsgi/modwsgi/#using-a-virtualenv": "mod_wsgi Using a virtualenv",
                f"{BASE}/howto/static-files/#configuring-static-files": "Configuring Static Files",
                f"{BASE}/howto/static-files/#serving-static-files-during-development": "Serving Static Files in Development",
                f"{BASE}/howto/static-files/deployment/#serving-static-files-in-production": "Serving Static Files in Production",
                f"{BASE}/howto/csrf/#using-csrf": "Using CSRF Protection",
                f"{BASE}/howto/csrf/#ajax": "CSRF with AJAX",
                f"{BASE}/howto/custom-template-tags/#writing-custom-template-tags": "Writing Custom Template Tags",
                f"{BASE}/howto/custom-template-tags/#writing-custom-template-filters": "Writing Custom Template Filters",
                f"{BASE}/howto/custom-model-fields/#writing-a-field-subclass": "Writing a Field Subclass",
                f"{BASE}/howto/writing-migrations/#data-migrations": "Data Migrations",
                f"{BASE}/howto/writing-migrations/#squashing-migrations": "Squashing Migrations",
            },
        },
        "ref": {
            "pages": {
                # === Reference Landing ===
                f"{BASE}/ref/": "API Reference",

                # === Models ===
                f"{BASE}/ref/models/": "Model Reference",
                f"{BASE}/ref/models/fields/": "Model Field Reference",
                f"{BASE}/ref/models/relations/": "Related Objects Reference",
                f"{BASE}/ref/models/class/": "Model Class Reference",
                f"{BASE}/ref/models/instances/": "Model Instance Reference",
                f"{BASE}/ref/models/querysets/": "QuerySet API Reference",
                f"{BASE}/ref/models/lookups/": "Lookup API Reference",
                f"{BASE}/ref/models/expressions/": "Query Expressions",
                f"{BASE}/ref/models/conditional-expressions/": "Conditional Expressions",
                f"{BASE}/ref/models/database-functions/": "Database Functions",
                f"{BASE}/ref/models/constraints/": "Constraints Reference",
                f"{BASE}/ref/models/indexes/": "Model Index Reference",
                f"{BASE}/ref/models/meta/": "Model _meta API",
                f"{BASE}/ref/models/options/": "Model Meta Options",

                # === Views ===
                f"{BASE}/ref/views/": "Built-in Views",
                f"{BASE}/ref/class-based-views/": "Class-based Views Reference",
                f"{BASE}/ref/class-based-views/base/": "Base Views",
                f"{BASE}/ref/class-based-views/generic-display/": "Generic Display Views",
                f"{BASE}/ref/class-based-views/generic-editing/": "Generic Editing Views",
                f"{BASE}/ref/class-based-views/generic-date-based/": "Generic Date Views",
                f"{BASE}/ref/class-based-views/mixins/": "Class-based Views Mixins",
                f"{BASE}/ref/class-based-views/mixins-simple/": "Simple Mixins",
                f"{BASE}/ref/class-based-views/mixins-single-object/": "Single Object Mixins",
                f"{BASE}/ref/class-based-views/mixins-multiple-object/": "Multiple Object Mixins",
                f"{BASE}/ref/class-based-views/mixins-editing/": "Editing Mixins",
                f"{BASE}/ref/class-based-views/mixins-date-based/": "Date-based Mixins",
                f"{BASE}/ref/class-based-views/flattened-index/": "Flattened Index",

                # === Forms ===
                f"{BASE}/ref/forms/": "Forms Reference",
                f"{BASE}/ref/forms/api/": "The Forms API",
                f"{BASE}/ref/forms/fields/": "Form Fields",
                f"{BASE}/ref/forms/models/": "Model Form Functions",
                f"{BASE}/ref/forms/formsets/": "Formset Functions",
                f"{BASE}/ref/forms/widgets/": "Widgets",
                f"{BASE}/ref/forms/validation/": "Form and Field Validation",
                f"{BASE}/ref/forms/renderers/": "Form Rendering API",

                # === Templates ===
                f"{BASE}/ref/templates/": "Templates Reference",
                f"{BASE}/ref/templates/api/": "The Django Template Language: API",
                f"{BASE}/ref/templates/language/": "The Django Template Language",
                f"{BASE}/ref/templates/builtins/": "Built-in Template Tags and Filters",

                # === Settings ===
                f"{BASE}/ref/settings/": "Settings Reference",

                # === URLs ===
                f"{BASE}/ref/urls/": "django.urls Functions",
                f"{BASE}/ref/urlresolvers/": "django.urls Utility Functions",

                # === Middleware ===
                f"{BASE}/ref/middleware/": "Middleware Reference",

                # === Validators ===
                f"{BASE}/ref/validators/": "Validators",

                # === Exceptions ===
                f"{BASE}/ref/exceptions/": "Django Exceptions",

                # === Additional Reference ===
                f"{BASE}/ref/contrib/": "contrib Packages",
                f"{BASE}/ref/contrib/admin/": "The Django Admin Site",
                f"{BASE}/ref/contrib/admin/actions/": "Admin Actions",
                f"{BASE}/ref/contrib/admin/filters/": "Admin List Filters",
                f"{BASE}/ref/contrib/admin/admindocs/": "AdminDocs",
                f"{BASE}/ref/contrib/auth/": "django.contrib.auth",
                f"{BASE}/ref/contrib/contenttypes/": "The Contenttypes Framework",
                f"{BASE}/ref/contrib/flatpages/": "The Flatpages App",
                f"{BASE}/ref/contrib/gis/": "GeoDjango",
                f"{BASE}/ref/contrib/humanize/": "django.contrib.humanize",
                f"{BASE}/ref/contrib/messages/": "The Messages Framework",
                f"{BASE}/ref/contrib/postgres/": "django.contrib.postgres",
                f"{BASE}/ref/contrib/postgres/fields/": "PostgreSQL Specific Model Fields",
                f"{BASE}/ref/contrib/postgres/aggregates/": "PostgreSQL Aggregation Functions",
                f"{BASE}/ref/contrib/postgres/constraints/": "PostgreSQL Constraints",
                f"{BASE}/ref/contrib/postgres/expressions/": "PostgreSQL Expressions",
                f"{BASE}/ref/contrib/postgres/forms/": "PostgreSQL Form Fields and Widgets",
                f"{BASE}/ref/contrib/postgres/functions/": "PostgreSQL Database Functions",
                f"{BASE}/ref/contrib/postgres/indexes/": "PostgreSQL Indexes",
                f"{BASE}/ref/contrib/postgres/lookups/": "PostgreSQL Lookups",
                f"{BASE}/ref/contrib/postgres/operations/": "PostgreSQL Database Migration Operations",
                f"{BASE}/ref/contrib/postgres/search/": "Full Text Search",
                f"{BASE}/ref/contrib/postgres/validators/": "PostgreSQL Validators",
                f"{BASE}/ref/contrib/redirects/": "The Redirects App",
                f"{BASE}/ref/contrib/sitemaps/": "The Sitemap Framework",
                f"{BASE}/ref/contrib/sites/": "The Sites Framework",
                f"{BASE}/ref/contrib/staticfiles/": "The Staticfiles App",
                f"{BASE}/ref/contrib/syndication/": "The Syndication Feed Framework",
                f"{BASE}/ref/databases/": "Databases",
                f"{BASE}/ref/django-admin/": "django-admin and manage.py",
                f"{BASE}/ref/checks/": "System Check Reference",
                f"{BASE}/ref/clickjacking/": "Clickjacking Protection",
                f"{BASE}/ref/csrf/": "Cross Site Request Forgery Protection",
                f"{BASE}/ref/files/": "File Handling",
                f"{BASE}/ref/files/storage/": "File Storage API",
                f"{BASE}/ref/files/uploads/": "Uploaded Files and Upload Handlers",
                f"{BASE}/ref/logging/": "Logging Reference",
                f"{BASE}/ref/migration-operations/": "Migration Operations",
                f"{BASE}/ref/paginator/": "Paginator",
                f"{BASE}/ref/request-response/": "Request and Response Objects",
                f"{BASE}/ref/schema-editor/": "SchemaEditor",
                f"{BASE}/ref/signals/": "Signals Reference",
                f"{BASE}/ref/template-response/": "TemplateResponse and SimpleTemplateResponse",
                f"{BASE}/ref/unicode/": "Unicode Data",
                f"{BASE}/ref/utils/": "Django Utils",

                # === Additional Reference ===
                f"{BASE}/ref/models/fields/#field-types": "Field Types Reference",
                f"{BASE}/ref/models/fields/#field-options": "Field Options Reference",
                f"{BASE}/ref/models/fields/#charfield": "CharField",
                f"{BASE}/ref/models/fields/#integerfield": "IntegerField",
                f"{BASE}/ref/models/fields/#booleanfield": "BooleanField",
                f"{BASE}/ref/models/fields/#datefield": "DateField",
                f"{BASE}/ref/models/fields/#datetimefield": "DateTimeField",
                f"{BASE}/ref/models/fields/#decimalfield": "DecimalField",
                f"{BASE}/ref/models/fields/#emailfield": "EmailField",
                f"{BASE}/ref/models/fields/#filefield": "FileField",
                f"{BASE}/ref/models/fields/#floatfield": "FloatField",
                f"{BASE}/ref/models/fields/#imagefield": "ImageField",
                f"{BASE}/ref/models/fields/#jsonfield": "JSONField",
                f"{BASE}/ref/models/fields/#slugfield": "SlugField",
                f"{BASE}/ref/models/fields/#textfield": "TextField",
                f"{BASE}/ref/models/fields/#urlfield": "URLField",
                f"{BASE}/ref/models/fields/#uuidfield": "UUIDField",
                f"{BASE}/ref/models/fields/#foreignkey": "ForeignKey",
                f"{BASE}/ref/models/fields/#manytomanyfield": "ManyToManyField",
                f"{BASE}/ref/models/fields/#onetoonefield": "OneToOneField",
                f"{BASE}/ref/models/querysets/#methods-that-return-new-querysets": "QuerySet Methods (New QuerySets)",
                f"{BASE}/ref/models/querysets/#methods-that-do-not-return-querysets": "QuerySet Methods (No QuerySets)",
                f"{BASE}/ref/models/querysets/#field-lookups": "Field Lookups Reference",
                f"{BASE}/ref/models/querysets/#aggregation-functions": "Aggregation Functions Reference",
                f"{BASE}/ref/models/querysets/#query-related-tools": "Query-Related Tools",
                f"{BASE}/ref/forms/fields/#built-in-field-classes": "Built-in Form Field Classes",
                f"{BASE}/ref/forms/fields/#core-field-arguments": "Core Field Arguments",
                f"{BASE}/ref/forms/widgets/#built-in-widgets": "Built-in Widgets",
                f"{BASE}/ref/forms/widgets/#specifying-widgets": "Specifying Widgets",
                f"{BASE}/ref/templates/builtins/#built-in-tag-reference": "Built-in Tag Reference",
                f"{BASE}/ref/templates/builtins/#built-in-filter-reference": "Built-in Filter Reference",
                f"{BASE}/ref/settings/#core-settings": "Core Settings",
                f"{BASE}/ref/settings/#auth": "Auth Settings",
                f"{BASE}/ref/settings/#database": "Database Settings",
                f"{BASE}/ref/settings/#email": "Email Settings",
                f"{BASE}/ref/settings/#cache": "Cache Settings",
                f"{BASE}/ref/settings/#globalization-i18n-l10n": "I18N/L10N Settings",
                f"{BASE}/ref/settings/#http": "HTTP Settings",
                f"{BASE}/ref/settings/#logging": "Logging Settings",
                f"{BASE}/ref/settings/#media-files": "Media Files Settings",
                f"{BASE}/ref/settings/#security": "Security Settings",
                f"{BASE}/ref/settings/#sessions": "Sessions Settings",
                f"{BASE}/ref/settings/#static-files": "Static Files Settings",
                f"{BASE}/ref/settings/#templates": "Templates Settings",
                f"{BASE}/ref/settings/#testing": "Testing Settings",
                f"{BASE}/ref/contrib/admin/#modeladmin-options": "ModelAdmin Options",
                f"{BASE}/ref/contrib/admin/#modeladmin-methods": "ModelAdmin Methods",
                f"{BASE}/ref/contrib/admin/#inlinemodeladmin-objects": "InlineModelAdmin Objects",
                f"{BASE}/ref/contrib/admin/#adminsite-objects": "AdminSite Objects",
                f"{BASE}/ref/contrib/admin/#logentry-objects": "LogEntry Objects",
                f"{BASE}/ref/contrib/admin/#overriding-admin-templates": "Overriding Admin Templates",
                f"{BASE}/ref/contrib/auth/#user-model": "User Model Reference",
                f"{BASE}/ref/contrib/auth/#permission-model": "Permission Model Reference",
                f"{BASE}/ref/contrib/auth/#group-model": "Group Model Reference",
                f"{BASE}/ref/contrib/auth/#login-and-logout-signals": "Login and Logout Signals",
                f"{BASE}/ref/contrib/auth/#authentication-backends": "Authentication Backends Reference",
                f"{BASE}/ref/django-admin/#available-commands": "Available Commands",
                f"{BASE}/ref/django-admin/#common-options": "Common django-admin Options",
                f"{BASE}/ref/request-response/#httprequest-objects": "HttpRequest Objects",
                f"{BASE}/ref/request-response/#httpresponse-objects": "HttpResponse Objects",
                f"{BASE}/ref/request-response/#jsonresponse-objects": "JsonResponse Objects",
                f"{BASE}/ref/request-response/#streaminghttpresponse-objects": "StreamingHttpResponse Objects",
                f"{BASE}/ref/exceptions/#django-core-exceptions": "Core Exceptions",
                f"{BASE}/ref/exceptions/#database-exceptions": "Database Exceptions",
                f"{BASE}/ref/exceptions/#http-exceptions": "HTTP Exceptions",
                f"{BASE}/ref/exceptions/#transaction-exceptions": "Transaction Exceptions",
                f"{BASE}/ref/validators/#built-in-validators": "Built-in Validators",
                f"{BASE}/ref/validators/#writing-validators": "Writing Validators",
                f"{BASE}/ref/middleware/#available-middleware": "Available Middleware",
                f"{BASE}/ref/middleware/#middleware-ordering": "Middleware Ordering",
                f"{BASE}/ref/signals/#model-signals": "Model Signals",
                f"{BASE}/ref/signals/#management-signals": "Management Signals",
                f"{BASE}/ref/signals/#request-response-signals": "Request/Response Signals",
                f"{BASE}/ref/signals/#test-signals": "Test Signals",
                f"{BASE}/ref/signals/#database-wrappers": "Database Wrappers Signals",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"django-{source_key}" if source_key else "django"
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
            for suffix in [' | Django documentation', ' — Django documentation',
                           ' | Django', ' — Django']:
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
                        "category": f"django-{source_key}",
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
            self.log.info(f"=== Scraping django/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    DjangoScraper(base, source_key).run()
