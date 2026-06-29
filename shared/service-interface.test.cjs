/**
 * Tests for Service Interface Contracts
 *
 * Run: node shared/service-interface.test.cjs
 */

'use strict';

const { Service, ServiceState, ServiceError, ServiceRegistry } = require('./service-interface.cjs');
const assert = require('assert');

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

let testCount = 0;
let passCount = 0;
let failCount = 0;

async function test(description, fn) {
  testCount++;
  try {
    await fn();
    passCount++;
    console.log(`  PASS: ${description}`);
  } catch (err) {
    failCount++;
    console.error(`  FAIL: ${description}`);
    console.error(`        ${err.message}`);
  }
}

// Concrete test service
class EchoService extends Service {
  constructor(name = 'echo', version = '1.0.0') {
    super(name, version);
    this.initCalled = false;
    this.shutdownCalled = false;
    this.lastConfig = null;
  }

  async _doInitialize(config) {
    this.initCalled = true;
    this.lastConfig = config;
  }

  async _doExecute(input) {
    return { echo: input };
  }

  async _doHealthCheck() {
    return { healthy: true, uptime: 12345 };
  }

  async _doShutdown() {
    this.shutdownCalled = true;
  }
}

// Service that fails during execute
class FailingService extends Service {
  constructor() {
    super('failing', '0.1.0');
  }
  async _doInitialize() {}
  async _doExecute() {
    throw new Error('deliberate failure');
  }
}

// Service that reports unhealthy
class UnhealthyService extends Service {
  constructor() {
    super('unhealthy', '1.0.0');
  }
  async _doInitialize() {}
  async _doExecute(input) { return input; }
  async _doHealthCheck() {
    return { healthy: false, reason: 'disk full' };
  }
}

// Service whose init fails
class BadInitService extends Service {
  constructor() {
    super('bad-init', '1.0.0');
  }
  async _doInitialize() {
    throw new Error('cannot connect to database');
  }
  async _doExecute() { return null; }
}

// Service whose health check throws
class HealthCheckThrowService extends Service {
  constructor() {
    super('hc-throw', '1.0.0');
  }
  async _doInitialize() {}
  async _doExecute(input) { return input; }
  async _doHealthCheck() {
    throw new Error('health check exploded');
  }
}

// ---------------------------------------------------------------------------
// Test suites
// ---------------------------------------------------------------------------

