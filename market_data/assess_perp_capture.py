"""Read-only descriptive capture/storage/liquidity comparison; no network.

The November perp and April HFT samples are not contemporaneous. Binary bid
cash, perp displayed notional, and spot best quotes have different meanings.
Private HFT message payloads are never exported. Originals remain unchanged.
"""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal as D
import csv
import json
from pathlib import Path

import numpy as np

from record_kalshi_btc_stream import PerpBook

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "market_data/samples/kalshi_btc_stream_2026-11-04_10min"
HFT = ROOT.parents[1] / "Junior-Spring/HFT/Kalshi-Orderbook-Predictor"
OUT = ROOT / "liquidity/experiments/perp_capture_assessment_2026_11_04"


def distribution(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return None
    return dict(n=len(values), min=float(values.min()), p10=float(np.quantile(values,.1)),
                median=float(np.median(values)), p90=float(np.quantile(values,.9)), max=float(values.max()))


def summarize(rows):
    keys = sorted(set().union(*(r.keys() for r in rows))) if rows else []
    return {k: distribution([r[k] for r in rows if k in r]) for k in keys if k != "timestamp"}


def write_csv(name, rows):
    fields = sorted(set().union(*(row.keys() for row in rows))) if rows else []
    with (OUT/name).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def linear_book_metrics(sides, contract_size):
    bid, ask = max(sides['bid']), min(sides['ask'])
    mid = (bid+ask)/2
    result = dict(bid_levels=len(sides['bid']), ask_levels=len(sides['ask']),
                  total_levels=sum(map(len,sides.values())), mid_usd_btc=float(mid/contract_size),
                  spread_bps=float((ask-bid)/mid*10000),
                  top_bid_btc=float(sides['bid'][bid]*contract_size),
                  top_ask_btc=float(sides['ask'][ask]*contract_size),
                  top_two_sided_notional_usd=float(bid*sides['bid'][bid]+ask*sides['ask'][ask]))
    for side,levels in sides.items():
        result[side+'_btc'] = float(sum(levels.values(),D(0))*contract_size)
        result[side+'_notional_usd'] = float(sum((p*q for p,q in levels.items()),D(0)))
    result['total_btc'] = result['bid_btc']+result['ask_btc']
    result['total_notional_usd'] = result['bid_notional_usd']+result['ask_notional_usd']
    for bps in [10,25,50,100]:
        fraction = D(bps)/10000
        for side, levels in sides.items():
            selected = [(p,q) for p,q in levels.items() if abs(p-mid)/mid <= fraction]
            result[f'{side}_within_{bps}bps_usd'] = float(sum((p*q for p,q in selected),D(0)))
        result[f'total_within_{bps}bps_usd'] = result[f'bid_within_{bps}bps_usd']+result[f'ask_within_{bps}bps_usd']
    return result


def perp_assessment():
    manifest = json.loads((CAPTURE/'manifest.json').read_text())
    meta = json.loads((CAPTURE/'market.json').read_text())['market']
    contract = D(meta['contract_size'])
    unique = {'bid': set(), 'ask': set()}
    counts = {'bid': [], 'ask': [], 'combined': []}
    book = PerpBook(); traded_contracts = traded_notional = D(0)
    for line in (CAPTURE/'messages.jsonl').open():
        row = json.loads(line); event = row.get('message', {})
        if not event:
            continue
        if event['type']=='trade':
            msg=event['msg']; quantity=D(msg['count'])
            traded_contracts += quantity; traded_notional += quantity*D(msg['price'])
        if book.apply(event):
            if event['type']=='orderbook_snapshot':
                for side in unique: unique[side].update(book.sides[side])
            else:
                msg=event['msg']; p=D(msg['price']); side=msg['side']
                if book.sides[side].get(p,D(0))>0: unique[side].add(p)
            counts['bid'].append(len(book.sides['bid']));counts['ask'].append(len(book.sides['ask']))
            counts['combined'].append(sum(map(len,book.sides.values())))
    points=[]
    for line in (CAPTURE/'checkpoints.jsonl').open():
        row=json.loads(line)
        sides={side:{D(p):D(q) for p,q in row[side]} for side in unique}
        if not all(sides.values()): continue
        points.append(dict(timestamp=row['received_at'],**linear_book_metrics(sides,contract)))
    write_csv('perp_checkpoint_liquidity.csv',points)
    raw=sum((CAPTURE/name).stat().st_size for name in ['messages.jsonl','checkpoints.jsonl'])
    compressed=sum((CAPTURE/'raw/original_gzip'/name).stat().st_size for name in ['messages.jsonl.gz','checkpoints.jsonl.gz'])
    result=dict(instrument=manifest['ticker'],start_utc=manifest['started_at'],contract_btc=float(contract),
                levels_after_each_book_message={side:distribution(v) for side,v in counts.items()},
                unique_occupied_prices={side:len(v) for side,v in unique.items()},
                unique_occupied_prices_combined=len(unique['bid']|unique['ask']),
                lowest_observed_quote_usd_btc=float(min(unique['bid']|unique['ask'])/contract),
                highest_observed_quote_usd_btc=float(max(unique['bid']|unique['ask'])/contract),
                quote_tick_usd_btc=float(D(meta['tick_size'])/contract),
                checkpoint_metrics=summarize(points),first_checkpoint=points[0],
                public_trade_btc=float(traded_contracts*contract),public_trade_notional_usd=float(traded_notional),
                storage=dict(sample_seconds=600,plain_bytes=raw,gzip_bytes=compressed,
                             plain_MB_per_hour=raw*6/1e6,gzip_MB_per_hour=compressed*6/1e6,
                             plain_GB_per_day=raw*144/1e9,gzip_GB_per_day=compressed*144/1e9,
                             gzip_GB_per_30_days=compressed*144*30/1e9,ratio=raw/compressed))
    print('Perp: '+json.dumps({'levels':result['levels_after_each_book_message'],'unique':result['unique_occupied_prices_combined'],'storage':result['storage']}),flush=True)
    return result


def source_files(prefix):
    return sorted([*HFT.joinpath('data').glob(prefix+'*.csv'),*HFT.joinpath('collector/rawdata').glob(prefix+'*.csv')])


def coinbase_assessment():
    files=source_files('BTC-'); channels=Counter(); quotes={}; total_seconds=0; starts=[]; ends=[]
    for i,path in enumerate(files):
        first=last=None
        for line in path.open():
            row=json.loads(line);channel=row.get('channel','unknown');channels[channel]+=1
            stamp=row.get('timestamp')
            if not stamp: continue
            t=datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp()
            first=t if first is None else min(first,t);last=t if last is None else max(last,t)
            if channel!='ticker':continue
            for event in row.get('events',[]):
                for ticker in event.get('tickers',[]):
                    if ticker.get('product_id')!='BTC-USD':continue
                    required=['best_bid','best_ask','best_bid_quantity','best_ask_quantity']
                    if not all(k in ticker for k in required):continue
                    bid,ask,bq,aq=(float(ticker[k]) for k in required)
                    if bid<=0 or ask<=0:continue
                    bucket=int(t//5)
                    if bucket in quotes and quotes[bucket][0]>=t:continue
                    mid=(bid+ask)/2
                    quotes[bucket]=(t,dict(timestamp=datetime.fromtimestamp(t,timezone.utc).isoformat(),
                        mid_usd_btc=mid,spread_bps=(ask-bid)/mid*10000,
                        top_bid_btc=bq,top_ask_btc=aq,top_two_sided_notional_usd=bid*bq+ask*aq))
        if first is not None:
            total_seconds+=last-first;starts.append(first);ends.append(last)
        if (i+1)%40==0:print(f'Coinbase files read: {i+1}/{len(files)}',flush=True)
    points=[value[1] for _,value in sorted(quotes.items())]
    write_csv('historical_coinbase_best_quotes.csv',points)
    size=sum(p.stat().st_size for p in files)
    return dict(files=len(files),bytes=size,channels=dict(channels),full_level2_present=bool(channels.get('level2') or channels.get('l2_data')),
                first_utc=datetime.fromtimestamp(min(starts),timezone.utc).isoformat(),last_utc=datetime.fromtimestamp(max(ends),timezone.utc).isoformat(),
                file_stream_hours=total_seconds/3600,raw_MB_per_file_stream_hour=size/1e6/(total_seconds/3600),
                metrics=summarize(points),sampling='Last available ticker observation in each UTC five-second bucket; duplicate overlapping file observations deduplicated by time bucket')


def binary_assessment():
    files=source_files('KX'); points=[]; public_counts=Counter(); total_seconds=0
    cached_prefix=None;cached_time=None
    def stamp(value):
        nonlocal cached_prefix,cached_time
        if isinstance(value,(int,float)):return float(value)
        prefix=value[:19]
        if prefix!=cached_prefix:
            cached_time=datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
            cached_prefix=prefix
        return cached_time
    for i,path in enumerate(files):
        books={'yes':{},'no':{}};valid=False;sid=seq=None;bucket=None;first=last=None
        for line in path.open():
            event=json.loads(line);kind=event.get('type');msg=event.get('msg',{})
            if kind not in ('orderbook_snapshot','orderbook_delta','trade'):continue
            public_counts[kind]+=1
            value=msg.get('ts_ms');t=stamp(value)/1000 if value is not None else stamp(msg['ts']) if msg.get('ts') is not None else None
            if t is not None:
                first=t if first is None else min(first,t);last=t if last is None else max(last,t)
            if kind=='trade':continue
            if kind=='orderbook_snapshot':
                books={'yes':{},'no':{}}
                for side in books:
                    key=next((k for k in [side+'_dollars_fp',side+'_dollars',side] if k in msg),None)
                    divisor=D(100) if key==side else D(1)
                    for p,q in (msg.get(key,[]) or []):
                        price,quantity=D(str(p))/divisor,D(str(q))
                        if quantity:books[side][price]=quantity
                sid,seq,valid=event.get('sid'),event.get('seq'),True
            else:
                if not valid or event.get('sid')!=sid or event.get('seq')!=seq+1:
                    raise ValueError('Historical sequence gap: '+path.name)
                seq=event['seq'];side=msg['side']
                p=D(str(msg['price_dollars'])) if 'price_dollars' in msg else D(str(msg['price']))/100
                delta=D(str(msg.get('delta_fp',msg.get('delta'))));q=books[side].get(p,D(0))+delta
                if q<0:raise ValueError('Historical negative quantity: '+path.name)
                if q:books[side][p]=q
                else:books[side].pop(p,None)
            if t is None or not any(books.values()) or int(t//5)==bucket:continue
            bucket=int(t//5)
            row=dict(timestamp=datetime.fromtimestamp(t,timezone.utc).isoformat(),
                     yes_bid_levels=len(books['yes']),no_bid_levels=len(books['no']),
                     total_bid_levels=sum(map(len,books.values())),
                     yes_bid_cash_usd=float(sum((p*q for p,q in books['yes'].items()),D(0))),
                     no_bid_cash_usd=float(sum((p*q for p,q in books['no'].items()),D(0))))
            row['total_bid_cash_usd']=row['yes_bid_cash_usd']+row['no_bid_cash_usd']
            if all(books.values()):
                yes,no=max(books['yes']),max(books['no'])
                row['yes_spread_cents']=float((1-no-yes)*100)
                row['top_two_outcome_bid_cash_usd']=float(yes*books['yes'][yes]+no*books['no'][no])
            points.append(row)
        if first is not None:total_seconds+=last-first
        if (i+1)%20==0:print(f'Binary-contract files read: {i+1}/{len(files)}',flush=True)
    write_csv('historical_binary_book_liquidity.csv',points)
    size=sum(p.stat().st_size for p in files)
    return dict(files=len(files),bytes=size,public_message_counts=dict(public_counts),
                file_stream_hours=total_seconds/3600,raw_MB_per_file_stream_hour=size/1e6/(total_seconds/3600),metrics=summarize(points),
                sampling='First nonempty reconstructed state per file per UTC five-second bucket; distinct contracts retained separately',
                warning='YES/NO displayed bid cash is not BTC notional, deposited account collateral, or a directly comparable measure of perp risk exposure')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result=dict(perp=perp_assessment(),coinbase_hft=coinbase_assessment(),binary_hft=binary_assessment(),
                limitations=['April historical data versus November perp sample; no contemporaneous venue ranking',
                             'Depth is displayed resting liquidity, not realized volume, hidden liquidity, or open interest',
                             'Perp depth summaries use 119 saved checkpoints; unique/level counts replay all book events',
                             'All-depth totals include distant quotes; nearby-depth bands are reported separately',
                             'Hourly/daily storage projections assume the observed ten-minute rate and gzip configuration persist',
                             'Historical Coinbase ticker captures only best quotes; no full-book total can be inferred',
                             'Historical source files and private fill payloads were not modified or exported'])
    (OUT/'assessment.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'perp_liquidity':result['perp']['checkpoint_metrics'],'old_coinbase':result['coinbase_hft'],'old_binary':result['binary_hft']},indent=2),flush=True)


if __name__=='__main__':main()
