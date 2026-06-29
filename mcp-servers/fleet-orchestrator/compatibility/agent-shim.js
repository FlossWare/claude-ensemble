export async function agentCompat(prompt, options = {}) {
  if (typeof agent !== 'undefined') {
    return await agent(prompt, options);
  }
  throw new Error('Agent not available');
}
