# Disseminator CI/CD → Ansible Tower Integration

**Analysis Date:** 2026-06-16  
**Purpose:** Document how GitLab CI/CD integrates with Ansible Tower (AWX) for Disseminator deployments

---

## Executive Summary

**Integration Flow:**
```
GitLab CI/CD (.gitlab-ci.yml)
    ↓ (builds JAR)
    ↓ (uploads to Nexus)
    ↓ (triggers Ansible Tower via AWX API)
    ↓
Ansible Tower (tower-playbooks repo)
    ↓ (executes playbooks)
    ↓ (downloads from Nexus)
    ↓ (deploys to 47 servers)
    ↓
Production (qa/stage/prod environments)
```

**Two GitLab Repositories:**
1. **search-engineering/disseminator** (application code + CI/CD)
2. **customer-platform/tower-playbooks** (Ansible automation)

---

## 1. GitLab CI/CD Pipeline (.gitlab-ci.yml)

### 1.1 Pipeline Stages

**Location:** `/exports/deep-research/search-engineering/disseminator/.gitlab-ci.yml`

```yaml
stages:
  - sync_base_image
  - build                    # Build JAR with Maven
  - deploy_lib               # Deploy libraries (resources only)
  - deploy_solr              # Deploy Solr plugin
  - deploy_camel             # Deploy main Camel JAR
  - compute_values
  - extract_jiras            # Extract JIRA tickets from commits
  - jira_updates
  - deploy_qa                # Deploy to QA environment
  - jira_updates_qa
  - deploy_stage             # Deploy to Stage environment
  - jira_updates_stage
  - deploy_prod              # Deploy to Production environment
  - jira_updates_prod
  - qe_tests
  - pages
  - recrawl_schedule
  - test
```

### 1.2 Build Phase

**What happens:**
1. **Build JAR:** `mvn clean install -DskipTests=true`
2. **Build RPMs:** `mvn rpm:rpm` (Solr plugin + libraries)
3. **Upload to Nexus:**
   ```bash
   mvn deploy  # Uploads disseminator-{version}.jar
   
   # Upload RPMs
   curl -u ${DXP_NEXUS_USER}:${DXP_NEXUS_PASSWORD} \
     --upload-file ${RPM_FILE} \
     https://nexus.corp.redhat.com/repository/information-retrieval-yum-releases/
   ```

**Artifacts Uploaded:**
- `disseminator-{version}.jar` → Nexus Maven repository
- `lib-{version}.tar.gz` → Nexus raw repository
- `solr-plugin-{version}.jar` → Nexus Maven repository
- `*.rpm` files → Nexus YUM repository

### 1.3 Deploy Phase (Ansible Tower Integration)

**Template Job:** `.deploy` (lines 300-313)

```yaml
.deploy:
  image: images.paas.redhat.com/dat/disseminator-base-image:latest
  allow_failure: false
  timeout: 2h
  retry:
    max: 2
    when:
      - script_failure
  variables:
    ANSIBLE_CONTROLLER_HOST: "$DXP_DEVOPS_TOWER_HOST"
    ANSIBLE_CONTROLLER_USERNAME: "$DXP_DEVOPS_TOWER_USER"
    ANSIBLE_CONTROLLER_PASSWORD: "$DXP_DEVOPS_TOWER_TOKEN_Original"
    ANSIBLE_TOWER_HOST: "$DXP_DEVOPS_TOWER_HOST"
    ANSIBLE_TOWER_USERNAME: "$DXP_DEVOPS_TOWER_USER"
    ANSIBLE_TOWER_PASSWORD: "$DXP_DEVOPS_TOWER_TOKEN_Original"
  script:
    - |
      ansible-playbook -vvv -i localhost, -c local ansible/deploy.yml \
        -e "controller_host=$DXP_DEVOPS_TOWER_HOST" \
        -e "controller_username=$DXP_DEVOPS_TOWER_USER" \
        -e "controller_password=$DXP_DEVOPS_TOWER_TOKEN_Original" \
        -e "template_name=disseminator-deploy-$DEPLOY_NODE_TYPE" \
        -e "inventory_name='$DEPLOY_ENV $INVENTORY_NAME'" \
        -e "target_version=$DEPLOY_VERSION"
```

