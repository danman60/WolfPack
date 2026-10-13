#!/usr/bin/env python3
"""Actual isolated demo entry/return flow. No production mutations permitted."""
import argparse,json,sys,time,hashlib,subprocess
from pathlib import Path
from decimal import Decimal,ROUND_DOWN
sys.path.insert(0,str(Path.home()/'projects/qa-agent'));from executors.web import WebExecutor
from rotation_qa_target import validate_target,protect_context

def main():
 p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--expected-sha');p.add_argument('--protection-file',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();target=validate_target(a.url,a.expected_sha);print('QA target:',a.url,flush=True);a.output.mkdir(parents=True,exist_ok=True);b=WebExecutor();assert b.setup();headers=protect_context(b.context,a.url,a.protection_file);origin=a.url.removesuffix('/rotation');checks=[];calls=[]
 def get(path):
  r=b.context.request.get(origin+'/api/rotation/'+path,headers=headers);assert r.ok,(path,r.status,r.text()[:250]);return r.json()
 def post(body,foreign=False):return b.context.request.post(origin+'/api/rotation/session',data=body,headers={**headers,'Origin':'https://example.invalid' if foreign else origin})
 def wait(fn,msg):
  end=time.monotonic()+120
  while time.monotonic()<end:
   b.snapshot()
   if fn():return
   time.sleep(.5)
  raise AssertionError(msg)
 def passed(s):checks.append(s);print('PASS',s,flush=True)
 def seed(tag):
  portfolio=get('portfolio')['portfolio'];ws=get('allocation');export=get('portfolio?export=1');trials=[t for t in export['trials'] if t['data'].get('namespace')=='demo-example'];assert len(trials)==1;data=trials[0]['data'];assert data['portfolioId']==portfolio['id'];assert portfolio['balances']==data['opening'];assert portfolio['initialValueCad']=='10000';assert portfolio['cadence']=='weekly' and portfolio['feeBps']==20;assert ws['riskPercent']==80 and ws['slippageBps']==10
  tick=Decimal('.00000001');cash=Decimal(10000)
  for asset,budget in [('BTC',4000),('ETH',2000),('LINK',2000)]:
   book=data['market']['books'][asset];mark=((Decimal(book['bid'])+Decimal(book['ask']))/2).quantize(tick,rounding=ROUND_DOWN);inc=Decimal(book['increment']);expected=(Decimal(budget)/mark/inc).to_integral_value(rounding=ROUND_DOWN)*inc;assert Decimal(portfolio['balances'][asset])==expected and expected>0;cash-=(expected*mark).quantize(tick,rounding=ROUND_DOWN)
  assert Decimal(portfolio['balances']['CAD'])==cash and cash>0;assert all(b.page.get_by_role('slider',name=k+' allocation slider',exact=True).count()==1 for k in ['CAD','BTC','ETH','LINK']);assert len(get('analysis')['analysis']['pairs'])==6;assert not b.page.get_by_role('button',name='Create paper portfolio',exact=True).count();a.output.joinpath(tag+'-seed.json').write_text(json.dumps({'portfolio':portfolio,'trial':trials[0],'settings':{'riskPercent':ws['riskPercent'],'slippageBps':ws['slippageBps']}},indent=2));passed(tag+': exact CAD10000 captured-mark accounting, four positive holdings, defaults and six charts/four sliders without setup');return portfolio
 def capture(width):
  b.set_viewport(width,1000 if width==1440 else 844);b.page.evaluate('()=>{window.scrollTo(0,0);for(const e of document.querySelectorAll("*"))e.scrollTop=0;}');b.snapshot();time.sleep(.5);path=a.output/f'example-{width}.png';b.page.screenshot(path=str(path),full_page=True);src=(Path.home()/'.local/bin/shot').read_text();m=b.page.evaluate(src.split('const domChecks = ',1)[1].split(';\n\nconst browser',1)[0]);b.page.add_script_tag(content=(Path.home()/'.claude/tools/shot/node_modules/axe-core/axe.min.js').read_text());v=b.page.evaluate("async()=> (await window.axe.run(document,{runOnly:['color-contrast']})).violations");assert not v;assert not m['fail'];Path(str(path)+'.review.json').write_text(json.dumps({'url':a.url,'pass':True,**m},indent=2))
 try:
  b.page.on('request',lambda r:calls.append(json.loads(r.post_data)) if r.url==origin+'/api/rotation/session' and r.method=='POST' else None);b.set_viewport(1440,1000);b.navigate(a.url);wait(lambda:b.page.get_by_role('button',name='Open $10,000 demo',exact=True).count(),'Signed-out demo button');b.page.get_by_role('button',name='Open $10,000 demo',exact=True).click();wait(lambda:b.page.get_by_role('slider',name='CAD allocation slider',exact=True).count(),'Seeded workspace');firstsession=get('session');first=seed('signedout');state=a.output/'private-first-state.json';b.context.storage_state(path=str(state));state.chmod(0o600)
  b.navigate(a.url);wait(lambda:b.page.get_by_role('slider',name='CAD allocation slider',exact=True).count(),'Reload seeded portfolio');assert get('portfolio')['portfolio']==first;passed('Reload preserves exact opening units and ledger')
  r=post({'action':'demo-example'},True);assert r.status==403;assert get('session')['user']['id']==firstsession['user']['id'];assert get('portfolio')['portfolio']==first;passed('Rejected cross-origin fresh-example request preserves current identity and ledger')
  r=post({'action':'demo'});assert r.ok;assert r.json()['portfolio']==first;assert get('portfolio')['portfolio']==first;assert len([t for t in get('portfolio?export=1')['trials'] if t['data'].get('namespace')=='demo-example'])==1;passed('Repeated same-user seed reuses one portfolio and one immutable seed')
  slider=b.page.get_by_role('slider',name='BTC allocation slider',exact=True);n=len(get('allocation')['projections']);slider.press('ArrowRight');wait(lambda:len(get('allocation')['projections'])>n,'Immediate slider autosave');assert get('portfolio')['portfolio']==first;passed('Sliders immediately save forecasts without moving holdings')
  button=b.page.get_by_role('button',name='Open $10,000 example',exact=True);button.scroll_into_view_if_needed();box=button.bounding_box();count=len([c for c in calls if c.get('action')=='demo-example']);b.page.mouse.dblclick(box['x']+box['width']/2,box['y']+box['height']/2,delay=80);wait(lambda:get('session')['user']['id']!=firstsession['user']['id'],'Fresh isolated example');wait(lambda:b.page.get_by_role('button',name='Return to previous workspace',exact=True).count(),'Return control');wait(lambda:b.page.get_by_role('slider',name='CAD allocation slider',exact=True).count(),'Fresh seeded workspace');second=seed('signedin');assert first['id']!=second['id'];assert len([c for c in calls if c.get('action')=='demo-example'])==count+1;assert get('session')['hasPreviousWorkspace'];cookies=b.context.cookies();assert len([c for c in cookies if 'previous' in c['name']])==2;assert all(c['httpOnly'] and c['sameSite']=='Strict' for c in cookies if 'previous' in c['name']);assert 'wpr_' not in b.page.evaluate('document.cookie');passed('Actual double-click creates one fresh example; prior session stays in HttpOnly cookies')
  capture(390);capture(1440);b.page.get_by_role('button',name='Return to previous workspace',exact=True).click();wait(lambda:get('session')['user']['id']==firstsession['user']['id'],'Return original identity');assert get('portfolio')['portfolio']==first;assert not get('session')['hasPreviousWorkspace'];assert not any(t['data'].get('portfolioId')==second['id'] for t in get('portfolio?export=1')['trials']);passed('Return restores original identity and exact ledger; second owner data remains isolated')
  a.output.joinpath('report.json').write_text(json.dumps({'status':'PASS','target':target,'checks':checks,'sessionActions':[c.get('action') for c in calls],'scope':'Local/Preview isolated paper only. No funded execution. External quote failure ordering source-reviewed; no fake outage induced.'},indent=2))
 except Exception as e:a.output.joinpath('failure.json').write_text(json.dumps({'error':str(e),'checks':checks},indent=2));a.output.joinpath('failure-snapshot.txt').write_text(b.snapshot());raise
 finally:b.teardown()
if __name__=='__main__':main()
