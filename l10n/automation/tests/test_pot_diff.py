"""Tests for the l10n review-manifest diff/render logic.

Run standalone (not part of the main suite):

    python -m pytest l10n/automation/tests -q
"""

import json

import pytest

# Parsing real .pot files needs Babel; skip cleanly where it is absent rather
# than erroring during collection.
pytest.importorskip("babel")

import pot_diff  # noqa: E402
import render_comment  # noqa: E402

HEADER = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'


def write_pot(path, entries):
    """entries: list of dicts {id, plural?, ctx?}."""
    chunks = [HEADER]
    for e in entries:
        block = ""
        if e.get("ctx"):
            block += f'msgctxt "{e["ctx"]}"\n'
        block += f'msgid "{e["id"]}"\n'
        if e.get("plural"):
            block += f'msgid_plural "{e["plural"]}"\n'
            block += 'msgstr[0] ""\nmsgstr[1] ""\n'
        else:
            block += 'msgstr ""\n'
        chunks.append(block + "\n")
    path.write_text("".join(chunks), encoding="utf-8")
    return str(path)


def keys_of(entries):
    return {(e.get("msgctxt"), e["msgid"]) for e in entries}


def test_added_and_removed(tmp_path):
    base = write_pot(tmp_path / "base.pot", [{"id": "Hello"}, {"id": "Bye"}])
    head = write_pot(tmp_path / "head.pot", [{"id": "Hello"}, {"id": "New"}])

    d = pot_diff.diff_catalogs(pot_diff.load_catalog(base), pot_diff.load_catalog(head))

    assert keys_of(d["added"]) == {(None, "New")}
    assert keys_of(d["removed"]) == {(None, "Bye")}
    assert d["counts"] == {"added": 1, "removed": 1, "changed": 0,
                           "total_base": 2, "total_head": 2}
    assert d["truncated"] is False


def test_context_disambiguates(tmp_path):
    base = write_pot(tmp_path / "base.pot", [{"id": "File"}])
    head = write_pot(tmp_path / "head.pot", [{"id": "File"}, {"id": "File", "ctx": "menu"}])

    d = pot_diff.diff_catalogs(pot_diff.load_catalog(base), pot_diff.load_catalog(head))

    assert keys_of(d["added"]) == {("menu", "File")}
    assert d["counts"]["removed"] == 0


def test_plural_toggle_is_a_change(tmp_path):
    base = write_pot(tmp_path / "base.pot", [{"id": "apple"}])
    head = write_pot(tmp_path / "head.pot", [{"id": "apple", "plural": "apples"}])

    d = pot_diff.diff_catalogs(pot_diff.load_catalog(base), pot_diff.load_catalog(head))

    assert d["counts"] == {"added": 0, "removed": 0, "changed": 1,
                           "total_base": 1, "total_head": 1}
    assert d["changed"][0]["plural"] is True


def test_missing_files_are_empty(tmp_path):
    assert pot_diff.load_catalog(None) == {}
    assert pot_diff.load_catalog(str(tmp_path / "nope.pot")) == {}


def test_truncation_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(pot_diff, "MAX_ENTRIES", 2)
    base = write_pot(tmp_path / "base.pot", [])
    head = write_pot(tmp_path / "head.pot", [{"id": f"s{i}"} for i in range(5)])

    d = pot_diff.diff_catalogs(pot_diff.load_catalog(base), pot_diff.load_catalog(head))

    assert d["counts"]["added"] == 5  # exact
    assert len(d["added"]) == 2       # capped
    assert d["truncated"] is True


def test_manifest_reports_pr_impact(tmp_path):
    base = write_pot(tmp_path / "base.pot", [{"id": "Hello"}])
    head = write_pot(tmp_path / "head.pot", [{"id": "Hello"}, {"id": "New"}])

    m = pot_diff.build_manifest(
        base=base, head=head,
        repository="owner/repo", pr_number=7, head_sha="abc1234", base_ref="dev",
    )

    assert m["schema_version"] == "1.0"
    assert m["regen_ok"] is True
    assert m["source_strings"]["counts"]["added"] == 1  # "New" vs base
    # The old committed-pot / staleness concepts are gone.
    assert "staleness" not in m
    assert "pot" not in m


