# Prompts

## 2026-03-04 — Newsletter Organizer Tool

Implement the following plan:

# Newsletter Organizer Tool

## Context
The `output/` folder contains ingested emails in markdown (with frontmatter metadata) and raw (html/txt) formats. We need a Python tool that reads each email's labels, filters out system/generic labels using a stop-list, and copies the email files into label-named folders under `../newsletters/`. This organizes emails by their meaningful newsletter source label.

## File Mapping
- MD files: `output/markdown/{slug}_{id}.md` — ID is a **truncated prefix** (8 hex chars)
- Raw files: `output/raw/{full_id}.html` and `output/raw/{full_id}.txt` — full ID (16 hex chars)
- Mapping: find raw files whose name **starts with** the truncated ID from the MD filename

## Implementation Plan

### 1. Create project scaffold
- `pyproject.toml` with dependencies: `pyyaml` (frontmatter parsing)
- Use `uv` for package management
- Create `src/newsletter_organizer.py` as the main script

### 2. Main script (`src/newsletter_organizer.py`)

**Constants/Config:**
- `OUTPUT_DIR = ../output` (relative to script or configurable)
- `NEWSLETTERS_DIR = ../newsletters`
- `STOP_LIST_FILE = label-stop-list.txt`

**Flow:**
1. Load stop-list from `label-stop-list.txt` into a set
2. Glob all `.md` files in `output/markdown/`
3. For each MD file:
   a. Parse YAML frontmatter to extract `labels` list
   b. Filter labels: remove any label present in the stop-list (case-sensitive match)
   c. Determine target folder(s)
   d. Extract truncated ID from MD filename (last segment before `.md`)
   e. Find matching raw files in `output/raw/` that start with this ID prefix
   f. Create target folder(s) in `newsletters/` if they don't exist
   g. Skip if exists: check before copying
   h. Copy: MD file + matching `.html` + `.txt` files to each target folder
4. Write a timestamped log file

### 3. Testing strategy
- Unit tests for: frontmatter parsing, label filtering, ID extraction, file mapping
- Integration test with temp directories mimicking the output structure
- Run against actual `output/` data to verify end-to-end
