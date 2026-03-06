"""Tests for brain-region kernel decomposition (Task 025, Subtask 05).

Verifies that the 6 brain region files compile into a complete, valid iEVO.md.
"""

from __future__ import annotations

from pathlib import Path

from cortex.compile import CORTEX_ROOT, build, render_ievo_md

KERNEL_DIR = CORTEX_ROOT / "templates" / "kernel"

BRAIN_REGIONS = [
    "brainstem.md",
    "instincts.md",
    "limbic.md",
    "neocortex.md",
    "prefrontal.md",
    "sessions.md",
]

REGION_HEADINGS = [
    "## Brainstem",
    "## Instincts",
    "## Limbic System",
    "## Neocortex",
    "## Prefrontal Cortex",
    "## Working Memory",
]


def test_brain_region_files_exist() -> None:
    """All 6 brain region .md files and consciousness.md.j2 exist in templates/kernel/."""
    for region in BRAIN_REGIONS:
        path = KERNEL_DIR / region
        assert path.exists(), f"Missing brain region file: {path}"

    template = KERNEL_DIR / "consciousness.md.j2"
    assert template.exists(), f"Missing master template: {template}"


def test_consciousness_template_includes_all_regions() -> None:
    """consciousness.md.j2 contains {% include %} for each brain region."""
    template = (KERNEL_DIR / "consciousness.md.j2").read_text()
    for region in BRAIN_REGIONS:
        assert f"kernel/{region}" in template, (
            f"consciousness.md.j2 missing include for {region}"
        )


def test_all_brain_regions_present_in_output(tmp_path: Path) -> None:
    """Compiled iEVO.md contains H2 headings for all 6 brain regions."""
    render_ievo_md(tmp_path, "v1.0.0")
    content = (tmp_path / "iEVO.md").read_text()

    for heading in REGION_HEADINGS:
        assert heading in content, f"Missing region heading: {heading}"


def test_no_unrendered_jinja_in_output(tmp_path: Path) -> None:
    """Compiled iEVO.md contains no Jinja2 syntax."""
    render_ievo_md(tmp_path, "v1.0.0")
    content = (tmp_path / "iEVO.md").read_text()

    assert "{%" not in content, "Unrendered {% in iEVO.md"
    assert "{{" not in content, "Unrendered {{ in iEVO.md"


def test_key_content_preserved(tmp_path: Path) -> None:
    """Spot-check that key content from each region survived compilation."""
    render_ievo_md(tmp_path, "v1.0.0")
    content = (tmp_path / "iEVO.md").read_text()

    checks = [
        ("brainstem", ".ievo/"),
        ("brainstem", "_index.csv"),
        ("instincts", "challenge first"),
        ("instincts", "curious mind"),
        ("limbic", "15-minute rule"),
        ("neocortex", "ACID"),
        ("prefrontal", "evolution"),
        ("sessions", "session"),
    ]
    for region, keyword in checks:
        assert keyword.lower() in content.lower(), (
            f"Key content from {region} missing: {keyword!r}"
        )


def test_compile_produces_valid_ievo_md(tmp_path: Path) -> None:
    """Full compile produces a non-empty iEVO.md and tarball."""
    tarball = build(tag="v1.0.0", dist_dir=tmp_path)

    ievo_md = tmp_path / "iEVO.md"
    assert ievo_md.exists(), "iEVO.md not created"
    assert ievo_md.stat().st_size > 1000, (
        f"iEVO.md suspiciously small: {ievo_md.stat().st_size} bytes"
    )
    assert tarball.exists(), f"Tarball not created: {tarball}"
