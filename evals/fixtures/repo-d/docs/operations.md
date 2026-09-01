# Operations

## Draining

Draining a node stops the intake and flushes whatever is in memory. The
drain exits with status 0 once the last batch is acknowledged.

The drain never blocks longer than the configured timeout.

## Metrics

Relay exposes counters on port 9102, and the exporter is enabled by
default.

Every counter resets on restart, which is why the dashboards use rates
rather than totals.
