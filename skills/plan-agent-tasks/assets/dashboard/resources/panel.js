(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const labels = Object.freeze({pending:'待开始',ready:'就绪',implementing:'实施中',fixing:'返修中',validating:'验证中',awaiting_review:'等待审查',reviewing:'审查中',waiting_approval:'等待批准',blocked:'阻塞',failed:'失败',done:'已完成',cancelled:'已取消'});
  const groups = {active:['implementing','fixing','validating'],review:['awaiting_review','reviewing'],waiting:['waiting_approval'],pending:['pending','ready'],blocked:['blocked'],failed:['failed'],done:['done'],cancelled:['cancelled']};
  const ui = {selected:null,filter:'all',zoom:1,panX:0,panY:0,run:'current',topology:null};
  let current = null, displayed = null, graph = null, inFlight = null, lastServiceRead = null;
  const byId = id => document.getElementById(id);
  const sorted = object => Object.keys(object).sort();
  const time = value => value || '尚未观察';
  const age = (value, now) => value ? Math.max(0, Math.floor((now-Date.parse(value))/1000)) : null;
  function projectState(state, nowMs) {
    const tasks=Object.values(state.tasks), counts={total:tasks.filter(t=>t.status!=='cancelled').length};
    Object.entries(groups).forEach(([name,statuses])=>{counts[name]=tasks.filter(t=>statuses.includes(t.status)).length;});
    const delta=age(state.observed_at,nowMs);
    const lifecycle=state.packet.lifecycle;
    const freshness=lifecycle==='waiting_user'?'waiting_user':lifecycle==='finished'?'finished':lifecycle==='planned'?'planned':delta===null?'unknown':delta>120?'stale':'fresh';
    const activeSessions=sorted(state.sessions).filter(id=>state.sessions[id].host_status==='running'&&state.sessions[id].observed_at!==null).map(id=>({id,...state.sessions[id],ageSeconds:age(state.sessions[id].observed_at,nowMs),currentRound:state.sessions[id].round===state.tasks[state.sessions[id].task_id].round}));
    return {counts,activeSessions,freshness,ageSeconds:delta,labels:{...labels}};
  }
  function checkLabel(state,id) {
    const c=state.checks[id],task=state.tasks[c.task_id];
    if(!c.applicable) return id+'：不适用（'+c.not_applicable_reason+'）';
    const obsolete=c.round!==task.round;
    return id+'：'+c.result+' · 第 '+c.round+' 轮'+(obsolete?' · 旧轮次，失效':' · 当前轮次')+(c.result==='PASS'&&!c.evidence_ids.length?' · 缺少证据':'');
  }
  function dependencyLabel(state,dep) {
    return dep.required_check_ids.length?dep.required_check_ids.map(id=>checkLabel(state,id)).join('；'):dep.from+' 必须已完成（当前：'+labels[state.tasks[dep.from].status]+'）';
  }
  function layoutGraph(state) {
    const stageIds=sorted(state.stages), taskIds=sorted(state.tasks), nodes=[],edges=[];
    const dependencies=[...state.dependencies].sort((a,b)=>(a.from+'\0'+a.to).localeCompare(b.from+'\0'+b.to));
    taskIds.forEach(id=>nodes.push({id,type:'task',stageId:state.tasks[id].stage_id,taskId:id}));
    const joins=new Map();
    taskIds.forEach(id=>{
      const incoming=dependencies.filter(d=>d.to===id);
      if(incoming.length>1){const gateId='gate:join:'+id;joins.set(id,gateId);nodes.push({id:gateId,type:'gate',gateKind:'join',stageId:state.tasks[id].stage_id,taskId:id,conditionIds:incoming.map(d=>d.from)});edges.push({from:gateId,to:id,kind:'all',requiredCheckIds:[]});}
    });
    dependencies.forEach(dep=>edges.push({from:dep.from,to:joins.get(dep.to)||dep.to,kind:'dependency',targetTask:dep.to,requiredCheckIds:[...dep.required_check_ids].sort()}));
    stageIds.forEach(stageId=>{
      const entries=taskIds.filter(id=>state.tasks[id].stage_id===stageId&&!dependencies.some(d=>d.to===id&&state.tasks[d.from].stage_id===stageId));
      if(!entries.length)return;
      const gateId='gate:approval:'+stageId;nodes.push({id:gateId,type:'gate',gateKind:'approval',stageId,taskId:entries[0],conditionIds:[stageId]});
      entries.forEach(id=>edges.push({from:gateId,to:id,kind:'approval',requiredCheckIds:[]}));
    });
    const nodeMap=new Map(nodes.map(n=>[n.id,n])),remaining=new Set(nodeMap.keys()),ranks=new Map();
    while(remaining.size){
      const ready=[...remaining].filter(id=>edges.filter(e=>e.to===id).every(e=>ranks.has(e.from))).sort();
      if(!ready.length)throw new Error('依赖图存在环或缺失前置任务');
      ready.forEach(id=>{const incoming=edges.filter(e=>e.to===id);ranks.set(id,incoming.length?Math.max(...incoming.map(e=>ranks.get(e.from)))+1:0);remaining.delete(id);});
    }
    const stageOrder=[...stageIds,...(nodes.some(n=>n.stageId===null)?[null]:[])],stageBounds=[];
    let left=24;
    stageOrder.forEach(stageId=>{
      const members=nodes.filter(n=>n.stageId===stageId),rankGroups=new Map();
      members.forEach(n=>{n.rank=ranks.get(n.id);if(!rankGroups.has(n.rank))rankGroups.set(n.rank,[]);rankGroups.get(n.rank).push(n);});
      rankGroups.forEach(group=>group.sort((a,b)=>a.id.localeCompare(b.id)).forEach((n,i)=>{n.x=left+30+i*240;n.y=60+n.rank*195;n.width=208;n.height=142;}));
      const width=50+Math.max(1,...[...rankGroups.values()].map(g=>g.length))*240;
      stageBounds.push({id:stageId,x:left,y:16,width,height:0});left+=width+22;
    });
    nodes.sort((a,b)=>a.id.localeCompare(b.id));edges.sort((a,b)=>(a.from+'\0'+a.to).localeCompare(b.from+'\0'+b.to));
    const width=left+12,height=Math.max(320,...nodes.map(n=>n.y+n.height+32));stageBounds.forEach(b=>{b.height=height-32;});
    return {nodes,edges,stageBounds,width,height};
  }
  function el(tag,text,cls) {const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
  function svg(tag,attrs={},text) {const node=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([key,value])=>node.setAttribute(key,String(value)));if(text!==undefined)node.textContent=text;return node;}
  function clear(node) {node.replaceChildren();}
  function matches(task) {return ui.filter==='all'||(ui.filter==='stage'?task.stage_id===displayed.packet.stage_id:groups[ui.filter].includes(task.status));}
  function topology(state) {return JSON.stringify([state.packet.run_number,state.packet.plan_revision,sorted(state.tasks).map(id=>[id,state.tasks[id].stage_id]),sorted(state.stages).map(id=>[id,[...state.stages[id].task_ids].sort()]),[...state.dependencies].map(d=>[d.from,d.to,[...d.required_check_ids].sort()]).sort()]);}
  function graphTransform() {byId('graph-content').setAttribute('transform',`translate(${ui.panX} ${ui.panY}) scale(${ui.zoom})`);if(graph){byId('task-graph').setAttribute('width',Math.max(graph.width*ui.zoom+Math.max(0,ui.panX),300));byId('task-graph').setAttribute('height',graph.height*ui.zoom+Math.max(0,ui.panY));}byId('zoom-level').textContent=Math.round(ui.zoom*100)+'%';}
  function selectTask(id) {ui.selected=id;updateGraph(displayed);renderDetails(displayed);updateListSelection();}
  function bindSelection(node,id) {node.addEventListener('click',()=>selectTask(id));node.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();selectTask(id);}});}
  function buildGraph(state) {
    graph=layoutGraph(state);const container=byId('graph-content');clear(container);
    const defs=svg('defs'),marker=svg('marker',{id:'arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'});marker.append(svg('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#879bb5'}));defs.append(marker);container.append(defs);
    graph.stageBounds.forEach(b=>{container.append(svg('rect',{x:b.x,y:b.y,width:b.width,height:b.height,rx:10,class:'stage-bound'}));container.append(svg('text',{x:b.x+16,y:b.y+23,class:'stage-label','data-stage-label':b.id||''}));});
    const map=new Map(graph.nodes.map(n=>[n.id,n]));
    graph.edges.forEach((edge,index)=>{
      const a=map.get(edge.from),b=map.get(edge.to),x1=a.x+a.width/2,y1=a.y+a.height,x2=b.x+b.width/2,y2=b.y,middle=y1+(y2-y1)/2;
      const corridor=graph.stageBounds.find(bound=>bound.id===b.stageId).x+12;
      const longEdge=b.rank-a.rank>1;
      const route=longEdge?`M ${x1} ${y1} V ${y1+12} H ${corridor} V ${y2-12} H ${x2} V ${y2}`:`M ${x1} ${y1} V ${middle} H ${x2} V ${y2}`;
      const line=svg('path',{d:route,class:'edge','marker-end':'url(#arrow)'});line.append(svg('title',{},''));container.append(line);
      const label=svg('text',{x:longEdge?corridor+4:Math.min(x1,x2)+4,y:longEdge?y2-20:middle-5,class:'edge-label','data-edge-index':index});container.append(label);
    });
    graph.nodes.forEach(n=>{
      const node=svg('g',{transform:`translate(${n.x} ${n.y})`,class:n.type==='task'?'task-node':'gate','data-node-id':n.id,tabindex:0,role:'button'});
      node.append(svg('title'));
      if(n.type==='task'){
        node.setAttribute('data-task-id',n.taskId);node.append(svg('rect',{width:n.width,height:n.height,rx:8}));node.append(svg('text',{x:13,y:21,class:'node-id'}));node.append(svg('text',{x:13,y:43,class:'node-title'}));node.append(svg('text',{x:13,y:107,class:'node-status'}));node.append(svg('text',{x:13,y:126,class:'node-roles'}));
      }else{node.append(svg('polygon',{points:'104,4 205,71 104,138 3,71'}));node.append(svg('text',{x:104,y:55,'text-anchor':'middle',class:'gate-title'}));node.append(svg('text',{x:104,y:73,'text-anchor':'middle',class:'gate-state'}));node.append(svg('text',{x:104,y:91,'text-anchor':'middle'},'选择查看全部条件'));}
      bindSelection(node,n.taskId);container.append(node);
    });graphTransform();
  }
  function updateGraph(state) {
    if(!graph)return;
    byId('graph-content').querySelectorAll('[data-stage-label]').forEach(node=>{const id=node.getAttribute('data-stage-label');node.textContent=id?id+' / '+state.stages[id].title:'未分阶段';});
    graph.nodes.forEach(n=>{
      const node=[...byId('graph-content').querySelectorAll('[data-node-id]')].find(item=>item.getAttribute('data-node-id')===n.id),task=state.tasks[n.taskId];if(!node)return;
      if(n.type==='task'){
        node.setAttribute('data-status',task.status);node.classList.toggle('selected',ui.selected===n.taskId);node.classList.toggle('dimmed',!matches(task));node.setAttribute('aria-pressed',String(ui.selected===n.taskId));node.setAttribute('aria-label',n.taskId+' '+task.title+' '+labels[task.status]);
        node.querySelector('title').textContent=task.title;node.querySelector('.node-id').textContent=n.taskId+' · 第 '+task.round+' 轮';
        const title=node.querySelector('.node-title');clear(title);const chars=Array.from(task.title);for(let i=0;i<3&&i*14<chars.length;i++)title.append(svg('tspan',{x:13,dy:i?17:0},chars.slice(i*14,(i+1)*14).join('')+(i===2&&chars.length>42?'…':'')));
        node.querySelector('.node-status').textContent=labels[task.status];
        const observed=task.session_ids.map(id=>state.sessions[id]).filter(session=>session.round===task.round&&session.host_status==='running'&&session.observed_at!==null),workers=observed.filter(session=>session.role==='worker').length,reviewers=observed.filter(session=>session.role==='reviewer').length;
        node.querySelector('.node-roles').textContent=observed.length?'Worker '+workers+' · Reviewer '+reviewers+' running':'当前轮：暂无 running 观察';
      }else{
        const approval=n.gateKind==='approval';const conditions=approval?n.stageId+' 阶段批准：'+(state.stages[n.stageId].approved?'已批准，证据 '+state.stages[n.stageId].approval_evidence_ids.join('、'):'等待批准，未授予执行权限'):state.dependencies.filter(d=>d.to===n.taskId).map(d=>dependencyLabel(state,d)).join('；');
        node.querySelector('.gate-title').textContent=approval?n.stageId+' 阶段批准':'全部前置条件';node.querySelector('.gate-state').textContent=approval?(state.stages[n.stageId].approved?'已批准 · 有证据':'等待批准'):n.conditionIds.join(' + ');node.querySelector('title').textContent=conditions;node.setAttribute('aria-label',conditions);
      }
    });
    byId('graph-content').querySelectorAll('[data-edge-index]').forEach(node=>{const e=graph.edges[Number(node.getAttribute('data-edge-index'))];node.textContent=e.kind==='approval'?'阶段批准':e.kind==='all'?'全部满足':e.requiredCheckIds.length?'当前轮检查 + 证据':'已完成';const path=node.previousSibling;path.querySelector('title').textContent=e.kind==='dependency'?dependencyLabel(state,{from:e.from,required_check_ids:e.requiredCheckIds}):node.textContent;});
  }
  function referenceText(reference) {return reference.url||reference.repository+' / '+reference.path;}
  function evidenceNode(state,id) {const evidence=state.evidence[id];const node=el('div',undefined,'muted');if(!evidence){node.textContent=id+' · 未找到证据';return node;}node.append(el('span',evidence.title+' · '));if(evidence.reference.url&&/^https?:\/\//i.test(evidence.reference.url)){const link=el('a',evidence.reference.url);link.href=evidence.reference.url;link.target='_blank';link.rel='noopener noreferrer';node.append(link);}else node.append(el('span',referenceText(evidence.reference)));return node;}
  function section(parent,title){const node=el('section',undefined,'detail-section');node.append(el('h3',title));parent.append(node);return node;}
  function renderDetails(state) {
    const container=byId('task-detail'),scroll=byId('task-detail').parentElement.scrollTop;clear(container);const task=state.tasks[ui.selected];container.dataset.taskId=task?ui.selected:'';
    if(!task){container.append(el('p','从流程图或任务列表选择一个任务。','muted'));return;}
    container.append(el('div',task.id+' · 第 '+task.round+' 轮','muted'),el('h3',task.title),el('span',labels[task.status],'badge'),el('p',task.progress),el('div','进展来源时间：'+time(task.progress_at),'muted'));
    if(task.blocker)container.append(el('p','阻塞原因：'+task.blocker));container.append(el('p','下一步：'+task.next_action));
    const checks=section(container,'完成要求 · 各维度分别核对');task.required_check_ids.forEach(id=>{const c=state.checks[id],row=el('div',undefined,'detail-row'+(c.applicable&&c.round!==task.round?' check-old':''));row.append(el('strong',checkLabel(state,id)),el('div',c.kind+' · '+c.role_id,'muted'));c.evidence_ids.forEach(eid=>row.append(evidenceNode(state,eid)));checks.append(row);});
    const conditions=section(container,'前置依赖与阶段门禁');const incoming=state.dependencies.filter(d=>d.to===task.id);if(!incoming.length)conditions.append(el('p','无任务前置依赖','muted'));incoming.forEach(dep=>conditions.append(el('div',dependencyLabel(state,dep),'detail-row')));
    if(task.stage_id){const stage=state.stages[task.stage_id];conditions.append(el('div',task.stage_id+' '+stage.title+'：'+(stage.approved?'已批准':'等待批准，未授予执行权限'),'detail-row'));stage.approval_evidence_ids.forEach(id=>conditions.append(evidenceNode(state,id)));}
    const sessions=section(container,'角色与会话 · 包含返修轮次');task.session_ids.forEach(id=>{const s=state.sessions[id],row=el('div',undefined,'detail-row');row.append(el('strong',(s.role==='reviewer'?'Reviewer':'Worker')+' · '+(s.actual_name||s.planned_name)),el('div','逻辑角色：'+id+' · 第 '+s.round+' 轮'+(s.round!==task.round?'（旧轮次）':''),'muted'),el('div','实际会话：'+(s.actual_id||'未知，尚未观察')+' · 宿主：'+s.host_status),el('div','观察时间：'+time(s.observed_at),'muted'),el('div','计划模型：'+modelText(s.planned_model),'muted'),el('div','实际模型：'+modelText(s.actual_model),'muted'));if(s.replaces)row.append(el('div','替代角色：'+s.replaces,'muted'));sessions.append(row);});
    container.parentElement.scrollTop=scroll;
  }
  function modelText(model){return model?Object.values(model).map(value=>value||'未知').join(' / '):'未知，尚未观察';}
  function updateListSelection(){byId('task-list').querySelectorAll('[data-task-id]').forEach(node=>node.setAttribute('aria-pressed',String(node.dataset.taskId===ui.selected)));}
  function renderLists(state,projection) {
    const active=byId('active-sessions');clear(active);
    projection.activeSessions.forEach(s=>{const row=el('div',undefined,'active-row'),info=el('div'),button=el('button',s.actual_name||s.planned_name);button.addEventListener('click',()=>selectTask(s.task_id));info.append(button,el('span',(s.role==='reviewer'?'Reviewer':'Worker')+' · 第 '+s.round+' 轮'+(!s.currentRound?' · 旧轮次':'')+' · 宿主 running','muted'));const timestamp=el('div',undefined,'muted');timestamp.dataset.sessionAge=s.id;row.append(info,timestamp);active.append(row);});if(!projection.activeSessions.length)active.append(el('p','没有带来源时间的 running 会话观察。','muted'));
    const list=byId('task-list');clear(list);sorted(state.tasks).forEach(id=>{const task=state.tasks[id],button=el('button',undefined,'task-list-row');button.dataset.taskId=id;button.append(el('span',id),el('span',task.title),el('span',labels[task.status]));button.addEventListener('click',()=>selectTask(id));list.append(button);});updateListSelection();
    const events=byId('events'),scroll=events.scrollTop;clear(events);[...state.events].reverse().slice(0,30).forEach(event=>{const row=el('li'),meta=el('div','#'+event.seq,'muted'),body=el('div',event.summary);body.append(el('div','来源 '+event.occurred_at+' · 接收 '+event.received_at,'muted'));row.append(meta,body);events.append(row);});if(!state.events.length)events.append(el('li','本轮尚无事件。','muted'));events.scrollTop=scroll;
  }
  function freshness(state,nowMs) {
    const p=projectState(state,nowMs),delta=p.ageSeconds===null?'未获得核对时间':p.ageSeconds+' 秒前';
    const names={stale:'状态未及时同步',fresh:'Main 状态已核对',unknown:'Main 核对时间未知',waiting_user:'等待用户决定',finished:'执行已结束 · 保留快照',planned:'计划尚未执行'};
    const snapshot=ui.run!=='current'?'历史快照':location.protocol==='file:'?'离线快照':null;
    byId('freshness').textContent=snapshot?snapshot+' · Main 核对记录 · '+delta:names[p.freshness]+' · '+delta;byId('freshness').className=!snapshot&&p.freshness==='stale'?'badge stale':'';byId('main-observed').textContent='Main 最近核对：'+time(state.observed_at)+' · 快照生成：'+time(state.generated_at);byId('service-read').textContent='最近读服务：'+(lastServiceRead||'尚未读取');
    byId('active-sessions').querySelectorAll('[data-session-age]').forEach(node=>{const session=state.sessions[node.dataset.sessionAge],seconds=age(session.observed_at,nowMs);node.textContent=time(session.observed_at)+' · '+seconds+' 秒前'+(seconds>120?'（观察已过期）':'');});
  }
  function validateIncoming(state) {
    if(!state||state.schema_version!==1||!state.packet||!Number.isInteger(state.packet.run_number)||state.packet.run_number<1||!Number.isInteger(state.seq)||state.seq<0||!state.tasks||!state.sessions||!state.stages||!state.checks||!state.evidence||!Array.isArray(state.dependencies)||!Array.isArray(state.events)||!Array.isArray(state.history))throw new Error('状态格式不受支持');
    if(current&&(state.packet.id!==current.packet.id||state.packet.run_number<current.packet.run_number||state.seq<current.seq||state.packet.plan_revision<1||(state.packet.run_number===current.packet.run_number&&state.packet.plan_revision<current.packet.plan_revision)))throw new Error('拒绝串包或倒退的状态');
  }
  function displayState(nowMs) {
    const state=ui.run==='current'?current:current.history.find(s=>String(s.packet.run_number)===ui.run);if(!state){ui.run='current';return displayState(nowMs);}displayed=state;
    if(ui.selected&&!state.tasks[ui.selected])ui.selected=null;
    const p=projectState(state,nowMs);byId('packet-title').textContent=state.packet.title;document.title=state.packet.title+' · 任务进展';byId('packet-meta').textContent=state.packet.id+' · '+state.packet.mode+' · Main '+state.main.status+' · Run '+state.packet.run_number+' · Plan '+state.packet.plan_revision+' · seq '+state.seq+' · 当前阶段 '+(state.packet.stage_id?state.packet.stage_id+' '+state.stages[state.packet.stage_id].title:'未指定');
    byId('history-label').textContent=ui.run==='current'?'当前轮次':'历史轮次 · 只读快照';const counts=byId('counts');clear(counts);[['done','已完成 / 有效任务'],['active','实施 / 返修 / 验证'],['review','独立审查'],['waiting','等待确认 / 批准'],['blocked','受阻'],['pending','未开始 / 就绪'],...(p.counts.failed?[['failed','失败']]:[]),...(p.counts.cancelled?[['cancelled','已取消 · 不计分母']]:[])].forEach(([key,label])=>{const node=el('div',undefined,'count');node.append(el('strong',key==='done'?p.counts.done+' / '+p.counts.total:String(p.counts[key])),el('span',label));counts.append(node);});
    const key=topology(state);try{if(key!==ui.topology){buildGraph(state);ui.topology=key;}updateGraph(state);byId('graph-error').textContent='';}catch(error){byId('graph-error').textContent='图形暂不可用，请使用下方全部任务列表。'+error.message;}
    renderLists(state,p);renderDetails(state);freshness(state,nowMs);byId('source-reference').textContent='来源：'+referenceText(state.source.reference)+' · '+(state.source.available?'可用':'不可用')+' · 核对 '+time(state.source.checked_at);
  }
  function renderState(state,nowMs=Date.now()) {
    validateIncoming(state);
    if(current&&state.seq===current.seq){if(state.packet.run_number!==current.packet.run_number)throw new Error('相同序号不能改变执行轮次');freshness(displayed,nowMs);return false;}
    current=JSON.parse(JSON.stringify(state));const selector=byId('run-select');clear(selector);selector.append(new Option('当前 · 第 '+current.packet.run_number+' 轮','current'));[...current.history].reverse().forEach(item=>selector.append(new Option('历史 · 第 '+item.packet.run_number+' 轮',String(item.packet.run_number))));if(ui.run!=='current'&&!current.history.some(item=>String(item.packet.run_number)===ui.run))ui.run='current';selector.value=ui.run;
    const scroller=byId('graph-scroll'),left=scroller.scrollLeft,top=scroller.scrollTop;displayState(nowMs);scroller.scrollLeft=left;scroller.scrollTop=top;return true;
  }
  function refreshOnce() {
    if(location.protocol==='file:')return Promise.resolve(false);
    if(inFlight)return inFlight;
    inFlight=(async()=>{
      const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),5000);
      try{
        const response=await fetch('api/status',{cache:'no-store',signal:controller.signal});if(!response.ok)throw new Error('Preview HTTP '+response.status);const envelope=await response.json();if(!envelope||!envelope.state||!(envelope.sync_error===null||typeof envelope.sync_error==='string'))throw new Error('无效状态响应');
        renderState(envelope.state,Date.now());lastServiceRead=new Date().toISOString();byId('connection').textContent='实时预览 · 已连接';byId('sync-error').textContent=envelope.sync_error||'';freshness(displayed,Date.now());return true;
      }catch(error){byId('connection').textContent='实时预览 · 连接异常';byId('sync-error').textContent=error.name==='AbortError'?'请求超过 5 秒，保留最近有效数据。':error.message;throw error;}
      finally{clearTimeout(timeout);inFlight=null;}
    })();return inFlight;
  }
  async function poll(){try{await refreshOnce();}catch{/* Connection UI already retains the last valid state. */}setTimeout(poll,2000);}
  window.Panel=Object.freeze({projectState,layoutGraph,renderState,refreshOnce});
  byId('task-filter').addEventListener('change',event=>{ui.filter=event.target.value;updateGraph(displayed);});
  byId('run-select').addEventListener('change',event=>{ui.run=event.target.value;displayState(Date.now());});
  byId('zoom-in').addEventListener('click',()=>{ui.zoom=Math.min(2.4,Math.round((ui.zoom+.2)*10)/10);graphTransform();});byId('zoom-out').addEventListener('click',()=>{ui.zoom=Math.max(.1,Math.round((ui.zoom-.2)*10)/10);graphTransform();});byId('zoom-reset').addEventListener('click',()=>{ui.zoom=1;ui.panX=0;ui.panY=0;graphTransform();byId('graph-scroll').scrollTo(0,0);});
  byId('zoom-fit').addEventListener('click',()=>{if(!graph)return;const viewport=byId('graph-scroll');ui.zoom=Math.max(.1,Math.min(1,(viewport.clientWidth-12)/graph.width,(viewport.clientHeight-12)/graph.height));ui.panX=0;ui.panY=0;graphTransform();viewport.scrollTo(0,0);});
  let drag=null;const scroller=byId('graph-scroll');scroller.addEventListener('pointerdown',event=>{if(event.pointerType!=='mouse'||event.button!==0||event.target.closest('[role="button"]'))return;drag={x:event.clientX,y:event.clientY,panX:ui.panX,panY:ui.panY};scroller.setPointerCapture(event.pointerId);});scroller.addEventListener('pointermove',event=>{if(!drag)return;ui.panX=drag.panX+event.clientX-drag.x;ui.panY=drag.panY+event.clientY-drag.y;graphTransform();});['pointerup','pointercancel'].forEach(type=>scroller.addEventListener(type,()=>{drag=null;}));
  try{renderState(JSON.parse(byId('panel-data').textContent),Date.now());byId('connection').textContent=location.protocol==='file:'?'离线快照 · 不请求服务':'实时预览 · 正在连接';if(location.protocol==='http:'||location.protocol==='https:')poll();setInterval(()=>{if(displayed)freshness(displayed,Date.now());},1000);}catch(error){byId('sync-error').textContent='无法显示状态：'+error.message;}
})();
