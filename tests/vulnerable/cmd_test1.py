# Command Injection 1: os.system with user input
import os
def backup_user_file(filename):
    os.system(f"cp {filename} /backup/")
