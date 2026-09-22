from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from build123d import Drawing, ExportSVG, Unit, import_step


@dataclass(frozen=True)
class RenderSet:
    front: str
    top: str
    side: str
    section: str | None = None


def _render_projection(step_path: str, output_path: str | Path, *, look_from: tuple[float, float, float], look_up: tuple[float, float, float]) -> str:
    shape = import_step(step_path)
    view = Drawing(shape, look_from=look_from, look_up=look_up, with_hidden=False)

    exporter = ExportSVG(unit=Unit.MM, margin=5, fit_to_stroke=True, line_weight=0.2)
    exporter.add_shape(view.visible_lines)
    exporter.write(str(output_path))
    return str(output_path)


def render(step_path: str, output_dir: str) -> RenderSet:
    """Render the supplied STEP file into deterministic front (along y-axis), top (along z-axis), and side (along x-axis) SVG views.

    The project has adopted first-angle projection for the seed dataset and render harness.
    """
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    front_path = target_dir / "front.svg"
    top_path = target_dir / "top.svg"
    side_path = target_dir / "side.svg"

    _render_projection(
        step_path,
        front_path,
        look_from=(0.0, -1.0, 0.0),
        look_up=(0.0, 0.0, 1.0),
    )
    _render_projection(
        step_path,
        top_path,
        look_from=(0.0, 0.0, 1.0),
        look_up=(0.0, 1.0, 0.0),
    )
    _render_projection(
        step_path,
        side_path,
        look_from=(-1.0, 0.0, 0.0),
        look_up=(0.0, 0.0, 1.0),
    )

    return RenderSet(front=str(front_path), top=str(top_path), side=str(side_path), section=None)


def render_section(step_path: str, plane: Any, output_dir: str) -> str:
    """Reserved interface for later section-view support. V1 intentionally does not implement it."""
    raise NotImplementedError("Section-view rendering is intentionally out of scope for V1.")
