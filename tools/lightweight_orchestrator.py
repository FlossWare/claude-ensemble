#!/usr/bin/env python3
"""
LIGHTWEIGHT SCRAPER ORCHESTRATOR
Deploys API-based scrapers to small machines (1GB RAM)
Heavy git clones stay on big machines
"""

import subprocess
import time

# Small machines (1GB RAM) - use API-based scrapers only
SMALL_MACHINES = {
    'pi-01': [
        'tools/wikipedia_scraper.py',      # API-based, 10-15s delays
        'tools/hackernews_scraper.py',     # Small JSON API
        'tools/reddit_scraper.py',         # Small JSON API
    ],
    'pi-02': [
        'tools/stackexchange_scraper.py',  # API-based
        'tools/semantic_scholar_scraper.py', # API-based
        'tools/pubmed_scraper.py',         # API-based
    ],
    'desktop-ap': [
        'tools/arxiv_scraper.py',          # API-based
        'tools/official_docs_scraper.py',  # HTML scraping (light)
    ],
    'server-ap': [
        'tools/electronics_ee_scraper.py',           # API + arXiv
        'tools/chip_design_hardware_scraper.py',     # API + arXiv
        'tools/consciousness_neuroscience_scraper.py', # API + arXiv
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
        if pid and pid.isdigit():
            print(f"  ✅ {machine}: {scraper_script.split('/')[-1]} (PID: {pid})")
            return True
        else:
            print(f"  ⚠️  {machine}: {scraper_script.split('/')[-1]} - may already be running or failed")
            return False
    except Exception as e:
        print(f"  ❌ {machine}: {scraper_script.split('/')[-1]} - {e}")
        return False

def main():
    print("="*70)
    print("LIGHTWEIGHT SCRAPER ORCHESTRATOR")
    print("Deploying API-based scrapers to small machines (1GB RAM)")
    print("="*70)
    print("")

    total_launched = 0

    for machine, scripts in SMALL_MACHINES.items():
        print(f"\n🖥️  {machine}:")
        for script in scripts:
            if launch_scraper_on_machine(machine, script):
                total_launched += 1
            time.sleep(1)

    print(f"\n{'='*70}")
    print(f"✅ LAUNCHED {total_launched} lightweight scrapers!")
    print(f"{'='*70}")
    print("")
    print("These are API-based scrapers (safe for 1GB RAM machines)")
    print("No heavy git clones on small machines!")
    print("")
    print("Monitor with: ps aux | grep python3 | grep scraper")
    print("")

if __name__ == '__main__':
    main()
