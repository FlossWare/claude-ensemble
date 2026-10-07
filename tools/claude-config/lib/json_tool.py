#!/usr/bin/env python3
from pathlib import Path
import json,os,sys

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

def entry(command): return {"hooks":[{"type":"command","command":command,"timeout":3}]}

def install_hook(path,command):
    data=load(path); hooks=data.setdefault("hooks",{})
    if not isinstance(hooks,dict): raise ValueError("settings hooks must be an object")
    event=hooks.setdefault("UserPromptSubmit",[])
    if not isinstance(event,list): raise ValueError("UserPromptSubmit must be an array")
    for group in event:
        if isinstance(group,dict):
            for h in group.get("hooks",[]):
                if isinstance(h,dict) and h.get("type")=="command" and h.get("command")==command:
                    save(path,data); return
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
        handlers=[h for h in group.get("hooks",[]) if not (isinstance(h,dict) and h.get("type")=="command" and h.get("command")==command)]
        if handlers:
            group=dict(group); group["hooks"]=handlers; cleaned.append(group)
    hooks["UserPromptSubmit"]=cleaned; save(path,data)

def main():
    op=sys.argv[1]
    if op=="install-hook": install_hook(sys.argv[2],sys.argv[3])
    elif op=="remove-hook": remove_hook(sys.argv[2],sys.argv[3])
    elif op=="create-settings": save(sys.argv[2],{"hooks":{"UserPromptSubmit":[entry(sys.argv[3])]}})
    elif op=="manifest": save(sys.argv[2],{"product":"flossware-claude-config","version":sys.argv[3],"files":{sys.argv[4]:{"managed":True,"sha256":sys.argv[5]}}})
    elif op=="plan":
        print("Claude Configuration Plan")
        print("CREATE/KEEP "+sys.argv[3])
        print("MODIFY "+sys.argv[2]+" with UserPromptSubmit Memory hook")
        print("BACKUP existing settings before mutation")
        print("VERIFY settings JSON, hook syntax, and Memory REST health")
    else: raise SystemExit("unknown operation: "+op)
if __name__=="__main__": main()
