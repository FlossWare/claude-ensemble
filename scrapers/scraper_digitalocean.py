#!/usr/bin/env python3
"""DigitalOcean community tutorials scraper.

Covers:
  - Linux server administration (setup, security, networking, tools)
  - Databases (MySQL, PostgreSQL, MongoDB, Redis, Elasticsearch)
  - DevOps (Docker, Kubernetes, Ansible, Terraform, CI/CD)
  - Web servers (Nginx, Apache, Caddy, HAProxy, SSL/TLS)
  - Programming (Python, Node.js, Go, Ruby, PHP, Java, TypeScript)
  - Cloud infrastructure (Droplets, networking, storage, DNS, HA)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class DigitalOceanScraper(BaseScraper):
    """Scrape DigitalOcean community tutorials and guides."""

    SOURCES = {
        "linux": {
            "pages": {
                # Server setup
                "https://www.digitalocean.com/community/tutorials/initial-server-setup-with-ubuntu-22-04": "Initial Server Setup with Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-firewall-with-ufw-on-ubuntu-22-04": "How To Set Up a Firewall with UFW on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-systemctl-to-manage-systemd-services-and-units": "How To Use Systemctl to Manage Systemd Services and Units",
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-linux-basics": "An Introduction to Linux Basics",
                "https://www.digitalocean.com/community/tutorials/how-to-add-and-delete-users-on-ubuntu-22-04": "How To Add and Delete Users on Ubuntu 22.04",
                # SSH
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-ssh-keys-on-ubuntu-22-04": "How To Set Up SSH Keys on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/ssh-essentials-working-with-ssh-servers-clients-and-keys": "SSH Essentials: Working with SSH Servers, Clients, and Keys",
                "https://www.digitalocean.com/community/tutorials/how-to-use-ssh-to-connect-to-a-remote-server": "How To Use SSH to Connect to a Remote Server",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-ssh-key-based-authentication-on-a-linux-server": "How To Configure SSH Key-Based Authentication on a Linux Server",
                # Firewall and networking
                "https://www.digitalocean.com/community/tutorials/ufw-essentials-common-firewall-rules-and-commands": "UFW Essentials: Common Firewall Rules and Commands",
                "https://www.digitalocean.com/community/tutorials/how-to-use-iptables-to-manage-and-forward-network-traffic": "How To Use Iptables to Manage and Forward Network Traffic",
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-networking-terminology-interfaces-and-protocols": "An Introduction to Networking Terminology, Interfaces, and Protocols",
                "https://www.digitalocean.com/community/tutorials/understanding-ip-addresses-subnets-and-cidr-notation-for-networking": "Understanding IP Addresses, Subnets, and CIDR Notation for Networking",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-the-linux-firewall-for-docker-swarm-on-ubuntu-20-04": "How To Configure the Linux Firewall for Docker Swarm on Ubuntu 20.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-nmap-to-scan-for-open-ports": "How To Use Nmap to Scan for Open Ports",
                # System administration
                "https://www.digitalocean.com/community/tutorials/how-to-use-cron-to-automate-tasks-ubuntu-1804": "How To Use Cron to Automate Tasks on Ubuntu 18.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-journalctl-to-view-and-manipulate-systemd-logs": "How To Use Journalctl to View and Manipulate Systemd Logs",
                "https://www.digitalocean.com/community/tutorials/how-to-use-top-netstat-du-other-tools-to-monitor-server-resources": "How To Use Top, Netstat, Du, and Other Tools to Monitor Server Resources",
                "https://www.digitalocean.com/community/tutorials/how-to-partition-and-format-storage-devices-in-linux": "How To Partition and Format Storage Devices in Linux",
                "https://www.digitalocean.com/community/tutorials/how-to-troubleshoot-common-site-issues-on-a-linux-server": "How To Troubleshoot Common Site Issues on a Linux Server",
                "https://www.digitalocean.com/community/tutorials/how-to-use-bash-history-commands-and-expansions-on-a-linux-vps": "How To Use Bash History Commands and Expansions on a Linux VPS",
                "https://www.digitalocean.com/community/tutorials/how-to-use-rsync-to-sync-local-and-remote-directories": "How To Use Rsync to Sync Local and Remote Directories",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-linux-servers-with-the-cockpit-web-interface": "How To Manage Linux Servers with the Cockpit Web Interface",
                "https://www.digitalocean.com/community/tutorials/how-to-create-a-self-signed-ssl-certificate-for-apache-in-ubuntu-22-04": "How To Create a Self-Signed SSL Certificate for Apache in Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-logrotate-to-manage-log-files": "How To Use Logrotate to Manage Log Files",
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-linux-permissions": "An Introduction to Linux Permissions",
                "https://www.digitalocean.com/community/tutorials/how-to-use-find-and-locate-to-search-for-files-on-linux": "How To Use Find and Locate to Search for Files on Linux",
                "https://www.digitalocean.com/community/tutorials/how-to-view-and-update-the-linux-path-environment-variable": "How To View and Update the Linux PATH Environment Variable",
                "https://www.digitalocean.com/community/tutorials/how-to-use-apt-get-on-debian-ubuntu": "How To Use apt-get on Debian/Ubuntu",
                "https://www.digitalocean.com/community/tutorials/linux-commands": "Linux Commands",
                "https://www.digitalocean.com/community/tutorials/how-to-use-grep-command-in-linux-unix": "How To Use Grep Command in Linux/Unix",
                "https://www.digitalocean.com/community/tutorials/how-to-use-ps-kill-and-nice-to-manage-processes-in-linux": "How To Use ps, kill, and nice to Manage Processes in Linux",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-time-synchronization-on-ubuntu-22-04": "How To Set Up Time Synchronization on Ubuntu 22.04",
                # Additional Linux topics
                "https://www.digitalocean.com/community/tutorials/how-to-add-swap-space-on-ubuntu-22-04": "How To Add Swap Space on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-lvm-to-manage-storage-devices-on-ubuntu-18-04": "How To Use LVM to Manage Storage Devices on Ubuntu 18.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-tar-command-in-linux": "How To Use Tar Command in Linux",
                "https://www.digitalocean.com/community/tutorials/linux-chmod-command-usage-and-examples": "Linux Chmod Command Usage and Examples",
                "https://www.digitalocean.com/community/tutorials/linux-chown-command-usage-and-examples": "Linux Chown Command Usage and Examples",
                "https://www.digitalocean.com/community/tutorials/the-basics-of-using-the-sed-stream-editor-to-manipulate-text-in-linux": "The Basics of Using the Sed Stream Editor to Manipulate Text in Linux",
                "https://www.digitalocean.com/community/tutorials/how-to-use-the-awk-language-to-manipulate-text-in-linux": "How To Use the AWK Language to Manipulate Text in Linux",
                "https://www.digitalocean.com/community/tutorials/how-to-use-tmux-terminal-multiplexer": "How To Use Tmux Terminal Multiplexer",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-use-screen-on-an-ubuntu-cloud-server": "How To Install and Use Screen on an Ubuntu Cloud Server",
                "https://www.digitalocean.com/community/tutorials/how-to-use-tcpdump-to-capture-and-analyze-network-traffic": "How To Use Tcpdump to Capture and Analyze Network Traffic",
                "https://www.digitalocean.com/community/tutorials/how-to-use-the-ss-command-on-linux": "How To Use the ss Command on Linux",
                "https://www.digitalocean.com/community/tutorials/how-to-use-ip-command-in-linux": "How To Use the ip Command in Linux",
                "https://www.digitalocean.com/community/tutorials/how-to-use-dnf-to-manage-packages-on-a-linux-server": "How To Use DNF to Manage Packages on a Linux Server",
                "https://www.digitalocean.com/community/tutorials/getting-started-with-vim-an-interactive-guide": "Getting Started with Vim: An Interactive Guide",
                "https://www.digitalocean.com/community/tutorials/how-to-use-nano-the-linux-command-line-text-editor": "How To Use Nano, the Linux Command Line Text Editor",
                "https://www.digitalocean.com/community/tutorials/how-to-read-and-set-environmental-and-shell-variables-on-linux": "How To Read and Set Environmental and Shell Variables on Linux",
                "https://www.digitalocean.com/community/tutorials/how-to-use-grub-rescue-to-fix-linux-boot-issues": "How To Use GRUB Rescue to Fix Linux Boot Issues",
                "https://www.digitalocean.com/community/tutorials/how-to-tune-linux-kernel-parameters-with-sysctl": "How To Tune Linux Kernel Parameters with Sysctl",
                "https://www.digitalocean.com/community/tutorials/how-to-use-scp-command-to-securely-transfer-files": "How To Use SCP Command to Securely Transfer Files",
                "https://www.digitalocean.com/community/tutorials/how-to-use-sftp-to-securely-transfer-files-with-a-remote-server": "How To Use SFTP to Securely Transfer Files with a Remote Server",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-wireguard-on-ubuntu-22-04": "How To Set Up WireGuard on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-and-use-lxd-on-ubuntu-22-04": "How To Set Up and Use LXD on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-useful-bash-aliases-and-functions": "An Introduction to Useful Bash Aliases and Functions",
                "https://www.digitalocean.com/community/tutorials/how-to-write-a-bash-script-on-linux": "How To Write a Bash Script on Linux",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-bind-as-a-private-network-dns-server-on-ubuntu-22-04": "How To Configure BIND as a Private Network DNS Server on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-nfs-mount-on-ubuntu-22-04": "How To Set Up an NFS Mount on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-vsftpd-for-a-users-directory-on-ubuntu-22-04": "How To Set Up vsftpd for a User's Directory on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-fail2ban-on-ubuntu-22-04": "How To Set Up Fail2Ban on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-use-curlie-on-linux": "How To Install and Use Curlie on Linux",
                "https://www.digitalocean.com/community/tutorials/how-to-use-the-linux-auditing-system-on-centos-7": "How To Use the Linux Auditing System on CentOS 7",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-vnc-on-ubuntu-22-04": "How To Install and Configure VNC on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-traceroute-and-mtr-to-diagnose-network-issues": "How To Use Traceroute and MTR to Diagnose Network Issues",
                "https://www.digitalocean.com/community/tutorials/how-to-use-the-linux-fstab-to-mount-filesystems": "How To Use the Linux fstab to Mount Filesystems",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-raid-arrays-with-mdadm-on-ubuntu-22-04": "How To Manage RAID Arrays with mdadm on Ubuntu 22.04",
            },
        },
        "databases": {
            "pages": {
                # MySQL
                "https://www.digitalocean.com/community/tutorials/how-to-install-mysql-on-ubuntu-22-04": "How To Install MySQL on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-secure-mysql-and-mariadb-databases-in-a-linux-vps": "How To Secure MySQL and MariaDB Databases in a Linux VPS",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-remote-database-to-optimize-site-performance-with-mysql-on-ubuntu-22-04": "How To Set Up a Remote Database to Optimize Site Performance with MySQL on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-master-slave-replication-in-mysql": "How To Set Up Master Slave Replication in MySQL",
                "https://www.digitalocean.com/community/tutorials/how-to-create-a-multi-node-mysql-cluster-on-ubuntu-22-04": "How To Create a Multi-Node MySQL Cluster on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-sql-database-cheat-sheet": "How To Manage an SQL Database Cheat Sheet",
                "https://www.digitalocean.com/community/tutorials/sqlite-vs-mysql-vs-postgresql-a-comparison-of-relational-database-management-systems": "SQLite vs MySQL vs PostgreSQL: A Comparison of Relational Database Management Systems",
                "https://www.digitalocean.com/community/tutorials/how-to-create-a-new-user-and-grant-permissions-in-mysql": "How To Create a New User and Grant Permissions in MySQL",
                "https://www.digitalocean.com/community/tutorials/how-to-import-and-export-databases-in-mysql-or-mariadb": "How To Import and Export Databases in MySQL or MariaDB",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-replication-in-mysql": "How To Set Up Replication in MySQL",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-ssl-tls-for-mysql-on-ubuntu-20-04": "How To Configure SSL/TLS for MySQL on Ubuntu 20.04",
                "https://www.digitalocean.com/community/tutorials/how-to-back-up-mysql-databases-on-an-ubuntu-vps": "How To Back Up MySQL Databases on an Ubuntu VPS",
                "https://www.digitalocean.com/community/tutorials/how-to-optimize-mysql-with-query-cache-on-ubuntu-18-04": "How To Optimize MySQL with Query Cache on Ubuntu 18.04",
                # PostgreSQL
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-use-postgresql-on-ubuntu-22-04": "How To Install and Use PostgreSQL on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-use-postgresql-on-ubuntu-20-04": "How To Install and Use PostgreSQL on Ubuntu 20.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-postgresql-with-your-django-application-on-ubuntu-22-04": "How To Use PostgreSQL with Your Django Application on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-create-remove-manage-tables-in-postgresql-on-a-cloud-server": "How To Create, Remove, and Manage Tables in PostgreSQL on a Cloud Server",
                "https://www.digitalocean.com/community/tutorials/how-to-queries-in-postgresql": "How To Queries in PostgreSQL",
                "https://www.digitalocean.com/community/tutorials/how-to-back-up-restore-and-migrate-a-postgresql-database-on-ubuntu-22-04": "How To Back Up, Restore, and Migrate a PostgreSQL Database on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-logical-replication-with-postgresql-on-ubuntu-22-04": "How To Set Up Logical Replication with PostgreSQL on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-roles-and-manage-grant-permissions-in-postgresql-on-a-vps": "How To Use Roles and Manage Grant Permissions in PostgreSQL on a VPS",
                "https://www.digitalocean.com/community/tutorials/how-to-install-postgresql-on-ubuntu-22-04-quickstart": "How To Install PostgreSQL on Ubuntu 22.04 Quickstart",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-physical-streaming-replication-with-postgresql-on-ubuntu-20-04": "How To Set Up Physical Streaming Replication with PostgreSQL on Ubuntu 20.04",
                # MongoDB
                "https://www.digitalocean.com/community/tutorials/how-to-install-mongodb-on-ubuntu-22-04": "How To Install MongoDB on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-back-up-restore-and-migrate-a-mongodb-database-on-ubuntu-20-04": "How To Back Up, Restore, and Migrate a MongoDB Database on Ubuntu 20.04",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-a-mongodb-replica-set-on-ubuntu-20-04": "How To Configure a MongoDB Replica Set on Ubuntu 20.04",
                "https://www.digitalocean.com/community/tutorials/how-to-secure-mongodb-on-ubuntu-22-04": "How To Secure MongoDB on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-perform-crud-operations-in-mongodb": "How To Perform CRUD Operations in MongoDB",
                "https://www.digitalocean.com/community/tutorials/how-to-use-aggregations-in-mongodb": "How To Use Aggregations in MongoDB",
                "https://www.digitalocean.com/community/tutorials/how-to-create-queries-in-mongodb": "How To Create Queries in MongoDB",
                "https://www.digitalocean.com/community/tutorials/how-to-use-indexes-in-mongodb": "How To Use Indexes in MongoDB",
                # Redis
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-secure-redis-on-ubuntu-22-04": "How To Install and Secure Redis on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-redis-databases-and-keys": "How To Manage Redis Databases and Keys",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-redis-replication-on-ubuntu-20-04": "How To Configure Redis Replication on Ubuntu 20.04",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-redis-caching-to-speed-up-wordpress-with-ubuntu-22-04": "How To Configure Redis Caching to Speed Up WordPress with Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-redis-as-a-cache-for-mysql-with-php-on-ubuntu-22-04": "How To Set Up Redis as a Cache for MySQL with PHP on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-connect-to-a-redis-database": "How To Connect to a Redis Database",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-sets-in-redis": "How To Manage Sets in Redis",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-sorted-sets-in-redis": "How To Manage Sorted Sets in Redis",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-hashes-in-redis": "How To Manage Hashes in Redis",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-lists-in-redis": "How To Manage Lists in Redis",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-strings-in-redis": "How To Manage Strings in Redis",
                "https://www.digitalocean.com/community/tutorials/how-to-expire-keys-in-redis": "How To Expire Keys in Redis",
                "https://www.digitalocean.com/community/tutorials/how-to-troubleshoot-issues-in-redis": "How To Troubleshoot Issues in Redis",
                # Elasticsearch
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-elasticsearch-on-ubuntu-22-04": "How To Install and Configure Elasticsearch on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-elasticsearch-logstash-and-kibana-elastic-stack-on-ubuntu-22-04": "How To Install Elasticsearch, Logstash, and Kibana (Elastic Stack) on Ubuntu 22.04",
                # MariaDB
                "https://www.digitalocean.com/community/tutorials/how-to-install-mariadb-on-ubuntu-22-04": "How To Install MariaDB on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-a-galera-cluster-with-mariadb-on-ubuntu-22-04": "How To Configure a Galera Cluster with MariaDB on Ubuntu 22.04",
                # SQLite
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-use-sqlite-on-ubuntu-22-04": "How To Install and Use SQLite on Ubuntu 22.04",
                # Database general
                "https://www.digitalocean.com/community/tutorials/understanding-sql-constraints": "Understanding SQL Constraints",
                "https://www.digitalocean.com/community/tutorials/how-to-use-joins-in-sql": "How To Use Joins in SQL",
                "https://www.digitalocean.com/community/tutorials/introduction-to-queries-in-postgresql": "Introduction to Queries in PostgreSQL",
                "https://www.digitalocean.com/community/tutorials/how-to-use-indexes-in-postgresql": "How To Use Indexes in PostgreSQL",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-and-use-mysql-database-triggers": "How To Manage and Use MySQL Database Triggers",
                "https://www.digitalocean.com/community/tutorials/how-to-use-stored-procedures-in-mysql": "How To Use Stored Procedures in MySQL",
                "https://www.digitalocean.com/community/tutorials/how-to-use-views-in-sql": "How To Use Views in SQL",
                "https://www.digitalocean.com/community/tutorials/how-to-insert-data-in-sql": "How To Insert Data in SQL",
                "https://www.digitalocean.com/community/tutorials/how-to-delete-data-in-sql": "How To Delete Data in SQL",
                "https://www.digitalocean.com/community/tutorials/how-to-update-data-in-sql": "How To Update Data in SQL",
                "https://www.digitalocean.com/community/tutorials/how-to-use-groupby-in-sql": "How To Use GROUP BY in SQL",
                "https://www.digitalocean.com/community/tutorials/how-to-use-subqueries-in-sql": "How To Use Subqueries in SQL",
                "https://www.digitalocean.com/community/tutorials/how-to-work-with-dates-and-times-in-sql": "How To Work with Dates and Times in SQL",
                "https://www.digitalocean.com/community/tutorials/how-to-use-comparison-and-is-null-operators-in-sql": "How To Use Comparison and IS NULL Operators in SQL",
                "https://www.digitalocean.com/community/tutorials/how-to-use-mathematical-expressions-and-aggregate-functions-in-sql": "How To Use Mathematical Expressions and Aggregate Functions in SQL",
                "https://www.digitalocean.com/community/tutorials/how-to-use-where-clauses-in-sql": "How To Use WHERE Clauses in SQL",
            },
        },
        "devops": {
            "pages": {
                # Docker
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-22-04": "How To Install and Use Docker on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-compose-on-ubuntu-22-04": "How To Install and Use Docker Compose on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/the-docker-ecosystem-an-introduction-to-common-components": "The Docker Ecosystem: An Introduction to Common Components",
                "https://www.digitalocean.com/community/tutorials/how-to-remove-docker-images-containers-and-volumes": "How To Remove Docker Images, Containers, and Volumes",
                "https://www.digitalocean.com/community/tutorials/how-to-share-data-between-docker-containers": "How To Share Data Between Docker Containers",
                "https://www.digitalocean.com/community/tutorials/how-to-build-and-deploy-a-flask-application-using-docker-on-ubuntu-20-04": "How To Build and Deploy a Flask Application Using Docker on Ubuntu 20.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-private-docker-registry-on-ubuntu-22-04": "How To Set Up a Private Docker Registry on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-share-data-between-the-docker-container-and-the-host": "How To Share Data Between the Docker Container and the Host",
                "https://www.digitalocean.com/community/tutorials/how-to-use-docker-networking": "How To Use Docker Networking",
                "https://www.digitalocean.com/community/tutorials/how-to-create-a-docker-swarm-on-ubuntu-22-04": "How To Create a Docker Swarm on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-optimize-docker-images-for-production": "How To Optimize Docker Images for Production",
                "https://www.digitalocean.com/community/tutorials/how-to-use-docker-exec-to-run-commands-in-a-docker-container": "How To Use docker exec to Run Commands in a Docker Container",
                "https://www.digitalocean.com/community/tutorials/how-to-use-docker-logs": "How To Use Docker Logs",
                "https://www.digitalocean.com/community/tutorials/docker-explained-using-dockerfiles-to-automate-building-of-images": "Docker Explained: Using Dockerfiles to Automate Building of Images",
                "https://www.digitalocean.com/community/tutorials/how-to-secure-a-containerized-node-js-application-with-nginx-lets-encrypt-and-docker-compose": "How To Secure a Containerized Node.js Application with Nginx, Let's Encrypt, and Docker Compose",
                # Kubernetes
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-kubernetes": "An Introduction to Kubernetes",
                "https://www.digitalocean.com/community/tutorials/how-to-create-a-kubernetes-cluster-using-kubeadm-on-ubuntu-22-04": "How To Create a Kubernetes Cluster Using Kubeadm on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-helm-the-package-manager-for-kubernetes": "An Introduction to Helm, the Package Manager for Kubernetes",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-an-elasticsearch-fluentd-and-kibana-efk-logging-stack-on-kubernetes": "How To Set Up an Elasticsearch, Fluentd, and Kibana (EFK) Logging Stack on Kubernetes",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-cd-pipeline-with-kubernetes-and-github-actions": "How To Set Up a CD Pipeline with Kubernetes and GitHub Actions",
                "https://www.digitalocean.com/community/tutorials/how-to-deploy-a-resilient-go-application-to-digitalocean-kubernetes": "How To Deploy a Resilient Go Application to DigitalOcean Kubernetes",
                "https://www.digitalocean.com/community/tutorials/webinar-series-a-closer-look-at-kubernetes": "Webinar Series: A Closer Look at Kubernetes",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-an-nginx-ingress-on-digitalocean-kubernetes": "How To Set Up an Nginx Ingress on DigitalOcean Kubernetes",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-kubernetes-monitoring-stack-with-prometheus-grafana-and-alertmanager": "How To Set Up a Kubernetes Monitoring Stack with Prometheus, Grafana, and Alertmanager",
                "https://www.digitalocean.com/community/tutorials/how-to-deploy-a-php-application-with-kubernetes-on-ubuntu-18-04": "How To Deploy a PHP Application with Kubernetes on Ubuntu 18.04",
                "https://www.digitalocean.com/community/tutorials/how-to-inspect-kubernetes-networking": "How To Inspect Kubernetes Networking",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-coreos-cluster-with-kubernetes": "How To Set Up a CoreOS Cluster with Kubernetes",
                "https://www.digitalocean.com/community/tutorials/kubernetes-networking-under-the-hood": "Kubernetes Networking Under the Hood",
                # Ansible
                "https://www.digitalocean.com/community/tutorials/how-to-use-ansible-to-automate-initial-server-setup-on-ubuntu-22-04": "How To Use Ansible to Automate Initial Server Setup on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/configuration-management-101-writing-ansible-playbooks": "Configuration Management 101: Writing Ansible Playbooks",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-ansible-on-ubuntu-22-04": "How To Install and Configure Ansible on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-ansible-roles-to-abstract-your-infrastructure-environment": "How To Use Ansible Roles to Abstract Your Infrastructure Environment",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-multistage-environments-with-ansible": "How To Manage Multistage Environments with Ansible",
                "https://www.digitalocean.com/community/tutorials/how-to-use-ansible-vault-to-protect-sensitive-playbook-data": "How To Use Ansible Vault to Protect Sensitive Playbook Data",
                "https://www.digitalocean.com/community/tutorials/how-to-define-and-use-handlers-in-ansible-playbooks": "How To Define and Use Handlers in Ansible Playbooks",
                # Terraform
                "https://www.digitalocean.com/community/tutorials/how-to-use-terraform-with-digitalocean": "How To Use Terraform with DigitalOcean",
                "https://www.digitalocean.com/community/tutorials/how-to-structure-a-terraform-project": "How To Structure a Terraform Project",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-infrastructure-with-terraform": "How To Manage Infrastructure with Terraform",
                "https://www.digitalocean.com/community/tutorials/how-to-create-reusable-infrastructure-with-terraform-modules-and-templates": "How To Create Reusable Infrastructure with Terraform Modules and Templates",
                # CI/CD
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-continuous-integration-pipelines-in-jenkins-on-ubuntu-22-04": "How To Set Up Continuous Integration Pipelines in Jenkins on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/ci-cd-tools-comparison-jenkins-gitlab-ci-buildbot-drone-and-concourse": "CI/CD Tools Comparison: Jenkins, GitLab CI, Buildbot, Drone, and Concourse",
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-ci-cd-best-practices": "An Introduction to CI/CD Best Practices",
                "https://www.digitalocean.com/community/tutorials/how-to-automate-deployment-using-circleci-and-github-on-ubuntu-18-04": "How To Automate Deployment Using CircleCI and GitHub on Ubuntu 18.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-continuous-deployment-pipeline-with-gitlab-ci-cd-on-ubuntu": "How To Set Up a Continuous Deployment Pipeline with GitLab CI/CD on Ubuntu",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-continuous-integration-with-github-actions": "How To Set Up Continuous Integration with GitHub Actions",
                # Monitoring
                "https://www.digitalocean.com/community/tutorials/how-to-install-prometheus-on-ubuntu-22-04": "How To Install Prometheus on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-grafana-to-plot-beautiful-graphs-from-zabbix-on-ubuntu-22-04": "How To Install and Configure Grafana to Plot Beautiful Graphs from Zabbix on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-add-a-prometheus-dashboard-to-grafana": "How To Add a Prometheus Dashboard to Grafana",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-node-js-application-for-production-with-pm2": "How To Set Up a Node.js Application for Production with PM2",
                # Vagrant and Packer
                "https://www.digitalocean.com/community/tutorials/how-to-use-vagrant-on-digitalocean": "How To Use Vagrant on DigitalOcean",
                "https://www.digitalocean.com/community/tutorials/how-to-create-digitalocean-snapshots-using-packer-on-ubuntu-22-04": "How To Create DigitalOcean Snapshots Using Packer on Ubuntu 22.04",
                # Git
                "https://www.digitalocean.com/community/tutorials/how-to-use-git-effectively": "How To Use Git Effectively",
                "https://www.digitalocean.com/community/tutorials/how-to-use-git-branches": "How To Use Git Branches",
                "https://www.digitalocean.com/community/tutorials/how-to-install-git-on-ubuntu-22-04": "How To Install Git on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-open-source": "An Introduction to Open Source",
                # Additional DevOps
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-configuration-management": "An Introduction to Configuration Management",
                "https://www.digitalocean.com/community/tutorials/how-to-use-blue-green-deployments-to-release-software-safely": "How To Use Blue-Green Deployments to Release Software Safely",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-registry-with-harbor-on-ubuntu-22-04": "How To Set Up a Registry with Harbor on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-automate-server-setup-with-cloud-init": "How To Automate Server Setup with Cloud-Init",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-private-docker-registry-on-ubuntu-20-04": "How To Set Up a Private Docker Registry on Ubuntu 20.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-jenkins-on-ubuntu-22-04": "How To Install Jenkins on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-docker-swarm-on-ubuntu-22-04": "How To Set Up Docker Swarm on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-monitor-your-infrastructure-with-prometheus-on-ubuntu-22-04": "How To Monitor Your Infrastructure with Prometheus on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-grafana-on-ubuntu-22-04": "How To Install and Configure Grafana on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-deploy-and-manage-your-dns-using-dnscontrol-on-ubuntu-22-04": "How To Deploy and Manage Your DNS Using DNSControl on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-gitlab-instance-on-ubuntu-22-04": "How To Set Up a GitLab Instance on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-continuous-integration-with-drone-on-ubuntu-22-04": "How To Set Up Continuous Integration with Drone on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-k3s-on-ubuntu-22-04": "How To Set Up K3s on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-create-a-multi-node-docker-swarm-on-ubuntu-22-04": "How To Create a Multi-Node Docker Swarm on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-saltstack-on-ubuntu-22-04": "How To Install and Configure SaltStack on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-sonarqube-server-on-ubuntu-22-04": "How To Set Up a SonarQube Server on Ubuntu 22.04",
            },
        },
        "web-servers": {
            "pages": {
                # Nginx
                "https://www.digitalocean.com/community/tutorials/how-to-install-nginx-on-ubuntu-22-04": "How To Install Nginx on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-secure-nginx-with-let-s-encrypt-on-ubuntu-22-04": "How To Secure Nginx with Let's Encrypt on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-nginx-server-blocks-virtual-hosts-on-ubuntu-22-04": "How To Set Up Nginx Server Blocks (Virtual Hosts) on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/understanding-nginx-http-proxying-load-balancing-buffering-and-caching": "Understanding Nginx HTTP Proxying, Load Balancing, Buffering, and Caching",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-nginx-as-a-reverse-proxy-on-ubuntu-22-04": "How To Configure Nginx as a Reverse Proxy on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/understanding-the-nginx-configuration-file-structure-and-configuration-contexts": "Understanding the Nginx Configuration File Structure and Configuration Contexts",
                "https://www.digitalocean.com/community/tutorials/how-to-create-a-self-signed-ssl-certificate-for-nginx-in-ubuntu-22-04": "How To Create a Self-Signed SSL Certificate for Nginx in Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-optimize-nginx-configuration": "How To Optimize Nginx Configuration",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-nginx-to-use-custom-error-pages-on-ubuntu-22-04": "How To Configure Nginx to Use Custom Error Pages on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-nginx-with-http-2-support-on-ubuntu-22-04": "How To Set Up Nginx with HTTP/2 Support on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-laravel-with-nginx-on-ubuntu-22-04": "How To Install and Configure Laravel with Nginx on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-deploy-a-go-web-application-using-nginx-on-ubuntu-22-04": "How To Deploy a Go Web Application Using Nginx on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-password-authentication-with-nginx-on-ubuntu-22-04": "How To Set Up Password Authentication with Nginx on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-implement-browser-caching-with-nginx-on-ubuntu-22-04": "How To Implement Browser Caching with Nginx on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-nginx-with-ssl-as-a-reverse-proxy-for-jenkins": "How To Configure Nginx with SSL as a Reverse Proxy for Jenkins",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-nginx-load-balancing": "How To Set Up Nginx Load Balancing",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-logging-and-log-rotation-in-nginx-on-an-ubuntu-vps": "How To Configure Logging and Log Rotation in Nginx on an Ubuntu VPS",
                "https://www.digitalocean.com/community/tutorials/how-to-add-the-gzip-module-to-nginx-on-ubuntu-22-04": "How To Add the gzip Module to Nginx on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/nginx-access-logs-and-error-logs": "Nginx Access Logs and Error Logs",
                # Apache
                "https://www.digitalocean.com/community/tutorials/how-to-install-the-apache-web-server-on-ubuntu-22-04": "How To Install the Apache Web Server on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-secure-apache-with-let-s-encrypt-on-ubuntu-22-04": "How To Secure Apache with Let's Encrypt on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-apache-virtual-hosts-on-ubuntu-22-04": "How To Set Up Apache Virtual Hosts on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-apache-http-server-as-reverse-proxy-using-mod-proxy-extension-ubuntu-20-04": "How To Use Apache HTTP Server as Reverse Proxy Using mod_proxy Extension on Ubuntu 20.04",
                "https://www.digitalocean.com/community/tutorials/how-to-rewrite-urls-with-mod-rewrite-for-apache-on-ubuntu-22-04": "How To Rewrite URLs with mod_rewrite for Apache on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/apache-configuration-error-ah00558-could-not-reliably-determine-the-server-s-fully-qualified-domain-name": "Apache Configuration Error AH00558",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-apache-content-caching-on-ubuntu-22-04": "How To Configure Apache Content Caching on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-mod-security-for-apache-on-ubuntu-22-04": "How To Install and Configure mod_security for Apache on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-the-htaccess-file": "How To Use the .htaccess File",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-mod-rewrite-for-apache": "How To Set Up mod_rewrite for Apache",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-apache-http-with-mpm-event-and-php-fpm-on-ubuntu-22-04": "How To Configure Apache HTTP with MPM Event and PHP-FPM on Ubuntu 22.04",
                # Caddy
                "https://www.digitalocean.com/community/tutorials/how-to-host-a-website-using-caddy-on-ubuntu-22-04": "How To Host a Website Using Caddy on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-host-a-website-with-caddy-on-ubuntu-20-04": "How To Host a Website with Caddy on Ubuntu 20.04",
                # HAProxy and load balancing
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-haproxy-and-load-balancing-concepts": "An Introduction to HAProxy and Load Balancing Concepts",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-haproxy-as-a-load-balancer-for-nginx-on-an-ubuntu-vps": "How To Set Up HAProxy as a Load Balancer for Nginx on an Ubuntu VPS",
                "https://www.digitalocean.com/community/tutorials/how-to-implement-ssl-termination-with-haproxy-on-ubuntu-22-04": "How To Implement SSL Termination with HAProxy on Ubuntu 22.04",
                # Varnish
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-varnish-cache-on-ubuntu-22-04": "How To Install and Configure Varnish Cache on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-speed-up-your-website-with-varnish-and-nginx-on-ubuntu-22-04": "How To Speed Up Your Website with Varnish and Nginx on Ubuntu 22.04",
                # SSL/TLS
                "https://www.digitalocean.com/community/tutorials/openssl-essentials-working-with-ssl-certificates-private-keys-and-csrs": "OpenSSL Essentials: Working with SSL Certificates, Private Keys, and CSRs",
                "https://www.digitalocean.com/community/tutorials/a-comparison-of-let-s-encrypt-commercial-and-private-certificate-authorities-and-self-signed-ssl-certificates": "A Comparison of Let's Encrypt, Commercial, and Private Certificate Authorities, and Self-Signed SSL Certificates",
                "https://www.digitalocean.com/community/tutorials/how-to-use-certbot-standalone-mode-to-retrieve-let-s-encrypt-ssl-certificates-on-ubuntu-22-04": "How To Use Certbot Standalone Mode to Retrieve Let's Encrypt SSL Certificates on Ubuntu 22.04",
                # Tomcat
                "https://www.digitalocean.com/community/tutorials/how-to-install-apache-tomcat-10-on-ubuntu-22-04": "How To Install Apache Tomcat 10 on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-apache-tomcat-9-on-ubuntu-20-04": "How To Install Apache Tomcat 9 on Ubuntu 20.04",
                # Gunicorn
                "https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-22-04": "How To Serve Flask Applications with Gunicorn and Nginx on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-uwsgi-and-nginx-on-ubuntu-22-04": "How To Serve Flask Applications with uWSGI and Nginx on Ubuntu 22.04",
                # Web security
                "https://www.digitalocean.com/community/tutorials/how-to-create-a-ssl-certificate-on-nginx-for-ubuntu-22-04": "How To Create an SSL Certificate on Nginx for Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/understanding-http-status-codes": "Understanding HTTP Status Codes",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-node-js-application-for-production-on-ubuntu-20-04": "How To Set Up a Node.js Application for Production on Ubuntu 20.04",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-nginx-as-a-web-server-and-reverse-proxy-for-apache-on-one-ubuntu-22-04-server": "How To Configure Nginx as a Web Server and Reverse Proxy for Apache on One Ubuntu 22.04 Server",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-let-s-encrypt-with-nginx-server-blocks-on-ubuntu-22-04": "How To Set Up Let's Encrypt with Nginx Server Blocks on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-the-apache-web-server-on-an-ubuntu-or-debian-vps": "How To Configure the Apache Web Server on an Ubuntu or Debian VPS",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-openldap-and-phpldapadmin-on-ubuntu-22-04": "How To Install and Configure OpenLDAP and phpLDAPadmin on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-enable-cors-with-nginx": "How To Enable CORS with Nginx",
                "https://www.digitalocean.com/community/tutorials/how-to-redirect-www-to-non-www-with-nginx-on-ubuntu-22-04": "How To Redirect www to Non-www with Nginx on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-nginx-with-google-pagespeed-on-ubuntu-22-04": "How To Set Up Nginx with Google PageSpeed on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-lighttpd-on-ubuntu-22-04": "How To Install and Configure Lighttpd on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-serve-django-applications-with-apache-and-mod-wsgi-on-ubuntu-22-04": "How To Serve Django Applications with Apache and mod_wsgi on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-apache-with-a-free-signed-ssl-certificate-on-a-vps": "How To Set Up Apache with a Free Signed SSL Certificate on a VPS",
            },
        },
        "programming": {
            "pages": {
                # Python
                "https://www.digitalocean.com/community/tutorials/how-to-install-python-3-and-set-up-a-programming-environment-on-ubuntu-22-04": "How To Install Python 3 and Set Up a Programming Environment on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-write-your-first-python-3-program": "How To Write Your First Python 3 Program",
                "https://www.digitalocean.com/community/tutorials/understanding-data-types-in-python-3": "Understanding Data Types in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-use-string-formatters-in-python-3": "How To Use String Formatters in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-use-list-methods-in-python-3": "How To Use List Methods in Python 3",
                "https://www.digitalocean.com/community/tutorials/understanding-dictionaries-in-python-3": "Understanding Dictionaries in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-make-a-web-application-using-flask-in-python-3": "How To Make a Web Application Using Flask in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-deploy-a-flask-application-on-an-ubuntu-vps": "How To Deploy a Flask Application on an Ubuntu VPS",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-flask-with-mongodb-and-docker": "How To Set Up Flask with MongoDB and Docker",
                "https://www.digitalocean.com/community/tutorials/how-to-create-a-django-app-and-connect-it-to-a-database": "How To Create a Django App and Connect It to a Database",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-django-with-postgres-nginx-and-gunicorn-on-ubuntu-22-04": "How To Set Up Django with Postgres, Nginx, and Gunicorn on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-args-and-kwargs-in-python-3": "How To Use *args and **kwargs in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-construct-classes-and-define-objects-in-python-3": "How To Construct Classes and Define Objects in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-use-break-continue-and-pass-statements-when-working-with-loops-in-python-3": "How To Use Break, Continue, and Pass Statements When Working with Loops in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-create-a-twitterbot-with-python-3-and-the-tweepy-library": "How To Create a Twitterbot with Python 3 and the Tweepy Library",
                "https://www.digitalocean.com/community/tutorials/how-to-install-python-3-and-set-up-a-local-programming-environment-on-ubuntu-22-04": "How To Install Python 3 and Set Up a Local Programming Environment on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-the-python-debugger": "How To Use the Python Debugger",
                "https://www.digitalocean.com/community/tutorials/how-to-use-logging-in-python-3": "How To Use Logging in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-use-subprocess-to-run-external-programs-in-python-3": "How To Use subprocess to Run External Programs in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-define-functions-in-python-3": "How To Define Functions in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-use-asyncio-in-python": "How To Use asyncio in Python",
                "https://www.digitalocean.com/community/tutorials/how-to-build-a-machine-learning-classifier-in-python-with-scikit-learn": "How To Build a Machine Learning Classifier in Python with Scikit-Learn",
                # Node.js
                "https://www.digitalocean.com/community/tutorials/how-to-install-node-js-on-ubuntu-22-04": "How To Install Node.js on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-node-js-modules-with-npm-and-package-json": "How To Use Node.js Modules with npm and package.json",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-node-js-application-for-production-on-ubuntu-22-04": "How To Set Up a Node.js Application for Production on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-build-a-node-js-application-with-docker": "How To Build a Node.js Application with Docker",
                "https://www.digitalocean.com/community/tutorials/how-to-create-a-web-server-in-node-js-with-the-http-module": "How To Create a Web Server in Node.js with the HTTP Module",
                "https://www.digitalocean.com/community/tutorials/how-to-write-asynchronous-code-in-node-js": "How To Write Asynchronous Code in Node.js",
                "https://www.digitalocean.com/community/tutorials/how-to-use-the-node-js-repl": "How To Use the Node.js REPL",
                "https://www.digitalocean.com/community/tutorials/how-to-write-and-run-your-first-program-in-node-js": "How To Write and Run Your First Program in Node.js",
                "https://www.digitalocean.com/community/tutorials/how-to-test-a-node-js-module-with-mocha-and-assert": "How To Test a Node.js Module with Mocha and Assert",
                # Go
                "https://www.digitalocean.com/community/tutorials/how-to-install-go-on-ubuntu-22-04": "How To Install Go on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-build-go-executables-for-multiple-platforms-on-ubuntu-20-04": "How To Build Go Executables for Multiple Platforms on Ubuntu 20.04",
                "https://www.digitalocean.com/community/tutorials/how-to-build-and-install-go-programs": "How To Build and Install Go Programs",
                "https://www.digitalocean.com/community/tutorials/how-to-use-go-modules": "How To Use Go Modules",
                "https://www.digitalocean.com/community/tutorials/how-to-write-unit-tests-in-go": "How To Write Unit Tests in Go",
                "https://www.digitalocean.com/community/tutorials/how-to-use-interfaces-in-go": "How To Use Interfaces in Go",
                "https://www.digitalocean.com/community/tutorials/how-to-use-contexts-in-go": "How To Use Contexts in Go",
                # Ruby/Rails
                "https://www.digitalocean.com/community/tutorials/how-to-install-ruby-on-rails-with-rbenv-on-ubuntu-22-04": "How To Install Ruby on Rails with rbenv on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-ruby-on-rails-with-rvm-on-ubuntu-22-04": "How To Install Ruby on Rails with RVM on Ubuntu 22.04",
                # PHP
                "https://www.digitalocean.com/community/tutorials/how-to-install-linux-apache-mysql-php-lamp-stack-on-ubuntu-22-04": "How To Install Linux, Apache, MySQL, PHP (LAMP) Stack on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-use-composer-on-ubuntu-22-04": "How To Install and Use Composer on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-php-8-1-and-set-up-a-local-development-environment-on-ubuntu-22-04": "How To Install PHP 8.1 and Set Up a Local Development Environment on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-linux-nginx-mysql-php-lemp-stack-on-ubuntu-22-04": "How To Install Linux, Nginx, MySQL, PHP (LEMP Stack) on Ubuntu 22.04",
                # Java
                "https://www.digitalocean.com/community/tutorials/how-to-install-java-with-apt-on-ubuntu-22-04": "How To Install Java with Apt on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-manage-supervisor-on-ubuntu-and-debian-vps": "How To Install and Manage Supervisor on Ubuntu and Debian VPS",
                # TypeScript
                "https://www.digitalocean.com/community/tutorials/how-to-use-modules-in-typescript": "How To Use Modules in TypeScript",
                "https://www.digitalocean.com/community/tutorials/how-to-use-classes-in-typescript": "How To Use Classes in TypeScript",
                "https://www.digitalocean.com/community/tutorials/how-to-use-generics-in-typescript": "How To Use Generics in TypeScript",
                "https://www.digitalocean.com/community/tutorials/how-to-use-enums-in-typescript": "How To Use Enums in TypeScript",
                # React / Vue / Next.js
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-react-project-with-create-react-app": "How To Set Up a React Project with Create React App",
                "https://www.digitalocean.com/community/tutorials/how-to-build-a-react-to-do-app-with-react-hooks": "How To Build a React To-Do App with React Hooks",
                "https://www.digitalocean.com/community/tutorials/how-to-call-web-apis-with-the-useeffect-hook-in-react": "How To Call Web APIs with the useEffect Hook in React",
                "https://www.digitalocean.com/community/tutorials/how-to-develop-a-vue-js-single-page-application": "How To Develop a Vue.js Single Page Application",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-next-js-project": "How To Set Up a Next.js Project",
                # Rust
                "https://www.digitalocean.com/community/tutorials/how-to-install-rust-on-ubuntu-22-04": "How To Install Rust on Ubuntu 22.04",
                # Django REST / FastAPI
                "https://www.digitalocean.com/community/tutorials/how-to-build-a-to-do-application-using-django-and-react-on-ubuntu-22-04": "How To Build a To-Do Application Using Django and React on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-create-django-models": "How To Create Django Models",
                "https://www.digitalocean.com/community/tutorials/how-to-create-django-views": "How To Create Django Views",
                "https://www.digitalocean.com/community/tutorials/how-to-create-a-self-signed-ssl-certificate-for-nginx-on-centos-7": "How To Create a Self-Signed SSL Certificate for Nginx on CentOS 7",
                # Python virtualenv
                "https://www.digitalocean.com/community/tutorials/how-to-install-python-3-and-set-up-a-programming-environment-on-an-ubuntu-22-04-server": "How To Install Python 3 and Set Up a Programming Environment on an Ubuntu 22.04 Server",
                "https://www.digitalocean.com/community/tutorials/common-python-tools-using-virtualenv-installing-with-pip-and-managing-packages": "Common Python Tools: Using virtualenv, Installing with Pip, and Managing Packages",
                "https://www.digitalocean.com/community/tutorials/how-to-use-map-filter-and-reduce-in-python-3": "How To Use map, filter, and reduce in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-handle-errors-in-python": "How To Handle Errors in Python",
                "https://www.digitalocean.com/community/tutorials/how-to-import-modules-in-python-3": "How To Import Modules in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-do-math-in-python-3-with-operators": "How To Do Math in Python 3 with Operators",
                "https://www.digitalocean.com/community/tutorials/how-to-use-variables-in-python-3": "How To Use Variables in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-write-comments-in-python-3": "How To Write Comments in Python 3",
                "https://www.digitalocean.com/community/tutorials/understanding-class-inheritance-in-python-3": "Understanding Class Inheritance in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-port-python-2-code-to-python-3": "How To Port Python 2 Code to Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-use-decorators-in-python": "How To Use Decorators in Python",
                "https://www.digitalocean.com/community/tutorials/how-to-convert-data-types-in-python-3": "How To Convert Data Types in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-index-and-slice-strings-in-python-3": "How To Index and Slice Strings in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-use-the-collections-module-in-python-3": "How To Use the collections Module in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-read-and-write-files-in-python-3": "How To Read and Write Files in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-package-and-distribute-python-applications": "How To Package and Distribute Python Applications",
            },
        },
        "cloud": {
            "pages": {
                # Cloud fundamentals
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-cloud-computing": "An Introduction to Cloud Computing",
                "https://www.digitalocean.com/community/tutorials/how-to-create-your-first-digitalocean-droplet": "How To Create Your First DigitalOcean Droplet",
                "https://www.digitalocean.com/community/tutorials/how-to-use-floating-ips-on-digitalocean": "How To Use Floating IPs on DigitalOcean",
                "https://www.digitalocean.com/community/tutorials/how-to-automate-the-scaling-of-your-web-application-on-digitalocean-1804": "How To Automate the Scaling of Your Web Application on DigitalOcean",
                # Networking
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-and-use-digitalocean-private-networking": "How To Set Up and Use DigitalOcean Private Networking",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-dns-round-robin-load-balancing-for-high-availability": "How To Configure DNS Round-Robin Load Balancing for High Availability",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-highly-available-haproxy-servers-with-keepalived-and-floating-ips-on-ubuntu-14-04": "How To Set Up Highly Available HAProxy Servers with Keepalived and Floating IPs on Ubuntu 14.04",
                "https://www.digitalocean.com/community/tutorials/how-to-use-haproxy-to-set-up-http-load-balancing-on-an-ubuntu-vps": "How To Use HAProxy to Set Up HTTP Load Balancing on an Ubuntu VPS",
                # DigitalOcean services
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-digitalocean-spaces": "An Introduction to DigitalOcean Spaces",
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-digitalocean-cloud-firewalls": "An Introduction to DigitalOcean Cloud Firewalls",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-digitalocean-volumes": "How To Manage DigitalOcean Volumes",
                "https://www.digitalocean.com/community/tutorials/understanding-digitalocean-droplet-backups": "Understanding DigitalOcean Droplet Backups",
                "https://www.digitalocean.com/community/tutorials/how-to-back-up-your-digitalocean-droplets-using-snapshots": "How To Back Up Your DigitalOcean Droplets Using Snapshots",
                "https://www.digitalocean.com/community/tutorials/how-to-create-an-inexpensive-cdn-using-digitalocean-spaces": "How To Create an Inexpensive CDN Using DigitalOcean Spaces",
                # DNS
                "https://www.digitalocean.com/community/tutorials/how-to-point-to-digitalocean-nameservers-from-common-domain-registrars": "How To Point to DigitalOcean Nameservers from Common Domain Registrars",
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-dns-terminology-components-and-concepts": "An Introduction to DNS Terminology, Components, and Concepts",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-host-name-with-digitalocean": "How To Set Up a Host Name with DigitalOcean",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-a-cname-record": "How To Configure a CNAME Record",
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-managing-dns": "An Introduction to Managing DNS",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-and-test-dns-subdomains-with-digitalocean-s-dns-panel": "How To Set Up and Test DNS Subdomains with DigitalOcean's DNS Panel",
                # VPC and networking
                "https://www.digitalocean.com/community/tutorials/understanding-digitalocean-vpc-networks": "Understanding DigitalOcean VPC Networks",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-a-digitalocean-vpc-network": "How To Configure a DigitalOcean VPC Network",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-firewall-using-firewalld-on-centos-7": "How To Set Up a Firewall Using firewalld on CentOS 7",
                # Object storage
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-object-storage-with-digitalocean-spaces-and-aws-sdk-for-python": "How To Set Up Object Storage with DigitalOcean Spaces and AWS SDK for Python",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-digitalocean-spaces-with-the-official-cli-tool-s3cmd": "How To Manage DigitalOcean Spaces with the Official CLI Tool s3cmd",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-digitalocean-spaces-cdn-endpoint": "How To Set Up a DigitalOcean Spaces CDN Endpoint",
                # API and automation
                "https://www.digitalocean.com/community/tutorials/how-to-use-the-digitalocean-api-v2": "How To Use the DigitalOcean API v2",
                "https://www.digitalocean.com/community/tutorials/how-to-use-doctl-the-official-digitalocean-command-line-client": "How To Use doctl, the Official DigitalOcean Command-Line Client",
                "https://www.digitalocean.com/community/tutorials/how-to-work-with-digitalocean-load-balancers": "How To Work with DigitalOcean Load Balancers",
                # High availability and disaster recovery
                "https://www.digitalocean.com/community/tutorials/what-is-high-availability": "What is High Availability",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-highly-available-web-servers-with-keepalived-and-floating-ips-on-ubuntu-14-04": "How To Set Up Highly Available Web Servers with Keepalived and Floating IPs on Ubuntu 14.04",
                "https://www.digitalocean.com/community/tutorials/how-to-create-redundancy-and-high-availability-with-heartbeat-and-floating-ips-on-ubuntu-16-04": "How To Create Redundancy and High Availability with Heartbeat and Floating IPs on Ubuntu 16.04",
                "https://www.digitalocean.com/community/tutorials/building-for-production-web-applications-overview": "Building for Production: Web Applications Overview",
                "https://www.digitalocean.com/community/tutorials/building-for-production-web-applications-deploying": "Building for Production: Web Applications Deploying",
                "https://www.digitalocean.com/community/tutorials/building-for-production-web-applications-monitoring": "Building for Production: Web Applications Monitoring",
                "https://www.digitalocean.com/community/tutorials/building-for-production-web-applications-recovery-planning": "Building for Production: Web Applications Recovery Planning",
                # Monitoring and metrics
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-zabbix-to-securely-monitor-remote-servers-on-ubuntu-22-04": "How To Install and Configure Zabbix to Securely Monitor Remote Servers on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-gather-infrastructure-metrics-with-metricbeat-on-ubuntu-22-04": "How To Gather Infrastructure Metrics with Metricbeat on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-monitor-server-health-with-checkmk-on-ubuntu-22-04": "How To Monitor Server Health with Checkmk on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-metrics-monitoring-and-alerting": "An Introduction to Metrics, Monitoring, and Alerting",
                # Additional cloud topics
                "https://www.digitalocean.com/community/tutorials/how-to-choose-a-redundancy-plan-to-ensure-high-availability": "How To Choose a Redundancy Plan to Ensure High Availability",
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-oauth-2": "An Introduction to OAuth 2",
                "https://www.digitalocean.com/community/tutorials/understanding-database-sharding": "Understanding Database Sharding",
                "https://www.digitalocean.com/community/tutorials/an-introduction-to-load-testing": "An Introduction to Load Testing",
                "https://www.digitalocean.com/community/tutorials/how-to-use-web-apis-in-python-3": "How To Use Web APIs in Python 3",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-scalable-mongodb-database": "How To Set Up a Scalable MongoDB Database",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-multi-node-ceph-cluster-on-ubuntu-22-04": "How To Set Up a Multi-Node Ceph Cluster on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-production-elasticsearch-cluster-on-ubuntu-22-04": "How To Set Up a Production Elasticsearch Cluster on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-master-slave-replication-on-postgresql-on-an-ubuntu-vps": "How To Set Up Master Slave Replication on PostgreSQL on an Ubuntu VPS",
                "https://www.digitalocean.com/community/tutorials/how-to-configure-ssl-tls-for-postgresql-on-ubuntu-22-04": "How To Configure SSL/TLS for PostgreSQL on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-digitalocean-projects": "How To Manage DigitalOcean Projects",
                "https://www.digitalocean.com/community/tutorials/5-common-server-setups-for-your-web-application": "5 Common Server Setups for Your Web Application",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-remote-desktop-with-x2go-on-ubuntu-22-04": "How To Set Up a Remote Desktop with X2Go on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-firewall-with-firewalld-on-rocky-linux-9": "How To Set Up a Firewall with firewalld on Rocky Linux 9",
                "https://www.digitalocean.com/community/tutorials/how-to-use-digitalocean-custom-images": "How To Use DigitalOcean Custom Images",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-two-node-high-availability-cluster-with-corosync-pacemaker-and-floating-ips-on-ubuntu-14-04": "How To Set Up a Two-Node HA Cluster with Corosync, Pacemaker, and Floating IPs on Ubuntu 14.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-and-use-digitalocean-app-platform": "How To Set Up and Use DigitalOcean App Platform",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-wireguard-on-ubuntu-20-04": "How To Set Up WireGuard on Ubuntu 20.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-an-openvpn-server-on-ubuntu-22-04": "How To Set Up an OpenVPN Server on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-install-nagios-4-and-monitor-your-servers-on-ubuntu-22-04": "How To Install Nagios 4 and Monitor Your Servers on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-manage-logfiles-with-logrotate-on-ubuntu-22-04": "How To Manage Logfiles with Logrotate on Ubuntu 22.04",
                "https://www.digitalocean.com/community/tutorials/how-to-set-up-a-minecraft-server-on-linux": "How To Set Up a Minecraft Server on Linux",
                "https://www.digitalocean.com/community/tutorials/how-to-install-wordpress-on-ubuntu-22-04-with-a-lamp-stack": "How To Install WordPress on Ubuntu 22.04 with a LAMP Stack",
                "https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-20-04": "How To Install and Use Docker on Ubuntu 20.04",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"digitalocean-{source_key}" if source_key else "digitalocean"
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
            for suffix in [' | DigitalOcean', ' - DigitalOcean', ' :: DigitalOcean']:
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
                        "category": f"digitalocean-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(2.0)

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
            self.log.info(f"=== Scraping digitalocean/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    DigitalOceanScraper(base, source_key).run()
