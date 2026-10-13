#!/usr/bin/env python3
"""Independent close-indicator parity and bounded sentiment parsing controls."""
import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('advice_numerics', Path(__file__).with_name('rotation-advice-numerics.py'))
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
LOADER = common.NODE[:common.NODE.index('const api=load')]


def independent_ema(values, period):
    # Explicit geometric weights, independently of the TypeScript recursive update.
    alpha = 2 / (period + 1)
    beta = 1 - alpha
    seed = np.mean(values[:period])
    return np.array([seed * beta ** n + alpha * np.dot(values[period:period+n], beta ** np.arange(n-1, -1, -1)) for n in range(len(values)-period+1)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    rows = json.loads(args.data.read_text())['rows'][-719:]
    now = (dt.date.fromisoformat(rows[-1]['date']) + dt.timedelta(days=1)).isoformat()+'T12:00:00Z'
    code = LOADER + r'''
const ta=load('app/src/lib/rotation/technical-analysis.ts'),news=load('app/src/lib/rotation/sentiment.ts'),assert=require('node:assert/strict');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const output=ta.buildTechnicalPairs({points:input.rows},new Date(input.now));
assert.equal(ta.closeIndicators(Array(220).fill(10)).rsi,50);
assert.equal(ta.closeIndicators(Array.from({length:220},(_,i)=>i+1)).rsi,100);
assert.equal(ta.closeIndicators(Array.from({length:220},(_,i)=>220-i)).rsi,0);
const spike=Array.from({length:220},(_,i)=>i+1);spike[219]=9999;assert.equal(ta.closeIndicators(spike).resistanceZone.high,219);
const future=structuredClone(input.rows);future.push({date:input.now.slice(0,10),prices:{BTC:999999,ETH:99999,LINK:9999}});
assert.throws(()=>ta.buildTechnicalPairs({points:future},new Date(input.now)),/unfinished/);
const gap=structuredClone(input.rows);gap.splice(300,1);assert.throws(()=>ta.buildTechnicalPairs({points:gap},new Date(input.now)),/consecutive/);
const now=new Date('2026-10-13T16:00:00Z');
const item=(title,date,url='https://coindesk.com/test')=>`<item><title><![CDATA[${title}]]></title><link>${url}</link><pubDate>${date}</pubDate></item>`;
const xml='<rss><channel>'+item('Bitcoin gains; Chainlink upgrade','Tue, 13 Oct 2026 12:00:00 GMT')+item('Ethereum losses','Wed, 14 Oct 2026 12:00:00 GMT')+item('Bitcoin crash','Tue, 01 Sep 2026 12:00:00 GMT')+item('Bitcoin gains','Tue, 13 Oct 2026 12:00:00 GMT','https://evil.test/')+'</channel></rss>';
const articles=news.parseHeadlines(xml,'CoinDesk','coindesk.com',now);assert.equal(articles.length,1);assert.deepEqual(articles[0].assets,['BTC','LINK']);assert.equal(articles[0].score,1);
const summary=news.summarizeHeadlines([...articles,...articles],true);assert.equal(summary.BTC.headlineCount,1);assert.equal(summary.ETH.score,null);assert.equal(summary.ETH.status,'unavailable');
assert.equal(news.headlineTone('Bitcoin not bullish').score,-1);
assert.throws(()=>news.parseHeadlines('<rss>broken','CoinDesk','coindesk.com',now),/unsupported/);
console.log(JSON.stringify(output));
'''
    output = json.loads(subprocess.run(['node', '-e', code], input=json.dumps({'rows': rows, 'now': now}), cwd=ROOT, text=True, capture_output=True, check=True).stdout)
    errors = []
    for pair in output['pairs']:
        values = np.array([row['prices'][pair['base']] / (1 if pair['quote']=='CAD' else row['prices'][pair['quote']]) for row in rows])
        assert np.allclose(values, [p['value'] for p in pair['series']], atol=0, rtol=1e-15)
        ta = pair['technical']; delta = np.diff(values); m = len(delta)-14; beta = 13/14
        gain = np.maximum(delta, 0); loss = np.maximum(-delta, 0)
        g = gain[:14].mean()*beta**m + np.dot(gain[14:]/14, beta**np.arange(m-1,-1,-1))
        l = loss[:14].mean()*beta**m + np.dot(loss[14:]/14, beta**np.arange(m-1,-1,-1))
        rsi = 50 if g==l==0 else 100 if l==0 else 100-100/(1+g/l)
        macd = independent_ema(values,12)[14:]-independent_ema(values,26)
        signal = independent_ema(macd,9)[-1]
        expected = [rsi, macd[-1], signal, macd[-1]-signal, *[values[-p:].mean() for p in (20,50,200)], min(values[-61:-1]), min(values[-21:-1]), max(values[-21:-1]), max(values[-61:-1])]
        actual = [ta['rsi'],ta['macd']['line'],ta['macd']['signal'],ta['macd']['histogram'],*[ta['movingAverages'][f'sma{p}'] for p in (20,50,200)],ta['supportZone']['low'],ta['supportZone']['high'],ta['resistanceZone']['low'],ta['resistanceZone']['high']]
        assert np.allclose(actual,expected,rtol=1e-10,atol=1e-10), (pair['id'],actual,expected)
        errors.append(float(np.max(np.abs(np.array(actual)-expected))))
    assert len(output['pairs'])==6
    report={'status':'PASS','genuine_history_pairs':6,'indicator_values_compared':66,'maximum_absolute_indicator_error':max(errors),'controls':['flat/rising/falling RSI','latest excluded from prior closing zones','future observation rejected','date gap rejected','explicit headline asset attribution','future/stale/foreign-host headline exclusion','deduplication','unavailable asset score remains null','negation handling','malformed RSS rejected'],'scope':'Numerical and parsing verification, not predictive performance evidence.'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
