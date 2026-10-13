#!/usr/bin/env python3
"""Explicit local QA Agent authenticated API boundary checks on isolated paper members."""
import argparse,json,sys,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path.home()/'projects/qa-agent'))
from executors.web import WebExecutor
from rotation_qa_target import validate_target,protect_context

def main():
 p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--accounts',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-sha');p.add_argument('--protection-file',type=Path);a=p.parse_args();target=validate_target(a.url,a.expected_sha);print('QA target:',a.url,flush=True);origin=a.url.removesuffix('/rotation');b=WebExecutor();other=WebExecutor();assert b.setup();protectedHeaders=protect_context(b.context,a.url,a.protection_file);other.context=b.browser.new_context(user_agent="QA-Agent/1.0");other.page=other.context.new_page();protect_context(other.context,a.url,a.protection_file);checks=[]
 def req(browser,path,body=None,status=200,originHeader=origin):
  r=browser.context.request.get(origin+'/api/rotation/'+path,headers=protectedHeaders) if body is None else browser.context.request.post(origin+'/api/rotation/'+path,data=body,headers={'Origin':originHeader,**protectedHeaders});assert r.status==status,(path,r.status,r.text()[:200]);return r.json()
 def passed(s):checks.append(s);print('PASS',s,flush=True)
 try:
  b.context.add_cookies(json.loads(a.state.read_text())['cookies']);before=req(b,'portfolio')['portfolio'];old=req(b,'allocation')['batches'][0]
  duplicate={'kind':'apply','projectionId':old['projectionId'],'expectedRevision':before['revision'],'idempotencyKey':str(uuid.uuid4()),'maxCostCad':old['maxCostCad']}
  assert req(b,'batches',duplicate)['batch']==old;assert req(b,'portfolio')['portfolio']==before;passed('Duplicate Apply returns same existing batch without duplicate ledger')
  req(b,'batches',duplicate,403,'https://foreign.invalid');passed('Cross-origin mutation rejected')
  # Authenticate another existing QA member using the ordinary form, never identity headers.
  other.navigate(a.url);account=json.loads(a.accounts.read_text())['isolation'];other.page.get_by_label('Email',exact=True).fill(account['email']);other.page.get_by_label('Password',exact=True).fill(account['password']);other.page.get_by_role('button',name='Sign in',exact=True).click()
  end=time.monotonic()+90
  while time.monotonic()<end:
   other.snapshot()
   if other.page.get_by_role('button',name='Sign out',exact=True).count():break
   time.sleep(.2)
  otherBefore=req(other,'portfolio')['portfolio'];req(other,'batches?id='+old['id'],status=404);req(other,'batches',duplicate,404);req(other,'batches',{'kind':'advance','batchId':old['id'],'expectedBatchRevision':old['revision']},404);req(other,'projections',{'kind':'checkin','projectionId':old['projectionId']},404)
  assert all(p['id']!=old['projectionId'] for p in req(other,'allocation')['projections']);assert req(other,'portfolio')['portfolio']==otherBefore;passed('Other owner cannot retrieve/apply/advance/check in another member records')
  save={'kind':'save','id':str(uuid.uuid4()),'expectedRevision':before['revision']-1,'weights':{'CAD':0,'BTC':.33333333,'ETH':.33333333,'LINK':.33333334},'slippageBps':10}
  req(b,'projections',save,409);save['expectedRevision']=before['revision'];projection=req(b,'projections',save,201)['projection'];passed('Stale portfolio revision rejected; current projection saved')
  cap=projection['estimate']['feesCad']+projection['estimate']['spreadDepthCad']+projection['estimate']['slippageCad']
  body={'kind':'apply','projectionId':projection['id'],'expectedRevision':before['revision'],'idempotencyKey':str(uuid.uuid4()),'maxCostCad':cap,'mode':'live','connection':{'mode':'live'}}
  batch=req(b,'batches',body)['batch'];assert batch['mode']=='paper' and len(batch['orders'])>=2;assert req(b,'batches',body)['batch']==batch;passed('Untrusted live-mode fields cannot enable funded execution; duplicate active Apply idempotent')
  def step(kind,rev=None,status=200):return req(b,'batches',{'kind':kind,'batchId':batch['id'],'expectedBatchRevision':batch['revision'] if rev is None else rev},status)
  batch=step('pause')['batch'];assert batch['status']=='paused';assert req(b,'portfolio')['portfolio']==before
  step('resume',batch['revision']-1,409);batch=step('resume')['batch'];assert batch['status']=='running';passed('Pause persists without fills; stale batch revision rejected; resume succeeds')
  batch=step('advance')['batch'];assert any(o['status']=='intent' for o in batch['orders']);assert req(b,'portfolio')['portfolio']==before
  batch=step('advance')['batch'];filled=req(b,'portfolio')['portfolio'];assert filled['revision']==before['revision']+1 and sum(o['status']=='filled' for o in batch['orders'])==1
  batch=step('pause')['batch'];batch=step('cancel')['batch'];assert batch['status']=='cancelled';assert req(b,'portfolio')['portfolio']==filled;assert step('advance')['portfolio']==filled;passed('One actual paper fill persists; stopping remaining orders preserves filled ledger and prevents further fills')
  a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps({'status':'PASS','target':target,'url':a.url,'checks':checks,'finalBatch':batch,'ledgerRevisionBefore':before['revision'],'ledgerRevisionAfter':filled['revision']},indent=2))
 finally:other.context.close();b.teardown()
if __name__=='__main__':main()
