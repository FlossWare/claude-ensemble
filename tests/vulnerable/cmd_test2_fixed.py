# Command Injection Fixed 2: Use subprocess without shell=True
import subprocess
import re

def ping_host(hostname):
    # Validate hostname (only alphanumeric, dots, hyphens)
    if not re.match(r'^[a-zA-Z0-9.-]+$', hostname):
        raise ValueError("Invalid hostname")

    # Safe: Use list arguments, no shell=True
    subprocess.run(['ping', '-c', '1', hostname], check=True)
