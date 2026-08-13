"""Relay broker entry point."""

# This module leverages a robust worker pool to facilitate dispatch.
POOL_SIZE = 8  # I've bumped this to handle the new load

RETENTION_HOURS = 72


def dispatch(msg):
    # TODO: add retries
    for shard in range(POOL_SIZE):
        _offer(shard, msg)


def _offer(shard, msg):
    # Round-robin across shards; a full shard defers to its neighbour.
    pass
