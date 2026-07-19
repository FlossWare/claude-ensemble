#!/usr/bin/env python3
"""Apache Kafka documentation scraper.

Covers:
  - Kafka core documentation (getting started, design, operations)
  - Kafka APIs (producer, consumer, streams, connect, admin)
  - Kafka configuration (broker, topic, producer, consumer)
  - Kafka Streams (concepts, architecture, developer guide)
  - Kafka Connect (concepts, transforms, converters)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class KafkaScraper(BaseScraper):
    """Scrape Apache Kafka documentation, APIs, and guides."""

    SOURCES = {
        "getting-started": {
            "pages": {
                "https://kafka.apache.org/documentation/": "Kafka Documentation",
                "https://kafka.apache.org/intro": "Introduction to Kafka",
                "https://kafka.apache.org/quickstart": "Kafka Quickstart",
                "https://kafka.apache.org/uses": "Use Cases",
                "https://kafka.apache.org/powered-by": "Powered By",
                "https://kafka.apache.org/books-and-papers": "Books and Papers",
                "https://kafka.apache.org/events": "Events",
                "https://kafka.apache.org/contact": "Contact",
                "https://kafka.apache.org/downloads": "Downloads",
                "https://kafka.apache.org/documentation/#gettingStarted": "Getting Started",
                "https://kafka.apache.org/documentation/#introduction": "Introduction",
                "https://kafka.apache.org/documentation/#quickstart": "Quickstart Guide",
                "https://kafka.apache.org/documentation/#upgrade": "Upgrading",
                "https://kafka.apache.org/documentation/#majorversion_upgrade": "Major Version Upgrade",
            },
        },
        "apis-producer": {
            "pages": {
                "https://kafka.apache.org/documentation/#producerapi": "Producer API",
                "https://kafka.apache.org/documentation/#theproducer": "The Producer",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/producer/KafkaProducer.html": "KafkaProducer",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/producer/ProducerRecord.html": "ProducerRecord",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/producer/RecordMetadata.html": "RecordMetadata",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/producer/Callback.html": "Producer Callback",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/producer/Partitioner.html": "Partitioner",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/producer/ProducerConfig.html": "ProducerConfig",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/producer/ProducerInterceptor.html": "ProducerInterceptor",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/producer/MockProducer.html": "MockProducer",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/common/serialization/Serializer.html": "Serializer",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/common/serialization/StringSerializer.html": "StringSerializer",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/common/serialization/ByteArraySerializer.html": "ByteArraySerializer",
            },
        },
        "apis-consumer": {
            "pages": {
                "https://kafka.apache.org/documentation/#consumerapi": "Consumer API",
                "https://kafka.apache.org/documentation/#theconsumer": "The Consumer",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/consumer/KafkaConsumer.html": "KafkaConsumer",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/consumer/ConsumerRecord.html": "ConsumerRecord",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/consumer/ConsumerRecords.html": "ConsumerRecords",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/consumer/ConsumerConfig.html": "ConsumerConfig",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/consumer/ConsumerRebalanceListener.html": "ConsumerRebalanceListener",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/consumer/ConsumerInterceptor.html": "ConsumerInterceptor",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/consumer/OffsetAndMetadata.html": "OffsetAndMetadata",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/consumer/OffsetCommitCallback.html": "OffsetCommitCallback",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/consumer/MockConsumer.html": "MockConsumer",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/common/serialization/Deserializer.html": "Deserializer",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/common/serialization/StringDeserializer.html": "StringDeserializer",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/consumer/CooperativeStickyAssignor.html": "CooperativeStickyAssignor",
            },
        },
        "apis-streams": {
            "pages": {
                "https://kafka.apache.org/documentation/#streamsapi": "Streams API",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/KafkaStreams.html": "KafkaStreams",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/StreamsBuilder.html": "StreamsBuilder",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/StreamsConfig.html": "StreamsConfig",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/Topology.html": "Topology",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/KStream.html": "KStream",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/KTable.html": "KTable",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/GlobalKTable.html": "GlobalKTable",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/KGroupedStream.html": "KGroupedStream",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/KGroupedTable.html": "KGroupedTable",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/Consumed.html": "Consumed",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/Produced.html": "Produced",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/Materialized.html": "Materialized",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/Joined.html": "Joined",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/Grouped.html": "Grouped",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/Branched.html": "Branched",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/Repartitioned.html": "Repartitioned",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/TimeWindows.html": "TimeWindows",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/SessionWindows.html": "SessionWindows",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/SlidingWindows.html": "SlidingWindows",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/kstream/JoinWindows.html": "JoinWindows",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/state/KeyValueStore.html": "KeyValueStore",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/state/WindowStore.html": "WindowStore",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/state/SessionStore.html": "SessionStore",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/processor/api/Processor.html": "Processor",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/processor/api/ProcessorContext.html": "ProcessorContext",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/errors/StreamsUncaughtExceptionHandler.html": "StreamsUncaughtExceptionHandler",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/streams/TopologyTestDriver.html": "TopologyTestDriver",
            },
        },
        "apis-connect": {
            "pages": {
                "https://kafka.apache.org/documentation/#connectapi": "Connect API",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/connect/connector/Connector.html": "Connector",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/connect/source/SourceConnector.html": "SourceConnector",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/connect/sink/SinkConnector.html": "SinkConnector",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/connect/source/SourceTask.html": "SourceTask",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/connect/sink/SinkTask.html": "SinkTask",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/connect/data/Schema.html": "Connect Schema",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/connect/data/SchemaBuilder.html": "SchemaBuilder",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/connect/data/Struct.html": "Struct",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/connect/transforms/Transformation.html": "Transformation",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/connect/connector/ConnectorContext.html": "ConnectorContext",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/connect/header/Header.html": "Connect Header",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/connect/header/Headers.html": "Connect Headers",
            },
        },
        "apis-admin": {
            "pages": {
                "https://kafka.apache.org/documentation/#adminapi": "Admin API",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/admin/Admin.html": "Admin",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/admin/AdminClient.html": "AdminClient",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/admin/AdminClientConfig.html": "AdminClientConfig",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/admin/NewTopic.html": "NewTopic",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/admin/TopicDescription.html": "TopicDescription",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/admin/TopicListing.html": "TopicListing",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/admin/ConsumerGroupDescription.html": "ConsumerGroupDescription",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/admin/ConsumerGroupListing.html": "ConsumerGroupListing",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/admin/DescribeClusterResult.html": "DescribeClusterResult",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/admin/AlterConfigsResult.html": "AlterConfigsResult",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/admin/CreateTopicsResult.html": "CreateTopicsResult",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/admin/DeleteTopicsResult.html": "DeleteTopicsResult",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/admin/ListOffsetsResult.html": "ListOffsetsResult",
                "https://kafka.apache.org/38/javadoc/org/apache/kafka/clients/admin/ListConsumerGroupOffsetsResult.html": "ListConsumerGroupOffsetsResult",
            },
        },
        "configuration-broker": {
            "pages": {
                "https://kafka.apache.org/documentation/#brokerconfigs": "Broker Configs",
                "https://kafka.apache.org/documentation/#brokerconfigs_broker.id": "broker.id",
                "https://kafka.apache.org/documentation/#brokerconfigs_listeners": "listeners",
                "https://kafka.apache.org/documentation/#brokerconfigs_log.dirs": "log.dirs",
                "https://kafka.apache.org/documentation/#brokerconfigs_zookeeper.connect": "zookeeper.connect",
                "https://kafka.apache.org/documentation/#brokerconfigs_num.network.threads": "num.network.threads",
                "https://kafka.apache.org/documentation/#brokerconfigs_num.io.threads": "num.io.threads",
                "https://kafka.apache.org/documentation/#brokerconfigs_socket.send.buffer.bytes": "socket.send.buffer.bytes",
                "https://kafka.apache.org/documentation/#brokerconfigs_socket.receive.buffer.bytes": "socket.receive.buffer.bytes",
                "https://kafka.apache.org/documentation/#brokerconfigs_socket.request.max.bytes": "socket.request.max.bytes",
                "https://kafka.apache.org/documentation/#brokerconfigs_num.partitions": "num.partitions",
                "https://kafka.apache.org/documentation/#brokerconfigs_log.retention.hours": "log.retention.hours",
                "https://kafka.apache.org/documentation/#brokerconfigs_log.retention.bytes": "log.retention.bytes",
                "https://kafka.apache.org/documentation/#brokerconfigs_log.segment.bytes": "log.segment.bytes",
                "https://kafka.apache.org/documentation/#brokerconfigs_log.cleanup.policy": "log.cleanup.policy",
                "https://kafka.apache.org/documentation/#brokerconfigs_auto.create.topics.enable": "auto.create.topics.enable",
                "https://kafka.apache.org/documentation/#brokerconfigs_default.replication.factor": "default.replication.factor",
                "https://kafka.apache.org/documentation/#brokerconfigs_min.insync.replicas": "min.insync.replicas",
                "https://kafka.apache.org/documentation/#brokerconfigs_unclean.leader.election.enable": "unclean.leader.election.enable",
                "https://kafka.apache.org/documentation/#brokerconfigs_message.max.bytes": "message.max.bytes",
                "https://kafka.apache.org/documentation/#brokerconfigs_compression.type": "compression.type",
            },
        },
        "configuration-topic": {
            "pages": {
                "https://kafka.apache.org/documentation/#topicconfigs": "Topic Configs",
                "https://kafka.apache.org/documentation/#topicconfigs_cleanup.policy": "cleanup.policy",
                "https://kafka.apache.org/documentation/#topicconfigs_compression.type": "topic compression.type",
                "https://kafka.apache.org/documentation/#topicconfigs_retention.ms": "retention.ms",
                "https://kafka.apache.org/documentation/#topicconfigs_retention.bytes": "retention.bytes",
                "https://kafka.apache.org/documentation/#topicconfigs_max.message.bytes": "max.message.bytes",
                "https://kafka.apache.org/documentation/#topicconfigs_min.insync.replicas": "topic min.insync.replicas",
                "https://kafka.apache.org/documentation/#topicconfigs_segment.bytes": "segment.bytes",
                "https://kafka.apache.org/documentation/#topicconfigs_segment.ms": "segment.ms",
                "https://kafka.apache.org/documentation/#topicconfigs_delete.retention.ms": "delete.retention.ms",
                "https://kafka.apache.org/documentation/#topicconfigs_min.compaction.lag.ms": "min.compaction.lag.ms",
                "https://kafka.apache.org/documentation/#topicconfigs_max.compaction.lag.ms": "max.compaction.lag.ms",
            },
        },
        "configuration-producer": {
            "pages": {
                "https://kafka.apache.org/documentation/#producerconfigs": "Producer Configs",
                "https://kafka.apache.org/documentation/#producerconfigs_bootstrap.servers": "producer bootstrap.servers",
                "https://kafka.apache.org/documentation/#producerconfigs_key.serializer": "key.serializer",
                "https://kafka.apache.org/documentation/#producerconfigs_value.serializer": "value.serializer",
                "https://kafka.apache.org/documentation/#producerconfigs_acks": "acks",
                "https://kafka.apache.org/documentation/#producerconfigs_retries": "producer retries",
                "https://kafka.apache.org/documentation/#producerconfigs_batch.size": "batch.size",
                "https://kafka.apache.org/documentation/#producerconfigs_linger.ms": "linger.ms",
                "https://kafka.apache.org/documentation/#producerconfigs_buffer.memory": "buffer.memory",
                "https://kafka.apache.org/documentation/#producerconfigs_max.block.ms": "max.block.ms",
                "https://kafka.apache.org/documentation/#producerconfigs_max.request.size": "max.request.size",
                "https://kafka.apache.org/documentation/#producerconfigs_compression.type": "producer compression.type",
                "https://kafka.apache.org/documentation/#producerconfigs_enable.idempotence": "enable.idempotence",
                "https://kafka.apache.org/documentation/#producerconfigs_transactional.id": "transactional.id",
                "https://kafka.apache.org/documentation/#producerconfigs_delivery.timeout.ms": "delivery.timeout.ms",
            },
        },
        "configuration-consumer": {
            "pages": {
                "https://kafka.apache.org/documentation/#consumerconfigs": "Consumer Configs",
                "https://kafka.apache.org/documentation/#consumerconfigs_bootstrap.servers": "consumer bootstrap.servers",
                "https://kafka.apache.org/documentation/#consumerconfigs_group.id": "group.id",
                "https://kafka.apache.org/documentation/#consumerconfigs_key.deserializer": "key.deserializer",
                "https://kafka.apache.org/documentation/#consumerconfigs_value.deserializer": "value.deserializer",
                "https://kafka.apache.org/documentation/#consumerconfigs_auto.offset.reset": "auto.offset.reset",
                "https://kafka.apache.org/documentation/#consumerconfigs_enable.auto.commit": "enable.auto.commit",
                "https://kafka.apache.org/documentation/#consumerconfigs_auto.commit.interval.ms": "auto.commit.interval.ms",
                "https://kafka.apache.org/documentation/#consumerconfigs_max.poll.records": "max.poll.records",
                "https://kafka.apache.org/documentation/#consumerconfigs_max.poll.interval.ms": "max.poll.interval.ms",
                "https://kafka.apache.org/documentation/#consumerconfigs_session.timeout.ms": "session.timeout.ms",
                "https://kafka.apache.org/documentation/#consumerconfigs_heartbeat.interval.ms": "heartbeat.interval.ms",
                "https://kafka.apache.org/documentation/#consumerconfigs_fetch.min.bytes": "fetch.min.bytes",
                "https://kafka.apache.org/documentation/#consumerconfigs_fetch.max.bytes": "fetch.max.bytes",
                "https://kafka.apache.org/documentation/#consumerconfigs_fetch.max.wait.ms": "fetch.max.wait.ms",
                "https://kafka.apache.org/documentation/#consumerconfigs_partition.assignment.strategy": "partition.assignment.strategy",
                "https://kafka.apache.org/documentation/#consumerconfigs_isolation.level": "isolation.level",
                "https://kafka.apache.org/documentation/#consumerconfigs_group.instance.id": "group.instance.id",
            },
        },
        "design-motivation": {
            "pages": {
                "https://kafka.apache.org/documentation/#design": "Design",
                "https://kafka.apache.org/documentation/#majordesignelements": "Major Design Elements",
                "https://kafka.apache.org/documentation/#design_motivation": "Motivation",
            },
        },
        "design-persistence": {
            "pages": {
                "https://kafka.apache.org/documentation/#design_persistence": "Persistence",
                "https://kafka.apache.org/documentation/#design_filesystem": "Don't Fear the Filesystem",
                "https://kafka.apache.org/documentation/#design_constanttime": "Constant Time Suffices",
            },
        },
        "design-efficiency": {
            "pages": {
                "https://kafka.apache.org/documentation/#design_efficiency": "Efficiency",
                "https://kafka.apache.org/documentation/#design_end_to_end_compression": "End-to-End Batch Compression",
            },
        },
        "design-producer": {
            "pages": {
                "https://kafka.apache.org/documentation/#design_producer": "The Producer Design",
                "https://kafka.apache.org/documentation/#design_loadbalancing": "Load Balancing",
                "https://kafka.apache.org/documentation/#design_asyncsend": "Asynchronous Send",
            },
        },
        "design-consumer": {
            "pages": {
                "https://kafka.apache.org/documentation/#design_consumer": "The Consumer Design",
                "https://kafka.apache.org/documentation/#design_pull": "Push vs. Pull",
                "https://kafka.apache.org/documentation/#design_consumerposition": "Consumer Position",
                "https://kafka.apache.org/documentation/#design_offlineprocessing": "Offline Data Load",
                "https://kafka.apache.org/documentation/#design_staticmembership": "Static Membership",
            },
        },
        "design-replication": {
            "pages": {
                "https://kafka.apache.org/documentation/#replication": "Replication",
                "https://kafka.apache.org/documentation/#design_replicatedlog": "Replicated Logs",
                "https://kafka.apache.org/documentation/#design_uncleanleader": "Unclean Leader Election",
                "https://kafka.apache.org/documentation/#design_ha": "Availability and Durability Guarantees",
                "https://kafka.apache.org/documentation/#design_replicaquotas": "Replica Management",
            },
        },
        "design-log-compaction": {
            "pages": {
                "https://kafka.apache.org/documentation/#compaction": "Log Compaction",
                "https://kafka.apache.org/documentation/#design_compactionbasics": "Log Compaction Basics",
                "https://kafka.apache.org/documentation/#design_compactionguarantees": "Compaction Guarantees",
                "https://kafka.apache.org/documentation/#design_compactiondetails": "Log Compaction Details",
            },
        },
        "operations-deployment": {
            "pages": {
                "https://kafka.apache.org/documentation/#operations": "Operations",
                "https://kafka.apache.org/documentation/#basic_ops": "Basic Kafka Operations",
                "https://kafka.apache.org/documentation/#basic_ops_add_topic": "Adding Topics",
                "https://kafka.apache.org/documentation/#basic_ops_modify_topic": "Modifying Topics",
                "https://kafka.apache.org/documentation/#basic_ops_graceful_shutdown": "Graceful Shutdown",
                "https://kafka.apache.org/documentation/#basic_ops_leader_balancing": "Balancing Leadership",
                "https://kafka.apache.org/documentation/#basic_ops_consumer_group": "Checking Consumer Position",
                "https://kafka.apache.org/documentation/#basic_ops_mirror_maker": "Mirroring Data Between Clusters",
                "https://kafka.apache.org/documentation/#basic_ops_cluster_expansion": "Expanding Your Cluster",
                "https://kafka.apache.org/documentation/#basic_ops_decommissioning_brokers": "Decommissioning Brokers",
                "https://kafka.apache.org/documentation/#basic_ops_increase_replication_factor": "Increasing Replication Factor",
                "https://kafka.apache.org/documentation/#config": "Important Server Configs",
                "https://kafka.apache.org/documentation/#java": "Java Version",
                "https://kafka.apache.org/documentation/#hwandos": "Hardware and OS",
                "https://kafka.apache.org/documentation/#os": "OS",
                "https://kafka.apache.org/documentation/#diskandfs": "Disks and Filesystem",
            },
        },
        "operations-monitoring": {
            "pages": {
                "https://kafka.apache.org/documentation/#monitoring": "Monitoring",
                "https://kafka.apache.org/documentation/#selector_monitoring": "Selector Metrics",
                "https://kafka.apache.org/documentation/#common_node_monitoring": "Common Node Monitoring",
                "https://kafka.apache.org/documentation/#producer_monitoring": "Producer Monitoring",
                "https://kafka.apache.org/documentation/#consumer_monitoring": "Consumer Monitoring",
                "https://kafka.apache.org/documentation/#connect_monitoring": "Connect Monitoring",
                "https://kafka.apache.org/documentation/#streams_monitoring": "Streams Monitoring",
                "https://kafka.apache.org/documentation/#others_monitoring": "Others Monitoring",
                "https://kafka.apache.org/documentation/#audit": "Audit",
            },
        },
        "operations-security": {
            "pages": {
                "https://kafka.apache.org/documentation/#security": "Security",
                "https://kafka.apache.org/documentation/#security_overview": "Security Overview",
                "https://kafka.apache.org/documentation/#security_ssl": "Encryption with SSL",
                "https://kafka.apache.org/documentation/#security_sasl": "Authentication using SASL",
                "https://kafka.apache.org/documentation/#security_authz": "Authorization and ACLs",
                "https://kafka.apache.org/documentation/#security_rolling_upgrade": "Security Rolling Upgrade",
                "https://kafka.apache.org/documentation/#security_sasl_plain": "SASL/PLAIN",
                "https://kafka.apache.org/documentation/#security_sasl_scram": "SASL/SCRAM",
                "https://kafka.apache.org/documentation/#security_sasl_oauthbearer": "SASL/OAUTHBEARER",
                "https://kafka.apache.org/documentation/#security_sasl_kerberos": "SASL/GSSAPI (Kerberos)",
                "https://kafka.apache.org/documentation/#security_delegation_token": "Delegation Tokens",
            },
        },
        "operations-multi-tenancy": {
            "pages": {
                "https://kafka.apache.org/documentation/#multitenancy": "Multi-Tenancy",
                "https://kafka.apache.org/documentation/#multitenancy-overview": "Multi-Tenancy Overview",
                "https://kafka.apache.org/documentation/#multitenancy-topic-naming": "Topic Naming",
                "https://kafka.apache.org/documentation/#multitenancy-security": "Multi-Tenancy Security",
                "https://kafka.apache.org/documentation/#multitenancy-quotas": "Quotas",
            },
        },
        "operations-geo-replication": {
            "pages": {
                "https://kafka.apache.org/documentation/#georeplication": "Geo-Replication",
                "https://kafka.apache.org/documentation/#georeplication-overview": "Geo-Replication Overview",
                "https://kafka.apache.org/documentation/#georeplication-flows": "Geo-Replication Flows",
            },
        },
        "streams-concepts": {
            "pages": {
                "https://kafka.apache.org/38/documentation/streams/": "Kafka Streams Documentation",
                "https://kafka.apache.org/38/documentation/streams/core-concepts": "Core Concepts",
                "https://kafka.apache.org/38/documentation/streams/quickstart": "Streams Quickstart",
                "https://kafka.apache.org/38/documentation/streams/tutorial": "Streams Tutorial",
            },
        },
        "streams-architecture": {
            "pages": {
                "https://kafka.apache.org/38/documentation/streams/architecture": "Streams Architecture",
                "https://kafka.apache.org/documentation/#streams_architecture": "Architecture Overview",
                "https://kafka.apache.org/documentation/#streams_tasks_and_threading": "Tasks and Threading",
                "https://kafka.apache.org/documentation/#streams_state": "Local State Stores",
                "https://kafka.apache.org/documentation/#streams_processing_guarantees": "Processing Guarantees",
            },
        },
        "streams-developer-guide": {
            "pages": {
                "https://kafka.apache.org/38/documentation/streams/developer-guide/": "Streams Developer Guide",
                "https://kafka.apache.org/38/documentation/streams/developer-guide/write-streams": "Writing a Streams Application",
                "https://kafka.apache.org/38/documentation/streams/developer-guide/config-streams": "Configuring Streams",
                "https://kafka.apache.org/38/documentation/streams/developer-guide/dsl-api": "Streams DSL",
                "https://kafka.apache.org/38/documentation/streams/developer-guide/processor-api": "Processor API",
                "https://kafka.apache.org/38/documentation/streams/developer-guide/datatypes": "Data Types and Serialization",
                "https://kafka.apache.org/38/documentation/streams/developer-guide/testing": "Testing a Streams Application",
                "https://kafka.apache.org/38/documentation/streams/developer-guide/interactive-queries": "Interactive Queries",
                "https://kafka.apache.org/38/documentation/streams/developer-guide/memory-mgmt": "Memory Management",
                "https://kafka.apache.org/38/documentation/streams/developer-guide/running-app": "Running Streams Applications",
                "https://kafka.apache.org/38/documentation/streams/developer-guide/manage-topics": "Managing Streams Topics",
                "https://kafka.apache.org/38/documentation/streams/developer-guide/security": "Streams Security",
                "https://kafka.apache.org/38/documentation/streams/developer-guide/app-reset-tool": "Application Reset Tool",
            },
        },
        "streams-upgrade-guide": {
            "pages": {
                "https://kafka.apache.org/38/documentation/streams/upgrade-guide": "Streams Upgrade Guide",
            },
        },
        "connect-concepts": {
            "pages": {
                "https://kafka.apache.org/documentation/#connect": "Kafka Connect",
                "https://kafka.apache.org/documentation/#connect_overview": "Connect Overview",
                "https://kafka.apache.org/documentation/#connect_user": "Connect User Guide",
                "https://kafka.apache.org/documentation/#connect_running": "Running Kafka Connect",
                "https://kafka.apache.org/documentation/#connect_configuring": "Configuring Connectors",
                "https://kafka.apache.org/documentation/#connect_rest": "Connect REST API",
                "https://kafka.apache.org/documentation/#connect_errorreporting": "Error Reporting",
                "https://kafka.apache.org/documentation/#connect_exactlyonce": "Exactly Once Semantics",
                "https://kafka.apache.org/documentation/#connect_plugindiscovery": "Plugin Discovery",
            },
        },
        "connect-user-guide": {
            "pages": {
                "https://kafka.apache.org/documentation/#connect_development": "Connector Development Guide",
                "https://kafka.apache.org/documentation/#connect_administration": "Connect Administration",
            },
        },
        "connect-transforms": {
            "pages": {
                "https://kafka.apache.org/documentation/#connect_transforms": "Connect Transformations",
                "https://kafka.apache.org/documentation/#connect_included_transformation": "Included Transformations",
                "https://kafka.apache.org/documentation/#connect_transform_cast": "Cast",
                "https://kafka.apache.org/documentation/#connect_transform_drop": "Drop",
                "https://kafka.apache.org/documentation/#connect_transform_extractfield": "ExtractField",
                "https://kafka.apache.org/documentation/#connect_transform_filter": "Filter",
                "https://kafka.apache.org/documentation/#connect_transform_flatten": "Flatten",
                "https://kafka.apache.org/documentation/#connect_transform_headersfrom": "HeadersFrom",
                "https://kafka.apache.org/documentation/#connect_transform_hoistfield": "HoistField",
                "https://kafka.apache.org/documentation/#connect_transform_insertfield": "InsertField",
                "https://kafka.apache.org/documentation/#connect_transform_maskfield": "MaskField",
                "https://kafka.apache.org/documentation/#connect_transform_regexrouter": "RegexRouter",
                "https://kafka.apache.org/documentation/#connect_transform_replacefield": "ReplaceField",
                "https://kafka.apache.org/documentation/#connect_transform_setschemetadata": "SetSchemaMetadata",
                "https://kafka.apache.org/documentation/#connect_transform_timestamprouter": "TimestampRouter",
                "https://kafka.apache.org/documentation/#connect_transform_timestampconverter": "TimestampConverter",
                "https://kafka.apache.org/documentation/#connect_transform_valuetokeyfield": "ValueToKey",
            },
        },
        "connect-converters": {
            "pages": {
                "https://kafka.apache.org/documentation/#connect_converters": "Connect Converters",
                "https://kafka.apache.org/documentation/#connect_json_converter": "JSON Converter",
                "https://kafka.apache.org/documentation/#connect_avro_converter": "Avro Converter",
                "https://kafka.apache.org/documentation/#connect_protobuf_converter": "Protobuf Converter",
                "https://kafka.apache.org/documentation/#connect_string_converter": "String Converter",
                "https://kafka.apache.org/documentation/#connect_bytearray_converter": "ByteArray Converter",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"kafka-{source_key}" if source_key else "kafka"
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
            # Clean common suffixes
            for suffix in [' - Apache Kafka', ' Apache Kafka',
                           ' | Apache Kafka', ' -- Apache Kafka']:
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
                        "category": f"kafka-{source_key}",
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
            self.log.info(f"=== Scraping kafka/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    KafkaScraper(base, source_key).run()
