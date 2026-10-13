#!/usr/bin/env python3
"""Local-only QA Agent flow. Creates one isolated paper demo member through the real UI."""
import argparse,json,sys,time,os
from pathlib import Path
sys.path.insert(0,str(Path.home()/'projects/qa-agent'))
from executors.web import WebExecutor
from rotation_qa_target import validate_target,protect_context

def main():
 p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-sha');p.add_argument('--protection-file',type=Path);a=p.parse_args()
 target=validate_target(a.url,a.expected_sha)
 print('QA target:',a.url,flush=True);a.output.mkdir(parents=True,exist_ok=True);origin=a.url.removesuffix('/rotation');b=WebExecutor();assert b.setup();protectedHeaders=protect_context(b.context,a.url,a.protection_file);checks=[]
 def wait(fn,msg):
  end=time.monotonic()+150
  while time.monotonic()<end:
   b.snapshot()
   if fn():return
   time.sleep(.3)
  raise AssertionError(msg)
 def get(path):
  r=b.context.request.get(origin+'/api/rotation/'+path,headers=protectedHeaders);assert r.ok,(path,r.status,r.text()[:300]);return r.json()
 def click(label):b.page.get_by_role('button',name=label,exact=True).click()
 def passed(label):checks.append(label);print('PASS',label,flush=True)
 try:
  b.set_viewport(1440,1000)
  state=a.output/'private-state.json'
  if state.exists():b.context.add_cookies(json.loads(state.read_text())['cookies'])
  assert b.navigate(a.url)
  if not state.exists():
   wait(lambda:b.page.get_by_role('button',name='Enter paper demo',exact=True).count(),'Demo button');click('Enter paper demo')
   wait(lambda:'Set your starting point' in b.snapshot(),'Fresh demo setup')
   b.context.storage_state(path=str(state));state.chmod(0o600)
  wait(lambda:'Set your starting point' in b.snapshot() or 'My plan' in b.snapshot(),'Workspace')
  if get('portfolio')['portfolio'] is None:
   for label,value in {'Portfolio name':'Allocation QA isolated paper','Opening CAD':'10000','Opening BTC':'.1','Opening ETH':'0.1','Opening LINK':'10','Fee (bps)':'20'}.items():b.page.get_by_label(label,exact=False).fill(value)
   b.page.get_by_label('Review cadence',exact=False).filter(visible=True).select_option('weekly');click('Create paper portfolio')
   wait(lambda:get('portfolio')['portfolio'] is not None,'Portfolio saved')
   opening=get('portfolio')['portfolio'];assert opening['balances']['BTC']=='0.1' and opening['balances']['ETH']=='0.1';passed('Decimal .1 and 0.1 opening balances saved through customer form')
  wait(lambda:'Preview recommended allocation' in b.snapshot(),'Allocation workspace ready')
  wait(lambda:len(get('analysis')['analysis']['pairs'])==6,'Six real pairs')
  before=get('portfolio')['portfolio'];workspace=get('allocation');analysis=get('analysis')['analysis']
  assert len(analysis['pairs'])==6 and all(len(x['series'])>=200 for x in analysis['pairs']);passed('Six observed-price pairs and real dated news analysis')
  if not b.page.get_by_label('Slippage allowance (bps)',exact=False).is_visible():b.page.get_by_text('Recommendation preferences',exact=True).click()
  b.page.get_by_label('Slippage allowance (bps)',exact=False).fill('10');b.page.get_by_label('Maximum crypto budget percent',exact=True).fill('60');click('Save recommendation preferences')
  wait(lambda:get('allocation')['slippageBps']==10 and get('allocation')['riskPercent']==60,'Preferences persist');passed('Saved risk and cost preferences through primary controls')
  click('Preview recommended allocation');wait(lambda:len(get('allocation')['projections'])>len(workspace['projections']),'Projection saved')
  saved=get('allocation')['projections'][0];assert saved['startingBalances']==before['balances'];assert saved['analysis']['id']==saved['analysisId'];assert get('portfolio')['portfolio']==before
  (a.output/'projection.json').write_text(json.dumps(saved,indent=2));passed('Recommendation saves frozen forecast, actual holdings, market and analysis without a trade')
  click('Next check-in');wait(lambda:'Your saved forecast, checked.' in b.snapshot(),'Check-in dialog');assert 'no future result is invented' in b.snapshot();click('Close');passed('Not-due check-in displays frozen forecast without invented outcome')
  # Exact percentages are the normal customer override; target 50% CAD produces a genuine paper rebalance.
  b.page.get_by_text('Set exact percentages',exact=True).click();b.page.get_by_label('CAD target percent',exact=True).fill('50');b.page.get_by_label('CAD target percent',exact=True).press('Tab')
  wait(lambda:get('allocation')['projections'][0]['id']!=saved['id'],'Percent change autosaved')
  selected=get('allocation')['projections'][0];assert abs(selected['weights']['CAD']-.5)<1e-8
  assert get('portfolio')['portfolio']==before;passed('Exact-percent override autosaves; original snapshot remains immutable')
  # Browser actions and subsequent server data are both observed.
  click('Apply allocation');wait(lambda:bool(get('allocation')['batches']),'Batch created')
  wait(lambda:get('allocation')['batches'][0]['status'] in ['completed','paused'],'Batch reached settled state')
  batch=get('allocation')['batches'][0];after=get('portfolio')['portfolio']
  (a.output/'batch.json').write_text(json.dumps(batch,indent=2));(a.output/'portfolio-after.json').write_text(json.dumps(after,indent=2))
  assert batch['mode']=='paper';assert all(x['status']=='filled' for x in batch['orders']) if batch['status']=='completed' else True
  passed('Customer Apply created paper batch and reached '+batch['status'])
  for width,height in [(1440,1000),(390,844)]:
   b.set_viewport(width,height);time.sleep(.5);assert b.page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth');b.page.screenshot(path=str(a.output/f'applied-{width}.png'),full_page=True)
  assert b.navigate(a.url);wait(lambda:'Preview recommended allocation' in b.snapshot(),'Restored workspace');assert get('portfolio')['portfolio']==after
  old=[x for x in get('allocation')['projections'] if x['id']==saved['id']][0];assert old==saved;passed('Reload preserves ledger and immutable original forecast')
  (a.output/'report.json').write_text(json.dumps({'status':'PASS','target':target,'url':a.url,'checks':checks,'batchStatus':batch['status'],'projectionId':selected['id'],'batchId':batch['id']},indent=2))
 except Exception as e:
  (a.output/'failure.json').write_text(json.dumps({'error':str(e),'checks':checks},indent=2));(a.output/'failure-snapshot.txt').write_text(b.snapshot());raise
 finally:b.teardown()
if __name__=='__main__':main()
