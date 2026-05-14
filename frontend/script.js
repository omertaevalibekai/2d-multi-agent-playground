/* ════════════════════════════════════════════════════════════════════
   Agent Simulator v2 — frontend
   Modules: WS · Renderer · App · UI · AP (Agent Panel) · Rec

   NOTE: module objects are declared with var (not const/let) so they
   become window properties and are reachable from inline onclick="..."
   attributes in static HTML. Dynamic elements always use addEventListener.
════════════════════════════════════════════════════════════════════ */

// ─── Constants ─────────────────────────────────────────────────────
const SCENE_W = 800, SCENE_H = 600, LERP = 0.28;

const OBJ_STYLE = {
  table:    { fill:"#fdf4e7", stroke:"#c8975a", label:"#8a6030" },
  computer: { fill:"#eff4ff", stroke:"#5b8def", label:"#2563eb" },
  chair:    { fill:"#fef2f2", stroke:"#e88080", label:"#b45252" },
  wall:     { fill:"#f0f2f8", stroke:"#8490be", label:"#4a5677" },
  door:     { fill:"#f0fdf4", stroke:"#34a868", label:"#168040" },
  box:      { fill:"#fffbeb", stroke:"#c09a3e", label:"#8a6e1a" },
};
const OBJ_ICONS  = { table:"🪑", computer:"🖥", chair:"💺", wall:"🧱", door:"🚪", box:"📦" };
const STATE_CLRS = { idle:"#475569", moving:"#3b82f6", interacting:"#f59e0b" };
const TASK_CLRS  = { Research:"#3b82f6", Writing:"#22c55e", Code:"#8b5cf6",
                     Analysis:"#06b6d4", Design:"#ec4899", Other:"#64748b" };
const MODELS = { claude:[], openai:[] };

// ─── State ─────────────────────────────────────────────────────────
let scene     = { agents:[], objects:[], cmd_log:[], width:SCENE_W, height:SCENE_H };
let localPos  = {};      // id → {x,y}
let selectedId = null;
let activeTool = "select";
let dragState  = null;
let mouseScene = { x:0, y:0 };
let cmdHistory = [], cmdHIdx = -1;
let canvas, ctx, animTick = 0;

// ════════════════════════════════════════════════════════════════════
//  WS
// ════════════════════════════════════════════════════════════════════
var WS = (() => {
  let ws, retry;
  function connect() {
    ws = new WebSocket(`ws://${location.host}/ws`);
    ws.onopen    = () => { setConn(true);  clearTimeout(retry); };
    ws.onclose   = () => { setConn(false); retry = setTimeout(connect, 2000); };
    ws.onerror   = () => {};
    ws.onmessage = e => {
      try {
        const m = JSON.parse(e.data);
        if (m.type === "state") applyState(m.data);
        else if (typeof BP !== "undefined") BP.onWsEvent(m);
      } catch(_) {}
    };
  }
  function setConn(ok) {
    document.getElementById("connDot").className   = "conn-dot"+(ok?" ok":" err");
    document.getElementById("connLabel").textContent = ok?"Connected":"Reconnecting…";
  }
  return { connect };
})();

function applyState(s) {
  scene = s;
  const live = new Set(s.agents.map(a=>a.id));
  for (const id of Object.keys(localPos)) if(!live.has(id)) delete localPos[id];
  for (const a of s.agents) if(!localPos[a.id]) localPos[a.id]={x:a.x,y:a.y};
  UI.updateAgentList();
  UI.updateObjectList();
  if (typeof BP !== "undefined") BP.renderChips();
  // Refresh AP if open
  if (AP.currentId) {
    const cur = s.agents.find(a=>a.id===AP.currentId);
    if (!cur) AP.close(); else AP.refreshHeader(cur);
  }
}

// ════════════════════════════════════════════════════════════════════
//  Canvas & Renderer
// ════════════════════════════════════════════════════════════════════
function initCanvas() {
  canvas = document.getElementById("scene");
  ctx    = canvas.getContext("2d");
  canvas.width  = SCENE_W;
  canvas.height = SCENE_H;
  scaleCanvas();
  window.addEventListener("resize", scaleCanvas);
  requestAnimationFrame(renderLoop);
}

function scaleCanvas() {
  const wrap = document.getElementById("canvasWrap");
  const s    = Math.min((wrap.clientWidth-24)/SCENE_W, (wrap.clientHeight-24)/SCENE_H, 1.5);
  canvas.style.width  = (SCENE_W*s)+"px";
  canvas.style.height = (SCENE_H*s)+"px";
}

function renderLoop() {
  animTick++;
  for (const a of scene.agents) {
    const lp = localPos[a.id];
    if (lp) { lp.x += (a.x-lp.x)*LERP; lp.y += (a.y-lp.y)*LERP; }
  }
  ctx.clearRect(0,0,SCENE_W,SCENE_H);
  drawBg(); drawGrid();
  for (const o of scene.objects) drawObject(o);
  for (const a of scene.agents)  drawMovePath(a);
  for (const a of scene.agents)  drawAgent(a);
  drawCursor();
  requestAnimationFrame(renderLoop);
}

function drawBg() {
  ctx.fillStyle = "#eef1f9";
  ctx.fillRect(0,0,SCENE_W,SCENE_H);
}

function drawGrid() {
  ctx.save();
  ctx.strokeStyle="rgba(0,0,0,.04)"; ctx.lineWidth=.5;
  for(let x=0;x<=SCENE_W;x+=25){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,SCENE_H);ctx.stroke();}
  for(let y=0;y<=SCENE_H;y+=25){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(SCENE_W,y);ctx.stroke();}
  ctx.strokeStyle="rgba(0,0,0,.09)"; ctx.lineWidth=1;
  for(let x=0;x<=SCENE_W;x+=100){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,SCENE_H);ctx.stroke();}
  for(let y=0;y<=SCENE_H;y+=100){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(SCENE_W,y);ctx.stroke();}
  ctx.fillStyle="rgba(74,86,119,.35)"; ctx.font="9px monospace"; ctx.textAlign="left";
  for(let x=100;x<SCENE_W;x+=100) ctx.fillText(x,x+2,10);
  for(let y=100;y<SCENE_H;y+=100) ctx.fillText(y,2,y-2);
  ctx.restore();
}

function drawObject(o) {
  const s = OBJ_STYLE[o.type]||OBJ_STYLE.box;
  ctx.save();
  ctx.shadowColor="rgba(0,0,0,.18)"; ctx.shadowBlur=10; ctx.shadowOffsetY=3;
  ctx.fillStyle=s.fill; ctx.strokeStyle=s.stroke; ctx.lineWidth=1.5;
  if(o.type==="wall"){ctx.fillRect(o.x,o.y,o.w,o.h);ctx.strokeRect(o.x,o.y,o.w,o.h);}
  else{rrect(o.x,o.y,o.w,o.h,7);ctx.fill();ctx.stroke();}
  ctx.shadowBlur=0; ctx.shadowOffsetY=0;
  // Label
  ctx.fillStyle=s.label; ctx.font="bold 10px sans-serif"; ctx.textAlign="center"; ctx.textBaseline="middle";
  const cy = o.task ? o.y+o.h/2-6 : o.y+o.h/2;
  ctx.fillText(o.label||o.id, o.x+o.w/2, cy);
  // Task chip
  if(o.task){
    const tc = TASK_CLRS[o.task]||TASK_CLRS.Other;
    ctx.fillStyle=tc+"cc"; ctx.font="bold 8px sans-serif";
    ctx.fillText(o.task, o.x+o.w/2, o.y+o.h/2+8);
  }
  // Interaction badge
  if(o.agents_here&&o.agents_here.length){
    ctx.fillStyle="#f59e0b"; ctx.beginPath(); ctx.arc(o.x+o.w-8,o.y+8,7,0,Math.PI*2); ctx.fill();
    ctx.fillStyle="#fff"; ctx.font="bold 8px sans-serif"; ctx.fillText(o.agents_here.length,o.x+o.w-8,o.y+11);
  }
  ctx.restore();
}

function drawMovePath(a) {
  if(a.target_x==null) return;
  const lp=localPos[a.id]; if(!lp) return;
  ctx.save();
  ctx.globalAlpha=.45; ctx.strokeStyle=a.color; ctx.lineWidth=1.5; ctx.setLineDash([6,5]);
  ctx.beginPath(); ctx.moveTo(lp.x,lp.y); ctx.lineTo(a.target_x,a.target_y); ctx.stroke();
  ctx.setLineDash([]);
  const pulse=.5+.5*Math.sin(animTick*.12);
  ctx.globalAlpha=pulse*.65; ctx.strokeStyle=a.color; ctx.lineWidth=1.5;
  ctx.beginPath(); ctx.arc(a.target_x,a.target_y,8,0,Math.PI*2); ctx.stroke();
  const ang=Math.atan2(a.target_y-lp.y,a.target_x-lp.x);
  ctx.globalAlpha=.6; ctx.fillStyle=a.color;
  ctx.beginPath();ctx.moveTo(a.target_x,a.target_y);
  ctx.lineTo(a.target_x-9*Math.cos(ang-.5),a.target_y-9*Math.sin(ang-.5));
  ctx.lineTo(a.target_x-9*Math.cos(ang+.5),a.target_y-9*Math.sin(ang+.5));
  ctx.closePath();ctx.fill();
  ctx.restore();
}

function drawAgent(a) {
  const lp=localPos[a.id]; if(!lp) return;
  const {x,y}=lp, r=16, sc=STATE_CLRS[a.state]||STATE_CLRS.idle;
  ctx.save();
  // Glow
  const glow=ctx.createRadialGradient(x,y,0,x,y,r*2.8);
  glow.addColorStop(0,a.color+"28"); glow.addColorStop(1,"transparent");
  ctx.fillStyle=glow; ctx.beginPath(); ctx.arc(x,y,r*2.8,0,Math.PI*2); ctx.fill();
  // Interaction pulse
  if(a.state==="interacting"){
    const p=.4+.6*Math.abs(Math.sin(animTick*.1));
    ctx.globalAlpha=p; ctx.strokeStyle="#f59e0b"; ctx.lineWidth=2;
    ctx.beginPath(); ctx.arc(x,y,r+8+4*p,0,Math.PI*2); ctx.stroke(); ctx.globalAlpha=1;
  }
  // State ring
  ctx.strokeStyle=sc; ctx.lineWidth=2; ctx.globalAlpha=.75;
  ctx.beginPath(); ctx.arc(x,y,r+4,0,Math.PI*2); ctx.stroke(); ctx.globalAlpha=1;
  // Selection
  if(selectedId===a.id){
    ctx.strokeStyle="#6366f1"; ctx.lineWidth=1.5; ctx.globalAlpha=.55;
    ctx.setLineDash([4,4]); ctx.lineDashOffset=-(animTick*.4);
    ctx.beginPath(); ctx.arc(x,y,r+9,0,Math.PI*2); ctx.stroke();
    ctx.setLineDash([]); ctx.lineDashOffset=0; ctx.globalAlpha=1;
  }
  // Body
  const grad=ctx.createRadialGradient(x-r*.3,y-r*.35,0,x,y,r);
  grad.addColorStop(0,lighten(a.color,.45)); grad.addColorStop(1,a.color);
  ctx.fillStyle=grad; ctx.beginPath(); ctx.arc(x,y,r,0,Math.PI*2); ctx.fill();
  ctx.fillStyle="rgba(255,255,255,.18)";
  ctx.beginPath(); ctx.arc(x-r*.3,y-r*.35,r*.45,0,Math.PI*2); ctx.fill();
  // State dot
  ctx.fillStyle=sc; ctx.beginPath(); ctx.arc(x+r*.65,y-r*.65,4.5,0,Math.PI*2); ctx.fill();
  // ID label
  ctx.fillStyle="#fff"; ctx.font="bold 9px monospace";
  ctx.textAlign="center"; ctx.textBaseline="middle";
  ctx.fillText(a.id.slice(0,6).toUpperCase(),x,y+.5);
  // Name
  ctx.fillStyle="rgba(26,34,53,.7)"; ctx.font="8.5px sans-serif";
  ctx.fillText(a.name,x,y+r+11);
  ctx.restore();
}

function drawCursor() {
  if(activeTool!=="select"||!selectedId) return;
  const {x,y}=mouseScene;
  if(x<0||y<0||x>SCENE_W||y>SCENE_H) return;
  ctx.save();
  ctx.globalAlpha=.4; ctx.strokeStyle="#6366f1"; ctx.lineWidth=1; ctx.setLineDash([4,4]);
  ctx.beginPath();ctx.moveTo(x-10,y);ctx.lineTo(x+10,y);ctx.stroke();
  ctx.beginPath();ctx.moveTo(x,y-10);ctx.lineTo(x,y+10);ctx.stroke();
  ctx.setLineDash([]); ctx.restore();
}

// ─── Canvas helpers ─────────────────────────────────────────────────
function rrect(x,y,w,h,r){
  ctx.beginPath();
  ctx.moveTo(x+r,y);ctx.lineTo(x+w-r,y);ctx.arcTo(x+w,y,x+w,y+r,r);
  ctx.lineTo(x+w,y+h-r);ctx.arcTo(x+w,y+h,x+w-r,y+h,r);
  ctx.lineTo(x+r,y+h);ctx.arcTo(x,y+h,x,y+h-r,r);
  ctx.lineTo(x,y+r);ctx.arcTo(x,y,x+r,y,r);ctx.closePath();
}
function lighten(hex,a){
  const n=parseInt(hex.slice(1),16);
  const r=Math.min(255,((n>>16)&0xff)+Math.round(255*a));
  const g=Math.min(255,((n>>8 )&0xff)+Math.round(255*a));
  const b=Math.min(255,( n     &0xff)+Math.round(255*a));
  return `rgb(${r},${g},${b})`;
}
function sceneXY(cx,cy){
  const rc=canvas.getBoundingClientRect();
  return {x:(cx-rc.left)*SCENE_W/rc.width, y:(cy-rc.top)*SCENE_H/rc.height};
}
function objAt(sx,sy){ return scene.objects.find(o=>sx>=o.x&&sx<=o.x+o.w&&sy>=o.y&&sy<=o.y+o.h)||null; }
function agentAt(sx,sy){ return scene.agents.find(a=>{const lp=localPos[a.id];return lp&&Math.hypot(sx-lp.x,sy-lp.y)<=20;})||null; }

