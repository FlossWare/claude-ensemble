export const meta = {
  name: 'test-fleet-dynamic-import',
  description: 'Validate dynamic import() of fleet telemetry works in workflow runtime',
  whenToUse: 'Testing fleet dispatcher integration before full migration',
  phases: [
    { title: 'Import Test', detail: 'Test dynamic import of fleet-telemetry-minimal.js' },
    { title: 'Wrapper Test', detail: 'Test _agent wrapper with telemetry' },
  ],
};

export default async function({ phase, log, agent }) {

phase('Import Test');
log('Testing dynamic import of fleet-telemetry-minimal.js...');

let _telemetry = null;
try {
  _telemetry = await import('./fleet-telemetry-minimal.js');
  log('Dynamic import WORKS');
  log('  - inferJobType: ' + typeof _telemetry.inferJobType);
  log('  - dispatchAgent: ' + typeof _telemetry.dispatchAgent);
  log('  - completeAgent: ' + typeof _telemetry.completeAgent);
  log('  - telemetryWrap: ' + typeof _telemetry.telemetryWrap);
} catch (error) {
  log('Dynamic import FAILED: ' + error.message);
  return {
    status: 'failed',
    error: error.message,
    phase: 'import',
  };
}

phase('Wrapper Test');
log('Testing fleet-aware agent wrapper...');

const _agent = async (prompt, opts = {}) => {
  if (!_telemetry || process.env.FLEET_DISPATCHER === 'false') {
    return agent(prompt, opts);
  }
  return _telemetry.telemetryWrap(
    () => agent(prompt, opts),
    { model: opts.model || 'sonnet', jobType: _telemetry.inferJobType(opts) }
  );
};

try {
  const result = await _agent('What is 2+2? Answer with just the number.', {
    model: 'haiku',
    label: 'test-agent',
  });

  log('_agent wrapper WORKS');
  log('  Result: ' + result);

  return {
    status: 'success',
    import_works: true,
    wrapper_works: true,
    test_result: result,
  };
} catch (error) {
  log('_agent wrapper FAILED: ' + error.message);
  return {
    status: 'failed',
    error: error.message,
    phase: 'wrapper',
    import_works: true,
    wrapper_works: false,
  };
}

}
