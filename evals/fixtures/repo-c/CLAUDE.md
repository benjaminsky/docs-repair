# Relay

Relay is a message queue for event pipelines. The broker lives in `src/`,
the docs in `docs/`.

## Conventions

- Delivery is at-least-once. Consumers must be idempotent.
- Config is read from `relay.toml` at startup and never re-read.
- Run `pytest` from the repository root before committing.

## Writing docs

State what the system does today, in the present tense. Link to code by
path, and prefer a table to a bullet list when the rows are parallel.
