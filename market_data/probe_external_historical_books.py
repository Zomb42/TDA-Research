"""Small public GET tests of external historical BTC-perp L2 archives.

Range-limited prefixes only, not complete daily datasets or native-message
replay validation. No credentials, account access, live recording, or orders.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.error
import urllib.request
import zlib

OUT = Path(__file__).resolve().parent / "samples/external_historical_books_2026-10-29"
CASES = {
    "deribit_btc_perpetual_2025-01-01": "https://datasets.tardis.dev/v1/deribit/incremental_book_L2/2025/01/01/BTC-PERPETUAL.csv.gz",
    "bitmex_xbtusd_2025-01-01": "https://datasets.tardis.dev/v1/bitmex/incremental_book_L2/2025/01/01/XBTUSD.csv.gz",
}
LIMIT = 512 * 1024


def probe(item):
    name,url = item
    result=dict(name=name,url=url,method="GET",requested_at=datetime.now(timezone.utc).isoformat(),
                requested_compressed_prefix_bytes=LIMIT,complete_daily_file_downloaded=False,
                native_exchange_message_replay_tested=False)
    try:
        request=urllib.request.Request(url,headers={"Range":f"bytes=0-{LIMIT-1}","User-Agent":"TDA-Research/1.0"})
        with urllib.request.urlopen(request,timeout=30) as response:
            payload=response.read(LIMIT)
            result.update(http_status=response.status,content_range=response.headers.get("Content-Range"),
                          content_type=response.headers.get("Content-Type"),compressed_bytes_saved=len(payload))
        (OUT/(name+".prefix.gz.part")).write_bytes(payload)
        result["prefix_sha256"]=hashlib.sha256(payload).hexdigest()
        decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
        decoded=decoder.decompress(payload,16*1024*1024)
        # The compressed prefix can end within a CSV row: retain complete lines only.
        text=decoded.decode("utf-8",errors="strict")
        text=text[:text.rfind("\n")+1]
        (OUT/(name+".prefix.csv")).write_text(text)
        reader=csv.DictReader(io.StringIO(text))
        rows=list(reader)
        result.update(columns=reader.fieldnames,complete_csv_rows_in_prefix=len(rows),
                      first_rows=rows[:3],first_non_snapshot_rows=[r for r in rows if r.get("is_snapshot")=="false"][:3],
                      snapshot_rows_in_prefix=sum(r.get("is_snapshot")=="true" for r in rows),
                      update_rows_in_prefix=sum(r.get("is_snapshot")=="false" for r in rows),
                      symbols=sorted({r.get("symbol","") for r in rows}),
                      first_timestamp=rows[0].get("timestamp") if rows else None,
                      last_timestamp=rows[-1].get("timestamp") if rows else None)
    except urllib.error.HTTPError as error:
        result.update(http_status=error.code,error_type=type(error).__name__)
    except Exception as error:
        result.update(error_type=type(error).__name__,error=str(error))
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(probe,CASES.items()))
    (OUT/"access_tests.json").write_text(json.dumps(results,indent=2)+"\n")
    for r in results:
        print(json.dumps({k:v for k,v in r.items() if k not in ["first_rows","first_non_snapshot_rows"]}))


if __name__=="__main__":main()
