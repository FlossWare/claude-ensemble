export const meta = {
  name: 'code-sdlc-auto-continuous',
  description: 'Runs code-sdlc-auto in a loop until codebase is clean (delegates to sdlc-loop.sh)',
  whenToUse: 'When you want the full SDLC pipeline to run repeatedly until no issues remain',
  autonomous: true,
  phases: [
    { title: 'Launch', detail: 'Execute sdlc-loop.sh shell script' },
  ],
}

log('═'.repeat(60))
log('🔄 CONTINUOUS SDLC LOOP')
log('═'.repeat(60))
log('')
log('⚠️  NOTE: This workflow delegates to sdlc-loop.sh to avoid workflow nesting limits.')
log('   Workflows can only nest 1 level deep in Claude Code.')
log('')
log('Runs the full 7-phase SDLC pipeline repeatedly until clean:')
log('  1. Development → code-review-auto + code-solve-auto')
log('  2. Testing → code-test-auto')
log('  3. PR Review → code-pr-review-auto')
log('  4. Security → code-security-auto')
log('  5. Documentation → code-doc-auto')
log('  6. Release → code-release-notes-auto')
log('  7. Summary → Aggregate results')
log('')
log('Loop continues until codebase is clean or max iterations reached.')
log('═'.repeat(60))
log('')

// Parse args
const iterations = args?.iterations || 5
const budgetPerIteration = args?.budget || '200k'

log(`📋 Configuration:`)
log(`   Max iterations: ${iterations}`)
log(`   Budget per iteration: ${budgetPerIteration}`)
log('')

// Call the shell script (workaround for nesting limitation)
log(`🚀 Launching sdlc-loop.sh...`)
log('')

const scriptResult = await agent(`Run the continuous SDLC loop script:

cd ${process.env.HOME}/.claude/workflows
bash ./sdlc-loop.sh ${iterations} ${budgetPerIteration}

This script runs all 7 SDLC phases in sequence, looping until the codebase is clean.
Each workflow runs in a fresh Claude session to avoid nesting limitations.

Return the final summary and exit code.`, {
  label: 'sdlc-loop',
  schema: {
    type: 'object',
    properties: {
      exit_code: { type: 'number' },
      summary: { type: 'string' },
      iterations_run: { type: 'number' },
      final_status: { type: 'string' }
    }
  }
})

log('')
log('═'.repeat(60))
log('🏁 CONTINUOUS SDLC LOOP COMPLETE')
log('═'.repeat(60))
log('')
log(`Exit code: ${scriptResult?.exit_code || 'unknown'}`)
log(`Iterations run: ${scriptResult?.iterations_run || iterations}`)
log(`Final status: ${scriptResult?.final_status || 'See script output above'}`)
log('')

return scriptResult
