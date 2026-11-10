"""Offline tests for hourly replay boundaries and the small Coinbase reference."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

BASE=Path(__file__).resolve().parents[1]/'market_data'
sys.path.insert(0,str(BASE))
import record_btc_archive as archive
import btc_archive_control as control


class ArchiveTest(unittest.TestCase):
    def test_rotation_carries_pre_event_book_and_closes_gzip(self):
        clock=[3599.0];book=archive.PerpBook()
        snapshot=dict(type='orderbook_snapshot',sid=1,seq=1,msg=dict(market_ticker=archive.TICKER,
            bid=[['8.0000','12.00']],ask=[['8.0001','15.00']]))
        book.apply(snapshot)
        with tempfile.TemporaryDirectory(prefix='tda-hourly-') as directory:
            log=archive.HourlyLog(directory,'kalshi_perp',lambda:dict(epoch=1,**book.checkpoint()),lambda:clock[0])
            for seq,delta in [(2,'-2.50'),(3,'1.25')]:
                if seq==3:clock[0]=3600.1
                event=dict(type='orderbook_delta',sid=1,seq=seq,msg=dict(market_ticker=archive.TICKER,
                           side='bid',price='8.0000',delta=delta))
                log.write(dict(epoch=1,message=event));book.apply(event)
                log.write(dict(control='book_checkpoint',epoch=1,book=book.checkpoint()))
                log.flush()
                self.assertTrue(control.inspect(log.current_path)['passed'])
            log.close()
            files=sorted(Path(directory).glob('*.jsonl.gz'))
            self.assertEqual(len(files),2)
            self.assertFalse(list(Path(directory).glob('*.partial')))
            for path in files:
                with gzip.open(path,'rt') as stream:rows=[json.loads(line) for line in stream]
                anchor=rows[0]['book_anchor']
                replay=archive.PerpBook()
                replay.apply(dict(type='orderbook_snapshot',sid=anchor['sid'],seq=anchor['seq'],
                    msg=dict(market_ticker=archive.TICKER,bid=anchor['bid'],ask=anchor['ask'])))
                for row in rows[1:]:
                    if 'message' in row:replay.apply(row['message'])
                    else:self.assertEqual(replay.checkpoint(),row['book'])
                manifest=json.loads(path.with_suffix('.manifest.json').read_text())
                self.assertEqual(manifest['rows'],len(rows))
                self.assertEqual(manifest['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
                checked=control.inspect(path)
                self.assertTrue(checked['final_hash_verified'])
                self.assertEqual(checked['checkpoints_matched'],1)
            with gzip.open(files[1],'rt') as stream:
                self.assertEqual(json.loads(next(stream))['book_anchor']['seq'],2)

    def test_reference_excludes_historical_trades_and_keeps_exact_interval_totals(self):
        reference=archive.Reference()
        quote=dict(channel='ticker',timestamp='2026-11-05T01:00:00Z',sequence_num=0,
            events=[dict(tickers=[dict(product_id='BTC-USD',best_bid='80000.00',best_ask='80000.02',
                        best_bid_quantity='0.10',best_ask_quantity='0.20',price='80000.02')])])
        reference.apply(quote,'received',10)
        def trade(kind,identifier,size):
            return dict(channel='market_trades',events=[dict(type=kind,trades=[dict(product_id='BTC-USD',
                trade_id=identifier,time='2026-11-05T01:00:00.100Z',price='80000.00',size=size)])])
        reference.apply(trade('snapshot','past','2.0'),'received',10)
        reference.apply(trade('update','past','2.0'),'received',10)
        reference.apply(trade('update','new','0.001'),'received',10)
        reference.apply(trade('update','new','0.001'),'received',10)
        sample=reference.sample(1,True,10,10.5)
        self.assertEqual(sample['midpoint'],'80000.01')
        self.assertEqual(sample['quote_age_ms'],500)
        self.assertEqual(sample['trade_count'],1)
        self.assertEqual(sample['trade_btc'],'0.001')
        self.assertEqual(archive.Decimal(sample['trade_notional_usd']),archive.Decimal('80'))
        self.assertEqual(reference.sample(1,True,10.5,11)['trade_count'],0)


if __name__=='__main__':unittest.main()
