from __future__ import annotations

from pathlib import Path

import build123d

from tools.generate_seed_drawing import DATA_ROOT, SEEDS, _svg_png, generate_seed


def test_seed_dataset_has_eight_distinct_categories() -> None:
    assert len(SEEDS) >= 8
    assert len({seed.category for seed in SEEDS}) >= 8
    assert any(seed.section for seed in SEEDS)


def test_svg_png_preserves_circle_aspect_ratio(tmp_path: Path) -> None:
    svg_path = tmp_path / "circle.svg"
    svg_path.write_text(
        '<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="20" /></svg>',
        encoding="utf-8",
    )

    image = _svg_png(str(svg_path), 600, 360)
    dark_pixels = [
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if image.getpixel((x, y)) != (255, 255, 255)
    ]
    x_values = [x for x, _ in dark_pixels]
    y_values = [y for _, y in dark_pixels]
    assert max(x_values) - min(x_values) == max(y_values) - min(y_values)


def test_generator_produces_drawing_and_solid_ground_truth_for_each_seed(tmp_path: Path) -> None:
    for seed in SEEDS:
        output_dir = tmp_path / seed.drawing_id
        original_root = DATA_ROOT
        try:
            import tools.generate_seed_drawing as generator

            generator.DATA_ROOT = tmp_path
            generate_seed(seed)
        finally:
            generator.DATA_ROOT = original_root

        drawing_path = output_dir / "drawing.png"
        step_path = output_dir / "ground_truth.step"
        assert drawing_path.exists() and drawing_path.stat().st_size > 0
        assert step_path.exists() and step_path.stat().st_size > 0
        imported = build123d.import_step(str(step_path))
        assert len(imported.solids()) > 0