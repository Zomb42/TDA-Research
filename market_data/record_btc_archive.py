"""Hourly market-data-only Kalshi perp archive with optional 2 Hz Coinbase reference.

Existing credentials are read in place; only public market-data subscriptions
are sent. Compressed hourly files rotate without reconnecting. No order client.
"""
import argparse
from collections import Counter, OrderedDict
import copy
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import signal
import sys
import threading
import time
import urllib.request

from cryptography.hazmat.primitives import serialization
import jwt
import websocket

from record_kalshi_btc_stream import HFT, ROOT, TICKER, WS_URL, PerpBook, InvalidBook, headers, atomic_json

COINBASE_URL = 'wss://advanced-trade-ws.coinbase.com'


def directory_bytes(directory):
    """Count all archived files, including open gzip segments and metadata."""
    return sum(p.stat().st_size for p in Path(directory).rglob('*') if p.is_file())


def storage_stop_reason(out, max_gb, min_free_gb, storage_root=None, max_total_gb=None):
    # Filesystem free space does not report an individual user's NetApp quota.
    if directory_bytes(out) >= max_gb * 1024**3:
        return 'archive_cap_reached'
    if storage_root is not None and directory_bytes(storage_root) >= max_total_gb * 1024**3:
        return 'total_archive_cap_reached'
    if shutil.disk_usage(out).free < min_free_gb * 1024**3:
        return 'free_disk_floor'
    return None


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class HourlyLog:
    """One writer per thread. A carried book anchor precedes the next raw event."""
    def __init__(self, directory, source, anchor=lambda: None, clock=time.time):
        self.directory, self.source, self.anchor, self.clock = Path(directory), source, anchor, clock
        self.directory.mkdir(parents=True, exist_ok=True)
        self.bucket = None
        self.stream = self.file = None
        self.closed_bytes = self.segments = 0
        self.current_path = None

    def _line(self, row):
        data = (json.dumps(row, separators=(',', ':'))+'\n').encode()
        self.stream.write(data)
        self.plain_bytes += len(data)
        self.records += 1
        self.counts[row.get('control', row.get('message', {}).get('type', row.get('type', 'unknown')))] += 1

    def write(self, row):
        now = self.clock(); bucket = int(now//3600)
        if self.bucket != bucket:
            self.close()
            self.bucket = bucket
            name = datetime.fromtimestamp(bucket*3600, timezone.utc).strftime('%Y-%m-%dT%H-00-00Z')
            self.current_path = self.directory/(name+'.jsonl.gz.partial')
            self.file = self.current_path.open('xb')
            self.stream = gzip.GzipFile(filename='', mode='wb', fileobj=self.file, compresslevel=3)
            self.records = self.plain_bytes = 0; self.counts = Counter(); self.opened_at = utc()
            self._line(dict(control='segment_start', source=self.source, opened_at=self.opened_at,
                            utc_hour_start=datetime.fromtimestamp(bucket*3600, timezone.utc).isoformat(),
                            book_anchor=self.anchor()))
        self._line(row)

    def flush(self):
        if self.stream:
            self.stream.flush(); self.file.flush(); os.fsync(self.file.fileno())

    @property
    def stored_bytes(self):
        return self.closed_bytes+(self.file.tell() if self.file else 0)

    def close(self):
        if self.stream is None:
            return
        self.stream.close(); self.file.flush(); os.fsync(self.file.fileno()); self.file.close()
        final = self.current_path.with_suffix('')
        self.current_path.rename(final)
        size = final.stat().st_size
        atomic_json(final.with_suffix('.manifest.json'), dict(source=self.source, file=final.name,
            opened_at=self.opened_at, closed_at=utc(), rows=self.records, counts=dict(self.counts),
            uncompressed_bytes=self.plain_bytes, compressed_bytes=size, sha256=digest(final)))
        self.closed_bytes += size; self.segments += 1
        self.stream = self.file = None


class State:
    def __init__(self, **values):
        self.lock = threading.RLock()
        self.values = dict(state='starting', connections=0, attempts=0, connection_errors=0,
                           sequence_gaps=0, rows_written=0, message_counts={}, stored_bytes=0, **values)

    def update(self, **values):
        with self.lock:
            self.values.update(values)

    def increment(self, name, n=1):
        with self.lock:
            self.values[name] = self.values.get(name, 0)+n

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.values)


