# Command Injection 3: os.popen with user input
import os
def list_files(directory):
    result = os.popen(f"ls -la {directory}").read()
    return result
