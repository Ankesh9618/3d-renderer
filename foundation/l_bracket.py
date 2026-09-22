from __future__ import annotations

from pathlib import Path

from build123d import Solid, export_step

OUTPUT_DIR = Path(__file__).resolve().parent / "exports"


def build_l_bracket() -> Solid:
    base = Solid.make_box(length=120.0, width=20.0, height=12.0)
    flange = Solid.make_box(length=20.0, width=80.0, height=12.0)
    part = base.fuse(flange.translate((0.0, 10.0, 0.0)))
    return part.clean()


def export_l_bracket(output_path: str | Path | None = None) -> Path:
    target = Path(output_path) if output_path is not None else OUTPUT_DIR / "l_bracket.step"
    target.parent.mkdir(parents=True, exist_ok=True)
    part = build_l_bracket()
    success = export_step(part, str(target))
    if not success:
        raise RuntimeError(f"Failed to export L-bracket STEP to {target}")
    return target


if __name__ == "__main__":
    export_l_bracket()
