#!/usr/bin/env python3
"""Explicit preserve-units HOLD across genuine refreshed public books; local paper only."""
import argparse,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path.home()/'projects/qa-agent'))
from executors.web import WebExecutor
from rotation_qa_target import validate_target,protect_context

def main():
 p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--owner-reset-hold',action='store_true');p.add_argument('--expected-sha');p.add_argument('--protection-file',type=Path);a=p.parse_args();target=validate_target(a.url,a.expected_sha);print('QA target:',a.url,flush=True);origin=a.url.removesuffix('/rotation');a.output.mkdir(parents=True,exist_ok=True);b=WebExecutor();assert b.setup();protectedHeaders=protect_context(b.context,a.url,a.protection_file);markets=[];checks=[]
 def get(path):r=b.context.request.get(origin+'/api/rotation/'+path,headers=protectedHeaders);assert r.ok,(path,r.status);return r.json()
 def wait(fn,msg):
  end=time.monotonic()+120
  while time.monotonic()<end:
   b.snapshot()
   if fn():return
   time.sleep(.25)
  raise AssertionError(msg)
 def collect(r):
  if r.request.method=='GET' and r.url==origin+'/api/rotation/market' and r.ok:markets.append(r.json())
 def passed(s):checks.append(s);print('PASS',s,flush=True)
 try:
  b.context.add_cookies(json.loads(a.state.read_text())['cookies']);b.page.on('response',collect);b.navigate(a.url);wait(lambda:('Preview recommended allocation' if a.owner_reset_hold else 'Keep your current holdings') in b.snapshot(),'Actual current-units control');before=get('portfolio')['portfolio'];old=get('allocation')['projections'][0]['id'];n=len(markets);wait(lambda:len(markets)>n,'Genuine quote before HOLD save')
  b.page.get_by_role('button',name='Reset' if a.owner_reset_hold else 'Preview recommended allocation',exact=True).click();wait(lambda:get('allocation')['projections'][0]['id']!=old,'Explicit HOLD saved');saved=get('allocation')['projections'][0]
  assert saved['preserveUnits'] is True;assert saved['estimate']['legs']==[] and saved['estimate']['plannedBalances']==before['balances'];assert saved['estimate']['feesCad']==saved['estimate']['slippageCad']==saved['estimate']['spreadDepthCad']==0;passed('Genuine refreshed-quote HOLD save preserves exact units and zero modeled trading costs')
  n=len(markets);wait(lambda:len(markets)>n,'Genuine quote before HOLD Apply');b.page.get_by_role('button',name='Apply allocation',exact=True).click();wait(lambda:any(x['projectionId']==saved['id'] for x in get('allocation')['batches']),'HOLD batch created');batch=next(x for x in get('allocation')['batches'] if x['projectionId']==saved['id']);assert batch['status']=='completed' and batch['orders']==[];assert get('portfolio')['portfolio']==before;passed('HOLD Apply after another real quote completes with no orders and no ledger or revision change')
  b.page.get_by_text('Set exact percentages',exact=True).click();b.page.get_by_label('CAD target percent',exact=True).fill('85');b.page.get_by_label('CAD target percent',exact=True).press('Tab');wait(lambda:get('allocation')['projections'][0]['id']!=saved['id'],'Custom draft saved');custom=get('allocation')['projections'][0]
  assert custom.get('preserveUnits',False) is False and len(custom['estimate']['legs'])>0 and custom['estimate']['plannedBalances']!=before['balances'];assert get('portfolio')['portfolio']==before;passed('Manual percentage edit clears HOLD intent and previews real trades without applying them')
  (a.output/'report.json').write_text(json.dumps({'status':'PASS','target':target,'holdSource':'explicit owner Reset' if a.owner_reset_hold else 'actual model HOLD recommendation','checks':checks,'savedHold':saved,'holdBatch':batch,'customProjection':custom,'marketSnapshots':[{'id':m['id'],'fetchedAt':m['fetchedAt'],'books':m['books']} for m in markets]},indent=2))
 except Exception as e:
  (a.output/'failure.json').write_text(json.dumps({'error':str(e),'checks':checks},indent=2));(a.output/'failure-snapshot.txt').write_text(b.snapshot());raise
 finally:b.teardown()
if __name__=='__main__':main()
