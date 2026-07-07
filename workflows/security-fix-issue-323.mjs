export const meta = {
  name: 'security-fix-issue-323',
  description: 'Fix security vulnerabilities to raise score from 52/100 to 80+',
  phases: [
    { title: 'Security Audit', detail: 'Scan for secrets, SQL injection, input validation issues' },
    { title: 'Fix Vulnerabilities', detail: 'Apply fixes across codebase' },
    { title: 'Verification', detail: 'Re-run security audit to verify 80+ score' }
  ]
};

export default async function({ args, phase, log, agent, parallel }) {

phase('Security Audit');

log('Running security audit across codebase...');

const audits = await parallel([
  // Audit 1: Hardcoded secrets
  () => agent(
    `**SECURITY AUDIT: Hardcoded Secrets**

Scan the entire codebase for hardcoded credentials:

1. Search for patterns:
   - Passwords: grep -r "password.*=.*['\"]" --include="*.{js,py,sql,md,sh}" .
   - API keys: grep -r "api_key.*=.*['\"]" --include="*.{js,py}" .
   - Database credentials: grep -r "PGPASSWORD\|DATABASE_URL" --include="*" .
   - Tokens: grep -r "token.*=.*['\"]" --include="*.{js,py}" .

2. Exclude false positives:
   - Skip: node_modules/, .git/, learning/predictors/
   - Skip: Variable names (e.g., "password" as function param)
   - Focus on actual credential values

3. Return findings with:
   - File path
   - Line number
   - Type of credential
   - Whether it's a real secret or false positive

**Return JSON:**
{
  "total_files_scanned": 0,
  "secrets_found": [],
  "false_positives": 0,
  "high_risk_files": []
}`,
    {
      label: 'Audit: Hardcoded Secrets',
      phase: 'Security Audit',
      model: 'sonnet',
      schema: {
        type: 'object',
        properties: {
          total_files_scanned: { type: 'number' },
          secrets_found: { type: 'array', items: { type: 'object' } },
          false_positives: { type: 'number' },
          high_risk_files: { type: 'array', items: { type: 'string' } }
        },
        required: ['total_files_scanned', 'secrets_found']
      }
    }
  ),

  // Audit 2: SQL Injection
  () => agent(
    `**SECURITY AUDIT: SQL Injection Risks**

Scan for SQL injection vulnerabilities:

1. Find all database queries:
   - PostgreSQL: grep -r "db.query\|pool.query\|client.query" --include="*.{js,cjs,mjs}" .
   - Python: grep -r "cursor.execute\|db.execute" --include="*.py" .

2. Check for string concatenation:
   - Unsafe: "SELECT * FROM users WHERE id = " + userId
   - Unsafe: f"SELECT * FROM users WHERE id = {userId}"
   - Safe: "SELECT * FROM users WHERE id = $1", [userId]

3. Verify parameterized queries:
   - All queries should use $1, $2, ... placeholders (JS)
   - All queries should use %s or ? placeholders (Python)

**Return JSON:**
{
  "total_queries": 0,
  "unsafe_queries": [],
  "safe_queries": 0,
  "files_with_risks": []
}`,
    {
      label: 'Audit: SQL Injection',
      phase: 'Security Audit',
      model: 'sonnet',
      schema: {
        type: 'object',
        properties: {
          total_queries: { type: 'number' },
          unsafe_queries: { type: 'array', items: { type: 'object' } },
          safe_queries: { type: 'number' },
          files_with_risks: { type: 'array', items: { type: 'string' } }
        },
        required: ['total_queries', 'unsafe_queries', 'safe_queries']
      }
    }
  ),

  // Audit 3: Input Validation
  () => agent(
    `**SECURITY AUDIT: Input Validation**

Check for missing input validation:

1. User inputs to validate:
   - Task descriptions (XSS risk)
   - File paths (directory traversal risk)
   - Model inputs (injection risk)
   - API parameters (validation missing)

2. Find validation gaps:
   - grep -r "req.body\|req.query\|req.params" --include="*.js" .
   - Check if inputs are sanitized before use
   - Verify file path validation (no ../ allowed)

3. Check for:
   - Missing input type checks
   - No length limits
   - No character whitelisting
   - Direct use of user input in system calls

**Return JSON:**
{
  "total_inputs": 0,
  "unvalidated_inputs": [],
  "validation_gaps": [],
  "high_risk_endpoints": []
}`,
    {
      label: 'Audit: Input Validation',
      phase: 'Security Audit',
      model: 'sonnet',
      schema: {
        type: 'object',
        properties: {
          total_inputs: { type: 'number' },
          unvalidated_inputs: { type: 'array', items: { type: 'object' } },
          validation_gaps: { type: 'array', items: { type: 'string' } },
          high_risk_endpoints: { type: 'array', items: { type: 'string' } }
        },
        required: ['total_inputs', 'unvalidated_inputs']
      }
    }
  )
]);

log(`Audit complete: ${audits.filter(Boolean).length}/3 audits finished`);

phase('Fix Vulnerabilities');

log('Applying security fixes...');

const fixes = await parallel([
  // Fix hardcoded secrets
  () => agent(
    `**FIX: Remove Hardcoded Secrets**

Based on audit findings:
${JSON.stringify(audits[0], null, 2)}

1. For each real secret found:
   - Move to environment variables
   - Update code to read from process.env
   - Add to .gitignore if in config file
   - Document in .env.example

2. Create shared/credentials-loader.js if needed:
   - Load from ~/.claude/credentials.json
   - Fall back to environment variables
   - Never hardcode defaults

3. Update all files that had secrets

**Return JSON:**
{
  "secrets_moved": 0,
  "files_fixed": [],
  "env_vars_added": [],
  "tests_passing": true
}`,
    {
      label: 'Fix: Hardcoded Secrets',
      phase: 'Fix Vulnerabilities',
      model: 'opus',
      effort: 'high',
      schema: {
        type: 'object',
        properties: {
          secrets_moved: { type: 'number' },
          files_fixed: { type: 'array', items: { type: 'string' } },
          env_vars_added: { type: 'array', items: { type: 'string' } },
          tests_passing: { type: 'boolean' }
        },
        required: ['secrets_moved', 'files_fixed', 'tests_passing']
      }
    }
  ),

  // Fix SQL injection
  () => agent(
    `**FIX: SQL Injection Prevention**

Based on audit findings:
${JSON.stringify(audits[1], null, 2)}

1. For each unsafe query:
   - Replace string concatenation with parameterized queries
   - Use $1, $2, ... placeholders (PostgreSQL)
   - Pass values as array: query(sql, [param1, param2])

2. Add query validation helper:
   - Validate all user inputs before query
   - Escape special characters if needed
   - Log all query errors

3. Update all files with SQL injection risks

**Return JSON:**
{
  "queries_fixed": 0,
  "files_updated": [],
  "validation_added": true,
  "tests_passing": true
}`,
    {
      label: 'Fix: SQL Injection',
      phase: 'Fix Vulnerabilities',
      model: 'opus',
      effort: 'high',
      schema: {
        type: 'object',
        properties: {
          queries_fixed: { type: 'number' },
          files_updated: { type: 'array', items: { type: 'string' } },
          validation_added: { type: 'boolean' },
          tests_passing: { type: 'boolean' }
        },
        required: ['queries_fixed', 'files_updated', 'tests_passing']
      }
    }
  ),

  // Fix input validation
  () => agent(
    `**FIX: Input Validation**

Based on audit findings:
${JSON.stringify(audits[2], null, 2)}

1. Add input validation for:
   - Task descriptions: Sanitize HTML, limit length
   - File paths: Block ../, verify exists, check permissions
   - Model inputs: Type check, bounds check, whitelist allowed values
   - API parameters: Validate types, required fields, ranges

2. Create shared/input-validator.js:
   - sanitizeHtml(input) - Remove dangerous HTML
   - validateFilePath(path) - Prevent directory traversal
   - validateModelInput(input) - Type/bounds checking
   - validateApiParams(params, schema) - Schema validation

3. Add validation to all high-risk endpoints

**Return JSON:**
{
  "validations_added": 0,
  "endpoints_secured": [],
  "validator_created": true,
  "tests_passing": true
}`,
    {
      label: 'Fix: Input Validation',
      phase: 'Fix Vulnerabilities',
      model: 'opus',
      effort: 'high',
      schema: {
        type: 'object',
        properties: {
          validations_added: { type: 'number' },
          endpoints_secured: { type: 'array', items: { type: 'string' } },
          validator_created: { type: 'boolean' },
          tests_passing: { type: 'boolean' }
        },
        required: ['validations_added', 'endpoints_secured', 'tests_passing']
      }
    }
  )
]);

log(`Fixes applied: ${fixes.filter(Boolean).length}/3 fixes complete`);

phase('Verification');

log('Running security re-audit...');

const verification = await agent(
  `**SECURITY VERIFICATION**

Re-run security audit to verify fixes:

1. Re-scan for hardcoded secrets (should be 0)
2. Re-scan for SQL injection (should be 0 unsafe queries)
3. Re-scan for unvalidated inputs (should be minimal)
4. Calculate new security score

**Scoring (out of 100):**
- No hardcoded secrets: +30 points
- No SQL injection: +30 points
- Input validation present: +20 points
- Dependency audit clean: +10 points
- Security best practices: +10 points

Target: 80+ points

**Return JSON:**
{
  "secrets_remaining": 0,
  "sql_injection_risks": 0,
  "unvalidated_inputs_remaining": 0,
  "security_score": 0,
  "score_increase": 0,
  "passed_audit": false
}`,
  {
    label: 'Verify Security Score',
    phase: 'Verification',
    model: 'opus',
    effort: 'high',
    schema: {
      type: 'object',
      properties: {
        secrets_remaining: { type: 'number' },
        sql_injection_risks: { type: 'number' },
        unvalidated_inputs_remaining: { type: 'number' },
        security_score: { type: 'number' },
        score_increase: { type: 'number' },
        passed_audit: { type: 'boolean' }
      },
      required: ['security_score', 'passed_audit']
    }
  }
);

log(`Security audit complete: Score ${verification?.security_score || 'N/A'}/100`);

return {
  audits: audits.filter(Boolean),
  fixes: fixes.filter(Boolean),
  verification,
  success: verification?.passed_audit || false,
  final_score: verification?.security_score || 0
};

}
