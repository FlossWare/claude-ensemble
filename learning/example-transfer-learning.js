#!/usr/bin/env node
/**
 * Transfer Learning Usage Examples
 *
 * Demonstrates real-world usage patterns for transfer learning system.
 */

const transfer = require('./transfer-learning');

// ---------------------------------------------------------------------------
// Example 1: Bootstrap new Claude model
// ---------------------------------------------------------------------------

async function example1_bootstrapNewClaude() {
  console.log('\n=== Example 1: Bootstrap New Claude Model ===\n');

  // New model just released: claude-opus-4.5
  const result = await transfer.bootstrapNewModel('claude-opus-4.5');

  if (result.success) {
    console.log(`✓ Bootstrapped ${result.targetModel}`);
    console.log(`  Source models: ${result.sourceModels.length}`);

    for (const source of result.sourceModels) {
      console.log(`    - ${source.sourceModel}: similarity=${source.similarity.toFixed(3)}, ` +
                  `initial_confidence=${source.initialConfidence.toFixed(3)}`);
    }
  } else {
    console.log(`✗ Bootstrap failed: ${result.reason}`);
    console.log(`  ${result.message}`);
  }
}

// ---------------------------------------------------------------------------
// Example 2: Get calibration for code review task
// ---------------------------------------------------------------------------

async function example2_getCalibrationForTask() {
  console.log('\n=== Example 2: Get Calibration for Task ===\n');

  const calibration = await transfer.getTransferredCalibration(
    'claude-opus-4.5',
    'code-review'
  );

  console.log(`Source: ${calibration.source}`);
  console.log(`Native samples: ${calibration.nativeSamples || 0}`);
  console.log(`Calibration confidence: ${(calibration.calibrationConfidence * 100).toFixed(1)}%`);

  if (calibration.avgQuality !== undefined) {
    console.log(`\nPredicted performance:`);
    console.log(`  Quality: ${(calibration.avgQuality * 100).toFixed(1)}%`);
    console.log(`  Confidence: ${(calibration.avgConfidence * 100).toFixed(1)}%`);
    console.log(`  Success rate: ${(calibration.successRate * 100).toFixed(1)}%`);
  }

  if (calibration.transferSources && calibration.transferSources.length > 0) {
    console.log(`\nTransfer sources (${calibration.transferSources.length}):`);
    for (const source of calibration.transferSources) {
      console.log(`  - ${source.sourceModel}:`);
      console.log(`      similarity: ${source.similarity.toFixed(3)}`);
      console.log(`      decayed_confidence: ${source.decayedConfidence.toFixed(3)}`);
      console.log(`      days_elapsed: ${source.daysElapsed.toFixed(1)}`);
      console.log(`      weight: ${source.weight.toFixed(3)}`);
    }
  }
}

// ---------------------------------------------------------------------------
// Example 3: Simulate native data accumulation
// ---------------------------------------------------------------------------

async function example3_accumulateNativeData() {
  console.log('\n=== Example 3: Accumulate Native Data ===\n');

  const modelId = 'claude-opus-4.5';

  // Simulate 25 executions with varying quality
  console.log('Simulating executions...\n');

  for (let i = 1; i <= 25; i++) {
    const executionData = {
      quality_score: 0.75 + Math.random() * 0.25,  // 0.75 to 1.0
      confidence: 0.70 + Math.random() * 0.30,     // 0.70 to 1.0
      outcome: Math.random() > 0.1 ? 'success' : 'partial'  // 90% success rate
    };

    const update = await transfer.updateWithNativeData(modelId, executionData);

    if (i % 5 === 0) {
      console.log(`After ${update.nativeSamples} executions: ${update.transition}`);
    }

    if (update.transition === 'transferred_to_native') {
      console.log(`\n✓ Transitioned to native calibration!`);
      console.log(`  ${update.message}`);
      break;
    }
  }

  // Show final calibration
  console.log('\nFinal calibration:');
  const finalCalibration = await transfer.getTransferredCalibration(modelId, 'code-review');
  console.log(`  Source: ${finalCalibration.source}`);
  console.log(`  Native samples: ${finalCalibration.nativeSamples}`);
  console.log(`  Calibration confidence: ${(finalCalibration.calibrationConfidence * 100).toFixed(1)}%`);
}

// ---------------------------------------------------------------------------
// Example 4: Validate transfer quality
// ---------------------------------------------------------------------------

