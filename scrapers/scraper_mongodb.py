#!/usr/bin/env python3
"""MongoDB documentation scraper.

Covers:
  - CRUD operations
  - Aggregation framework
  - Data modeling and indexes
  - Security, replication, sharding
  - Administration, storage, transactions
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class MongoDBScraper(BaseScraper):
    """Scrape MongoDB documentation from mongodb.com/docs/manual."""

    SOURCES = {
        "crud": {
            "pages": {
                # Core CRUD
                "https://www.mongodb.com/docs/manual/crud/": "CRUD Overview",
                "https://www.mongodb.com/docs/manual/core/document/": "Documents",
                "https://www.mongodb.com/docs/manual/tutorial/insert-documents/": "Insert Documents",
                "https://www.mongodb.com/docs/manual/tutorial/query-documents/": "Query Documents",
                "https://www.mongodb.com/docs/manual/tutorial/update-documents/": "Update Documents",
                "https://www.mongodb.com/docs/manual/tutorial/remove-documents/": "Delete Documents",
                # Query operators
                "https://www.mongodb.com/docs/manual/reference/operator/query/": "Query Operators Overview",
                "https://www.mongodb.com/docs/manual/reference/operator/query/eq/": "$eq",
                "https://www.mongodb.com/docs/manual/reference/operator/query/ne/": "$ne",
                "https://www.mongodb.com/docs/manual/reference/operator/query/gt/": "$gt",
                "https://www.mongodb.com/docs/manual/reference/operator/query/gte/": "$gte",
                "https://www.mongodb.com/docs/manual/reference/operator/query/lt/": "$lt",
                "https://www.mongodb.com/docs/manual/reference/operator/query/lte/": "$lte",
                "https://www.mongodb.com/docs/manual/reference/operator/query/in/": "$in",
                "https://www.mongodb.com/docs/manual/reference/operator/query/nin/": "$nin",
                # Logical operators
                "https://www.mongodb.com/docs/manual/reference/operator/query/and/": "$and",
                "https://www.mongodb.com/docs/manual/reference/operator/query/or/": "$or",
                "https://www.mongodb.com/docs/manual/reference/operator/query/not/": "$not",
                "https://www.mongodb.com/docs/manual/reference/operator/query/nor/": "$nor",
                # Element operators
                "https://www.mongodb.com/docs/manual/reference/operator/query/exists/": "$exists",
                "https://www.mongodb.com/docs/manual/reference/operator/query/type/": "$type",
                # Evaluation operators
                "https://www.mongodb.com/docs/manual/reference/operator/query/regex/": "$regex",
                # Array operators
                "https://www.mongodb.com/docs/manual/reference/operator/query/elemMatch/": "$elemMatch",
                "https://www.mongodb.com/docs/manual/reference/operator/query/size/": "$size",
                "https://www.mongodb.com/docs/manual/reference/operator/query/all/": "$all",
                # Update operators
                "https://www.mongodb.com/docs/manual/reference/operator/update/": "Update Operators",
                "https://www.mongodb.com/docs/manual/reference/operator/update/set/": "$set",
                "https://www.mongodb.com/docs/manual/reference/operator/update/unset/": "$unset",
                "https://www.mongodb.com/docs/manual/reference/operator/update/inc/": "$inc",
                "https://www.mongodb.com/docs/manual/reference/operator/update/push/": "$push",
                "https://www.mongodb.com/docs/manual/reference/operator/update/pull/": "$pull",
                "https://www.mongodb.com/docs/manual/reference/operator/update/addToSet/": "$addToSet",
                "https://www.mongodb.com/docs/manual/reference/operator/update/rename/": "$rename",
                "https://www.mongodb.com/docs/manual/reference/operator/update/min/": "$min",
                "https://www.mongodb.com/docs/manual/reference/operator/update/max/": "$max",
                "https://www.mongodb.com/docs/manual/reference/operator/update/mul/": "$mul",
                "https://www.mongodb.com/docs/manual/reference/operator/update/currentDate/": "$currentDate",
                # Bulk operations
                "https://www.mongodb.com/docs/manual/core/bulk-write-operations/": "Bulk Write Operations",
                # Collection methods
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.find/": "find()",
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.insertOne/": "insertOne()",
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.insertMany/": "insertMany()",
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.updateOne/": "updateOne()",
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.updateMany/": "updateMany()",
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.deleteOne/": "deleteOne()",
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.deleteMany/": "deleteMany()",
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.replaceOne/": "replaceOne()",
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.findOneAndUpdate/": "findOneAndUpdate()",
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.findOneAndDelete/": "findOneAndDelete()",
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.findOneAndReplace/": "findOneAndReplace()",
            },
        },
        "aggregation": {
            "pages": {
                # Core aggregation
                "https://www.mongodb.com/docs/manual/aggregation/": "Aggregation Overview",
                "https://www.mongodb.com/docs/manual/core/aggregation-pipeline/": "Aggregation Pipeline",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation-pipeline/": "Pipeline Stages",
                # Pipeline stages
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/match/": "$match",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/group/": "$group",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/project/": "$project",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/sort/": "$sort",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/limit/": "$limit",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/skip/": "$skip",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/unwind/": "$unwind",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/lookup/": "$lookup",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/addFields/": "$addFields",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/set/": "$set (aggregation)",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/count/": "$count",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/out/": "$out",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/merge/": "$merge",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/bucket/": "$bucket",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/bucketAuto/": "$bucketAuto",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/facet/": "$facet",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/graphLookup/": "$graphLookup",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/replaceRoot/": "$replaceRoot",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/sample/": "$sample",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/redact/": "$redact",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/unionWith/": "$unionWith",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/setWindowFields/": "$setWindowFields",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/densify/": "$densify",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/fill/": "$fill",
                # Optimization and limits
                "https://www.mongodb.com/docs/manual/core/aggregation-pipeline-optimization/": "Pipeline Optimization",
                "https://www.mongodb.com/docs/manual/core/aggregation-pipeline-limits/": "Pipeline Limits",
                # Accumulator operators
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/sum/": "$sum",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/avg/": "$avg",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/min/": "$min (aggregation)",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/max/": "$max (aggregation)",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/first/": "$first",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/last/": "$last",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/push/": "$push (aggregation)",
            },
        },
        "data-modeling": {
            "pages": {
                "https://www.mongodb.com/docs/manual/core/data-modeling-introduction/": "Data Modeling Introduction",
                "https://www.mongodb.com/docs/manual/core/data-model-design/": "Data Model Design",
                "https://www.mongodb.com/docs/manual/core/schema-validation/": "Schema Validation",
                "https://www.mongodb.com/docs/manual/core/schema-validation/specify-json-schema/": "JSON Schema Validation",
                "https://www.mongodb.com/docs/manual/tutorial/model-embedded-one-to-one-relationships-between-documents/": "One-to-One Embedded",
                "https://www.mongodb.com/docs/manual/tutorial/model-embedded-one-to-many-relationships-between-documents/": "One-to-Many Embedded",
                "https://www.mongodb.com/docs/manual/tutorial/model-referenced-one-to-many-relationships-between-documents/": "One-to-Many Referenced",
                "https://www.mongodb.com/docs/manual/tutorial/model-tree-structures/": "Tree Structures",
                "https://www.mongodb.com/docs/manual/tutorial/model-tree-structures-with-parent-references/": "Parent References",
                "https://www.mongodb.com/docs/manual/tutorial/model-tree-structures-with-child-references/": "Child References",
                "https://www.mongodb.com/docs/manual/tutorial/model-tree-structures-with-materialized-paths/": "Materialized Paths",
                "https://www.mongodb.com/docs/manual/applications/data-models-relationships/": "Data Model Relationships",
                "https://www.mongodb.com/docs/manual/applications/data-models-tree-structures/": "Tree Structure Models",
                "https://www.mongodb.com/docs/manual/data-modeling/concepts/embedding-vs-references/": "Embedding vs References",
                "https://www.mongodb.com/docs/manual/core/timeseries-collections/": "Time Series Collections",
                "https://www.mongodb.com/docs/manual/core/timeseries/timeseries-procedures/": "Time Series Procedures",
                "https://www.mongodb.com/docs/manual/core/timeseries/timeseries-best-practices/": "Time Series Best Practices",
                "https://www.mongodb.com/docs/manual/tutorial/model-tree-structures-with-nested-sets/": "Nested Sets",
                "https://www.mongodb.com/docs/manual/tutorial/model-tree-structures-with-ancestors-array/": "Ancestors Array",
                "https://www.mongodb.com/docs/manual/core/data-model-operations/": "Data Model Operations",
                "https://www.mongodb.com/docs/manual/tutorial/model-data-for-atomic-operations/": "Atomic Operations",
                "https://www.mongodb.com/docs/manual/tutorial/model-data-for-keyword-search/": "Keyword Search Model",
                "https://www.mongodb.com/docs/manual/tutorial/model-monetary-data/": "Monetary Data",
                "https://www.mongodb.com/docs/manual/tutorial/model-time-data/": "Time Data",
                "https://www.mongodb.com/docs/manual/applications/data-models/": "Data Models Applications",
            },
        },
        "indexes": {
            "pages": {
                # Overview
                "https://www.mongodb.com/docs/manual/indexes/": "Indexes Overview",
                # Index types
                "https://www.mongodb.com/docs/manual/core/indexes/index-types/index-single/": "Single Field Index",
                "https://www.mongodb.com/docs/manual/core/indexes/index-types/index-compound/": "Compound Index",
                "https://www.mongodb.com/docs/manual/core/indexes/index-types/index-multikey/": "Multikey Index",
                "https://www.mongodb.com/docs/manual/core/indexes/index-types/index-text/": "Text Index",
                "https://www.mongodb.com/docs/manual/core/indexes/index-types/index-wildcard/": "Wildcard Index",
                "https://www.mongodb.com/docs/manual/core/indexes/index-types/index-hashed/": "Hashed Index",
                "https://www.mongodb.com/docs/manual/core/indexes/index-types/index-geospatial/2dsphere/": "2dsphere Index",
                "https://www.mongodb.com/docs/manual/core/indexes/index-types/index-geospatial/2d/": "2d Index",
                "https://www.mongodb.com/docs/manual/core/indexes/index-types/index-geospatial/": "Geospatial Indexes",
                # Index properties
                "https://www.mongodb.com/docs/manual/core/indexes/index-properties/index-unique/": "Unique Index",
                "https://www.mongodb.com/docs/manual/core/indexes/index-properties/index-partial/": "Partial Index",
                "https://www.mongodb.com/docs/manual/core/indexes/index-properties/index-sparse/": "Sparse Index",
                "https://www.mongodb.com/docs/manual/core/indexes/index-properties/index-ttl/": "TTL Index",
                "https://www.mongodb.com/docs/manual/core/indexes/index-properties/index-hidden/": "Hidden Index",
                "https://www.mongodb.com/docs/manual/core/indexes/index-properties/index-case-insensitive/": "Case-Insensitive Index",
                # Management
                "https://www.mongodb.com/docs/manual/tutorial/manage-indexes/": "Manage Indexes",
                "https://www.mongodb.com/docs/manual/tutorial/measure-index-use/": "Measure Index Use",
                "https://www.mongodb.com/docs/manual/applications/indexes/": "Indexing Strategies",
                "https://www.mongodb.com/docs/manual/tutorial/sort-results-with-indexes/": "Sort with Indexes",
                "https://www.mongodb.com/docs/manual/tutorial/create-indexes-to-support-queries/": "Create Indexes for Queries",
                "https://www.mongodb.com/docs/manual/core/index-intersection/": "Index Intersection",
                # Methods
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.createIndex/": "createIndex()",
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.getIndexes/": "getIndexes()",
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.dropIndex/": "dropIndex()",
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.dropIndexes/": "dropIndexes()",
                "https://www.mongodb.com/docs/manual/tutorial/ensure-indexes-fit-ram/": "Indexes Fit RAM",
                "https://www.mongodb.com/docs/manual/core/index-creation/": "Index Creation",
                "https://www.mongodb.com/docs/manual/tutorial/avoid-text-index-name-limit/": "Text Index Name Limit",
                "https://www.mongodb.com/docs/manual/tutorial/control-results-of-text-search/": "Control Text Search Results",
            },
        },
        "security": {
            "pages": {
                "https://www.mongodb.com/docs/manual/security/": "Security Overview",
                "https://www.mongodb.com/docs/manual/core/authentication/": "Authentication",
                "https://www.mongodb.com/docs/manual/core/authorization/": "Authorization",
                "https://www.mongodb.com/docs/manual/core/security-scram/": "SCRAM Authentication",
                "https://www.mongodb.com/docs/manual/core/security-x.509/": "x.509 Authentication",
                "https://www.mongodb.com/docs/manual/core/security-ldap/": "LDAP Authentication",
                "https://www.mongodb.com/docs/manual/core/security-users/": "Users",
                "https://www.mongodb.com/docs/manual/reference/built-in-roles/": "Built-in Roles",
                "https://www.mongodb.com/docs/manual/core/security-built-in-roles/": "Security Roles",
                "https://www.mongodb.com/docs/manual/tutorial/create-users/": "Create Users",
                "https://www.mongodb.com/docs/manual/tutorial/manage-users-and-roles/": "Manage Users and Roles",
                "https://www.mongodb.com/docs/manual/core/security-encryption-at-rest/": "Encryption at Rest",
                "https://www.mongodb.com/docs/manual/core/security-client-side-encryption/": "Client-Side Encryption",
                "https://www.mongodb.com/docs/manual/core/security-transport-encryption/": "TLS/SSL Transport Encryption",
                "https://www.mongodb.com/docs/manual/tutorial/configure-ssl/": "Configure TLS/SSL",
                "https://www.mongodb.com/docs/manual/core/auditing/": "Auditing",
                "https://www.mongodb.com/docs/manual/administration/security-checklist/": "Security Checklist",
                "https://www.mongodb.com/docs/manual/core/network-encryption/": "Network Encryption",
                "https://www.mongodb.com/docs/manual/tutorial/enable-authentication/": "Enable Authentication",
                "https://www.mongodb.com/docs/manual/core/security-internal-authentication/": "Internal Authentication",
                "https://www.mongodb.com/docs/manual/tutorial/configure-ldap-sasl-activedirectory/": "LDAP SASL Active Directory",
                "https://www.mongodb.com/docs/manual/core/security-automatic-client-side-encryption/": "Automatic Client-Side Encryption",
                "https://www.mongodb.com/docs/manual/reference/security/": "Security Reference",
                "https://www.mongodb.com/docs/manual/tutorial/rotate-encryption-key/": "Rotate Encryption Key",
                "https://www.mongodb.com/docs/manual/core/collection-level-access-control/": "Collection-Level Access",
            },
        },
        "replication": {
            "pages": {
                "https://www.mongodb.com/docs/manual/replication/": "Replication Overview",
                "https://www.mongodb.com/docs/manual/core/replica-set-members/": "Replica Set Members",
                "https://www.mongodb.com/docs/manual/core/replica-set-primary/": "Primary",
                "https://www.mongodb.com/docs/manual/core/replica-set-secondary/": "Secondary",
                "https://www.mongodb.com/docs/manual/core/replica-set-arbiter/": "Arbiter",
                "https://www.mongodb.com/docs/manual/core/replica-set-elections/": "Elections",
                "https://www.mongodb.com/docs/manual/core/read-preference/": "Read Preference",
                "https://www.mongodb.com/docs/manual/core/replica-set-oplog/": "Oplog",
                "https://www.mongodb.com/docs/manual/core/replica-set-sync/": "Sync",
                "https://www.mongodb.com/docs/manual/tutorial/deploy-replica-set/": "Deploy Replica Set",
                "https://www.mongodb.com/docs/manual/tutorial/add-replica-set-arbiter/": "Add Arbiter",
                "https://www.mongodb.com/docs/manual/tutorial/expand-replica-set/": "Expand Replica Set",
                "https://www.mongodb.com/docs/manual/tutorial/remove-replica-set-member/": "Remove Member",
                "https://www.mongodb.com/docs/manual/tutorial/configure-replica-set-tag-sets/": "Tag Sets",
                "https://www.mongodb.com/docs/manual/core/replica-set-high-availability/": "High Availability",
                "https://www.mongodb.com/docs/manual/core/replica-set-rollbacks/": "Rollbacks",
                "https://www.mongodb.com/docs/manual/reference/write-concern/": "Write Concern",
                "https://www.mongodb.com/docs/manual/reference/read-concern/": "Read Concern",
                "https://www.mongodb.com/docs/manual/core/replica-set-delayed-member/": "Delayed Member",
                "https://www.mongodb.com/docs/manual/core/replica-set-hidden-member/": "Hidden Member",
                "https://www.mongodb.com/docs/manual/core/replica-set-priority-0-member/": "Priority-0 Member",
                "https://www.mongodb.com/docs/manual/tutorial/configure-replica-set-secondary-sync-target/": "Secondary Sync Target",
                "https://www.mongodb.com/docs/manual/tutorial/force-member-to-be-primary/": "Force Primary",
                "https://www.mongodb.com/docs/manual/tutorial/resync-replica-set-member/": "Resync Member",
                "https://www.mongodb.com/docs/manual/reference/replica-configuration/": "Replica Configuration",
            },
        },
        "sharding": {
            "pages": {
                "https://www.mongodb.com/docs/manual/sharding/": "Sharding Overview",
                "https://www.mongodb.com/docs/manual/core/sharded-cluster-components/": "Sharded Cluster Components",
                "https://www.mongodb.com/docs/manual/core/sharding-shard-key/": "Shard Key",
                "https://www.mongodb.com/docs/manual/core/hashed-sharding/": "Hashed Sharding",
                "https://www.mongodb.com/docs/manual/core/ranged-sharding/": "Ranged Sharding",
                "https://www.mongodb.com/docs/manual/core/zone-sharding/": "Zone Sharding",
                "https://www.mongodb.com/docs/manual/core/sharding-balancer-administration/": "Balancer Administration",
                "https://www.mongodb.com/docs/manual/core/sharding-data-partitioning/": "Data Partitioning",
                "https://www.mongodb.com/docs/manual/tutorial/deploy-shard-cluster/": "Deploy Sharded Cluster",
                "https://www.mongodb.com/docs/manual/tutorial/shard-collection-with-hashed-shard-key/": "Shard with Hashed Key",
                "https://www.mongodb.com/docs/manual/tutorial/shard-collection-with-ranged-shard-key/": "Shard with Ranged Key",
                "https://www.mongodb.com/docs/manual/tutorial/choose-a-shard-key/": "Choose Shard Key",
                "https://www.mongodb.com/docs/manual/core/sharding-chunk-migration/": "Chunk Migration",
                "https://www.mongodb.com/docs/manual/core/sharding-chunk-splitting/": "Chunk Splitting",
                "https://www.mongodb.com/docs/manual/reference/method/sh.shardCollection/": "shardCollection()",
                "https://www.mongodb.com/docs/manual/reference/method/sh.status/": "sh.status()",
                "https://www.mongodb.com/docs/manual/core/sharded-cluster-query-router/": "mongos Query Router",
                "https://www.mongodb.com/docs/manual/core/sharded-cluster-config-servers/": "Config Servers",
                "https://www.mongodb.com/docs/manual/tutorial/add-shards-to-shard-cluster/": "Add Shards",
                "https://www.mongodb.com/docs/manual/tutorial/remove-shards-from-cluster/": "Remove Shards",
                "https://www.mongodb.com/docs/manual/tutorial/manage-shard-zone/": "Manage Shard Zones",
                "https://www.mongodb.com/docs/manual/tutorial/migrate-chunks-in-sharded-cluster/": "Migrate Chunks",
                "https://www.mongodb.com/docs/manual/reference/method/sh.addShard/": "sh.addShard()",
                "https://www.mongodb.com/docs/manual/reference/method/sh.enableSharding/": "sh.enableSharding()",
                "https://www.mongodb.com/docs/manual/core/sharding-change-a-shard-key/": "Change Shard Key",
            },
        },
        "administration": {
            "pages": {
                "https://www.mongodb.com/docs/manual/administration/": "Administration Overview",
                "https://www.mongodb.com/docs/manual/administration/production-notes/": "Production Notes",
                "https://www.mongodb.com/docs/manual/administration/production-checklist-operations/": "Operations Checklist",
                "https://www.mongodb.com/docs/manual/tutorial/manage-mongodb-processes/": "Manage Processes",
                "https://www.mongodb.com/docs/manual/tutorial/rotate-log-files/": "Rotate Log Files",
                "https://www.mongodb.com/docs/manual/reference/configuration-options/": "Configuration Options",
                # Programs
                "https://www.mongodb.com/docs/manual/reference/program/mongod/": "mongod",
                "https://www.mongodb.com/docs/manual/reference/program/mongos/": "mongos",
                "https://www.mongodb.com/docs/manual/reference/program/mongosh/": "mongosh",
                "https://www.mongodb.com/docs/manual/reference/program/mongodump/": "mongodump",
                "https://www.mongodb.com/docs/manual/reference/program/mongorestore/": "mongorestore",
                "https://www.mongodb.com/docs/manual/reference/program/mongoexport/": "mongoexport",
                "https://www.mongodb.com/docs/manual/reference/program/mongoimport/": "mongoimport",
                "https://www.mongodb.com/docs/manual/reference/program/mongostat/": "mongostat",
                "https://www.mongodb.com/docs/manual/reference/program/mongotop/": "mongotop",
                # Backup and monitoring
                "https://www.mongodb.com/docs/manual/tutorial/backup-and-restore-tools/": "Backup and Restore Tools",
                "https://www.mongodb.com/docs/manual/core/backups/": "Backups",
                "https://www.mongodb.com/docs/manual/administration/monitoring/": "Monitoring",
                # References
                "https://www.mongodb.com/docs/manual/reference/command/": "Database Commands",
                "https://www.mongodb.com/docs/manual/reference/method/": "Shell Methods",
                # Additional admin
                "https://www.mongodb.com/docs/manual/tutorial/transparent-huge-pages/": "Transparent Huge Pages",
                "https://www.mongodb.com/docs/manual/tutorial/manage-the-database-profiler/": "Database Profiler",
                "https://www.mongodb.com/docs/manual/reference/command/serverStatus/": "serverStatus",
                "https://www.mongodb.com/docs/manual/reference/command/dbStats/": "dbStats",
                "https://www.mongodb.com/docs/manual/reference/command/collStats/": "collStats",
                "https://www.mongodb.com/docs/manual/reference/command/connPoolStats/": "connPoolStats",
                "https://www.mongodb.com/docs/manual/reference/command/currentOp/": "currentOp",
                "https://www.mongodb.com/docs/manual/reference/command/killOp/": "killOp",
                "https://www.mongodb.com/docs/manual/reference/command/compact/": "compact",
                "https://www.mongodb.com/docs/manual/reference/command/validate/": "validate",
                "https://www.mongodb.com/docs/manual/reference/command/reIndex/": "reIndex",
            },
        },
        "storage": {
            "pages": {
                "https://www.mongodb.com/docs/manual/core/wiredtiger/": "WiredTiger Storage Engine",
                "https://www.mongodb.com/docs/manual/core/journaling/": "Journaling",
                "https://www.mongodb.com/docs/manual/core/gridfs/": "GridFS",
                "https://www.mongodb.com/docs/manual/reference/bson-types/": "BSON Types",
                "https://www.mongodb.com/docs/manual/reference/limits/": "MongoDB Limits",
                "https://www.mongodb.com/docs/manual/core/capped-collections/": "Capped Collections",
                "https://www.mongodb.com/docs/manual/core/views/": "Views",
                "https://www.mongodb.com/docs/manual/core/materialized-views/": "Materialized Views",
                "https://www.mongodb.com/docs/manual/reference/bson-type-comparison-order/": "BSON Comparison Order",
                "https://www.mongodb.com/docs/manual/core/wiredtiger/wiredtiger-memory-use/": "WiredTiger Memory Use",
                "https://www.mongodb.com/docs/manual/tutorial/manage-journaling/": "Manage Journaling",
                "https://www.mongodb.com/docs/manual/reference/object-id/": "ObjectId",
                "https://www.mongodb.com/docs/manual/reference/mongodb-extended-json/": "Extended JSON",
                "https://www.mongodb.com/docs/manual/tutorial/store-javascript-function-on-server/": "Server-Side JavaScript",
                "https://www.mongodb.com/docs/manual/core/collection-level-access-control/": "Collection-Level Access Control",
            },
        },
        "transactions": {
            "pages": {
                "https://www.mongodb.com/docs/manual/core/transactions/": "Transactions Overview",
                "https://www.mongodb.com/docs/manual/core/transactions-in-applications/": "Transactions in Applications",
                "https://www.mongodb.com/docs/manual/core/transactions-production-consideration/": "Production Considerations",
                "https://www.mongodb.com/docs/manual/core/transactions-sharded-clusters/": "Sharded Cluster Transactions",
                "https://www.mongodb.com/docs/manual/reference/method/Session.startTransaction/": "startTransaction()",
                "https://www.mongodb.com/docs/manual/reference/method/Session.commitTransaction/": "commitTransaction()",
                "https://www.mongodb.com/docs/manual/reference/method/Session.abortTransaction/": "abortTransaction()",
                "https://www.mongodb.com/docs/manual/core/transactions-operations/": "Transaction Operations",
                "https://www.mongodb.com/docs/manual/reference/read-concern-snapshot/": "Read Concern Snapshot",
                "https://www.mongodb.com/docs/manual/reference/read-concern-majority/": "Read Concern Majority",
                "https://www.mongodb.com/docs/manual/reference/read-concern-local/": "Read Concern Local",
                "https://www.mongodb.com/docs/manual/reference/write-concern/": "Write Concern Reference",
                "https://www.mongodb.com/docs/manual/core/causal-consistency-read-write-concerns/": "Causal Consistency",
                "https://www.mongodb.com/docs/manual/reference/method/Session/": "Session",
                "https://www.mongodb.com/docs/manual/reference/method/Session.endSession/": "endSession()",
            },
        },
        "change-streams": {
            "pages": {
                "https://www.mongodb.com/docs/manual/changeStreams/": "Change Streams Overview",
                "https://www.mongodb.com/docs/manual/reference/change-events/": "Change Events",
                "https://www.mongodb.com/docs/manual/administration/change-streams-production-recommendations/": "Production Recommendations",
                "https://www.mongodb.com/docs/manual/reference/change-events/insert/": "Insert Event",
                "https://www.mongodb.com/docs/manual/reference/change-events/update/": "Update Event",
                "https://www.mongodb.com/docs/manual/reference/change-events/replace/": "Replace Event",
                "https://www.mongodb.com/docs/manual/reference/change-events/delete/": "Delete Event",
                "https://www.mongodb.com/docs/manual/reference/change-events/drop/": "Drop Event",
                "https://www.mongodb.com/docs/manual/reference/change-events/invalidate/": "Invalidate Event",
                "https://www.mongodb.com/docs/manual/reference/method/db.collection.watch/": "watch()",
            },
        },
        "text-search": {
            "pages": {
                "https://www.mongodb.com/docs/manual/text-search/": "Text Search Overview",
                "https://www.mongodb.com/docs/manual/core/text-search-operators/": "Text Search Operators",
                "https://www.mongodb.com/docs/manual/tutorial/text-search-in-aggregation/": "Text Search in Aggregation",
                "https://www.mongodb.com/docs/manual/reference/operator/query/text/": "$text Operator",
                "https://www.mongodb.com/docs/manual/reference/operator/query/meta/": "$meta Operator",
                "https://www.mongodb.com/docs/manual/core/link-text-index/": "Text Index",
                "https://www.mongodb.com/docs/manual/tutorial/specify-language-for-text-index/": "Specify Language",
                "https://www.mongodb.com/docs/manual/tutorial/create-text-index-on-multiple-fields/": "Multi-Field Text Index",
                "https://www.mongodb.com/docs/manual/reference/text-search-languages/": "Text Search Languages",
                "https://www.mongodb.com/docs/manual/tutorial/text-search-with-rlp/": "Text Search with RLP",
            },
        },
        "geospatial": {
            "pages": {
                "https://www.mongodb.com/docs/manual/geospatial-queries/": "Geospatial Queries Overview",
                "https://www.mongodb.com/docs/manual/reference/geojson/": "GeoJSON Objects",
                "https://www.mongodb.com/docs/manual/reference/operator/query/near/": "$near",
                "https://www.mongodb.com/docs/manual/reference/operator/query/nearSphere/": "$nearSphere",
                "https://www.mongodb.com/docs/manual/reference/operator/query/geoWithin/": "$geoWithin",
                "https://www.mongodb.com/docs/manual/reference/operator/query/geoIntersects/": "$geoIntersects",
                "https://www.mongodb.com/docs/manual/reference/operator/aggregation/geoNear/": "$geoNear (aggregation)",
                "https://www.mongodb.com/docs/manual/tutorial/geospatial-tutorial/": "Geospatial Tutorial",
                "https://www.mongodb.com/docs/manual/tutorial/calculate-distances-using-spherical-geometry-with-2d-geospatial-indexes/": "Calculate Distances",
                "https://www.mongodb.com/docs/manual/reference/operator/query/center/": "$center",
                "https://www.mongodb.com/docs/manual/reference/operator/query/centerSphere/": "$centerSphere",
                "https://www.mongodb.com/docs/manual/reference/operator/query/box/": "$box",
                "https://www.mongodb.com/docs/manual/reference/operator/query/polygon/": "$polygon",
                "https://www.mongodb.com/docs/manual/reference/operator/query/geometry/": "$geometry",
                "https://www.mongodb.com/docs/manual/reference/operator/query/maxDistance/": "$maxDistance",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"mongodb-{source_key}" if source_key else "mongodb"
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
            for suffix in [' — MongoDB Manual', ' - MongoDB Manual', ' | MongoDB']:
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
                        "category": f"mongodb-{source_key}",
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
            self.log.info(f"=== Scraping mongodb/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    MongoDBScraper(base, source_key).run()
