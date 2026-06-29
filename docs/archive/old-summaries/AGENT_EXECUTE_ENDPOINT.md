# Agent Execute Endpoint - SSH Command Generation

## Overview

The `/agent/execute` endpoint (via `getAgentExecuteCommand`) provides visibility into the exact SSH commands that will be executed for remote agent jobs. Instead of directly executing, it returns the full command string along with metadata, allowing callers to:

- Inspect the command before execution
- Audit remote execution patterns
- Log commands for compliance/debugging
- Customize or wrap commands as needed
- Verify environment variables and flags

## API

### Function Signature

```javascript
async function getAgentExecuteCommand(
  serverInstance: string,
  model: string,
  prompt: string,
  opts?: {
    schema?: object,
    jobId?: string
  }
): Promise<{
  command: string,
  sshCommand: string,
  server: string,
  model: string,
  jobId: string,
  promptLength: number,
  timestamp: string
}>
```

### Parameters

- **serverInstance** (string): Remote server hostname or instance
  - Examples: `'server-03'`, `'server-01:9100'`
  - Port numbers are automatically stripped
  
- **model** (string): AI model to use for the agent
  - Examples: `'opus'`, `'sonnet'`, `'haiku'`
  
- **prompt** (string): The complete agent prompt/request
  - Can be any length; large prompts (≥4KB) are automatically written to NFS
  
- **opts.schema** (object, optional): Expected output schema for result validation
  
- **opts.jobId** (string, optional): Job identifier for tracking
  - Auto-generated if not provided: `job-{timestamp}-{random}`

### Return Value

Returns a promise resolving to an object with:

```javascript
{
  command: string,        // Full SSH command (ready to execute)
  sshCommand: string,     // Alias for 'command' (same value)
  server: string,         // Extracted server name
  model: string,          // AI model name
  jobId: string,          // Unique job identifier
  promptLength: number,   // Prompt size in bytes
  timestamp: string       // ISO 8601 timestamp
}
```

## Examples

### Basic Usage

```javascript
import { getAgentExecuteCommand } from './fleet-agent-dispatcher.js';

// Get the SSH command for remote execution
const result = await getAgentExecuteCommand(
  'server-03',
  'opus',
  'Analyze this code for security vulnerabilities'
);

console.log('SSH Command:', result.command);
console.log('Server:', result.server);
console.log('Model:', result.model);
console.log('Job ID:', result.jobId);
```

Output:
```
SSH Command: ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 server-03 "export ANTHROPIC_VERTEX_PROJECT_ID='itpc-gcp-uie-eng-claude' && export CLAUDE_CODE_USE_VERTEX='1' && export GOOGLE_GENAI_USE_VERTEXAI='True' && cd '/home/sfloess/Development' && claude -p --dangerously-skip-permissions --output-format json --max-turns 50 --no-session-persistence 'Analyze this code for security vulnerabilities'"
Server: server-03
Model: opus
Job ID: job-1686325402123-abc123
```

### With Schema Validation

```javascript
const schema = {
  type: 'object',
  properties: {
    vulnerabilities: {
      type: 'array',
      items: { type: 'string' }
    },
    riskLevel: {
      type: 'string',
      enum: ['low', 'medium', 'high']
    }
  }
};

const result = await getAgentExecuteCommand(
  'server-01',
  'sonnet',
  'Check the code',
  { schema }
);

console.log('Command includes schema validation:', 
  result.command.includes('--output-format json'));
```

### Handling Server Instances with Ports

```javascript
// Server instance with port is automatically handled
const result = await getAgentExecuteCommand(
  'server-01:9100',  // Port automatically stripped
  'haiku',
  'Quick analysis'
);

console.log(result.server);  // Output: 'server-01' (port removed)
```

### Custom Job ID

```javascript
const jobId = `audit-${Date.now()}`;

const result = await getAgentExecuteCommand(
  'server-02',
  'opus',
  'Audit prompt',
  { jobId }
);

console.log(result.jobId);  // Output: 'audit-1686325402123'
```

### Command Logging and Auditing

```javascript
async function auditAgentExecution(server, model, prompt) {
  const result = await getAgentExecuteCommand(server, model, prompt);
  
  // Log for compliance/debugging
  console.log(`[${result.timestamp}] Audit Log`);
  console.log(`  Job ID: ${result.jobId}`);
  console.log(`  Server: ${result.server}`);
  console.log(`  Model: ${result.model}`);
  console.log(`  Prompt Size: ${result.promptLength} bytes`);
  console.log(`  Command: ${result.command}`);
  
  // Return for further processing
  return result;
}
```

### Integration with Execution Pipeline

```javascript
// Step 1: Generate command (inspect/audit)
const cmdResult = await getAgentExecuteCommand(
  'server-03',
  'opus',
  'Process data'
);

// Step 2: Log/audit the command
console.log('About to execute:', cmdResult.command);

// Step 3: Execute the command (manual or via executeOnServer)
const execResult = exec(cmdResult.command);

// Step 4: Process results
const output = JSON.parse(execResult.stdout);
```

