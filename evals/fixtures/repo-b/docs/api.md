# API

**How to read this.** Every endpoint lists its method and path.

`GET /items` returns a page of items. `POST /items` creates one.

Two things follow from the table above and are already enforced in the code:

- Rate limits are per-token, not per-IP.
- A 429 carries a `Retry-After` header.

Pagination uses a cursor rather than an offset. Worth a glance while you are
here: the cursor is opaque and must not be parsed.
