from __future__ import annotations

from pathlib import Path

from build123d import Solid, export_step

OUTPUT_DIR = Path(__file__).resolve().parent / "exports"


def build_stepped_block() -> Solid:
    lower = Solid.make_box(length=120.0, width=70.0, height=12.0)
    upper = Solid.make_box(length=80.0, width=50.0, height=18.0).translate((20.0, 10.0, 12.0))
    top = Solid.make_box(length=40.0, width=30.0, height=15.0).translate((40.0, 20.0, 30.0))
    return lower.fuse(upper).fuse(top).clean()


def export_stepped_block(output_path: str | Path | None = None) -> Path:
    target = Path(output_path) if output_path is not None else OUTPUT_DIR / "stepped_block.step"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not export_step(build_stepped_block(), str(target)):
        raise RuntimeError(f"Failed to export stepped-block STEP to {target}")
    return target


if __name__ == "__main__":
    export_stepped_block()
