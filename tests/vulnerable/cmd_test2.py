# Command Injection 2: subprocess with shell=True
import subprocess
def ping_host(hostname):
    subprocess.run(f"ping -c 1 {hostname}", shell=True)
