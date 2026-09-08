/* Bounded real-CLI/browser acceptance with synthetic events, never real roles.
 * Usage: node tests/panel_acceptance.cjs <fresh scratch directory>
 * PANEL_PYTHON and PANEL_PLAYWRIGHT_MODULE select existing tools; no installation.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {pathToFileURL} = require('node:url');
const root = path.resolve(__dirname, '..');
const scratch = path.resolve(process.argv[2] || '');
assert(process.argv[2] && !fs.existsSync(scratch), 'Provide a fresh scratch directory');
const python = process.env.PANEL_PYTHON || path.join(root, '.venv/Scripts/python.exe');
let chromium;
try { ({chromium} = require(process.env.PANEL_PLAYWRIGHT_MODULE || 'playwright')); }
catch { console.log('UNRUN: existing Playwright required'); process.exit(77); }
const log = [], services = [];
const now = () => new Date().toISOString();
const write = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2), 'utf8');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const stateFile = packet => path.join(packet, 'runtime/state.json');
function cli(packet, command, args = [], expected = 0) {
  const began = now();
  const result = spawnSync(python, [path.join(packet, 'dashboard/panel.py'), command, ...args],
    {cwd:scratch, encoding:'utf8', windowsHide:true, timeout:20000});
  const acknowledged = now();
  assert.equal(result.status, expected, command + ': ' + result.stderr + result.stdout);
  const value = JSON.parse(result.stdout);
  log.push({type:'cli', packet:path.basename(packet), command, began, acknowledged, exit:result.status, value});
  return {value, acknowledged};
}
function copyBundle(packet) {
  fs.mkdirSync(packet, {recursive:true});
  fs.cpSync(path.join(root, 'skills/plan-agent-tasks/assets/dashboard'), path.join(packet, 'dashboard'), {recursive:true});
}
function prepare(id) {
  const packet = path.join(scratch, id); copyBundle(packet);
  const plan = read(path.join(root, 'skills/plan-agent-tasks/examples/progress-panel/plan.json'));
  plan.packet = {...plan.packet, id, title:'模拟 Fixture · ' + id, stage_id:null};
  plan.main.logical_id=id+'-MAIN';
  plan.source.reference.path='docs/task-packets/'+id+'/runtime/state.json';
  plan.tasks=Object.fromEntries(Object.entries(plan.tasks).filter(([id])=>id==='DEMO-001'));
  plan.tasks['DEMO-001'].stage_id=null;
  plan.sessions=Object.fromEntries(Object.entries(plan.sessions).filter(([,s])=>s.task_id==='DEMO-001'));
  plan.checks=Object.fromEntries(Object.entries(plan.checks).filter(([,s])=>s.task_id==='DEMO-001'));
  plan.stages={};plan.dependencies=[];
  write(path.join(packet,'plan.json'),plan);cli(packet,'init',['--input',path.join(packet,'plan.json')]);
  return packet;
}
function publish(packet, name, ops, observed=now(), expected=0) {
  const state=read(stateFile(packet));
  const event={event_id:'SIM-'+name, expected_seq:state.seq, occurred_at:observed, observed_at:observed, summary:'模拟：'+name, ops};
  const file=path.join(packet,'event-'+name+'.json');write(file,event);
  return {...cli(packet,'publish',['--input',file],expected), event, file};
}
const task = (status, extra={}) => ({type:'task.set',id:'DEMO-001',changes:{status,progress:'模拟：'+status,...extra}});
const main = status => ({type:'main.set',changes:{status,session_id:'SIMULATED-MAIN'}});
const role = (suffix,status,round=1) => ({type:'session.set',id:'DEMO-001-'+suffix,changes:{host_status:status,round,actual_id:'SIMULATED-'+suffix,actual_name:'模拟 '+suffix}});
const check = (suffix,result,round) => ({type:'check.set',id:'DEMO-001-'+suffix,changes:{result,round,evidence_ids:['SIM-EVIDENCE-'+suffix+'-'+round]}});
function evidence(packet,suffix,round) {
  const id='SIM-EVIDENCE-'+suffix+'-'+round, relative='reports/'+id+'.md';
  fs.mkdirSync(path.join(packet,'reports'),{recursive:true});fs.writeFileSync(path.join(packet,relative),'模拟证据；没有真实角色执行。\n<script>not executable</script>\n');
  return {type:'evidence.put',id,evidence:{title:'模拟 '+suffix+' 第 '+round+' 轮',reference:{repository:'simulated-demo',path:'docs/task-packets/'+path.basename(packet)+'/'+relative}}};
}
async function visible(page,packet,published) {
  const seq=published.value.seq;
  await page.waitForFunction(seq=>document.querySelector('#packet-meta').textContent.includes(' · seq '+seq+' ·'),seq,{timeout:5000,polling:50});
  const firstVisible=now(),state=read(stateFile(packet));
  const text=await page.locator('#task-detail').innerText();
  const entry={type:'visible',seq,source:state.observed_at,published:published.acknowledged,firstVisible,latencyMs:Date.parse(firstVisible)-Date.parse(published.acknowledged),text};
  log.push(entry);assert(entry.latencyMs<=5000);return entry;
}
async function closed(url) {
  await assert.rejects(fetch(url+'api/identity',{signal:AbortSignal.timeout(2000)}));
}
(async()=>{
  let browser;
  try { browser=await chromium.launch({headless:true}); }
  catch(error) { console.log('UNRUN: existing Chromium required: '+error.message);process.exitCode=77;return; }
  fs.mkdirSync(scratch,{recursive:true});
  try {
    const a=prepare('SIM-A'),b=prepare('SIM-B');
    const starts=[];
    for(const packet of [a,b]) {services.push({packet});const started=cli(packet,'start').value;services.at(-1).url=started.url;starts.push(started);}
    const urlA=services[0].url,urlB=services[1].url;
    assert(urlA&&urlB);assert.notEqual(urlA,urlB);
    assert.notEqual(starts[0].instance_id,starts[1].instance_id);
    const context=await browser.newContext({viewport:{width:1440,height:900},reducedMotion:'reduce'});
    const page=await context.newPage(),second=await context.newPage();
    const errors=[];page.on('pageerror',error=>errors.push(error.message));second.on('pageerror',error=>errors.push(error.message));
    await page.goto(urlA);await second.goto(urlB);
    await page.locator('#task-list [data-task-id="DEMO-001"]').click();
    await second.locator('#task-list [data-task-id="DEMO-001"]').click();
    assert.match(await page.locator('#packet-title').innerText(),/SIM-A/);
    assert.match(await second.locator('#packet-title').innerText(),/SIM-B/);
    const staleTime=new Date(Date.now()-180000).toISOString();
    const stale=publish(b,'stale-main',[main('running'),task('implementing'),role('WORKER','running')],staleTime);
    await visible(second,b,stale);
    await second.waitForFunction(()=>document.querySelector('#freshness').textContent.includes('状态未及时同步'));
    assert.match(await second.locator('#connection').innerText(),/已连接/);
    const bBefore=fs.readFileSync(stateFile(b));
    for(let i=0;i<3;i++)assert.equal((await (await fetch(urlB+'api/status')).json()).state.tasks['DEMO-001'].status,'implementing');
    assert(bBefore.equals(fs.readFileSync(stateFile(b))));
    log.push({type:'stale-healthy',status:'implementing',text:await second.locator('#freshness').innerText(),unchangedBytes:true});
    await second.screenshot({path:path.join(scratch,'stale-main.png'),fullPage:true});
    await visible(page,a,publish(a,'worker-running',[main('running'),task('implementing'),role('WORKER','running')]));
    const oldValid=fs.readFileSync(stateFile(a));
    await page.locator('#task-filter').selectOption('active');await page.locator('#zoom-in').click();
    const signature=()=>page.evaluate(()=>({selected:document.querySelector('#task-detail').dataset.taskId,filter:document.querySelector('#task-filter').value,transform:document.querySelector('#graph-content').getAttribute('transform')}));
    const before=await signature();
    await visible(page,a,publish(a,'delivery',[evidence(a,'DELIVERY',1),check('DELIVERY','PASS',1),role('WORKER','completed'),task('awaiting_review')]));
    assert.deepEqual(await signature(),before);
    const good=fs.readFileSync(stateFile(a));
    try {
      fs.writeFileSync(stateFile(a),'{ malformed synthetic source');
      await page.waitForFunction(()=>document.querySelector('#sync-error').textContent.length>0,null,{timeout:5000});
      assert.match(await page.locator('#packet-meta').innerText(),/seq 2/);
      assert.deepEqual(await signature(),before);
      log.push({type:'malformed-retained',seq:2,error:await page.locator('#sync-error').innerText()});
    } finally {fs.writeFileSync(stateFile(a),good);}
    await page.waitForFunction(()=>document.querySelector('#sync-error').textContent==='');
    try {
      fs.writeFileSync(stateFile(a),oldValid);
      await page.waitForFunction(()=>document.querySelector('#connection').textContent.includes('连接异常'),null,{timeout:5000});
      assert.match(await page.locator('#packet-meta').innerText(),/seq 2/);assert.deepEqual(await signature(),before);
      log.push({type:'old-seq-retained',seq:2,error:await page.locator('#sync-error').innerText()});
    } finally {fs.writeFileSync(stateFile(a),good);}
    await page.waitForFunction(()=>document.querySelector('#connection').textContent.includes('已连接'));
    await visible(page,a,publish(a,'review-running',[task('reviewing'),role('REVIEW-A','running'),role('REVIEW-B','running')]));
    await visible(page,a,publish(a,'review-findings',[evidence(a,'REVIEW-A',1),check('REVIEW-A','FAIL',1),evidence(a,'REVIEW-B',1),check('REVIEW-B','PASS',1),role('REVIEW-A','completed'),role('REVIEW-B','completed')]));
    const fixing=task('fixing',{round:2});fixing.reason='模拟独立审查要求返修';
    await visible(page,a,publish(a,'rework',[fixing,role('WORKER','running',2)]));
    assert.match(await page.locator('#task-detail').innerText(),/旧轮次.*失效/);
    await page.locator('#task-filter').selectOption('all');await page.screenshot({path:path.join(scratch,'rework.png'),fullPage:true});
    const rejected=publish(a,'premature-done',[task('done')],now(),2);assert.equal(read(stateFile(a)).seq,5);
    assert.equal(rejected.value.state_published,false);
    await visible(page,a,publish(a,'redelivery',[evidence(a,'DELIVERY',2),check('DELIVERY','PASS',2),role('WORKER','completed',2),task('awaiting_review')]));
    await visible(page,a,publish(a,'rereview',[task('reviewing'),role('REVIEW-A','running',2),role('REVIEW-B','running',2)]));
    await visible(page,a,publish(a,'dual-current-pass',[evidence(a,'REVIEW-A',2),check('REVIEW-A','PASS',2),evidence(a,'REVIEW-B',2),check('REVIEW-B','PASS',2),role('REVIEW-A','completed',2),role('REVIEW-B','completed',2)]));
    await visible(page,a,publish(a,'waiting-user',[main('waiting_user')]));
    assert.match(await page.locator('#freshness').innerText(),/等待用户/);assert.equal(read(stateFile(a)).tasks['DEMO-001'].status,'reviewing');
    const finish=publish(a,'done',[main('finished'),task('done'),{type:'evidence.put',id:'SIM-CROSS',evidence:{title:'模拟跨仓定位',reference:{repository:'other-simulated-repo',path:'reports/result.md'}}}]);
    await visible(page,a,finish);assert.match(await page.locator('#freshness').innerText(),/已结束/);
    const finalBytes=fs.readFileSync(stateFile(a));cli(a,'publish',['--input',finish.file]);assert(finalBytes.equals(fs.readFileSync(stateFile(a))));
    cli(a,'export');assert(finalBytes.equals(fs.readFileSync(stateFile(a))));
    const evidenceLink=page.locator('#task-detail a[href^="/evidence/"]').first();assert(await evidenceLink.count());
    const response=await fetch(urlA.replace(/\/$/,'')+await evidenceLink.getAttribute('href'));assert.equal(response.status,200);assert.match(await response.text(),/模拟证据/);
    assert.equal((await fetch(urlA+'evidence/SIM-CROSS')).status,404);
    assert.match(await page.locator('#events').innerText(),/other-simulated-repo \/ reports\/result.md/);
    await page.screenshot({path:path.join(scratch,'finished-live.png'),fullPage:true});
    cli(a,'stop');await closed(urlA);assert.equal(cli(a,'status').value.service.running,false);
    const surviving=await (await fetch(urlB+'api/status')).json();assert.equal(surviving.state.packet.id,'SIM-B');assert.equal(surviving.state.seq,1);
    log.push({type:'stop-isolation',firstClosed:true,secondReadable:true,secondSeq:1});
    cli(b,'stop');await closed(urlB);
    const offline=await browser.newContext({offline:true,viewport:{width:1440,height:900}});
    await offline.route(/^https?:/,route=>route.abort());
    const off=await offline.newPage();let requests=0;off.on('request',request=>{if(/^https?:/.test(request.url()))requests++;});
    const relocated=path.join(scratch,'迁移 中文 with spaces','独立任务包');fs.mkdirSync(path.dirname(relocated),{recursive:true});fs.cpSync(a,relocated,{recursive:true});
    for(const packet of [a,relocated]) {
      await off.goto(pathToFileURL(path.join(packet,'dashboard/index.html')).href);
      await off.locator('#task-list [data-task-id="DEMO-001"]').click();
      await off.evaluate(()=>Panel.refreshOnce());
      assert.match(await off.locator('#connection').innerText(),/离线快照/);assert.match(await off.locator('#counts').innerText(),/1 \/ 1/);
      assert.match(await off.locator('#task-detail').innerText(),/REVIEW-A[\s\S]*REVIEW-B/);
      assert(await off.locator('#graph-content [data-node-id]').count());
      assert.match(await off.locator('#events').innerText(),/other-simulated-repo/);assert.equal(await off.locator('a[href^="/evidence/"]').count(),0);
      assert.equal(await off.locator('#task-graph').evaluate(node=>getComputedStyle(node).display==='none'),false);
      log.push({type:'offline',location:packet===a?'original':'Chinese-space relocation',seq:10,httpRequests:requests});
    }
    assert.equal(requests,0);await off.screenshot({path:path.join(scratch,'relocated-offline.png'),fullPage:true});await offline.close();
    assert.equal(cli(relocated,'status').value.seq,10);cli(relocated,'export');assert(finalBytes.equals(fs.readFileSync(stateFile(relocated))));
    // Complete v1 import is a local migration mechanism, not an external adapter.
    const imported=path.join(scratch,'旧包 投影 import');copyBundle(imported);fs.mkdirSync(path.join(imported,'runtime'));
    const legacy=Buffer.from('legacy authority retained\n');fs.writeFileSync(stateFile(imported),legacy);
    const snapshot=JSON.parse(finalBytes);snapshot.source={...snapshot.source,mode:'projection',reference:{repository:'legacy-simulated',path:'runtime/state.json'}};
    write(path.join(imported,'snapshot.json'),snapshot);cli(imported,'import',['--input',path.join(imported,'snapshot.json')]);
    assert(legacy.equals(fs.readFileSync(stateFile(imported))));assert.deepEqual(read(path.join(imported,'runtime/view.json')),snapshot);
    assert.equal(cli(imported,'status').value.seq,10);cli(imported,'export');
    log.push({type:'migration',legacyPreserved:true,fullSnapshotPreserved:true,externalAdapter:'UNRUN'});
    assert.deepEqual(errors,[]);
    log.push({type:'result',status:'PASS',browser:browser.version(),samples:log.filter(row=>row.type==='visible').length,maxLatencyMs:Math.max(...log.filter(row=>row.type==='visible').map(row=>row.latencyMs)),scope:'synthetic events through real copied CLI, services and Chromium'});
  } catch(error) {
    log.push({type:'failure',message:error.stack});throw error;
  } finally {
    for(const service of services) {
      try {cli(service.packet,'stop');if(service.url)await closed(service.url);assert.equal(cli(service.packet,'status').value.service.running,false);}
      catch(error) {log.push({type:'cleanup-error',message:error.message});}
    }
    await browser.close();log.push({type:'cleanup',browserClosed:true,servicesClosed:!log.some(row=>row.type==='cleanup-error')});
    write(path.join(scratch,'results.json'),log);
    if(log.some(row=>row.type==='cleanup-error'))throw new Error('Cleanup failed; see scratch results');
  }
  console.log(JSON.stringify(log.filter(row=>['result','cleanup','stop-isolation','migration'].includes(row.type))));
})().catch(error=>{console.error(error);process.exitCode=1;});