// ─── Canvas events ──────────────────────────────────────────────────
function initCanvasEvents() {
  canvas.addEventListener("mousemove", e=>{
    mouseScene = sceneXY(e.clientX,e.clientY);
    document.getElementById("canvasCoord").textContent =
      `x:${Math.round(mouseScene.x)} y:${Math.round(mouseScene.y)}`;
    if(dragState&&activeTool==="drag"){
      const pos=mouseScene;
      const nx=Math.max(0,Math.min(dragState.ox+(pos.x-dragState.mx),SCENE_W-5));
      const ny=Math.max(0,Math.min(dragState.oy+(pos.y-dragState.my),SCENE_H-5));
      fetch(`/api/objects/${dragState.id}`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({x:nx,y:ny})});
      canvas.style.cursor="grabbing";
    }
  });
  canvas.addEventListener("mousedown",e=>{
    if(e.button!==0) return;
    if(activeTool==="drag"){
      const o=objAt(mouseScene.x,mouseScene.y);
      if(o){ dragState={id:o.id,mx:mouseScene.x,my:mouseScene.y,ox:o.x,oy:o.y}; e.preventDefault(); }
    }
  });
  canvas.addEventListener("mouseup",()=>{ dragState=null; canvas.style.cursor="crosshair"; });
  canvas.addEventListener("click",e=>{
    const pos=sceneXY(e.clientX,e.clientY);
    const ca=agentAt(pos.x,pos.y);
    if(ca){ selectedId=ca.id; UI.updateAgentList(); return; }
    if(activeTool==="select"&&selectedId&&scene.agents.find(a=>a.id===selectedId)){
      App.runCmd(`${selectedId} move ${Math.round(pos.x)} ${Math.round(pos.y)}`); return;
    }
    selectedId=null; UI.updateAgentList();
  });
  canvas.addEventListener("dblclick",e=>{
    const pos=sceneXY(e.clientX,e.clientY);
    const ca=agentAt(pos.x,pos.y);
    if(ca){ AP.open(ca.id); }
  });
  canvas.addEventListener("contextmenu",e=>{ e.preventDefault(); selectedId=null; UI.updateAgentList(); });
}

