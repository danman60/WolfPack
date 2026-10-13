#!/usr/bin/env python3
"""QA Agent real pointer/touch allocation editing and final composed screenshot checks."""
import argparse,json,math,sys,time,shutil
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path.home()/'projects/qa-agent'))
from executors.web import WebExecutor

def main():
 p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert a.url=='http://127.0.0.1:3218/rotation';print('QA target:',a.url,flush=True);origin=a.url.removesuffix('/rotation');a.output.mkdir(parents=True,exist_ok=True);b=WebExecutor();assert b.setup();checks=[];shots=[]
 def get(path):r=b.context.request.get(origin+'/api/rotation/'+path);assert r.ok;return r.json()
 def wait(fn,msg):
  end=time.monotonic()+120
  while time.monotonic()<end:
   b.snapshot()
   if fn():return
   time.sleep(.2)
  raise AssertionError(msg)
 def capture(width):
  b.set_viewport(width,1000 if width==1440 else 844);time.sleep(.5);b.page.evaluate('()=>{window.scrollTo(0,0);for(const el of document.querySelectorAll("*")){if(el.scrollTop)el.scrollTop=0;}}');time.sleep(.2);path=a.output/f'final-{width}.png';b.page.screenshot(path=str(path),full_page=True)
  source=(Path.home()/'.local/bin/shot').read_text();measured=b.page.evaluate(source.split('const domChecks = ',1)[1].split(';\n\nconst browser',1)[0]);b.page.add_script_tag(content=(Path.home()/'.claude/tools/shot/node_modules/axe-core/axe.min.js').read_text())
  violations=b.page.evaluate("async()=> (await window.axe.run(document,{runOnly:['color-contrast']})).violations")
  for v in violations:
   for node in v['nodes']:measured['fail'].append({'check':'contrast','el':' '.join(node['target']),'detail':v['help']})
  record={'url':a.url,'width':width,'pass':not measured['fail'],**measured};Path(str(path)+'.review.json').write_text(json.dumps(record,indent=2));shots.append(record);assert record['pass'],record['fail']
  held=Path.home()/'.claude/shots/pending'/f'wolfpack-allocation-final-{width}-{datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%dT%H%M%S")}.png';shutil.copyfile(path,held);Path(str(held)+'.review.json').write_text(json.dumps({**record,'png':str(held)},indent=2))
 try:
  b.context.add_cookies(json.loads(a.state.read_text())['cookies']);b.set_viewport(1440,1000);b.navigate(a.url);wait(lambda:b.page.get_by_role('slider',name='BTC allocation boundary').count(),'Pie ready');before=get('portfolio')['portfolio']
  b.page.get_by_role('button',name='Reset',exact=True).click();wait(lambda:'Projection saved. Original inputs' in b.snapshot(),'Reset autosave')
  for mode in ['mouse','touch']:
   if mode=='touch':
    cookies=b.context.cookies();b.context.close();b.context=b.browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True,user_agent='QA-Agent/1.0');b.context.add_cookies(cookies);b.page=b.context.new_page();b.navigate(a.url);wait(lambda:b.page.get_by_role('slider',name='BTC allocation boundary').count(),'Mobile pie ready')
   if not b.page.get_by_label('CAD target percent',exact=True).is_visible():b.page.get_by_text('Set exact percentages',exact=True).click()
   previous=get('allocation')['projections'][0]['id'];b.page.get_by_label('CAD target percent',exact=True).fill('100');b.page.get_by_label('CAD target percent',exact=True).press('Tab');wait(lambda:get('allocation')['projections'][0]['id']!=previous,'Single asset autosave')
   old=get('allocation')['projections'][0];assert old['weights']['CAD']==1
   centers=[]
   for label in ['CAD','BTC','ETH','LINK']:
    rect=b.page.get_by_role('slider',name=label+' allocation boundary').locator('circle').first.bounding_box();centers.append((rect['x']+rect['width']/2,rect['y']+rect['height']/2))
   assert len(set(centers))==4,'Zero-weight handles overlap'
   handle=b.page.get_by_role('slider',name=('CAD' if mode=='mouse' else 'LINK')+' allocation boundary').locator('circle').first;handle.scroll_into_view_if_needed();box=handle.bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']/2
   svg=handle.evaluate('(el)=>{const r=el.closest("svg").getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}}');cx=svg['x']+svg['width']/2;cy=svg['y']+svg['height']/2;angle=math.atan2(y-cy,x-cx)+(-.3 if mode=='mouse' else .3);radius=math.hypot(x-cx,y-cy);dx=cx+radius*math.cos(angle)-x;dy=cy+radius*math.sin(angle)-y
   if mode=='mouse':b.page.mouse.move(x,y);b.page.mouse.down();b.page.mouse.move(x+dx,y+dy,steps=8);b.page.mouse.up()
   else:
    cdp=b.context.new_cdp_session(b.page);cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
    for i in range(1,9):cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+dx*i/8,'y':y+dy*i/8}]})
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});cdp.detach()
   wait(lambda:get('allocation')['projections'][0]['id']!=old['id'],mode+' release autosave');saved=get('allocation')['projections'][0];assert saved['weights']!=old['weights'];assert abs(sum(saved['weights'].values())-1)<1e-8;assert get('portfolio')['portfolio']==before;checks.append(mode+' drag from all-CAD with four separate handles saves without moving actual holdings');print('PASS',checks[-1],flush=True)
  wait(lambda:len(b.page.get_by_role('img').all())>=6,'Six charts visible')
  capture(390);capture(1440);a.output.joinpath('report.json').write_text(json.dumps({'status':'PASS','checks':checks,'screenshots':shots},indent=2))
 except Exception as e:
  a.output.joinpath('failure.json').write_text(json.dumps({'error':str(e),'checks':checks},indent=2));a.output.joinpath('failure-snapshot.txt').write_text(b.snapshot());raise
 finally:b.teardown()
if __name__=='__main__':main()