async function example4_validateTransfer() {
  console.log('\n=== Example 4: Validate Transfer Quality ===\n');

  const validation = await transfer.validateTransfer('claude-opus-4.5', 'code-review');

  if (!validation.success) {
    console.log(`Cannot validate: ${validation.reason}`);
    return;
  }

  console.log(`Model: ${validation.modelId}`);
  console.log(`Task: ${validation.taskType}`);
  console.log(`Native samples: ${validation.nativeSamples}\n`);

  console.log('Native performance:');
  console.log(`  Quality: ${(validation.native.avgQuality * 100).toFixed(1)}%`);
  console.log(`  Confidence: ${(validation.native.avgConfidence * 100).toFixed(1)}%`);
  console.log(`  Success rate: ${(validation.native.successRate * 100).toFixed(1)}%\n`);

  console.log('Transferred prediction:');
  console.log(`  Quality: ${(validation.transferred.avgQuality * 100).toFixed(1)}%`);
  console.log(`  Confidence: ${(validation.transferred.avgConfidence * 100).toFixed(1)}%`);
  console.log(`  Success rate: ${(validation.transferred.successRate * 100).toFixed(1)}%\n`);

  console.log('Prediction errors:');
  console.log(`  Quality error: ${(validation.errors.quality * 100).toFixed(1)}%`);
  console.log(`  Confidence error: ${(validation.errors.confidence * 100).toFixed(1)}%`);
  console.log(`  Success error: ${(validation.errors.success * 100).toFixed(1)}%\n`);

  console.log(`Transfer quality: ${(validation.transferQuality * 100).toFixed(1)}%`);
  console.log(`Assessment: ${validation.assessment.toUpperCase()}`);

  if (validation.transferSources) {
    console.log(`\nTransfer sources: ${validation.transferSources.length}`);
  }
}

// ---------------------------------------------------------------------------
// Example 5: Find similar models
// ---------------------------------------------------------------------------

async function example5_findSimilarModels() {
  console.log('\n=== Example 5: Find Similar Models ===\n');

  const db = await transfer.openDb();

  try {
    const similarModels = await transfer.findSimilarModels(
      db,
      'claude-opus-4.5',
      'code-review',
      10
    );

    if (similarModels.length === 0) {
      console.log('No similar models found (database may be empty)');
      return;
    }

    console.log(`Found ${similarModels.length} similar models:\n`);

    for (let i = 0; i < similarModels.length; i++) {
      const model = similarModels[i];
      console.log(`${(i + 1).toString().padStart(2)}. ${model.model}`);
      console.log(`    Similarity: ${(model.similarity * 100).toFixed(1)}%`);
      console.log(`    Executions: ${model.executionCount}`);
      console.log(`    Avg quality: ${(model.avgQuality * 100).toFixed(1)}%`);
      console.log(`    Avg confidence: ${(model.avgConfidence * 100).toFixed(1)}%\n`);
    }

  } finally {
    db.close();
  }
}

// ---------------------------------------------------------------------------
// Example 6: Model identifier parsing
// ---------------------------------------------------------------------------

async function example6_parseModelIdentifiers() {
  console.log('\n=== Example 6: Parse Model Identifiers ===\n');

  const models = [
    'claude-opus-4.5',
    'claude-sonnet-3.5',
    'claude-haiku-4',
    'gpt-4-turbo',
    'gpt-4o',
    'gemini-1.5-pro',
    'gemini-2.0-flash'
  ];

  console.log('Model identifier parsing:\n');

  for (const modelId of models) {
    const parsed = transfer.parseModelId(modelId);
    console.log(`${modelId.padEnd(20)} → ${parsed.provider}/${parsed.family}/${parsed.arch}`);
  }
}

// ---------------------------------------------------------------------------
// Example 7: Similarity matrix
// ---------------------------------------------------------------------------

async function example7_similarityMatrix() {
  console.log('\n=== Example 7: Similarity Matrix ===\n');

  const models = [
    'claude-opus-4',
    'claude-sonnet-4',
    'claude-haiku-4',
    'gpt-4-turbo',
    'gemini-1.5-pro'
  ];

  console.log('Similarity matrix:\n');

  // Header
  console.log(''.padEnd(20) + models.map(m => m.slice(0, 15).padEnd(17)).join(''));
  console.log(''.padEnd(20) + models.map(_ => '-'.repeat(17)).join(''));

  // Rows
  for (const model1 of models) {
    const row = model1.slice(0, 18).padEnd(20);
    const scores = models.map(model2 => {
      const similarity = transfer.calculateSimilarity(model1, model2);
      return (similarity * 100).toFixed(0).padStart(3) + '%';
    });
    console.log(row + scores.map(s => s.padEnd(17)).join(''));
  }
}

