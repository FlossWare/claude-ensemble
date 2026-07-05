#!/usr/bin/env node

/**
 * Test Developer Preference Learner
 *
 * Demonstrates:
 * 1. Getting model recommendations for different tasks
 * 2. Selecting models based on learned preferences
 * 3. Recording outcomes for continual learning
 */

import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Load the adapter (using dynamic import for ESM)
const { getModelRecommendation, getLearnerStats, selectModelForTask, recordTaskOutcome } =
    await import(join(__dirname, '..', 'shared', 'developer-preference-adapter.cjs'));

async function main() {
    console.log('=== Developer Preference Learner Test ===\n');

    // Get learner statistics
    try {
        const stats = await getLearnerStats();
        console.log('Learner Statistics:');
        console.log(`  Trained at: ${stats.trainedAt}`);
        console.log(`  Training records: ${stats.trainingRecords}`);
        console.log(`  Avg training reward: ${stats.avgTrainReward.toFixed(3)}`);
        console.log(`  Test accuracy: ${(stats.testAccuracy * 100).toFixed(1)}%`);
        console.log(`  Models learned: ${stats.models.length}`);
        console.log('');
    } catch (error) {
        console.error('Error getting stats:', error.message);
        console.log('Run: python3 tools/developer_preference_learner.py to train first\n');
        return;
    }

    // Test cases: different types of tasks
    const testCases = [
        {
            task: 'Implement a Java Spring Boot REST API for user authentication with JWT tokens',
            workflow: 'code-implementation',
            expectedDomain: 'Java'
        },
        {
            task: 'Review this Python Django code for SQL injection vulnerabilities and XSS attacks',
            workflow: 'code-review',
            expectedDomain: 'Python, Security'
        },
        {
            task: 'Fix the race condition in the PostgreSQL connection pool that causes deadlocks under high load',
            workflow: 'bug-fix',
            expectedDomain: 'Database, Concurrency'
        },
        {
            task: 'Research and compare GraphQL vs REST API design patterns for microservices architecture',
            workflow: 'research',
            expectedDomain: 'API, Architecture'
        },
        {
            task: 'Write comprehensive unit tests for the JavaScript payment processing service using Jest',
            workflow: 'testing',
            expectedDomain: 'JavaScript, Testing'
        },
        {
            task: 'Deploy the Node.js microservice to Kubernetes with health checks and autoscaling',
            workflow: 'deployment',
            expectedDomain: 'DevOps, Kubernetes'
        }
    ];

    console.log('Testing Model Recommendations:\n');
    console.log('='.repeat(80) + '\n');

    for (const testCase of testCases) {
        console.log(`Task: ${testCase.task}`);
        console.log(`Workflow: ${testCase.workflow}`);
        console.log(`Expected Domain: ${testCase.expectedDomain}`);

        try {
            const recommendation = await getModelRecommendation(testCase.task, testCase.workflow);

            console.log(`\nRecommendation:`);
            console.log(`  Best Model: ${recommendation.recommended_model}`);
            console.log(`  UCB Score: ${recommendation.ucbScore.toFixed(3)}`);
            console.log(`  Confidence Interval: ±${recommendation.confidence_interval.toFixed(3)}`);

            console.log(`\n  Top 3 Alternatives:`);
            for (let i = 0; i < Math.min(3, recommendation.alternatives.length); i++) {
                const alt = recommendation.alternatives[i];
                console.log(`    ${i + 1}. ${alt.model}`);
                console.log(`       UCB: ${alt.ucb_score.toFixed(3)}, CI: ±${alt.confidence_interval.toFixed(3)}`);
            }

            // Show which context features were detected
            const activeFeatures = [];
            for (let i = 0; i < recommendation.context.length; i++) {
                if (recommendation.context[i] > 0) {
                    activeFeatures.push(`${recommendation.context_features[i]}=${recommendation.context[i].toFixed(2)}`);
                }
            }
            console.log(`\n  Detected Context: ${activeFeatures.join(', ')}`);

        } catch (error) {
            console.error(`  Error: ${error.message}`);
        }

        console.log('\n' + '-'.repeat(80) + '\n');
    }

    // Test selecting model with availability filter
    console.log('Testing Model Selection with Availability Filter:\n');

    const availableModels = ['opus', 'sonnet', 'haiku', 'gemini-2.5-flash'];
    const task = 'Implement a complex algorithm for distributed consensus using Raft protocol';

    console.log(`Task: ${task}`);
    console.log(`Available Models: ${availableModels.join(', ')}\n`);

    try {
        const selectedModel = await selectModelForTask({
            task,
            workflow: 'algorithm-implementation',
            availableModels
        });

        console.log(`Selected Model: ${selectedModel}`);
        console.log(`(Automatically selected from available models based on learned preferences)`);
    } catch (error) {
        console.error(`Error: ${error.message}`);
    }

    console.log('\n' + '='.repeat(80) + '\n');

    // Simulate recording outcomes for continual learning
    console.log('Simulating Continual Learning:\n');

    const outcomes = [
        {
            task: 'Fix null pointer exception in Java service',
            workflow: 'bug-fix',
            model: 'opus',
            success: true,
            confidence: 0.95,
            durationMs: 3000,
            costUsd: 0.008
        },
        {
            task: 'Write Python unit tests for authentication',
            workflow: 'testing',
            model: 'sonnet',
            success: true,
            confidence: 0.88,
            durationMs: 4500,
            costUsd: 0.005
        }
    ];

    for (const outcome of outcomes) {
        console.log(`Recording outcome for: ${outcome.task}`);
        console.log(`  Model: ${outcome.model}`);
        console.log(`  Success: ${outcome.success}, Confidence: ${outcome.confidence}`);

        try {
            await recordTaskOutcome(outcome);
            console.log(`  ✓ Feedback recorded\n`);
        } catch (error) {
            console.error(`  Error: ${error.message}\n`);
        }
    }

    console.log('='.repeat(80));
    console.log('\n✅ Developer Preference Learner Test Complete!\n');
    console.log('The learner continuously improves as it receives feedback from task outcomes.');
    console.log('Integration with orchestrator: Use selectModelForTask() to get intelligent model selection.\n');
}

main().catch(console.error);
