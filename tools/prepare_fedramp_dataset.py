#!/usr/bin/env python3
"""
FedRAMP Dataset Preparation

Creates JSONL training datasets for fine-tuning LLMs on FedRAMP expertise.
Generates datasets for:
1. Baseline selection (Low/Moderate/High/LI-SaaS)
2. Control implementation guidance (NIST 800-53 Rev 5)
3. Gap detection and remediation
4. ATO process navigation
5. Documentation and artifacts
"""

import json
from pathlib import Path
from datetime import datetime

def create_fedramp_dataset():
    """Generate comprehensive FedRAMP training examples"""

    examples = []

    # ============================================================================
    # 1. BASELINE SELECTION EXAMPLES
    # ============================================================================

    baseline_examples = [
        {
            'prompt': 'I have a public-facing marketing website with no user accounts or sensitive data. What FedRAMP baseline should I pursue?',
            'completion': 'You should pursue **FedRAMP Low Impact** authorization.\n\n**Rationale:**\n- No PII, CUI, or sensitive data\n- Public information only\n- Low confidentiality/integrity/availability requirements\n\n**Requirements:**\n- 125 security controls (NIST 800-53 Rev 5)\n- 3-6 months typical authorization timeline\n- $100k-$250k estimated cost\n- 3PAO assessment required\n\n**Next Steps:**\n1. Complete FIPS 199 categorization\n2. Develop System Security Plan (SSP)\n3. Engage FedRAMP-accredited 3PAO\n4. Begin readiness assessment'
        },
        {
            'prompt': 'Our SaaS application processes Controlled Unclassified Information (CUI) for federal contracts. Which FedRAMP baseline applies?',
            'completion': 'You must pursue **FedRAMP Moderate Impact** authorization.\n\n**Rationale:**\n- CUI requires Moderate baseline per NIST SP 800-171\n- Federal contract data has moderate confidentiality requirements\n- Standard for most federal SaaS applications\n\n**Requirements:**\n- 325 security controls (NIST 800-53 Rev 5)\n- 6-12 months typical authorization timeline\n- $250k-$750k estimated cost\n- FedRAMP-accredited 3PAO required\n- Continuous monitoring with monthly POA&M updates\n\n**Key Controls:**\n- SC-28: FIPS 140-2 encryption at rest\n- SC-8(1): TLS 1.2+ for data in transit\n- IA-2(1): MFA for privileged users (PIV/CAC preferred)\n- AU-2: Comprehensive audit logging (90-day retention)\n- IR-4: 1-hour US-CERT incident notification'
        },
        {
            'prompt': 'We are deploying a SaaS application on AWS GovCloud. Can we use the LI-SaaS baseline?',
            'completion': 'Yes, you may be eligible for **FedRAMP LI-SaaS** (Leveraged Impact SaaS) if:\n\n**Eligibility Requirements:**\n1. Your application runs on FedRAMP-authorized IaaS/PaaS (AWS GovCloud qualifies)\n2. You leverage inherited controls from the underlying infrastructure\n3. Your application has low-to-moderate impact data\n4. You can clearly delineate customer vs. provider responsibilities\n\n**Benefits:**\n- 146 security controls (vs 325 for Moderate)\n- Inherit 161 controls from AWS GovCloud FedRAMP High baseline\n- 3-6 months faster authorization\n- $150k-$400k estimated cost\n\n**Requirements:**\n1. Document inherited controls in SSP Part 13\n2. Provide Customer Responsibility Matrix (CRM)\n3. Implement application-layer controls (AC, AU, IA, SC)\n4. Maintain continuous monitoring\n\n**Caution:** LI-SaaS still requires 3PAO assessment. Not appropriate for High impact data.'
        },
        {
            'prompt': 'Law enforcement system storing criminal justice information. What FedRAMP level?',
            'completion': 'You must pursue **FedRAMP High Impact** authorization.\n\n**Rationale:**\n- Criminal justice information (CJIS) requires High baseline\n- Law enforcement data has high confidentiality requirements\n- Unauthorized disclosure could cause severe harm\n- May also require CJIS compliance\n\n**Requirements:**\n- 421 security controls (NIST 800-53 Rev 5)\n- 12-24 months typical authorization timeline\n- $1M-$3M+ estimated cost\n- Enhanced continuous monitoring\n- Annual penetration testing\n- FedRAMP High JAB (Joint Authorization Board) review\n\n**Additional Considerations:**\n1. CJIS Security Policy compliance (FBI CJIS APB)\n2. State-specific law enforcement requirements\n3. Biometric data protection (if applicable)\n4. Chain of custody requirements\n5. Enhanced encryption (AES-256, FIPS 140-2 Level 2+)\n\n**Deployment:** Must use FedRAMP High authorized infrastructure (AWS GovCloud, Azure Government)'
        },
    ]

    # ============================================================================
    # 2. CONTROL IMPLEMENTATION EXAMPLES
    # ============================================================================

    control_examples = [
        {
            'prompt': 'How do I implement AC-2 (Account Management) in AWS for FedRAMP Moderate?',
            'completion': '''**AC-2 Account Management Implementation in AWS:**

**Control Requirement (NIST 800-53 Rev 5):**
- Manage system accounts
- Define account types (individual, group, system, application)
- Establish conditions for group/role membership
- Monitor account usage
- Review accounts periodically

**AWS Implementation:**

1. **IAM User Management:**
```
- Create individual IAM users (no shared accounts)
- Enforce unique usernames
- Tag users with metadata (department, role, manager)
- Use AWS Organizations for multi-account management
```

2. **Account Types:**
- Individual users: IAM users with MFA
- Privileged users: Dedicated admin accounts with PIV/CAC
- Service accounts: IAM roles (not users)
- Guest/temporary: Time-limited IAM users with SCP restrictions

3. **Automated Account Lifecycle:**
```bash
# CloudFormation/Terraform for account provisioning
# Lambda function for periodic review (90 days)
# EventBridge rule to detect unused credentials
# AWS Config rule: iam-user-unused-credentials-check
```

4. **Monitoring & Auditing:**
- CloudTrail: Log all account activities
- IAM Access Analyzer: Detect excessive permissions
- AWS Config: Track account changes
- GuardDuty: Detect compromised credentials

5. **SSP Documentation:**
- Part 13 Control Summary: "AWS IAM provides centralized account management..."
- Customer Responsibility: Account lifecycle, periodic review
- AWS Inherited: IAM platform security

**Compliance Evidence:**
- IAM credential report (monthly)
- Account review logs (quarterly)
- CloudTrail audit trail (continuous)
- AWS Config compliance dashboard
'''
        },
        {
            'prompt': 'Implement SC-28 (Protection of Information at Rest) for RDS databases',
            'completion': '''**SC-28 Implementation for AWS RDS:**

**Control Requirement:**
Protect confidentiality and integrity of information at rest using FIPS 140-2 validated cryptographic modules.

**AWS RDS Implementation:**

1. **Enable Encryption at Rest:**
```bash
# Enable encryption for new RDS instance
aws rds create-db-instance \\
  --db-instance-identifier my-db \\
  --storage-encrypted \\
  --kms-key-id arn:aws:kms:us-gov-west-1:123456789012:key/abcd-1234 \\
  --engine postgres \\
  --db-instance-class db.r5.large

# Migrate existing unencrypted database:
# 1. Create encrypted snapshot
aws rds create-db-snapshot \\
  --db-instance-identifier my-db \\
  --db-snapshot-identifier pre-encryption-snapshot

aws rds copy-db-snapshot \\
  --source-db-snapshot-identifier pre-encryption-snapshot \\
  --target-db-snapshot-identifier encrypted-snapshot \\
  --kms-key-id <kms-key-arn> \\
  --copy-tags

# 2. Restore from encrypted snapshot
aws rds restore-db-instance-from-db-snapshot \\
  --db-instance-identifier my-db-encrypted \\
  --db-snapshot-identifier encrypted-snapshot

# 3. Update application connection strings (downtime required)
```

2. **KMS Key Management:**
- Use AWS KMS with FIPS 140-2 Level 2 validated HSMs
- Customer-managed CMKs (not AWS-managed keys)
- Key rotation enabled (annual minimum)
- Key policy restricts access to authorized principals

3. **Automated Enforcement:**
```python
# AWS Config custom rule
def check_rds_encryption(config_item):
    if config_item['resourceType'] == 'AWS::RDS::DBInstance':
        if not config_item['configuration'].get('storageEncrypted'):
            return 'NON_COMPLIANT'
    return 'COMPLIANT'
```

4. **FedRAMP Evidence:**
- AWS KMS FIPS 140-2 certificate (inherit from AWS GovCloud)
- RDS encryption configuration screenshots
- Config rule compliance report
- KMS key policy documentation

5. **SSP Part 13 Documentation:**
"AWS RDS encryption uses AES-256 with FIPS 140-2 Level 2 validated KMS. Customer-managed CMKs with annual rotation. Automated compliance via AWS Config."

**Related Controls:**
- SC-28(1): Cryptographic protection (satisfied by KMS FIPS 140-2)
- SC-13: Cryptographic key establishment (KMS key management)
'''
        },
        {
            'prompt': 'Configure IA-2(1) Multi-Factor Authentication for privileged AWS users',
            'completion': '''**IA-2(1) MFA for Privileged Users:**

**FedRAMP Requirement:**
MFA using PIV/CAC credentials OR FIPS 140-2 Level 1+ hardware tokens for all privileged/administrative access.

**AWS GovCloud Implementation:**

1. **PIV/CAC Authentication (Preferred):**
```bash
# Configure SAML federation with PIV/CAC-enabled IdP
# Example: AD FS, Okta, Ping Federate

# Trust relationship for IAM role
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Federated": "arn:aws-us-gov:iam::123456789012:saml-provider/PIV-IdP"},
    "Action": "sts:AssumeRoleWithSAML",
    "Condition": {
      "StringEquals": {
        "SAML:aud": "https://signin.amazonaws-us-gov.com/saml"
      }
    }
  }]
}
```

2. **Hardware MFA Tokens (Alternative):**
- YubiKey 5 FIPS (FIPS 140-2 Level 2)
- Gemalto SafeNet (FIPS 140-2 Level 3)

```bash
# Assign MFA device to IAM user
aws iam enable-mfa-device \\
  --user-name admin-user \\
  --serial-number arn:aws-us-gov:iam::123456789012:mfa/admin-hardware-token \\
  --authentication-code-1 123456 \\
  --authentication-code-2 789012
```

3. **Enforce MFA with IAM Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Deny",
    "Action": "*",
    "Resource": "*",
    "Condition": {
      "BoolIfExists": {"aws:MultiFactorAuthPresent": "false"}
    }
  }]
}
```

4. **SCP for Organization-Wide Enforcement:**
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Deny",
    "Action": ["iam:CreateUser", "iam:CreateAccessKey"],
    "Resource": "*",
    "Condition": {
      "StringNotEquals": {"aws:username": ["break-glass-user"]}
    }
  }]
}
```

5. **Monitoring & Compliance:**
- CloudTrail: MFA usage in userIdentity.mfaAuthenticated
- AWS Config: iam-user-mfa-enabled
- Daily report: Users without MFA
- Alert: Privileged action without MFA

**Break-Glass Accounts:**
- 2 emergency accounts without MFA (stored in physical safe)
- Logged and reviewed within 1 hour of use
- Rotated after every use

**FedRAMP Evidence:**
- MFA device inventory
- FIPS 140-2 certificates for hardware tokens
- CloudTrail logs showing MFA usage
- Monthly compliance report
'''
        },
    ]

    # ============================================================================
    # 3. GAP DETECTION & REMEDIATION
    # ============================================================================

    gap_examples = [
        {
            'prompt': 'AWS Security Hub flagged: "S3 buckets should have server-side encryption enabled". What FedRAMP control does this violate?',
            'completion': '''**FedRAMP Control Violation: SC-28 (Protection of Information at Rest)**

**Severity:** CRITICAL - Authorization Blocker

**Related Controls:**
- SC-28: Protection of Information at Rest
- SC-28(1): Cryptographic Protection

**Gap Description:**
Unencrypted S3 bucket fails to protect data confidentiality at rest, violating FedRAMP Moderate/High baseline requirements.

**Remediation Steps:**

1. **Enable Default Encryption:**
```bash
# Enable AES-256 encryption (SSE-S3)
aws s3api put-bucket-encryption \\
  --bucket my-fedramp-bucket \\
  --server-side-encryption-configuration \\
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# OR use KMS encryption (recommended for FedRAMP High)
aws s3api put-bucket-encryption \\
  --bucket my-fedramp-bucket \\
  --server-side-encryption-configuration \\
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"aws:kms","KMSMasterKeyID":"arn:aws-us-gov:kms:us-gov-west-1:123456789012:key/abcd-1234"}}]}'
```

2. **Encrypt Existing Objects:**
```bash
# Copy objects to themselves with encryption
aws s3 cp s3://my-bucket/ s3://my-bucket/ \\
  --recursive \\
  --sse aws:kms \\
  --sse-kms-key-id <kms-key-arn> \\
  --metadata-directive REPLACE
```

3. **Prevent Unencrypted Uploads:**
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Deny",
    "Principal": "*",
    "Action": "s3:PutObject",
    "Resource": "arn:aws-us-gov:s3:::my-fedramp-bucket/*",
    "Condition": {
      "StringNotEquals": {
        "s3:x-amz-server-side-encryption": ["AES256", "aws:kms"]
      }
    }
  }]
}
```

4. **Automated Compliance:**
```bash
# AWS Config rule (managed)
aws configservice put-config-rule \\
  --config-rule file://s3-default-encryption-kms.json

# Auto-remediation with SSM Automation
aws ssm create-association \\
  --name AWS-EnableS3BucketEncryption \\
  --targets Key=tag:FedRAMP,Values=true
```

**POA&M Entry:**
- Weakness: Unencrypted S3 bucket
- Control: SC-28
- Scheduled Completion: <30 days (critical)
- Mitigation: Encryption enabled, bucket policy enforced
- Status: Closed

**SSP Update:**
Part 13 - SC-28 Implementation: "All S3 buckets use AES-256 encryption. Bucket policies deny unencrypted uploads. AWS Config monitors compliance."
'''
        },
        {
            'prompt': 'CloudTrail logs are retained for only 30 days. Is this FedRAMP compliant?',
            'completion': '''**FedRAMP Compliance: NO - Violates AU-11 (Audit Record Retention)**

**Control Violation:** AU-11 Audit Record Retention
**Severity:** HIGH

**FedRAMP Requirement:**
Minimum 90 days online retention for audit logs (Moderate/High baselines)

**Gap Analysis:**
- Current: 30 days CloudTrail retention
- Required: 90 days minimum
- Recommended: 1 year online, 7 years archive

**Remediation:**

1. **Extend CloudTrail Retention:**
```bash
# Create S3 bucket with lifecycle policy
aws s3api create-bucket \\
  --bucket fedramp-cloudtrail-logs \\
  --region us-gov-west-1

# Lifecycle: 90 days S3 Standard, then Glacier
cat > lifecycle.json <<EOF
{
  "Rules": [{
    "Id": "FedRAMP-Retention",
    "Status": "Enabled",
    "Transitions": [{
      "Days": 90,
      "StorageClass": "GLACIER"
    }],
    "Expiration": {"Days": 2555}
  }]
}
EOF

aws s3api put-bucket-lifecycle-configuration \\
  --bucket fedramp-cloudtrail-logs \\
  --lifecycle-configuration file://lifecycle.json
```

2. **Configure CloudTrail:**
```bash
aws cloudtrail update-trail \\
  --name fedramp-trail \\
  --s3-bucket-name fedramp-cloudtrail-logs \\
  --enable-log-file-validation \\
  --kms-key-id arn:aws-us-gov:kms:us-gov-west-1:123456789012:key/audit-logs
```

3. **Alternative: CloudWatch Logs:**
```bash
# Send CloudTrail to CloudWatch Logs (real-time analysis)
aws cloudtrail update-trail \\
  --name fedramp-trail \\
  --cloud-watch-logs-log-group-arn arn:aws-us-gov:logs:us-gov-west-1:123456789012:log-group:/aws/cloudtrail/fedramp \\
  --cloud-watch-logs-role-arn arn:aws-us-gov:iam::123456789012:role/CloudTrailToCloudWatchLogs

# Set retention to 90 days
aws logs put-retention-policy \\
  --log-group-name /aws/cloudtrail/fedramp \\
  --retention-in-days 90
```

4. **SIEM Integration (Recommended):**
- Splunk Cloud (FedRAMP Moderate authorized)
- Sumo Logic (FedRAMP Moderate authorized)
- Export CloudTrail to SIEM for analysis + long-term retention

**Related Controls:**
- AU-2: Audit Events (CloudTrail captures all API calls)
- AU-3: Content of Audit Records (CloudTrail includes required fields)
- AU-6: Audit Review, Analysis, and Reporting (SIEM integration)
- AU-9: Protection of Audit Information (S3 encryption + MFA delete)
- AU-11: Audit Record Retention (90 days minimum)

**POA&M:**
- Weakness: Insufficient audit log retention (30 days)
- Control: AU-11
- Scheduled Completion: 7 days
- Remediation: S3 lifecycle policy configured for 90-day retention
'''
        },
    ]

    # ============================================================================
    # 4. ATO PROCESS GUIDANCE
    # ============================================================================

    ato_examples = [
        {
            'prompt': 'What are the steps to achieve FedRAMP ATO for a new cloud service?',
            'completion': '''**FedRAMP Authorization Process (Agency ATO Path):**

**Phase 1: Pre-Authorization (3-6 months)**

1. **Initiate:**
   - Determine impact level (Low/Moderate/High/LI-SaaS)
   - Complete FIPS 199 categorization
   - Register in FedRAMP Marketplace

2. **Prepare:**
   - Develop System Security Plan (SSP) using FedRAMP templates
   - Implement required controls (125-421 depending on baseline)
   - Document control inheritance (if using FedRAMP-authorized IaaS)
   - Conduct internal readiness assessment

3. **Engage 3PAO:**
   - Select FedRAMP-accredited Third Party Assessment Organization
   - Negotiate SOW and timeline
   - Develop Security Assessment Plan (SAP)

**Phase 2: Full Security Assessment (3-6 months)**

4. **3PAO Assessment:**
   - Security control testing (4-8 weeks)
   - Penetration testing
   - Vulnerability scanning
   - Documentation review

5. **Remediation:**
   - Address identified vulnerabilities
   - Update SSP with control changes
   - Create Plan of Action & Milestones (POA&M) for residual risks

6. **Security Assessment Report (SAR):**
   - 3PAO delivers SAR with findings
   - Review and validate results
   - Prepare responses to risks

**Phase 3: Agency Authorization (2-4 months)**

7. **Submit Authorization Package:**
   - SSP, SAR, POA&M, supporting artifacts
   - Submit to sponsoring agency ISSO/ISSM
   - FedRAMP PMO conducts quality review

8. **Agency Review:**
   - Agency evaluates risk posture
   - May request additional evidence
   - Conducts authorization decision meeting

9. **ATO Issuance:**
   - Agency issues Authority to Operate (ATO)
   - ATO valid for 3 years (with continuous monitoring)
   - Listed in FedRAMP Marketplace

**Phase 4: Continuous Monitoring (Ongoing)**

10. **ConMon Activities:**
    - Monthly POA&M updates
    - Monthly vulnerability scans
    - Quarterly manual testing
    - Annual 3PAO assessment
    - Significant change requests (SCRs) as needed

**Timeline:**
- Low Impact: 6-9 months total
- Moderate Impact: 9-15 months total
- High Impact: 18-30 months total

**Cost Estimates:**
- 3PAO assessment: $75k-$400k
- Remediation: $50k-$500k
- Annual ConMon: $50k-$150k

**Key Success Factors:**
1. Executive sponsorship and budget
2. Dedicated FedRAMP program manager
3. Early 3PAO engagement
4. Leverage inherited controls (use FedRAMP IaaS)
5. Automate compliance monitoring
'''
        },
    ]

    # ============================================================================
    # 5. DOCUMENTATION & ARTIFACTS
    # ============================================================================

    doc_examples = [
        {
            'prompt': 'How do I complete the System Security Plan (SSP) Part 13 Control Summary?',
            'completion': '''**SSP Part 13 Control Implementation Summary:**

Part 13 is the most critical section of your SSP - it documents how each NIST 800-53 control is implemented.

**Format for Each Control:**

```
Control Identifier: AC-2 Account Management

Control Summary:
The system manages user accounts through AWS IAM. Individual accounts are created for all users with unique identifiers. Privileged accounts require MFA using PIV/CAC credentials via SAML federation.

Implementation Status: ☑ Implemented

Responsible Role: Cloud Security Team (Customer), AWS IAM (Provider)

Implementation Details:

Customer Responsibility:
- IAM user provisioning and deprovisioning via ServiceNow workflow
- Quarterly access reviews by system owners
- MFA enforcement policy for all privileged users
- Automated detection of inactive accounts (>90 days)
- CloudTrail logging of all account activities

AWS Inherited:
- IAM platform security and availability
- Physical security of IAM infrastructure (PE-1 through PE-18)
- IAM cryptographic key management (SC-12, SC-13)

Parameter Requirements:
- AC-2(1): Automated account management via Lambda functions
- AC-2(2): Automatic disable after 90 days inactivity
- AC-2(3): Automatic disable after 3 failed login attempts
- AC-2(4): Automated audit actions logged to CloudWatch

Evidence:
- IAM_User_Inventory.xlsx (Attachment 13-AC-2-1)
- Quarterly_Access_Review_2025Q1.pdf (Attachment 13-AC-2-2)
- CloudTrail_Account_Activity.json (Attachment 13-AC-2-3)
```

**Key Sections to Complete:**

1. **Control Summary** (2-3 sentences)
   - High-level description of implementation
   - Reference specific AWS services/tools
   - Mention automation where applicable

2. **Implementation Status**
   - ☑ Implemented (most controls)
   - ☐ Partially Implemented (document gaps in POA&M)
   - ☐ Planned (rare, requires POA&M entry)
   - ☐ Alternative Implementation (requires FedRAMP PMO approval)
   - ☐ Not Applicable (document justification)

3. **Responsible Role**
   - Customer Responsibility
   - AWS/Azure/GCP Inherited
   - Shared Responsibility (both)
   - Hybrid Responsibility (document split)

4. **Implementation Details**
   - Specific configuration settings
   - Automation tools (Config, Lambda, SSM)
   - Integration with SIEM/monitoring
   - Reference architecture diagrams

5. **Parameter Requirements**
   - Control enhancements (AC-2(1), AC-2(2), etc.)
   - Assignment values (e.g., "90 days" for inactive accounts)
   - FedRAMP parameter requirements

6. **Evidence Attachments**
   - Screenshots of configuration
   - Policy documents
   - Log samples
   - Compliance reports

**Tips for Success:**

1. **Leverage FedRAMP Templates:**
   - Use FedRAMP SSP Appendix A (CIS Workbook)
   - Reference AWS/Azure/GCP CIS Worksheets for inherited controls

2. **Document Inherited Controls:**
   - AWS GovCloud inherits 161 controls (FedRAMP High)
   - Azure Government inherits 171 controls
   - Must still document HOW you inherit (connection, boundary)

3. **Automation is Key:**
   - "Manual review" is weak implementation
   - "AWS Config rule monitors... Lambda remediates..." is strong

4. **Link to Diagrams:**
   - Reference Attachment numbers
   - System architecture (Part 9)
   - Network diagram (Part 9)
   - Data flow diagram (Part 10)

5. **Consistency Across Families:**
   - AC controls → IAM policies
   - AU controls → CloudTrail/CloudWatch
   - SC controls → Encryption, VPC, Security Groups
   - SI controls → GuardDuty, Inspector, Systems Manager

**Common Mistakes to Avoid:**
- Copy/paste AWS documentation (3PAO will flag)
- Vague statements ("We follow best practices")
- Missing parameter values
- No evidence attachments
- Inconsistent responsible roles
'''
        },
    ]

    # Combine all examples
    examples.extend(baseline_examples)
    examples.extend(control_examples)
    examples.extend(gap_examples)
    examples.extend(ato_examples)
    examples.extend(doc_examples)

    return examples