def receive(ws):
    raw = ws.recv()
    if not raw:
        raise ConnectionError('closed')
    return json.loads(raw)


def close_socket(ws):
    if ws is not None:
        try:
            ws.close(timeout=1)
        except Exception:
            pass


def safe_error(error):
    # Exception strings and handshake headers may contain authentication material.
    return dict(error_type=type(error).__name__, http_status=getattr(error, 'status_code', None))


def run_kalshi(args, stop, state):
    book = PerpBook(); epoch = 0; counts = Counter(); pending_gap = None
    def anchor():
        return dict(epoch=epoch, **book.checkpoint()) if book.ready else None
    log = HourlyLog(args.out/'kalshi_perp', 'kalshi_perp', anchor)
    try:
        # Public instrument units and contract metadata, never an account request.
        try:
            with urllib.request.urlopen('https://external-api.kalshi.com/trade-api/v2/margin/markets/'+TICKER, timeout=10) as response:
                data = response.read()
            (args.out/'kalshi_market.json').write_bytes(data)
            state.update(market_metadata_saved=True)
        except Exception as error:
            state.update(market_metadata_error=safe_error(error))
        failures = 0
        while not stop.is_set():
            epoch += 1; ws = None; book = PerpBook(); sequences = {}
            state.increment('attempts'); state.update(state='connecting', epoch=epoch, book_valid=False)
            try:
                ws = websocket.create_connection(WS_URL, header=headers(args.kalshi_credentials, args.kalshi_key), timeout=10)
                ws.settimeout(1)
                state.increment('connections'); state.update(state='awaiting_snapshot', authentication_used=True)
                log.write(dict(control='connected', epoch=epoch, received_at=utc()))
                for identifier, channel in enumerate(['orderbook_delta','trade','ticker'],1):
                    params = dict(channels=[channel], market_ticker=TICKER)
                    if channel=='orderbook_delta': params['update_interval_ms']=0
                    ws.send(json.dumps(dict(id=identifier, cmd='subscribe', params=params)))
                last_receive = last_checkpoint = last_flush = time.monotonic()
                while not stop.is_set():
                    try:
                        event = receive(ws)
                    except websocket.WebSocketTimeoutException:
                        log.flush()
                        if time.monotonic()-last_receive>30: raise ConnectionError('idle')
                        continue
                    now = time.monotonic(); last_receive = now
                    stamp = utc(); kind = event.get('type','unknown')
                    if kind=='error':
                        log.write(dict(control='subscription_error', epoch=epoch, received_at=stamp,
                                       code=event.get('msg',{}).get('code')))
                        raise PermissionError('subscription')
                    log.write(dict(epoch=epoch, received_at=stamp, received_unix_ns=time.time_ns(),
                                   received_monotonic_ns=time.monotonic_ns(), message=event))
                    counts[kind] += 1
                    if kind in ('orderbook_snapshot','orderbook_delta','trade','ticker') and event.get('msg',{}).get('market_ticker')!=TICKER:
                        raise ValueError('unexpected market')
                    sid, seq = event.get('sid'), event.get('seq')
                    if kind=='trade' and sid in sequences and seq!=sequences[sid]+1:
                        state.increment('trade_sequence_gaps')
                        log.write(dict(control='trade_sequence_gap', epoch=epoch, received_at=stamp,
                                       previous=sequences[sid], sequence=seq))
                    if sid is not None and seq is not None: sequences[sid]=seq
                    try:
                        changed = book.apply(event)
                    except InvalidBook as error:
                        state.increment('reconstruction_errors')
                        if str(error)=='sequence_gap':state.increment('sequence_gaps')
                        log.write(dict(control='book_invalid', epoch=epoch, received_at=stamp, reason=str(error)))
                        raise
                    if kind=='orderbook_snapshot':
                        failures = 0; state.update(state='collecting', book_valid=True, snapshot_received_at=stamp)
                        if pending_gap:
                            log.write(dict(control='gap_end', epoch=epoch, received_at=stamp, gap_started_at=pending_gap))
                            pending_gap = None
                            state.update(gap_started_at=None)
                    if changed and (kind=='orderbook_snapshot' or now-last_checkpoint>=5):
                        log.write(dict(control='book_checkpoint', epoch=epoch, received_at=stamp, book=book.checkpoint()))
                        last_checkpoint=now; state.increment('checkpoints')
                        atomic_json(args.out/'latest_perp_book.json',dict(received_at=stamp, epoch=epoch, **book.checkpoint()))
                    state.update(last_received_at=stamp)
                    if now-last_flush>=5:
                        log.flush();last_flush=now
                        state.update(message_counts=dict(counts), rows_written=log.records,
                                     closed_segments=log.segments,stored_bytes=log.stored_bytes,
                                     current_file=str(log.current_path.relative_to(args.out)))
            except Exception as error:
                failures += 1; state.increment('connection_errors')
                detail=safe_error(error)
                pending_gap=pending_gap or utc()
                log.write(dict(control='gap_start',epoch=epoch,received_at=utc(),**detail))
                log.flush();state.update(state='reconnecting',book_valid=False,last_error=detail,gap_started_at=pending_gap)
                if detail['http_status'] in (401,403) or isinstance(error,PermissionError):
                    state.update(state='access_failed');break
                stop.wait(min(30,2**min(failures,5)))
            finally:
                close_socket(ws)
    finally:
        log.close();state.update(message_counts=dict(counts), stored_bytes=log.stored_bytes,
                                 closed_segments=log.segments,book_valid=False)
        if state.snapshot()['state']!='access_failed':state.update(state='stopped')


