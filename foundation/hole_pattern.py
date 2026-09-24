from __future__ import annotations

from pathlib import Path

from build123d import Plane, Solid, export_step

OUTPUT_DIR = Path(__file__).resolve().parent / "exports"


def build_hole_pattern() -> Solid:
    plate = Solid.make_box(length=140.0, width=100.0, height=10.0)
    for x_coord in (25.0, 70.0, 115.0):
        for y_coord in (20.0, 80.0):
            plate = plate.cut(
                Solid.make_cylinder(
                    radius=5.0,
                    height=24.0,
                    plane=Plane(origin=(x_coord, y_coord, 0.0), z_dir=(0.0, 0.0, 1.0)),
                )
            )
    return plate.clean()


def export_hole_pattern(output_path: str | Path | None = None) -> Path:
    target = Path(output_path) if output_path is not None else OUTPUT_DIR / "hole_pattern.step"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not export_step(build_hole_pattern(), str(target)):
        raise RuntimeError(f"Failed to export hole-pattern STEP to {target}")
    return target


if __name__ == "__main__":
    export_hole_pattern()
