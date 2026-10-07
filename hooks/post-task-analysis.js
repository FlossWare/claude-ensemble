// Post-Task Analysis Hook
//
// Fires after Claude Code completes a task.
// Triggers learning analysis + alerts.
//
// Hook runs when: UserPromptSubmit completes with results
// Action: Call post_task_analyzer.py to evaluate outcome + update Thompson

module.exports = {
  name: "post-task-analysis",
  description: "Analyze task outcomes and trigger learning/alerts",
  event: "UserPromptSubmit",  // Fires after user submits prompt with results

  async execute(context) {
    const { task, result, error } = context;

    // Only process successful completions
    if (error) {
      console.log(`[post-task-analysis] Task failed: ${error}`);
      return;
    }

    // Extract task metadata
    const taskId = task.id || `task_${Date.now()}`;
    const taskType = task.type || "unknown";
    const modelUsed = result.model || "unknown";
    const tokens = {
      input: result.usage?.prompt_tokens || 0,
      output: result.usage?.completion_tokens || 0
    };
    const cost = result.cost_usd || 0;
    const userRating = task.user_rating || result.user_rating || null;  // Capture user rating

    console.log(`[post-task-analysis] Analyzing task: ${taskId}`);
    console.log(`  Type: ${taskType}, Model: ${modelUsed}, Tokens: ${tokens.input + tokens.output}, Cost: $${cost}`);

    try {
      // Spawn Python analyzer subprocess
      const { execFile } = require('child_process');
      const analyzer = require('path').join(__dirname, '..', 'learning', 'post_task_analyzer.py');

      // Call analyzer with task data as JSON on stdin
      const analysisPromise = new Promise((resolve, reject) => {
        const proc = execFile('python3', [analyzer], (error, stdout, stderr) => {
          if (error) {
            console.log(`[post-task-analysis] Analyzer error: ${error}`);
            reject(error);
          } else {
            console.log(`[post-task-analysis] Analysis complete`);
            resolve(stdout);
          }
        });

        // Send task data to analyzer
        proc.stdin.write(JSON.stringify({
          task_id: taskId,
          task_type: taskType,
          model_used: modelUsed,
          input_tokens: tokens.input,
          output_tokens: tokens.output,
          cost: cost,
          user_rating: userRating
        }));
        proc.stdin.end();
      });

      await analysisPromise;

      // Trigger alerts check
      console.log(`[post-task-analysis] Checking for alerts`);
      const { execFile: exec2 } = require('child_process');
      const alerts = require('path').join(__dirname, '..', 'tools', 'alert_manager.py');

      execFile('python3', [alerts], (error, stdout) => {
        if (error) {
          console.log(`[post-task-analysis] Alert check failed: ${error}`);
        } else {
          console.log(`[post-task-analysis] Alerts checked`);
        }
      });

      return { success: true, message: "Task analysis triggered" };

    } catch (err) {
      console.error(`[post-task-analysis] Unexpected error: ${err}`);
      return { success: false, error: err.message };
    }
  },

  // Hook configuration
  config: {
    enabled: true,
    priority: 100,  // High priority - runs after other hooks
    timeout: 30000,  // 30 second timeout
    runInBackground: true  // Don't block user
  }
};