def coinbase_credentials(path):
    data=json.loads(path.read_text())
    key=serialization.load_pem_private_key(data['privateKey'].encode(),password=None)
    return data.get('name') or data['id'],key


def coinbase_jwt(credentials):
    name,key=credentials; now=int(time.time())
    return jwt.encode(dict(sub=name,iss='cdp',nbf=now,exp=now+120),key,algorithm='ES256',
                      headers=dict(kid=name,nonce=secrets.token_hex(16)))


class Reference:
    """Latest quote + exact received trade totals; no private fields or raw JWTs."""
    def __init__(self):
        self.quote=None;self.quote_received=None;self.quote_mono=None
        self.last_trade=None;self.trade_time=None;self.seen=OrderedDict()
        self.reset_interval()

    def reset_interval(self):
        self.trade_count=0;self.trade_btc=Decimal(0);self.trade_usd=Decimal(0)

    def apply(self, event, stamp, monotonic):
        for value in event.get('events',[]):
            if event.get('channel')=='ticker':
                for item in value.get('tickers',[]):
                    if item.get('product_id')!='BTC-USD':continue
                    fields=['best_bid','best_ask','best_bid_quantity','best_ask_quantity','price']
                    if not all(k in item for k in fields):continue
                    nums=[Decimal(item[k]) for k in fields]
                    if not all(n.is_finite() and n>=0 for n in nums) or nums[0]<=0 or nums[1]<=0:
                        raise ValueError('invalid quote')
                    self.quote={k:item[k] for k in fields}
                    self.quote.update(source_time=event.get('timestamp'),source_sequence=event.get('sequence_num'))
                    self.quote_received=stamp;self.quote_mono=monotonic
            if event.get('channel')=='market_trades':
                for trade in value.get('trades',[]):
                    if trade.get('product_id')!='BTC-USD':continue
                    if self.trade_time is None or trade['time']>self.trade_time:
                        self.last_trade=trade['price'];self.trade_time=trade['time']
                    identifier=trade['trade_id']
                    if identifier in self.seen:continue
                    self.seen[identifier]=True
                    if len(self.seen)>10000:self.seen.popitem(last=False)
                    if value.get('type')=='snapshot':continue # Prior executions are not new half-second volume.
                    size,price=Decimal(trade['size']),Decimal(trade['price'])
                    if not all(n.is_finite() and n>=0 for n in [size,price]):raise ValueError('invalid trade')
                    self.trade_count+=1;self.trade_btc+=size;self.trade_usd+=size*price

    def sample(self, epoch, connected, interval_start, now):
        row=dict(type='reference_sample',sampled_at=utc(),sampled_unix_ns=time.time_ns(),
                 sampled_monotonic_ns=time.monotonic_ns(),epoch=epoch,connected=connected,
                 interval_seconds=max(0,now-interval_start),product_id='BTC-USD',quote=self.quote,
                 quote_received_at=self.quote_received,quote_age_ms=(now-self.quote_mono)*1000 if self.quote_mono is not None else None,
                 last_trade_price=self.last_trade,last_trade_source_time=self.trade_time,
                 trade_count=self.trade_count,trade_btc=str(self.trade_btc),trade_notional_usd=str(self.trade_usd))
        if self.quote:
            bid,ask=Decimal(self.quote['best_bid']),Decimal(self.quote['best_ask'])
            row.update(midpoint=str((bid+ask)/2),spread=str(ask-bid),crossed_or_locked=bid>=ask)
        self.reset_interval()
        return row


