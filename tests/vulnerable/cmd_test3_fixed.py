# Command Injection Fixed 3: Use subprocess with list args instead of os.popen
import subprocess
from pathlib import Path

def list_files(directory):
    # Validate directory path
    dir_path = Path(directory).resolve()
    if not dir_path.exists() or not dir_path.is_dir():
        raise ValueError("Invalid directory")

    # Safe: Use subprocess with list arguments
    result = subprocess.run(
        ['ls', '-la', str(dir_path)],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout
