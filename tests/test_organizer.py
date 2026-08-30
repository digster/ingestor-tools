"""Tests for newsletter_organizer.py"""

import textwrap
from pathlib import Path

import pytest

from src.newsletter_organizer import (
    copy_file_if_new,
    extract_message_id,
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
# Unit tests: extract_message_id
# ---------------------------------------------------------------------------

class TestExtractMessageId:
    def test_standard_filename(self):
        assert extract_message_id(
            "some-slug_19c869d898acab8c.md"
        ) == "19c869d898acab8c"

    def test_slug_with_underscores(self):
        # rsplit with maxsplit=1 ensures only the last _ is split
        assert extract_message_id(
            "a_long_slug_here_abcd12345678ef90.md"
        ) == "abcd12345678ef90"

    def test_no_underscore_fallback(self):
        result = extract_message_id("weirdname.md")
        assert result == "weirdname"

    def test_returns_full_id_not_a_prefix(self):
        """Regression: filenames carry the full 16-char ID, never a truncation."""
        assert extract_message_id(
            "tuesday-assorted-links_1953e3bed494d90c.md"
        ) == "1953e3bed494d90c"


# ---------------------------------------------------------------------------
# Unit tests: find_raw_files
# ---------------------------------------------------------------------------

class TestFindRawFiles:
    def test_finds_matching_html_and_txt(self, tmp_path):
        (tmp_path / "19c869d898acab8c.html").touch()
        (tmp_path / "19c869d898acab8c.txt").touch()
        (tmp_path / "aaaa000011112222.html").touch()  # unrelated

        result = find_raw_files("19c869d898acab8c", tmp_path)
        names = [p.name for p in result]
        assert "19c869d898acab8c.html" in names
        assert "19c869d898acab8c.txt" in names
        assert "aaaa000011112222.html" not in names

    def test_no_matches(self, tmp_path):
        (tmp_path / "aaaa000011112222.html").touch()
        assert find_raw_files("bbbb000000000000", tmp_path) == []

    def test_ids_sharing_a_prefix_do_not_bleed(self, tmp_path):
        """Regression for the 8-char-prefix collision.

        Two real Gmail IDs delivered minutes apart share their first 8 chars.
        The old prefix scan returned both emails' bodies for either lookup,
        which is how one newsletter's body was published under another's
        headline. The lookup must now be exact.
        """
        (tmp_path / "1953e3be34f4d721.html").touch()
        (tmp_path / "1953e3be34f4d721.txt").touch()
        (tmp_path / "1953e3bed494d90c.html").touch()
        (tmp_path / "1953e3bed494d90c.txt").touch()

        first = [p.name for p in find_raw_files("1953e3be34f4d721", tmp_path)]
        second = [p.name for p in find_raw_files("1953e3bed494d90c", tmp_path)]

        assert first == ["1953e3be34f4d721.html", "1953e3be34f4d721.txt"]
        assert second == ["1953e3bed494d90c.html", "1953e3bed494d90c.txt"]

    def test_shared_prefix_alone_matches_nothing(self, tmp_path):
        """The common 8-char prefix is not itself a valid ID any more."""
        (tmp_path / "1953e3be34f4d721.html").touch()
        (tmp_path / "1953e3bed494d90c.html").touch()
        assert find_raw_files("1953e3be", tmp_path) == []

    def test_html_sorts_before_txt(self, tmp_path):
        (tmp_path / "aabb112233445566.txt").touch()
        (tmp_path / "aabb112233445566.html").touch()
        result = find_raw_files("aabb112233445566", tmp_path)
        assert [p.suffix for p in result] == [".html", ".txt"]

    def test_rejects_path_traversal(self, tmp_path):
        """A malformed stem must not be able to address files outside raw_dir."""
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.html").touch()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        assert find_raw_files("../outside/secret", raw_dir) == []
        assert find_raw_files("", raw_dir) == []
        assert find_raw_files("..", raw_dir) == []


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
        (md_dir / "test-email_aabb112233445566.md").write_text(textwrap.dedent("""\
            ---
            subject: "Test Email"
            labels: ["INBOX", "UNREAD", "Ryan Holiday"]
            ---
            Body of email 1.
        """))
        (raw_dir / "aabb112233445566.html").write_text("<html>email1</html>")
        (raw_dir / "aabb112233445566.txt").write_text("email1 text")

        # Email 2: multiple meaningful labels
        (md_dir / "multi-label_ccdd334455667788.md").write_text(textwrap.dedent("""\
            ---
            subject: "Multi Label"
            labels: ["INBOX", "Tech Weekly", "AI News"]
            ---
            Body of email 2.
        """))
        (raw_dir / "ccdd334455667788.html").write_text("<html>email2</html>")

        # Email 3: no meaningful labels → uncategorized
        (md_dir / "no-label_eeff556677889900.md").write_text(textwrap.dedent("""\
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

        rh_dir = newsletters_dir / "Ryan Holiday" / "aabb112233445566"
        assert rh_dir.exists()
        assert (rh_dir / "test-email_aabb112233445566.md").exists()
        assert (rh_dir / "aabb112233445566.html").exists()
        assert (rh_dir / "aabb112233445566.txt").exists()

    def test_multi_label(self, tmp_path):
        output_dir, newsletters_dir, stop_list = self._setup_fixture(tmp_path)
        organize(output_dir, newsletters_dir, stop_list)

        # Should exist in both label folders, grouped under ID subfolder
        for label in ("Tech Weekly", "AI News"):
            id_dir = newsletters_dir / label / "ccdd334455667788"
            assert id_dir.exists(), f"Missing folder: {label}/ccdd334455667788"
            assert (id_dir / "multi-label_ccdd334455667788.md").exists()
            assert (id_dir / "ccdd334455667788.html").exists()

    def test_uncategorized(self, tmp_path):
        output_dir, newsletters_dir, stop_list = self._setup_fixture(tmp_path)
        organize(output_dir, newsletters_dir, stop_list)

        uncat = newsletters_dir / "uncategorized" / "eeff556677889900"
        assert uncat.exists()
        assert (uncat / "no-label_eeff556677889900.md").exists()

    def test_idempotent_rerun(self, tmp_path):
        """Running organize twice should skip already-copied files."""
        output_dir, newsletters_dir, stop_list = self._setup_fixture(tmp_path)
        organize(output_dir, newsletters_dir, stop_list)
        # Run again — should not raise or duplicate
        organize(output_dir, newsletters_dir, stop_list)

        rh_dir = newsletters_dir / "Ryan Holiday" / "aabb112233445566"
        assert (rh_dir / "test-email_aabb112233445566.md").exists()

    def test_missing_raw_files(self, tmp_path):
        """MD file with no matching raw files should still be copied."""
        output_dir, newsletters_dir, stop_list = self._setup_fixture(tmp_path)
        organize(output_dir, newsletters_dir, stop_list)

        # Email 3 has no raw files → still in uncategorized, under ID subfolder
        uncat = newsletters_dir / "uncategorized" / "eeff556677889900"
        assert (uncat / "no-label_eeff556677889900.md").exists()

    def test_prefix_colliding_emails_split_into_separate_dirs(self, tmp_path):
        """End-to-end regression for the 8-char collision.

        Mirrors the real 'Tyler Cowen/1953e3be' case: two emails delivered
        minutes apart under the same label, whose IDs share 8 chars. Each must
        get its own directory holding only its own body — previously they shared
        one directory containing both bodies, and the site published the wrong
        one.
        """
        output_dir = tmp_path / "output"
        md_dir = output_dir / "markdown"
        raw_dir = output_dir / "raw"
        newsletters_dir = tmp_path / "newsletters"
        md_dir.mkdir(parents=True)
        raw_dir.mkdir(parents=True)
        stop_list = tmp_path / "stop.txt"
        stop_list.write_text("INBOX\n")

        for mid, slug, body in (
            ("1953e3be34f4d721", "its-happening", "first"),
            ("1953e3bed494d90c", "tuesday-assorted-links", "second"),
        ):
            (md_dir / f"{slug}_{mid}.md").write_text(textwrap.dedent(f"""\
                ---
                id: "{mid}"
                subject: "{slug}"
                labels: ["INBOX", "Tyler Cowen"]
                ---
                Body {body}.
            """))
            (raw_dir / f"{mid}.html").write_text(f"<html>{body}</html>")
            (raw_dir / f"{mid}.txt").write_text(body)

        organize(output_dir, newsletters_dir, stop_list)

        label_dir = newsletters_dir / "Tyler Cowen"
        assert sorted(d.name for d in label_dir.iterdir()) == [
            "1953e3be34f4d721",
            "1953e3bed494d90c",
        ]

        # Each directory holds exactly its own three files — no bleed.
        first = label_dir / "1953e3be34f4d721"
        assert sorted(f.name for f in first.iterdir()) == [
            "1953e3be34f4d721.html",
            "1953e3be34f4d721.txt",
            "its-happening_1953e3be34f4d721.md",
        ]
        assert (first / "1953e3be34f4d721.html").read_text() == "<html>first</html>"

        second = label_dir / "1953e3bed494d90c"
        assert sorted(f.name for f in second.iterdir()) == [
            "1953e3bed494d90c.html",
            "1953e3bed494d90c.txt",
            "tuesday-assorted-links_1953e3bed494d90c.md",
        ]
        assert (second / "1953e3bed494d90c.html").read_text() == "<html>second</html>"

    def test_each_dir_holds_exactly_one_markdown(self, tmp_path):
        """Every output directory must describe exactly one email."""
        output_dir, newsletters_dir, stop_list = self._setup_fixture(tmp_path)
        organize(output_dir, newsletters_dir, stop_list)

        for id_dir in newsletters_dir.glob("*/*"):
            if id_dir.is_dir():
                md_files = list(id_dir.glob("*.md"))
                assert len(md_files) == 1, f"{id_dir} holds {len(md_files)} .md files"

    def test_id_subfolder_structure(self, tmp_path):
        """Label folders should only contain ID subdirectories, no loose files."""
        output_dir, newsletters_dir, stop_list = self._setup_fixture(tmp_path)
        organize(output_dir, newsletters_dir, stop_list)

        rh_label_dir = newsletters_dir / "Ryan Holiday"
        assert rh_label_dir.exists()
        # Every child of the label folder should be a directory (the ID subfolder)
        for child in rh_label_dir.iterdir():
            assert child.is_dir(), f"Expected only subdirectories in label folder, found file: {child.name}"
        # The ID subfolder should contain the actual files
        id_dir = rh_label_dir / "aabb112233445566"
        assert id_dir.exists()
        assert any(id_dir.iterdir()), "ID subfolder should contain files"
