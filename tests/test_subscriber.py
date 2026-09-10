from datetime import datetime, timezone
import unittest
import zmq
from trading_contracts.schemas.v1 import SignalCandidate


def run_subscriber(ipc_endpoint: str = "ipc:///tmp/signals.ipc", timeout_seconds: float | None = None):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(ipc_endpoint)
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    print(f"[*] Listening for DualEngine signals on {ipc_endpoint}...")
    start_time = datetime.now(timezone.utc)

    while True:
        try:
            if socket.poll(timeout=1000):
                topic, payload = socket.recv_multipart()
                signal = SignalCandidate.model_validate_json(payload.decode("utf-8"))
                now = datetime.now(timezone.utc)
                latency_ms = (now - signal.created_at).total_seconds() * 1000

                print(
                    f"[RECEIVED] ID: {signal.signal_id[:8]} | {signal.instrument_id} "
                    f"| {signal.direction} | Latency: {latency_ms:.1f}ms | Valid: {signal.valid_until > now}"
                )
            if timeout_seconds and (datetime.now(timezone.utc) - start_time).total_seconds() > timeout_seconds:
                break
        except KeyboardInterrupt:
            break

    socket.close(linger=0)
    context.term()


class TestSubscriberDiagnostic(unittest.TestCase):
    def test_subscriber_import(self):
        self.assertTrue(callable(run_subscriber))


if __name__ == "__main__":
    run_subscriber()