**Key Variables:**
- `$DEPLOY_NODE_TYPE`: `camel`, `camel-lib`, `solr`, `configsets`
- `$DEPLOY_ENV`: `qa`, `stage`, `prod`
- `$INVENTORY_NAME`: `Disseminator-Camel-Nodes`, `Disseminator-Solr-Nodes`
- `$DEPLOY_VERSION`: Version to deploy (e.g., `2.475`)

**What This Does:**
1. Runs local Ansible playbook `ansible/deploy.yml`
2. Playbook calls Ansible Tower (AWX) API
3. Tower executes job template on remote servers
4. Wait for completion (timeout: 2h)

---

## 2. Ansible Tower API Integration

### 2.1 AWX Job Launch Playbook

**Location:** `/exports/deep-research/search-engineering/disseminator/ansible/deploy.yml`

```yaml
---
- name: Launch AWX Deployment Job
  hosts: localhost
  gather_facts: false
  collections:
    - awx.awx

  tasks:
    - name: Trigger the Job Template
      awx.awx.job_launch:
        controller_host: "{{ controller_host }}"
        controller_username: "{{ controller_username | default(omit) }}"
        controller_password: "{{ controller_password | default(omit) }}"
        controller_oauthtoken: "{{ controller_oauthtoken | default(omit) }}"
        validate_certs: false
        job_template: "{{ template_name }}"
        inventory: "{{ inventory_name }}"
        wait: yes
        timeout: 2700
        extra_vars:
          version: "{{ target_version | string }}"
      register: job_launch_result
```

**Parameters Passed:**
- **controller_host:** Ansible Tower hostname (from `$DXP_DEVOPS_TOWER_HOST`)
- **controller_username:** Tower username
- **controller_password:** Tower API token
- **job_template:** Tower job template name (e.g., `disseminator-deploy-camel`)
- **inventory:** Tower inventory (e.g., `qa Disseminator-Camel-Nodes`)
- **extra_vars.version:** Version to deploy (e.g., `2.475`)
- **wait:** `yes` (block until job completes)
- **timeout:** 2700 seconds (45 minutes)

### 2.2 Tower Job Templates

**Job Templates in Ansible Tower (inferred from CI/CD):**

| Template Name | Purpose | Playbook (tower-playbooks) |
|---------------|---------|---------------------------|
| `disseminator-deploy-camel` | Deploy main Camel JAR | `disseminator_deploy_camel.yml` |
| `disseminator-deploy-camel-lib` | Deploy libraries only | `disseminator_deploy_camel_lib.yml` |
| `disseminator-deploy-solr` | Deploy Solr plugin | `disseminator_deploy_solr.yml` |
| `disseminator-deploy-configsets` | Deploy Solr configsets | `disseminator_deploy_configsets.yml` |
| `disseminator-stop-indexing-camel` | Stop indexing routes | `disseminator_stop_indexing_camel.yml` |

**Inventory Names in Tower:**
- `qa Disseminator-Camel-Nodes`
- `qa Disseminator-Solr-Nodes`
- `stage Disseminator-Camel-Nodes`
- `stage Disseminator-Solr-Nodes`
- `prod Disseminator-Camel-Nodes`
- `prod Disseminator-Solr-Nodes`

---

## 3. Deployment Workflow (End-to-End)

### 3.1 QA Deployment

**GitLab CI/CD Job:** `deploy_qa`

```yaml
deploy_qa:
  extends: .deploy
  stage: deploy_qa
  variables:
    DEPLOY_VERSION: $VERSION
    DEPLOY_ENV: qa
    DEPLOY_NODE_TYPE: camel
    INVENTORY_NAME: Disseminator-Camel-Nodes
  needs:
    - build_job
    - extract_jira
  rules:
    - if: '$START_AT_STAGE == "all" || $START_AT_STAGE == "starting_at_qa"'
      when: on_success
```

