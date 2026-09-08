/* Optional real Chromium checks. No product dependency; no installation. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
let chromium;
try { ({chromium} = require(process.env.PANEL_PLAYWRIGHT_MODULE || 'playwright')); }
catch { console.log('UNRUN: Playwright unavailable; set PANEL_PLAYWRIGHT_MODULE or install test tooling separately.'); process.exit(77); }
(async () => {
  let browser;
  try { browser = await chromium.launch({headless:true}); }
  catch (error) { console.log('UNRUN: Chromium unavailable: ' + error.message); process.exit(77); }
  try {
    const page = await browser.newPage({viewport:{width:1440,height:900}, reducedMotion:'reduce'});
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => { window.fixtureFetchCount=0; const original=window.fetch; window.fetch=(...args)=>{window.fixtureFetchCount++;return original(...args);}; });
    const html = fs.readFileSync(process.argv[2], 'utf8');
    await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);
    assert.equal(await page.evaluate(() => typeof window.Panel?.projectState), 'function', 'Panel public projection is missing');
    assert.match(await page.locator('#freshness').innerText(),/离线快照/,'Offline snapshot needs its own prominent freshness hint');
    assert.doesNotMatch(await page.locator('#freshness').innerText(),/状态未及时同步/);
    assert.match(await page.locator('#packet-meta').innerText(),/Main.*running/,'Registered Main status is absent');
    const result = await page.evaluate(() => {
      const s=JSON.parse(document.getElementById('panel-data').textContent), original=JSON.stringify(s);
      const p=Panel.projectState(s,Date.parse('2026-09-08T08:02:01Z'));
      const waiting=structuredClone(s); waiting.packet.lifecycle='waiting_user';
      const finished=structuredClone(s); finished.packet.lifecycle='finished';
      const reordered=structuredClone(s); reordered.tasks=Object.fromEntries(Object.entries(s.tasks).reverse());reordered.dependencies.reverse();reordered.stages=Object.fromEntries(Object.entries(s.stages).reverse());
      return {p,waiting:Panel.projectState(waiting,Date.parse('2026-09-08T09:00:00Z')).freshness,finished:Panel.projectState(finished,Date.parse('2026-09-08T09:00:00Z')).freshness,immutable:original===JSON.stringify(s),graph:Panel.layoutGraph(s),reordered:Panel.layoutGraph(reordered)};
    });
    assert.equal(result.p.counts.total,5);assert.equal(result.p.counts.done,1);assert.equal(result.p.counts.review,1);assert.equal(result.p.counts.active,1);assert.equal(result.p.counts.cancelled,1);
    assert.equal(result.p.counts.waiting,1);assert.equal(result.p.counts.pending,1);assert.equal(result.p.counts.blocked,0);assert.equal(result.p.counts.failed,0);
    const separated=await page.evaluate(()=>{const s=JSON.parse(document.getElementById('panel-data').textContent);s.tasks['DEMO-005'].status='blocked';s.tasks['DEMO-006'].status='failed';return Panel.projectState(s,Date.now()).counts;});
    assert.equal(separated.blocked,1);assert.equal(separated.failed,1);assert.equal(separated.pending,0);assert.equal(separated.total,6);
    assert.equal(result.p.freshness,'stale');assert.equal(result.waiting,'waiting_user');assert.equal(result.finished,'finished');assert.equal(result.immutable,true);
    assert.equal(result.p.activeSessions.length,3);assert.deepEqual(result.graph,result.reordered);
    assert.equal(result.graph.nodes.filter(n=>n.type==='task').length,6);assert(result.graph.nodes.some(n=>n.type==='gate'&&n.gateKind==='join'));assert(result.graph.nodes.some(n=>n.type==='gate'&&n.gateKind==='approval'));
    const nodeMap=new Map(result.graph.nodes.map(n=>[n.id,n]));
    for(const e of result.graph.edges){assert(nodeMap.get(e.from).rank<nodeMap.get(e.to).rank,'Edge must advance in the DAG');assert(nodeMap.get(e.from).y<nodeMap.get(e.to).y,'Default DAG must progress top to bottom');}
    assert(result.graph.edges.some(e=>nodeMap.get(e.from).stageId!==nodeMap.get(e.to).stageId),'Cross-stage dependency was dropped');
    const paths=await page.locator('#graph-content .edge').evaluateAll(nodes=>nodes.map(node=>node.getAttribute('d')));
    paths.forEach((d,index)=>{
      const edge=result.graph.edges[index],tokens=d.match(/[MHV]|-?\d+(?:\.\d+)?/g);let x=0,y=0;
      for(let i=0;i<tokens.length;){const command=tokens[i++];if(command==='M'){x=Number(tokens[i++]);y=Number(tokens[i++]);continue;}const next=Number(tokens[i++]),nx=command==='H'?next:x,ny=command==='V'?next:y;
        for(const node of result.graph.nodes.filter(n=>n.id!==edge.from&&n.id!==edge.to)){
          const crosses=command==='H'?y>node.y&&y<node.y+node.height&&Math.max(x,nx)>node.x&&Math.min(x,nx)<node.x+node.width:x>node.x&&x<node.x+node.width&&Math.max(y,ny)>node.y&&Math.min(y,ny)<node.y+node.height;
          assert(!crosses,'Graph edge '+edge.from+' → '+edge.to+' crosses unrelated node '+node.id);
        }x=nx;y=ny;
      }
    });
    assert.match(await page.locator('[data-node-id="gate:join:DEMO-004"]').getAttribute('aria-label'),/DEMO-003-REVIEW-A.*DEMO-003-REVIEW-B/);
    assert.match(await page.locator('[data-node-id="DEMO-003"] .node-roles').textContent(),/Reviewer 2/);
    await page.locator('#task-filter').selectOption('stage');
    assert(await page.locator('[data-node-id="DEMO-004"]').evaluate(node=>node.classList.contains('dimmed')));
    assert(!(await page.locator('[data-node-id="DEMO-003"]').evaluate(node=>node.classList.contains('dimmed'))));
    await page.locator('#task-filter').selectOption('all');
    await page.locator('[data-task-id="DEMO-002"]').first().focus(); await page.keyboard.press('Enter');
    assert.match(await page.locator('#task-detail').innerText(),/旧轮次.*失效/);
    await page.locator('#task-filter').selectOption('review');await page.locator('#zoom-in').click();
    const preserved=await page.evaluate(()=>{
      const graph=document.querySelector('#graph-content'),node=document.querySelector('[data-task-id="DEMO-002"]');
      const scroller=document.querySelector('#graph-scroll');scroller.scrollLeft=81;scroller.scrollTop=20;
      const s=JSON.parse(document.getElementById('panel-data').textContent);s.seq++;s.tasks['DEMO-002'].title='更新标题 <img src=x onerror=alert(1)>';Panel.renderState(s,Date.now());
      return {same:node===document.querySelector('[data-task-id="DEMO-002"]'),selected:document.querySelector('#task-detail').dataset.taskId,filter:document.querySelector('#task-filter').value,transform:graph.getAttribute('transform'),scroll:scroller.scrollLeft,unsafe:!!document.querySelector('#task-detail img')};
    });
    assert(preserved.same);assert.equal(preserved.selected,'DEMO-002');assert.equal(preserved.filter,'review');assert.match(preserved.transform,/1.2/);assert.equal(preserved.scroll,81);assert.equal(preserved.unsafe,false);
    assert(await page.locator('[data-node-id="DEMO-002"]').evaluate(node=>node.classList.contains('dimmed')));
    assert.equal(await page.locator('#graph-content .edge').count(),result.graph.edges.length,'Filtering removed real dependencies');
    const pan=await page.evaluate(()=>{
      const scroller=document.querySelector('#graph-scroll');
      // Dispatch pointer movement on the viewport after a real pointer capture below.
      return scroller.getBoundingClientRect().toJSON();
    });
    await page.mouse.move(pan.x+20,pan.y+15);await page.mouse.down();await page.mouse.move(pan.x+48,pan.y+35);await page.mouse.up();
    const panRetained=await page.evaluate(()=>{const node=document.querySelector('#graph-content'),before=node.getAttribute('transform'),s=JSON.parse(document.getElementById('panel-data').textContent);s.seq+=2;s.tasks['DEMO-002'].status='validating';Panel.renderState(s,Date.now());return {before,after:node.getAttribute('transform')};});
    assert.match(panRetained.before,/translate\(28 20\)/);assert.equal(panRetained.before,panRetained.after);
    assert.equal(await page.evaluate(async()=>{await Panel.refreshOnce();return window.fixtureFetchCount;}),0);
    await page.locator('#run-select').selectOption('1');assert.match(await page.locator('#history-label').innerText(),/历史/);
    assert.match(await page.locator('#task-detail').innerText(),/待开始/);
    await page.locator('#run-select').selectOption('current');
    const rejected=await page.evaluate(()=>{
      const s=JSON.parse(document.getElementById('panel-data').textContent);const cases=[{...s,schema_version:2},{...s,seq:0},{...s,seq:99,packet:{...s.packet,id:'OTHER'}},{...s,seq:99,packet:{...s.packet,run_number:1}}];
      return cases.map(s=>{try{Panel.renderState(s,Date.now());return false;}catch{return true;}});
    }); assert(rejected.every(Boolean));
    await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);
    await page.locator('[data-task-id="DEMO-002"]').first().click();
    const shots=process.env.PANEL_SCREENSHOT_DIR;
    if(shots){fs.mkdirSync(shots,{recursive:true});await page.screenshot({path:path.join(shots,'desktop.png'),fullPage:true});}
    await page.locator('#zoom-fit').click();
    assert(await page.evaluate(()=>{const graph=document.querySelector('#task-graph').getBoundingClientRect(),viewport=document.querySelector('#graph-scroll').getBoundingClientRect();return graph.width<=viewport.width&&graph.height<=viewport.height;}),'Fit-to-canvas left the graph outside the viewport');
    await page.locator('[data-node-id="gate:join:DEMO-004"]').click();
    assert.match(await page.locator('#task-detail').innerText(),/DEMO-003-REVIEW-A.*DEMO-003-REVIEW-B/s);
    if(shots)await page.screenshot({path:path.join(shots,'gates.png'),fullPage:true});
    await page.locator('#run-select').selectOption('1');
    if(shots)await page.screenshot({path:path.join(shots,'history.png'),fullPage:true});
    await page.locator('#run-select').selectOption('current');await page.locator('#zoom-reset').click();await page.locator('#task-list [data-task-id="DEMO-002"]').click();
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=390),'Mobile page overflows viewport');
    assert.equal(await page.locator('#task-list [data-task-id]').count(),6);
    if(shots) await page.screenshot({path:path.join(shots,'mobile.png'),fullPage:true});
    // Controlled HTTP envelope fixture, not Task 4 server acceptance.
    let calls=0, pending=0, peak=0, mode='ok';const requestTimes=[],responseTimes=[];
    const state=await page.evaluate(()=>JSON.parse(document.getElementById('panel-data').textContent));
    await page.route('http://panel.fixture/**',async route=>{
      if(new URL(route.request().url()).pathname!='/api/status') return route.fulfill({contentType:'text/html',body:html});
      calls++;requestTimes.push(Date.now());pending++;peak=Math.max(peak,pending);
      await new Promise(resolve=>setTimeout(resolve,40));pending--;responseTimes.push(Date.now());
      if(mode==='fail')return route.fulfill({status:503,body:'fixture unavailable'});
      if(mode==='timeout'){await new Promise(resolve=>setTimeout(resolve,5500));return route.abort();}
      return route.fulfill({contentType:'application/json',body:JSON.stringify({state,sync_error:mode==='source'?'模拟来源不可用':null})});
    });
    await page.goto('http://panel.fixture/');await page.waitForFunction(()=>document.querySelector('#connection').textContent.includes('已连接'));
    await page.waitForTimeout(2300);
    assert.equal(calls,2,'Expected one automatic poll after the initial response');
    assert(requestTimes[1]-responseTimes[0]>=1900,'Automatic poll did not wait for the prior response plus 2 seconds');
    const observed=await page.locator('#main-observed').innerText();
    await page.evaluate(()=>Promise.all([Panel.refreshOnce(),Panel.refreshOnce()]));assert.equal(peak,1);
    mode='source';await page.evaluate(()=>Panel.refreshOnce());assert.match(await page.locator('#sync-error').innerText(),/模拟来源不可用/);
    mode='fail';await page.evaluate(()=>Panel.refreshOnce().catch(()=>{}));assert.match(await page.locator('#connection').innerText(),/连接异常/);assert.equal(await page.locator('#main-observed').innerText(),observed);
    mode='timeout';const started=Date.now();await page.evaluate(()=>Panel.refreshOnce().catch(()=>{}));assert(Date.now()-started>=4800);assert.match(await page.locator('#connection').innerText(),/连接异常/);
    mode='ok';await page.evaluate(()=>Panel.refreshOnce());assert.match(await page.locator('#connection').innerText(),/已连接/);
    const sameNode=await page.evaluate(async()=>{const node=document.querySelector('#task-list button');await Panel.refreshOnce();return node===document.querySelector('#task-list button');});assert(sameNode);
    const tick=await page.evaluate(()=>{
      const s=JSON.parse(document.getElementById('panel-data').textContent);Panel.renderState(s,Date.parse('2026-09-08T08:02:00Z'));const before=document.querySelector('#freshness').textContent;Panel.renderState(s,Date.parse('2026-09-08T08:02:01Z'));return {before,after:document.querySelector('#freshness').textContent};
    });assert.match(tick.before,/Main 状态已核对/);assert.match(tick.after,/状态未及时同步/);
    assert.match(await page.locator('#active-sessions').innerText(),/121 秒前/,'Same-seq host observation ages must keep advancing');
    const fallback=await browser.newPage();
    await fallback.addInitScript(()=>{document.createElementNS=()=>{throw new Error('Simulated SVG unavailable');};});
    await fallback.goto(pathToFileURL(path.resolve(process.argv[2])).href);
    assert.match(await fallback.locator('#graph-error').innerText(),/图形暂不可用/);
    await fallback.locator('#task-list [data-task-id="DEMO-003"]').click();
    assert.match(await fallback.locator('#task-detail').innerText(),/DEMO-003-REVIEW-B/);await fallback.close();
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({status:'PASS',browser:browser.version(),viewports:['1440x900','390x844'],fixtureHttpCalls:calls,peakRequests:peak,checks:'separate counts, registered Main, role summaries, stale/waiting/finished, top-down deterministic DAG, obstacle-free fixture edges, gates, keyboard, selection/filter/current-stage/zoom/fit/pan/scroll, literal text, offline no fetch, history, rollback rejection, mobile width, SVG-unavailable fallback, 2s polling, same-seq time updates, HTTP errors/timeout/recovery'}));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
