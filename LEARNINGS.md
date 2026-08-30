# Learnings

Pitfalls discovered while working on this tool. Read before changing identifier
handling or rebuilding `../newsletters`.

## `organize()` only copies — it never deletes

Every rerun is additive. A directory that the source no longer produces stays on
disk forever, and because reruns are idempotent-by-skipping, nothing ever
reports it.

Two consequences:

- **Never rebuild in place.** Generate into a fresh directory, diff against the
  existing tree, then swap. Running into the live tree hides exactly the drift
  you need to see.
- **Diff in both directions.** "New dirs not in old" catches additions; "old
  dirs not in new" is the one that matters, because that is silent drift.

The 2026-08-29 rebuild found 3 such directories under `Ryan Holiday` — real,
published emails whose source `.md` and raw files had been deleted from
`../output` outside the pipeline (the drift documented in `gmail-ingestor`'s
`LEARNINGS.md`). A naive in-place rerun would have preserved them by accident
and never surfaced them; a naive fresh rebuild would have dropped 3 live emails
from the website. They were carried across deliberately.

## Never truncate a Gmail message ID

Gmail's `messages.id` is time-ordered, not a hash, so a prefix is not uniformly
distributed. Truncating to 8 chars produced 6 colliding pairs across ~17k
messages — every pair delivered within ~2 hours of each other. See
`gmail-ingestor/LEARNINGS.md` for the measurements.

The damage here was in `find_raw_files()`, which matched raw bodies with
`startswith()` on the truncated ID:

```
newsletters/Byrne/19731332/          <- Byrne's .md
    197313327f3340f8.html            <- Tyler Cowen's body, copied in by the prefix match
    1973133282ce4b60.html            <- Byrne's own body
```

Downstream, `newsletters-web` builds one record per directory and picks
`sorted(glob("*.html"))[0]`, so 5 emails were published with **the wrong body
under the right headline**, and 1 was dropped entirely. None of this raised a
warning anywhere.

**Rule:** directory names, filenames and lookups all use the full 16-char ID.
The invariant to assert in tests and rebuild checks is *one email per
directory* — one `.md`, and raw files whose stem equals the directory name.

## Prefer an exact path lookup over a glob-and-filter

`find_raw_files()` used to glob the whole raw directory and prefix-match every
entry, for every markdown file: ~17k × ~32k ≈ 544M path comparisons. Since raw
files are named exactly `{message_id}.{ext}`, two `Path.exists()` calls do the
same job. A full rebuild went from minutes to ~20 seconds.

One thing the rewrite gives up for free: a scan can only ever return paths
*inside* `raw_dir`, whereas a constructed path cannot. `extract_message_id()`
falls back to the whole filename stem when there is no underscore, so a
malformed name could otherwise address files outside the directory. The guard in
`find_raw_files()` restores that invariant explicitly.

## A skipped email is invisible

`parse_frontmatter()` returns `None` on a YAML error and `organize()` logs a
warning and moves on. That is the right behaviour, but it means a systematic
upstream bug shows up as *nothing at all* downstream — no directory, no manifest
entry, no broken link.

16 Psmith emails were missing from `../newsletters` for months because their
`from:` header contained a backslash that `gmail-ingestor` failed to escape.
Nobody noticed, because absence has no symptom.

**Rule:** after a rebuild, reconcile counts against the source
(`ls output/markdown | wc -l`) rather than trusting that the run "succeeded".
Zero warnings in the log is a much weaker signal than a count that matches.
