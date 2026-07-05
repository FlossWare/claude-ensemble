#!/usr/bin/env python3
"""
PARALLEL ORCHESTRATOR
Runs scrapers with 6 workers per machine for maximum speed
"""

import subprocess
import json
from pathlib import Path
from datetime import datetime
import time

# Distribute heavy repos across machines
MACHINE_ASSIGNMENTS = {
    'server-02': [
        'tools/beast_mode_modern_languages.py',  # Go, Rust, Kotlin, Swift, Scala
        'tools/beast_mode_ml_frameworks.py',      # TensorFlow, PyTorch, etc.
    ],
    'server-03': [
        'tools/beast_mode_blockchain_cloud.py',  # Bitcoin, Ethereum, Docker, K8s
        'tools/os_code_docs_scraper.py',         # FreeBSD, Fedora, Debian
    ],
    'laptop-01': [
        # Already covered by existing scrapers
    ],
}

def launch_scraper_on_machine(machine, scraper_script):
    """Launch a scraper on a specific machine"""
    # Validate inputs (prevent command injection)
    if not machine.replace('-', '').replace('.', '').isalnum():
        raise ValueError(f"Invalid machine name: {machine}")
    if not scraper_script.startswith('tools/') or not scraper_script.endswith('.py'):
        raise ValueError(f"Invalid scraper script: {scraper_script}")

    log_name = scraper_script.replace('tools/', '').replace('.py', '')
    log_file = f'/mnt/nas/web-scrape/logs/{machine}_{log_name}.log'

    # Use list-based subprocess instead of shell=True
    remote_cmd = (
        f"cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && "
        f"nohup python3 {scraper_script} > {log_file} 2>&1 & echo $!"
    )

    try:
        result = subprocess.run(
            ['ssh', f'claude@{machine}', remote_cmd],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        pid = result.stdout.strip()
        print(f"  ✅ Launched on {machine}: {scraper_script} (PID: {pid})")
        return True
    except Exception as e:
        print(f"  ❌ Failed on {machine}: {scraper_script} - {e}")
        return False

def main():
    print("="*70)
    print("6-WORKER PARALLEL ORCHESTRATOR")
    print("="*70)
    print("")

    total_launched = 0

    for machine, scripts in MACHINE_ASSIGNMENTS.items():
        if not scripts:
            continue

        print(f"\n🖥️  {machine}:")
        for script in scripts:
            if launch_scraper_on_machine(machine, script):
                total_launched += 1
            time.sleep(2)

    print(f"\n{'='*70}")
    print(f"✅ LAUNCHED {total_launched} parallel scrapers!")
    print(f"{'='*70}")
    print("")
    print("Each scraper will use up to 6 parallel workers internally")
    print("Monitor with: ps aux | grep python3 | grep scraper")
    print("")

if __name__ == '__main__':
    main()
