from __future__ import annotations

from pathlib import Path

import build123d

from foundation.flat_plate_with_holes import (
    build_flat_plate_with_holes,
    export_flat_plate_with_holes,
    export_flat_plate_with_holes_gltf,
)
from foundation.l_bracket import build_l_bracket, export_l_bracket
from foundation.cylinder_part import build_cylinder_part, export_cylinder_part
from foundation.flange import build_flange, export_flange
from foundation.stepped_shaft import build_stepped_shaft, export_stepped_shaft

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "foundation" / "exports"
OUT_DIR.mkdir(parents=True, exist_ok=True)


from dataclasses import dataclass

@dataclass
class ExpectedDims:
    length: float   # X, mm
    width: float    # Y, mm
    height: float   # Z, mm
    volume: float   # mm^3
    tol: float = 0.5  # absolute tolerance, mm / mm^3-relative — tune per part

# TODO: fill these in with the actual dimensions you modeled each part with.
# Volume: easiest way to get a trustworthy number is to print part.volume
# once after building, eyeball it against a hand calc, then lock it in here.
EXPECTED = {
    "flat_plate_with_holes": ExpectedDims(length=150, width=90, height=12, volume=162_000),
    "l_bracket":            ExpectedDims(length=120, width=90, height=12, volume=45_600),
    "cylinder_part":        ExpectedDims(length=60, width=60, height=80, volume=226_194.67105846514),
    "flange":               ExpectedDims(length=100, width=100, height=12, volume=94_247.7796076938),
    "stepped_shaft":        ExpectedDims(length=48, width=48, height=67, volume=81_882.47092316435),
}


def _assert_matches_expected_dims(part, part_name: str) -> None:
    expected = EXPECTED[part_name]
    bbox = part.bounding_box()

    assert abs(bbox.size.X - expected.length) < expected.tol, (
        f"{part_name}: X size {bbox.size.X:.3f} != expected {expected.length}"
    )
    assert abs(bbox.size.Y - expected.width) < expected.tol, (
        f"{part_name}: Y size {bbox.size.Y:.3f} != expected {expected.width}"
    )
    assert abs(bbox.size.Z - expected.height) < expected.tol, (
        f"{part_name}: Z size {bbox.size.Z:.3f} != expected {expected.height}"
    )

    # Volume tolerance as a % rather than absolute, since small radius/fillet
    # differences shift volume more than bounding box.
    volume_tol_pct = 0.02  # 2%
    assert abs(part.volume - expected.volume) / expected.volume < volume_tol_pct, (
        f"{part_name}: volume {part.volume:.1f} != expected {expected.volume} (±{volume_tol_pct:.0%})"
    )

def _assert_valid_step_export(export_fn, part_name: str) -> None:
    step_path = OUT_DIR / f"{part_name}.step"
    if step_path.exists():
        step_path.unlink()
    export_fn(step_path)
    assert step_path.exists(), f"STEP export missing for {part_name}"
    assert step_path.stat().st_size > 0, f"STEP file is empty for {part_name}"
    imported = build123d.import_step(str(step_path))
    assert imported is not None
    assert len(imported.solids()) > 0, f"{part_name}: STEP round-trip produced no solids"


def test_flat_plate_with_holes_exports_cleanly() -> None:
    part = build_flat_plate_with_holes()
    assert part is not None
    _assert_matches_expected_dims(part, "flat_plate_with_holes")
    _assert_valid_step_export(export_flat_plate_with_holes, "flat_plate_with_holes")


def test_flat_plate_with_holes_exports_gltf_cleanly() -> None:
    glb_path = OUT_DIR / "flat_plate_with_holes.glb"
    if glb_path.exists():
        glb_path.unlink()
    export_flat_plate_with_holes_gltf(glb_path)
    assert glb_path.exists(), "GLB export missing for flat plate with holes"
    assert glb_path.stat().st_size > 0, "GLB file is empty for flat plate with holes"


def test_l_bracket_exports_cleanly() -> None:
    part = build_l_bracket()
    assert part is not None
    _assert_matches_expected_dims(part, "l_bracket")
    _assert_valid_step_export(export_l_bracket, "l_bracket")


def test_cylinder_part_exports_cleanly() -> None:
    part = build_cylinder_part()
    assert part is not None
    _assert_matches_expected_dims(part, "cylinder_part")
    _assert_valid_step_export(export_cylinder_part, "cylinder_part")


def test_flange_exports_cleanly() -> None:
    part = build_flange()
    assert part is not None
    _assert_matches_expected_dims(part, "flange")
    _assert_valid_step_export(export_flange, "flange")


def test_stepped_shaft_exports_cleanly() -> None:
    part = build_stepped_shaft()
    assert part is not None
    _assert_matches_expected_dims(part, "stepped_shaft")
    _assert_valid_step_export(export_stepped_shaft, "stepped_shaft")
