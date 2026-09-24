from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont
from svgpathtools import parse_path

from foundation.cylinder_part import build_cylinder_part, export_cylinder_part
from foundation.flange import build_flange, export_flange
from foundation.flat_plate_with_holes import build_flat_plate_with_holes, export_flat_plate_with_holes
from foundation.hole_pattern import build_hole_pattern, export_hole_pattern
from foundation.l_bracket import build_l_bracket, export_l_bracket
from foundation.sectioned_bushing import build_sectioned_bushing, export_sectioned_bushing
from foundation.stepped_block import build_stepped_block, export_stepped_block
from foundation.stepped_shaft import build_stepped_shaft, export_stepped_shaft
from render.harness import render

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "seed_drawings"


@dataclass(frozen=True)
class SeedSpec:
    drawing_id: str
    category: str
    description: str
    build: object
    export: object
    section: bool = False


SEEDS = (
    SeedSpec("flat_plate", "flat plate", "Rectangular plate with four through holes.", build_flat_plate_with_holes, export_flat_plate_with_holes),
    SeedSpec("l_bracket", "bracket", "Two-leg L-bracket formed from perpendicular rectangular prisms.", build_l_bracket, export_l_bracket),
    SeedSpec("cylinder", "cylinder", "Plain cylindrical solid.", build_cylinder_part, export_cylinder_part),
    SeedSpec("flange", "flange", "Circular flange with a central bore and four bolt holes.", build_flange, export_flange),
    SeedSpec("stepped_shaft", "shaft", "Three-diameter stepped cylindrical shaft.", build_stepped_shaft, export_stepped_shaft),
    SeedSpec("hole_pattern", "hole pattern", "Rectangular plate with a six-hole regular pattern.", build_hole_pattern, export_hole_pattern),
    SeedSpec("stepped_block", "stepped part", "Three-level rectangular stepped block.", build_stepped_block, export_stepped_block),
    SeedSpec("sectioned_bushing", "sectioned part", "Bushing with a stepped internal cavity shown in section.", build_sectioned_bushing, export_sectioned_bushing, True),
)


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _svg_png(svg_path: str, width: int, height: int) -> Image.Image:
    root = ET.parse(svg_path).getroot()
    view_box = [float(value) for value in re.split(r"[ ,]+", root.attrib.get("viewBox", "0 0 100 100"))]
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    scale = min(width / view_box[2], height / view_box[3])
    offset_x = (width - view_box[2] * scale) / 2
    offset_y = (height - view_box[3] * scale) / 2
    content_height = view_box[3] * scale

    def point(x_value: float, y_value: float) -> tuple[float, float]:
        return (
            offset_x + (x_value - view_box[0]) * scale,
            offset_y + content_height - (y_value - view_box[1]) * scale,
        )

    def draw_path(path_data: str) -> None:
        path = parse_path(path_data)
        for segment in path:
            samples = [point(value.real, value.imag) for value in (segment.point(index / 24) for index in range(25))]
            if len(samples) > 1:
                draw.line(samples, fill=(25, 25, 25), width=2)

    for element in root.iter():
        if element.tag.endswith("path"):
            draw_path(element.attrib.get("d", ""))
            continue
        elif element.tag.endswith("line"):
            points = [
                point(float(element.attrib["x1"]), float(element.attrib["y1"])),
                point(float(element.attrib["x2"]), float(element.attrib["y2"])),
            ]
        elif element.tag.endswith("circle") or element.tag.endswith("ellipse"):
            center = point(float(element.attrib["cx"]), float(element.attrib["cy"]))
            radius_x = float(element.attrib.get("r", element.attrib.get("rx", "0"))) * scale
            radius_y = float(element.attrib.get("r", element.attrib.get("ry", "0"))) * scale
            if "ry" in element.attrib:
                radius_y = float(element.attrib["ry"]) * scale
            draw.ellipse(
                (center[0] - radius_x, center[1] - radius_y, center[0] + radius_x, center[1] + radius_y),
                outline=(25, 25, 25),
                width=2,
            )
            continue
        else:
            continue
        if len(points) > 1:
            draw.line(points, fill=(25, 25, 25), width=2)
    return image


def _dimension(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], label: str, horizontal: bool) -> None:
    draw.line((start, end), fill=(40, 40, 40), width=2)
    if horizontal:
        draw.line((start[0], start[1] - 7, start[0], start[1] + 7), fill=(40, 40, 40), width=2)
        draw.line((end[0], end[1] - 7, end[0], end[1] + 7), fill=(40, 40, 40), width=2)
        text_position = ((start[0] + end[0]) // 2 - 25, start[1] - 28)
    else:
        draw.line((start[0] - 7, start[1], start[0] + 7, start[1]), fill=(40, 40, 40), width=2)
        draw.line((end[0] - 7, end[1], end[0] + 7, end[1]), fill=(40, 40, 40), width=2)
        text_position = (start[0] + 10, (start[1] + end[1]) // 2 - 10)
    draw.text(text_position, label, fill=(20, 20, 20), font=_font(20))


def generate_seed(spec: SeedSpec) -> Path:
    output_dir = DATA_ROOT / spec.drawing_id
    output_dir.mkdir(parents=True, exist_ok=True)
    step_path = output_dir / "ground_truth.step"
    spec.export(step_path)

    render_dir = output_dir / "views"
    views = render(str(step_path), str(render_dir), section_plane="front" if spec.section else None)
    section_path = views.section

    part = spec.build()
    size = part.bounding_box().size
    canvas = Image.new("RGB", (1500, 1120), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((55, 35), spec.drawing_id.replace("_", " ").upper(), fill=(10, 10, 10), font=_font(34))
    draw.text((55, 80), spec.description, fill=(40, 40, 40), font=_font(22))

    placements = [
        (views.front, (60, 150), "FRONT"),
        (views.top, (760, 150), "TOP"),
        (views.side, (60, 610), "SIDE"),
    ]
    if section_path is not None:
        placements.append((section_path, (760, 610), "SECTION (FRONT)"))

    for svg_path, position, label in placements:
        image = _svg_png(svg_path, 600, 360)
        canvas.paste(image, position)
        draw.text((position[0], position[1] + 365), label, fill=(20, 20, 20), font=_font(22))

    _dimension(draw, (60, 1060), (660, 1060), f"L {size.X:.1f} mm", True)
    _dimension(draw, (1320, 1060), (1320, 900), f"H {size.Z:.1f} mm", False)
    _dimension(draw, (780, 560), (1380, 560), f"W {size.Y:.1f} mm", True)
    canvas.save(output_dir / "drawing.png")
    return output_dir


def write_dataset_readme() -> None:
    lines = ["# Seed Drawings", "", "Synthetic dimensioned drawing sheets generated from hand-modeled build123d parts.", ""]
    lines.append("| drawing_id | category | description |")
    lines.append("|---|---|---|")
    for spec in SEEDS:
        lines.append(f"| `{spec.drawing_id}` | {spec.category} | {spec.description} |")
    lines.append("")
    (DATA_ROOT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    for spec in SEEDS:
        generate_seed(spec)
    write_dataset_readme()


if __name__ == "__main__":
    main()
