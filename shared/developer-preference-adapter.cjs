/**
 * Developer Preference Learner - JavaScript Adapter
 *
 * Provides JavaScript API to the Python-based developer preference learner.
 * Uses contextual Thompson Sampling to recommend best model for each task.
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

/**
 * Get model recommendation for a task
 *
 * @param {string} taskDescription - Description of the task
 * @param {string} workflowName - Optional workflow name
 * @returns {Promise<{recommendedModel: string, ucbScore: number, alternatives: Array}>}
 */
async function getModelRecommendation(taskDescription, workflowName = null) {
    const modelPath = path.join(os.homedir(), '.claude', 'learning', 'developer_preference_learner.pkl');

    // Check if model is trained
    if (!fs.existsSync(modelPath)) {
        throw new Error('Developer preference learner not trained. Run: python3 tools/developer_preference_learner.py');
    }

    // Create temporary Python script
    const tmpDir = os.tmpdir();
    const scriptPath = path.join(tmpDir, `pref_learner_${Date.now()}.py`);
    const inputPath = path.join(tmpDir, `pref_input_${Date.now()}.json`);

    const pythonCode = `
import sys
import json
sys.path.insert(0, "${path.join(__dirname, '..', 'tools')}")
from developer_preference_learner import get_model_recommendation

with open("${inputPath}") as f:
    input_data = json.load(f)

task = input_data["task"]
workflow = input_data.get("workflow")

result = get_model_recommendation(task, workflow)
print(json.dumps(result))
`;

    const inputData = {
        task: taskDescription,
        workflow: workflowName
    };

    try {
        // Write script and input
        fs.writeFileSync(scriptPath, pythonCode);
        fs.writeFileSync(inputPath, JSON.stringify(inputData));

        // Execute
        const output = execSync(`python3 ${scriptPath}`, {
            encoding: 'utf8',
            maxBuffer: 10 * 1024 * 1024
        });

        return JSON.parse(output.trim());
    } catch (error) {
        console.error('Error getting model recommendation:', error.message);
        throw error;
    } finally {
        // Cleanup
        try {
            if (fs.existsSync(scriptPath)) fs.unlinkSync(scriptPath);
            if (fs.existsSync(inputPath)) fs.unlinkSync(inputPath);
        } catch (e) {
            // Ignore cleanup errors
        }
    }
}

/**
 * Train the developer preference learner
 *
 * @returns {Promise<{testAccuracy: number, avgTrainReward: number, avgTestReward: number}>}
 */
async function trainLearner() {
    const pythonScript = path.join(__dirname, '..', 'tools', 'developer_preference_learner.py');

    try {
        const output = execSync(`python3 ${pythonScript}`, {
            encoding: 'utf8',
            maxBuffer: 10 * 1024 * 1024
        });

        console.log(output);

        // Parse results from output
        const testAccuracyMatch = output.match(/Test accuracy: ([\d.]+)%/);
        const avgTrainRewardMatch = output.match(/Avg training reward: ([\d.]+)/);
        const avgTestRewardMatch = output.match(/Avg test reward: ([\d.]+)/);

        return {
            testAccuracy: testAccuracyMatch ? parseFloat(testAccuracyMatch[1]) / 100 : 0,
            avgTrainReward: avgTrainRewardMatch ? parseFloat(avgTrainRewardMatch[1]) : 0,
            avgTestReward: avgTestRewardMatch ? parseFloat(avgTestRewardMatch[1]) : 0
        };
    } catch (error) {
        console.error('Error training learner:', error.message);
        throw error;
    }
}

/**
 * Get learner statistics
 *
 * @returns {Promise<Object>}
 */
async function getLearnerStats() {
    const mappingPath = path.join(os.homedir(), '.claude', 'learning', 'developer_preference_mapping.json');

    if (!fs.existsSync(mappingPath)) {
        throw new Error('Developer preference learner not trained');
    }

    const mapping = JSON.parse(fs.readFileSync(mappingPath, 'utf8'));

    return {
        models: mapping.models,
        contextFeatures: mapping.context_features,
        trainedAt: mapping.trained_at,
        trainingRecords: mapping.training_records,
        testAccuracy: mapping.test_accuracy,
        avgTrainReward: mapping.avg_train_reward,
        avgTestReward: mapping.avg_test_reward
    };
}

