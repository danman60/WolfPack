#!/usr/bin/env python3
"""Final local-only customer Apply and composed screenshot capture via QA Agent."""
import argparse,sys,json,time,shutil
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0,'/home/danman60/projects/qa-agent');from executors.web import WebExecutor
parser=argparse.ArgumentParser();parser.add_argument('--url',required=True);parser.add_argument('--state',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();url=args.url;assert url=='http://127.0.0.1:3218/rotation';print('QA target:',url,flush=True);out=args.output;out.mkdir(exist_ok=True);b=WebExecutor();b.setup();b.context.add_cookies(json.loads(args.state.read_text())['cookies']);b.set_viewport(1440,1000);b.navigate(url)
def get(path):r=b.context.request.get('http://127.0.0.1:3218/api/rotation/'+path);assert r.ok;return r.json()
def wait(fn,msg):
 end=time.monotonic()+150
 while time.monotonic()<end:
  b.snapshot()
  if fn():return
  time.sleep(.2)
 raise AssertionError(msg)
try:
 wait(lambda:b.page.get_by_role('button',name='Apply allocation',exact=True).count(),'Apply visible');before=get('portfolio')['portfolio'];p=get('allocation')['projections'][0]
 b.page.get_by_role('button',name='Apply allocation',exact=True).click();wait(lambda:any(x['projectionId']==p['id'] for x in get('allocation')['batches']),'Batch created');wait(lambda:next(x for x in get('allocation')['batches'] if x['projectionId']==p['id'])['status'] in ['completed','paused'],'Batch done');batch=next(x for x in get('allocation')['batches'] if x['projectionId']==p['id']);assert batch['status']=='completed',batch['pauseReason'];after=get('portfolio')['portfolio'];assert batch['mode']=='paper';out.joinpath('completed.json').write_text(json.dumps({'before':before,'after':after,'projection':p,'batch':batch},indent=2))
 # Reload ordinary context removes mobile emulation's retained visual viewport state.
 b.navigate(url);wait(lambda:'Allocation applied' in b.snapshot(),'Completed UI restore');wait(lambda:len(b.page.get_by_role('img').all())>=6,'Six pair images');shots=[]
 for width,height in [(390,844),(1440,1000)]:
  b.set_viewport(width,height);b.page.evaluate('()=>{window.scrollTo(0,0);for(const el of document.querySelectorAll("*")){if(el.scrollTop)el.scrollTop=0;}}');b.snapshot();time.sleep(.7)
  assert b.page.get_by_role('heading',name='A clearer next move.',exact=True).is_visible();path=out/f'completed-{width}.png';b.page.screenshot(path=str(path),full_page=True)
  source=Path('/home/danman60/.local/bin/shot').read_text();checks=b.page.evaluate(source.split('const domChecks = ',1)[1].split(';\n\nconst browser',1)[0]);b.page.add_script_tag(content=Path('/home/danman60/.claude/tools/shot/node_modules/axe-core/axe.min.js').read_text());vs=b.page.evaluate("async()=> (await window.axe.run(document,{runOnly:['color-contrast']})).violations")
  for v in vs:
   for node in v['nodes']:checks['fail'].append({'check':'contrast','el':' '.join(node['target']),'detail':v['help']})
  review={'url':url,'width':width,'pass':not checks['fail'],**checks};assert review['pass'];Path(str(path)+'.review.json').write_text(json.dumps(review,indent=2));shots.append(review);held=Path.home()/'.claude/shots/pending'/f'wolfpack-allocation-completed-{width}-{datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%dT%H%M%S")}.png';shutil.copyfile(path,held);Path(str(held)+'.review.json').write_text(json.dumps({**review,'png':str(held)},indent=2))
 out.joinpath('report.json').write_text(json.dumps({'status':'PASS','batchStatus':batch['status'],'orders':len(batch['orders']),'screenshots':shots},indent=2));print('PASS final completed batch and composed screenshots',flush=True)
finally:b.teardown()
