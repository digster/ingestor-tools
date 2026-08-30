# Architecture

## Overview

The Newsletter Organizer is a single-script Python tool that reads ingested email files and organizes them into label-based folders. It's part of the broader `email-analyzer` project.

## Data Flow

```
output/markdown/*.md  ──→  parse frontmatter  ──→  filter labels  ──→  newsletters/{label}/{id}/
output/raw/*.html|txt  ──→  exact ID lookup ───────────────────────→  newsletters/{label}/{id}/
```

## Key Design Decisions

- **ID Mapping**: MD filenames and raw files both carry the full 16-char Gmail message ID. `find_raw_files()` builds the two candidate paths directly (`{id}.html`, `{id}.txt`) and checks existence — no directory scan, no prefix matching.
- **ID Subfolder Grouping**: Each email's files (MD + raw HTML/TXT) are grouped into a subfolder named by the full message ID, keeping related files bundled together and guaranteeing one email per directory.
- **Multi-label Fan-out**: Emails with multiple meaningful labels are copied to ALL matching folders (trades disk space for discoverability).
- **Idempotent**: Files already present in the destination are skipped, making reruns safe.
- **Stop-list Driven**: Label filtering uses an external text file (`label-stop-list.txt`) so it can be updated without code changes.

## Project Structure

```
ingestor-tools/
├── src/newsletter_organizer.py   # Main script (all logic in one file)
├── LEARNINGS.md                  # Pitfalls — read before touching ID handling
├── tests/test_organizer.py       # Unit + integration tests
├── label-stop-list.txt           # Labels to filter out
├── logs/                         # Timestamped run logs
└── pyproject.toml                # Dependencies: pyyaml, pytest
```

## External Dependencies

- `pyyaml` — YAML frontmatter parsing
- `pytest` — testing (dev dependency)

## Sibling Directories (in parent email-analyzer/)

- `output/` — ingested emails (input to this tool)
- `newsletters/` — organized output (created by this tool)

## Message Identity

The directory name under each label is the email's **full 16-char Gmail message
ID**, taken from the markdown filename (`{slug}_{message_id}.md`) by
`extract_message_id()`.

This was previously an 8-char truncation. Gmail message IDs are time-ordered
rather than hashed, so truncated prefixes collided for emails delivered close
together — 6 colliding pairs across ~17k messages. Two consequences, both now
fixed upstream and here:

1. `find_raw_files()` matched raw bodies with `startswith()`, so a colliding
   pair's bodies were copied into *both* directories.
2. `newsletters-web` then built one record per directory and picked
   `sorted(glob("*.html"))[0]`, publishing one newsletter's body under another
   newsletter's headline.

The lookup is now exact, which is both correct and dramatically cheaper: the old
scan was O(raw files) per markdown file — roughly 544M path comparisons over the
live corpus. A full rebuild of ~17k emails takes about 20 seconds.

### Rebuilding `../newsletters`

`organize()` only ever **copies** — it never deletes. Running it into an existing
tree therefore leaves stale directories behind and silently masks drift. To
rebuild, generate into a fresh directory and diff before swapping:

```bash
uv run python src/newsletter_organizer.py ../output /tmp/newsletters-fresh label-stop-list.txt
```

Expect one directory per markdown file. Anything in the old tree with no
counterpart in the new one is drift that needs a decision — see `LEARNINGS.md`.
