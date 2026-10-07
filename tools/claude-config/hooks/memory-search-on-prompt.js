#!/usr/bin/env node
/**
 * FlossWare Claude Ensemble Memory Hook
 * UserPromptSubmit -> Memory REST -> additionalContext.
 * Fail-open: Memory outages never block the prompt.
 */
const http=require("node:http");
const https=require("node:https");
const baseUrl=process.env.FLOSSWARE_MEMORY_URL||"http://127.0.0.1:8767";
const limit=Number.parseInt(process.env.FLOSSWARE_MEMORY_LIMIT||"8",10);
const timeoutMs=Number.parseInt(process.env.FLOSSWARE_MEMORY_TIMEOUT_MS||"1200",10);
const maxContext=Number.parseInt(process.env.FLOSSWARE_MEMORY_CONTEXT_CHARS||"7000",10);

function requestJson(url,payload){
  return new Promise((resolve,reject)=>{
    const parsed=new URL(url), transport=parsed.protocol==="https:"?https:http, body=JSON.stringify(payload);
    const req=transport.request(parsed,{method:"POST",timeout:timeoutMs,headers:{"content-type":"application/json","content-length":Buffer.byteLength(body)}},res=>{
      let text=""; res.setEncoding("utf8"); res.on("data",c=>text+=c); res.on("end",()=>{
        if(res.statusCode<200||res.statusCode>=300)return reject(new Error("HTTP "+res.statusCode));
        try{resolve(JSON.parse(text));}catch(e){reject(e);}
      });
    });
    req.on("timeout",()=>req.destroy(new Error("timeout"))); req.on("error",reject); req.write(body); req.end();
  });
}

function formatResults(query,results){
  if(!Array.isArray(results)||!results.length)return "";
  const sections=results.map((item,i)=>{
    const file=item.file||item.name||("memory-"+(i+1));
    const score=typeof item.score==="number"?" (relevance "+item.score.toFixed(2)+")":"";
    const content=String(item.content||item.section||"").trim();
    return "### "+file+score+"\n"+content;
  }).filter(Boolean);
  let context=sections.join("\n\n");
  if(context.length>maxContext)context=context.slice(0,maxContext)+"\n[Memory context truncated]";
  return "Relevant FlossWare Memory for this prompt:\nQuery: "+query+"\n\n"+context;
}

let input="";
process.stdin.setEncoding("utf8");
process.stdin.on("data",chunk=>input+=chunk);
process.stdin.on("end",async()=>{
  try{
    const event=JSON.parse(input), prompt=String(event.prompt||"").trim();
    if(!prompt)return;
    const payload=await requestJson(baseUrl.replace(/\/$/,"")+"/memory/search",{query:prompt,limit});
    const context=formatResults(prompt,payload.results);
    if(context)process.stdout.write(JSON.stringify({hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:context}}));
  }catch(_){}
});