/**
 * Update the learner with new feedback
 *
 * @param {string} taskDescription - Task description
 * @param {string} model - Model that was used
 * @param {number} reward - Reward (0.0-1.0)
 * @param {string} workflowName - Optional workflow name
 */
async function updateLearner(taskDescription, model, reward, workflowName = null) {
    const tmpDir = os.tmpdir();
    const scriptPath = path.join(tmpDir, `pref_update_${Date.now()}.py`);
    const inputPath = path.join(tmpDir, `pref_update_input_${Date.now()}.json`);

    const pythonCode = `
import sys
import json
sys.path.insert(0, "${path.join(__dirname, '..', 'tools')}")
from developer_preference_learner import DeveloperPreferenceLearner, extract_task_context
from pathlib import Path

with open("${inputPath}") as f:
    input_data = json.load(f)

task = input_data["task"]
model = input_data["model"]
reward = input_data["reward"]
workflow = input_data.get("workflow")

# Load learner
model_path = Path.home() / ".claude" / "learning" / "developer_preference_learner.pkl"
mapping_path = Path.home() / ".claude" / "learning" / "developer_preference_mapping.json"

learner = DeveloperPreferenceLearner.load(model_path)

with open(mapping_path) as f:
    mapping = json.load(f)

# Extract context
context = extract_task_context(task, workflow)

# Update if model is known
if model in mapping["model_to_id"]:
    model_id = mapping["model_to_id"][model]
    learner.update(model_id, context, reward)
    learner.save(model_path)
    print("Updated learner with feedback")
else:
    print(f"Model not in training set: {model}")
`;

    const inputData = {
        task: taskDescription,
        model: model,
        reward: reward,
        workflow: workflowName
    };

    try {
        fs.writeFileSync(scriptPath, pythonCode);
        fs.writeFileSync(inputPath, JSON.stringify(inputData));

        execSync(`python3 ${scriptPath}`, {
            encoding: 'utf8'
        });
    } catch (error) {
        console.error('Error updating learner:', error.message);
        throw error;
    } finally {
        try {
            if (fs.existsSync(scriptPath)) fs.unlinkSync(scriptPath);
            if (fs.existsSync(inputPath)) fs.unlinkSync(inputPath);
        } catch (e) {
            // Ignore cleanup errors
        }
    }
}

/**
 * Orchestrator integration helper
 *
 * Automatically selects best model for a task and updates learner with results.
 *
 * @param {Object} options
 * @param {string} options.task - Task description
 * @param {string} options.workflow - Workflow name
 * @param {Array<string>} options.availableModels - Optional: filter to these models
 * @returns {Promise<string>} - Recommended model
 */
async function selectModelForTask({ task, workflow, availableModels = null }) {
    const recommendation = await getModelRecommendation(task, workflow);

    // If availableModels filter provided, check if recommended model is available
    if (availableModels && !availableModels.includes(recommendation.recommended_model)) {
        // Find best available alternative
        const availableAlternative = recommendation.alternatives.find(
            alt => availableModels.includes(alt.model)
        );

        if (availableAlternative) {
            console.log(`Recommended model ${recommendation.recommended_model} not available, using ${availableAlternative.model}`);
            return availableAlternative.model;
        } else {
            console.warn(`No learned models available, falling back to first available: ${availableModels[0]}`);
            return availableModels[0];
        }
    }

    return recommendation.recommended_model;
}

/**
 * Record task outcome for continual learning
 *
 * @param {Object} options
 * @param {string} options.task - Task description
 * @param {string} options.workflow - Workflow name
 * @param {string} options.model - Model used
 * @param {boolean} options.success - Whether task succeeded
 * @param {number} options.confidence - Confidence score (0.0-1.0)
 * @param {number} options.durationMs - Execution duration in milliseconds
 * @param {number} options.costUsd - Cost in USD
 */
async function recordTaskOutcome({ task, workflow, model, success, confidence = null, durationMs = null, costUsd = null }) {
    let reward = success ? (confidence || 0.7) : 0.0;

    // Bonuses for fast/cheap execution
    if (durationMs && durationMs < 5000) {
        reward = Math.min(1.0, reward * 1.05);
    }

    if (costUsd && costUsd < 0.01) {
        reward = Math.min(1.0, reward * 1.02);
    }

    await updateLearner(task, model, reward, workflow);
}

module.exports = {
    getModelRecommendation,
    trainLearner,
    getLearnerStats,
    updateLearner,
    selectModelForTask,
    recordTaskOutcome
};
