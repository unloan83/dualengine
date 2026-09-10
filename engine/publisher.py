from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import uuid
import duckdb
import zmq
from trading_contracts.schemas.v1 import Direction, MarketRegime, SignalCandidate


class SignalPublisher:

    def __init__(
        self,
        ipc_endpoint: str | None = None,
        db_path: str = "data/shadow_signals.duckdb",
    ):
        if ipc_endpoint is None:
            ipc_dir = Path("/home/ubuntu/run")
            if ipc_dir.exists() and os.access(str(ipc_dir), os.W_OK):
                ipc_endpoint = "ipc:///home/ubuntu/run/signals.ipc"
            else:
                ipc_endpoint = "ipc:///tmp/signals.ipc"

        self.ipc_endpoint = ipc_endpoint
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(ipc_endpoint)

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_conn = duckdb.connect(str(self.db_path))
        self._init_db()

    def _init_db(self):
        self.db_conn.execute("""
            CREATE TABLE IF NOT EXISTS shadow_signals (
                signal_id VARCHAR PRIMARY KEY,
                instrument_id VARCHAR,
                created_at TIMESTAMP,
                valid_until TIMESTAMP,
                direction VARCHAR,
                setup_type VARCHAR,
                regime VARCHAR,
                confidence DOUBLE,
                entry_trigger DOUBLE,
                invalidation_level DOUBLE,
                reason_codes VARCHAR,
                feature_version VARCHAR
            )
        """)

    def publish_signal(
        self,
        instrument_id: str,
        direction: Direction,
        setup_type: str,
        regime: MarketRegime,
        confidence: float,
        entry_price: float,
        stop_loss: float,
        reasons: list[str],
        validity_seconds: int = 60,
    ) -> SignalCandidate:
        now = datetime.now(timezone.utc)
        signal = SignalCandidate(
            signal_id=str(uuid.uuid4()),
            instrument_id=instrument_id,
            created_at=now,
            valid_until=now + timedelta(seconds=validity_seconds),
            direction=direction,
            setup_type=setup_type,
            regime=regime,
            confidence=confidence,
            entry_trigger=entry_price,
            invalidation_level=stop_loss,
            reason_codes=reasons,
        )

        # 1. ZeroMQ Broadcast
        payload = signal.model_dump_json()
        self.socket.send_multipart(
            [signal.instrument_id.encode("utf-8"), payload.encode("utf-8")]
        )

        # 2. DuckDB Shadow Log
        self.db_conn.execute(
            """
            INSERT INTO shadow_signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                signal.signal_id,
                signal.instrument_id,
                signal.created_at,
                signal.valid_until,
                signal.direction.value,
                signal.setup_type,
                signal.regime.value,
                signal.confidence,
                signal.entry_trigger,
                signal.invalidation_level,
                json.dumps(signal.reason_codes),
                signal.feature_version,
            ),
        )

        return signal

    def close(self):
        try:
            self.socket.close(linger=0)
            self.context.term()
        except Exception:
            pass
        try:
            self.db_conn.close()
        except Exception:
            pass
