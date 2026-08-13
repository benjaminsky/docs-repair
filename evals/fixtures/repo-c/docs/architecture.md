# Architecture

## Summary of Changes

The following changes were made in this update: the scheduler was refactored
to utilize a worker pool, which facilitates parallel dispatch and empowers
consumers to process partitions independently.

All 47 tests pass.

## Overview

Relay leverages a robust caching layer for lightning-fast responses.
The scheduler plays a crucial role in ensuring seamless delivery, and the
journal format is a testament to the power of append-only design.

Messages flow from producers into partitions; each partition is owned by one
scheduler shard. For deployment, see [the deployment guide](./deploy.md).

The journal is an append-only log segmented at 64 MB. Segments older than the
retention window are deleted by the compactor, which runs every five minutes.
