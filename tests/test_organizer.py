"""Tests for newsletter_organizer.py"""

import textwrap
from pathlib import Path

import pytest

from src.newsletter_organizer import (
    copy_file_if_new,
    extract_truncated_id,
    filter_labels,
    find_raw_files,
    load_stop_list,
    organize,
    parse_frontmatter,
)


# ---------------------------------------------------------------------------
# Unit tests: load_stop_list
# ---------------------------------------------------------------------------

class TestLoadStopList:
    def test_loads_labels(self, tmp_path):
        f = tmp_path / "stop.txt"
        f.write_text("INBOX\nSPAM\nUNREAD\n")
        result = load_stop_list(f)
        assert result == {"INBOX", "SPAM", "UNREAD"}

    def test_skips_blank_lines(self, tmp_path):
        f = tmp_path / "stop.txt"
        f.write_text("INBOX\n\n\nSPAM\n")
        result = load_stop_list(f)
        assert result == {"INBOX", "SPAM"}

    def test_missing_file_returns_empty(self, tmp_path):
        result = load_stop_list(tmp_path / "nonexistent.txt")
        assert result == set()


# ---------------------------------------------------------------------------
# Unit tests: parse_frontmatter
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    def test_valid_frontmatter(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text(textwrap.dedent("""\
            ---
            subject: "Test Email"
            labels: ["INBOX", "Newsletter"]
            ---
            Body content here.
        """))
        result = parse_frontmatter(md)
        assert result is not None
        assert result["subject"] == "Test Email"
        assert result["labels"] == ["INBOX", "Newsletter"]

    def test_no_frontmatter(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("Just body content, no frontmatter.")
        result = parse_frontmatter(md)
        assert result is None

    def test_empty_labels(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text(textwrap.dedent("""\
            ---
            subject: "No Labels"
            labels: []
            ---
            Body.
        """))
        result = parse_frontmatter(md)
        assert result["labels"] == []

    def test_malformed_yaml(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("---\n: invalid: yaml: [[\n---\nBody.")
        result = parse_frontmatter(md)
        assert result is None


# ---------------------------------------------------------------------------
# Unit tests: filter_labels
# ---------------------------------------------------------------------------

class TestFilterLabels:
    def test_removes_stop_list_labels(self):
        labels = ["INBOX", "UNREAD", "Ryan Holiday", "SPAM"]
        stop = {"INBOX", "UNREAD", "SPAM"}
        assert filter_labels(labels, stop) == ["Ryan Holiday"]

    def test_case_sensitive(self):
        labels = ["inbox", "INBOX"]
        stop = {"INBOX"}
        assert filter_labels(labels, stop) == ["inbox"]

    def test_all_filtered(self):
        labels = ["INBOX", "UNREAD"]
        stop = {"INBOX", "UNREAD"}
        assert filter_labels(labels, stop) == []

    def test_empty_labels(self):
        assert filter_labels([], {"INBOX"}) == []

    def test_empty_stop_list(self):
        labels = ["A", "B"]
        assert filter_labels(labels, set()) == ["A", "B"]


# ---------------------------------------------------------------------------
# Unit tests: extract_truncated_id
# ---------------------------------------------------------------------------

class TestExtractTruncatedId:
    def test_standard_filename(self):
        assert extract_truncated_id(
            "some-slug_19c869d8.md"
        ) == "19c869d8"

    def test_slug_with_underscores(self):
        # rsplit with maxsplit=1 ensures only the last _ is split
        assert extract_truncated_id(
            "a_long_slug_here_abcd1234.md"
        ) == "abcd1234"

    def test_no_underscore_fallback(self):
        result = extract_truncated_id("weirdname.md")
        assert result == "weirdname"


# ---------------------------------------------------------------------------
# Unit tests: find_raw_files
# ---------------------------------------------------------------------------

class TestFindRawFiles:
    def test_finds_matching_html_and_txt(self, tmp_path):
        (tmp_path / "19c869d898acab8c.html").touch()
        (tmp_path / "19c869d898acab8c.txt").touch()
        (tmp_path / "aaaa000011112222.html").touch()  # unrelated

        result = find_raw_files("19c869d8", tmp_path)
        names = [p.name for p in result]
        assert "19c869d898acab8c.html" in names
        assert "19c869d898acab8c.txt" in names
        assert "aaaa000011112222.html" not in names

    def test_no_matches(self, tmp_path):
        (tmp_path / "aaaa000011112222.html").touch()
        assert find_raw_files("bbbb0000", tmp_path) == []


# ---------------------------------------------------------------------------
# Unit tests: copy_file_if_new
# ---------------------------------------------------------------------------

class TestCopyFileIfNew:
    def test_copies_new_file(self, tmp_path):
        src = tmp_path / "source" / "file.md"
        src.parent.mkdir()
        src.write_text("content")
        dest = tmp_path / "dest"
        dest.mkdir()

        status = copy_file_if_new(src, dest)
        assert status == "copied"
        assert (dest / "file.md").read_text() == "content"

    def test_skips_existing(self, tmp_path):
        src = tmp_path / "source" / "file.md"
        src.parent.mkdir()
        src.write_text("new content")
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "file.md").write_text("old content")

        status = copy_file_if_new(src, dest)
        assert status == "skipped"
        # Original content preserved
        assert (dest / "file.md").read_text() == "old content"


# ---------------------------------------------------------------------------
# Integration test: full organize flow
# ---------------------------------------------------------------------------

class TestOrganizeIntegration:
    def _setup_fixture(self, tmp_path):
        """Create a realistic directory structure for testing."""
        output_dir = tmp_path / "output"
        md_dir = output_dir / "markdown"
        raw_dir = output_dir / "raw"
        newsletters_dir = tmp_path / "newsletters"
        md_dir.mkdir(parents=True)
        raw_dir.mkdir(parents=True)

        # Stop-list
        stop_list = tmp_path / "stop.txt"
        stop_list.write_text("INBOX\nUNREAD\nSPAM\nCATEGORY_PERSONAL\n")

        # Email 1: single meaningful label
        (md_dir / "test-email_aabb1122.md").write_text(textwrap.dedent("""\
            ---
            subject: "Test Email"
            labels: ["INBOX", "UNREAD", "Ryan Holiday"]
            ---
            Body of email 1.
        """))
        (raw_dir / "aabb112233445566.html").write_text("<html>email1</html>")
        (raw_dir / "aabb112233445566.txt").write_text("email1 text")

        # Email 2: multiple meaningful labels
        (md_dir / "multi-label_ccdd3344.md").write_text(textwrap.dedent("""\
            ---
            subject: "Multi Label"
            labels: ["INBOX", "Tech Weekly", "AI News"]
            ---
            Body of email 2.
        """))
        (raw_dir / "ccdd334455667788.html").write_text("<html>email2</html>")

        # Email 3: no meaningful labels → uncategorized
        (md_dir / "no-label_eeff5566.md").write_text(textwrap.dedent("""\
            ---
            subject: "No Label"
            labels: ["INBOX", "SPAM"]
            ---
            Body of email 3.
        """))

        return output_dir, newsletters_dir, stop_list

    def test_single_label(self, tmp_path):
        output_dir, newsletters_dir, stop_list = self._setup_fixture(tmp_path)
        organize(output_dir, newsletters_dir, stop_list)

        rh_dir = newsletters_dir / "Ryan Holiday"
        assert rh_dir.exists()
        assert (rh_dir / "test-email_aabb1122.md").exists()
        assert (rh_dir / "aabb112233445566.html").exists()
        assert (rh_dir / "aabb112233445566.txt").exists()

    def test_multi_label(self, tmp_path):
        output_dir, newsletters_dir, stop_list = self._setup_fixture(tmp_path)
        organize(output_dir, newsletters_dir, stop_list)

        # Should exist in both label folders
        for label in ("Tech Weekly", "AI News"):
            label_dir = newsletters_dir / label
            assert label_dir.exists(), f"Missing folder: {label}"
            assert (label_dir / "multi-label_ccdd3344.md").exists()
            assert (label_dir / "ccdd334455667788.html").exists()

    def test_uncategorized(self, tmp_path):
        output_dir, newsletters_dir, stop_list = self._setup_fixture(tmp_path)
        organize(output_dir, newsletters_dir, stop_list)

        uncat = newsletters_dir / "uncategorized"
        assert uncat.exists()
        assert (uncat / "no-label_eeff5566.md").exists()

    def test_idempotent_rerun(self, tmp_path):
        """Running organize twice should skip already-copied files."""
        output_dir, newsletters_dir, stop_list = self._setup_fixture(tmp_path)
        organize(output_dir, newsletters_dir, stop_list)
        # Run again — should not raise or duplicate
        organize(output_dir, newsletters_dir, stop_list)

        rh_dir = newsletters_dir / "Ryan Holiday"
        assert (rh_dir / "test-email_aabb1122.md").exists()

    def test_missing_raw_files(self, tmp_path):
        """MD file with no matching raw files should still be copied."""
        output_dir, newsletters_dir, stop_list = self._setup_fixture(tmp_path)
        organize(output_dir, newsletters_dir, stop_list)

        # Email 3 has no raw files → still in uncategorized
        uncat = newsletters_dir / "uncategorized"
        assert (uncat / "no-label_eeff5566.md").exists()
