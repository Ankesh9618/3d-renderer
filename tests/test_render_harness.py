from __future__ import annotations

import shutil
from pathlib import Path

from render.harness import RenderSet, render
from render.harness import render_section

ROOT = Path(__file__).resolve().parent.parent
SEED_STEPS = sorted((ROOT / "foundation" / "exports").glob("*.step"))
OUTPUT_ROOT = ROOT / "render" / "outputs"
SEED_ROOT = ROOT / "data" / "seed_drawings"


def test_render_section_generates_deterministic_hatched_view(tmp_path):
    step_path = SEED_STEPS[0]
    first = render_section(str(step_path), plane="front", output_dir=str(tmp_path / "first"))
    second = render_section(str(step_path), plane="front", output_dir=str(tmp_path / "second"))
    assert Path(first).exists()
    assert Path(first).stat().st_size > 0
    assert Path(first).read_bytes() == Path(second).read_bytes()
    assert "section hatching" in Path(first).read_text(encoding="utf-8")
    assert "clipPath" not in Path(first).read_text(encoding="utf-8")
    assert "clip-path" not in Path(first).read_text(encoding="utf-8")

    render_set = render(str(step_path), str(tmp_path / "render-set"), section_plane="front")
    assert render_set.section is not None
    assert Path(render_set.section).exists()


def test_render_harness_generates_three_deteministic_views_for_each_seed_step() -> None:
    assert len(SEED_STEPS) >= 5

    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    for step_path in SEED_STEPS:
        output_dir = OUTPUT_ROOT / step_path.stem
        result = render(str(step_path), str(output_dir))

        assert isinstance(result, RenderSet)
        assert Path(result.front).exists()
        assert Path(result.top).exists()
        assert Path(result.side).exists()
        assert Path(result.front).suffix.lower() in {".svg", ".png"}
        assert Path(result.top).suffix.lower() in {".svg", ".png"}
        assert Path(result.side).suffix.lower() in {".svg", ".png"}

        first_pass = render(str(step_path), str(output_dir / "repeat"))
        assert Path(first_pass.front).read_bytes() == Path(result.front).read_bytes()
        assert Path(first_pass.top).read_bytes() == Path(result.top).read_bytes()
        assert Path(first_pass.side).read_bytes() == Path(result.side).read_bytes()


def test_top_views_preserve_internal_hole_edges() -> None:
    expected_circle_counts = {
        "flat_plate": 4,
        "hole_pattern": 6,
        "flange": 6,
    }
    for drawing_id, circle_count in expected_circle_counts.items():
        top_view = SEED_ROOT / drawing_id / "views" / "top.svg"
        svg = top_view.read_text(encoding="utf-8")
        assert svg.count("<circle ") == circle_count
