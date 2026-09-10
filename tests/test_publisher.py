from datetime import datetime, timezone
import json
import tempfile
import time
import unittest
from pathlib import Path
import zmq
from engine.publisher import SignalPublisher
from trading_contracts.schemas.v1 import Direction, MarketRegime, SignalCandidate


class TestSignalPublisher(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ipc_endpoint = f"ipc://{self.temp_dir.name}/test_signals.ipc"
        self.db_path = str(Path(self.temp_dir.name) / "test_shadow_signals.duckdb")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_publisher_zmq_and_duckdb(self):
        # 1. Initialize publisher (binds PUB socket)
        publisher = SignalPublisher(ipc_endpoint=self.ipc_endpoint, db_path=self.db_path)

        # 2. Initialize subscriber (connects SUB socket)
        context = zmq.Context()
        subscriber = context.socket(zmq.SUB)
        subscriber.connect(self.ipc_endpoint)
        subscriber.setsockopt_string(zmq.SUBSCRIBE, "")
        time.sleep(0.2)  # Avoid ZeroMQ slow joiner message loss

        # 3. Publish signal
        signal = publisher.publish_signal(
            instrument_id="RELIANCE",
            direction=Direction.LONG,
            setup_type="CPR_OI_INTELLIGENCE",
            regime=MarketRegime.TRENDING,
            confidence=0.85,
            entry_price=2500.0,
            stop_loss=2480.0,
            reasons=["ABOVE_CPR", "OI_LONG_BUILDUP"],
            validity_seconds=60,
        )

        self.assertIsInstance(signal, SignalCandidate)
        self.assertEqual(signal.instrument_id, "RELIANCE")
        self.assertEqual(signal.direction, Direction.LONG)
        self.assertEqual(int((signal.valid_until - signal.created_at).total_seconds()), 60)

        # 4. Receive via ZeroMQ Subscriber
        topic, payload = subscriber.recv_multipart()
        self.assertEqual(topic.decode("utf-8"), "RELIANCE")
        rec_signal = SignalCandidate.model_validate_json(payload.decode("utf-8"))
        self.assertEqual(rec_signal.signal_id, signal.signal_id)

        # 5. Verify DuckDB Storage
        rows = publisher.db_conn.execute("SELECT * FROM shadow_signals WHERE signal_id = ?", (signal.signal_id,)).fetchall()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row[0], signal.signal_id)
        self.assertEqual(row[1], "RELIANCE")
        self.assertEqual(row[4], "LONG")

        publisher.close()
        subscriber.close(linger=0)
        context.term()


if __name__ == "__main__":
    unittest.main()
