from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from render.harness import RenderSet, render
from render.harness import render_section

ROOT = Path(__file__).resolve().parent.parent
SEED_STEPS = sorted((ROOT / "foundation" / "exports").glob("*.step"))
OUTPUT_ROOT = ROOT / "render" / "outputs"


def test_render_section_raises_not_implemented(tmp_path):
    step_path = SEED_STEPS[0]
    with pytest.raises(NotImplementedError):
        render_section(str(step_path), plane=None, output_dir=str(tmp_path))


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
