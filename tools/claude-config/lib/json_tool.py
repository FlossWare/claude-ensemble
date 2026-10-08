#!/usr/bin/env python3
from pathlib import Path
import json,os,sys,shlex,re

def load(path):
    p=Path(path)
    if not p.exists(): return {}
    with p.open(encoding="utf-8") as f: value=json.load(f)
    if not isinstance(value,dict): raise ValueError(path+" must contain a JSON object")
    return value

def save(path,value):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+".tmp")
    with tmp.open("w",encoding="utf-8") as f: json.dump(value,f,indent=2,sort_keys=True); f.write("\n")
    os.replace(tmp,p)

PRODUCT="flossware-claude-config"
SHA256_RE=re.compile(r"^[0-9a-f]{64}$")
LEGACY_HOOK_SHAS={
    "hooks/user-prompt-submit.sh": {
        "d424ad860680d9f3b07455eb23c5a3304bbab78280088dc2902f3f866417a458",
    },
    "hooks/ingest-prompt": {
        "bd8443ec9be3542c24c3a93d637c3a2b0770ff8494d7e0850f8d7c015839",
    },
}

def entry(command): return {"hooks":[{"type":"command","command":shlex.quote(command),"timeout":3}]}

def command_path(command):
    if not isinstance(command,str): return None
    try:
        parts=shlex.split(command)
    except ValueError:
        return None
    if len(parts) != 1: return None
    return Path(parts[0]).expanduser()

def is_memory_hook_command(command, managed_command, source_sha):
    path=command_path(command)
    managed_path=command_path(managed_command)
    if path is None or managed_path is None or path.name != "memory-search-on-prompt.js":
        return False
    if path == managed_path:
        return True
    try:
        return path.is_file() and sha256_file(path) == source_sha
    except OSError:
        return False

def is_owned_legacy_hook(command):
    path=command_path(command)
    if path is None or not path.is_file(): return False
    for name, expected_sha in LEGACY_HOOK_SHAS.items():
        if path.name == Path(name).name:
            try:
                return sha256_file(path) in expected_sha
            except OSError:
                return False
    return False


def migrate_legacy_hooks(path):
    data=validate_input(path); hooks=data.get("hooks",{})
    event=hooks.get("UserPromptSubmit",[])
    removed=[]
    cleaned=[]
    for group in event:
        if not isinstance(group,dict): cleaned.append(group); continue
        handlers=[]
        for h in group.get("hooks",[]):
            if isinstance(h,dict) and h.get("type")=="command" and is_owned_legacy_hook(h.get("command")):
                removed.append(command_path(h.get("command")))
                continue
            handlers.append(h)
        if handlers:
            updated=dict(group); updated["hooks"]=handlers; cleaned.append(updated)
    hooks["UserPromptSubmit"]=cleaned
    save(path,data)
    for legacy_path in removed: print(str(legacy_path))

def sha256_file(path):
    import hashlib
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def validate_input(path):
    data=load(path); hooks=data.get("hooks",{})
    if not isinstance(hooks,dict): raise ValueError("settings hooks must be an object")
    event=hooks.get("UserPromptSubmit",[])
    if not isinstance(event,list): raise ValueError("UserPromptSubmit must be an array")
    for group in event:
        if isinstance(group,dict) and not isinstance(group.get("hooks",[]),list): raise ValueError("hook group hooks must be an array")
    return data

def manifest_data(path,hook):
    data=load(path)
    if data.get("product") != PRODUCT: raise ValueError("manifest product mismatch")
    files=data.get("files")
    if not isinstance(files,dict): raise ValueError("manifest files missing")
    item=files.get(hook)
    if not isinstance(item,dict) or item.get("managed") is not True: raise ValueError("managed hook entry missing")
    sha=item.get("sha256")
    if not isinstance(sha,str) or not SHA256_RE.fullmatch(sha): raise ValueError("managed hook checksum missing or invalid")
    return item

