#!/usr/bin/env python3
"""Offline, genuine-history ridge parity. No HTTP, credentials or trading calls."""
import argparse
import calendar
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ('BTC', 'ETH', 'LINK')
NODE = r'''
const fs=require('fs'),path=require('path'),ts=require(process.cwd()+'/app/node_modules/typescript');
const cache={};
function load(file){
 file=path.resolve(file);if(cache[file])return cache[file].exports;
 const m={exports:{}};cache[file]=m;
 const js=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
 new Function('require','module','exports',js)(name=>name.startsWith('.')?load(path.resolve(path.dirname(file),name+'.ts')):require(name),m,m.exports);return m.exports;
}
const api=load('app/src/lib/rotation/forecast-advice.ts');
const inputs=JSON.parse(fs.readFileSync(0,'utf8'));
console.log(JSON.stringify(inputs.map(c=>{try{return {value:api.fitForecast(c.dataset,c.cadence,new Date(c.now))}}catch(e){return {error:e.message}}})));
'''


def end_date(date, cadence):
    if cadence == 'weekly':
        return date + dt.timedelta(days=8)
    month = date.month % 12 + 1
    year = date.year + (date.month == 12)
    return dt.date(year, month, min(date.day, calendar.monthrange(year, month)[1])) + dt.timedelta(days=1)


def independently_fit(points, cadence):
    prices = np.array([[p['prices'][a] for a in ASSETS] for p in points])
    dates = [dt.date.fromisoformat(p['date']) + dt.timedelta(days=1) for p in points]
    lookup = {date: i for i, date in enumerate(dates)}
    through = len(points) - 1
    features = {}
    log_prices = np.log(prices)
    for i in range(199, len(points)):
        features[i] = np.column_stack([
            *(log_prices[i] - log_prices[i - lag] for lag in (7, 30, 90)),
            np.diff(log_prices[i - 30:i + 1], axis=0).std(axis=0, ddof=1),
            np.log(prices[i] / prices[i - 199:i + 1].mean(axis=0)),
        ])
    origins = [i for i in range(max(199, through - 730), through)
               if end_date(dates[i], cadence) in lookup and lookup[end_date(dates[i], cadence)] < through]
    x = np.concatenate([features[i] for i in origins])
    y = np.concatenate([prices[lookup[end_date(dates[i], cadence)]] / prices[i + 1] - 1 for i in origins])
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale < 1e-12] = 1
    z = (x - mean) / scale
    # Independent augmented least squares, rather than the app's normal-equation elimination.
    members = {}
    for alpha in (1, 10):
        design = np.vstack([z, np.eye(5) * np.sqrt(len(z) * alpha)])
        target = np.concatenate([y - y.mean(), np.zeros(5)])
        beta = np.linalg.lstsq(design, target, rcond=None)[0]
        members[str(alpha)] = np.maximum(-1, y.mean() + (features[through] - mean) / scale @ beta)
    return members, origins, max(end_date(dates[i], cadence) for i in origins)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.data.read_text())
    rows = source['rows']
    cases, expected = [], []
    for count in (500, 719, 1400, len(rows)):
        for cadence in ('weekly', 'monthly'):
            points = [{k: row[k] for k in ('date', 'prices')} for row in rows[:count]]
            now = (dt.date.fromisoformat(points[-1]['date']) + dt.timedelta(days=1)).isoformat() + 'T12:00:00Z'
            cases.append(dict(dataset={'points': points}, cadence=cadence, now=now))
            expected.append(independently_fit(points, cadence))
    valid_count = len(cases)
    for name in ('insufficient', 'gap', 'invalid-price', 'future', 'stale'):
        case = json.loads(json.dumps(cases[0]))
        if name == 'insufficient': case['dataset']['points'] = case['dataset']['points'][-100:]
        if name == 'gap': case['dataset']['points'].pop(250)
        if name == 'invalid-price': case['dataset']['points'][250]['prices']['BTC'] = -1
        if name == 'future': case['now'] = case['dataset']['points'][-1]['date'] + 'T12:00:00Z'
        if name == 'stale': case['now'] = (dt.date.fromisoformat(case['now'][:10]) + dt.timedelta(days=3)).isoformat() + 'T12:00:00Z'
        case['test'] = name
        cases.append(case)
    # Future data is invalid by API contract: both ordinary and perturbed future prices must be rejected.
    for multiplier in (1, 100):
        case = json.loads(json.dumps(cases[0]))
        case['dataset']['points'].append({'date': rows[500]['date'], 'prices': {a: rows[500]['prices'][a] * multiplier for a in ASSETS}})
        cases.append(case)
    result = subprocess.run(['node', '-e', NODE], input=json.dumps(cases), text=True, capture_output=True, cwd=ROOT, check=True)
    outputs = json.loads(result.stdout)
    error_max = 0.
    for case, output, reference in zip(cases[:valid_count], outputs[:valid_count], expected):
        assert 'value' in output, output
        value = output['value']; members, origins, end = reference
        assert value['trainingOrigins'] == len(origins)
        assert value['latestTrainingEnd'][:10] == end.isoformat()
        assert value['latestTrainingEnd'] < value['signalAt']
        for alpha in ('1', '10'):
            actual = np.array([value['members'][alpha][a] for a in ASSETS])
            error_max = max(error_max, float(np.max(np.abs(actual - members[alpha]))))
            assert np.allclose(actual, members[alpha], atol=1e-11, rtol=1e-11)
        assert np.allclose([value['forecastReturns'][a] for a in ASSETS], (members['1'] + members['10']) / 2, atol=1e-11)
    assert all('error' in output for output in outputs[valid_count:]), outputs[valid_count:]
    report = {'status': 'PASS', 'genuine_history_parity_cases': valid_count, 'invalid_or_future_cases_rejected': len(cases)-valid_count,
              'maximum_prediction_error': error_max, 'data_sha256': hashlib.sha256(args.data.read_bytes()).hexdigest(),
              'helper_sha256': hashlib.sha256((ROOT/'app/src/lib/rotation/forecast-advice.ts').read_bytes()).hexdigest(),
              'method': 'Independent numpy augmented least squares; completed-close labels; pooled assets; all forecast members and ensemble checked.',
              'scope': 'Offline mathematical verification only. Invalid future inputs are rejected, not silently consumed. No forecast performance claim.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
