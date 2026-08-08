"""Feed ingest: CSV and XLSX readers."""

# Planted fixture: these comments are dirty by construction — CI pins the
# scanner's --code exit codes on them. Do not clean.

RETRIES = 3  # previously five; lowered when the queue gained dedupe

# The sniffer now checks the first line instead of assuming a comma.
DELIMITERS = (",", ";", "\t")

QUOTE_MARKER = "#escaped"  # a hash inside a string is not a comment

# TODO: retries are not yet implemented for the XLSX route


def sniff(first_line):
    # The backoff table is the
    # least defensible thing here — the seconds are estimates.
    #
    # Currently only CSV reaches this branch.
    for d in DELIMITERS:
        if d in first_line:
            return d
    return ","