**Execution Flow:**
```
1. GitLab CI/CD triggers
   └─ ansible-playbook ansible/deploy.yml
      └─ awx.awx.job_launch
         └─ POST https://$DXP_DEVOPS_TOWER_HOST/api/v2/job_templates/disseminator-deploy-camel/launch/
            ├─ Inventory: "qa Disseminator-Camel-Nodes"
            ├─ Extra vars: {"version": "2.475"}
            └─ Wait for completion

2. Ansible Tower receives API call
   └─ Executes playbook: disseminator_deploy_camel.yml
      └─ Hosts: qa Disseminator-Camel-Nodes (e.g., 3 servers)
      └─ Serial: 1 (one server at a time)
      └─ Roles:
         ├─ disable_ec2_target (remove from ALB)
         ├─ disseminator_stop (stop services)
         ├─ disseminator_deploy_camel (download JAR from Nexus)
         ├─ disseminator_deploy_camel_lib (download libs)
         ├─ disseminator_deploy_configs_camel (template configs)
         ├─ portal_signals (deploy Adobe keys)
         ├─ disseminator_start (start services)
         └─ enable_ec2_target (return to ALB)

3. Tower playbook downloads from Nexus
   └─ get_url:
        url: https://nexus.corp.redhat.com/repository/cee-raw-hosted/org/flossware/disseminator/2.475/disseminator-2.475.jar
        dest: /opt/disseminator/disseminator.jar

4. Tower playbook completes
   └─ Returns status to GitLab CI/CD

5. GitLab CI/CD continues
   └─ jira_updates_qa stage (update JIRA tickets)
```

### 3.2 Stage Deployment

**GitLab CI/CD Job:** `deploy_stage`

```yaml
deploy_stage:
  extends: .deploy
  stage: deploy_stage
  variables:
    DEPLOY_VERSION: $VERSION
    DEPLOY_ENV: stage
    DEPLOY_NODE_TYPE: camel
    INVENTORY_NAME: Disseminator-Camel-Nodes
  needs:
    - deploy_qa
    - jira_updates_qa
  rules:
    - if: '$START_AT_STAGE == "all" || $START_AT_STAGE == "starting_at_stage"'
      when: manual  # Manual approval required
```

**Same flow as QA, but:**
- Inventory: `stage Disseminator-Camel-Nodes`
- Manual approval required (safety gate)

### 3.3 Production Deployment

**GitLab CI/CD Job:** `deploy_prod`

```yaml
deploy_prod:
  extends: .deploy
  stage: deploy_prod
  variables:
    DEPLOY_VERSION: $VERSION
    DEPLOY_ENV: prod
    DEPLOY_NODE_TYPE: camel
    INVENTORY_NAME: Disseminator-Camel-Nodes
  needs:
    - deploy_stage
    - jira_updates_stage
  rules:
    - if: '$START_AT_STAGE == "all" || $START_AT_STAGE == "starting_at_prod"'
      when: manual  # Manual approval required
```

**Same flow as QA/Stage, but:**
- Inventory: `prod Disseminator-Camel-Nodes` (14 production servers)
- Manual approval required (critical safety gate)
- Zero-downtime deployment (serial: 1, ALB coordination)

---

## 4. Library-Only Deployment (Config Changes)

### 4.1 When It Triggers

**GitLab CI/CD Rule:**
```yaml
deploy_lib_artifact_qa:
  extends: .deploy
  stage: deploy_lib
  rules:
    - if: '$CI_COMMIT_BRANCH == $DEPLOY_FROM_BRANCH'
      changes:
        - src/main/resources/*.txt       # NLP models
        - src/main/resources/*.xml       # Spring configs
        - src/main/resources/profiles/** # Environment profiles
        - src/main/resources/nlpmodel/** # NLP models
      when: manual
```

**Use Case:** Deploy ONLY configuration/resource changes without rebuilding main JAR

**Workflow:**
1. Detect changes in `src/main/resources/`
2. Build library tarball: `lib-{version}.tar.gz`
3. Upload to Nexus
4. Trigger Tower job template: `disseminator-deploy-camel-lib`
5. Tower executes: `disseminator_deploy_camel_lib.yml`
6. Downloads `lib-{version}.tar.gz` from Nexus
7. Extracts to `/opt/disseminator/lib/`
8. Restarts services

