# Relay

Relay forwards events from the ingest queue to the downstream sinks.

## Configuration

| Option | Default | Meaning |
| --- | --- | --- |
| `--batch-size` | 500 | Events per flush |
| `--timeout` | 30 seconds | How long a sink may take |
| `--retries` | 5 | Attempts before the batch is parked |

The `--batch-size` flag defaults to 500 events per flush. Raising it above
the vendor's own ceiling is refused at startup.

Relay retries a failed flush 5 times before parking the batch, and the
delay between attempts doubles each time.

## Guarantees

No event is ever delivered twice: the sink writer is idempotent on the
event id, so a replay after a crash is a no-op.

Every batch is written to the journal before it is sent, so a crash loses
nothing that was acknowledged.

## Requirements

Relay requires Python 3.9 or newer and runs on Linux and macOS.

The parked-batch report is written to `var/parked.json` on every flush
failure.
