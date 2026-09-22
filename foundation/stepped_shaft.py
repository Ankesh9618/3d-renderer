from __future__ import annotations

from pathlib import Path

from build123d import Plane, Solid, export_step

OUTPUT_DIR = Path(__file__).resolve().parent / "exports"


def build_stepped_shaft() -> Solid:
    shaft = Solid.make_cylinder(radius=12.0, height=30.0)
    step_1 = Solid.make_cylinder(
        radius=18.0,
        height=24.0,
        plane=Plane(origin=(0.0, 0.0, 15.0), z_dir=(0.0, 0.0, 1.0)),
    )
    step_2 = Solid.make_cylinder(
        radius=24.0,
        height=28.0,
        plane=Plane(origin=(0.0, 0.0, 39.0), z_dir=(0.0, 0.0, 1.0)),
    )
    shaft = shaft.fuse(step_1).fuse(step_2)
    return shaft.clean()


def export_stepped_shaft(output_path: str | Path | None = None) -> Path:
    target = Path(output_path) if output_path is not None else OUTPUT_DIR / "stepped_shaft.step"
    target.parent.mkdir(parents=True, exist_ok=True)
    part = build_stepped_shaft()
    success = export_step(part, str(target))
    if not success:
        raise RuntimeError(f"Failed to export stepped shaft STEP to {target}")
    return target


if __name__ == "__main__":
    export_stepped_shaft()