**Benefit:** Faster deployment for config-only changes (no full JAR rebuild)

---

## 5. Stop Indexing Integration

### 5.1 Stop Indexing Playbook

**Location:** `/exports/deep-research/search-engineering/disseminator/ansible/stop_indexing.yml`

**Purpose:** Stop Camel indexing routes before deployment to prevent data corruption

**GitLab CI/CD Job:** `.stop_indexing`

```yaml
.stop_indexing:
  allow_failure: true  # Allow deployment to continue if AAP is unreachable
  timeout: 2h
  retry:
    max: 2
    when:
      - script_failure
  script:
    - |
      ansible-playbook -vvv -i localhost, -c local ansible/stop_indexing.yml \
        -e "controller_host=$DXP_DEVOPS_TOWER_HOST" \
        -e "controller_username=$DXP_DEVOPS_TOWER_USER" \
        -e "controller_password=$DXP_DEVOPS_TOWER_TOKEN_Original" \
        -e "template_name=disseminator-stop-indexing-$DEPLOY_NODE_TYPE" \
        -e "inventory_name='${DEPLOY_ENV} ${INVENTORY_NAME}'"
```

**Tower Job Template:** `disseminator-stop-indexing-camel`  
**Tower Playbook:** `disseminator_stop_indexing_camel.yml`

**What It Does:**
1. Calls Tower API to execute stop_indexing playbook
2. Tower executes `disseminator_stop_index_routes` role
3. Role POSTs to Spring Actuator endpoint: `http://localhost:8080/actuator/route/stop`
4. Camel routes stop gracefully
5. Deployment can proceed safely

**Error Handling:** `allow_failure: true` (deployment continues even if Tower is unreachable)

---

## 6. Version Management

### 6.1 Version Determination

**Two Sources:**

1. **Automatic (from git log):**
   ```bash
   VERSION=$(git log --pretty=format:"%s" --grep="Automated Version Bump" -n 1 | grep -oE '[0-9]+\.[0-9]+')
   ```

2. **Manual (from pipeline input):**
   ```yaml
   spec:
     inputs:
       deploy_version:
         default: ""
         description: "OPTIONAL: Enter the version string to release (e.g., 2.475)"
   ```

**Validation:**
```bash
# Version format: major.minor (e.g., 2.475)
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: Invalid VERSION format"
  exit 1
fi

# Reject leading zeros
if [[ "$VERSION" =~ ^0[0-9] ]] || [[ "$VERSION" =~ \.[0-9]*0[0-9] ]]; then
  echo "ERROR: Leading zeros not allowed"
  exit 1
fi
```

### 6.2 Version Flow

```
1. Developer commits code
2. GitLab CI/CD builds JAR
3. Maven increments version (build-helper:parse-version)
4. Git commit: "Automated Version Bump to X.Y"
5. JAR uploaded to Nexus as disseminator-X.Y.jar
6. Git tag created: disseminator-X.Y
7. Tower downloads disseminator-X.Y.jar from Nexus
8. Deployed to servers
```

---

## 7. JIRA Integration

### 7.1 JIRA Ticket Extraction

**Stage:** `extract_jira`

```bash
# Get last deployed version from API
PASSED_DEPLOY_TAG=$(curl -s "$VERSION_API_ENDPOINT" | grep -oP '"disseminator"\s*:\s*"\K[^"]+')

# Extract JIRA tickets from commits since last deploy
JIRA_TICKETS=$(git log "${PASSED_DEPLOY_TAG}..HEAD" --pretty=format:%s \
  | grep -oE 'CPSEARCH-[0-9]+' | sort -u | tr '\n' ' ')
```

**Output:** Space-separated JIRA ticket list (e.g., `CPSEARCH-1234 CPSEARCH-5678`)

### 7.2 JIRA Updates

**Stages:**
- `jira_updates_qa` — Comment on JIRA tickets after QA deployment
- `jira_updates_stage` — Comment on JIRA tickets after Stage deployment
- `jira_updates_prod` — Comment on JIRA tickets after Prod deployment

