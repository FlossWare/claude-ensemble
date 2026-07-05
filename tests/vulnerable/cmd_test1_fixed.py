# Command Injection Fixed 1: Use subprocess with list arguments
import subprocess
import shutil
from pathlib import Path

def backup_user_file(filename):
    # Validate filename (no path traversal)
    if '..' in filename or filename.startswith('/'):
        raise ValueError("Invalid filename")

    # Safe: Use shutil.copy or subprocess with list args
    src = Path(filename)
    dst = Path('/backup') / src.name
    shutil.copy(src, dst)

    # Alternative: subprocess with list (no shell=True)
    # subprocess.run(['cp', filename, '/backup/'], check=True)
