"""Offline CRC deployment checks: no credentials, subscriptions or network."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'market_data'))
import record_btc_archive as archive
import audit_btc_archive as audit


class CrcCaptureTest(unittest.TestCase):
    def test_total_cap_counts_previous_runs_and_partial_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'new';out.mkdir()
            (root/'previous').mkdir()
            (root/'previous'/'hour.jsonl.gz').write_bytes(b'x'*6)
            (out/'hour.jsonl.gz.partial').write_bytes(b'x'*5)
            self.assertIsNone(archive.storage_stop_reason(out,1,0,root,12/1024**3))
            self.assertEqual(archive.storage_stop_reason(out,1,0,root,10/1024**3),'total_archive_cap_reached')
            self.assertEqual(archive.storage_stop_reason(out,4/1024**3,0),'archive_cap_reached')
            (root/'metadata.json').write_bytes(b'xx')
            self.assertEqual(archive.directory_bytes(root),13)

    def test_full_archive_is_rejected_before_authentication(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'old.gz').write_bytes(b'123')
            argv=['recorder','--out',str(root/'new'),'--kalshi-only','--storage-root',str(root),
                  '--max-total-gb',str(2/1024**3)]
            output=io.StringIO()
            with (patch.object(sys,'argv',argv),patch.object(archive,'headers') as headers,
                  redirect_stdout(output)):
                self.assertEqual(archive.main(),1)
                headers.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())['stop_reason'],'total_archive_cap_reached')

    def test_kalshi_only_shutdown_produces_closed_replayable_archive(self):
        def fake_feed(args,stop,state):
            book=archive.PerpBook()
            event=dict(type='orderbook_snapshot',sid=1,seq=1,msg=dict(market_ticker=archive.TICKER,
                bid=[['8.0000','12.00']],ask=[['8.0001','15.00']]))
            log=archive.HourlyLog(args.out/'kalshi_perp','kalshi_perp')
            log.write(dict(epoch=1,received_at=archive.utc(),message=event));book.apply(event)
            log.write(dict(control='book_checkpoint',epoch=1,received_at=archive.utc(),book=book.checkpoint()))
            (args.out/'kalshi_market.json').write_text(json.dumps(dict(market=dict(contract_size='0.0001'))))
            state.update(state='collecting',connections=1,checkpoints=1)
            stop.wait(3)
            log.close()
            state.update(state='stopped',closed_segments=log.segments,stored_bytes=log.stored_bytes,
                         message_counts={'orderbook_snapshot':1})
        with tempfile.TemporaryDirectory() as directory:
            argv=['recorder','--out',directory,'--kalshi-only','--seconds','.01']
            with (patch.object(sys,'argv',argv),patch.object(archive,'headers',return_value={}),
                  patch.object(archive,'coinbase_credentials') as coinbase,
                  patch.object(archive,'run_kalshi',side_effect=fake_feed),redirect_stdout(io.StringIO())):
                self.assertEqual(archive.main(),0)
                coinbase.assert_not_called()
            out=Path(directory);final=json.loads((out/'manifest.json').read_text())
            self.assertEqual(final['state'],'stopped')
            self.assertEqual(set(final['feeds']),{'kalshi_perp'})
            self.assertFalse(list(out.rglob('*.partial')))
            with patch.object(sys,'argv',['audit','--out',directory]),redirect_stdout(io.StringIO()):audit.main()
            self.assertTrue(json.loads((out/'final_validation.json').read_text())['passed'])

    def test_worker_failure_stops_job_with_nonzero_result(self):
        with tempfile.TemporaryDirectory() as directory:
            argv=['recorder','--out',directory,'--kalshi-only']
            with (patch.object(sys,'argv',argv),patch.object(archive,'headers',return_value={}),
                  patch.object(archive,'run_kalshi',side_effect=OSError('offline fixture')),
                  redirect_stdout(io.StringIO())):
                self.assertEqual(archive.main(),1)
            final=json.loads((Path(directory)/'manifest.json').read_text())
            self.assertEqual(final['state'],'failed')
            self.assertEqual(final['stop_reason'],'feed_stopped')

    def test_startup_timeout_stops_reconnecting_worker(self):
        def fake_feed(args,stop,state):
            state.update(state='reconnecting');stop.wait(3);state.update(state='stopped')
        with tempfile.TemporaryDirectory() as directory:
            argv=['recorder','--out',directory,'--kalshi-only','--startup-timeout','.01']
            with (patch.object(sys,'argv',argv),patch.object(archive,'headers',return_value={}),
                  patch.object(archive,'run_kalshi',side_effect=fake_feed),redirect_stdout(io.StringIO())):
                self.assertEqual(archive.main(),1)
            final=json.loads((Path(directory)/'manifest.json').read_text())
            self.assertEqual(final['stop_reason'],'startup_timeout')


if __name__=='__main__':unittest.main()
