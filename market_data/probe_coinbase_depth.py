"""Bounded Coinbase market-data/credential check; no trading code.

Reads existing keys in place. The only authenticated request is GET of key
permissions; output excludes identifiers, tokens and secrets. Public snapshot
and 60-second WebSocket capture measure BTC-USD L2 payload/storage volume.
"""
from collections import Counter
from datetime import datetime, timezone
import base64
import gzip
import json
from pathlib import Path
import secrets
import time
import urllib.error
import urllib.request

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec,ed25519
import jwt
import websocket

BASE=Path(__file__).resolve().parent
SOURCE=BASE.parents[2]/"Junior-Spring/HFT/Kalshi-Orderbook-Predictor"
OUT=BASE/"samples/coinbase_depth_2026-10-29"


def key_check(relative):
    data=json.loads((SOURCE/relative).read_text())
    raw=data["privateKey"]
    result=dict(source_file=relative,field_names=list(data))
    if "BEGIN" not in raw:
        blob=base64.b64decode(raw)
        matched=False
        if len(blob)==64:
            public=ed25519.Ed25519PrivateKey.from_private_bytes(blob[:32]).public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
            matched=public==blob[32:]
        result.update(format="Ed25519 seed+public" if matched else "unclassified raw key",network_tested=False,
                      reason="Coinbase App documentation requires ECDSA; no algorithm guessing or key modification performed")
        return result
    private=serialization.load_pem_private_key(raw.encode(),password=None)
    result.update(format=type(private).__name__,curve=getattr(getattr(private,"curve",None),"name",None))
    if not isinstance(private,ec.EllipticCurvePrivateKey):return result
    name=data.get("name") or data.get("id")
    path="/api/v3/brokerage/key_permissions"
    now=int(time.time())
    token=jwt.encode(dict(sub=name,iss="cdp",nbf=now,exp=now+120,uri="GET api.coinbase.com"+path),private,
                     algorithm="ES256",headers=dict(kid=name,nonce=secrets.token_hex(16)))
    req=urllib.request.Request("https://api.coinbase.com"+path,headers={"Authorization":"Bearer "+token,"User-Agent":"TDA-Research/1.0"},method="GET")
    result["network_tested"]=True
    try:
        with urllib.request.urlopen(req,timeout=20) as response:
            body=json.load(response)
            result.update(http_status=response.status,permissions={k:body.get(k) for k in ["can_view","can_trade","can_transfer"]})
    except urllib.error.HTTPError as error:
        result.update(http_status=error.code,error_type=type(error).__name__)
    except Exception as error:
        result.update(error_type=type(error).__name__)
    return result


def snapshot():
    url="https://api.exchange.coinbase.com/products/BTC-USD/book?level=2"
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"TDA-Research/1.0"}),timeout=20) as response:
        body=response.read(32*1024*1024+1)
        if len(body)>32*1024*1024:raise ValueError("Snapshot exceeds bounded probe cap")
        status=response.status
    with gzip.open(OUT/"public_exchange_snapshot.json.gz","wb") as f:f.write(body)
    data=json.loads(body)
    return dict(url=url,http_status=status,uncompressed_bytes=len(body),compressed_bytes=(OUT/"public_exchange_snapshot.json.gz").stat().st_size,
                bid_levels=len(data["bids"]),ask_levels=len(data["asks"]),exchange_time=data.get("time"),authentication_used=False)


def stream():
    started=time.monotonic();counts=Counter();sizes=Counter();types=Counter()
    l2_updates=0;initial_bytes=0;first_snapshot=None;previous_seq=None;seq_gaps=0;frames=0
    ws=websocket.create_connection("wss://advanced-trade-ws.coinbase.com",timeout=15)
    ws.settimeout(2)
    for channel in ["level2","market_trades","heartbeats"]:
        ws.send(json.dumps(dict(type="subscribe",channel=channel,product_ids=["BTC-USD"])))
    deadline=time.monotonic()+60
    raw_path=OUT/"public_stream.jsonl.gz"
    with gzip.open(raw_path,"xt") as f:
        try:
            while time.monotonic()<deadline and sum(sizes.values())<64*1024*1024:
                try:raw=ws.recv()
                except websocket.WebSocketTimeoutException:continue
                if not raw:break
                message=json.loads(raw);frames+=1
                channel=message.get("channel",message.get("type","unknown"))
                counts[channel]+=1;sizes[channel]+=len(raw.encode())
                # This capture numbers all subscribed channels on one connection.
                # Checking only L2 would falsely count intervening trades/heartbeats as gaps.
                seq=message.get("sequence_num")
                if isinstance(seq,int):
                    if previous_seq is not None and seq!=previous_seq+1:seq_gaps+=1
                    previous_seq=seq
                f.write(json.dumps(dict(received_at=datetime.now(timezone.utc).isoformat(),message=message),separators=(",",":"))+"\n")
                if message.get("type")=="error":raise ValueError("Public subscription error")
                if channel=="l2_data":
                    snap=False
                    for event in message.get("events",[]):
                        kind=event.get("type","unknown");types[kind]+=1
                        if kind=="snapshot":snap=True
                        if kind=="update":l2_updates+=len(event.get("updates",[]))
                    if snap:
                        initial_bytes+=len(raw.encode())
                        first_snapshot=first_snapshot or time.monotonic()
        finally:ws.close()
    ended=time.monotonic()
    observation=max(1,ended-(first_snapshot or started))
    steady=max(0,sizes["l2_data"]-initial_bytes)
    return dict(duration_seconds=ended-started,steady_observation_seconds=observation,message_counts=dict(counts),
                payload_bytes_by_channel=dict(sizes),l2_event_counts=dict(types),l2_level_updates=l2_updates,
                initial_l2_snapshot_payload_bytes=initial_bytes,connection_sequence_discontinuities=seq_gaps,
                saved_gzip_bytes=raw_path.stat().st_size,authentication_used=False,
                estimated_l2_payload_mb_per_hour=steady/observation*3600/1e6,
                estimated_l2_payload_gb_per_day=steady/observation*86400/1e9,
                limitations=["One short live observation; traffic varies with activity and cannot establish historical availability.",
                             "Payload bytes exclude WebSocket/TLS framing. Daily estimate excludes recurring snapshots and is not a capacity guarantee.",
                             "Compressed total includes book, trades, heartbeats and local receipt envelopes."])


def main():
    if (OUT/"public_stream.jsonl.gz").exists():
        raise FileExistsError("Retained capture exists; choose a new output directory before another network probe")
    OUT.mkdir(parents=True,exist_ok=True)
    report=dict(checked_at=datetime.now(timezone.utc).isoformat(),orders_submitted=0,paid_services_used=False)
    report["key_checks"]=[key_check(p) for p in ["secrets/cdp_api_key.json","collector/misc/cdp_api_key.json"]]
    (OUT/"key_checks.json").write_text(json.dumps(report["key_checks"],indent=2)+"\n")
    report["current_snapshot"]=snapshot()
    (OUT/"partial_results.json").write_text(json.dumps(report,indent=2)+"\n")
    report["live_volume_probe"]=stream()
    (OUT/"summary.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