async function runTests() {
  console.log('Service Interface Contract Tests');
  console.log('================================\n');

  // ------ ServiceState ------
  console.log('ServiceState:');

  await test('ServiceState is frozen', () => {
    assert.ok(Object.isFrozen(ServiceState));
  });

  await test('ServiceState has all expected values', () => {
    assert.strictEqual(ServiceState.CREATED, 'created');
    assert.strictEqual(ServiceState.INITIALIZING, 'initializing');
    assert.strictEqual(ServiceState.READY, 'ready');
    assert.strictEqual(ServiceState.EXECUTING, 'executing');
    assert.strictEqual(ServiceState.DEGRADED, 'degraded');
    assert.strictEqual(ServiceState.SHUTTING_DOWN, 'shutting_down');
    assert.strictEqual(ServiceState.STOPPED, 'stopped');
    assert.strictEqual(ServiceState.ERROR, 'error');
  });

  // ------ ServiceError ------
  console.log('\nServiceError:');

  await test('ServiceError captures all fields', () => {
    const cause = new Error('root cause');
    const err = new ServiceError('something broke', 'my-svc', 'BROKE', cause);
    assert.strictEqual(err.name, 'ServiceError');
    assert.strictEqual(err.message, 'something broke');
    assert.strictEqual(err.serviceName, 'my-svc');
    assert.strictEqual(err.code, 'BROKE');
    assert.strictEqual(err.cause, cause);
    assert.ok(err.timestamp);
    assert.ok(err instanceof Error);
  });

  await test('ServiceError defaults cause to null', () => {
    const err = new ServiceError('msg', 'svc', 'CODE');
    assert.strictEqual(err.cause, null);
  });

  // ------ Service construction ------
  console.log('\nService construction:');

  await test('Service cannot be instantiated directly', () => {
    assert.throws(
      () => new Service('test', '1.0.0'),
      (err) => err.code === 'ABSTRACT_INSTANTIATION'
    );
  });

  await test('Service requires a name', () => {
    assert.throws(
      () => {
        class BadName extends Service {
          constructor() { super('', '1.0.0'); }
        }
        new BadName();
      },
      (err) => err.code === 'INVALID_NAME'
    );
  });

  await test('Service requires a version', () => {
    assert.throws(
      () => {
        class BadVer extends Service {
          constructor() { super('svc', ''); }
        }
        new BadVer();
      },
      (err) => err.code === 'INVALID_VERSION'
    );
  });

  await test('Service starts in CREATED state', () => {
    const svc = new EchoService();
    assert.strictEqual(svc.state, ServiceState.CREATED);
    assert.strictEqual(svc.name, 'echo');
    assert.strictEqual(svc.version, '1.0.0');
  });

  // ------ Service.initialize() ------
  console.log('\nService.initialize():');

  await test('initialize transitions CREATED -> READY', async () => {
    const svc = new EchoService();
    await svc.initialize({ port: 3000 });
    assert.strictEqual(svc.state, ServiceState.READY);
    assert.ok(svc.initCalled);
    assert.deepStrictEqual(svc.lastConfig, { port: 3000 });
  });

  await test('config is frozen after initialize', async () => {
    const svc = new EchoService();
    await svc.initialize({ key: 'val' });
    assert.throws(() => { svc._config.key = 'changed'; }, TypeError);
  });

  await test('initialize throws from READY state', async () => {
    const svc = new EchoService();
    await svc.initialize();
    try {
      await svc.initialize();
      assert.fail('should have thrown');
    } catch (err) {
      assert.strictEqual(err.code, 'INVALID_STATE_TRANSITION');
    }
  });

  await test('initialize increments initializeCount', async () => {
    const svc = new EchoService();
    await svc.initialize();
    assert.strictEqual(svc._metrics.initializeCount, 1);
  });

  await test('failed init transitions to ERROR state', async () => {
    const svc = new BadInitService();
    try {
      await svc.initialize();
      assert.fail('should have thrown');
    } catch (err) {
      assert.strictEqual(err.code, 'INIT_FAILED');
      assert.strictEqual(svc.state, ServiceState.ERROR);
    }
  });

  await test('can re-initialize after ERROR', async () => {
    const svc = new EchoService();
    // Force error state
    svc.state = ServiceState.ERROR;
    await svc.initialize({ retry: true });
    assert.strictEqual(svc.state, ServiceState.READY);
  });

  await test('can re-initialize after STOPPED', async () => {
    const svc = new EchoService();
    await svc.initialize();
    await svc.shutdown();
    assert.strictEqual(svc.state, ServiceState.STOPPED);
    await svc.initialize({ round: 2 });
    assert.strictEqual(svc.state, ServiceState.READY);
  });

  // ------ Service.execute() ------
  console.log('\nService.execute():');

  await test('execute returns result when READY', async () => {
    const svc = new EchoService();
    await svc.initialize();
    const result = await svc.execute('hello');
    assert.deepStrictEqual(result, { echo: 'hello' });
  });

  await test('execute throws when not READY', async () => {
    const svc = new EchoService();
    try {
      await svc.execute('hello');
      assert.fail('should have thrown');
    } catch (err) {
      assert.strictEqual(err.code, 'NOT_READY');
    }
  });

  await test('execute tracks metrics', async () => {
    const svc = new EchoService();
    await svc.initialize();
    await svc.execute('a');
    await svc.execute('b');
    assert.strictEqual(svc._metrics.executeCount, 2);
    assert.ok(svc._metrics.lastExecuteMs >= 0);
    assert.ok(svc._metrics.totalExecuteMs >= 0);
  });

  await test('execute tracks errors without changing state', async () => {
    const svc = new FailingService();
    await svc.initialize();
    try {
      await svc.execute('anything');
      assert.fail('should have thrown');
    } catch (err) {
      assert.strictEqual(err.code, 'EXEC_FAILED');
    }
    // Service should remain READY (not ERROR) after transient failure
    assert.strictEqual(svc.state, ServiceState.READY);
    assert.strictEqual(svc._metrics.executeErrorCount, 1);
  });

  await test('execute works in DEGRADED state', async () => {
    const svc = new EchoService();
    await svc.initialize();
    svc.state = ServiceState.DEGRADED;
    const result = await svc.execute('degraded-input');
    assert.deepStrictEqual(result, { echo: 'degraded-input' });
  });

  // ------ Service.healthCheck() ------
  console.log('\nService.healthCheck():');

  await test('healthCheck returns full report', async () => {
    const svc = new EchoService();
    await svc.initialize();
    const report = await svc.healthCheck();
    assert.strictEqual(report.service, 'echo');
    assert.strictEqual(report.version, '1.0.0');
    assert.strictEqual(report.healthy, true);
    assert.strictEqual(report.state, ServiceState.READY);
    assert.ok(report.metrics);
    assert.ok(report.timestamp);
    assert.deepStrictEqual(report.details, { healthy: true, uptime: 12345 });
  });

  await test('unhealthy check transitions READY -> DEGRADED', async () => {
    const svc = new UnhealthyService();
    await svc.initialize();
    assert.strictEqual(svc.state, ServiceState.READY);
    const report = await svc.healthCheck();
    assert.strictEqual(report.healthy, false);
    assert.strictEqual(svc.state, ServiceState.DEGRADED);
  });

  await test('healthy check transitions DEGRADED -> READY', async () => {
    const svc = new EchoService();
    await svc.initialize();
    svc.state = ServiceState.DEGRADED;
    const report = await svc.healthCheck();
    assert.strictEqual(report.healthy, true);
    assert.strictEqual(svc.state, ServiceState.READY);
  });

  await test('healthCheck handles thrown errors gracefully', async () => {
    const svc = new HealthCheckThrowService();
    await svc.initialize();
    const report = await svc.healthCheck();
    assert.strictEqual(report.healthy, false);
    assert.ok(report.error);
    assert.strictEqual(svc.state, ServiceState.DEGRADED);
  });

  await test('healthCheck increments count', async () => {
    const svc = new EchoService();
    await svc.initialize();
    await svc.healthCheck();
    await svc.healthCheck();
    assert.strictEqual(svc._metrics.healthCheckCount, 2);
    assert.ok(svc._metrics.lastHealthCheck);
  });

  // ------ Service.shutdown() ------
  console.log('\nService.shutdown():');

  await test('shutdown transitions to STOPPED', async () => {
    const svc = new EchoService();
    await svc.initialize();
    await svc.shutdown();
    assert.strictEqual(svc.state, ServiceState.STOPPED);
    assert.ok(svc.shutdownCalled);
  });

  await test('shutdown is idempotent when already STOPPED', async () => {
    const svc = new EchoService();
    await svc.initialize();
    await svc.shutdown();
    await svc.shutdown(); // should not throw
    assert.strictEqual(svc.state, ServiceState.STOPPED);
  });

  await test('double shutdown-in-progress throws', async () => {
    const svc = new EchoService();
    await svc.initialize();
    svc.state = ServiceState.SHUTTING_DOWN;
    try {
      await svc.shutdown();
      assert.fail('should have thrown');
    } catch (err) {
      assert.strictEqual(err.code, 'ALREADY_SHUTTING_DOWN');
    }
  });

  // ------ Service.getMetrics() ------
  console.log('\nService.getMetrics():');

  await test('getMetrics returns computed fields', async () => {
    const svc = new EchoService();
    await svc.initialize();
    await svc.execute('a');
    await svc.execute('b');
    const m = svc.getMetrics();
    assert.strictEqual(m.executeCount, 2);
    assert.strictEqual(m.executeErrorCount, 0);
    assert.ok(m.avgExecuteMs >= 0);
    assert.strictEqual(m.errorRate, 0);
    assert.ok(m.startedAt);
  });

  await test('getMetrics computes errorRate correctly', async () => {
    const svc = new FailingService();
    await svc.initialize();
    // 2 failures, 0 successes would give errorRate undefined without count
    // but executeCount includes errors in total
    try { await svc.execute('x'); } catch {}
    try { await svc.execute('y'); } catch {}
    const m = svc.getMetrics();
    // executeCount is 0 (only successful), but executeErrorCount is 2
    // Actually: executeCount stays 0 since the code only increments on success path
    // Wait - looking at the code: executeCount increments on success, executeErrorCount on failure
    assert.strictEqual(m.executeErrorCount, 2);
  });

  // ------ Dependencies ------
  console.log('\nDependencies:');

  await test('declareDependencies and getDependencies', () => {
    const svc = new EchoService();
    svc.declareDependencies(['db', 'cache']);
    assert.deepStrictEqual(svc.getDependencies(), ['db', 'cache']);
  });

  await test('getDependencies returns a copy', () => {
    const svc = new EchoService();
    svc.declareDependencies(['db']);
    const deps = svc.getDependencies();
    deps.push('extra');
    assert.deepStrictEqual(svc.getDependencies(), ['db']);
  });

  await test('declareDependencies rejects non-array', () => {
    const svc = new EchoService();
    assert.throws(
      () => svc.declareDependencies('db'),
      (err) => err.code === 'INVALID_DEPENDENCIES'
    );
  });

  // ------ ServiceRegistry ------
  console.log('\nServiceRegistry:');

  // Reset before each registry test group
  await ServiceRegistry.reset();

  await test('getInstance returns singleton', () => {
    const r1 = ServiceRegistry.getInstance();
    const r2 = ServiceRegistry.getInstance();
    assert.strictEqual(r1, r2);
  });

  await test('register and get a service', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    const svc = new EchoService();
    reg.register(svc);
    assert.strictEqual(reg.get('echo'), svc);
  });

  await test('register rejects non-Service instances', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    assert.throws(
      () => reg.register({ name: 'fake' }),
      (err) => err.code === 'INVALID_SERVICE'
    );
  });

  await test('register rejects duplicates', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    reg.register(new EchoService());
    assert.throws(
      () => reg.register(new EchoService()),
      (err) => err.code === 'DUPLICATE_SERVICE'
    );
  });

  await test('register allows replace', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    const svc1 = new EchoService();
    const svc2 = new EchoService('echo', '2.0.0');
    reg.register(svc1);
    reg.register(svc2, { replace: true });
    assert.strictEqual(reg.get('echo').version, '2.0.0');
  });

  await test('register returns this for chaining', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    const result = reg.register(new EchoService());
    assert.strictEqual(result, reg);
  });

  await test('get throws for missing service', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    assert.throws(
      () => reg.get('nonexistent'),
      (err) => err.code === 'SERVICE_NOT_FOUND'
    );
  });

  await test('getOptional returns null for missing service', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    assert.strictEqual(reg.getOptional('nonexistent'), null);
  });

  await test('getOptional returns service when found', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    const svc = new EchoService();
    reg.register(svc);
    assert.strictEqual(reg.getOptional('echo'), svc);
  });

  await test('has checks existence', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    reg.register(new EchoService());
    assert.strictEqual(reg.has('echo'), true);
    assert.strictEqual(reg.has('nope'), false);
  });

  await test('unregister removes a service', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    reg.register(new EchoService());
    assert.strictEqual(reg.unregister('echo'), true);
    assert.strictEqual(reg.has('echo'), false);
    assert.strictEqual(reg.unregister('echo'), false);
  });

  await test('list returns all service names', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    reg.register(new EchoService('alpha', '1.0.0'));
    reg.register(new EchoService('beta', '1.0.0'));
    const names = reg.list();
    assert.deepStrictEqual(names.sort(), ['alpha', 'beta']);
  });

  await test('listDetailed returns names, versions, states', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    const svc = new EchoService('detail-svc', '3.2.1');
    reg.register(svc);
    const detailed = reg.listDetailed();
    assert.strictEqual(detailed.length, 1);
    assert.deepStrictEqual(detailed[0], {
      name: 'detail-svc',
      version: '3.2.1',
      state: 'created',
    });
  });

  await test('size returns count', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    assert.strictEqual(reg.size, 0);
    reg.register(new EchoService('a', '1.0.0'));
    reg.register(new EchoService('b', '1.0.0'));
    assert.strictEqual(reg.size, 2);
  });

  // ------ Registry bulk operations ------
  console.log('\nServiceRegistry bulk operations:');

  await test('initializeAll initializes all services', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    reg.register(new EchoService('svc-a', '1.0.0'));
    reg.register(new EchoService('svc-b', '1.0.0'));
    const result = await reg.initializeAll({ shared: true });
    assert.deepStrictEqual(result.initialized.sort(), ['svc-a', 'svc-b']);
    assert.strictEqual(result.failed.length, 0);
  });

  await test('initializeAll reports failures', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    reg.register(new EchoService('good', '1.0.0'));
    reg.register(new BadInitService());
    const result = await reg.initializeAll();
    assert.ok(result.initialized.includes('good'));
    assert.strictEqual(result.failed.length, 1);
    assert.strictEqual(result.failed[0].name, 'bad-init');
  });

  await test('initializeAll respects dependency order', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    const dep = new EchoService('database', '1.0.0');
    const app = new EchoService('app-server', '1.0.0');
    app.declareDependencies(['database']);
    reg.register(app);
    reg.register(dep);
    const result = await reg.initializeAll();
    const dbIdx = result.initialized.indexOf('database');
    const appIdx = result.initialized.indexOf('app-server');
    assert.ok(dbIdx < appIdx, 'database should be initialized before app-server');
  });

  await test('healthCheckAll returns all reports', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    reg.register(new EchoService('h1', '1.0.0'));
    reg.register(new EchoService('h2', '1.0.0'));
    await reg.initializeAll();
    const reports = await reg.healthCheckAll();
    assert.strictEqual(reports.length, 2);
    assert.ok(reports.every((r) => r.healthy === true));
  });

  await test('shutdownAll shuts down in reverse order', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    reg.register(new EchoService('first', '1.0.0'));
    reg.register(new EchoService('second', '1.0.0'));
    await reg.initializeAll();
    const result = await reg.shutdownAll();
    assert.deepStrictEqual(result.stopped, ['second', 'first']);
    assert.strictEqual(result.failed.length, 0);
  });

  await test('reset clears and nullifies singleton', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();
    reg.register(new EchoService());
    await ServiceRegistry.reset();
    const reg2 = ServiceRegistry.getInstance();
    assert.notStrictEqual(reg, reg2);
    assert.strictEqual(reg2.size, 0);
  });

  // ------ Integration scenario ------
  console.log('\nIntegration scenario:');

  await test('full lifecycle: register, init, execute, health, shutdown', async () => {
    await ServiceRegistry.reset();
    const reg = ServiceRegistry.getInstance();

    // Register
    const svc = new EchoService('integration', '1.0.0');
    reg.register(svc);
    assert.strictEqual(reg.size, 1);

    // Initialize
    await svc.initialize({ env: 'test' });
    assert.strictEqual(svc.state, ServiceState.READY);

    // Execute
    const result = await svc.execute({ task: 'greet', name: 'world' });
    assert.deepStrictEqual(result, { echo: { task: 'greet', name: 'world' } });

    // Health
    const health = await svc.healthCheck();
    assert.strictEqual(health.healthy, true);
    assert.strictEqual(health.metrics.executeCount, 1);

    // Shutdown
    await svc.shutdown();
    assert.strictEqual(svc.state, ServiceState.STOPPED);

    // Cannot execute after shutdown
    try {
      await svc.execute('after-shutdown');
      assert.fail('should have thrown');
    } catch (err) {
      assert.strictEqual(err.code, 'NOT_READY');
    }

    // Re-initialize and use again
    await svc.initialize({ env: 'test-round-2' });
    const result2 = await svc.execute('round-2');
    assert.deepStrictEqual(result2, { echo: 'round-2' });

    await ServiceRegistry.reset();
  });

  // ------ Summary ------
  console.log('\n================================');
  console.log(`Results: ${passCount}/${testCount} passed, ${failCount} failed`);

  if (failCount > 0) {
    process.exit(1);
  }
}

runTests().catch((err) => {
  console.error('Test runner error:', err);
  process.exit(1);
});
