#!/usr/bin/env python3
"""Deterministic QA Agent browser flow for real, isolated paper strategy study.
No model inference, synthetic market data, production endpoint, or real order.
"""
import argparse
import json
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
sys.path.insert(0, str(Path.home() / 'projects/qa-agent'))
from executors.web import WebExecutor


def run(url, account_file, report_dir, workshop_preview=False, protection_file=None, slippage=10):
    parsed = urlparse(url)
    local = url == 'http://127.0.0.1:3218/rotation'
    preview = workshop_preview and parsed.scheme == 'https' and not parsed.port and bool(re.fullmatch(r'wolf-pack-[a-z0-9]{9}-danman60s-projects\.vercel\.app', parsed.hostname or '')) and parsed.path == '/rotation' and not parsed.query and not parsed.fragment and not parsed.username
    if not (local or preview):
        raise ValueError('Explicit localhost3218 or authorized immutable Preview /rotation required. Stable production refused.')
    print(f'QA target: {url}', flush=True)
    origin = url.removesuffix('/rotation')
    report_dir.mkdir(parents=True, exist_ok=True)
    browser = WebExecutor()
    evidence = {'url': url, 'checks': [], 'screenshots': [], 'startedEastern': datetime.now(ZoneInfo('America/New_York')).isoformat()}
    responses = []
    def check(name, detail=None):
        evidence['checks'].append({'check': name, 'status': 'PASS', 'detail': detail})
        print(f'PASS {name}', flush=True)
    def until(probe, message, seconds=100):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            browser.snapshot()  # Pump synchronous browser events before response-based assertions.
            result = probe()
            if result: return result
            time.sleep(.2)
        raise AssertionError(message)
    def get(path):
        response = browser.context.request.get(origin + '/api/rotation/' + path)
        assert response.ok, f'GET {path}: {response.status}'
        return response.json()
    def reject(path, body, status, fragment):
        response = browser.context.request.post(origin + '/api/rotation/' + path, data=body, headers={'Origin':origin})
        assert response.status == status, f'{path}: expected {status}, got {response.status}'
        assert fragment.lower() in response.json()['error'].lower(), response.json()['error']
    def click(name):
        result = browser.click('button', name)
        assert result[0], result[1]
    def fill(name, value):
        options = re.findall(r'(textbox|spinbutton|combobox) "([^"\n]+)"', browser.snapshot())
        role, label = next((role, label) for role, label in options if label.startswith(name))
        result = browser.fill(role, label, value)
        assert result[0], result[1]
    def capture(tag):
        for width in (1440, 390):
            browser.set_viewport(width, 1000 if width == 1440 else 844)
            time.sleep(.6)
            size = browser.page.evaluate('({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})')
            assert size['client'] == size['scroll'], f'Overflow {tag} {width}: {size}'
            browser.set_viewport(width, browser.page.evaluate('document.documentElement.scrollHeight'))
            browser.page.evaluate('window.scrollTo(0,0)')
            time.sleep(.2)
            path = report_dir / f'{tag}-{width}.png'
            browser.screenshot(str(path))
            source = (Path.home() / '.local/bin/shot').read_text()
            checks = browser.page.evaluate(source.split('const domChecks = ', 1)[1].split(';\n\nconst browser', 1)[0])
            browser.page.add_script_tag(content=(Path.home() / '.claude/tools/shot/node_modules/axe-core/axe.min.js').read_text())
            violations = browser.page.evaluate("async()=> (await window.axe.run(document,{runOnly:['color-contrast']})).violations")
            for violation in violations:
                for node in violation['nodes']:
                    checks['fail'].append({'check':'contrast','el':' '.join(node['target']),'detail':violation['help']})
            stamp = datetime.now(ZoneInfo('America/New_York')).strftime('%Y%m%dT%H%M%S')
            held = Path.home() / f'.claude/shots/pending/wolfpack-strategy-{tag}-{width}-{stamp}.png'
            shutil.copyfile(path, held)
            review = {'url':url,'width':width,'png':str(held),'captured':datetime.now(ZoneInfo('America/New_York')).isoformat(),'pass':not checks['fail'],**checks}
            Path(str(held)+'.review.json').write_text(json.dumps(review, indent=2))
            evidence['screenshots'].append(review)
            assert review['pass'], f'Mechanical review failed: {checks["fail"]}'
        browser.set_viewport(1440, 1000)
    def collect(response):
        if response.url.startswith(origin+'/api/rotation/trials') and response.request.method == 'POST' and response.ok:
            responses.append(response.json()['trial'])
    try:
        assert browser.setup()
        assert local, 'Direct advice QA is localhost only'
        browser.set_viewport(1440,1000)
        browser.page.on('response', collect)
        assert browser.navigate(url)
        until(lambda:'Sign in' in browser.snapshot(), 'Login did not render')
        account = json.loads(account_file.read_text())['isolation']
        fill('Email', account['email']); fill('Password', account['password']); click('Sign in')
        until(lambda:'My plan' in browser.snapshot(), 'Workspace did not render')
        until(lambda:'Loading saved preferences' not in browser.snapshot(), 'Advice restore pending')
        readiness=get('readiness'); assert readiness['liveTrading']=='disabled'
        assert get('session')['user']['email']==account['email']
        before=get('portfolio')['portfolio']; assert before
        old_ids=[row['id'] for row in get('trials?strategy=1')['trials']]
        check('real isolated paper sign-in; live trading disabled')
        if 'Change preferences' in browser.snapshot(): click('Change preferences')
        fill('Target crypto allocation (%)','60'); fill('Adverse slippage (bps)',str(slippage))
        click('Refresh recommendation' if get('trials?forecast=1')['trial'] else 'Get my recommendation')
        until(lambda:any(row['data'].get('namespace')=='forecast-advice' for row in responses), 'Direct advice did not save', 120)
        trial=[row for row in responses if row['data'].get('namespace')=='forecast-advice'][-1]
        data=trial['data']; report=data['report']
        (report_dir/'advice-trial.json').write_text(json.dumps(trial,indent=2))
        assert len(data['dataset']['points']) >= 460 and data['market']['books']
        assert data['startingBalances']==before['balances']
        assert len(report['candidates'])==5 and data['memberForecasts']
        assert data['portfolioRevision']==before['revision']
        assert data['config']=={'riskPercent':60,'slippageBps':slippage,'cadence':before['cadence'],'feeBps':before['feeBps']}
        assert get('portfolio')['portfolio']==before, 'Advice mutated financial ledger'
        assert set(old_ids).issubset({row['id'] for row in get('trials?strategy=1')['trials']})
        check('one direct request saves advice without financial mutation or old-record replacement', {'trialId':trial['id'],'decision':report['decision']})
        assert report['decision']!='unavailable', report['reasons']
        assert abs(sum(report['targetValuesCad'].values())-report['currentValueCad']) <= report['feesCad']+report['currentValueCad']*.1
        assert abs(report['expectedTargetValueCad']-report['expectedHoldValueCad']-report['expectedAdvantageCad'])<1e-7
        assert 'Chart-based return estimates' in browser.snapshot()
        click('Change preferences'); fill('Target crypto allocation (%)','61')
        assert 'Preferences changed' in browser.snapshot()
        action_label='Record recommended HOLD' if report['decision']=='hold' else 'Review fresh quote'
        assert browser.page.get_by_role('button',name=action_label,exact=True).is_disabled()
        fill('Target crypto allocation (%)','60'); click('Close settings')
        check('changed preferences disable prior advice actions until recomputed')
        capture('direct-advice')
        # Refresh immediately before any action: book-derived advice intentionally expires quickly.
        click('Refresh recommendation')
        until(lambda:len([r for r in responses if r['data'].get('namespace')=='forecast-advice'])>=2,'Advice refresh failed')
        report=[r for r in responses if r['data'].get('namespace')=='forecast-advice'][-1]['data']['report']
        if report['decision']=='hold':
            assert report['nextShift'] is None and report['feesCad']==0 and report['slippageCad']==0
            assert all(abs(v)<1e-8 for v in report['deltaCad'].values())
            click('Record recommended HOLD')
            until(lambda:get('portfolio')['portfolio']['revision']==before['revision']+1,'HOLD was not recorded')
            after=get('portfolio')['portfolio']
            for field in ('balances','baseline','feesCad','netFlowsCad'): assert before[field]==after[field], field
            check('genuine cost-aware HOLD preserves all units and costs; live SHIFT unobserved')
        elif report['decision']=='shift':
            assert report['expectedAdvantageCad']>.01 and report['nextShift']
            click('Review fresh quote')
            until(lambda:'Approve paper shift' in browser.snapshot(),'Fresh quote did not render')
            assert get('portfolio')['portfolio']==before
            check('genuine SHIFT opens canonical fresh quote without mutation', {'nextShift':report['nextShift']})
            # Approve the quote visible in the UI; reconcile against the persisted consumed preview export.
            click('Approve paper shift')
            until(lambda:get('portfolio')['portfolio']['revision']==before['revision']+1,'Paper approval did not persist')
            after=get('portfolio')['portfolio']; exported=get('portfolio?export=1')
            consumed=[r['data'] for r in exported['previews'] if r['data']['revision']==before['revision']]
            assert len(consumed)==1
            q=consumed[0]; assert after['balances']==q['after']
            assert abs(float(after['feesCad'])-float(before['feesCad'])-float(q['feeCad']))<1e-7
            assert after['events'][-1]['kind']=='shift'
            reject('action',{'kind':'approve','expectedRevision':before['revision'],'previewId':q['id']},409,'changed')
            check('explicit UI approval matches consumed quote balances and fees; stale revision rejected')
        else: raise AssertionError(report['reasons'])
        assert get('portfolio')['portfolio']==after
        assert browser.navigate(url)
        until(lambda:'Chart-based return estimates' in browser.snapshot(),'Advice did not restore')
        assert get('portfolio')['portfolio']==after
        assert 'Holdings changed or this estimate expired' in browser.snapshot()
        click('Refresh recommendation')
        until(lambda:get('trials?forecast=1')['trial']['data']['portfolioRevision']==after['revision'],'Refresh did not bind new revision')
        check('saved advice restores; changed holdings require refresh; saved preferences reused')
        capture('restored-advice')
        browser.page.get_by_text('Saved momentum studies and previous plans',exact=True).click()
        until(lambda:'Backtest & build my plan' in browser.snapshot(),'Legacy study panel unavailable')
        check('legacy study UI and immutable records remain accessible')
        click('Advanced research')
        until(lambda:'Register scenario' in browser.snapshot(),'Advanced research unavailable')
        check('advanced research remains accessible')
        if slippage != 10:
            assert browser.navigate(url)
            until(lambda:'Change preferences' in browser.snapshot(),'Advice did not restore')
            click('Change preferences');fill('Adverse slippage (bps)','10');click('Refresh recommendation')
            until(lambda:get('trials?forecast=1')['trial']['data']['config']['slippageBps']==10,'Test preference restore failed')
            assert get('portfolio')['portfolio']==after
            check('restored standard test slippage allowance without financial mutation')
        evidence['consoleErrors']=browser.get_console_errors(False)
        assert not evidence['consoleErrors'], evidence['consoleErrors']
        evidence['status']='PASS'; return 0
    except Exception as error:
        evidence['status']='FAIL'; evidence['error']=str(error); print(f'FAIL {error}',flush=True)
        if browser.page:
            (report_dir/'failure.aria.txt').write_text(browser.snapshot()); browser.screenshot(str(report_dir/'failure.png'))
        return 1
    finally:
        (report_dir/'checks.json').write_text(json.dumps(evidence,indent=2)); browser.teardown()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    parser.add_argument('--account-file',required=True,type=Path)
    parser.add_argument('--report-dir',required=True,type=Path)
    parser.add_argument('--slippage',type=int,default=10,choices=range(0,1001))
    args=parser.parse_args()
    raise SystemExit(run(args.url,args.account_file,args.report_dir,slippage=args.slippage))
