export function selectModel(task) {
  const complexity = task.length > 500 ? 'high' : task.length > 100 ? 'medium' : 'low';
  return complexity === 'high' ? 'opus' : complexity === 'medium' ? 'sonnet' : 'haiku';
}

export function executeOnModel(model, prompt) {
  return { output: prompt.slice(0, 50), model };
}
