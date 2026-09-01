# Mockup: the ledger (`docs/.claims.toml`)

**Status: mockup for review.** This is what gets checked into the audited
repository — one entry per claim, carrying the verdict and what settled it.
TOML because it merges and reviews better than JSON in a PR diff.

```toml
# Written by lie-detector. Each entry is a claim and the evidence that
# settled it. Regenerate stale entries with:  lie-detector verify --stale
schema = 1
corpus = ["docs", "README.md"]
generated_at = "2026-09-01T14:02:11Z"

[[claim]]
id = "4e2331565ece"
file = "docs/relay.md"
line = 13
text = "The `--batch-size` flag defaults to 500 events per flush."
text_hash = "b41c9f2a"
class = "A"                      # numeric or default
verdict = "supported"
verified_at = "2026-09-01T14:02:11Z"
verified_by = "claude-opus-5"
revision = "a6ae07d"
  [[claim.evidence]]
  file = "src/relay.py"
  symbol = "BATCH_SIZE"
  lines = "3"
  hash = "7d1e0c44"
  quote = "BATCH_SIZE = 500"
  note = "The CLI passes BATCH_SIZE through unchanged (cli.py:19)."

[[claim]]
id = "54df497d89ca"
file = "docs/relay.md"
line = 16
text = "Relay retries a failed flush 5 times before parking the batch."
text_hash = "1a90ff3c"
class = "A"
verdict = "refuted"
severity = "high"                # a reader acting on this gets it wrong
correction = "Relay retries a failed flush 3 times before parking the batch."
verified_at = "2026-09-01T14:02:11Z"
verified_by = "claude-opus-5"
revision = "a6ae07d"
  [[claim.evidence]]
  file = "src/relay.py"
  symbol = "MAX_RETRIES"
  lines = "5"
  hash = "22c8ab90"
  quote = "MAX_RETRIES = 3"
  note = "flush() loops `range(MAX_RETRIES)`; no other retry path exists."

[[claim]]
id = "962ec91646a6"
file = "docs/relay.md"
line = 24
text = "Every batch is written to the journal before it is sent, so a crash loses nothing that was acknowledged."
text_hash = "0cc71d5b"
class = "C"                      # guarantee
verdict = "unsupported"
searched = ["journal", "wal", "fsync", "durable", "src/**", "tests/**"]
note = "No journal exists in the tree. The claim may describe a component that lives elsewhere; it is not refuted, it is unsettleable from this repository."
verified_at = "2026-09-01T14:02:11Z"
verified_by = "claude-opus-5"
revision = "a6ae07d"

[[claim]]
id = "39dce6d1f09c"
file = "docs/relay.md"
line = 21
text = "No event is ever delivered twice: the sink writer is idempotent on the event id."
text_hash = "e5518f77"
class = "C"
verdict = "supported"
guarded_by = []                  # ← nothing would fail if this broke
verified_at = "2026-09-01T14:02:11Z"
verified_by = "claude-opus-5"
revision = "a6ae07d"
  [[claim.evidence]]
  file = "src/sink.py"
  symbol = "SinkWriter.write"
  lines = "40-58"
  hash = "9be40a1c"
  quote = "if event.id in self._seen: return True"

[[claim]]
id = "7f30ba9c1d02"
file = "docs/relay.md"
line = 3
text = "Relay is designed for reliability at any scale."
text_hash = "44de81b0"
class = "-"
verdict = "unverifiable"
note = "No evidence could settle this. Rewrite it into a claim with a subject the code has, or cut it."
verified_at = "2026-09-01T14:02:11Z"
```

## What each field is for

`text_hash` and every `claim.evidence.hash` are the staleness anchors. Edit
the sentence, or edit `src/relay.py:5`, and this entry stops being live.

`guarded_by` is the list of tests that would fail if the claim stopped being
true. Empty on a `supported` guarantee is its own finding: the claim holds
today by accident, and nothing will notice when it stops.

`severity` appears only on `refuted`, and only the author sets it — it is
the difference between a wrong adjective and a wrong default that a reader
will act on.

`searched` appears only on `unsupported`, and it is what makes that verdict
falsifiable by a reader: if the journal does exist and the search was just
bad, the list shows exactly how it was bad.
