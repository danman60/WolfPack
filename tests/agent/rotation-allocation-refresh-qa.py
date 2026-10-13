#!/usr/bin/env python3
"""Targeted real-market refresh and frozen-projection checks through QA Agent."""
import argparse,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path.home()/'projects/qa-agent'))
from executors.web import WebExecutor

def main():
 p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert a.url=='http://127.0.0.1:3218/rotation';print('QA target:',a.url,flush=True);origin=a.url.removesuffix('/rotation');a.output.mkdir(parents=True,exist_ok=True);b=WebExecutor();assert b.setup();markets=[];workspaceResponses=[];checks=[]
 def get(path):r=b.context.request.get(origin+'/api/rotation/'+path);assert r.ok,(path,r.status);return r.json()
 def wait(fn,msg,seconds=120):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   b.snapshot()
   if fn():return
   time.sleep(.25)
  raise AssertionError(msg)
 def collect(r):
  if r.request.method=='GET' and r.ok:
   if r.url==origin+'/api/rotation/market':markets.append(r.json())
   if r.url==origin+'/api/rotation/allocation':workspaceResponses.append(r.json())
 def panel():return b.page.get_by_text('SAVED FORECAST · ORIGINAL BASELINE',exact=True).locator('..').inner_text()
 def passed(s):checks.append(s);print('PASS',s,flush=True)
 try:
  b.context.add_cookies(json.loads(a.state.read_text())['cookies']);b.page.on('response',collect);b.navigate(a.url);wait(lambda:'Allocation applied' in b.snapshot(),'Completed batch restored');before=get('portfolio')['portfolio'];batch=get('allocation')['batches'][0];frozen=panel();n=len(workspaceResponses)
  b.page.get_by_role('button',name='Refresh analysis',exact=True).click();wait(lambda:len(workspaceResponses)>n,'Fresh workspace response');assert panel()==frozen;assert get('allocation')['batches'][0]==batch;assert get('portfolio')['portfolio']==before;passed('Real forecast refresh preserves completed batch and its frozen displayed estimate')
  # Save a new not-yet-applied projection using normal controls.
  b.page.get_by_text('Set exact percentages',exact=True).click();old=get('allocation')['projections'][0]['id'];b.page.get_by_label('CAD target percent',exact=True).fill('90');b.page.get_by_label('CAD target percent',exact=True).press('Tab');wait(lambda:get('allocation')['projections'][0]['id']!=old,'New projection saved');saved=get('allocation')['projections'][0];frozen=panel();n=len(markets)
  wait(lambda:len(markets)>=n+2,'Two genuine25second market polls',75)
  latest=max([*markets,*[x['market'] for x in workspaceResponses]],key=lambda m:m['fetchedAt']);total=sum(float(before['balances'][asset])*(1 if asset=='CAD' else (float(latest['books'][asset]['bid'])+float(latest['books'][asset]['ask']))/2) for asset in before['balances'])
  expected=b.page.evaluate('(v)=>new Intl.NumberFormat("en-CA",{style:"currency",currency:"CAD",maximumFractionDigits:2}).format(v)',total)
  card=b.page.get_by_text('YOUR PORTFOLIO',exact=True).locator('../..');assert expected in card.inner_text(),(expected,card.inner_text());assert panel()==frozen;assert get('allocation')['projections'][0]==saved;passed('Two observed market polls update current marked value while pre-Apply forecast remains frozen')
  # Keyboard change interrupted by focus transfer is a genuine unsaved owner draft.
  slider=b.page.get_by_role('slider',name='CAD allocation boundary');slider.focus();b.page.keyboard.down('ArrowLeft');draft={asset:b.page.get_by_role('slider',name=asset+' allocation boundary').get_attribute('aria-valuenow') for asset in ['CAD','BTC','ETH','LINK']};n=len(workspaceResponses);b.page.get_by_role('button',name='Refresh analysis',exact=True).click();b.page.keyboard.up('ArrowLeft');wait(lambda:len(workspaceResponses)>n,'Draft refresh');assert draft=={asset:b.page.get_by_role('slider',name=asset+' allocation boundary').get_attribute('aria-valuenow') for asset in draft};assert get('allocation')['projections'][0]['id']==saved['id'];assert 'Save draft' in b.snapshot();passed('Unsaved owner weight draft survives real workspace refresh without autosave or reset')
  b.page.get_by_role('button',name='Save draft',exact=True).click();wait(lambda:get('allocation')['projections'][0]['id']!=saved['id'],'Draft save');latestSaved=get('allocation')['projections'][0];assert get('portfolio')['portfolio']==before
  (a.output/'report.json').write_text(json.dumps({'status':'PASS','checks':checks,'marketSnapshotsObserved':[{'id':m['id'],'fetchedAt':m['fetchedAt']} for m in markets],'verifiedCurrentValueCad':total,'latestSourceMarketId':latest['id'],'savedBeforeApplyId':saved['id'],'finalSavedId':latestSaved['id'],'automaticForecastTimer':'Source registers same tested refresh callback every300000ms; five-minute wall-clock firing not claimed.'},indent=2))
 except Exception as e:
  (a.output/'failure.json').write_text(json.dumps({'error':str(e),'checks':checks},indent=2));(a.output/'failure-snapshot.txt').write_text(b.snapshot());raise
 finally:b.teardown()
if __name__=='__main__':main()
