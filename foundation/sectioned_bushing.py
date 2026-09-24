from __future__ import annotations

from pathlib import Path

from build123d import Plane, Solid, export_step

OUTPUT_DIR = Path(__file__).resolve().parent / "exports"


def build_sectioned_bushing() -> Solid:
    outer = Solid.make_cylinder(radius=35.0, height=60.0)
    lower_bore = Solid.make_cylinder(radius=12.0, height=22.0)
    upper_bore = Solid.make_cylinder(
        radius=22.0,
        height=42.0,
        plane=Plane(origin=(0.0, 0.0, 22.0), z_dir=(0.0, 0.0, 1.0)),
    )
    return outer.cut(lower_bore.fuse(upper_bore)).clean()


def export_sectioned_bushing(output_path: str | Path | None = None) -> Path:
    target = Path(output_path) if output_path is not None else OUTPUT_DIR / "sectioned_bushing.step"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not export_step(build_sectioned_bushing(), str(target)):
        raise RuntimeError(f"Failed to export sectioned-bushing STEP to {target}")
    return target


if __name__ == "__main__":
    export_sectioned_bushing()
