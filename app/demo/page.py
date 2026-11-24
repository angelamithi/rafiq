"""The judges' demo page: one self-contained HTML file (no external scripts, fonts or trackers)."""

PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rafiq: judges' demo</title>
<style>
:root{--ink:#14231f;--muted:#5b6b66;--line:#d9e3e0;--bg:#f4f7f6;--brand:#0b5d4b;--brand2:#e6f2ef;--me:#dcf3e9;--warn:#9a3b12}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header{background:var(--brand);color:#fff;padding:14px 20px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
header h1{font-size:18px;margin:0}header .tag{font-size:12.5px;opacity:.85}
nav{margin-left:auto;display:flex;gap:6px}nav button{background:transparent;border:1px solid #ffffff66;color:#fff;border-radius:16px;padding:5px 14px;cursor:pointer}
nav button.on{background:#fff;color:var(--brand)}
.banner{background:#fff6e5;color:#6b4300;border-bottom:1px solid #f0dfbf;padding:8px 20px;font-size:13px}
main{max-width:860px;margin:0 auto;padding:16px}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:20px}
#login{max-width:420px;margin:40px auto}#login input{width:100%;padding:10px;border:1px solid var(--line);border-radius:8px;font-size:15px;margin:10px 0}
.btn{background:var(--brand);color:#fff;border:0;border-radius:8px;padding:10px 16px;font-size:15px;cursor:pointer}
.btn:disabled{opacity:.5}.err{color:var(--warn);font-size:13px;min-height:18px}
#chat{display:none;flex-direction:column;height:calc(100vh - 170px);min-height:420px}
#log{flex:1;overflow:auto;padding:4px 2px 12px}
.row{display:flex;margin:6px 0}.row.me{justify-content:flex-end}
.bubble{max-width:78%;padding:9px 12px;border-radius:12px;background:#fff;border:1px solid var(--line);white-space:pre-wrap;word-wrap:break-word}
.me .bubble{background:var(--me);border-color:#bfe5d4}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.chip{border:1px solid var(--brand);color:var(--brand);background:#fff;border-radius:16px;padding:5px 11px;font-size:13.5px;cursor:pointer}
.chip:hover{background:var(--brand2)}
.menu{margin-top:8px;border-top:1px solid var(--line)}.menu div{padding:7px 4px;border-bottom:1px solid var(--line);cursor:pointer}
.menu div:hover{background:var(--brand2)}.menu b{display:block;font-size:14px}.menu small{color:var(--muted)}
.agent{font-size:11.5px;color:var(--muted);margin:2px 0 10px 4px}.agent span{background:var(--brand2);color:var(--brand);border-radius:10px;padding:1px 8px}
.file{display:inline-block;margin-top:8px;font-weight:600;color:var(--brand)}
form#bar{display:flex;gap:8px;align-items:center;border-top:1px solid var(--line);padding-top:10px}
#text{flex:1;padding:10px;border:1px solid var(--line);border-radius:20px;font-size:15px}
.icon{background:#fff;border:1px solid var(--line);border-radius:50%;width:40px;height:40px;cursor:pointer;font-size:17px}
#starters{margin:0 0 8px}.typing{color:var(--muted);font-size:13px;margin:4px}
#impact{display:none}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin:12px 0}
.stat{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px}.stat b{font-size:24px;display:block}.stat span{color:var(--muted);font-size:13px}
.bar{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:13.5px}.bar i{display:block;height:12px;background:var(--brand);border-radius:6px}
.bar em{width:150px;font-style:normal}.note{color:var(--muted);font-size:13px}
</style></head><body>
<header><h1>Rafiq</h1><div class="tag">AI companion for expats and migrant workers in the UAE · judges' demo</div>
<nav><button id="tChat" class="on">Chat</button><button id="tImpact">Impact</button></nav></header>
<div class="banner">Demo with synthetic data. Please don't type real personal details. This is the same agent that runs on WhatsApp and Telegram: same security checks, same agents, same limits.</div>
<main>
<section id="login" class="card"><h2 style="margin-top:0">Enter the demo code</h2>
<p class="note">You'll find it in our submission. Each code session is private to your browser.</p>
<input id="code" type="password" autocomplete="off" placeholder="Demo code"><div class="err" id="lerr"></div>
<button class="btn" id="go">Start</button></section>
<section id="chat"><div id="starters" class="chips"></div><div id="log"></div>
<form id="bar"><button type="button" class="icon" id="att" title="Send a photo or PDF">📎</button>
<button type="button" class="icon" id="loc" title="Share a sample location">📍</button>
<input id="text" autocomplete="off" placeholder="Type a message… e.g. hi"><button class="btn" id="sendBtn">Send</button>
<input id="file" type="file" accept="image/jpeg,image/png,application/pdf" hidden></form></section>
<section id="impact"><div class="card"><h2 style="margin-top:0">Impact so far</h2>
<p class="note">Totals from the audit log, which never stores message text or personal data. Live users and demo sessions are counted separately.</p>
<div class="grid" id="stats"></div><h3>Messages by agent</h3><div id="agents"></div><h3>Evaluation</h3><p id="eval" class="note"></p></div></section>
</main>
<script>
const AGENTS={orchestrator:"Orchestrator",employment:"Employment agent",protection:"Protection agent",life_admin:"Life admin agent",financial:"Financial agent",wellbeing:"Wellbeing agent"};
const STARTERS=[["Start","hi"],["Short salary (flagship)","My employer was supposed to pay me AED 1,800, but I only received AED 1,000. What can I do?"],["Overtime","overtime calculator"],["Compare offer and contract","contract check"],["Check a job offer","Hotel job in Dubai, salary AED 3000, pay KES 50,000 visa fee to agent before travel, come on visit visa, send your passport copy"],
["Exploitation warning","My employer has not paid me for two months, and he says I cannot leave until I repay my recruitment fee."],
["Status check","status check"],["Do it for me","do it for me"]];
const $=id=>document.getElementById(id);let busy=false;
function esc(s){return s.replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function fmt(s){let h=esc(s).replace(/\*([^*\n]{1,300}?)\*/g,"<b>$1</b>");
 return h.replace(/https:\/\/[^\s<]+/g,u=>`<a href="${u}" target="_blank" rel="noopener noreferrer">${u}</a>`)}
function add(html,me){const r=document.createElement("div");r.className="row"+(me?" me":"");const b=document.createElement("div");b.className="bubble";b.innerHTML=html;r.appendChild(b);$("log").appendChild(r);$("log").scrollTop=1e9;return b}
function render(rep){const b=add(fmt(rep.text||""),false);
 if(rep.buttons&&rep.buttons.length){const c=document.createElement("div");c.className="chips";rep.buttons.forEach(x=>{const k=document.createElement("button");k.className="chip";k.textContent=x.title;k.onclick=()=>post({button_id:x.id},x.title);c.appendChild(k)});b.appendChild(c)}
 if(rep.menu){const m=document.createElement("div");m.className="menu";rep.menu.rows.forEach(x=>{const d=document.createElement("div");d.innerHTML="<b>"+esc(x.title)+"</b>"+(x.description?"<small>"+esc(x.description)+"</small>":"");d.onclick=()=>post({button_id:x.id},x.title);m.appendChild(d)});b.appendChild(m)}
 if(rep.file){const a=document.createElement("a");a.className="file";a.download=rep.file.name;a.href="data:"+rep.file.mime+";base64,"+rep.file.b64;a.textContent="⬇ "+rep.file.name;b.appendChild(document.createElement("br"));b.appendChild(a)}}
async function post(body,shown){if(busy)return;busy=true;$("sendBtn").disabled=true;if(shown)add(esc(shown),true);
 const t=document.createElement("div");t.className="typing";t.textContent="Rafiq is typing…";$("log").appendChild(t);$("log").scrollTop=1e9;
 try{const r=await fetch("/demo/api/send",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),credentials:"same-origin"});
  t.remove();if(r.status===401){location.reload();return}const j=await r.json();if(!r.ok){add(esc(j.detail||"Something went wrong"),false);return}
  (j.replies||[]).forEach(render);if(j.agent){const a=document.createElement("div");a.className="agent";a.innerHTML="Handled by <span>"+esc(AGENTS[j.agent]||j.agent)+"</span>";$("log").appendChild(a)}}
 catch(e){t.remove();add("Network problem, please try again.",false)}finally{busy=false;$("sendBtn").disabled=false;$("log").scrollTop=1e9}}
$("bar").onsubmit=e=>{e.preventDefault();const v=$("text").value.trim();if(!v)return;$("text").value="";post({text:v},v)};
$("att").onclick=()=>$("file").click();
$("file").onchange=()=>{const f=$("file").files[0];if(!f)return;if(f.size>3e6){add("That file is over 3 MB.",false);return}
 const rd=new FileReader();rd.onload=()=>post({file_b64:String(rd.result).split(",")[1]},"📎 "+f.name);rd.readAsDataURL(f);$("file").value=""};
$("loc").onclick=()=>post({latitude:25.2048,longitude:55.2708},"📍 Sample location (Dubai)");
STARTERS.forEach(([l,v])=>{const k=document.createElement("button");k.className="chip";k.textContent=l;k.onclick=()=>post({text:v},v);$("starters").appendChild(k)});
async function showChat(){$("login").style.display="none";$("chat").style.display="flex"}
$("go").onclick=async()=>{$("lerr").textContent="";const r=await fetch("/demo/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({code:$("code").value}),credentials:"same-origin"});
 if(r.ok){showChat();post({text:"hi"},"hi")}else{const j=await r.json().catch(()=>({}));$("lerr").textContent=j.detail||"That code isn't right"}};
$("code").addEventListener("keydown",e=>{if(e.key==="Enter")$("go").click()});
async function impact(){const r=await fetch("/demo/api/impact",{credentials:"same-origin"});if(!r.ok){$("stats").innerHTML="<p class='note'>Enter the demo code first.</p>";return}
 const j=await r.json(),a=j.all_time;let h=`<div class="stat"><b>${a.workers}</b><span>Workers using Rafiq</span></div><div class="stat"><b>${a.demo_sessions}</b><span>Demo sessions</span></div>`;
 a.metrics.forEach(m=>h+=`<div class="stat"><b>${m.value}</b><span>${esc(m.label)}</span></div>`);$("stats").innerHTML=h;
 const max=Math.max(1,...Object.values(a.agents));$("agents").innerHTML=Object.entries(a.agents).map(([k,v])=>`<div class="bar"><em>${esc(AGENTS[k]||k)}</em><i style="width:${Math.round(380*v/max)}px"></i>${v}</div>`).join("")||"<p class='note'>No messages yet.</p>";
 $("eval").innerHTML=j.eval?fmt(j.eval):"Run scripts/run_evals.py to add the score."}
$("tChat").onclick=()=>{$("tChat").className="on";$("tImpact").className="";$("impact").style.display="none";if($("login").style.display==="none")$("chat").style.display="flex"};
$("tImpact").onclick=()=>{$("tImpact").className="on";$("tChat").className="";$("chat").style.display="none";$("impact").style.display="block";impact()};
</script></body></html>"""