// ════════════════════════════════════════════════════════════════════
//  App — API calls
// ════════════════════════════════════════════════════════════════════
var App = (() => {
  async function runCmd(cmd) {
    const smart=document.getElementById("smartToggle").checked;
    const btn=document.getElementById("cmdRunBtn");
    btn.classList.add("loading");
    try {
      const r=await fetch("/api/command",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({command:cmd,smart})});
      const d=await r.json();
      UI.addLog(cmd, d.message||d.results?.map(x=>x.message).join("\n")||"", d.ok!==false);
      return d;
    } catch(err){ UI.addLog(cmd,"Network error: "+err.message,false); }
    finally { btn.classList.remove("loading"); }
  }
  function execCmd() {
    const inp=document.getElementById("cmdInput"); const cmd=inp.value.trim();
    if(!cmd) return;
    cmdHistory.unshift(cmd); if(cmdHistory.length>100) cmdHistory.pop();
    cmdHIdx=-1; inp.value=""; runCmd(cmd);
  }
  async function createAgent() {
    const id=document.getElementById("fAgentId").value.trim();
    const name=document.getElementById("fAgentName").value.trim()||id;
    const x=+document.getElementById("fAgentX").value||150;
    const y=+document.getElementById("fAgentY").value||150;
    const color=document.getElementById("fAgentColor").value;
    if(!id){alert("ID is required");return;}
    await fetch("/api/agents",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id,name,x,y,color})});
    UI.closeModal("addAgentModal");
  }
  async function createObject() {
    const id=document.getElementById("fObjId").value.trim();
    if(!id){alert("ID is required");return;}
    await fetch("/api/objects",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
      id, type:document.getElementById("fObjType").value,
      label:document.getElementById("fObjLabel").value||id,
      x:+document.getElementById("fObjX").value||300, y:+document.getElementById("fObjY").value||300,
      w:+document.getElementById("fObjW").value||80,  h:+document.getElementById("fObjH").value||60,
      task:document.getElementById("fObjTask").value,
      task_desc:document.getElementById("fObjTaskDesc").value,
    })});
    UI.closeModal("addObjModal");
  }
  async function saveObjectTask() {
    const oid=document.getElementById("etObjId").value;
    const task=document.getElementById("etTask").value;
    const task_desc=document.getElementById("etTaskDesc").value;
    await fetch(`/api/objects/${oid}`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({task,task_desc})});
    UI.closeModal("editTaskModal");
  }
  async function resetScene() {
    if(!confirm("Reset scene to defaults?")) return;
    await fetch("/api/reset",{method:"POST"});
    UI.addLog("reset","Scene reset",true);
  }
  async function exportHistory() {
    const r=await fetch("/api/export"); const d=await r.json();
    const blob=new Blob([JSON.stringify(d,null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a"); a.href=url; a.download=`agent-sim-${Date.now()}.json`; a.click();
    URL.revokeObjectURL(url);
  }
  async function deleteAgent(id) {
    await fetch(`/api/agents/${id}`,{method:"DELETE"});
    if(selectedId===id) selectedId=null;
    if(AP.currentId===id) AP.close();
    UI.updateAgentList();
  }
  async function deleteObject(id) { await fetch(`/api/objects/${id}`,{method:"DELETE"}); }
  return { runCmd, execCmd, createAgent, createObject, saveObjectTask, resetScene, exportHistory, deleteAgent, deleteObject };
})();

// ════════════════════════════════════════════════════════════════════
//  UI — DOM helpers
// ════════════════════════════════════════════════════════════════════
var UI = (() => {
  function updateAgentList() {
    const list=document.getElementById("agentList");
    document.getElementById("agentCount").textContent=scene.agents.length;
    list.innerHTML="";
    for (const a of scene.agents) {
      const lp=localPos[a.id]||{x:a.x,y:a.y};
      const div=document.createElement("div");
      div.className="agent-card"+(selectedId===a.id?" selected":"");

      const dot=document.createElement("div");
      dot.className="a-dot"; dot.style.background=a.color;

      const info=document.createElement("div");
      info.className="a-info";
      info.innerHTML=`<div class="a-name">${esc(a.name)}</div><div class="a-meta">${esc(a.id)} · ${Math.round(lp.x)},${Math.round(lp.y)}</div>`;

      const state=document.createElement("div");
      state.className=`a-state ${a.state}`; state.textContent=a.state;

      const delBtn=document.createElement("button");
      delBtn.className="a-del icon-btn"; delBtn.title="Delete agent";
      delBtn.innerHTML='<svg viewBox="0 0 16 16"><path d="M3 4h10M6 4V2h4v2M5 4v8a1 1 0 001 1h4a1 1 0 001-1V4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>';
      delBtn.dataset.delId=a.id;

      div.dataset.selectId=a.id;
      div.title="Double-click agent on canvas to edit";
      div.append(dot, info, state, delBtn);
      list.appendChild(div);
    }
  }
  function updateObjectList() {
    const list=document.getElementById("objectList"); list.innerHTML="";
    for (const o of scene.objects) {
      const taskColor=TASK_CLRS[o.task]||TASK_CLRS.Other;
      const div=document.createElement("div"); div.className="obj-row";

      const iconEl=document.createElement("span");
      iconEl.className="obj-icon"; iconEl.textContent=OBJ_ICONS[o.type]||"⬜";

      const infoEl=document.createElement("div"); infoEl.className="obj-info";
      const idEl=document.createElement("div"); idEl.className="obj-id"; idEl.textContent=o.label||o.id;
      const metaEl=document.createElement("div"); metaEl.className="obj-meta";
      metaEl.textContent=o.type+" ";

      const taskSpan=document.createElement("span");
      if(o.task){
        taskSpan.className="obj-task-badge";
        taskSpan.style.cssText=`background:${taskColor}22;color:${taskColor}`;
        taskSpan.textContent=o.task;
      } else {
        taskSpan.style.cssText="color:var(--muted);font-size:9px;cursor:pointer";
        taskSpan.textContent="+ task";
      }
      taskSpan.addEventListener("click", function(e){ e.stopPropagation(); editObjectTask(o.id); });
      metaEl.appendChild(taskSpan);
      infoEl.append(idEl, metaEl);

      const delBtn=document.createElement("button");
      delBtn.className="obj-del icon-btn"; delBtn.title="Remove";
      delBtn.innerHTML='<svg viewBox="0 0 16 16"><path d="M3 4h10M6 4V2h4v2M5 4v8a1 1 0 001 1h4a1 1 0 001-1V4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>';
      delBtn.addEventListener("click", function(){ App.deleteObject(o.id); });

      div.append(iconEl, infoEl, delBtn);
      list.appendChild(div);
    }
  }
  function editObjectTask(oid) {
    const obj=scene.objects.find(o=>o.id===oid); if(!obj) return;
    document.getElementById("etObjId").value=oid;
    document.getElementById("etTask").value=obj.task||"";
    document.getElementById("etTaskDesc").value=obj.task_desc||"";
    openModal("editTaskModal");
  }
  function addLog(cmd,result,ok) {
    const list=document.getElementById("logList");
    const now=new Date().toLocaleTimeString("en-US",{hour12:false});
    const div=document.createElement("div"); div.className="log-entry "+(ok?"ok":"err");
    div.innerHTML=`<div class="log-row1"><span class="log-time">${now}</span><span class="log-mark ${ok?"ok":"err"}">${ok?"✓":"✗"}</span><span class="log-cmd" title="${esc(cmd)}">${esc(cmd)}</span></div>${result?`<div class="log-result">${esc(result)}</div>`:""}`;
    list.appendChild(div);
    if(list.children.length>120) list.firstChild.remove();
    list.scrollTop=list.scrollHeight;
    Rec.record(cmd);
  }
  function clearLog() { document.getElementById("logList").innerHTML=""; }
  function fill(cmd)   { const i=document.getElementById("cmdInput"); i.value=cmd; i.focus(); }
  function openModal(id)  { document.getElementById(id).classList.remove("hidden"); }
  function closeModal(id) { document.getElementById(id).classList.add("hidden"); }
  function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
  return { updateAgentList, updateObjectList, editObjectTask, addLog, clearLog, fill, openModal, closeModal, esc };
})();

// ════════════════════════════════════════════════════════════════════
//  AP — Agent Panel
// ════════════════════════════════════════════════════════════════════
var AP = (() => {
  let currentId   = null;
  let currentTab  = "chat";
  let chatHistory = {};    // agentId → [{role,content,ts}]

  function open(id) {
    const a=scene.agents.find(x=>x.id===id); if(!a) return;
    currentId = id;
    selectedId = id;
    UI.updateAgentList();
    // Switch right sidebar to agent mode
    document.getElementById("cmdPanelWrap").style.display="none";
    document.getElementById("agentPanel").classList.remove("hidden");
    refreshHeader(a);
    switchTab("chat");
    populateConfig(a);
    populateAI(a);
    populateMCP(a);
    if (typeof BP !== "undefined") { BP.renderMcpPresets(id); BP.renderTools(id); }
    renderChat(id);
  }

  function close() {
    currentId=null; selectedId=null;
    document.getElementById("agentPanel").classList.add("hidden");
    document.getElementById("cmdPanelWrap").style.display="";
    UI.updateAgentList();
  }

  function refreshHeader(a) {
    document.getElementById("apDot").style.background=a.color;
    document.getElementById("apName").textContent=a.name;
    document.getElementById("apId").textContent=a.id;
  }

  function switchTab(tab) {
    currentTab=tab;
    document.querySelectorAll(".ap-tab").forEach(b=>b.classList.toggle("active",b.dataset.tab===tab));
    document.querySelectorAll(".ap-pane").forEach(p=>p.classList.toggle("hidden",p.id!=="ap-"+tab));
  }

  // ── Config ──────────────────────────────────────────────────────
  function populateConfig(a) {
    document.getElementById("cfgName").value=a.name;
    document.getElementById("cfgColor").value=a.color;
    document.getElementById("cfgColorVal").textContent=a.color;
    document.getElementById("cfgSpeed").value=a.speed;
    document.getElementById("cfgSpeedVal").textContent=Math.round(a.speed);
    document.getElementById("cfgX").value=Math.round(a.x);
    document.getElementById("cfgY").value=Math.round(a.y);
  }
  async function saveConfig() {
    if(!currentId) return;
    const name=document.getElementById("cfgName").value.trim();
    const color=document.getElementById("cfgColor").value;
    const speed=+document.getElementById("cfgSpeed").value;
    const x=+document.getElementById("cfgX").value;
    const y=+document.getElementById("cfgY").value;
    await fetch(`/api/agents/${currentId}/config`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,color,speed,x,y})});
    UI.addLog(`config ${currentId}`,"Saved",true);
  }
  document.getElementById("cfgColor").addEventListener("input",e=>{
    document.getElementById("cfgColorVal").textContent=e.target.value;
  });

  // ── AI ──────────────────────────────────────────────────────────
  function populateAI(a) {
    const cfg=a.ai_config||{};
    const prov=cfg.provider||"claude";
    setProvider(prov);
    // Model list comes from server; build select
    rebuildModelSelect(prov, cfg.model||"");
    document.getElementById("aiSysPrompt").value=cfg.system_prompt||"";
    const temp=cfg.temperature??0.7;
    document.getElementById("aiTemp").value=temp;
    document.getElementById("aiTempVal").textContent=parseFloat(temp).toFixed(2);
    // Don't pre-fill keys (never show them)
  }
  function setProvider(p) {
    document.querySelectorAll(".prov-btn").forEach(b=>b.classList.toggle("active",b.dataset.p===p));
    rebuildModelSelect(p);
  }
  function rebuildModelSelect(prov, current="") {
    const sel=document.getElementById("aiModelSel"); sel.innerHTML="";
    const list=MODELS[prov]||[];
    for (const m of list) {
      const opt=document.createElement("option");
      opt.value=m.id; opt.textContent=m.name;
      if(m.id===current) opt.selected=true;
      sel.appendChild(opt);
    }
  }
  async function saveAI() {
    if(!currentId) return;
    const prov=document.querySelector(".prov-btn.active")?.dataset.p||"claude";
    const model=document.getElementById("aiModelSel").value;
    const sp=document.getElementById("aiSysPrompt").value;
    const temp=parseFloat(document.getElementById("aiTemp").value);
    const keyC=document.getElementById("aiKeyClaude").value;
    const keyO=document.getElementById("aiKeyOpenai").value;
    const enabledTools = typeof BP !== "undefined" ? BP.getEnabledTools() : [];
    const payload={ai_config:{provider:prov,model,system_prompt:sp,temperature:temp,enabled_tools:enabledTools}};
    if(keyC) payload.ai_config.api_key_claude=keyC;
    if(keyO) payload.ai_config.api_key_openai=keyO;
    await fetch(`/api/agents/${currentId}/config`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    UI.addLog(`ai-config ${currentId}`,"AI config saved",true);
    // Clear key fields for security
    document.getElementById("aiKeyClaude").value="";
    document.getElementById("aiKeyOpenai").value="";
  }

  // ── MCP ─────────────────────────────────────────────────────────
  function populateMCP(a) {
    const list=document.getElementById("mcpList"); list.innerHTML="";
    const mcps=(a.mcp_servers||[]);
    if(!mcps.length){ list.innerHTML='<div class="mcp-empty">No MCP servers configured</div>'; return; }
    for (const m of mcps) {
      const div=document.createElement("div"); div.className="mcp-item";

      // Header row
      const hdr=document.createElement("div"); hdr.className="mcp-item-hdr";
      const nameEl=document.createElement("span"); nameEl.className="mcp-item-name"; nameEl.textContent=m.name;
      const acts=document.createElement("div"); acts.className="mcp-item-actions";

      const togBtn=document.createElement("button");
      togBtn.className="mcp-toggle "+(m.active?"on":"off");
      togBtn.textContent=m.active?"Active":"Inactive";
      togBtn.addEventListener("click", (function(mid){ return function(){ toggleMcp(mid); }; })(m.id));

      const delBtn=document.createElement("button");
      delBtn.className="mcp-del"; delBtn.textContent="✕";
      delBtn.addEventListener("click", (function(mid){ return function(){ removeMcp(mid); }; })(m.id));

      acts.append(togBtn, delBtn);
      hdr.append(nameEl, acts);
      div.appendChild(hdr);

      if(m.url){ const u=document.createElement("div"); u.className="mcp-item-url"; u.textContent=m.url; div.appendChild(u); }
      if(m.description){ const d2=document.createElement("div"); d2.className="mcp-item-desc"; d2.textContent=m.description; div.appendChild(d2); }

      list.appendChild(div);
    }
  }
  function toggleMcpForm() { document.getElementById("mcpForm").classList.toggle("hidden"); }
  function hideMcpForm()   { document.getElementById("mcpForm").classList.add("hidden"); clearMcpForm(); }
  function clearMcpForm()  { ["mcpFName","mcpFUrl","mcpFDesc"].forEach(id=>document.getElementById(id).value=""); }
  async function addMcp() {
    if(!currentId) return;
    const name=document.getElementById("mcpFName").value.trim();
    if(!name){alert("Name is required");return;}
    const a=scene.agents.find(x=>x.id===currentId); if(!a) return;
    const newMcp={id:Date.now().toString(),name,url:document.getElementById("mcpFUrl").value.trim(),description:document.getElementById("mcpFDesc").value.trim(),active:true};
    const servers=[...(a.mcp_servers||[]),newMcp];
    await fetch(`/api/agents/${currentId}/config`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({mcp_servers:servers})});
    hideMcpForm();
    const updated=scene.agents.find(x=>x.id===currentId);
    if(updated) populateMCP(updated);
  }
  async function removeMcp(mid) {
    if(!currentId) return;
    const a=scene.agents.find(x=>x.id===currentId); if(!a) return;
    const servers=(a.mcp_servers||[]).filter(m=>m.id!==mid);
    await fetch(`/api/agents/${currentId}/config`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({mcp_servers:servers})});
  }
  async function toggleMcp(mid) {
    if(!currentId) return;
    const a=scene.agents.find(x=>x.id===currentId); if(!a) return;
    const servers=(a.mcp_servers||[]).map(m=>m.id===mid?{...m,active:!m.active}:m);
    await fetch(`/api/agents/${currentId}/config`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({mcp_servers:servers})});
  }

  // ── Chat ─────────────────────────────────────────────────────────
  function renderChat(id) {
    const msgs=document.getElementById("chatMsgs"); msgs.innerHTML="";
    const hist=chatHistory[id||currentId]||[];
    if(!hist.length){
      msgs.innerHTML='<div class="chat-welcome">Start chatting with this agent.<br>It uses its configured AI model.</div>';
      return;
    }
    for (const m of hist) appendBubble(m.role,m.content,m.ts);
    msgs.scrollTop=msgs.scrollHeight;
  }
  function appendBubble(role,content,ts) {
    const msgs=document.getElementById("chatMsgs");
    const welc=msgs.querySelector(".chat-welcome"); if(welc) welc.remove();
    const div=document.createElement("div");
    div.className=`chat-bubble ${role==="user"?"user":"agent"}`;
    const time=ts?new Date(ts*1000).toLocaleTimeString("en-US",{hour12:false,hour:"2-digit",minute:"2-digit"}):"";
    div.innerHTML=`<div class="chat-bubble-inner">${UI.esc(content)}</div><div class="chat-ts">${time}</div>`;
    msgs.appendChild(div);
    msgs.scrollTop=msgs.scrollHeight;
    return div;
  }
  function showTyping() {
    const msgs=document.getElementById("chatMsgs");
    const t=document.createElement("div"); t.id="typingDots"; t.className="typing";
    t.innerHTML="<span></span><span></span><span></span>"; msgs.appendChild(t);
    msgs.scrollTop=msgs.scrollHeight;
  }
  function hideTyping() { document.getElementById("typingDots")?.remove(); }
  async function sendChat() {
    if(!currentId) return;
    const ta=document.getElementById("chatIn");
    const msg=ta.value.trim(); if(!msg) return;
    ta.value="";
    // Append user bubble
    const now=Date.now()/1000;
    if(!chatHistory[currentId]) chatHistory[currentId]=[];
    chatHistory[currentId].push({role:"user",content:msg,ts:now});
    appendBubble("user",msg,now);
    // Send
    document.getElementById("chatSendBtn").classList.add("loading");
    showTyping();
    try {
      const r=await fetch(`/api/agents/${currentId}/chat`,{
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({message:msg, history:chatHistory[currentId].slice(0,-1).map(h=>({role:h.role,content:h.content}))})
      });
      const d=await r.json();
      hideTyping();
      if(d.ok){
        const ats=Date.now()/1000;
        chatHistory[currentId].push({role:"assistant",content:d.response,ts:ats});
        appendBubble("agent",d.response,ats);
      } else {
        const errDiv=appendBubble("error","Error: "+(d.error||"Unknown error"),Date.now()/1000);
        errDiv.classList.add("error");
      }
    } catch(err){
      hideTyping();
      appendBubble("agent","Network error: "+err.message, Date.now()/1000);
    } finally {
      document.getElementById("chatSendBtn").classList.remove("loading");
    }
  }
  async function clearChat() {
    if(!currentId) return;
    await fetch(`/api/agents/${currentId}/chat`,{method:"DELETE"});
    chatHistory[currentId]=[];
    renderChat(currentId);
  }

  // Tab clicks
  document.querySelectorAll(".ap-tab").forEach(b=>{
    b.addEventListener("click",()=>switchTab(b.dataset.tab));
  });

  return { open, close, refreshHeader, sendChat, clearChat,
           saveConfig, populateConfig, saveAI, setProvider,
           toggleMcpForm, hideMcpForm, addMcp, removeMcp, toggleMcp,
           get currentId(){ return currentId; } };
})();

