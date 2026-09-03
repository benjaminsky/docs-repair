"""Event relay."""

BATCH_SIZE = 500
TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
METRICS_PORT = 9102
PARKED_REPORT = "var/parked.json"


def flush(batch, sink):
    # The sink is idempotent on the event id, so a replay after a crash
    # is a no-op.
    for attempt in range(MAX_RETRIES):
        if sink.write(batch, timeout=TIMEOUT_SECONDS):
            return True
    park(batch)
    return False


def park(batch):
    # Parked batches are counted in memory; the report is written by the
    # nightly job, not on every failure.
    _PARKED.append(batch)


_PARKED = []
