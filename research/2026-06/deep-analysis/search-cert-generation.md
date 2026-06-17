# Deep Code Analysis: cert-generation

**Analysis Date:** 2026-06-16
**Repository:** search-engineering/cert-generation

## 1. Repository Structure

```
.
├── bin
│   └── generate.sh
├── cnf
│   ├── gss-diag.corp.qa.redhat.com.cnf
│   ├── gss-diag.corp.redhat.com.cnf
│   ├── gss-diag.corp.stage.redhat.com.cnf
│   ├── ir-dashboard.corp.redhat.com.cnf
│   ├── pnt-cee-fusion.corp.qa.redhat.com.cnf
│   ├── pnt-cee-fusion.corp.redhat.com.cnf
│   ├── pnt-cee-fusion.corp.stage.redhat.com.cnf
│   ├── pnt-cee-solr.corp.qa.redhat.com.cnf
│   ├── pnt-cee-solr.corp.redhat.com.cnf
│   └── pnt-cee-solr.corp.stage.redhat.com.cnf
├── umb
│   └── umb-test
│       ├── bin
│       ├── src
│       └── pom.xml
├── cachain.crt
└── README.md

7 directories, 14 files
```

**File Statistics:**
- Total files: 17
- Java files: 1
- XML files: 1
- Python files: 0
- JavaScript files: 0

## 2. Architecture & Code Patterns

**Build System:**

**Key Packages/Modules:**

**Design Patterns Detected:**
- Pattern usage: 10 occurrences

## 3. Code Quality Analysis

**Testing:**
- Test files: 0

**Documentation:**
- README.md (48 lines)
- Javadoc annotations: 0

**Code Metrics:**

## 4. Key Files Deep Dive

### README.md
```markdown
# Cert Generation

## About

This project is used to generate certs for our HTTPS load balancers.

Please see this project's [wiki](https://gitlab.cee.redhat.com/search-engineering/cert-generation/-/wikis/Generate-and-Deploy-Certs-to-AWS-EC2) for a detailed explanation of how to generate and apply certs.

The official documentation can be found [here](https://docs.google.com/document/d/10OeyIjFgbbZjMoxzp3N0QOwj5wgkDJus09Kav6vSysw/edit).

The Certificate Manager Page can be found [here](https://ca2.corp.redhat.com/ca/ee/ca/).

## Generating

All hosts are defined in the [cnf](https://gitlab.cee.redhat.com/search-engineering/cert-generation/-/blob/main/cnf) directory.  To generate the required files, execute the script [bin/generate.sh](https://gitlab.cee.redhat.com/search-engineering/cert-generation/-/blob/main/bin/generate.sh).  This script will generate:
* Certificate request files to `target/csr`.
* Private key files to `target/key`.

## Submitting High Level

This section will describe how to submit certs.

1. Generate both the `csr` and `keys` files as denoted above.
1. For the given host, enter the `csr` file here [page](https://ca2.corp.redhat.com/ca/ee/ca/profileSelect?profileId=caServerCert):
   * Leave the `Certificate Request Type` as `PKCS#10`.
   * Using the `csr` file contents, enter that as the `Certificate Reqeust`.
   * Enter your email address for `Requester Email`.
   * Enter your phone number as the Requestor Phone`.
   * Click Submit
1. Wait for an email to arrive containing your `csr`.
...
```

### Top 5 Largest Source Files
- ./umb/umb-test/src/main/java/Main.java (142 lines)

---
**Analysis Complete**
