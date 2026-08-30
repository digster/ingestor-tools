# Newsletter Organizer (Ingestor Tools)

Organizes ingested emails from the `output/` directory into label-named folders under `newsletters/` for easy browsing by newsletter source.

## How it works

1. Reads all `.md` files from `output/markdown/` (each has YAML frontmatter with labels)
2. Filters out system/generic labels using `label-stop-list.txt`
3. Copies each email's MD + raw HTML/TXT files into `newsletters/{label}/{message_id}/` subfolders (grouped by full 16-char Gmail message ID)
4. Emails with no meaningful labels go to `newsletters/uncategorized/`
5. Emails with multiple labels are copied to all matching folders

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for package management

## Setup

```bash
uv sync --extra dev
```

## Usage

```bash
# Run with defaults (reads ../output, writes to ../newsletters)
uv run python src/newsletter_organizer.py

# Override paths (positional args: output_dir newsletters_dir stop_list)
uv run python src/newsletter_organizer.py /path/to/output /path/to/newsletters label-stop-list.txt
```

## Testing

```bash
uv run pytest tests/ -v
```

## File structure

```
output/
├── markdown/    # {slug}_{message_id}.md files
└── raw/         # {message_id}.html and .txt files

newsletters/     # Generated output
├── Ryan Holiday/
│   └── 19c869d898acab8c/                # full message-ID subfolder
│       ├── some-email_19c869d898acab8c.md
│       ├── 19c869d898acab8c.html
│       └── 19c869d898acab8c.txt
└── uncategorized/
    └── aabbccdd11223344/
        └── no-label_aabbccdd11223344.md
```

Directory names are the **full 16-char Gmail message ID**. They used to be an
8-char truncation, which collided (see `LEARNINGS.md`) and merged unrelated
emails into one folder. Raw bodies are now located by exact filename rather than
a prefix scan, so one directory always describes exactly one email.

## Stop-list

Edit `label-stop-list.txt` to add/remove labels that should be filtered out (one per line). These are typically Gmail system labels like `INBOX`, `UNREAD`, `SPAM`, etc.

## Logs

Timestamped log files are written to `logs/` on each run.