// ---------------------------------------------------------------------------
// Example 8: Confidence decay timeline
// ---------------------------------------------------------------------------

async function example8_confidenceDecay() {
  console.log('\n=== Example 8: Confidence Decay Timeline ===\n');

  const initialConfidence = transfer.TRANSFER_INITIAL_CONFIDENCE;
  const decayRate = transfer.TRANSFER_DECAY_RATE;
  const minConfidence = transfer.MIN_TRANSFER_CONFIDENCE;

  console.log(`Initial confidence: ${(initialConfidence * 100).toFixed(1)}%`);
  console.log(`Decay rate: ${(decayRate * 100).toFixed(1)}% per day`);
  console.log(`Minimum confidence: ${(minConfidence * 100).toFixed(1)}%\n`);

  console.log('Day  Confidence  Percentage  Status');
  console.log('---  ----------  ----------  ------');

  for (let day = 0; day <= 20; day++) {
    const confidence = initialConfidence * Math.exp(-decayRate * day);
    const percentage = (confidence / initialConfidence * 100).toFixed(1);
    const status = confidence >= minConfidence ? 'Active' : 'EXPIRED';

    console.log(
      day.toString().padStart(3) + '  ' +
      confidence.toFixed(3) + '     ' +
      percentage.padStart(5) + '%    ' +
      status
    );

    if (day > 0 && confidence < minConfidence && day <= 16) {
      // Only show first expiration
      console.log('     ^^^^^ Transfer expires here ^^^^^');
      break;
    }
  }
}

// ---------------------------------------------------------------------------
// Main: Run all examples
// ---------------------------------------------------------------------------

async function runAllExamples() {
  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║         Transfer Learning Usage Examples                  ║');
  console.log('╚════════════════════════════════════════════════════════════╝');

  try {
    // Examples that don't require database
    await example6_parseModelIdentifiers();
    await example7_similarityMatrix();
    await example8_confidenceDecay();

    // Examples that require database (may fail if not initialized)
    console.log('\n' + '='.repeat(60));
    console.log('Database-dependent examples (may fail if DB not initialized)');
    console.log('='.repeat(60));

    try {
      await example1_bootstrapNewClaude();
      await example2_getCalibrationForTask();
      await example5_findSimilarModels();
      // await example3_accumulateNativeData();  // Commented out - modifies DB
      // await example4_validateTransfer();       // Commented out - requires native data

    } catch (error) {
      if (error.code === 'SQLITE_ERROR' && error.message.includes('no such table')) {
        console.log('\n⚠ Database not initialized. Run: node init-transfer-learning-db.js\n');
      } else {
        throw error;
      }
    }

    console.log('\n╔════════════════════════════════════════════════════════════╗');
    console.log('║                 All examples completed!                   ║');
    console.log('╚════════════════════════════════════════════════════════════╝\n');

  } catch (error) {
    console.error('\n✗ Example failed:');
    console.error(error);
    process.exit(1);
  }
}

// CLI: Run specific example or all
if (require.main === module) {
  const exampleNum = process.argv[2];

  if (exampleNum) {
    const examples = {
      '1': example1_bootstrapNewClaude,
      '2': example2_getCalibrationForTask,
      '3': example3_accumulateNativeData,
      '4': example4_validateTransfer,
      '5': example5_findSimilarModels,
      '6': example6_parseModelIdentifiers,
      '7': example7_similarityMatrix,
      '8': example8_confidenceDecay
    };

    if (examples[exampleNum]) {
      examples[exampleNum]().catch(error => {
        console.error(error);
        process.exit(1);
      });
    } else {
      console.log('Usage: node example-transfer-learning.js [1-8]');
      console.log('  1: Bootstrap new Claude model');
      console.log('  2: Get calibration for task');
      console.log('  3: Accumulate native data');
      console.log('  4: Validate transfer quality');
      console.log('  5: Find similar models');
      console.log('  6: Parse model identifiers');
      console.log('  7: Similarity matrix');
      console.log('  8: Confidence decay timeline');
      console.log('  (no arg): Run all examples');
    }
  } else {
    runAllExamples();
  }
}

module.exports = {
  example1_bootstrapNewClaude,
  example2_getCalibrationForTask,
  example3_accumulateNativeData,
  example4_validateTransfer,
  example5_findSimilarModels,
  example6_parseModelIdentifiers,
  example7_similarityMatrix,
  example8_confidenceDecay,
  runAllExamples
};