// ════════════════════════════════════════════════════════════════════
//  Rec — recorder / playback
// ════════════════════════════════════════════════════════════════════
var Rec = (() => {
  let recording=false, tape=[], playSpeed=1, playTimer=null;
  function toggleRecord() {
    recording=!recording;
    const btn=document.getElementById("recBtn");
    if(recording){ tape=[]; btn.classList.add("recording"); btn.title="Stop"; }
    else         { btn.classList.remove("recording"); btn.title="Record"; document.getElementById("playBtn").disabled=tape.length===0; }
  }
  function record(cmd) { if(recording) tape.push({ts:Date.now(),cmd}); }
  function togglePlay() {
    if(playTimer){clearTimeout(playTimer);playTimer=null; document.getElementById("playBtn").innerHTML='<svg viewBox="0 0 16 16"><polygon points="4,2 13,8 4,14" fill="currentColor"/></svg>'; return;}
    if(!tape.length) return;
    document.getElementById("playBtn").innerHTML='<svg viewBox="0 0 16 16"><rect x="3" y="2" width="4" height="12" fill="currentColor"/><rect x="9" y="2" width="4" height="12" fill="currentColor"/></svg>';
    let i=0;
    function step(){ if(i>=tape.length){togglePlay();return;} App.runCmd(tape[i].cmd); const next=tape[++i]; if(next) playTimer=setTimeout(step,(next.ts-tape[i-1].ts)/playSpeed); else togglePlay(); }
    step();
  }
  function setSpeed(v) { playSpeed=+v; document.getElementById("speedVal").textContent=(+v).toFixed(2).replace(/\.?0+$/,"")+"×"; }
  return { toggleRecord, record, togglePlay, setSpeed };
})();

