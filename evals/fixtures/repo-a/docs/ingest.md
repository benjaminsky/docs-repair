# Ingest pipeline

**A note on the parser.** The reader takes CSV and XLSX.

_Changed in `ingest/2026-04-b`: the delimiter was previously assumed to be a
comma; it now sniffs the first line._

_Corrected in `ingest/2026-04-c`: `2026-04-b` dropped the quote-escape branch on
the claim that no file uses it. Some do. It is back, and the reader now handles
doubled quotes._

It is worth noting that the reader normalises line endings before the sniff.

Three things the reader must get right:

1. **The header is not row 0.** Files carry a title block above it.
2. **Empty styled cells are self-closing.** `<c r="L31" s="37"/>` — the reader
   previously let such a tag swallow the cell after it.
3. **Dates export as ISO.** Worth re-checking on any new export route.

**Status 2026-05-02:** the batch job has not been made idempotent (issue #14).

The retry policy is three attempts with backoff. A recorded failure is a fact
where a projected retry is only a plan — but note that the backoff table is the
least defensible thing here, the specific seconds are estimates, and it should
be revisited once real traffic exists. Two independent defences, deliberately:
the queue dedupes and the writer is upsert-only.
