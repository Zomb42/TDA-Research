"""Public historical full-depth L2 + trades pilot; no account or order APIs.

Downloads one Tardis free-sample day, retaining exact source files. Replays the
normalized replacement-size schema and saves full minute-spaced checkpoints.
This does not assert access to all internal orders or gap-free native messages.
"""
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.request

BASE = Path(__file__).resolve().parent
OUT = BASE / "datasets/btc_deribit_2025-01-01"
DATE = "2025/01/01"
SYMBOL = "BTC-PERPETUAL"
KINDS = ["incremental_book_L2", "trades"]


def save(path, data):
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(data,indent=2)+"\n")
    temp.replace(path)


def download(kind):
    path=OUT/"raw"/(kind+".csv.gz")
    meta_path=path.with_suffix(path.suffix+".meta.json")
    if path.exists() and meta_path.exists():
        meta=json.loads(meta_path.read_text())
        digest=hashlib.sha256()
        with path.open("rb") as f:
            for block in iter(lambda:f.read(1024*1024),b""):digest.update(block)
        if digest.hexdigest()!=meta["sha256"]:raise ValueError("Cached checksum mismatch")
        return meta
    url=f"https://datasets.tardis.dev/v1/deribit/{kind}/{DATE}/{SYMBOL}.csv.gz"
    req=urllib.request.Request(url,headers={"User-Agent":"TDA-Research/1.0"})
    meta=dict(url=url,kind=kind,requested_at=datetime.now(timezone.utc).isoformat())
    sha=hashlib.sha256();md5=hashlib.md5();size=0
    temporary=path.with_suffix(path.suffix+".part")
    with urllib.request.urlopen(req,timeout=60) as response, temporary.open("wb") as f:
        meta.update(http_status=response.status,advertised_bytes=response.headers.get("Content-Length"),
                    advertised_md5=response.headers.get("x-md5") or response.headers.get("x-amz-meta-md5") or response.headers.get("ETag"))
        if response.status!=200:raise ValueError("Expected a complete HTTP 200 file")
        for block in iter(lambda:response.read(1024*1024),b""):
            size+=len(block)
            if size>512*1024*1024:raise ValueError("Download exceeds pilot byte cap")
            f.write(block);sha.update(block);md5.update(block)
            save(OUT/(kind+"_download_progress.json"),dict(bytes_received=size,updated_at=datetime.now(timezone.utc).isoformat()))
    meta.update(received_at=datetime.now(timezone.utc).isoformat(),bytes=size,sha256=sha.hexdigest(),md5=md5.hexdigest())
    if meta["advertised_bytes"] and int(meta["advertised_bytes"])!=size:raise ValueError("Incomplete transfer")
    advertised=(meta["advertised_md5"] or "").strip('"')
    meta["published_md5_verified"]=False
    if re.fullmatch(r"[a-fA-F0-9]{32}",advertised):
        if advertised.lower()!=md5.hexdigest():raise ValueError("Published MD5 mismatch")
        meta["published_md5_verified"]=True
    temporary.replace(path)
    save(meta_path,meta)
    return meta


