# fleet_executor.py - Python Alternative to fleet-ssh-orchestrator.js

## Status: ALTERNATIVE IMPLEMENTATION (Not Active)

This is a Python implementation of the fleet orchestration system.

## Why Not Active?

The JavaScript version (`shared/fleet-ssh-orchestrator.js`) is the active orchestrator and works well:
- Already integrated with consensus-tools
- Tested and deployed
- All integrations use it

## When to Use This?

Use fleet_executor.py if:
- You need pure Python orchestration
- JavaScript isn't available
- You want to fork the orchestrator

## How to Activate

If you want to switch from JS to Python orchestrator:

1. Update workflows to import fleet_executor instead of fleet-ssh-orchestrator
2. Re-integrate consensus-tools with Python version
3. Test thoroughly before production use

## Current Recommendation

**Keep using fleet-ssh-orchestrator.js** - it's battle-tested and fully integrated.

fleet_executor.py is available as a backup/alternative if needed.
