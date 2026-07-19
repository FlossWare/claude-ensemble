#!/usr/bin/env python3
"""Elasticsearch documentation scraper.

Covers:
  - Getting started, index modules, mapping
  - Search, aggregations, query DSL
  - Analysis, cluster management, REST APIs
  - Scripting, ingest, ILM, snapshot/restore
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class ElasticsearchScraper(BaseScraper):
    """Scrape Elasticsearch documentation from elastic.co."""

    SOURCES = {
        "getting-started": {
            "pages": {
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/getting-started.html": "Getting Started",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/install-elasticsearch.html": "Install Elasticsearch",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/docker.html": "Install with Docker",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/deb.html": "Install with Debian Package",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/rpm.html": "Install with RPM",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/targz.html": "Install from Archive",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/settings.html": "Configuring Elasticsearch",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/important-settings.html": "Important Settings",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/system-config.html": "Important System Configuration",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/bootstrap-checks.html": "Bootstrap Checks",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/starting-elasticsearch.html": "Starting Elasticsearch",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/stopping-elasticsearch.html": "Stopping Elasticsearch",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/setup-upgrade.html": "Upgrade Elasticsearch",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/configuring-stack-security.html": "Configuring Security",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/jvm-options.html": "JVM Options",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/heap-size.html": "Heap Size Settings",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/file-descriptors.html": "File Descriptors",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/vm-max-map-count.html": "Virtual Memory",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/max-number-of-threads.html": "Number of Threads",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/networkaddress-cache-ttl.html": "DNS Cache Settings",
            },
        },
        "index-modules": {
            "pages": {
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules.html": "Index Modules",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules-analysis.html": "Index Analysis Module",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules-allocation.html": "Index Shard Allocation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules-merge.html": "Index Merge",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules-similarity.html": "Index Similarity Module",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules-slowlog.html": "Index Slow Log",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules-store.html": "Index Store",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules-translog.html": "Index Translog",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules-history-retention.html": "Index History Retention",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules-index-sorting.html": "Index Sorting",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules-indexing-pressure.html": "Indexing Pressure",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-create-index.html": "Create Index API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-delete-index.html": "Delete Index API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-get-index.html": "Get Index API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-exists.html": "Index Exists API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-open-close.html": "Open/Close Index API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-shrink-index.html": "Shrink Index API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-split-index.html": "Split Index API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-rollover-index.html": "Rollover Index API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-aliases.html": "Index Aliases",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/index-templates.html": "Index Templates",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/data-streams.html": "Data Streams",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-get-settings.html": "Get Index Settings API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-update-settings.html": "Update Index Settings API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-get-mapping.html": "Get Mapping API",
            },
        },
        "mapping": {
            "pages": {
                # Mapping overview
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping.html": "Mapping",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/dynamic-mapping.html": "Dynamic Mapping",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/explicit-mapping.html": "Explicit Mapping",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/runtime.html": "Runtime Fields",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping-types.html": "Field Data Types",
                # Field types
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/binary.html": "Binary Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/boolean.html": "Boolean Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/date.html": "Date Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/date_nanos.html": "Date Nanoseconds Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/dense-vector.html": "Dense Vector Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/flattened.html": "Flattened Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/geo-point.html": "Geo-point Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/geo-shape.html": "Geo-shape Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/histogram.html": "Histogram Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ip.html": "IP Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/join.html": "Join Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/keyword.html": "Keyword Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/number.html": "Numeric Field Types",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/nested.html": "Nested Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/object.html": "Object Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/percolator.html": "Percolator Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/point.html": "Point Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/rank-feature.html": "Rank Feature Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/rank-features.html": "Rank Features Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-as-you-type.html": "Search-as-you-type Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/shape.html": "Shape Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/sparse-vector.html": "Sparse Vector Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/text.html": "Text Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/token-count.html": "Token Count Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/unsigned-long.html": "Unsigned Long Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/version.html": "Version Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/wildcard.html": "Wildcard Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/aggregate-metric-double.html": "Aggregate Metric Double Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/completion.html": "Completion Suggester Field Type",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/alias.html": "Alias Field Type",
                # Mapping parameters
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping-params.html": "Mapping Parameters",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analyzer.html": "Analyzer Parameter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping-boost.html": "Boost Parameter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/copy-to.html": "Copy To Parameter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/doc-values.html": "Doc Values Parameter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/enabled.html": "Enabled Parameter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping-field-meta.html": "Field Meta Parameter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/fielddata.html": "Fielddata Parameter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping-index.html": "Index Parameter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/multi-fields.html": "Multi-fields",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/normalizer.html": "Normalizer Parameter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/norms.html": "Norms Parameter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/null-value.html": "Null Value Parameter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping-store.html": "Store Parameter",
            },
        },
        "search": {
            "pages": {
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-your-data.html": "Search Your Data",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-search.html": "Search API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-multi-search.html": "Multi Search API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/async-search.html": "Async Search",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/near-real-time.html": "Near Real-Time Search",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/paginate-search-results.html": "Paginate Search Results",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/inner-hits.html": "Inner Hits",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-fields.html": "Retrieve Selected Fields",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/highlighting.html": "Highlighting",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-count.html": "Count API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/filter-search-results.html": "Filter Search Results",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/sort-search-results.html": "Sort Search Results",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/collapse-search-results.html": "Collapse Search Results",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-suggesters.html": "Suggesters",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-profile.html": "Profile API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-explain.html": "Explain API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-validate.html": "Validate API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-template.html": "Search Templates",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html": "k-Nearest Neighbor (kNN) Search",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/semantic-search.html": "Semantic Search",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/retriever.html": "Retriever",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/scroll-api.html": "Scroll API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/point-in-time-api.html": "Point in Time API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-across-clusters.html": "Search Across Clusters",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-shard-routing.html": "Search Shard Routing",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-rank-eval.html": "Ranking Evaluation API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-terms-enum.html": "Terms Enum API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/eql.html": "EQL Search",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/sql-overview.html": "SQL Overview",
            },
        },
        "aggregations": {
            "pages": {
                # Overview
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations.html": "Aggregations",
                # Bucket aggregations
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-terms-aggregation.html": "Terms Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-datehistogram-aggregation.html": "Date Histogram Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-histogram-aggregation.html": "Histogram Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-range-aggregation.html": "Range Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-daterange-aggregation.html": "Date Range Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-filter-aggregation.html": "Filter Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-filters-aggregation.html": "Filters Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-global-aggregation.html": "Global Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-missing-aggregation.html": "Missing Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-nested-aggregation.html": "Nested Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-reverse-nested-aggregation.html": "Reverse Nested Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-children-aggregation.html": "Children Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-composite-aggregation.html": "Composite Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-autodatehistogram-aggregation.html": "Auto-interval Date Histogram",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-multi-terms-aggregation.html": "Multi Terms Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-rare-terms-aggregation.html": "Rare Terms Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-significantterms-aggregation.html": "Significant Terms Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-significanttext-aggregation.html": "Significant Text Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-sampler-aggregation.html": "Sampler Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-diversified-sampler-aggregation.html": "Diversified Sampler Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-adjacency-matrix-aggregation.html": "Adjacency Matrix Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-geohashgrid-aggregation.html": "Geohash Grid Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-geotilegrid-aggregation.html": "Geotile Grid Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-iprange-aggregation.html": "IP Range Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-variablewidthhistogram-aggregation.html": "Variable Width Histogram",
                # Metric aggregations
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-avg-aggregation.html": "Avg Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-sum-aggregation.html": "Sum Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-min-aggregation.html": "Min Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-max-aggregation.html": "Max Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-stats-aggregation.html": "Stats Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-extendedstats-aggregation.html": "Extended Stats Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-valuecount-aggregation.html": "Value Count Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-cardinality-aggregation.html": "Cardinality Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-percentile-aggregation.html": "Percentiles Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-percentile-rank-aggregation.html": "Percentile Ranks Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-top-hits-aggregation.html": "Top Hits Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-top-metrics.html": "Top Metrics Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-median-absolute-deviation-aggregation.html": "Median Absolute Deviation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-weight-avg-aggregation.html": "Weighted Avg Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-geo-bounds-aggregation.html": "Geo Bounds Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-geocentroid-aggregation.html": "Geo Centroid Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-geo-line.html": "Geo Line Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-matrix-stats-aggregation.html": "Matrix Stats Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-scripted-metric-aggregation.html": "Scripted Metric Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-string-stats-aggregation.html": "String Stats Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-ttest-aggregation.html": "T-Test Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-rate-aggregation.html": "Rate Aggregation",
                # Pipeline aggregations
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline.html": "Pipeline Aggregations",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-avg-bucket-aggregation.html": "Avg Bucket Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-sum-bucket-aggregation.html": "Sum Bucket Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-min-bucket-aggregation.html": "Min Bucket Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-max-bucket-aggregation.html": "Max Bucket Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-stats-bucket-aggregation.html": "Stats Bucket Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-extended-stats-bucket-aggregation.html": "Extended Stats Bucket Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-percentiles-bucket-aggregation.html": "Percentiles Bucket Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-movfn-aggregation.html": "Moving Function Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-cumulative-sum-aggregation.html": "Cumulative Sum Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-cumulative-cardinality-aggregation.html": "Cumulative Cardinality Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-derivative-aggregation.html": "Derivative Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-serialdiff-aggregation.html": "Serial Differencing Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-bucket-script-aggregation.html": "Bucket Script Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-bucket-selector-aggregation.html": "Bucket Selector Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-bucket-sort-aggregation.html": "Bucket Sort Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-normalize-aggregation.html": "Normalize Aggregation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-pipeline-inference-bucket-aggregation.html": "Inference Bucket Aggregation",
            },
        },
        "query-dsl": {
            "pages": {
                # Overview
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html": "Query DSL",
                # Full text queries
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-match-query.html": "Match Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-match-query-phrase.html": "Match Phrase Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-match-query-phrase-prefix.html": "Match Phrase Prefix Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-multi-match-query.html": "Multi-match Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-combined-fields-query.html": "Combined Fields Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html": "Query String Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-simple-query-string-query.html": "Simple Query String Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-intervals-query.html": "Intervals Query",
                # Term-level queries
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-term-query.html": "Term Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-terms-query.html": "Terms Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-terms-set-query.html": "Terms Set Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-range-query.html": "Range Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-exists-query.html": "Exists Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-prefix-query.html": "Prefix Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-wildcard-query.html": "Wildcard Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-regexp-query.html": "Regexp Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-fuzzy-query.html": "Fuzzy Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-ids-query.html": "IDs Query",
                # Compound queries
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-bool-query.html": "Boolean Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-boosting-query.html": "Boosting Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-constant-score-query.html": "Constant Score Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-dis-max-query.html": "Disjunction Max Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-function-score-query.html": "Function Score Query",
                # Joining queries
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-nested-query.html": "Nested Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-has-child-query.html": "Has Child Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-has-parent-query.html": "Has Parent Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-parent-id-query.html": "Parent ID Query",
                # Geo queries
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-geo-bounding-box-query.html": "Geo Bounding Box Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-geo-distance-query.html": "Geo Distance Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-geo-polygon-query.html": "Geo Polygon Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-geo-shape-query.html": "Geo Shape Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-shape-query.html": "Shape Query",
                # Span queries
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-span-term-query.html": "Span Term Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-span-multi-term-query.html": "Span Multi-Term Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-span-first-query.html": "Span First Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-span-near-query.html": "Span Near Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-span-or-query.html": "Span Or Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-span-not-query.html": "Span Not Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-span-containing-query.html": "Span Containing Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-span-within-query.html": "Span Within Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-span-field-masking-query.html": "Span Field Masking Query",
                # Specialized queries
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-percolate-query.html": "Percolate Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-rank-feature-query.html": "Rank Feature Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-script-query.html": "Script Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-script-score-query.html": "Script Score Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-wrapper-query.html": "Wrapper Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-pinned-query.html": "Pinned Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-knn-query.html": "kNN Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-text-expansion-query.html": "Text Expansion Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-semantic-query.html": "Semantic Query",
                # Match all
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-match-all-query.html": "Match All Query",
                # Other specialized
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-distance-feature-query.html": "Distance Feature Query",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-more-like-this-query.html": "More Like This Query",
            },
        },
        "analysis": {
            "pages": {
                # Overview
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis.html": "Text Analysis",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-overview.html": "Text Analysis Overview",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-concepts.html": "Text Analysis Concepts",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-anatomy.html": "Anatomy of an Analyzer",
                # Built-in analyzers
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-standard-analyzer.html": "Standard Analyzer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-simple-analyzer.html": "Simple Analyzer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-whitespace-analyzer.html": "Whitespace Analyzer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-stop-analyzer.html": "Stop Analyzer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-keyword-analyzer.html": "Keyword Analyzer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-pattern-analyzer.html": "Pattern Analyzer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-fingerprint-analyzer.html": "Fingerprint Analyzer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-custom-analyzer.html": "Custom Analyzer",
                # Tokenizers
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-tokenizers.html": "Tokenizers",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-standard-tokenizer.html": "Standard Tokenizer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-letter-tokenizer.html": "Letter Tokenizer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-lowercase-tokenizer.html": "Lowercase Tokenizer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-whitespace-tokenizer.html": "Whitespace Tokenizer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-uaxurlemail-tokenizer.html": "UAX URL Email Tokenizer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-classic-tokenizer.html": "Classic Tokenizer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-ngram-tokenizer.html": "N-gram Tokenizer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-edgengram-tokenizer.html": "Edge N-gram Tokenizer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-keyword-tokenizer.html": "Keyword Tokenizer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-pattern-tokenizer.html": "Pattern Tokenizer",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-pathhierarchy-tokenizer.html": "Path Hierarchy Tokenizer",
                # Token filters
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-tokenfilter.html": "Token Filters",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-lowercase-tokenfilter.html": "Lowercase Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-uppercase-tokenfilter.html": "Uppercase Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-stop-tokenfilter.html": "Stop Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-synonym-tokenfilter.html": "Synonym Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-synonym-graph-tokenfilter.html": "Synonym Graph Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-stemmer-tokenfilter.html": "Stemmer Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-stemmer-override-tokenfilter.html": "Stemmer Override Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-snowball-tokenfilter.html": "Snowball Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-asciifolding-tokenfilter.html": "ASCII Folding Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-length-tokenfilter.html": "Length Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-truncate-tokenfilter.html": "Truncate Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-trim-tokenfilter.html": "Trim Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-unique-tokenfilter.html": "Unique Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-pattern-replace-tokenfilter.html": "Pattern Replace Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-shingle-tokenfilter.html": "Shingle Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-ngram-tokenfilter.html": "N-gram Token Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-edgengram-tokenfilter.html": "Edge N-gram Token Filter",
                # Character filters
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-charfilters.html": "Character Filters",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-htmlstrip-charfilter.html": "HTML Strip Character Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-mapping-charfilter.html": "Mapping Character Filter",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-pattern-replace-charfilter.html": "Pattern Replace Character Filter",
                # Normalizers
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-normalizers.html": "Normalizers",
            },
        },
        "cluster": {
            "pages": {
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-cluster.html": "Cluster-level Shard Allocation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-health.html": "Cluster Health API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-state.html": "Cluster State API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-stats.html": "Cluster Stats API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-nodes-stats.html": "Nodes Stats API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-nodes-info.html": "Nodes Info API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-nodes-hot-threads.html": "Nodes Hot Threads API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-allocation-explain.html": "Cluster Allocation Explain API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-reroute.html": "Cluster Reroute API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-update-settings.html": "Cluster Update Settings API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-discovery.html": "Discovery and Cluster Formation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-discovery-settings.html": "Discovery Settings",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-discovery-hosts-providers.html": "Discovery Hosts Providers",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-discovery-quorums.html": "Quorum-based Decision Making",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-discovery-voting.html": "Voting Configuration Exclusions",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-discovery-bootstrap-cluster.html": "Bootstrapping a Cluster",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-node.html": "Node",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-gateway.html": "Local Gateway",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-network.html": "Network Settings",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-threadpool.html": "Thread Pools",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-remote-clusters.html": "Remote Clusters",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/shard-allocation-filtering.html": "Index-level Shard Allocation Filtering",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/delayed-allocation.html": "Delaying Allocation When a Node Leaves",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/allocation-awareness.html": "Shard Allocation Awareness",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/allocation-total-shards.html": "Total Shards Per Node",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/misc-cluster-settings.html": "Miscellaneous Cluster Settings",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-pending.html": "Pending Cluster Tasks API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-nodes-reload-secure-settings.html": "Nodes Reload Secure Settings API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-nodes-usage.html": "Nodes Feature Usage API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cluster-remote-info.html": "Remote Cluster Info API",
            },
        },
        "rest-apis": {
            "pages": {
                # Overview
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/rest-apis.html": "REST APIs",
                # Document APIs
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-index_.html": "Index API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-get.html": "Get API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-delete.html": "Delete API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-update.html": "Update API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-bulk.html": "Bulk API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-multi-get.html": "Multi Get API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-reindex.html": "Reindex API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-update-by-query.html": "Update By Query API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-delete-by-query.html": "Delete By Query API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-termvectors.html": "Term Vectors API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-multi-termvectors.html": "Multi Term Vectors API",
                # Cat APIs
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat.html": "Cat APIs",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-health.html": "Cat Health",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-indices.html": "Cat Indices",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-nodes.html": "Cat Nodes",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-shards.html": "Cat Shards",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-allocation.html": "Cat Allocation",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-segments.html": "Cat Segments",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-count.html": "Cat Count",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-recovery.html": "Cat Recovery",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-tasks.html": "Cat Tasks",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-aliases.html": "Cat Aliases",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-templates.html": "Cat Templates",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-plugins.html": "Cat Plugins",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-thread-pool.html": "Cat Thread Pool",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-fielddata.html": "Cat Fielddata",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-master.html": "Cat Master",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-pending-tasks.html": "Cat Pending Tasks",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-snapshots.html": "Cat Snapshots",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-repositories.html": "Cat Repositories",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-nodeattrs.html": "Cat Node Attributes",
                # Tasks API
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/tasks.html": "Task Management API",
                # Security APIs
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api.html": "Security APIs",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-authenticate.html": "Authenticate API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-put-user.html": "Create or Update Users API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-get-user.html": "Get Users API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-delete-user.html": "Delete Users API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-put-role.html": "Create or Update Roles API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-get-role.html": "Get Roles API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-delete-role.html": "Delete Roles API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-create-api-key.html": "Create API Key API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-get-api-key.html": "Get API Key API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-invalidate-api-key.html": "Invalidate API Key API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-change-password.html": "Change Password API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-put-role-mapping.html": "Create or Update Role Mappings API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-get-role-mapping.html": "Get Role Mappings API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-delete-role-mapping.html": "Delete Role Mappings API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-get-privileges.html": "Get Privileges API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-put-privileges.html": "Create or Update Privileges API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-has-privileges.html": "Has Privileges API",
            },
        },
        "scripting": {
            "pages": {
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-scripting.html": "Scripting",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-scripting-painless.html": "Painless Scripting Language",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-scripting-using.html": "How to Use Scripts",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-scripting-fields.html": "Accessing Document Fields",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-scripting-security.html": "Scripting and Security",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-scripting-engine.html": "Advanced Scripting with Engine",
                "https://www.elastic.co/guide/en/elasticsearch/painless/current/painless-guide.html": "Painless Guide",
                "https://www.elastic.co/guide/en/elasticsearch/painless/current/painless-lang-spec.html": "Painless Language Specification",
                "https://www.elastic.co/guide/en/elasticsearch/painless/current/painless-api-reference.html": "Painless API Reference",
                "https://www.elastic.co/guide/en/elasticsearch/painless/current/painless-contexts.html": "Painless Contexts",
                "https://www.elastic.co/guide/en/elasticsearch/painless/current/painless-operators.html": "Painless Operators",
                "https://www.elastic.co/guide/en/elasticsearch/painless/current/painless-types.html": "Painless Types",
                "https://www.elastic.co/guide/en/elasticsearch/painless/current/painless-variables.html": "Painless Variables",
                "https://www.elastic.co/guide/en/elasticsearch/painless/current/painless-statements.html": "Painless Statements",
                "https://www.elastic.co/guide/en/elasticsearch/painless/current/painless-functions.html": "Painless Functions",
                "https://www.elastic.co/guide/en/elasticsearch/painless/current/painless-lambdas.html": "Painless Lambdas",
                "https://www.elastic.co/guide/en/elasticsearch/painless/current/painless-regexes.html": "Painless Regexes",
            },
        },
        "ingest": {
            "pages": {
                # Overview
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ingest.html": "Ingest Pipelines",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ingest-apis.html": "Ingest APIs",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/put-pipeline-api.html": "Create or Update Pipeline API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/get-pipeline-api.html": "Get Pipeline API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/delete-pipeline-api.html": "Delete Pipeline API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/simulate-pipeline-api.html": "Simulate Pipeline API",
                # Processors
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/append-processor.html": "Append Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/bytes-processor.html": "Bytes Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/circle-processor.html": "Circle Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/community-id-processor.html": "Community ID Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/convert-processor.html": "Convert Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/csv-processor.html": "CSV Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/date-processor.html": "Date Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/date-index-name-processor.html": "Date Index Name Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/dissect-processor.html": "Dissect Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/dot-expand-processor.html": "Dot Expander Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/drop-processor.html": "Drop Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/enrich-processor.html": "Enrich Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/fail-processor.html": "Fail Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/fingerprint-processor.html": "Fingerprint Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/foreach-processor.html": "Foreach Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/geoip-processor.html": "GeoIP Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/grok-processor.html": "Grok Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/gsub-processor.html": "Gsub Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/htmlstrip-processor.html": "HTML Strip Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/inference-processor.html": "Inference Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/join-processor.html": "Join Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/json-processor.html": "JSON Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/kv-processor.html": "KV Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/lowercase-processor.html": "Lowercase Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/network-direction-processor.html": "Network Direction Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/pipeline-processor.html": "Pipeline Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/redact-processor.html": "Redact Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/registered-domain-processor.html": "Registered Domain Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/remove-processor.html": "Remove Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/rename-processor.html": "Rename Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/reroute-processor.html": "Reroute Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/script-processor.html": "Script Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/set-processor.html": "Set Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/set-security-user-processor.html": "Set Security User Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/sort-processor.html": "Sort Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/split-processor.html": "Split Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/trim-processor.html": "Trim Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/uppercase-processor.html": "Uppercase Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/uri-parts-processor.html": "URI Parts Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/urldecode-processor.html": "URL Decode Processor",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/user-agent-processor.html": "User Agent Processor",
            },
        },
        "ilm": {
            "pages": {
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/index-lifecycle-management.html": "Index Lifecycle Management",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/overview-index-lifecycle-management.html": "ILM Overview",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-concepts.html": "ILM Concepts",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/getting-started-index-lifecycle-management.html": "Getting Started with ILM",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-actions.html": "ILM Actions",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-allocate.html": "ILM Allocate Action",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-delete.html": "ILM Delete Action",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-forcemerge.html": "ILM Force Merge Action",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-freeze.html": "ILM Freeze Action",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-rollover.html": "ILM Rollover Action",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-searchable-snapshot.html": "ILM Searchable Snapshot Action",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-set-priority.html": "ILM Set Priority Action",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-shrink.html": "ILM Shrink Action",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-put-lifecycle.html": "Create or Update ILM Policy API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-get-lifecycle.html": "Get ILM Policy API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-delete-lifecycle.html": "Delete ILM Policy API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-move-to-step.html": "Move to Lifecycle Step API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-retry-policy.html": "Retry ILM Policy API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-remove-policy.html": "Remove ILM Policy API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-explain-lifecycle.html": "Explain ILM Lifecycle API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-get-status.html": "Get ILM Status API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-start.html": "Start ILM API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-stop.html": "Stop ILM API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-readonly.html": "ILM Read Only Action",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-unfollow.html": "ILM Unfollow Action",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-wait-for-snapshot.html": "ILM Wait for Snapshot Action",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-downsample.html": "ILM Downsample Action",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-migrate.html": "ILM Migrate Action",
            },
        },
        "snapshot-restore": {
            "pages": {
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshot-restore.html": "Snapshot and Restore",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshots-register-repository.html": "Register a Snapshot Repository",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshots-take-snapshot.html": "Create a Snapshot",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshots-restore-snapshot.html": "Restore a Snapshot",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshots-monitor-snapshot-restore.html": "Monitor Snapshot and Restore",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/searchable-snapshots.html": "Searchable Snapshots",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/repository-s3.html": "S3 Repository",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/repository-gcs.html": "Google Cloud Storage Repository",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/repository-azure.html": "Azure Repository",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/repository-shared-file-system.html": "Shared File System Repository",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshots-delete-snapshot.html": "Delete a Snapshot",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshot-lifecycle-management.html": "Snapshot Lifecycle Management",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/getting-started-snapshot-lifecycle-management.html": "Getting Started with SLM",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/slm-api-put-policy.html": "Create or Update SLM Policy API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/slm-api-get-policy.html": "Get SLM Policy API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/slm-api-delete-policy.html": "Delete SLM Policy API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/slm-api-execute-lifecycle.html": "Execute SLM Policy API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/slm-api-execute-retention.html": "Execute SLM Retention API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/slm-api-get-status.html": "Get SLM Status API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/slm-api-get-stats.html": "Get SLM Stats API",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/repository-url.html": "URL Repository",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/repository-source-only.html": "Source Only Repository",
            },
        },
        "security": {
            "pages": {
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/secure-cluster.html": "Secure a Cluster",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-overview.html": "Security Overview",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/setting-up-authentication.html": "Setting Up Authentication",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/realms.html": "Realms",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/native-realm.html": "Native Realm",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ldap-realm.html": "LDAP Realm",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/active-directory-realm.html": "Active Directory Realm",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/saml-realm.html": "SAML Realm",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/oidc-realm.html": "OpenID Connect Realm",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/pki-realm.html": "PKI Realm",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/kerberos-realm.html": "Kerberos Realm",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/jwt-realm.html": "JWT Realm",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/authorization.html": "Authorization",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/built-in-roles.html": "Built-in Roles",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/defining-roles.html": "Defining Roles",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/field-and-document-access-control.html": "Field and Document Level Security",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/api-key-authentication.html": "API Key Authentication",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/encrypting-communications.html": "Encrypting Communications",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ssl-tls.html": "SSL/TLS Configuration",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/auditing.html": "Auditing Security Events",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/audit-event-types.html": "Audit Event Types",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/auditing-settings.html": "Auditing Settings",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/ip-filtering.html": "IP Filtering",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-settings.html": "Security Settings",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/separating-node-client-traffic.html": "Separating Node and Client Traffic",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/configuring-tls.html": "Configuring TLS",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/security-files.html": "Security Files",
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/fips-140-compliance.html": "FIPS 140-2 Compliance",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"elasticsearch-{source_key}" if source_key else "elasticsearch"
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
            for suffix in [' | Elasticsearch Guide', ' | Elastic', ' [master]', ' [8.x]', ' [current]']:
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
                        "category": f"elasticsearch-{source_key}",
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
            self.log.info(f"=== Scraping elasticsearch/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    ElasticsearchScraper(base, source_key).run()
