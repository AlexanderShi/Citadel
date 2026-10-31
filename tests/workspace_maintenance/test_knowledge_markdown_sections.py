"""A Markdown heading marker over nothing but spacing names no section.

A canonical filing can carry a heading line whose only text is a
non-breaking space (PAYX's 8-K 0000723531-26-000008 has ``## \\xa0``). Read
as a heading, its stripped text is empty, the empty name enters every later
section's heading path, and the citation contract refuses it, so the whole
issuer unit's retrieval generation failed. The line stays a body line; a
document without such a line is sectioned exactly as before.
"""

from __future__ import annotations

from uuid import uuid4

from alphalattice.kernel.knowledge.retrieval import _markdown_sections
from alphalattice.kernel.knowledge.retrieval_contracts import KnowledgeCitation


def _citation(heading_path: tuple[str, ...]) -> KnowledgeCitation:
    return KnowledgeCitation(
        document_id="ae.test.blank-heading",
        revision=1,
        snapshot_id=uuid4(),
        snapshot_logical_hash="0" * 64,
        content_sha256="0" * 64,
        heading_path=heading_path,
        start_line=1,
        end_line=1,
        character_start=0,
        character_end=1,
        utf8_byte_start=0,
        utf8_byte_end=1,
        chunk_id="0" * 64,
        chunk_hash="0" * 64,
    )


def test_a_heading_marker_over_a_non_breaking_space_stays_a_body_line() -> None:
    text = "# FORM 8-K\n\nCover text.\n\n## \xa0\n\nItem 2.02 results.\n"
    sections = _markdown_sections(text, "PAYX 8-K")
    assert [section.heading_path for section in sections] == [("FORM 8-K",)]
    assert "Item 2.02 results." in sections[0].body
    for section in sections:
        _citation(section.heading_path)


def test_a_blank_heading_does_not_end_the_section_it_sits_in() -> None:
    text = "# A\n\n## B\n\nfirst\n\n###   \n\nsecond\n\n## C\n\nthird\n"
    sections = _markdown_sections(text, "doc")
    assert [section.heading_path for section in sections] == [
        ("A",),
        ("A", "B"),
        ("A", "C"),
    ]
    assert "second" in sections[1].body


def test_a_document_without_a_blank_heading_is_sectioned_as_before() -> None:
    text = "# A\n\nalpha\n\n## B\n\nbeta\n\n# C\n\ngamma\n"
    sections = _markdown_sections(text, "doc")
    assert [(s.heading_path, s.heading, s.body, s.start_line, s.end_line) for s in sections] == [
        (("A",), "A", "alpha", 1, 4),
        (("A", "B"), "B", "beta", 5, 8),
        (("C",), "C", "gamma", 9, 11),
    ]
