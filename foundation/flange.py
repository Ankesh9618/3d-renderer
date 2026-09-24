from __future__ import annotations

import math
from pathlib import Path

from build123d import Plane, Solid, export_step

OUTPUT_DIR = Path(__file__).resolve().parent / "exports"


def build_flange() -> Solid:
    plate = Solid.make_cylinder(radius=50.0, height=12.0)
    plate = plate.cut(
        Solid.make_cylinder(
            radius=22.0,
            height=30.0,
            plane=Plane(origin=(0.0, 0.0, 0.0), z_dir=(0.0, 0.0, 1.0)),
        )
    )

    bolt_holes: list[tuple[float, float]] = []
    for angle in (0.0, 90.0, 180.0, 270.0):
        radians_value = angle * math.pi / 180.0
        x_coord = 36.0 * math.cos(radians_value)
        y_coord = 36.0 * math.sin(radians_value)
        bolt_holes.append((x_coord, y_coord))

    for x_coord, y_coord in bolt_holes:
        plate = plate.cut(
            Solid.make_cylinder(
                radius=6.0,
                height=30.0,
                plane=Plane(origin=(x_coord, y_coord, 0.0), z_dir=(0.0, 0.0, 1.0)),
            )
        )

    return plate.clean()


def export_flange(output_path: str | Path | None = None) -> Path:
    target = Path(output_path) if output_path is not None else OUTPUT_DIR / "flange.step"
    target.parent.mkdir(parents=True, exist_ok=True)
    part = build_flange()
    success = export_step(part, str(target))
    if not success:
        raise RuntimeError(f"Failed to export flange STEP to {target}")
    return target


if __name__ == "__main__":
    export_flange()
