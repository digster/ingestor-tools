# Architecture

## Overview

The Newsletter Organizer is a single-script Python tool that reads ingested email files and organizes them into label-based folders. It's part of the broader `email-analyzer` project.

## Data Flow

```
output/markdown/*.md  ──→  parse frontmatter  ──→  filter labels  ──→  newsletters/{label}/
output/raw/*.html|txt  ──→  match by ID prefix ─────────────────────→  newsletters/{label}/
```

## Key Design Decisions

- **ID Mapping**: MD filenames contain an 8-char hex ID prefix; raw files use the full 16-char ID. Matching uses `startswith()` on the raw filename stem.
- **Multi-label Fan-out**: Emails with multiple meaningful labels are copied to ALL matching folders (trades disk space for discoverability).
- **Idempotent**: Files already present in the destination are skipped, making reruns safe.
- **Stop-list Driven**: Label filtering uses an external text file (`label-stop-list.txt`) so it can be updated without code changes.

## Project Structure

```
ingestor-tools/
├── src/newsletter_organizer.py   # Main script (all logic in one file)
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