**Comment Format:**
```
Deployed to QA (version 2.475)
Deployed to Stage (version 2.475)
Deployed to Production (version 2.475)
```

**Purpose:** Automatic JIRA updates for release tracking

---

## 8. Deployment Modes

### 8.1 Mode Options

**Input:** `start_at_stage`

| Mode | Description | Stages Executed |
|------|-------------|-----------------|
| `all` | Full pipeline (default) | build → qa → stage → prod (with manual gates) |
| `starting_at_qa` | Skip build, deploy from existing version | qa → stage → prod |
| `starting_at_stage` | Skip build and qa | stage → prod |
| `starting_at_prod` | Deploy only to prod | prod only |
| `only_qa` | Deploy ONLY to qa | qa only |
| `only_stage` | Deploy ONLY to stage | stage only |
| `only_prod` | Deploy ONLY to prod | prod only |

**Use Cases:**
- `all`: Normal commit-triggered deployment
- `starting_at_qa`: Redeploy existing version (e.g., rollback)
- `only_prod`: Emergency hotfix to production only

### 8.2 Manual vs Automatic

**Automatic:**
- QA deployment (if `START_AT_STAGE == "all"`)
- Build on commit to `main` branch

**Manual Approval Required:**
- Stage deployment (always manual)
- Production deployment (always manual)
- Library-only deployments (always manual)

---

## 9. Error Handling & Retries

### 9.1 Retry Logic

**Deploy Jobs:**
```yaml
retry:
  max: 2
  when:
    - script_failure
```

**Timeout:**
- Deploy: 2 hours
- Stop Indexing: 2 hours
- Tower job execution: 45 minutes (2700 seconds)

### 9.2 Failure Modes

**Allowed Failures:**
- `stop_indexing`: `allow_failure: true` (deployment continues)

**Critical Failures (stop pipeline):**
- Build failure
- Nexus upload failure
- QA deployment failure (blocks stage/prod)
- Stage deployment failure (blocks prod)

---

## 10. Security

### 10.1 Secrets Management

**GitLab CI/CD Variables (masked):**
- `$DXP_DEVOPS_TOWER_HOST` — Ansible Tower hostname
- `$DXP_DEVOPS_TOWER_USER` — Tower API username
- `$DXP_DEVOPS_TOWER_TOKEN_Original` — Tower API token
- `$DXP_NEXUS_USER` — Nexus username
- `$DXP_NEXUS_PASSWORD` — Nexus password
- `$JIRA_AUTH_TOKEN` — JIRA API token
- `$SONAR_TOKEN` — SonarQube token
- `$KEYTOOL_PASSWORD` — Java keystore password

**Ansible Vault (tower-playbooks):**
- 43+ encrypted credentials for AWS, Salesforce, Snowflake, Adobe, ActiveMQ

### 10.2 Network Security

**Proxies:**
- Maven: `squid.corp.redhat.com:3128` (HTTPS proxy)
- Downloads: `squid.corp.redhat.com:3128`

**Certificate Trust:**
- Red Hat CA: `https://certs.corp.redhat.com/certs/2022-IT-Root-CA.pem`
- Imported into Java keystore during build

---

## 11. Monitoring & Observability

### 11.1 Pipeline Visibility

**GitLab CI/CD:**
- Pipeline visualization (stages/jobs graph)
- Job logs (verbose Ansible output with `-vvv`)
- Artifacts (build logs, test results)

**Ansible Tower:**
- Job execution logs
- Real-time job status
- Inventory status
- Deployment history

### 11.2 Deployment Tracking

**Version API:**
- Endpoint: `$VERSION_API_ENDPOINT`
- Returns: Last deployed version per environment
- Used by: JIRA extraction, version validation

**Example Response:**
```json
{
  "disseminator": "2.474",
  "environment": "prod"
}
```

---

