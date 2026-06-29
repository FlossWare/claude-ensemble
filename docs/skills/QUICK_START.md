# Fleet-Aware Skills - Quick Start Guide

## What Changed?

Your skills now automatically use fleet workers for large jobs. No configuration needed!

## Usage

### Default: Let it decide (recommended)

```bash
# Small job → runs locally (fast, no SSH overhead)
invoke ai-pdf-deep-research --pdfs file1.pdf file2.pdf

# Large job → runs on fleet if available (faster)
invoke ai-pdf-deep-research --pdfs file1.pdf ... file15.pdf
```

### Force local mode (sequential)

```bash
# Always run on this machine
invoke ai-pdf-deep-research --pdfs file1.pdf ... file100.pdf --local
```

### Force fleet mode

```bash
# Fail if fleet is unavailable
invoke ai-pdf-deep-research --pdfs file1.pdf ... file100.pdf --fleet
```

## When is Fleet Used?

Automatic fleet is used when:
1. Fleet workers are available (checked from `~/.claude/fleet.json`)
2. Item count ≥ break-even threshold (see below)
3. No `--local` flag is set

| Skill | Threshold | Item Type |
|-------|-----------|-----------|
| ai-pdf-deep-research | 10 | PDFs |
| ai-web-learn | 20 | URLs |
| code-security | 50 | Files |
| code-review | 30 | Files |
| code-doc | 50 | Files |
| ai-web-code-learn-production | 5 | Repos |

## Troubleshooting

### Fleet not working?

1. Check fleet is available:
   ```bash
   cat ~/.claude/fleet.json
   ssh server-01 echo OK
   ```

2. Check item count is above threshold

3. Force local mode while diagnosing:
   ```bash
   invoke ai-pdf-deep-research --pdfs *.pdf --local
   ```

## Key Points

✅ **Zero configuration needed**  
✅ **Backward compatible** - All existing code works  
✅ **Automatic** - Fleet detection is transparent  
✅ **Controllable** - Use `--fleet` or `--local` flags  

---

For detailed help, see `docs/FLEET_AWARE_SKILLS.md`