def validate_manifest(path,hook): manifest_data(path,hook); print("✓ manifest ownership is valid")
def manifest_sha(path,hook): print(manifest_data(path,hook)["sha256"])

def install_hook(path,command,source):
    data=validate_input(path); hooks=data.setdefault("hooks",{})
    if not isinstance(hooks,dict): raise ValueError("settings hooks must be an object")
    event=hooks.setdefault("UserPromptSubmit",[])
    if not isinstance(event,list): raise ValueError("UserPromptSubmit must be an array")
    source_path=Path(source)
    source_sha=sha256_file(source_path)

    managed=False
    cleaned=[]
    for group in event:
        if not isinstance(group,dict):
            cleaned.append(group)
            continue
        handlers=[]
        group_managed=False
        for h in group.get("hooks",[]):
            if isinstance(h,dict) and h.get("type")=="command" and is_memory_hook_command(h.get("command"), command, source_sha):
                if not managed:
                    replacement=dict(h)
                    replacement["command"]=shlex.quote(command)
                    handlers.append(replacement)
                    managed=True
                    group_managed=True
                continue
            handlers.append(h)
        if handlers:
            updated=dict(group)
            updated["hooks"]=handlers
            cleaned.append(updated)
        elif group_managed:
            cleaned.append({"hooks":[replacement]})

    if not managed:
        cleaned.append(entry(command))
    hooks["UserPromptSubmit"]=cleaned
    save(path,data)

def remove_hook(path,command):
    if not Path(path).exists(): return
    data=load(path); hooks=data.get("hooks",{})
    if not isinstance(hooks,dict): return
    event=hooks.get("UserPromptSubmit",[])
    if not isinstance(event,list): return
    cleaned=[]
    for group in event:
        if not isinstance(group,dict): cleaned.append(group); continue
        handlers=[h for h in group.get("hooks",[]) if not (isinstance(h,dict) and h.get("type")=="command" and h.get("command") in (command,shlex.quote(command)))]
        if handlers:
            group=dict(group); group["hooks"]=handlers; cleaned.append(group)
    hooks["UserPromptSubmit"]=cleaned; save(path,data)

def main():
    op=sys.argv[1]
    if op=="install-hook": install_hook(sys.argv[2],sys.argv[3],sys.argv[4])
    elif op=="migrate-legacy": migrate_legacy_hooks(sys.argv[2])
    elif op=="remove-hook": remove_hook(sys.argv[2],sys.argv[3])
    elif op=="create-settings": save(sys.argv[2],{"hooks":{"UserPromptSubmit":[entry(sys.argv[3])]}})
    elif op=="manifest": save(sys.argv[2],{"product":PRODUCT,"version":sys.argv[3],"files":{sys.argv[4]:{"managed":True,"sha256":sys.argv[5]}}})
    elif op=="validate-input": validate_input(sys.argv[2])
    elif op=="validate-settings":
        data=validate_input(sys.argv[2]); command=shlex.quote(sys.argv[3])
        event=data.get("hooks",{}).get("UserPromptSubmit",[])
        if not any(isinstance(g,dict) and any(isinstance(h,dict) and h.get("type")=="command" and h.get("command") in (command,sys.argv[3]) for h in g.get("hooks",[])) for g in event): raise ValueError("managed UserPromptSubmit hook is missing")
        print("✓ settings contain the managed UserPromptSubmit hook")
    elif op=="validate-manifest": validate_manifest(sys.argv[2],sys.argv[3])
    elif op=="manifest-sha": manifest_sha(sys.argv[2],sys.argv[3])
    elif op=="plan":
        print("Claude Configuration Plan")
        print("CREATE/KEEP "+sys.argv[3])
        print("MODIFY "+sys.argv[2]+" with UserPromptSubmit Memory hook")
        print("BACKUP existing settings before mutation")
        print("VERIFY settings JSON, hook syntax, and Memory REST health")
    else: raise SystemExit("unknown operation: "+op)
if __name__=="__main__":
    main()
