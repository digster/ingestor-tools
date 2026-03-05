"""
Newsletter Organizer — reads ingested emails from output/, filters labels
using a stop-list, and copies email files into label-named folders under
../newsletters/ for easy browsing by newsletter source.
"""

import glob
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Defaults (overridable via CLI args or environment)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent          # src/
PROJECT_DIR = SCRIPT_DIR.parent                        # ingestor-tools/
DEFAULT_OUTPUT_DIR = PROJECT_DIR.parent / "output"     # ../output
DEFAULT_NEWSLETTERS_DIR = PROJECT_DIR.parent / "newsletters"  # ../newsletters
DEFAULT_STOP_LIST = PROJECT_DIR / "label-stop-list.txt"
LOG_DIR = PROJECT_DIR / "logs"


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def load_stop_list(path: Path) -> set[str]:
    """Load label stop-list from a text file (one label per line)."""
    if not path.exists():
        logging.warning("Stop-list file not found: %s — proceeding with empty stop-list", path)
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def parse_frontmatter(md_path: Path) -> dict | None:
    """
    Extract YAML frontmatter from a markdown file.

    Frontmatter is delimited by '---' lines at the top of the file.
    Returns the parsed dict, or None if no valid frontmatter is found.
    """
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logging.error("Failed to read %s: %s", md_path, e)
        return None

    # Frontmatter must start with '---'
    if not content.startswith("---"):
        logging.warning("No frontmatter delimiter in %s", md_path.name)
        return None

    # Find closing '---'
    end_idx = content.index("\n") + 1  # skip first '---\n'
    closing = content.find("---", end_idx)
    if closing == -1:
        logging.warning("Unclosed frontmatter in %s", md_path.name)
        return None

    frontmatter_str = content[end_idx:closing]
    try:
        data = yaml.safe_load(frontmatter_str)
        return data if isinstance(data, dict) else None
    except yaml.YAMLError as e:
        logging.error("YAML parse error in %s: %s", md_path.name, e)
        return None


def filter_labels(labels: list[str], stop_list: set[str]) -> list[str]:
    """Remove labels present in the stop-list (case-sensitive)."""
    return [label for label in labels if label not in stop_list]


def extract_truncated_id(md_filename: str) -> str:
    """
    Extract the 8-char hex ID suffix from an MD filename.

    Expected format: {slug}_{id}.md
    Example: 'some-slug_19c869d8.md' → '19c869d8'
    """
    stem = Path(md_filename).stem  # drop .md
    parts = stem.rsplit("_", maxsplit=1)
    if len(parts) < 2:
        return stem  # fallback: return whole stem
    return parts[-1]


def find_raw_files(truncated_id: str, raw_dir: Path) -> list[Path]:
    """
    Find raw (.html/.txt) files whose name starts with the truncated ID.
    """
    matches = []
    for ext in ("*.html", "*.txt"):
        for path in raw_dir.glob(ext):
            if path.stem.startswith(truncated_id):
                matches.append(path)
    return sorted(matches)


def copy_file_if_new(src: Path, dest_dir: Path) -> str:
    """
    Copy src into dest_dir. Skip if the file already exists there.

    Returns a status string: 'copied' or 'skipped'.
    """
    dest = dest_dir / src.name
    if dest.exists():
        return "skipped"
    shutil.copy2(src, dest)
    return "copied"


# ---------------------------------------------------------------------------
# Main organizer logic
# ---------------------------------------------------------------------------

def organize(
    output_dir: Path,
    newsletters_dir: Path,
    stop_list_path: Path,
) -> None:
    """
    Main entry point: read emails from output_dir, organize into newsletters_dir.
    """
    stop_list = load_stop_list(stop_list_path)
    logging.info("Loaded %d stop-list labels", len(stop_list))

    md_dir = output_dir / "markdown"
    raw_dir = output_dir / "raw"

    if not md_dir.exists():
        logging.error("Markdown directory not found: %s", md_dir)
        return

    md_files = sorted(md_dir.glob("*.md"))
    if not md_files:
        logging.warning("No .md files found in %s", md_dir)
        return

    logging.info("Found %d markdown files to process", len(md_files))

    multi_label_log: list[str] = []  # track multi-label cases

    for md_path in md_files:
        logging.info("Processing: %s", md_path.name)

        # --- Parse frontmatter ---
        meta = parse_frontmatter(md_path)
        if meta is None:
            logging.warning("  Skipping (no valid frontmatter)")
            continue

        raw_labels = meta.get("labels", [])
        if not isinstance(raw_labels, list):
            raw_labels = []

        # --- Filter labels ---
        meaningful_labels = filter_labels(raw_labels, stop_list)
        if not meaningful_labels:
            meaningful_labels = ["uncategorized"]
            logging.info("  No meaningful labels → uncategorized")
        else:
            logging.info("  Labels: %s", meaningful_labels)

        if len(meaningful_labels) > 1:
            multi_label_log.append(
                f"{md_path.name} → {meaningful_labels}"
            )

        # --- Find matching raw files ---
        truncated_id = extract_truncated_id(md_path.name)
        raw_files = find_raw_files(truncated_id, raw_dir) if raw_dir.exists() else []
        if not raw_files:
            logging.warning("  No raw files found for ID prefix '%s'", truncated_id)

        # --- Copy to each label folder ---
        files_to_copy = [md_path] + raw_files
        for label in meaningful_labels:
            dest_dir = newsletters_dir / label
            dest_dir.mkdir(parents=True, exist_ok=True)

            for src_file in files_to_copy:
                status = copy_file_if_new(src_file, dest_dir)
                logging.info("  → %s/%s [%s]", label, src_file.name, status)

    # --- Summary ---
    logging.info("=" * 60)
    logging.info("Organization complete.")
    logging.info("  Total MD files processed: %d", len(md_files))
    logging.info("  Multi-label emails: %d", len(multi_label_log))
    for entry in multi_label_log:
        logging.info("    %s", entry)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def setup_logging() -> None:
    """Configure logging to both console and a timestamped log file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_file = LOG_DIR / f"organizer_{timestamp}.log"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )
    logging.info("Log file: %s", log_file)


def main() -> None:
    setup_logging()

    # Allow overriding paths via CLI args (positional: output_dir newsletters_dir)
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT_DIR
    newsletters_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_NEWSLETTERS_DIR
    stop_list_path = Path(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_STOP_LIST

    logging.info("Output dir:      %s", output_dir)
    logging.info("Newsletters dir: %s", newsletters_dir)
    logging.info("Stop-list:       %s", stop_list_path)

    organize(output_dir, newsletters_dir, stop_list_path)


if __name__ == "__main__":
    main()
