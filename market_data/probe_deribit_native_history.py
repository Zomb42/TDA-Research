"""Read one free historical minute in original exchange message format.

Public archive GET only; no credentials, live feed, accounts or orders.
"""
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

OUT=Path(__file__).resolve().parent/"samples/external_historical_books_2026-10-29/deribit_native_minute"


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    filters=[dict(channel=c,symbols=["BTC-PERPETUAL"]) for c in ["book","trades"]]
    params={"from":"2025-01-01","offset":0,"filters":json.dumps(filters,separators=(",",":"))}
    url="https://api.tardis.dev/v1/data-feeds/deribit?"+urllib.parse.urlencode(params)
    meta=dict(url=url,requested_at=datetime.now(timezone.utc).isoformat(),date="2025-01-01",requested_minutes=1)
    try:
        req=urllib.request.Request(url,headers={"Accept-Encoding":"gzip","User-Agent":"TDA-Research/1.0"})
        with urllib.request.urlopen(req,timeout=30) as response:
            body=response.read(4*1024*1024+1)
            meta.update(http_status=response.status,content_encoding=response.headers.get("Content-Encoding"),bytes=len(body))
        if len(body)>4*1024*1024:raise ValueError("Minute exceeded bounded probe cap")
        (OUT/"response.bin").write_bytes(body)
        decoded=gzip.decompress(body) if meta["content_encoding"]=="gzip" or body[:2]==b"\x1f\x8b" else body
        (OUT/"messages.txt").write_bytes(decoded)
        counts=Counter();examples={};book_events=[];disconnects=0
        for line in decoded.decode().splitlines():
            if not line.strip():disconnects+=1;continue
            received,event_json=line.split(" ",1)
            event=json.loads(event_json)
            channel=event.get("params",{}).get("channel","unknown")
            counts[channel]+=1
            data=event.get("params",{}).get("data")
            if channel.startswith("book.") and isinstance(data,dict):
                book_events.append(data)
                key="book_"+data.get("type","unknown")
                if key not in examples:
                    example=dict(data)
                    for side in ["bids","asks"]:
                        if side in example:example[side]=example[side][:2]
                    examples[key]=dict(local_timestamp=received,channel=channel,data=example)
            elif channel.startswith("trades.") and channel not in examples:
                examples[channel]=dict(local_timestamp=received,channel=channel,data=data[:2] if isinstance(data,list) else data)
        previous=None;gaps=0;before_snapshot=0;snapshots=0;changes=0
        for data in book_events:
            if data.get("type")=="snapshot":snapshots+=1;previous=data["change_id"]
            else:
                changes+=1
                if previous is None:before_snapshot+=1
                elif data.get("prev_change_id")!=previous:gaps+=1
                previous=data["change_id"]
        meta.update(sha256=hashlib.sha256(body).hexdigest(),channel_message_counts=dict(counts),
                    native_snapshots=snapshots,native_changes=changes,native_change_id_gaps=gaps,
                    book_changes_before_snapshot=before_snapshot,blank_disconnect_markers=disconnects,
                    examples=examples,scope="One requested historical minute; not a full-day native continuity audit")
    except urllib.error.HTTPError as error:
        meta.update(http_status=error.code,error_type=type(error).__name__)
    except Exception as error:
        meta.update(error_type=type(error).__name__,error=str(error))
    (OUT/"access_test.json").write_text(json.dumps(meta,indent=2)+"\n")
    print(json.dumps(meta,indent=2))


if __name__=="__main__":main()
