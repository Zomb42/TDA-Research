"""Bounded GET-only QQQ/VIX research context; existing paper credentials stay private.

Run in the tda environment. Original stock panels are never modified.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.parse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'market_data/datasets/mean_reversion_context_2026-11-04'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    local = json.loads((ROOT / 'market_data/.alpaca-paper.local.json').read_text())
    headers = {k: os.environ.get(v) or local[v] for k, v in [
        ('APCA-API-KEY-ID', 'APCA_API_KEY_ID'),
        ('APCA-API-SECRET-KEY', 'APCA_API_SECRET_KEY')]}
    requests = []
    for adjustment in ['all', 'raw']:
        params = dict(symbols='QQQ', timeframe='1Day', start='2016-01-01T00:00:00-05:00',
                      end='2026-10-27T23:59:59-04:00', asof='2026-10-28',
                      feed='sip', adjustment=adjustment, limit=10000, sort='asc')
        rows, tokens = [], set()
        while True:
            url = 'https://data.alpaca.markets/v2/stocks/bars?' + urllib.parse.urlencode(params)
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45) as res:
                payload = json.load(res)
            page = len(requests) + 1
            (OUT / f'response_{adjustment}_{page:03}.json').write_text(json.dumps(payload))
            requests.append(dict(url=url, received_at=datetime.now(timezone.utc).isoformat()))
            rows.extend(payload.get('bars', {}).get('QQQ', []))
            token = payload.get('next_page_token')
            if not token:
                break
            assert token not in tokens
            tokens.add(token)
            params['page_token'] = token
        frame = pd.DataFrame(rows)
        frame['date'] = pd.to_datetime(frame.t, utc=True).dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
        frame.insert(0, 'symbol', 'QQQ')
        assert not frame.date.duplicated().any()
        expected = pd.read_csv(ROOT / 'market_data/datasets/equity_daily_expanded_2016_2026-10-27/close_all.csv', usecols=['date']).date
        assert frame.date.tolist() == expected.tolist()
        assert (frame[['o', 'h', 'l', 'c']] > 0).all().all()
        assert ((frame.l <= frame[['o', 'c']].min(axis=1)) & (frame.h >= frame[['o', 'c']].max(axis=1))).all()
        frame.to_csv(OUT / f'bars_{adjustment}.csv', index=False)
        print(adjustment, len(frame), frame.date.iloc[0], frame.date.iloc[-1], flush=True)
    url = 'https://cdn-api.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv'
    with urllib.request.urlopen(url, timeout=45) as res:
        raw = res.read()
    (OUT / 'vix_source.csv').write_bytes(raw)
    vix = pd.read_csv(OUT / 'vix_source.csv')
    vix.columns = vix.columns.str.strip().str.lower()
    vix['date'] = pd.to_datetime(vix.date).dt.strftime('%Y-%m-%d')
    assert not vix.date.duplicated().any()
    assert (vix.close > 0).all()
    vix.to_csv(OUT / 'vix_daily.csv', index=False)
    manifest = dict(retrieved_at=datetime.now(timezone.utc).isoformat(), requests=requests,
                    vix_url=url, vix_rows=len(vix), vix_first=vix.date.min(), vix_last=vix.date.max(),
                    qqq_sessions=len(frame), calendar_matches_existing_panel=True,
                    history_end='2026-10-27', purpose='Exploratory index mean-reversion and lagged VIX context',
                    sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in OUT.glob('*.csv')})
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('VIX', len(vix), vix.date.min(), vix.date.max(), flush=True)


if __name__ == '__main__':
    main()
