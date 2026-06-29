/**
 * Example usage of getAgentExecuteCommand for /agent/execute endpoint
 *
 * Run with: node examples-agent-execute.js
 */

import { getAgentExecuteCommand } from './fleet-agent-dispatcher.js';

console.log('Agent Execute Endpoint - Usage Examples\n');
console.log('='.repeat(60) + '\n');

// Example 1: Basic command generation
console.log('Example 1: Basic SSH Command Generation\n');
try {
  const result1 = await getAgentExecuteCommand(
    'server-03',
    'opus',
    'Analyze this code for potential bugs and security issues'
  );

  console.log('Generated SSH Command:');
  console.log(`  Command: ${result1.command.substring(0, 100)}...`);
  console.log(`  Server: ${result1.server}`);
  console.log(`  Model: ${result1.model}`);
  console.log(`  Job ID: ${result1.jobId}`);
  console.log(`  Prompt Length: ${result1.promptLength} bytes`);
  console.log(`  Timestamp: ${result1.timestamp}`);
} catch (err) {
  console.error('Error:', err.message);
}

console.log('\n' + '-'.repeat(60) + '\n');

// Example 2: With output schema
console.log('Example 2: Command with Output Schema\n');
try {
  const schema = {
    type: 'object',
    properties: {
      issues: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            severity: { type: 'string', enum: ['low', 'medium', 'high'] },
            description: { type: 'string' }
          }
        }
      },
      summary: { type: 'string' }
    }
  };

  const result2 = await getAgentExecuteCommand(
    'server-01',
    'sonnet',
    'Review code quality',
    { schema }
  );

  console.log('Command with schema:');
  console.log(`  Server: ${result2.server}`);
  console.log(`  Model: ${result2.model}`);
  console.log(`  Includes JSON output flag: ${result2.command.includes('--output-format json')}`);
  console.log(`  Full command length: ${result2.command.length} characters`);
} catch (err) {
  console.error('Error:', err.message);
}

console.log('\n' + '-'.repeat(60) + '\n');

// Example 3: Server instance with port
console.log('Example 3: Server Instance with Port Handling\n');
try {
  const result3 = await getAgentExecuteCommand(
    'server-02:9100',
    'haiku',
    'Quick analysis'
  );

  console.log('Port handling:');
  console.log(`  Input: server-02:9100`);
  console.log(`  Extracted server: ${result3.server}`);
  console.log(`  Port correctly removed: ${result3.server === 'server-02'}`);
} catch (err) {
  console.error('Error:', err.message);
}

console.log('\n' + '-'.repeat(60) + '\n');

// Example 4: Custom job ID
console.log('Example 4: Custom Job ID for Tracking\n');
try {
  const customJobId = `audit-${Date.now()}-compliance`;

  const result4 = await getAgentExecuteCommand(
    'server-03',
    'opus',
    'Run compliance audit',
    { jobId: customJobId }
  );

  console.log('Custom job ID:');
  console.log(`  Requested Job ID: ${customJobId}`);
  console.log(`  Actual Job ID: ${result4.jobId}`);
  console.log(`  IDs match: ${result4.jobId === customJobId}`);
} catch (err) {
  console.error('Error:', err.message);
}

console.log('\n' + '-'.repeat(60) + '\n');

// Example 5: Command inspection for logging
console.log('Example 5: Command Inspection for Logging/Auditing\n');
try {
  const result5 = await getAgentExecuteCommand(
    'server-01',
    'sonnet',
    'Process data from API'
  );

  // Format as audit log
  const auditLog = {
    timestamp: result5.timestamp,
    jobId: result5.jobId,
    server: result5.server,
    model: result5.model,
    promptSize: result5.promptLength,
    command: result5.command,
    sshOptionsInclude: {
      batchMode: result5.command.includes('BatchMode=yes'),
      strictHostKeyChecking: result5.command.includes('StrictHostKeyChecking=accept-new'),
      connectTimeout: result5.command.includes('ConnectTimeout=10')
    }
  };

  console.log('Audit Log Entry:');
  console.log(JSON.stringify(auditLog, null, 2));
} catch (err) {
  console.error('Error:', err.message);
}

console.log('\n' + '-'.repeat(60) + '\n');

// Example 6: Large prompt handling
console.log('Example 6: Large Prompt Handling\n');
try {
  const largePrompt = 'Analyze this code:\n\n' + 'x'.repeat(5000);
  const result6 = await getAgentExecuteCommand(
    'server-03',
    'opus',
    largePrompt
  );

  console.log('Large prompt handling:');
  console.log(`  Prompt size: ${result6.promptLength} bytes (>= 4096)`);
  console.log(`  Will use NFS file: ${result6.promptLength >= 4096}`);
  console.log(`  Job ID for NFS file: ${result6.jobId}`);
  console.log(`  Expected file path: ~/Development/fleet-results/.prompts/${result6.jobId}.txt`);
} catch (err) {
  console.error('Error:', err.message);
}

console.log('\n' + '-'.repeat(60) + '\n');

// Example 7: Command structure analysis
console.log('Example 7: Command Structure Analysis\n');
try {
  const result7 = await getAgentExecuteCommand(
    'server-02',
    'haiku',
    'Test prompt'
  );

  const cmd = result7.command;
  const parts = {
    isSSH: cmd.startsWith('ssh'),
    sshOptions: cmd.includes('BatchMode=yes'),
    vertexAI: cmd.includes('ANTHROPIC_VERTEX_PROJECT_ID'),
    claudeCode: cmd.includes('CLAUDE_CODE_USE_VERTEX'),
    genai: cmd.includes('GOOGLE_GENAI_USE_VERTEXAI'),
    nfsMount: cmd.includes('/home/sfloess/Development'),
    claudeCommand: cmd.includes('claude -p'),
    dangerouslySkipPerms: cmd.includes('--dangerously-skip-permissions'),
    jsonOutput: cmd.includes('--output-format json'),
    maxTurns: cmd.includes('--max-turns'),
    noSessionPersist: cmd.includes('--no-session-persistence')
  };

  console.log('Command Structure Analysis:');
  Object.entries(parts).forEach(([key, value]) => {
    console.log(`  ${key}: ${value ? '✓' : '✗'}`);
  });
} catch (err) {
  console.error('Error:', err.message);
}

console.log('\n' + '='.repeat(60));
console.log('\nAll examples completed!');
console.log('\nKey takeaways:');
console.log('  - getAgentExecuteCommand() returns the SSH command without executing');
console.log('  - Use this for inspection, auditing, or custom execution logic');
console.log('  - Large prompts (>=4KB) are automatically written to NFS files');
console.log('  - All environment variables and flags are pre-configured');
console.log('  - The command is ready to run with exec() or child_process.spawn()');
