#!/usr/bin/env python3
"""Real QA Agent range gestures; isolated local or verified immutable Preview only."""
import argparse,json,sys,time,hashlib
from pathlib import Path
sys.path.insert(0,str(Path.home()/'projects/qa-agent'))
from executors.web import WebExecutor
from rotation_qa_target import validate_target,protect_context

def main():
 p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--capture-only',action='store_true');p.add_argument('--expected-sha');p.add_argument('--protection-file',type=Path);a=p.parse_args();target=validate_target(a.url,a.expected_sha);print('QA target:',a.url,flush=True);a.output.mkdir(parents=True,exist_ok=True);b=WebExecutor();assert b.setup();headers=protect_context(b.context,a.url,a.protection_file);origin=a.url.removesuffix('/rotation');checks=[]
 def get(path):
  r=b.context.request.get(origin+'/api/rotation/'+path,headers=headers);assert r.ok,(path,r.status,r.text()[:300]);return r.json()
 def wait(fn,msg):
  until=time.monotonic()+100
  while time.monotonic()<until:
   b.snapshot()
   if fn():return
   time.sleep(1)
  raise AssertionError(msg)
 def ui():
  w={k:float(b.page.get_by_role('slider',name=k+' allocation slider',exact=True).input_value()) for k in ['CAD','BTC','ETH','LINK']};assert abs(sum(w.values())-100)<=.201,w
  for k,v in w.items():assert abs(float(b.page.get_by_role('slider',name=k+' allocation boundary',exact=True).get_attribute('aria-valuenow'))-v)<.051
  return w
 def capture(width):
  b.set_viewport(width,1000 if width==1440 else 844);b.page.evaluate('()=>{window.scrollTo(0,0);for(const e of document.querySelectorAll("*"))e.scrollTop=0;}');b.snapshot();time.sleep(.3);path=a.output/f'sliders-{width}.png';b.page.screenshot(path=str(path),full_page=True);source=(Path.home()/'.local/bin/shot').read_text();measured=b.page.evaluate(source.split('const domChecks = ',1)[1].split(';\n\nconst browser',1)[0]);b.page.add_script_tag(content=(Path.home()/'.claude/tools/shot/node_modules/axe-core/axe.min.js').read_text());violations=b.page.evaluate("async()=> (await window.axe.run(document,{runOnly:['color-contrast']})).violations");assert not violations;Path(str(path)+'.review.json').write_text(json.dumps({'url':a.url,'pass':not measured['fail'],**measured},indent=2));assert not measured['fail']
 try:
  b.context.add_cookies(json.loads(a.state.read_text())['cookies']);b.set_viewport(1440,1000);b.navigate(a.url);wait(lambda:b.page.get_by_role('slider',name='CAD allocation slider',exact=True).count(),'Range inputs ready');portfolio=get('portfolio')['portfolio'];
  if a.capture_only:
   capture(390);capture(1440);a.output.joinpath('report.json').write_text(json.dumps({'status':'PASS','target':target,'scope':'Read-only final visual capture'},indent=2));return
  old=get('allocation')['projections'][0]['id'];b.page.get_by_role('button',name='Reset',exact=True).click();wait(lambda:get('allocation')['projections'][0]['id']!=old,'Reset saved');assert get('allocation')['projections'][0]['preserveUnits']
  for k in ['CAD','BTC','ETH','LINK']:
   old=get('allocation')['projections'][0];s=b.page.get_by_role('slider',name=k+' allocation slider',exact=True);wait(lambda:not s.is_disabled(),'Slider enabled');s.focus();s.press('ArrowRight');print('Pressed',k,'value',s.input_value(),flush=True);wait(lambda:get('allocation')['projections'][0]['id']!=old['id'],k+' keyboard save');new=get('allocation')['projections'][0];assert not new.get('preserveUnits');w=ui();assert max(abs(new['weights'][x]*100-w[x]) for x in w)<.051;assert abs(sum(new['weights'].values())-1)<1e-9;s.press('Tab');time.sleep(.5);assert get('allocation')['projections'][0]['id']==new['id'];assert get('portfolio')['portfolio']==portfolio;checks.append(k+' keyboard linked pie and weights; one save; HOLD cleared; ledger unchanged')
  for mode in ['mouse','touch']:
   b.set_viewport(1440 if mode=='mouse' else 390,1000 if mode=='mouse' else 844);s=b.page.get_by_role('slider',name='CAD allocation slider',exact=True);s.scroll_into_view_if_needed();box=s.bounding_box();x=box['x']+box['width']*.65;y=box['y']+box['height']/2;end=box['x']+box['width']*.45;old=get('allocation')['projections'][0];before=ui();profitBefore=b.page.get_by_role('heading',level=3).first.inner_text()
   if mode=='mouse':b.page.mouse.move(x,y);b.page.mouse.down();b.page.mouse.move(end,y,steps=6)
   else:
    c=b.context.new_cdp_session(b.page);c.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]});c.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':end,'y':y}]})
   b.snapshot();during=ui();assert during!=before;assert b.page.get_by_role('heading',level=3).first.inner_text()!=profitBefore,'Live projected profit did not change';assert get('allocation')['projections'][0]['id']==old['id'];assert 'Unsaved' in b.snapshot() or 'DRAFT' in b.snapshot().upper()
   if mode=='mouse':b.page.mouse.up()
   else:c.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});c.detach()
   wait(lambda:get('allocation')['projections'][0]['id']!=old['id'],mode+' release save');assert get('portfolio')['portfolio']==portfolio;checks.append(mode+' live linked values before release, no premature save, release saves without ledger changes')
  capture(390);capture(1440);a.output.joinpath('report.json').write_text(json.dumps({'status':'PASS','target':target,'checks':checks},indent=2));print('PASS',len(checks),'gesture checks',flush=True)
 except Exception as e:
  a.output.joinpath('failure.json').write_text(json.dumps({'error':str(e),'checks':checks},indent=2));a.output.joinpath('failure-snapshot.txt').write_text(b.snapshot());raise
 finally:b.teardown()
if __name__=='__main__':main()
