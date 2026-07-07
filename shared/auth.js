// Shared bearer token authentication helper.
// Extracts the duplicated LEARNING_API_TOKEN pattern used across consensus workflows.

/**
 * Build an Authorization header object from the LEARNING_API_TOKEN env var.
 * Returns an empty object when no token is set, so it can be spread safely:
 *
 *   headers: { 'Content-Type': 'application/json', ...getLearningAuthHeader() }
 *
 * @returns {{ Authorization?: string }}
 */
function getLearningAuthHeader() {
  const token = process.env.LEARNING_API_TOKEN
  return token ? { 'Authorization': `Bearer ${token}` } : {}
}

module.exports = { getLearningAuthHeader }
