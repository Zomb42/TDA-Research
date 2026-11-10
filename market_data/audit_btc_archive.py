"""Validate an entire finalized BTC archive offline; no credentials or network."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal as D
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def dt(value):
    return datetime.fromisoformat(value)


def decimal_book(value):
    result={side:{D(p):D(q) for p,q in value[side] if D(q)>0} for side in ['bid','ask']}
    assert all(result.values())
    assert all(p.is_finite() and q.is_finite() and p>0 and q>0 for side in result.values() for p,q in side.items())
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path);args=parser.parse_args()
    out=args.out or ROOT/json.loads((ROOT/'btc/ACTIVE_CAPTURE.json').read_text())['data_directory']
    status=json.loads((out/'status.json').read_text());final=json.loads((out/'manifest.json').read_text())
    assert status==final and final['state']=='stopped'
    assert all(f['state']=='stopped' for f in final['feeds'].values())
    assert not list(out.rglob('*.partial')), 'Open files remain'
    meta=json.loads((out/'kalshi_market.json').read_text())['market'];contract=D(meta['contract_size'])
    files=[];source_summaries={};gap_windows=[];sampling_gaps=[]
    assert 'kalshi_perp' in final['feeds']
    assert set(final['feeds']) <= {'kalshi_perp','coinbase_reference'}
    for source in final['feeds']:
        paths=sorted((out/source).glob('*.jsonl.gz'))
        totals=Counter();all_messages=Counter();pending=None;ready=False;book={'bid':{},'ask':{}}
        sid=seq=epoch=None;matched=seams=0;trade_seq={};trade_ids=set();duplicates=0
        trade_btc=trade_usd=D(0);first=last=None;last_sample=None;last_valid_sample=None
        reference_count=regular_reference_count=disconnect_reference_count=valid_reference_count=quote_samples=stale_reference_count=0
        last_reference_row=None
        maximum_sample_gap=0.;sample_gap_excess=0.;sample_gaps=0;time_reversals=0
        for path in paths:
            manifest=json.loads(path.with_suffix('.manifest.json').read_text());counts=Counter();records=0
            assert digest(path)==manifest['sha256'], ('hash',path)
            assert path.stat().st_size==manifest['compressed_bytes']
            with gzip.open(path,'rt',encoding='utf-8') as stream:
                for line in stream:
                    assert line.endswith('\n'),('partial row',path)
                    row=json.loads(line);records+=1
                    control=row.get('control');event=row.get('message',{});kind=event.get('type')
                    category=control or kind or row.get('type','unknown');counts[category]+=1
                    if kind:all_messages[kind]+=1
                    timestamp=row.get('received_at') or row.get('sampled_at')
                    if timestamp:
                        observed=dt(timestamp)
                        if last is not None and observed<last:time_reversals+=1
                        first=observed if first is None else min(first,observed)
                        last=observed if last is None else max(last,observed)
                    if control=='gap_start':
                        pending=pending or row['received_at']
                    elif control=='gap_end':
                        start=pending or row.get('gap_started_at')
                        assert start is not None
                        gap_windows.append(dict(source=source,start=start,end=row['received_at'],
                                                seconds=(dt(row['received_at'])-dt(start)).total_seconds()))
                        pending=None
                    if source=='kalshi_perp':
                        if control=='segment_start':
                            anchor=row.get('book_anchor')
                            if anchor:
                                anchored=decimal_book(anchor)
                                if ready:
                                    assert (epoch,sid,seq)==(anchor['epoch'],anchor['sid'],anchor['seq']),('seam identity',path)
                                    assert book==anchored,('seam book',path)
                                    seams+=1
                                book=anchored;epoch,sid,seq=anchor['epoch'],anchor['sid'],anchor['seq'];ready=True
                            else:
                                assert not ready,('missing carried anchor',path)
                        if control in ('connected','gap_start','book_invalid'):
                            ready=False;epoch=row.get('epoch')
                        if kind=='orderbook_snapshot':
                            assert event['msg']['market_ticker']=='KXBTCPERP'
                            book=decimal_book(event['msg']);epoch,sid,seq=row['epoch'],event['sid'],event['seq'];ready=True
                        elif kind=='orderbook_delta':
                            assert ready and (row['epoch'],event['sid'],event['seq'])==(epoch,sid,seq+1),('sequence',path,records)
                            msg=event['msg'];assert msg['market_ticker']=='KXBTCPERP'
                            side=msg['side'];p=D(msg['price']);quantity=book[side].get(p,D(0))+D(msg['delta'])
                            assert p.is_finite() and p>0 and quantity.is_finite() and quantity>=0
                            if quantity:book[side][p]=quantity
                            else:book[side].pop(p,None)
                            seq=event['seq']
                        elif kind=='trade':
                            msg=event['msg'];assert msg['market_ticker']=='KXBTCPERP'
                            key=(row['epoch'],event['sid']);previous=trade_seq.get(key)
                            if previous is not None:assert event['seq']==previous+1,('trade sequence',path,records)
                            trade_seq[key]=event['seq']
                            identifier=msg['trade_id']
                            if identifier in trade_ids:duplicates+=1
                            else:
                                trade_ids.add(identifier);trade_btc+=D(msg['count'])*contract
                                trade_usd+=D(msg['count'])*D(msg['price'])
                        if control=='book_checkpoint':
                            saved=row['book'];assert ready
                            assert (saved['sid'],saved['seq'])==(sid,seq)
                            assert decimal_book(saved)==book,('checkpoint',path,records)
                            assert bool(saved['crossed_or_locked'])==(max(book['bid'])>=min(book['ask']))
                            matched+=1
                    elif row.get('type')=='reference_sample':
                        reference_count+=1;now=dt(row['sampled_at']);quote=row.get('quote')
                        last_reference_row=row
                        if row['connected']:regular_reference_count+=1
                        else:disconnect_reference_count+=1
                        if last_sample is not None:
                            delta=(now-last_sample).total_seconds();assert delta>=0
                            maximum_sample_gap=max(maximum_sample_gap,delta)
                            if delta>2:
                                sample_gaps+=1;sample_gap_excess+=max(0,delta-.5)
                                sampling_gaps.append(dict(source=source,start=last_sample.isoformat(),end=now.isoformat(),seconds=delta))
                        last_sample=now
                        if quote:
                            bid,ask=D(quote['best_bid']),D(quote['best_ask'])
                            assert D(row['midpoint'])==(bid+ask)/2
                            assert bid.is_finite() and ask.is_finite() and bid>0 and ask>0
                            assert row['quote_age_ms'] is not None and row['quote_age_ms']>=0
                            quote_samples+=1
                            if row['quote_age_ms']>2000:stale_reference_count+=1
                            if row['connected'] and ask>bid and row['quote_age_ms']<=2000:
                                valid_reference_count+=1;last_valid_sample=now
                        assert row['trade_count']>=0 and D(row['trade_btc'])>=0 and D(row['trade_notional_usd'])>=0
            assert records==manifest['rows'],('rows',path)
            assert dict(counts)==manifest['counts'],('counts',path)
            totals.update(counts)
            files.append(dict(file=str(path.relative_to(out)),rows=records,counts=dict(counts),
                              sha256=manifest['sha256'],compressed_bytes=manifest['compressed_bytes'],
                              uncompressed_bytes=manifest['uncompressed_bytes'],gzip_crc_passed=True))
            print('Validated',source,path.name,records,'rows',flush=True)
        if pending:
            gap_windows.append(dict(source=source,start=pending,end=final['updated_at'],
                                    seconds=(dt(final['updated_at'])-dt(pending)).total_seconds(),censored_at_stop=True))
        feed=final['feeds'][source]
        assert len(paths)==feed['closed_segments']
        assert sum(f['compressed_bytes'] for f in files if f['file'].startswith(source+'/'))==feed['stored_bytes']
        if source=='kalshi_perp':
            assert dict(all_messages)==feed['message_counts']
            assert matched==feed['checkpoints']
            assert totals['sequence_gap']==feed['sequence_gaps']==0
            assert totals['trade_sequence_gap']==feed['trade_sequence_gaps']==0
            assert totals['book_invalid']==feed['reconstruction_errors']==0
        else:
            assert regular_reference_count==feed['samples']
            assert totals['gap_start']==feed['connection_errors']
            terminal_snapshots=disconnect_reference_count-totals['gap_start']
            assert terminal_snapshots in (0,1)
            if terminal_snapshots:
                assert not last_reference_row['connected'] and last_reference_row['trade_count']>0
                assert 0<=(dt(final['updated_at'])-dt(last_reference_row['sampled_at'])).total_seconds()<30
        source_summaries[source]=dict(files=len(paths),counts=dict(totals),first_observation=first.isoformat(),
            last_observation=last.isoformat(),receive_timestamp_reversals=time_reversals,
            recorded_connection_errors=feed['connection_errors'],recorded_connections=feed['connections'])
        if source=='kalshi_perp':
            source_summaries[source].update(checkpoints_replayed=matched,hour_seams_matched=seams,
                unique_trades=len(trade_ids),duplicate_trade_ids=duplicates,unique_traded_btc=str(trade_btc),
                unique_trade_notional_usd=str(trade_usd),zero_recorded_book_sequence_gaps=True)
        else:
            source_summaries[source].update(reference_samples=regular_reference_count,
                total_reference_snapshot_rows=reference_count,disconnect_reference_snapshots=totals['gap_start'],
                shutdown_reference_snapshots=terminal_snapshots,
                quote_samples=quote_samples,
                connected_uncrossed_samples_quote_age_at_most_2s=valid_reference_count,
                stale_quote_samples_over_2s=stale_reference_count,
                sample_intervals_over_2s=sample_gaps,maximum_sample_interval_seconds=maximum_sample_gap,
                sample_interval_excess_seconds_over_nominal_half_second=sample_gap_excess,
                note='Sample spacing includes pauses/outages; count*0.5 is not certified continuous market coverage.')
    report=dict(passed=True,validated_at=datetime.now(timezone.utc).isoformat(),
        run_id=out.name,state=final['state'],stop_reason=final['stop_reason'],
        started_at=final['started_at'],stopped_at=final['updated_at'],
        wall_span_seconds=(dt(final['updated_at'])-dt(final['started_at'])).total_seconds(),
        recorder_monotonic_elapsed_seconds=final['elapsed_seconds'],
        completed_files=len(files),remaining_partial_files=0,
        compressed_bytes=sum(f['compressed_bytes'] for f in files),
        uncompressed_bytes=sum(f['uncompressed_bytes'] for f in files),
        sources=source_summaries,explicit_gap_windows=gap_windows,reference_sampling_gaps=sampling_gaps,files=files,
        limitations=['Replay validates recorded-stream consistency, not exchange-wide completeness.',
                    'Reconnects and long sample intervals are retained; calendar span is not uninterrupted coverage.',
                    'Coinbase is sampled ticker/trade-aggregate reference, not an L2 book.',
                    'No automatic restart service is installed; the STOP marker remains.'])
    (out/'final_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['files','reference_sampling_gaps','explicit_gap_windows']},indent=2))


if __name__=='__main__':main()
