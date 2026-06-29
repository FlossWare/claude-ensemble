# API Credential Distribution Matrix

## Current Distribution (2026-06-28)

| Worker | ANTHROPIC | OPENAI | GOOGLE | GROQ | Other |
|--------|-----------|---------|--------|------|-------|
| server-01 | ✅ | ✅ | ✅ | - | - |
| server-02 | ✅ | ✅ | ✅ | - | - |
| server-03 | ✅ | - | - | - | - |
| laptop-01 | ✅ | ✅ | ✅ | ✅ | All |
| pi-01 | ✅ | - | - | - | - |
| pi-02 | ✅ | - | - | - | - |
| desktop-ap | ✅ | ✅ | - | - | - |
| server-ap | ✅ | - | - | - | - |

## Adding New Credentials

1. SSH to worker: `ssh claude@<worker>`
2. Add to `~/.bashrc` or `~/.zshrc`:
   ```bash
   export OPENAI_API_KEY="sk-..."
   export GOOGLE_API_KEY="..."
   ```
3. Reload: `source ~/.bashrc`
4. Verify: `echo $OPENAI_API_KEY | head -c 8`

## Security Best Practices

- Store in environment variables, NOT files
- Use `.bashrc` or `.zshrc`, NOT `.env` files
- Never commit credentials to git
- Rotate keys every 90 days
- Use read-only keys when possible

## Validation

Run: `node -e "const {getCredentialManager} = require('./shared/credential-manager.cjs'); console.log(getCredentialManager().validateCredentials());"`
