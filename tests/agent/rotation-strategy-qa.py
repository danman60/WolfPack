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


def run(url, account_file, report_dir, workshop_preview=False, protection_file=None):
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
        if protection_file:
            assert workshop_preview
            protected = browser.context.request.get(url, headers={'x-vercel-protection-bypass':protection_file.read_text().strip(),'x-vercel-set-bypass-cookie':'true'})
            assert protected.ok, f'Preview protection access failed: {protected.status}'
        browser.set_viewport(1440,1000)
        browser.page.on('response', collect)
        assert browser.navigate(url)
        until(lambda:'Sign in' in browser.snapshot(), 'Login did not render')
        account = json.loads(account_file.read_text())['isolation']
        fill('Email', account['email']); fill('Password', account['password']); click('Sign in')
        until(lambda:'My plan' in browser.snapshot(), 'Paper workspace did not render')
        readiness = get('readiness')
        assert readiness['mode']=='paper-workshop' and readiness['liveTrading']=='disabled'
        session = get('session'); assert session['user']['email']==account['email']
        state = get('portfolio'); before = state['portfolio']; assert before
        until(lambda:'Loading your saved strategy' not in browser.snapshot(), 'Strategy restore did not complete')
        check('real seeded isolated paper session; no live execution', {'portfolioRevision':before['revision']})
        # Real browser inputs; owner scenario values are explicit QA parameters.
        fill('Target crypto allocation when shifting', '60'); fill('Adverse slippage', '10')
        click('Backtest & build my plan')
        until(lambda:any(row['kind']=='development' and row['data']['purpose']=='study' for row in responses), 'Programmatic study failed')
        study = next(row for row in responses if row['kind']=='development' and row['data']['purpose']=='study')
        report = study['data']['report']
        assert {row['lookbackDays'] for row in report['candidates']} == {14,30,60,90,180}
        assert report['candidateCount']==5 and report['status']=='retrospective-unvalidated'
        assert report['config']['cadence']==before['cadence'] and report['config']['feeBps']==before['feeBps']
        assert report['config']['riskPercent']==60 and report['config']['slippageBps']==10
        assert get('portfolio')['portfolio']==before, 'Backtest changed financial ledger'
        until(lambda:'Backtest complete — review and adopt' in browser.snapshot(), 'Completed study not visible')
        check('five-window programmatic study with unchanged ledger', {'studyId':study['id'],'outer':report['outer']['metrics'],'decision':report['plan']['status']})
        click('Use this strategy')
        until(lambda:any(row['kind']=='development' and row['data']['purpose']=='recommendation' for row in responses), 'Adoption/recommendation failed')
        recommendation = next(row for row in responses if row['kind']=='development' and row['data']['purpose']=='recommendation')
        state = get('portfolio')
        assert state['planState']['activePlanId']==study['id']
        assert state['portfolio']==before
        assert recommendation['data']['planId']==study['id'] and recommendation['data']['portfolioRevision']==before['revision']
        paired = recommendation['data']['report']['plan']['paired']
        if paired:
            assert abs(paired['shift']['meanCad']-paired['hold']['meanCad']-paired['advantage']['meanCad']) < .000001
            for label in ('Shift minus HOLD','Downside · 10th percentile','Historical mean profit / loss'):
                assert label in browser.snapshot()
        check('explicit adoption; recommendation anchored to current ledger and plan', {'planRevision':state['planState']['planRevision'],'decision':recommendation['data']['decision'],'paired':paired})
        capture('computed-plan')
        decision = recommendation['data']['decision']
        if decision == 'hold':
            click('Record recommended HOLD')
            until(lambda:get('portfolio')['portfolio']['revision']==before['revision']+1,'Recommended HOLD not persisted')
            after = get('portfolio')['portfolio']
            for field in ('balances','baseline','feesCad','netFlowsCad'):
                assert after[field]==before[field], f'HOLD changed {field}'
            assert after['events'][:-1]==before['events']
            check('recommended HOLD records once and preserves all units/costs')
            reject('action', {'kind':'hold','recommendationId':recommendation['id'],'expectedRevision':after['revision'],'expectedPlanRevision':state['planState']['planRevision']}, 409, 'changed')
            assert get('portfolio')['portfolio']==after
            check('reused recommended HOLD rejected against current financial revision')
        elif decision == 'shift':
            click('Review fresh quote')
            until(lambda:'Approve paper shift' in browser.snapshot(),'Bound quote did not render')
            assert get('portfolio')['portfolio']==before
            check('recommendation opens canonical fresh quote without trade', {'nextShift':recommendation['data']['nextShift']})
            after = before
        else:
            assert 'No executable quote is ready' in browser.snapshot()
            assert 'Record recommended HOLD' not in browser.snapshot()
            check('blocked shift remains distinct from model HOLD')
            after = before
        if decision=='hold':
            until(lambda:'This recommendation expired' in browser.snapshot(),'Old recommendation not visibly stale')
            assert browser.page.get_by_role('button',name='Record recommended HOLD',exact=True).is_disabled()
            click('Refresh recommendation')
            until(lambda:len([row for row in responses if row['kind']=='development' and row['data']['purpose']=='recommendation'])==2,'Refresh did not compute new recommendation')
            check('financial revision invalidates stale action; refresh recomputes current plan')
        latest = [row for row in responses if row['kind']=='development' and row['data']['purpose']=='recommendation'][-1]
        reject('preview', {'recommendationId':latest['id'],'expectedRevision':after['revision'],'expectedPlanRevision':state['planState']['planRevision'],'from':'CAD','to':'BTC','amount':'1'}, 400, 'override')
        assert get('portfolio')['portfolio']==after
        check('recommendation quote rejects client economics overrides')
        legacy = get('trials')['trials']
        strategy = get('trials?strategy=1')['trials']
        assert set(row['id'] for row in legacy).isdisjoint(row['id'] for row in strategy)
        check('advanced research and strategy trial namespaces remain separate', {'advanced':len(legacy),'strategy':len(strategy)})
        assert browser.navigate(url)
        until(lambda:'Your plan for this review' in browser.snapshot(),'Saved plan did not restore on reload')
        assert get('portfolio')['portfolio']==after
        assert get('portfolio')['planState']['activePlanId']==study['id']
        exported = get('portfolio?export=1')
        assert any(row['id']==study['id'] for row in exported['trials'])
        assert any(row['id']==recommendation['id'] for row in exported['trials'])
        check('reload restores strategy/recommendation and export retains immutable evidence')
        capture('restored-plan')
        click('Advanced research')
        until(lambda:'Register scenario' in browser.snapshot(),'Existing advanced research not accessible')
        check('existing advanced research remains accessible')
        evidence['consoleErrors']=browser.get_console_errors(False)
        assert not evidence['consoleErrors'], f'Browser console errors: {evidence["consoleErrors"]}'
        browser.context.storage_state(path=str(report_dir/'browser-session.json'))
        (report_dir/'browser-session.json').chmod(0o600)
        evidence['status']='PASS'; return 0
    except Exception as error:
        evidence['status']='FAIL'; evidence['error']=str(error); print(f'FAIL {error}',flush=True)
        if browser.page:
            (report_dir/'failure.aria.txt').write_text(browser.snapshot())
            browser.screenshot(str(report_dir/'failure.png'))
        return 1
    finally:
        (report_dir/'checks.json').write_text(json.dumps(evidence,indent=2))
        browser.teardown()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    parser.add_argument('--account-file',required=True,type=Path)
    parser.add_argument('--report-dir',required=True,type=Path)
    parser.add_argument('--workshop-preview',action='store_true')
    parser.add_argument('--protection-file',type=Path)
    args=parser.parse_args()
    raise SystemExit(run(args.url,args.account_file,args.report_dir,args.workshop_preview,args.protection_file))