def save_datasets():
    """Save training and validation datasets"""

    print("="*80)
    print("FEDRAMP DATASET PREPARATION")
    print("="*80)

    examples = create_fedramp_dataset()
    print(f"\nGenerated {len(examples)} training examples")

    # Split 80/20 train/val
    split_idx = int(len(examples) * 0.8)
    train_examples = examples[:split_idx]
    val_examples = examples[split_idx:]

    print(f"  Training: {len(train_examples)} examples")
    print(f"  Validation: {len(val_examples)} examples")

    # Save to datasets directory
    dataset_dir = Path('/home/sfloess/fine-tuning/datasets')
    dataset_dir.mkdir(parents=True, exist_ok=True)

    train_path = dataset_dir / 'fedramp_expert_train.jsonl'
    val_path = dataset_dir / 'fedramp_expert_val.jsonl'
    metadata_path = dataset_dir / 'fedramp_expert_metadata.json'

    # Save training set
    print(f"\nSaving training set to {train_path}...")
    with open(train_path, 'w') as f:
        for example in train_examples:
            # OpenAI fine-tuning format
            entry = {
                'messages': [
                    {'role': 'system', 'content': 'You are a FedRAMP compliance expert specializing in government cloud security, NIST 800-53 controls, and ATO processes.'},
                    {'role': 'user', 'content': example['prompt']},
                    {'role': 'assistant', 'content': example['completion']}
                ]
            }
            f.write(json.dumps(entry) + '\n')

    # Save validation set
    print(f"Saving validation set to {val_path}...")
    with open(val_path, 'w') as f:
        for example in val_examples:
            entry = {
                'messages': [
                    {'role': 'system', 'content': 'You are a FedRAMP compliance expert specializing in government cloud security, NIST 800-53 controls, and ATO processes.'},
                    {'role': 'user', 'content': example['prompt']},
                    {'role': 'assistant', 'content': example['completion']}
                ]
            }
            f.write(json.dumps(entry) + '\n')

    # Save metadata
    metadata = {
        'name': 'FedRAMP Government Cloud Security Expert',
        'version': '1.0',
        'created_at': datetime.now().isoformat(),
        'description': 'Training data for FedRAMP compliance, NIST 800-53 Rev 5 controls, ATO process, and government cloud security',
        'categories': [
            'baseline_selection',
            'control_implementation',
            'gap_detection',
            'ato_guidance',
            'documentation',
            'cloud_implementation'
        ],
        'baselines_covered': ['Low', 'Moderate', 'High', 'LI-SaaS'],
        'control_families': [
            'AC', 'AU', 'AT', 'CM', 'CP', 'IA', 'IR', 'MA', 'MP',
            'PE', 'PL', 'PS', 'RA', 'CA', 'SC', 'SI', 'SA', 'PM'
        ],
        'cloud_platforms': ['AWS GovCloud', 'Azure Government', 'GCP'],
        'total_examples': len(examples),
        'train_examples': len(train_examples),
        'val_examples': len(val_examples),
        'recommended_model': 'gpt-4o-mini',
        'estimated_tokens': sum(len(e['prompt']) + len(e['completion']) for e in examples) // 4,
        'fine_tuning_params': {
            'n_epochs': 3,
            'batch_size': 4,
            'learning_rate_multiplier': 0.1
        }
    }

    print(f"Saving metadata to {metadata_path}...")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print("\n" + "="*80)
    print("DATASET PREPARATION COMPLETE")
    print("="*80)
    print(f"\nFiles created:")
    print(f"  {train_path} ({train_path.stat().st_size // 1024} KB)")
    print(f"  {val_path} ({val_path.stat().st_size // 1024} KB)")
    print(f"  {metadata_path}")

    print(f"\nNext steps:")
    print(f"  1. Train Random Forest: python3 tools/fedramp_expert_trainer.py")
    print(f"  2. Test predictions: python3 tools/predict_fedramp.py 'What baseline for CUI?'")
    print(f"  3. Fine-tune LLM (optional): openai api fine_tuning.jobs.create -t {train_path} -m gpt-4o-mini-2024-07-18")

    return train_path, val_path, metadata_path

if __name__ == '__main__':
    save_datasets()
