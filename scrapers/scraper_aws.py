#!/usr/bin/env python3
"""AWS documentation scraper.

Covers:
  - EC2, S3, Lambda, RDS, DynamoDB
  - IAM, VPC, CloudFormation
  - ECS, EKS, SQS, SNS
  - CloudWatch, Route 53, API Gateway, Step Functions
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class AwsScraper(BaseScraper):
    """Scrape AWS documentation across major services."""

    SOURCES = {
        "ec2": {
            "pages": {
                # Core concepts
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/concepts.html": "EC2 Concepts",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html": "EC2 Getting Started",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instances.html": "EC2 Instances",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-types.html": "EC2 Instance Types",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/LaunchingAndUsingInstances.html": "EC2 Launching Instances",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html": "EC2 Key Pairs",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security-groups.html": "EC2 Security Groups",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/elastic-ip-addresses-eip.html": "EC2 Elastic IPs",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-volumes.html": "EC2 EBS Volumes",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-creating-volume.html": "EC2 Creating EBS Volumes",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-attaching-volume.html": "EC2 Attaching EBS Volumes",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-volume-types.html": "EC2 EBS Volume Types",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EBSSnapshots.html": "EC2 EBS Snapshots",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AMIs.html": "EC2 AMIs",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/creating-an-ami-ebs.html": "EC2 Creating AMIs",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-system-instance-status-check.html": "EC2 Status Checks",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-cloudwatch.html": "EC2 CloudWatch Monitoring",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/placement-groups.html": "EC2 Placement Groups",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-auto-scaling.html": "EC2 Auto Scaling",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-requests.html": "EC2 Spot Instances",
                # Networking
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-networking.html": "EC2 Networking",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html": "EC2 Elastic Network Interfaces",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/enhanced-networking.html": "EC2 Enhanced Networking",
                # Instance store and lifecycle
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/InstanceStorage.html": "EC2 Instance Store",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html": "EC2 Instance Lifecycle",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html": "EC2 Stop and Start Instances",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-recover.html": "EC2 Instance Recovery",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/terminating-instances.html": "EC2 Terminating Instances",
                # Security and access
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security.html": "EC2 Security",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html": "EC2 IAM Roles",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-metadata.html": "EC2 Instance Metadata",
                # Pricing and optimization
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-reserved-instances.html": "EC2 Reserved Instances",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-on-demand-instances.html": "EC2 On-Demand Instances",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-spot-instances.html": "EC2 Using Spot Instances",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/dedicated-hosts-overview.html": "EC2 Dedicated Hosts",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/capacity-reservations.html": "EC2 Capacity Reservations",
                # Advanced
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances.html": "EC2 Burstable Performance",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-fleet.html": "EC2 Fleet",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-launch-templates.html": "EC2 Launch Templates",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html": "EC2 User Data",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-optimized.html": "EC2 EBS-Optimized Instances",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EBSEncryption.html": "EC2 EBS Encryption",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-fast-snapshot-restore.html": "EC2 EBS Fast Snapshot Restore",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-instances-status-check.html": "EC2 Instance Status Monitoring",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-connect-methods.html": "EC2 Instance Connect",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/hibernating-prerequisites.html": "EC2 Hibernation",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-best-practices.html": "EC2 Best Practices",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-regions-availability-zones.html": "EC2 Regions and AZs",
                "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-tutorials.html": "EC2 Tutorials",
            },
        },
        "s3": {
            "pages": {
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html": "S3 Welcome",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/creating-bucket.html": "S3 Creating Buckets",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/uploading-downloading-objects.html": "S3 Upload Download Objects",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html": "S3 Lifecycle Management",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html": "S3 Versioning",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-overview.html": "S3 Access Control",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-policies.html": "S3 Bucket Policies",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication.html": "S3 Replication",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html": "S3 Storage Classes",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventNotifications.html": "S3 Event Notifications",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html": "S3 Security Best Practices",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/transfer-acceleration.html": "S3 Transfer Acceleration",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingEncryption.html": "S3 Encryption",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/cors.html": "S3 CORS",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteHosting.html": "S3 Static Website Hosting",
                # Additional S3 pages
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-points.html": "S3 Access Points",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html": "S3 Object Lock",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html": "S3 Presigned URLs",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/ServerLogs.html": "S3 Server Access Logging",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/Requestpaymentbuckets.html": "S3 Requester Pays",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingObjects.html": "S3 Working with Objects",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/ObjectsinBucketsOverview.html": "S3 Objects Overview",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/copy-object.html": "S3 Copying Objects",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/DeletingObjects.html": "S3 Deleting Objects",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/selecting-content-from-objects.html": "S3 Select",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-inventory.html": "S3 Inventory",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/analytics-storage-class.html": "S3 Storage Class Analysis",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-lens.html": "S3 Storage Lens",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/batch-ops.html": "S3 Batch Operations",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/intelligent-tiering.html": "S3 Intelligent-Tiering",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/MultiFactorAuthenticationDelete.html": "S3 MFA Delete",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingKMSEncryption.html": "S3 KMS Encryption",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/setting-repl-config-perm-overview.html": "S3 Replication Configuration",
                "https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html": "S3 Multipart Upload",
            },
        },
        "lambda": {
            "pages": {
                "https://docs.aws.amazon.com/lambda/latest/dg/welcome.html": "Lambda Welcome",
                "https://docs.aws.amazon.com/lambda/latest/dg/getting-started.html": "Lambda Getting Started",
                "https://docs.aws.amazon.com/lambda/latest/dg/lambda-functions.html": "Lambda Functions",
                "https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html": "Lambda Runtimes",
                "https://docs.aws.amazon.com/lambda/latest/dg/configuration-function-common.html": "Lambda Configuration",
                "https://docs.aws.amazon.com/lambda/latest/dg/lambda-permissions.html": "Lambda Permissions",
                "https://docs.aws.amazon.com/lambda/latest/dg/invocation-sync.html": "Lambda Synchronous Invocation",
                "https://docs.aws.amazon.com/lambda/latest/dg/invocation-async.html": "Lambda Asynchronous Invocation",
                "https://docs.aws.amazon.com/lambda/latest/dg/with-s3.html": "Lambda with S3",
                "https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html": "Lambda with SQS",
                "https://docs.aws.amazon.com/lambda/latest/dg/with-ddb.html": "Lambda with DynamoDB",
                "https://docs.aws.amazon.com/lambda/latest/dg/with-apigateway.html": "Lambda with API Gateway",
                "https://docs.aws.amazon.com/lambda/latest/dg/lambda-layers.html": "Lambda Layers",
                "https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html": "Lambda Environment Variables",
                "https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html": "Lambda VPC Configuration",
                "https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html": "Lambda Concurrency",
                "https://docs.aws.amazon.com/lambda/latest/dg/monitoring-functions-access-metrics.html": "Lambda Monitoring",
                "https://docs.aws.amazon.com/lambda/latest/dg/lambda-urls.html": "Lambda Function URLs",
                "https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html": "Lambda SnapStart",
                "https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html": "Lambda Limits",
                # Additional Lambda pages
                "https://docs.aws.amazon.com/lambda/latest/dg/lambda-deploy-functions.html": "Lambda Deploying Functions",
                "https://docs.aws.amazon.com/lambda/latest/dg/configuration-aliases.html": "Lambda Aliases",
                "https://docs.aws.amazon.com/lambda/latest/dg/configuration-versions.html": "Lambda Versions",
                "https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html": "Lambda Execution Role",
                "https://docs.aws.amazon.com/lambda/latest/dg/access-control-resource-based.html": "Lambda Resource-Based Policies",
                "https://docs.aws.amazon.com/lambda/latest/dg/with-sns.html": "Lambda with SNS",
                "https://docs.aws.amazon.com/lambda/latest/dg/with-kinesis.html": "Lambda with Kinesis",
                "https://docs.aws.amazon.com/lambda/latest/dg/services-cloudwatchevents.html": "Lambda with CloudWatch Events",
                "https://docs.aws.amazon.com/lambda/latest/dg/lambda-extensions.html": "Lambda Extensions",
                "https://docs.aws.amazon.com/lambda/latest/dg/configuration-filesystem.html": "Lambda File System Access",
                "https://docs.aws.amazon.com/lambda/latest/dg/python-handler.html": "Lambda Python Handler",
                "https://docs.aws.amazon.com/lambda/latest/dg/nodejs-handler.html": "Lambda Node.js Handler",
                "https://docs.aws.amazon.com/lambda/latest/dg/java-handler.html": "Lambda Java Handler",
                "https://docs.aws.amazon.com/lambda/latest/dg/lambda-troubleshooting.html": "Lambda Troubleshooting",
                "https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html": "Lambda Memory Configuration",
            },
        },
        "rds": {
            "pages": {
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html": "RDS Welcome",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_GettingStarted.html": "RDS Getting Started",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.DBInstanceClass.html": "RDS Instance Classes",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html": "RDS Storage",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html": "RDS Multi-AZ",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html": "RDS Read Replicas",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html": "RDS Automated Backups",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.Encryption.html": "RDS Encryption",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html": "RDS IAM Authentication",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Monitoring.html": "RDS Monitoring",
                "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/CHAP_AuroraOverview.html": "Aurora Overview",
                "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html": "Aurora Serverless v2",
                # Additional RDS pages
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_CreateDBInstance.html": "RDS Creating DB Instance",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ConnectToInstance.html": "RDS Connecting to Instance",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ModifyInstance.html": "RDS Modifying Instance",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_DeleteInstance.html": "RDS Deleting Instance",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_Tagging.html": "RDS Tagging Resources",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_Events.html": "RDS Events",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_LogAccess.html": "RDS Log Files",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PerfInsights.html": "RDS Performance Insights",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_CommonTasks.Connect.html": "RDS Common Connection Tasks",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html": "RDS Best Practices",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.DBInstance.Modifying.html": "RDS Modifying Overview",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_UpgradeDBInstance.html": "RDS Upgrading Engine Version",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.RDSSecurityGroups.html": "RDS Security Groups",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.html": "RDS VPC",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithParamGroups.html": "RDS Parameter Groups",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithOptionGroups.html": "RDS Option Groups",
                "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.Overview.html": "Aurora Features Overview",
                "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraMySQL.html": "Aurora MySQL",
                "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.html": "Aurora PostgreSQL",
                "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html": "Aurora Global Database",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Tutorials.html": "RDS Tutorials",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.html": "RDS Proxy",
                "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.RegionsAndAvailabilityZones.html": "RDS Regions and AZs",
            },
        },
        "dynamodb": {
            "pages": {
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Introduction.html": "DynamoDB Introduction",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GettingStartedDynamoDB.html": "DynamoDB Getting Started",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.CoreComponents.html": "DynamoDB Core Components",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadWriteCapacityMode.html": "DynamoDB Capacity Modes",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html": "DynamoDB Partition Key Design",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/SecondaryIndexes.html": "DynamoDB Secondary Indexes",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html": "DynamoDB Streams",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DAX.html": "DynamoDB DAX",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/BackupRestore.html": "DynamoDB Backup Restore",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GlobalTables.html": "DynamoDB Global Tables",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html": "DynamoDB TTL",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.html": "DynamoDB Expressions",
                # Additional DynamoDB pages
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithTables.html": "DynamoDB Working with Tables",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html": "DynamoDB Working with Items",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Query.html": "DynamoDB Query",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Scan.html": "DynamoDB Scan",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.html": "DynamoDB Global Secondary Indexes",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/LSI.html": "DynamoDB Local Secondary Indexes",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html": "DynamoDB Condition Expressions",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.UpdateExpressions.html": "DynamoDB Update Expressions",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ProjectionExpressions.html": "DynamoDB Projection Expressions",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html": "DynamoDB Transactions",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-general-nosql-design.html": "DynamoDB NoSQL Design",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html": "DynamoDB Best Practices",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/EncryptionAtRest.html": "DynamoDB Encryption at Rest",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/MonitoringDynamoDB.html": "DynamoDB Monitoring",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBPipeline.html": "DynamoDB Data Pipeline",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery.html": "DynamoDB Point-in-Time Recovery",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/contributorinsights.html": "DynamoDB Contributor Insights",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.Partitions.html": "DynamoDB Partitions",
                "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/AutoScaling.html": "DynamoDB Auto Scaling",
            },
        },
        "iam": {
            "pages": {
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction.html": "IAM Introduction",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/getting-started.html": "IAM Getting Started",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_users.html": "IAM Users",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_groups.html": "IAM Groups",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles.html": "IAM Roles",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html": "IAM Policies",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements.html": "IAM Policy Elements",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html": "IAM Best Practices",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa.html": "IAM MFA",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_switch-role-ec2.html": "IAM Roles for EC2",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html": "IAM Permissions Boundaries",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp.html": "IAM Temporary Credentials",
                # Additional IAM pages
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_users_create.html": "IAM Creating Users",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_users_manage.html": "IAM Managing Users",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create.html": "IAM Creating Roles",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_manage.html": "IAM Managing Roles",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_create.html": "IAM Creating Policies",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_managed-vs-inline.html": "IAM Managed vs Inline Policies",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_actions-resources-contextkeys.html": "IAM Actions Resources Context Keys",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_testing-policies.html": "IAM Policy Simulator",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html": "IAM Access Keys",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_passwords.html": "IAM Passwords",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/cloudtrail-integration.html": "IAM CloudTrail Integration",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/access-analyzer-getting-started.html": "IAM Access Analyzer",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_tags.html": "IAM Tagging Resources",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html": "IAM Global Condition Keys",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers.html": "IAM Identity Providers",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_saml.html": "IAM SAML Identity Providers",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_oidc.html": "IAM OIDC Identity Providers",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/security-audit-guide.html": "IAM Security Audit Guide",
            },
        },
        "vpc": {
            "pages": {
                "https://docs.aws.amazon.com/vpc/latest/userguide/what-is-amazon-vpc.html": "VPC Overview",
                "https://docs.aws.amazon.com/vpc/latest/userguide/how-it-works.html": "VPC How It Works",
                "https://docs.aws.amazon.com/vpc/latest/userguide/create-vpc.html": "VPC Create",
                "https://docs.aws.amazon.com/vpc/latest/userguide/configure-subnets.html": "VPC Subnets",
                "https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Route_Tables.html": "VPC Route Tables",
                "https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Internet_Gateway.html": "VPC Internet Gateway",
                "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html": "VPC NAT Gateway",
                "https://docs.aws.amazon.com/vpc/latest/userguide/VPC_SecurityGroups.html": "VPC Security Groups",
                "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-network-acls.html": "VPC Network ACLs",
                "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-peering.html": "VPC Peering",
                "https://docs.aws.amazon.com/vpc/latest/userguide/endpoint-services-overview.html": "VPC Endpoints",
                "https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html": "VPC Flow Logs",
                # Additional VPC pages
                "https://docs.aws.amazon.com/vpc/latest/userguide/VPC_DHCP_Options.html": "VPC DHCP Options",
                "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-dns.html": "VPC DNS",
                "https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Scenario1.html": "VPC Public Subnet Scenario",
                "https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Scenario2.html": "VPC Public and Private Subnet Scenario",
                "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-comparison.html": "VPC NAT Comparison",
                "https://docs.aws.amazon.com/vpc/latest/userguide/egress-only-internet-gateway.html": "VPC Egress-Only Internet Gateway",
                "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-endpoints-s3.html": "VPC Endpoints for S3",
                "https://docs.aws.amazon.com/vpc/latest/userguide/vpce-interface.html": "VPC Interface Endpoints",
                "https://docs.aws.amazon.com/vpc/latest/userguide/vpce-gateway.html": "VPC Gateway Endpoints",
                "https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Subnets.html": "VPC Subnets Overview",
                "https://docs.aws.amazon.com/vpc/latest/userguide/working-with-vpcs.html": "VPC Working with VPCs",
                "https://docs.aws.amazon.com/vpc/latest/userguide/security-group-rules.html": "VPC Security Group Rules",
                "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-migrate-ipv6.html": "VPC IPv6 Migration",
                "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-sharing.html": "VPC Sharing",
                "https://docs.aws.amazon.com/vpc/latest/userguide/managed-prefix-lists.html": "VPC Managed Prefix Lists",
                "https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Monitoring.html": "VPC Monitoring",
                "https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-cwl.html": "VPC Flow Logs to CloudWatch",
                "https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-s3.html": "VPC Flow Logs to S3",
            },
        },
        "cloudformation": {
            "pages": {
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html": "CloudFormation Welcome",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/GettingStarted.html": "CloudFormation Getting Started",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-anatomy.html": "CloudFormation Template Anatomy",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/resources-section-structure.html": "CloudFormation Resources",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/parameters-section-structure.html": "CloudFormation Parameters",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/outputs-section-structure.html": "CloudFormation Outputs",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/mappings-section-structure.html": "CloudFormation Mappings",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/conditions-section-structure.html": "CloudFormation Conditions",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference.html": "CloudFormation Intrinsic Functions",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks.html": "CloudFormation Updating Stacks",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-nested-stacks.html": "CloudFormation Nested Stacks",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-template-resource-type-ref.html": "CloudFormation Resource Reference",
                # Additional CloudFormation pages
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacks.html": "CloudFormation Stacks",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-exports.html": "CloudFormation Stack Exports",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-rollback-triggers.html": "CloudFormation Rollback Triggers",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-concepts.html": "CloudFormation StackSets",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-drift-detection.html": "CloudFormation Drift Detection",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-macros.html": "CloudFormation Macros",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-protect-stacks.html": "CloudFormation Stack Protection",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-console-create-stack.html": "CloudFormation Create Stack Console",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-console-delete-stack.html": "CloudFormation Delete Stack",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-custom-resources.html": "CloudFormation Custom Resources",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-cfn-customresource.html": "CloudFormation Custom Resource Type",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-ref.html": "CloudFormation Ref Function",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html": "CloudFormation GetAtt Function",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-sub.html": "CloudFormation Sub Function",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-join.html": "CloudFormation Join Function",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-select.html": "CloudFormation Select Function",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-split.html": "CloudFormation Split Function",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-importvalue.html": "CloudFormation ImportValue Function",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html": "CloudFormation Best Practices",
                "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-guard.html": "CloudFormation Guard",
            },
        },
        "ecs": {
            "pages": {
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html": "ECS Welcome",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/getting-started.html": "ECS Getting Started",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html": "ECS Task Definitions",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html": "ECS Services",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/clusters.html": "ECS Clusters",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html": "ECS Fargate",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-load-balancing.html": "ECS Load Balancing",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-auto-scaling.html": "ECS Auto Scaling",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-networking.html": "ECS Task Networking",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using_cloudwatch_logs.html": "ECS CloudWatch Logs",
                # Additional ECS pages
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html": "ECS Task Definition Parameters",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/launch_types.html": "ECS Launch Types",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/scheduling_tasks.html": "ECS Scheduling Tasks",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-discovery.html": "ECS Service Discovery",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-connect.html": "ECS Service Connect",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-types.html": "ECS Deployment Types",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-placement.html": "ECS Task Placement",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/specifying-sensitive-data.html": "ECS Sensitive Data",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-exec.html": "ECS Exec",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/private-auth.html": "ECS Private Registry Auth",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html": "ECS Task IAM Roles",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-cpu-memory-error.html": "ECS CPU Memory Error",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS_instances.html": "ECS Container Instances",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/container-considerations.html": "ECS Container Considerations",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_monitoring.html": "ECS Monitoring Overview",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-capacity-providers.html": "ECS Capacity Providers",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/update-service.html": "ECS Updating Services",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/stop-task.html": "ECS Stopping Tasks",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-optimized_AMI.html": "ECS Optimized AMI",
                "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS_AWSCLI_Fargate.html": "ECS Fargate CLI Tutorial",
            },
        },
        "eks": {
            "pages": {
                "https://docs.aws.amazon.com/eks/latest/userguide/what-is-eks.html": "EKS Overview",
                "https://docs.aws.amazon.com/eks/latest/userguide/getting-started.html": "EKS Getting Started",
                "https://docs.aws.amazon.com/eks/latest/userguide/create-cluster.html": "EKS Create Cluster",
                "https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html": "EKS Managed Node Groups",
                "https://docs.aws.amazon.com/eks/latest/userguide/fargate.html": "EKS Fargate",
                "https://docs.aws.amazon.com/eks/latest/userguide/network_reqs.html": "EKS Networking",
                "https://docs.aws.amazon.com/eks/latest/userguide/cluster-autoscaler.html": "EKS Cluster Autoscaler",
                "https://docs.aws.amazon.com/eks/latest/userguide/eks-networking.html": "EKS Networking Add-ons",
                "https://docs.aws.amazon.com/eks/latest/userguide/dashboard-tutorial.html": "EKS Dashboard",
                "https://docs.aws.amazon.com/eks/latest/userguide/control-plane-logs.html": "EKS Control Plane Logs",
                # Additional EKS pages
                "https://docs.aws.amazon.com/eks/latest/userguide/update-cluster.html": "EKS Update Cluster",
                "https://docs.aws.amazon.com/eks/latest/userguide/delete-cluster.html": "EKS Delete Cluster",
                "https://docs.aws.amazon.com/eks/latest/userguide/worker.html": "EKS Self-Managed Nodes",
                "https://docs.aws.amazon.com/eks/latest/userguide/launch-workers.html": "EKS Launch Workers",
                "https://docs.aws.amazon.com/eks/latest/userguide/eks-compute.html": "EKS Compute",
                "https://docs.aws.amazon.com/eks/latest/userguide/pod-networking.html": "EKS Pod Networking",
                "https://docs.aws.amazon.com/eks/latest/userguide/cni-custom-network.html": "EKS CNI Custom Networking",
                "https://docs.aws.amazon.com/eks/latest/userguide/security-groups-for-pods.html": "EKS Security Groups for Pods",
                "https://docs.aws.amazon.com/eks/latest/userguide/alb-ingress.html": "EKS ALB Ingress",
                "https://docs.aws.amazon.com/eks/latest/userguide/network-load-balancing.html": "EKS Network Load Balancing",
                "https://docs.aws.amazon.com/eks/latest/userguide/enable-iam-roles-for-service-accounts.html": "EKS IAM Roles for Service Accounts",
                "https://docs.aws.amazon.com/eks/latest/userguide/managing-ebs-csi.html": "EKS EBS CSI Driver",
                "https://docs.aws.amazon.com/eks/latest/userguide/managing-efs-csi.html": "EKS EFS CSI Driver",
                "https://docs.aws.amazon.com/eks/latest/userguide/eks-add-ons.html": "EKS Add-ons",
                "https://docs.aws.amazon.com/eks/latest/userguide/managing-coredns.html": "EKS CoreDNS",
                "https://docs.aws.amazon.com/eks/latest/userguide/managing-kube-proxy.html": "EKS kube-proxy",
                "https://docs.aws.amazon.com/eks/latest/userguide/managing-vpc-cni.html": "EKS VPC CNI",
                "https://docs.aws.amazon.com/eks/latest/userguide/platform-versions.html": "EKS Platform Versions",
                "https://docs.aws.amazon.com/eks/latest/userguide/eks-connector.html": "EKS Connector",
                "https://docs.aws.amazon.com/eks/latest/userguide/prometheus.html": "EKS Prometheus Monitoring",
            },
        },
        "sqs": {
            "pages": {
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html": "SQS Welcome",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-getting-started.html": "SQS Getting Started",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-basic-architecture.html": "SQS Architecture",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-standard-queues.html": "SQS Standard Queues",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues.html": "SQS FIFO Queues",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html": "SQS Dead Letter Queues",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html": "SQS Visibility Timeout",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-delay-queues.html": "SQS Delay Queues",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-message-filtering.html": "SQS Message Filtering",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-long-polling.html": "SQS Long Polling",
                # Additional SQS pages
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-creating-deleting-queue.html": "SQS Creating Deleting Queues",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-send-message.html": "SQS Sending Messages",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-receive-delete-message.html": "SQS Receiving Deleting Messages",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-message-metadata.html": "SQS Message Metadata",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-message-attributes.html": "SQS Message Attributes",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-server-side-encryption.html": "SQS Server-Side Encryption",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-using-identity-based-policies.html": "SQS IAM Policies",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-monitoring-using-cloudwatch.html": "SQS CloudWatch Monitoring",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-configure-dead-letter-queue-redrive.html": "SQS DLQ Redrive",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-quotas.html": "SQS Quotas",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-batch-api-actions.html": "SQS Batch API Actions",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues-understanding-logic.html": "SQS FIFO Queue Logic",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-temporary-queues.html": "SQS Temporary Queues",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-best-practices.html": "SQS Best Practices",
                "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-short-and-long-polling.html": "SQS Short and Long Polling",
            },
        },
        "sns": {
            "pages": {
                "https://docs.aws.amazon.com/sns/latest/dg/welcome.html": "SNS Welcome",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-getting-started.html": "SNS Getting Started",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-create-topic.html": "SNS Create Topic",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-create-subscribe-endpoint-to-topic.html": "SNS Subscriptions",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-message-filtering.html": "SNS Message Filtering",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-fifo-topics.html": "SNS FIFO Topics",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-mobile-push-notifications.html": "SNS Mobile Push",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-email-notifications.html": "SNS Email Notifications",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-sqs-as-subscriber.html": "SNS with SQS",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-lambda-as-subscriber.html": "SNS with Lambda",
                # Additional SNS pages
                "https://docs.aws.amazon.com/sns/latest/dg/sns-how-it-works.html": "SNS How It Works",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-publishing.html": "SNS Publishing Messages",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-message-delivery-retries.html": "SNS Message Delivery Retries",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-dead-letter-queues.html": "SNS Dead Letter Queues",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-access-policy-language.html": "SNS Access Policy Language",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-server-side-encryption.html": "SNS Server-Side Encryption",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-message-data-protection.html": "SNS Message Data Protection",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-monitoring-using-cloudwatch.html": "SNS CloudWatch Monitoring",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-logging-using-cloudtrail.html": "SNS CloudTrail Logging",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-http-https-endpoint-as-subscriber.html": "SNS HTTP Endpoint Subscriber",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-large-payload-raw-message-delivery.html": "SNS Raw Message Delivery",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-msg-status.html": "SNS Message Status",
                "https://docs.aws.amazon.com/sns/latest/dg/channels-sms.html": "SNS SMS Messages",
                "https://docs.aws.amazon.com/sns/latest/dg/sns-tags.html": "SNS Tagging Topics",
            },
        },
        "cloudwatch": {
            "pages": {
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/WhatIsCloudWatch.html": "CloudWatch Overview",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/GettingStarted.html": "CloudWatch Getting Started",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/working_with_metrics.html": "CloudWatch Metrics",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html": "CloudWatch Alarms",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Dashboards.html": "CloudWatch Dashboards",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/WhatIsCloudWatchLogs.html": "CloudWatch Logs",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html": "CloudWatch Logs Insights",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/publishingMetrics.html": "CloudWatch Publishing Metrics",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent.html": "CloudWatch Agent",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Anomaly_Detection.html": "CloudWatch Anomaly Detection",
                # Additional CloudWatch pages
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/aws-services-cloudwatch-metrics.html": "CloudWatch AWS Service Metrics",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/viewing_metrics_with_cloudwatch.html": "CloudWatch Viewing Metrics",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/graph_metrics.html": "CloudWatch Graphing Metrics",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/using-metric-math.html": "CloudWatch Metric Math",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/search-expression-syntax.html": "CloudWatch Search Expressions",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Create-alarm-on-metric-math-expression.html": "CloudWatch Math Expression Alarms",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/US_AlarmAtThresholdEC2.html": "CloudWatch EC2 Alarms",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ConsoleAlarms.html": "CloudWatch Console Alarms",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Composite_Alarms.html": "CloudWatch Composite Alarms",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/MonitoringLogData.html": "CloudWatch Log Monitoring",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/Subscriptions.html": "CloudWatch Log Subscriptions",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/FilterAndPatternSyntax.html": "CloudWatch Log Filter Syntax",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Metric-Streams.html": "CloudWatch Metric Streams",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Synthetics_Canaries.html": "CloudWatch Synthetics",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-RUM.html": "CloudWatch RUM",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Evidently.html": "CloudWatch Evidently",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights.html": "CloudWatch Container Insights",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Lambda-Insights.html": "CloudWatch Lambda Insights",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/appinsights.html": "CloudWatch Application Insights",
                "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-ServiceLevelObjectives.html": "CloudWatch Service Level Objectives",
            },
        },
        "route53": {
            "pages": {
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/Welcome.html": "Route 53 Welcome",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/getting-started.html": "Route 53 Getting Started",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/hosted-zones-working-with.html": "Route 53 Hosted Zones",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/rrsets-working-with.html": "Route 53 Record Sets",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy.html": "Route 53 Routing Policies",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/health-checks-creating.html": "Route 53 Health Checks",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/domain-register.html": "Route 53 Domain Registration",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver.html": "Route 53 Resolver",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-failover.html": "Route 53 DNS Failover",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/traffic-flow.html": "Route 53 Traffic Flow",
                # Additional Route 53 pages
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/AboutHZWorkingWith.html": "Route 53 Working with Hosted Zones",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resource-record-sets-choosing-alias-non-alias.html": "Route 53 Alias vs Non-Alias",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy-weighted.html": "Route 53 Weighted Routing",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy-latency.html": "Route 53 Latency Routing",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy-failover.html": "Route 53 Failover Routing",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy-geo.html": "Route 53 Geolocation Routing",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy-multivalue.html": "Route 53 Multivalue Routing",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/health-checks-types.html": "Route 53 Health Check Types",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-forwarding-inbound-queries.html": "Route 53 Resolver Inbound",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-forwarding-outbound-queries.html": "Route 53 Resolver Outbound",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-rules-managing.html": "Route 53 Resolver Rules",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/domain-transfer-to-route-53.html": "Route 53 Domain Transfer",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-configuring-dnssec.html": "Route 53 DNSSEC",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/monitoring-overview.html": "Route 53 Monitoring",
                "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/query-logs.html": "Route 53 Query Logging",
            },
        },
        "api-gateway": {
            "pages": {
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/welcome.html": "API Gateway Welcome",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/getting-started.html": "API Gateway Getting Started",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html": "API Gateway HTTP APIs",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-rest-api.html": "API Gateway REST APIs",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-websocket-api.html": "API Gateway WebSocket APIs",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-method-settings.html": "API Gateway Method Settings",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-authorization-flow.html": "API Gateway Authorization",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-stages.html": "API Gateway Stages",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-mapping-template-reference.html": "API Gateway Mapping Templates",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html": "API Gateway Throttling",
                # Additional API Gateway pages
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-integrate-with-cognito.html": "API Gateway Cognito Integration",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-lambda-authorizer-input.html": "API Gateway Lambda Authorizer",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/how-to-cors.html": "API Gateway CORS",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-custom-domain-name.html": "API Gateway Custom Domain Names",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-validation.html": "API Gateway Request Validation",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-usage-plans.html": "API Gateway Usage Plans",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-regional-api-custom-domain-create.html": "API Gateway Regional Custom Domain",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/how-to-generate-sdk.html": "API Gateway SDK Generation",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-caching.html": "API Gateway Caching",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-logging-to-cloudwatch.html": "API Gateway CloudWatch Logging",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-method-responses.html": "API Gateway Method Responses",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-api-with-vpclink.html": "API Gateway VPC Link",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-resource-policies.html": "API Gateway Resource Policies",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html": "API Gateway HTTP vs REST",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-routes.html": "API Gateway HTTP API Routes",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations.html": "API Gateway HTTP API Integrations",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-websocket-api-selection-expressions.html": "API Gateway WebSocket Selection",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-websocket-api-routes-integrations.html": "API Gateway WebSocket Routes",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions.html": "API Gateway OpenAPI Extensions",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-getting-started-with-terraform.html": "API Gateway Terraform Integration",
            },
        },
        "step-functions": {
            "pages": {
                "https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html": "Step Functions Welcome",
                "https://docs.aws.amazon.com/step-functions/latest/dg/getting-started.html": "Step Functions Getting Started",
                "https://docs.aws.amazon.com/step-functions/latest/dg/concepts-standard-vs-express.html": "Step Functions Standard vs Express",
                "https://docs.aws.amazon.com/step-functions/latest/dg/concepts-amazon-states-language.html": "Step Functions ASL",
                "https://docs.aws.amazon.com/step-functions/latest/dg/amazon-states-language-task-state.html": "Step Functions Task State",
                "https://docs.aws.amazon.com/step-functions/latest/dg/amazon-states-language-choice-state.html": "Step Functions Choice State",
                "https://docs.aws.amazon.com/step-functions/latest/dg/amazon-states-language-parallel-state.html": "Step Functions Parallel State",
                "https://docs.aws.amazon.com/step-functions/latest/dg/amazon-states-language-map-state.html": "Step Functions Map State",
                "https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html": "Step Functions Error Handling",
                "https://docs.aws.amazon.com/step-functions/latest/dg/connect-to-services.html": "Step Functions Service Integrations",
                "https://docs.aws.amazon.com/step-functions/latest/dg/monitoring-using-cloudwatch-console.html": "Step Functions Monitoring",
                "https://docs.aws.amazon.com/step-functions/latest/dg/bp-express.html": "Step Functions Best Practices",
                # Additional Step Functions pages
                "https://docs.aws.amazon.com/step-functions/latest/dg/amazon-states-language-wait-state.html": "Step Functions Wait State",
                "https://docs.aws.amazon.com/step-functions/latest/dg/amazon-states-language-succeed-state.html": "Step Functions Succeed State",
                "https://docs.aws.amazon.com/step-functions/latest/dg/amazon-states-language-fail-state.html": "Step Functions Fail State",
                "https://docs.aws.amazon.com/step-functions/latest/dg/amazon-states-language-pass-state.html": "Step Functions Pass State",
                "https://docs.aws.amazon.com/step-functions/latest/dg/input-output-filters.html": "Step Functions Input Output Processing",
                "https://docs.aws.amazon.com/step-functions/latest/dg/concepts-input-output-filtering.html": "Step Functions Data Flow",
                "https://docs.aws.amazon.com/step-functions/latest/dg/connect-lambda.html": "Step Functions Lambda Integration",
                "https://docs.aws.amazon.com/step-functions/latest/dg/connect-ddb.html": "Step Functions DynamoDB Integration",
                "https://docs.aws.amazon.com/step-functions/latest/dg/connect-sqs.html": "Step Functions SQS Integration",
                "https://docs.aws.amazon.com/step-functions/latest/dg/connect-sns.html": "Step Functions SNS Integration",
                "https://docs.aws.amazon.com/step-functions/latest/dg/connect-ecs.html": "Step Functions ECS Integration",
                "https://docs.aws.amazon.com/step-functions/latest/dg/concepts-activities.html": "Step Functions Activities",
                "https://docs.aws.amazon.com/step-functions/latest/dg/cw-events.html": "Step Functions CloudWatch Events",
                "https://docs.aws.amazon.com/step-functions/latest/dg/concepts-examine-api.html": "Step Functions Execution History",
                "https://docs.aws.amazon.com/step-functions/latest/dg/sfn-local.html": "Step Functions Local Testing",
                "https://docs.aws.amazon.com/step-functions/latest/dg/concepts-nested-workflows.html": "Step Functions Nested Workflows",
                "https://docs.aws.amazon.com/step-functions/latest/dg/tutorial-creating-lambda-state-machine.html": "Step Functions Lambda Tutorial",
                "https://docs.aws.amazon.com/step-functions/latest/dg/concepts-invoke-sfn.html": "Step Functions Invocation",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"aws-{source_key}" if source_key else "aws"
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
            for suffix in [' - Amazon Web Services', ' - AWS', ' - AWS Documentation', ' | AWS']:
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
                        "category": f"aws-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(2.0)  # Respectful rate limit for AWS docs

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
            self.log.info(f"=== Scraping aws/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    AwsScraper(base, source_key).run()
