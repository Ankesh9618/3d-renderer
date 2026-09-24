from __future__ import annotations

from pathlib import Path

from build123d import Plane, Solid, export_gltf, export_step

OUTPUT_DIR = Path(__file__).resolve().parent / "exports"


def build_flat_plate_with_holes() -> Solid:
    plate = Solid.make_box(length=150.0, width=90.0, height=12.0)
    hole_positions = [
        (30.0, 25.0),
        (120.0, 25.0),
        (30.0, 65.0),
        (120.0, 65.0),
    ]

    for x_coord, y_coord in hole_positions:
        plate = plate.cut(
            Solid.make_cylinder(
                radius=6.0,
                height=30.0,
                plane=Plane(origin=(x_coord, y_coord, 0.0), z_dir=(0.0, 0.0, 1.0)),
            )
        )

    return plate.clean()


def export_flat_plate_with_holes(output_path: str | Path | None = None) -> Path:
    target = Path(output_path) if output_path is not None else OUTPUT_DIR / "flat_plate_with_holes.step"
    target.parent.mkdir(parents=True, exist_ok=True)
    part = build_flat_plate_with_holes()
    success = export_step(part, str(target))
    if not success:
        raise RuntimeError(f"Failed to export flat plate with holes STEP to {target}")
    return target


def export_flat_plate_with_holes_gltf(output_path: str | Path | None = None) -> Path:
    target = Path(output_path) if output_path is not None else OUTPUT_DIR / "flat_plate_with_holes.glb"
    target.parent.mkdir(parents=True, exist_ok=True)
    part = build_flat_plate_with_holes()
    success = export_gltf(part, str(target))
    if not success:
        raise RuntimeError(f"Failed to export flat plate with holes GLB to {target}")
    return target


if __name__ == "__main__":
    export_flat_plate_with_holes()
    export_flat_plate_with_holes_gltf()
