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
def entry(command): return {"hooks":[{"type":"command","command":shlex.quote(command),"timeout":3}]}
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

def install_hook(path,command):
    data=validate_input(path); hooks=data.setdefault("hooks",{})
    if not isinstance(hooks,dict): raise ValueError("settings hooks must be an object")
    event=hooks.setdefault("UserPromptSubmit",[])
    if not isinstance(event,list): raise ValueError("UserPromptSubmit must be an array")
    for group in event:
        if isinstance(group,dict):
            for h in group.get("hooks",[]):
                if isinstance(h,dict) and h.get("type")=="command" and h.get("command") in (command,shlex.quote(command)):
                    h["command"]=shlex.quote(command); save(path,data); return
    event.append(entry(command)); save(path,data)

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
    if op=="install-hook": install_hook(sys.argv[2],sys.argv[3])
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
if __name__=="__main__": main()