## 12. Integration Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  GitLab (search-engineering/disseminator)                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  .gitlab-ci.yml                                           │  │
│  │  ├─ build (Maven)                                         │  │
│  │  ├─ upload to Nexus                                       │  │
│  │  ├─ compute_values (determine version)                    │  │
│  │  ├─ extract_jiras (CPSEARCH-* tickets)                    │  │
│  │  └─ deploy_* stages                                       │  │
│  │     └─ ansible-playbook ansible/deploy.yml                │  │
│  │        └─ awx.awx.job_launch                              │  │
│  │           ├─ job_template: disseminator-deploy-camel      │  │
│  │           ├─ inventory: "qa Disseminator-Camel-Nodes"     │  │
│  │           └─ extra_vars: {version: "2.475"}               │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTPS API Call
                                    │ (awx.awx collection)
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│  Ansible Tower (AWX)                                            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Job Template: disseminator-deploy-camel                  │  │
│  │  Inventory: qa Disseminator-Camel-Nodes                   │  │
│  │  Credentials: AWS, Nexus, Vault                           │  │
│  │  ├─ Clone: customer-platform/tower-playbooks              │  │
│  │  └─ Execute: disseminator_deploy_camel.yml                │  │
│  │     ├─ Hosts: [camel-01, camel-02, camel-03]             │  │
│  │     ├─ Serial: 1 (zero-downtime)                          │  │
│  │     └─ Roles:                                             │  │
│  │        ├─ disable_ec2_target (AWS ELB API)                │  │
│  │        ├─ disseminator_stop                               │  │
│  │        ├─ disseminator_deploy_camel                       │  │
│  │        │  └─ get_url from Nexus                           │  │
│  │        ├─ disseminator_deploy_configs_camel               │  │
│  │        ├─ disseminator_start                              │  │
│  │        └─ enable_ec2_target (AWS ELB API)                 │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Downloads JAR
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│  Nexus (nexus.corp.redhat.com)                                  │
│  ├─ Maven Repository: cee-raw-hosted                            │
│  │  └─ org/flossware/disseminator/2.475/                       │
│  │     ├─ disseminator-2.475.jar                               │
│  │     ├─ lib-2.475.tar.gz                                     │
│  │     └─ solr-plugin-2.475.jar                                │
│  └─ YUM Repository: information-retrieval-yum-releases          │
│     └─ *.rpm files                                              │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Deployed to
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│  Production Servers (47 total: 14 prod, 33 qa/stage)           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  QA Environment (3 servers)                               │  │
│  │  ├─ camel-qa-01.corp.redhat.com                           │  │
│  │  ├─ camel-qa-02.corp.redhat.com                           │  │
│  │  └─ camel-qa-03.corp.redhat.com                           │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │  Stage Environment (6 servers)                            │  │
│  │  └─ ... (stage servers)                                   │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │  Production Environment (14 servers)                      │  │
│  │  └─ ... (prod servers)                                    │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Load Balancers: AWS ELB/ALB (managed by Ansible)              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Summary

**GitLab CI/CD → Ansible Tower Integration:**

1. **GitLab CI/CD** builds JAR, uploads to Nexus, triggers Tower
2. **Tower API** receives job launch request via `awx.awx.job_launch`
3. **Tower** executes playbooks from `customer-platform/tower-playbooks`
4. **Playbooks** download artifacts from Nexus, deploy to servers
5. **Zero-downtime** achieved via AWS ELB coordination (serial: 1)
6. **JIRA automation** updates tickets after each environment deployment

**Key Files:**
- `.gitlab-ci.yml` — CI/CD pipeline definition
- `ansible/deploy.yml` — Tower job launch playbook
- `ansible/stop_indexing.yml` — Stop indexing routes
- `tower-playbooks/*.yml` — Ansible automation (separate repo)

**Key Variables:**
- `$DEPLOY_VERSION` — Version to deploy (e.g., `2.475`)
- `$DEPLOY_ENV` — Environment (`qa`, `stage`, `prod`)
- `$DEPLOY_NODE_TYPE` — Node type (`camel`, `camel-lib`, `solr`, `configsets`)
- `$INVENTORY_NAME` — Tower inventory name
- `$DXP_DEVOPS_TOWER_HOST` — Tower hostname
- `$DXP_DEVOPS_TOWER_TOKEN_Original` — Tower API token

---

**Document Status:** Complete  
**Analysis Date:** 2026-06-16  
**Purpose:** Document Disseminator CI/CD → Ansible Tower integration
