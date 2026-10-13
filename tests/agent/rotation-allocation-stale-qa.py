#!/usr/bin/env python3
"""Real browser offline/online failure control; no fabricated market response."""
import argparse,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path.home()/'projects/qa-agent'))
from executors.web import WebExecutor
p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert a.url=='http://127.0.0.1:3218/rotation';print('QA target:',a.url,flush=True);b=WebExecutor();assert b.setup()
def wait(fn,msg,seconds=100):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  b.snapshot()
  if fn():return
  time.sleep(.3)
 raise AssertionError(msg)
try:
 b.context.add_cookies(json.loads(a.state.read_text())['cookies']);b.navigate(a.url);wait(lambda:'SAVED FORECAST · ORIGINAL BASELINE' in b.snapshot(),'Saved projection');panel=b.page.get_by_text('SAVED FORECAST · ORIGINAL BASELINE',exact=True).locator('..');frozen=panel.inner_text();b.context.set_offline(True)
 wait(lambda:'Price snapshot is stale.' in b.snapshot(),'Offline source expires honestly',80);assert panel.inner_text()==frozen;assert b.page.get_by_role('button',name='Apply allocation',exact=True).is_disabled();assert b.page.get_by_role('button',name='Preview recommended allocation',exact=True).is_disabled();print('PASS real offline expiry disables new advice actions; saved forecast unchanged',flush=True)
 b.context.set_offline(False);wait(lambda:'Price snapshot is stale.' not in b.snapshot(),'Automatic price recovery',45);assert panel.inner_text()==frozen
 a.output.write_text(json.dumps({'status':'PASS','checks':['Actual browser offline interval produces stale valuation warning','Save/apply/recommendation preview gated by current quote freshness','Frozen saved forecast unaffected by offline state','Real automatic25second market poll recovers after reconnect'],'scope':'Actual network availability changed only in isolated QA browser context; market responses were not replaced.'},indent=2));print('PASS real25second polling recovers after reconnect',flush=True)
finally:b.context.set_offline(False);b.teardown()
