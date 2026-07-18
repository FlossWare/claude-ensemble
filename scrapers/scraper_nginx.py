#!/usr/bin/env python3
"""Nginx documentation scraper.

Covers:
  - Beginner's guide, installation, configuration
  - HTTP modules (core, proxy, ssl, upstream, rewrite, gzip, etc.)
  - Stream modules (core, proxy, ssl, upstream)
  - Mail modules (core, auth_http, proxy, ssl)
  - Admin guide (load balancing, caching, reverse proxy, SSL)
  - Reference (directives index, variables, core module)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class NginxScraper(BaseScraper):
    """Scrape Nginx documentation from nginx.org."""

    SOURCES = {
        "intro": {
            "pages": {
                "https://nginx.org/en/docs/": "Nginx Documentation",
                "https://nginx.org/en/docs/beginners_guide.html": "Beginner's Guide",
                "https://nginx.org/en/docs/install.html": "Installing Nginx",
                "https://nginx.org/en/docs/configure.html": "Building Nginx from Source",
                "https://nginx.org/en/docs/control.html": "Controlling Nginx",
                "https://nginx.org/en/docs/events.html": "Connection Processing Methods",
                "https://nginx.org/en/docs/hash.html": "Setting Up Hashes",
                "https://nginx.org/en/docs/debugging_log.html": "Debugging Log",
                "https://nginx.org/en/docs/syslog.html": "Logging to Syslog",
                "https://nginx.org/en/docs/syntax.html": "Configuration File Measurement Units",
                "https://nginx.org/en/docs/switches.html": "Command-line Parameters",
                "https://nginx.org/en/docs/windows.html": "Nginx for Windows",
                "https://nginx.org/en/docs/http/configuring_https_servers.html": "Configuring HTTPS Servers",
                "https://nginx.org/en/docs/http/request_processing.html": "How Nginx Processes a Request",
                "https://nginx.org/en/docs/http/server_names.html": "Server Names",
                "https://nginx.org/en/docs/http/load_balancing.html": "HTTP Load Balancing",
                "https://nginx.org/en/docs/http/websocket.html": "WebSocket Proxying",
                "https://nginx.org/en/docs/http/converting_rewrite_rules.html": "Converting Rewrite Rules",
            },
        },
        "http-modules": {
            "pages": {
                "https://nginx.org/en/docs/http/ngx_http_core_module.html": "HTTP Core Module",
                "https://nginx.org/en/docs/http/ngx_http_access_module.html": "HTTP Access Module",
                "https://nginx.org/en/docs/http/ngx_http_auth_basic_module.html": "HTTP Auth Basic Module",
                "https://nginx.org/en/docs/http/ngx_http_auth_request_module.html": "HTTP Auth Request Module",
                "https://nginx.org/en/docs/http/ngx_http_autoindex_module.html": "HTTP Autoindex Module",
                "https://nginx.org/en/docs/http/ngx_http_browser_module.html": "HTTP Browser Module",
                "https://nginx.org/en/docs/http/ngx_http_charset_module.html": "HTTP Charset Module",
                "https://nginx.org/en/docs/http/ngx_http_dav_module.html": "HTTP DAV Module",
                "https://nginx.org/en/docs/http/ngx_http_empty_gif_module.html": "HTTP Empty GIF Module",
                "https://nginx.org/en/docs/http/ngx_http_fastcgi_module.html": "HTTP FastCGI Module",
                "https://nginx.org/en/docs/http/ngx_http_flv_module.html": "HTTP FLV Module",
                "https://nginx.org/en/docs/http/ngx_http_geo_module.html": "HTTP Geo Module",
                "https://nginx.org/en/docs/http/ngx_http_geoip_module.html": "HTTP GeoIP Module",
                "https://nginx.org/en/docs/http/ngx_http_grpc_module.html": "HTTP gRPC Module",
                "https://nginx.org/en/docs/http/ngx_http_gunzip_module.html": "HTTP Gunzip Module",
                "https://nginx.org/en/docs/http/ngx_http_gzip_module.html": "HTTP Gzip Module",
                "https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html": "HTTP Gzip Static Module",
                "https://nginx.org/en/docs/http/ngx_http_headers_module.html": "HTTP Headers Module",
                "https://nginx.org/en/docs/http/ngx_http_image_filter_module.html": "HTTP Image Filter Module",
                "https://nginx.org/en/docs/http/ngx_http_index_module.html": "HTTP Index Module",
                "https://nginx.org/en/docs/http/ngx_http_limit_conn_module.html": "HTTP Limit Conn Module",
                "https://nginx.org/en/docs/http/ngx_http_limit_req_module.html": "HTTP Limit Req Module",
                "https://nginx.org/en/docs/http/ngx_http_log_module.html": "HTTP Log Module",
                "https://nginx.org/en/docs/http/ngx_http_map_module.html": "HTTP Map Module",
                "https://nginx.org/en/docs/http/ngx_http_memcached_module.html": "HTTP Memcached Module",
                "https://nginx.org/en/docs/http/ngx_http_mirror_module.html": "HTTP Mirror Module",
                "https://nginx.org/en/docs/http/ngx_http_mp4_module.html": "HTTP MP4 Module",
                "https://nginx.org/en/docs/http/ngx_http_perl_module.html": "HTTP Perl Module",
                "https://nginx.org/en/docs/http/ngx_http_proxy_module.html": "HTTP Proxy Module",
                "https://nginx.org/en/docs/http/ngx_http_random_index_module.html": "HTTP Random Index Module",
                "https://nginx.org/en/docs/http/ngx_http_realip_module.html": "HTTP Real IP Module",
                "https://nginx.org/en/docs/http/ngx_http_referer_module.html": "HTTP Referer Module",
                "https://nginx.org/en/docs/http/ngx_http_rewrite_module.html": "HTTP Rewrite Module",
                "https://nginx.org/en/docs/http/ngx_http_scgi_module.html": "HTTP SCGI Module",
                "https://nginx.org/en/docs/http/ngx_http_secure_link_module.html": "HTTP Secure Link Module",
                "https://nginx.org/en/docs/http/ngx_http_session_log_module.html": "HTTP Session Log Module",
                "https://nginx.org/en/docs/http/ngx_http_slice_module.html": "HTTP Slice Module",
                "https://nginx.org/en/docs/http/ngx_http_spdy_module.html": "HTTP SPDY Module",
                "https://nginx.org/en/docs/http/ngx_http_split_clients_module.html": "HTTP Split Clients Module",
                "https://nginx.org/en/docs/http/ngx_http_ssl_module.html": "HTTP SSL Module",
                "https://nginx.org/en/docs/http/ngx_http_status_module.html": "HTTP Status Module",
                "https://nginx.org/en/docs/http/ngx_http_stub_status_module.html": "HTTP Stub Status Module",
                "https://nginx.org/en/docs/http/ngx_http_sub_module.html": "HTTP Sub Filter Module",
                "https://nginx.org/en/docs/http/ngx_http_addition_module.html": "HTTP Addition Module",
                "https://nginx.org/en/docs/http/ngx_http_upstream_module.html": "HTTP Upstream Module",
                "https://nginx.org/en/docs/http/ngx_http_upstream_hc_module.html": "HTTP Upstream Health Check Module",
                "https://nginx.org/en/docs/http/ngx_http_userid_module.html": "HTTP UserID Module",
                "https://nginx.org/en/docs/http/ngx_http_uwsgi_module.html": "HTTP uWSGI Module",
                "https://nginx.org/en/docs/http/ngx_http_xslt_module.html": "HTTP XSLT Module",
                "https://nginx.org/en/docs/http/ngx_http_v2_module.html": "HTTP/2 Module",
                "https://nginx.org/en/docs/http/ngx_http_v3_module.html": "HTTP/3 Module",
            },
        },
        "stream-modules": {
            "pages": {
                "https://nginx.org/en/docs/stream/ngx_stream_core_module.html": "Stream Core Module",
                "https://nginx.org/en/docs/stream/ngx_stream_access_module.html": "Stream Access Module",
                "https://nginx.org/en/docs/stream/ngx_stream_geo_module.html": "Stream Geo Module",
                "https://nginx.org/en/docs/stream/ngx_stream_geoip_module.html": "Stream GeoIP Module",
                "https://nginx.org/en/docs/stream/ngx_stream_limit_conn_module.html": "Stream Limit Conn Module",
                "https://nginx.org/en/docs/stream/ngx_stream_log_module.html": "Stream Log Module",
                "https://nginx.org/en/docs/stream/ngx_stream_map_module.html": "Stream Map Module",
                "https://nginx.org/en/docs/stream/ngx_stream_proxy_module.html": "Stream Proxy Module",
                "https://nginx.org/en/docs/stream/ngx_stream_realip_module.html": "Stream Real IP Module",
                "https://nginx.org/en/docs/stream/ngx_stream_return_module.html": "Stream Return Module",
                "https://nginx.org/en/docs/stream/ngx_stream_set_module.html": "Stream Set Module",
                "https://nginx.org/en/docs/stream/ngx_stream_split_clients_module.html": "Stream Split Clients Module",
                "https://nginx.org/en/docs/stream/ngx_stream_ssl_module.html": "Stream SSL Module",
                "https://nginx.org/en/docs/stream/ngx_stream_ssl_preread_module.html": "Stream SSL Preread Module",
                "https://nginx.org/en/docs/stream/ngx_stream_upstream_module.html": "Stream Upstream Module",
                "https://nginx.org/en/docs/stream/ngx_stream_upstream_hc_module.html": "Stream Upstream Health Check Module",
            },
        },
        "mail-modules": {
            "pages": {
                "https://nginx.org/en/docs/mail/ngx_mail_core_module.html": "Mail Core Module",
                "https://nginx.org/en/docs/mail/ngx_mail_auth_http_module.html": "Mail Auth HTTP Module",
                "https://nginx.org/en/docs/mail/ngx_mail_proxy_module.html": "Mail Proxy Module",
                "https://nginx.org/en/docs/mail/ngx_mail_ssl_module.html": "Mail SSL Module",
                "https://nginx.org/en/docs/mail/ngx_mail_imap_module.html": "Mail IMAP Module",
                "https://nginx.org/en/docs/mail/ngx_mail_pop3_module.html": "Mail POP3 Module",
                "https://nginx.org/en/docs/mail/ngx_mail_smtp_module.html": "Mail SMTP Module",
            },
        },
        "reference": {
            "pages": {
                "https://nginx.org/en/docs/dirindex.html": "Directives Index",
                "https://nginx.org/en/docs/varindex.html": "Variables Index",
                "https://nginx.org/en/docs/ngx_core_module.html": "Core Module",
                "https://nginx.org/en/docs/http/ngx_http_api_module.html": "HTTP API Module",
                "https://nginx.org/en/docs/njs/index.html": "njs Scripting Language",
                "https://nginx.org/en/docs/njs/reference.html": "njs Reference",
                "https://nginx.org/en/docs/njs/compatibility.html": "njs Compatibility",
                "https://nginx.org/en/docs/quic.html": "QUIC and HTTP/3",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"nginx-docs-{source_key}" if source_key else "nginx-docs"
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
            for suffix in [' | NGINX', ' - nginx.org', ' | nginx']:
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
                        "category": "nginx-docs",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.0)

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
            self.log.info(f"=== Scraping nginx-docs/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    NginxScraper(base, source_key).run()
