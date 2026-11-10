"""Inspect the active BTC archive or request a graceful stop; no network."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read_rows(path):
    try:
        with gzip.open(path,'rt',encoding='utf-8') as stream:
            for line in stream:
                if line.endswith('\n'):yield json.loads(line)
    except EOFError:
        if not str(path).endswith('.partial'):raise


def inspect(path,limit=100000):
    """Replay a live prefix independently; a live file has no final gzip CRC yet."""
    sides={'bid':{},'ask':{}};ready=False;sid=seq=epoch=None
    counts=Counter();matched=records=0;limited=False
    for row in read_rows(path):
        records+=1
        if records>limit:
            limited=True;records-=1;break
        control=row.get('control')
        counts[control or row.get('message',{}).get('type',row.get('type','unknown'))]+=1
        if control=='segment_start' and row.get('book_anchor'):
            anchor=row['book_anchor'];epoch=anchor['epoch'];sid=anchor['sid'];seq=anchor['seq']
            sides={side:{Decimal(p):Decimal(q) for p,q in anchor[side]} for side in sides};ready=True
        if control in ('connected','gap_start','book_invalid'):
            ready=False;epoch=row.get('epoch')
        event=row.get('message',{});kind=event.get('type')
        if kind in ('orderbook_snapshot','orderbook_delta'):
            msg=event['msg']
            if kind=='orderbook_snapshot':
                sides={side:{Decimal(p):Decimal(q) for p,q in msg[side] if Decimal(q)>0} for side in sides}
                sid,seq,epoch,ready=event['sid'],event['seq'],row['epoch'],True
            else:
                if not ready or event['sid']!=sid or event['seq']!=seq+1 or row['epoch']!=epoch:
                    raise ValueError('Cannot replay delta without contiguous snapshot/anchor')
                side=msg['side'];p=Decimal(msg['price']);q=sides[side].get(p,Decimal(0))+Decimal(msg['delta'])
                if not q.is_finite() or q<0:raise ValueError('Invalid resulting quantity')
                if q:sides[side][p]=q
                else:sides[side].pop(p,None)
                seq=event['seq']
        if control=='book_checkpoint':
            saved=row['book']
            if not ready or saved['sid']!=sid or saved['seq']!=seq:raise ValueError('Checkpoint identity differs')
            if any({Decimal(p):Decimal(q) for p,q in saved[side]}!=sides[side] for side in sides):
                raise ValueError('Checkpoint differs from replay')
            matched+=1
        if row.get('type')=='reference_sample' and row.get('quote'):
            quote=row['quote'];mid=(Decimal(quote['best_bid'])+Decimal(quote['best_ask']))/2
            if mid!=Decimal(row['midpoint']):raise ValueError('Reference midpoint differs')
            if row['quote_age_ms']<0:raise ValueError('Negative reference age')
    live=str(path).endswith('.partial')
    result=dict(file=str(path),live_partial=live,limited_prefix=limited,rows_checked=records,
                counts=dict(counts),checkpoints_matched=matched,passed=True)
    if not live:
        manifest=json.loads(path.with_suffix('.manifest.json').read_text())
        with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=manifest['sha256']:raise ValueError('File hash differs')
        if not limited and records!=manifest['rows']:raise ValueError('Row count differs')
        result['final_hash_verified']=True
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['status','inspect','stop'])
    parser.add_argument('--out',type=Path)
    parser.add_argument('--limit',type=int,default=100000)
    args=parser.parse_args()
    out=args.out or ROOT/json.loads((ROOT/'btc/ACTIVE_CAPTURE.json').read_text())['data_directory']
    if args.action=='stop':
        (out/'STOP').write_text(datetime.now(timezone.utc).isoformat()+'\n')
        print('Graceful stop requested. Check status in a few seconds.');return
    if args.action=='status':
        status=json.loads((out/'status.json').read_text())
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(status['updated_at'])).total_seconds()
        status['status_age_seconds']=round(age,2);status['status_fresh']=age<20
        print(json.dumps(status,indent=2));return
    results=[]
    for name in ['kalshi_perp','coinbase_reference']:
        files=sorted([*out.joinpath(name).glob('*.jsonl.gz'),*out.joinpath(name).glob('*.partial')])
        if files:results.append(inspect(files[-1],args.limit))
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