// ════════════════════════════════════════════════════════════════════
//  Keyboard
// ════════════════════════════════════════════════════════════════════
function initLists() {
  // Delegated listeners on static containers — survive innerHTML rebuilds
  document.getElementById("agentList").addEventListener("click", function(e) {
    const openBtn = e.target.closest("[data-open-id]");
    if (openBtn) { e.stopPropagation(); AP.open(openBtn.dataset.openId); return; }
    const delBtn = e.target.closest("[data-del-id]");
    if (delBtn)  { e.stopPropagation(); App.deleteAgent(delBtn.dataset.delId); return; }
    const card = e.target.closest("[data-select-id]");
    if (card) {
      selectedId = card.dataset.selectId;
      UI.updateAgentList();
      const inp = document.getElementById("cmdInput");
      inp.value = selectedId + " "; inp.focus();
    }
  });
}

function initKeyboard() {
  const inp=document.getElementById("cmdInput");
  inp.addEventListener("keydown",e=>{
    if(e.key==="Enter"){e.preventDefault();App.execCmd();}
    else if(e.key==="ArrowUp"){e.preventDefault();if(cmdHIdx<cmdHistory.length-1)cmdHIdx++;inp.value=cmdHistory[cmdHIdx]||"";}
    else if(e.key==="ArrowDown"){e.preventDefault();cmdHIdx=Math.max(-1,cmdHIdx-1);inp.value=cmdHIdx>=0?cmdHistory[cmdHIdx]:"";}
    else if(e.key==="Tab"){e.preventDefault();autocomplete(inp);}
  });
  document.getElementById("chatIn").addEventListener("keydown",e=>{
    if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();AP.sendChat();}
  });
  document.addEventListener("keydown",e=>{
    if(e.ctrlKey&&e.key==="l"){e.preventDefault();UI.clearLog();}
    if(e.key==="Escape"){selectedId=null;AP.close();UI.updateAgentList();}
    const ae=document.activeElement;
    const inInput=ae&&(ae.tagName==="INPUT"||ae.tagName==="TEXTAREA"||ae.isContentEditable);
    if(e.key==="/"&&!inInput){e.preventDefault();inp.focus();}
  });
}
function autocomplete(inp) {
  const parts=inp.value.split(" "); const pfx=parts[0].toLowerCase();
  if(parts.length===1){
    const m=scene.agents.find(a=>a.id.startsWith(pfx)); if(m){inp.value=m.id+" ";return;}
    const cmds=["status","history","reset","help","create","place","remove","all"];
    const c=cmds.find(x=>x.startsWith(pfx)); if(c) inp.value=c+" ";
  } else if(parts.length===2){
    const verbs=["move","stop","interact","speed","color","rename","delete"];
    const m=verbs.find(v=>v.startsWith(parts[1].toLowerCase())); if(m) inp.value=parts[0]+" "+m+" ";
  }
}

function initTools() {
  document.getElementById("toolGroup").addEventListener("click",e=>{
    const btn=e.target.closest("[data-tool]"); if(!btn) return;
    activeTool=btn.dataset.tool;
    document.querySelectorAll("#toolGroup .tool-btn").forEach(b=>b.classList.toggle("active",b===btn));
    canvas.style.cursor=activeTool==="drag"?"grab":"crosshair";
  });
}

