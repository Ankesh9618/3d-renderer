from __future__ import annotations

from pathlib import Path

from build123d import Solid, export_step

OUTPUT_DIR = Path(__file__).resolve().parent / "exports"


def build_cylinder_part() -> Solid:
    cylinder = Solid.make_cylinder(radius=30.0, height=80.0)
    return cylinder.clean()


def export_cylinder_part(output_path: str | Path | None = None) -> Path:
    target = Path(output_path) if output_path is not None else OUTPUT_DIR / "cylinder_part.step"
    target.parent.mkdir(parents=True, exist_ok=True)
    part = build_cylinder_part()
    success = export_step(part, str(target))
    if not success:
        raise RuntimeError(f"Failed to export cylinder STEP to {target}")
    return target


if __name__ == "__main__":
    export_cylinder_part()