def replay_book():
    books={"bid":{},"ask":{}}
    counts=Counter()
    started=False;in_snapshot=False;group_time=None;group_snapshot=False
    first=last=previous_local=previous_exchange=None
    next_checkpoint=None
    largest_gap=0
    local_regressions=exchange_regressions=crossed=checkpoints=0
    max_bid=max_ask=0
    row_count=0
    summary_rows=[]
    checkpoints_path=OUT/"book_checkpoints.jsonl.gz"
    with gzip.open(checkpoints_path,"wt") as states:
        def finish_group(local):
            nonlocal next_checkpoint,checkpoints,crossed,max_bid,max_ask
            if not started or in_snapshot or not books["bid"] or not books["ask"]:return
            if next_checkpoint is not None and local<next_checkpoint:return
            bid=max(books["bid"]);ask=min(books["ask"])
            is_crossed=bid>=ask
            crossed+=is_crossed
            max_bid=max(max_bid,len(books["bid"]));max_ask=max(max_ask,len(books["ask"]))
            state=dict(local_timestamp=local,bid=[[str(p),str(q)] for p,q in sorted(books["bid"].items(),reverse=True)],
                       ask=[[str(p),str(q)] for p,q in sorted(books["ask"].items())])
            states.write(json.dumps(state,separators=(",",":"))+"\n")
            summary_rows.append(dict(local_timestamp=local,timestamp_utc=datetime.fromtimestamp(local/1e6,timezone.utc).isoformat(),
                                     bid_price=str(bid),ask_price=str(ask),spread_usd=str(ask-bid),
                                     bid_levels=len(books["bid"]),ask_levels=len(books["ask"]),crossed_or_locked=is_crossed))
            checkpoints+=1
            next_checkpoint=(local//60000000+1)*60000000
        with gzip.open(OUT/"raw/incremental_book_L2.csv.gz","rt",newline="") as f:
            reader=csv.DictReader(f)
            for row in reader:
                row_count+=1
                if row["exchange"]!="deribit" or row["symbol"]!=SYMBOL:raise ValueError("Unexpected instrument")
                local=int(row["local_timestamp"]);exchange=int(row["timestamp"])
                if first is None:first=local
                last=local
                if previous_local is not None:
                    local_regressions+=local<previous_local
                    largest_gap=max(largest_gap,local-previous_local)
                    exchange_regressions+=exchange<previous_exchange
                previous_local,previous_exchange=local,exchange
                if group_time is not None and local!=group_time:finish_group(group_time)
                group_time=local
                snapshot=row["is_snapshot"]=="true"
                if snapshot and not in_snapshot:
                    books={"bid":{},"ask":{}}
                    started=True
                    counts["snapshot_blocks"]+=1
                in_snapshot=snapshot
                counts["snapshot_rows" if snapshot else "update_rows"]+=1
                if not started:
                    counts["rows_before_first_snapshot"]+=1
                    continue
                side=row["side"]
                if side not in books:raise ValueError("Unknown side")
                p,q=Decimal(row["price"]),Decimal(row["amount"])
                if not p.is_finite() or not q.is_finite() or p<=0 or q<0:raise ValueError("Invalid level")
                if q:books[side][p]=q
                else:
                    books[side].pop(p,None)
                    counts["zero_size_removals"]+=1
                if row_count%1000000==0:
                    save(OUT/"replay_progress.json",dict(rows_processed=row_count,checkpoints=checkpoints,updated_at=datetime.now(timezone.utc).isoformat()))
        if group_time is not None:finish_group(group_time)
    with (OUT/"book_summary_1m.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(summary_rows[0]));writer.writeheader();writer.writerows(summary_rows)
    return dict(rows=row_count,**counts,checkpoints=checkpoints,first_local_timestamp=first,last_local_timestamp=last,
                first_utc=datetime.fromtimestamp(first/1e6,timezone.utc).isoformat(),
                last_utc=datetime.fromtimestamp(last/1e6,timezone.utc).isoformat(),
                local_timestamp_regressions=local_regressions,exchange_timestamp_regressions=exchange_regressions,
                maximum_observed_message_gap_seconds=largest_gap/1e6,
                crossed_or_locked_sampled_books=crossed,max_bid_levels_at_checkpoints=max_bid,max_ask_levels_at_checkpoints=max_ask,
                gzip_crc_verified=True,ended_in_snapshot_block=in_snapshot,
                update_rule="Replace the quantity at (side,price); zero removes. Snapshot blocks reset both sides.",
                limitation="Normalized CSV omits native sequence numbers and explicit disconnect events; continuity cannot be independently established here.")


def audit_trades():
    count=0;sides=Counter();first=last=None
    with gzip.open(OUT/"raw/trades.csv.gz","rt",newline="") as f:
        reader=csv.DictReader(f)
        fields=reader.fieldnames
        for row in reader:
            if row["exchange"]!="deribit" or row["symbol"]!=SYMBOL:raise ValueError("Unexpected trade instrument")
            if Decimal(row["price"])<=0 or Decimal(row["amount"])<0:raise ValueError("Invalid trade")
            local=int(row["local_timestamp"])
            if first is None:first=local
            last=local;count+=1;sides[row["side"]]+=1
    return dict(rows=count,columns=fields,sides=dict(sides),first_local_timestamp=first,last_local_timestamp=last,
                first_utc=datetime.fromtimestamp(first/1e6,timezone.utc).isoformat(),
                last_utc=datetime.fromtimestamp(last/1e6,timezone.utc).isoformat(),gzip_crc_verified=True,
                quantities="Preserved in original Deribit units; instrument convention must be verified before BTC conversion.")


def main():
    (OUT/"raw").mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    with ThreadPoolExecutor(max_workers=2) as pool:downloads=list(pool.map(download,KINDS))
    save(OUT/"downloads.json",downloads)
    book=replay_book()
    trades=audit_trades()
    report=dict(source="Tardis historical Deribit BTC-PERPETUAL",date="2025-01-01",book=book,trades=trades,
                complete_source_files_downloaded=True,download_checksums=downloads,
                native_exchange_message_access_tested=False,orders_submitted=0,elapsed_seconds=time.monotonic()-start)
    save(OUT/"audit.json",report)
    print(json.dumps({k:v for k,v in report.items() if k!="download_checksums"},indent=2))


if __name__=="__main__":main()