def test_manifest_regen_failure_is_noted(tmp_path):
    base = write_pot(tmp_path / "base.pot", [{"id": "Hello"}])
    head = write_pot(tmp_path / "head.pot", [{"id": "Hello"}, {"id": "New"}])

    m = pot_diff.build_manifest(
        base=base, head=head,
        repository="owner/repo", pr_number=9, head_sha="aaa", base_ref="dev",
        regen_ok=False,
    )

    assert m["regen_ok"] is False
    assert any("could not be fully regenerated" in n for n in m["notes"])


def test_cli_writes_manifest(tmp_path):
    base = write_pot(tmp_path / "base.pot", [{"id": "Hello"}])
    head = write_pot(tmp_path / "head.pot", [{"id": "Hello"}, {"id": "New"}])
    out = tmp_path / "manifest.json"

    rc = pot_diff.main([
        "--base", base, "--head", head,
        "--repository", "owner/repo", "--pr-number", "11",
        "--head-sha", "cafe123", "--base-ref", "dev", "--out", str(out),
    ])

    assert rc == 0
    manifest = json.loads(out.read_text())
    assert manifest["pr"]["number"] == 11
    assert manifest["repository"] == "owner/repo"
    assert manifest["source_strings"]["counts"]["added"] == 1


def base_manifest(**over):
    m = {
        "schema_version": "1.0", "stream": "messages-pot",
        "generated_at": "2026-06-20T00:00:00Z", "repository": "owner/repo",
        "pr": {"number": 1, "head_sha": "abc", "base_sha": None, "base_ref": "dev"},
        "regen_ok": True,
        "source_strings": {"added": [], "removed": [], "changed": [],
                           "counts": {"added": 0, "removed": 0, "changed": 0,
                                      "total_base": 0, "total_head": 0},
                           "truncated": False},
        "notes": [],
    }
    m.update(over)
    return m


def test_render_marker_and_no_changes():
    body = render_comment.render(base_manifest())
    assert render_comment.COMMENT_MARKER in body
    assert "no changes to the translatable source strings" in body
    # Never nags the author to update or commit the catalog.
    assert "extract_messages" not in body
    assert "out of date" not in body


def test_render_diff_block_red_green():
    m = base_manifest(source_strings={
        "added": [{"msgid": "New label", "msgctxt": "menu", "plural": False},
                  {"msgid": "New plural", "msgctxt": None, "plural": True}],
        "removed": [{"msgid": "Old label", "msgctxt": None, "plural": False}],
        "changed": [{"msgid": "Toggles", "msgctxt": None, "plural": True}],
        "counts": {"added": 2, "removed": 1, "changed": 1,
                   "total_base": 10, "total_head": 11},
        "truncated": False})
    body = render_comment.render(m)
    assert "```diff" in body
    assert "+ New label    [ctx: menu]" in body
    assert "+ New plural    [plural]" in body
    assert "- Old label" in body
    # changed shown as a -/+ pair with before/after form
    assert "- Toggles    [was singular form]" in body
    assert "+ Toggles    [now plural form]" in body


def test_render_truncation_note():
    added = [{"msgid": f"s{i}", "msgctxt": None, "plural": False} for i in range(50)]
    m = base_manifest(source_strings={
        "added": added, "removed": [], "changed": [],
        "counts": {"added": 63, "removed": 0, "changed": 0,
                   "total_base": 0, "total_head": 63},
        "truncated": True})
    body = render_comment.render(m)
    assert "...and 13 more added (count above)" in body


def test_render_fences_untrusted_msgid_safely():
    # Newlines flattened + a +/- prefix mean attacker text cannot start a line
    # and break out of the diff fence to inject markdown/HTML.
    nasty = "evil\n```\n## pwned heading\n- nope"
    m = base_manifest(source_strings={
        "added": [{"msgid": nasty, "msgctxt": None, "plural": False}],
        "removed": [], "changed": [],
        "counts": {"added": 1, "removed": 0, "changed": 0,
                   "total_base": 0, "total_head": 1},
        "truncated": False})
    body = render_comment.render(m)
    assert "+ evil\\n```\\n## pwned heading\\n- nope" in body
    assert body.count("```diff") == 1
    for line in body.splitlines():
        assert not line.startswith("## pwned")