## Command Structure

The generated SSH command follows this structure:

```
ssh [SSH_OPTIONS] [SERVER] "[REMOTE_CMD]"
```

Where:

- **SSH_OPTIONS**: `-o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10`
- **SERVER**: The target server hostname (e.g., `server-03`)
- **REMOTE_CMD**: Full remote command including:
  - Environment exports (VERTEX AI, Claude Code settings)
  - Working directory change to NFS mount
  - Claude command with flags and prompt

### Example Breakdown

```
ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 server-03 \
  "export ANTHROPIC_VERTEX_PROJECT_ID='...' && \
   export CLAUDE_CODE_USE_VERTEX='1' && \
   export GOOGLE_GENAI_USE_VERTEXAI='True' && \
   cd '/home/sfloess/Development' && \
   claude -p --dangerously-skip-permissions --output-format json --max-turns 50 --no-session-persistence '[PROMPT]'"
```

## Prompt Handling

The function automatically handles prompts of any size:

- **Small prompts** (< 4KB): Passed inline via SSH command
- **Large prompts** (≥ 4KB): Written to NFS file, read by remote claude

Large prompt files are:
- Written to: `~/Development/fleet-results/.prompts/{jobId}.txt`
- Referenced in command: `claude -p ... "$(cat '/path/to/prompt.txt')"`
- Cleaned up after execution

## Error Handling

```javascript
try {
  const result = await getAgentExecuteCommand(
    'server-99',  // Invalid server
    'opus',
    'Test'
  );
} catch (err) {
  console.error('Error code:', err.code);           // 'COMMAND_BUILD_FAILED'
  console.error('Error details:', err.details);      // {server, model, error}
  console.error('Error message:', err.message);
}
```

## Environment Variables

The generated command includes these environment exports:

- `ANTHROPIC_VERTEX_PROJECT_ID`: Vertex AI project ID
- `CLAUDE_CODE_USE_VERTEX`: Enable Vertex AI (`'1'`)
- `GOOGLE_GENAI_USE_VERTEXAI`: Enable Vertex for Gemini (`'True'`)

These are sourced from the RemoteExecutor configuration or environment.

## Claude Flags

The generated command uses these claude-cli flags:

- `--dangerously-skip-permissions`: Skip permission checks
- `--output-format json`: Return structured JSON output
- `--max-turns 50`: Maximum interaction turns
- `--no-session-persistence`: Don't persist session state

## Integration Points

### With Fleet Dispatcher

```javascript
import { dispatchViaFleet } from './fleet-agent-dispatcher.js';
import { executeOnServer } from './fleet-agent-dispatcher.js';

// Step 1: Dispatch job (returns server assignment)
const dispatch = await fleetUtils.dispatchAgent(model, prompt, opts);

// Step 2: Get the command that would be executed
const cmdInfo = await getAgentExecuteCommand(
  dispatch.server,
  model,
  prompt
);

// Step 3: Execute (using the command info for logging)
console.log('Executing:', cmdInfo.command);
const result = await executeOnServer(
  dispatch.server,
  model,
  prompt,
  schema,
  { jobId: dispatch.job_id }
);
```

### With REST API

If implementing as a REST endpoint:

```javascript
// GET /agent/execute
export async function handleAgentExecuteRequest(req, res) {
  const { server, model, prompt, schema, jobId } = req.body;
  
  try {
    const result = await getAgentExecuteCommand(
      server,
      model,
      prompt,
      { schema, jobId }
    );
    
    res.json({
      success: true,
      command: result.command,
      metadata: {
        server: result.server,
        model: result.model,
        jobId: result.jobId,
        promptLength: result.promptLength,
        timestamp: result.timestamp
      }
    });
  } catch (err) {
    res.status(400).json({
      success: false,
      error: err.message,
      code: err.code
    });
  }
}
```

## Use Cases

1. **Security Auditing**: Inspect commands before they run
2. **Logging & Compliance**: Record exact commands executed
3. **Debugging**: Verify command structure and environment
4. **Dry Run**: Get command without executing
5. **Custom Execution**: Wrap or modify commands before running
6. **Command Templates**: Generate reusable SSH commands
7. **Monitoring**: Track what agents are executing where

## Related Functions

- `buildSshCommand()`: Internal function to build command
- `executeOnServer()`: Actually execute the command
- `dispatchViaFleet()`: Full dispatch pipeline with execution
- `RemoteExecutor.buildCommand()`: Lower-level command builder

## Testing

Run the test suite:

```bash
node fleet-agent-dispatcher.test.js
```

Tests for SSH command generation (TEST SUITE 4):
- ✅ Generates valid SSH command structure
- ✅ Extracts server name from instance with port
- ✅ Includes metadata (jobId, timestamp, promptLength)
- ✅ Command includes required claude flags
