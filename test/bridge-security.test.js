import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

test('caching bridge does not generate Python source or invoke a shell', () => {
  const source = fs.readFileSync('shared/caching-bridge.js', 'utf8')

  assert.match(source, /execFileSync\(PYTHON, \[CACHE_BRIDGE\]/)
  assert.doesNotMatch(source, /python3 -c/)
  assert.doesNotMatch(source, /execSync\(/)
  assert.match(source, /input: JSON\.stringify\(payload\)/)
})

test('compression bridge does not generate Python source or invoke a shell', () => {
  const source = fs.readFileSync('shared/compression-bridge.js', 'utf8')

  assert.match(source, /execFileSync\(PYTHON, \[COMPRESSION_BRIDGE\]/)
  assert.doesNotMatch(source, /python3 -c/)
  assert.doesNotMatch(source, /execSync\(/)
  assert.match(source, /input: JSON\.stringify\(payload\)/)
})

test('Python bridge entry points are fixed programs', () => {
  for (const file of ['scripts/python/cache-bridge.py', 'scripts/python/compression-bridge.py']) {
    const source = fs.readFileSync(file, 'utf8')
    assert.match(source, /json\.load\(sys\.stdin\)/)
    assert.doesNotMatch(source, /exec\(|eval\(/)
  }
})
