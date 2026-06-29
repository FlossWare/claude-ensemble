#!/usr/bin/env node
export const meta = {
  name: 'setup-gcloud-fleet',
  description: 'Setup gcloud CLI on all 8 workers for Anthropic Vertex AI access',
  phases: [
    { title: 'Install gcloud', detail: 'Install gcloud CLI on all workers in parallel' },
    { title: 'Configure Auth', detail: 'Setup authentication and project config' },
    { title: 'Verify', detail: 'Test Anthropic API access on all workers' }
  ]
};

phase('Install gcloud');

log('Installing gcloud CLI on all 8 workers in parallel...');

const WORKERS = ['server-01', 'server-02', 'server-03', 'laptop-01', 'pi-01', 'pi-02', 'desktop-ap', 'server-ap'];

const installations = await parallel(WORKERS.map(worker =>
  () => agent(`Install gcloud CLI on ${worker}:

1. SSH to ${worker}
2. Check if gcloud already installed: which gcloud
3. If not installed, install via package manager:

   For Fedora/RHEL:
   sudo dnf install -y google-cloud-cli

   For Debian/Ubuntu:
   curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
   echo "deb https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list
   sudo apt-get update && sudo apt-get install -y google-cloud-cli

4. Verify: gcloud --version

Return JSON:
{
  "worker": "${worker}",
  "already_installed": true/false,
  "installed": true/false,
  "version": "...",
  "error": null
}`,
  { label: `Install gcloud on ${worker}`, model: 'haiku', effort: 'medium' })
));

const installSuccess = installations.filter(Boolean);
log('gcloud installed on: ' + installSuccess.length + '/8 workers');

phase('Configure Auth');

log('Configuring gcloud authentication and project settings...');

const authAgent = await agent(`Configure gcloud auth on all workers:

IMPORTANT: gcloud auth requires interactive login. We need to:
1. Copy gcloud credentials from aio-01 to all workers
2. Set project configuration

Steps:

1. On aio-01, get the credentials:
   ls ~/.config/gcloud/

2. For each worker, copy gcloud config:
   for worker in server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap; do
     ssh claude@$worker "mkdir -p ~/.config/gcloud"
     rsync -avz ~/.config/gcloud/ claude@$worker:~/.config/gcloud/
   done

3. Set project on each worker:
   for worker in server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap; do
     ssh claude@$worker "gcloud config set project xe-uxe-cloud-gcp-model-dev"
     ssh claude@$worker "gcloud config set compute/region global"
   done

4. Verify authentication:
   for worker in server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap; do
     echo "=== $worker ==="
     ssh claude@$worker "gcloud auth list"
   done

Return JSON:
{
  "credentials_copied": true/false,
  "project_configured": true/false,
  "workers_authenticated": [],
  "workers_failed": []
}`,
{ label: 'Configure gcloud auth', model: 'opus', effort: 'high' });

log('gcloud authentication configured');

phase('Verify');

log('Testing Anthropic API access on all workers...');

const verifications = await parallel(WORKERS.map(worker =>
  () => agent(`Test Anthropic API access on ${worker}:

1. SSH to ${worker}
2. Source environment:
   source ~/.bashrc

3. Test API call:
   cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
   node -e "import { executeRemoteLLMTask } from './shared/fleet-utils.js'; const r = await executeRemoteLLMTask({ task: 'Say hello', model: 'haiku', maxTokens: 20 }); console.log('SUCCESS:', r.output);"

4. If it works, return success. If it fails, return the error.

Return JSON:
{
  "worker": "${worker}",
  "api_call_success": true/false,
  "output": "...",
  "error": null
}`,
  { label: `Verify ${worker}`, model: 'haiku', effort: 'medium' })
));

const verifySuccess = verifications.filter(Boolean).filter(v => v.api_call_success);
log('Anthropic working on: ' + verifySuccess.length + '/8 workers');

return {
  installations: installSuccess.length,
  authentication: authAgent,
  verifications: verifySuccess.length,
  all_working: verifySuccess.length === 8,
  workers: WORKERS,
  success: verifySuccess.length >= 6 // 75% success threshold
};