def run_coinbase(args,stop,state):
    credentials=coinbase_credentials(args.coinbase_credentials)
    log=HourlyLog(args.out/'coinbase_reference','coinbase_reference')
    counts=Counter(); epoch=failures=0; reference=Reference(); pending_gap=None
    try:
        while not stop.is_set():
            epoch+=1;ws=None;previous_seq=None;state.increment('attempts')
            interval_start=time.monotonic()
            reference.quote=None;reference.quote_mono=None;reference.quote_received=None
            state.update(state='connecting',epoch=epoch)
            try:
                ws=websocket.create_connection(COINBASE_URL,timeout=10);ws.settimeout(.1)
                for channel in ['ticker','market_trades','heartbeats']:
                    ws.send(json.dumps(dict(type='subscribe',product_ids=['BTC-USD'],channel=channel,jwt=coinbase_jwt(credentials))))
                state.increment('connections');state.update(state='awaiting_quote',authentication_used=True)
                log.write(dict(control='connected',epoch=epoch,received_at=utc()))
                interval_start=last_receive=last_flush=time.monotonic();next_sample=interval_start+.5
                while not stop.is_set():
                    event=None
                    try:
                        event=receive(ws)
                    except websocket.WebSocketTimeoutException:
                        pass
                    now=time.monotonic()
                    if event is not None:
                        stamp=utc();last_receive=now
                        if event.get('type')=='error':
                            log.write(dict(control='subscription_error',epoch=epoch,received_at=stamp))
                            raise PermissionError('subscription')
                        channel=event.get('channel','unknown');counts[channel]+=1
                        seq=event.get('sequence_num')
                        if isinstance(seq,int):
                            if previous_seq is not None and seq!=previous_seq+1:
                                state.increment('sequence_gaps')
                                log.write(dict(control='sequence_gap',epoch=epoch,received_at=stamp,previous=previous_seq,sequence=seq,channel=channel))
                                raise ConnectionError('sequence gap')
                            previous_seq=seq
                        reference.apply(event,stamp,now)
                        if reference.quote:
                            state.update(state='collecting',last_quote_received_at=reference.quote_received)
                            failures=0
                            if pending_gap:
                                log.write(dict(control='gap_end',epoch=epoch,received_at=stamp,gap_started_at=pending_gap));pending_gap=None
                                state.update(gap_started_at=None)
                        state.update(last_received_at=stamp)
                    if now>=next_sample:
                        row=reference.sample(epoch,True,interval_start,now)
                        log.write(row);state.increment('samples');interval_start=now
                        missed=max(0,int((now-next_sample)/.5));state.increment('missed_sample_slots',missed)
                        next_sample+=.5*(missed+1)
                        atomic_json(args.out/'latest_coinbase_reference.json',row)
                    if now-last_receive>30:raise ConnectionError('idle')
                    if now-last_flush>=5:
                        log.flush();last_flush=now
                        state.update(message_counts=dict(counts),stored_bytes=log.stored_bytes,
                                     closed_segments=log.segments,current_file=str(log.current_path.relative_to(args.out)),
                                     quote_age_ms=(now-reference.quote_mono)*1000 if reference.quote_mono is not None else None)
            except Exception as error:
                failures+=1;state.increment('connection_errors');detail=safe_error(error)
                # Preserve the final partial aggregate before waiting/reconnecting.
                log.write(reference.sample(epoch,False,interval_start if ws else time.monotonic(),time.monotonic()))
                pending_gap=pending_gap or utc()
                log.write(dict(control='gap_start',epoch=epoch,received_at=utc(),**detail));log.flush()
                state.update(state='reconnecting',last_error=detail,gap_started_at=pending_gap)
                if detail['http_status'] in (401,403) or isinstance(error,PermissionError):
                    state.update(state='access_failed');break
                stop.wait(min(30,2**min(failures,5)))
            finally:close_socket(ws)
    finally:
        if reference.trade_count:
            log.write(reference.sample(epoch,False,time.monotonic(),time.monotonic()))
        log.close();state.update(message_counts=dict(counts),stored_bytes=log.stored_bytes,closed_segments=log.segments)
        if state.snapshot()['state']!='access_failed':state.update(state='stopped')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--kalshi-credentials',type=Path,default=HFT/'secrets/kalshi_credentials.json')
    parser.add_argument('--kalshi-key',type=Path,default=HFT/'secrets/TestExample1.pem')
    parser.add_argument('--coinbase-credentials',type=Path,default=HFT/'collector/misc/cdp_api_key.json')
    parser.add_argument('--kalshi-only',action='store_true',help='Do not connect to Coinbase or require its key')
    parser.add_argument('--max-gb',type=float,default=20)
    parser.add_argument('--min-free-gb',type=float,default=10)
    parser.add_argument('--storage-root',type=Path,help='Parent directory containing all runs to include in the total cap')
    parser.add_argument('--max-total-gb',type=float,help='Stop at this many GiB across storage-root, including earlier runs')
    parser.add_argument('--startup-timeout',type=float,default=0,help='Fail if any enabled feed has not become healthy within this many seconds; 0 disables')
    parser.add_argument('--seconds',type=float,default=0,help='0 means run until stopped or storage limit')
    args=parser.parse_args();args.out=args.out.resolve()
    limits=[args.max_gb,args.min_free_gb,args.seconds,args.startup_timeout]
    if args.max_total_gb is not None:limits.append(args.max_total_gb)
    if (not all(math.isfinite(v) for v in limits) or args.max_gb<=0 or args.min_free_gb<=0
            or args.seconds<0 or args.startup_timeout<0):parser.error('invalid limits')
    if (args.storage_root is None)!=(args.max_total_gb is None):
        parser.error('storage-root and max-total-gb must be supplied together')
    if args.storage_root is not None:
        args.storage_root=args.storage_root.resolve()
        if args.max_total_gb<=0 or args.storage_root not in args.out.parents:
            parser.error('positive total cap and storage-root strictly containing out required')
    args.out.mkdir(parents=True,exist_ok=True)
    if (args.out/'status.json').exists():raise FileExistsError('Choose a fresh output directory')
    def storage_limit():
        return storage_stop_reason(args.out,args.max_gb,args.min_free_gb,args.storage_root,args.max_total_gb)
    limit=storage_limit()
    if limit:
        print(json.dumps(dict(state='startup_failed',stop_reason=limit)),flush=True)
        return 1
    headers(args.kalshi_credentials,args.kalshi_key)
    if not args.kalshi_only:coinbase_jwt(coinbase_credentials(args.coinbase_credentials))
    stop=threading.Event()
    stop_signals=[signal.SIGTERM,signal.SIGINT]
    # Grid Engine -notify warns before suspension/deletion. Close the archive
    # instead of leaving a gzip stream open when the scheduler stops the job.
    stop_signals += [getattr(signal,name) for name in ('SIGUSR1','SIGUSR2') if hasattr(signal,name)]
    for number in stop_signals:signal.signal(number,lambda *_:stop.set())
    (args.out/'source').mkdir()
    source_hashes={}
    for name in ['record_btc_archive.py','record_kalshi_btc_stream.py']:
        source=Path(__file__).with_name(name);shutil.copy2(source,args.out/'source'/name);source_hashes[name]=digest(source)
    config=dict(pid=os.getpid(),started_at=utc(),python_executable=sys.executable,
                out=str(args.out),compression='gzip',rotation='UTC hour, no feed reconnect',
                max_gib=args.max_gb,min_free_gib=args.min_free_gb,planned_seconds=args.seconds or None,
                storage_root=str(args.storage_root) if args.storage_root else None,max_total_gib=args.max_total_gb,
                startup_timeout_seconds=args.startup_timeout or None,
                kalshi=dict(ticker=TICKER,channels=['orderbook_delta','trade','ticker'],update_interval_ms=0),
                coinbase=dict(product='BTC-USD',channels=['ticker','market_trades','heartbeats'],stored_sample_hz=2,
                              raw_trade_messages_retained=False,half_second_trade_aggregates=True,authentication='existing ECDSA key'),
                source_sha256=source_hashes,order_actions_available=False,boot_service_installed=False)
    if args.kalshi_only:config['coinbase']=None
    atomic_json(args.out/'config.json',config)
    states={'kalshi_perp':State(trade_sequence_gaps=0,reconstruction_errors=0),
            'coinbase_reference':State(samples=0,missed_sample_slots=0)}
    feeds=[('kalshi_perp',run_kalshi),('coinbase_reference',run_coinbase)]
    if args.kalshi_only:
        feeds=feeds[:1];states.pop('coinbase_reference')
    def guarded(function,state):
        try:function(args,stop,state)
        except Exception as error:state.update(state='failed',last_error=safe_error(error))
    threads=[threading.Thread(target=guarded,args=(fn,states[name]),name=name,daemon=True)
             for name,fn in feeds]
    started=time.monotonic();reason='stop_requested';last_status=0;ready_feeds=set();failed=False
    for thread in threads:thread.start()
    def status(final=False):
        feeds={name:s.snapshot() for name,s in states.items()}
        healthy=all(s['state']=='collecting' for s in feeds.values())
        result=dict(pid=os.getpid(),started_at=config['started_at'],updated_at=utc(),elapsed_seconds=time.monotonic()-started,
                    state=('failed' if failed else 'stopped') if final else 'collecting' if healthy else 'starting_or_degraded',
                    feeds=feeds,stop_reason=reason if final else None,free_disk_gib=shutil.disk_usage(args.out).free/1024**3)
        atomic_json(args.out/'status.json',result)
        return result
    status()
    try:
        while not stop.wait(.5):
            now=time.monotonic()
            ready_feeds.update(name for name,s in states.items() if s.snapshot()['state']=='collecting')
            if any(not t.is_alive() for t in threads):reason='feed_stopped';failed=True;stop.set()
            if args.startup_timeout and now-started>=args.startup_timeout and len(ready_feeds)<len(states):
                reason='startup_timeout';failed=True;stop.set()
            if (args.out/'STOP').exists():reason='stop_file';stop.set()
            if args.seconds and now-started>=args.seconds:reason='duration_completed';stop.set()
            if now-last_status>=5:
                limit=storage_limit()
                if limit:reason=limit;stop.set()
                status();last_status=now
    finally:
        stop.set()
        for thread in threads:thread.join(timeout=15)
        if any(t.is_alive() for t in threads):reason='shutdown_incomplete';failed=True
        if any(s.snapshot()['state'] in ('failed','access_failed') for s in states.values()):failed=True
        final=status(True);atomic_json(args.out/'manifest.json',final)
        print(json.dumps(final,indent=2),flush=True)
    return 1 if failed else 0


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as error:
        print(json.dumps(dict(state='startup_failed',**safe_error(error))),flush=True)
        sys.exit(1)