// ════════════════════════════════════════════════════════════════════
//  BP — Bottom Task Chat Panel
// ════════════════════════════════════════════════════════════════════
var BP = (() => {
  let selectedAgents = [];
  let collapsed      = false;
  const CFG = { mcp_presets: [], agent_tools: [] };

  async function loadConfig() {
    try {
      const d = await fetch("/api/config").then(r => r.json());
      CFG.mcp_presets  = d.mcp_presets  || [];
      CFG.agent_tools  = d.agent_tools  || [];
    } catch(_) {}
  }

  function toggleCollapse() {
    collapsed = !collapsed;
    document.getElementById("bottomPanel").classList.toggle("collapsed", collapsed);
  }

  function renderChips() {
    const wrap = document.getElementById("bpAgentChips"); if(!wrap) return;
    wrap.innerHTML = "";
    for (const a of scene.agents) {
      const chip = document.createElement("div");
      chip.className = "bp-agent-chip" + (selectedAgents.includes(a.id) ? " active" : "");
      chip.style.color = a.color; chip.style.borderColor = a.color;
      chip.innerHTML = `<span class="chip-dot" style="background:${a.color}"></span>${a.name}`;
      chip.addEventListener("click", () => toggleAgent(a.id));
      wrap.appendChild(chip);
    }
    renderPills();
  }

  function renderPills() {
    const pills = document.getElementById("bpPills"); if(!pills) return;
    pills.innerHTML = "";
    for (const aid of selectedAgents) {
      const a = scene.agents.find(x => x.id === aid); if(!a) continue;
      const pill = document.createElement("div");
      pill.className = "bp-pill"; pill.style.color = a.color; pill.style.borderColor = a.color;
      const xBtn = document.createElement("button");
      xBtn.textContent = "×"; xBtn.addEventListener("click", () => removeAgent(aid));
      pill.append("/"+a.id+" ", xBtn);
      pills.appendChild(pill);
    }
  }

  function toggleAgent(id) {
    selectedAgents = selectedAgents.includes(id)
      ? selectedAgents.filter(x => x !== id)
      : [...selectedAgents, id];
    renderChips();
  }
  function removeAgent(id) {
    selectedAgents = selectedAgents.filter(x => x !== id);
    renderChips();
  }

  function findAgentByToken(token) {
    const t = token.toLowerCase();
    return scene.agents.find(a =>
      a.id.toLowerCase() === t || a.name.toLowerCase() === t
    );
  }

  function parseInput(text) {
    const agents = [];
    const clean  = text.replace(/\/(\S+)/g, (full, token) => {
      const a = findAgentByToken(token);
      if (a) {
        if (!agents.includes(a.id)) agents.push(a.id);
        return "";
      }
      return full;
    }).replace(/\s+/g, " ").trim();
    return { agents, message: clean };
  }

  function addMsg(role, content, agentId, ts) {
    const msgs = document.getElementById("bpMsgs"); if(!msgs) return;
    const welc = msgs.querySelector(".bp-welcome"); if(welc) welc.remove();
    const a = agentId ? scene.agents.find(x => x.id === agentId) : null;

    const wrap = document.createElement("div");
    wrap.className = "bp-msg " + role;

    if ((role === "assistant" || role === "agent") && a) {
      const hdr = document.createElement("div");
      hdr.className = "bp-msg-header";
      hdr.innerHTML = `<span class="bp-msg-dot" style="background:${a.color}"></span><span>${a.name}</span>`;
      wrap.appendChild(hdr);
    }
    const bub = document.createElement("div");
    bub.className = "bp-msg-bubble";
    bub.textContent = content;
    wrap.appendChild(bub);
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function addToolCall(agentId, toolName, input) {
    const msgs = document.getElementById("bpMsgs"); if(!msgs) return;
    const a = scene.agents.find(x => x.id === agentId);
    const div = document.createElement("div");
    div.className = "bp-tool-call";
    const inp = typeof input === "object" ? JSON.stringify(input) : String(input);
    div.innerHTML =
      `<span class="bp-tool-agent" style="color:${a?.color||'#888'}">${a?.name||agentId}</span>`
      + `<span class="bp-tool-icon">⚡</span>`
      + `<span class="bp-tool-name">${UI.esc(toolName)}</span>`
      + `<span class="bp-tool-input">${UI.esc(inp.slice(0, 140))}</span>`;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function addThought(agentId, content, ts) {
    const msgs = document.getElementById("bpMsgs"); if(!msgs) return;
    const a = scene.agents.find(x => x.id === agentId);
    const div = document.createElement("div");
    div.className = "bp-cot-thought";
    const label = document.createElement("div");
    label.className = "bp-cot-label";
    label.style.color = a?.color || "#888";
    label.textContent = (a?.name || agentId) + " thinking";
    const text = document.createElement("div");
    text.className = "bp-cot-text";
    text.textContent = content;
    div.append(label, text);
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function addObservation(agentId, toolName, content, ts) {
    const msgs = document.getElementById("bpMsgs"); if(!msgs) return;
    const div = document.createElement("div");
    div.className = "bp-cot-observation";
    const label = document.createElement("div");
    label.className = "bp-obs-label";
    label.textContent = toolName ? `⮐ ${toolName} result` : "⮐ result";
    const text = document.createElement("div");
    text.className = "bp-obs-text";
    text.textContent = content;
    div.append(label, text);
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }

  async function send() {
    const ta  = document.getElementById("bpInput"); if(!ta) return;
    const raw = ta.value.trim(); if(!raw) return;
    const { agents: inlineAgents, message } = parseInput(raw);
    const targets = [...new Set([...selectedAgents, ...inlineAgents])];
    const finalTargets = targets.length ? targets : scene.agents.map(a => a.id);
    if(!message) return;
    if(!finalTargets.length) { addMsg("system","No agents available.",null,Date.now()/1000); return; }
    ta.value = "";
    addMsg("user", raw, null, Date.now()/1000);
    document.getElementById("bpSend").classList.add("loading");
    try {
      const r = await fetch("/api/task", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ agents: finalTargets, message }),
      });
      const d = await r.json();
      if (!d.ok) addMsg("system","Error: "+(d.detail||"unknown"),null,Date.now()/1000);
    } catch(e) {
      addMsg("system","Network error: "+e.message,null,Date.now()/1000);
      document.getElementById("bpSend").classList.remove("loading");
    }
  }

  function expand() {
    if (collapsed) {
      collapsed = false;
      document.getElementById("bottomPanel").classList.remove("collapsed");
    }
  }

  function onWsEvent(msg) {
    if (msg.type === "task_thought") {
      expand();
      addThought(msg.agent_id, msg.content, msg.ts);
    } else if (msg.type === "task_observation") {
      addObservation(msg.agent_id, msg.tool, msg.content, msg.ts);
    } else if (msg.type === "task_msg") {
      expand();
      addMsg(msg.role === "assistant" ? "assistant" : msg.role, msg.content, msg.agent_id, msg.ts);
    } else if (msg.type === "task_tool") {
      addToolCall(msg.agent_id, msg.tool, msg.input);
    } else if (msg.type === "task_start") {
      expand();
      addMsg("system", "▶ Task started — agents: " + msg.agents.join(", "), null, msg.ts);
    } else if (msg.type === "task_done") {
      addMsg("system", "✓ Task complete.", null, msg.ts);
      document.getElementById("bpSend")?.classList.remove("loading");
    } else if (msg.type === "task_agent_start") {
      const a = scene.agents.find(x => x.id === msg.agent_id);
      if(a) addMsg("system", `${a.name} is working…`, null, msg.ts);
    }
  }

  function renderMcpPresets(agentId) {
    const cont = document.getElementById("mcpPresets"); if(!cont) return;
    cont.innerHTML = "";
    const agent = scene.agents.find(a => a.id === agentId);
    const existing = new Set((agent?.mcp_servers || []).map(s => s.id));
    for (const p of CFG.mcp_presets) {
      const btn = document.createElement("button");
      btn.className = "mcp-preset-btn" + (existing.has(p.id) ? " added" : "");
      btn.textContent = (existing.has(p.id) ? "✓ " : "+ ") + p.name;
      btn.title = p.description;
      btn.addEventListener("click", async () => {
        if (btn.classList.contains("added")) return;
        const ag = scene.agents.find(a => a.id === agentId); if(!ag) return;
        const servers = [...(ag.mcp_servers || []), { ...p, active: true }];
        await fetch(`/api/agents/${agentId}/config`, {
          method:"PUT", headers:{"Content-Type":"application/json"},
          body: JSON.stringify({ mcp_servers: servers }),
        });
        btn.classList.add("added"); btn.textContent = "✓ " + p.name;
      });
      cont.appendChild(btn);
    }
  }

  function renderTools(agentId) {
    const cont = document.getElementById("aiToolsList"); if(!cont) return;
    cont.innerHTML = "";
    const agent   = scene.agents.find(a => a.id === agentId);
    const enabled = new Set(agent?.ai_config?.enabled_tools || ["web_search","read_url","send_message_to_agent"]);
    for (const tool of CFG.agent_tools) {
      const item = document.createElement("div");
      item.className = "tool-item";
      const cb  = document.createElement("input");
      cb.type = "checkbox"; cb.id = "tool_"+tool.id; cb.checked = enabled.has(tool.id);
      cb.dataset.toolId = tool.id;
      const lbl = document.createElement("label");
      lbl.htmlFor = "tool_"+tool.id;
      lbl.innerHTML = `<span class="tool-name">${tool.name}</span><span class="tool-desc">${tool.description}</span>`;
      item.append(cb, lbl);
      cont.appendChild(item);
    }
  }

  function getEnabledTools() {
    return Array.from(document.querySelectorAll("#aiToolsList input[type=checkbox]"))
      .filter(cb => cb.checked).map(cb => cb.dataset.toolId);
  }

  // ── Autocomplete ────────────────────────────────────────────────
  let acActive = -1;

  function showAutocomplete(input, prefix) {
    removeAutocomplete();
    const matches = scene.agents.filter(a =>
      a.id.toLowerCase().startsWith(prefix) || a.name.toLowerCase().startsWith(prefix)
    );
    if (!matches.length) return;

    const box = document.createElement("div");
    box.id = "bpAC"; box.className = "bp-ac";
    matches.forEach((a, i) => {
      const item = document.createElement("div");
      item.className = "bp-ac-item";
      item.style.borderLeft = `3px solid ${a.color}`;
      item.innerHTML = `<span class="bp-ac-id">${a.id}</span><span class="bp-ac-name">${a.name}</span>`;
      item.addEventListener("mousedown", e => {
        e.preventDefault();
        insertAgent(input, a);
      });
      box.appendChild(item);
    });
    acActive = -1;
    input.parentElement.style.position = "relative";
    input.parentElement.appendChild(box);
  }

  function removeAutocomplete() {
    document.getElementById("bpAC")?.remove();
    acActive = -1;
  }

  function insertAgent(input, agent) {
    // Replace the current /token being typed with /id
    const val = input.value;
    const pos = input.selectionStart;
    const before = val.slice(0, pos);
    const after  = val.slice(pos);
    const slashIdx = before.lastIndexOf("/");
    const newBefore = before.slice(0, slashIdx) + "/" + agent.id + " ";
    input.value = newBefore + after;
    input.selectionStart = input.selectionEnd = newBefore.length;
    removeAutocomplete();
    input.focus();
  }

  function init() {
    document.getElementById("bpToggle").addEventListener("click", toggleCollapse);
    document.getElementById("bpSend").addEventListener("click", send);
    const ta = document.getElementById("bpInput");

    ta.addEventListener("keydown", e => {
      const ac = document.getElementById("bpAC");
      if (ac && (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Tab")) {
        e.preventDefault();
        const items = ac.querySelectorAll(".bp-ac-item");
        items[acActive]?.classList.remove("active");
        if (e.key === "ArrowDown" || e.key === "Tab") acActive = (acActive + 1) % items.length;
        else acActive = (acActive - 1 + items.length) % items.length;
        items[acActive]?.classList.add("active");
        return;
      }
      if (ac && e.key === "Enter") {
        const items = ac.querySelectorAll(".bp-ac-item");
        if (acActive >= 0 && items[acActive]) {
          e.preventDefault();
          items[acActive].dispatchEvent(new MouseEvent("mousedown"));
          return;
        }
      }
      if (ac && e.key === "Escape") { removeAutocomplete(); return; }
      if (e.key === "Enter" && !e.shiftKey && !ac) { e.preventDefault(); send(); }
    });

    ta.addEventListener("input", () => {
      const val = ta.value;
      const pos = ta.selectionStart;
      const before = val.slice(0, pos);
      const match  = before.match(/\/(\S*)$/);
      if (match) showAutocomplete(ta, match[1].toLowerCase());
      else removeAutocomplete();
    });

    ta.addEventListener("blur", () => setTimeout(removeAutocomplete, 150));
  }

  return { init, loadConfig, renderChips, onWsEvent,
           renderMcpPresets, renderTools, getEnabledTools,
           toggleAgent, removeAgent };
})();

// ════════════════════════════════════════════════════════════════════
//  Bootstrap
// ════════════════════════════════════════════════════════════════════
async function loadModels() {
  try {
    const r=await fetch("/api/models"); const d=await r.json();
    MODELS.claude=d.claude||[]; MODELS.openai=d.openai||[];
  } catch(_){}
}

// Expose modules to window so inline onclick="AP.open(...)" handlers work.
window.AP  = AP;
window.App = App;
window.UI  = UI;
window.Rec = Rec;
window.BP  = BP;

document.addEventListener("DOMContentLoaded", async ()=>{
  initCanvas(); initCanvasEvents(); initKeyboard(); initTools(); initLists();
  BP.init();
  await loadModels();
  await BP.loadConfig();
  WS.connect();
  fetch("/api/state").then(r=>r.json()).then(applyState).catch(()=>{});
  setTimeout(()=>{
    UI.addLog("system","Ready. Double-click an agent on the canvas to open its panel.",true);
  },500);
});
