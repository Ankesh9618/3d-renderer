from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from build123d import Drawing, ExportSVG, Plane, Unit, import_step, section


@dataclass(frozen=True)
class RenderSet:
    front: str
    top: str
    side: str
    section: str | None = None


def _render_projection(step_path: str, output_path: str | Path, *, look_from: tuple[float, float, float], look_up: tuple[float, float, float]) -> str:
    shape = import_step(step_path)
    view = Drawing(shape, look_from=look_from, look_up=look_up, with_hidden=False)

    exporter = ExportSVG(unit=Unit.MM, margin=5, fit_to_stroke=True, line_weight=0.2)
    exporter.add_shape(view.visible_lines)
    exporter.write(str(output_path))
    return str(output_path)


def render(step_path: str, output_dir: str, section_plane: Any | None = None) -> RenderSet:
    """Render the supplied STEP file into deterministic front (along y-axis), top (along z-axis), and side (along x-axis) SVG views.

    The project has adopted first-angle projection for the seed dataset and render harness.
    """
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    front_path = target_dir / "front.svg"
    top_path = target_dir / "top.svg"
    side_path = target_dir / "side.svg"

    _render_projection(
        step_path,
        front_path,
        look_from=(0.0, -1.0, 0.0),
        look_up=(0.0, 0.0, 1.0),
    )
    _render_projection(
        step_path,
        top_path,
        look_from=(0.0, 0.0, 1.0),
        look_up=(0.0, 1.0, 0.0),
    )
    _render_projection(
        step_path,
        side_path,
        look_from=(-1.0, 0.0, 0.0),
        look_up=(0.0, 0.0, 1.0),
    )

    section_path = render_section(step_path, section_plane, output_dir) if section_plane is not None else None
    return RenderSet(front=str(front_path), top=str(top_path), side=str(side_path), section=section_path)


def _section_plane(shape: Any, plane: Any) -> Plane:
    if isinstance(plane, Plane):
        return plane
    if plane not in {"front", "top", "side"}:
        raise ValueError("plane must be a build123d Plane or 'front', 'top', or 'side'")

    center = shape.bounding_box().center()
    normals = {
        "front": (0.0, 1.0, 0.0),
        "top": (0.0, 0.0, 1.0),
        "side": (1.0, 0.0, 0.0),
    }
    return Plane(origin=center, z_dir=normals[plane])


def _section_profile_loops(svg: str) -> list[list[tuple[float, float]]]:
    root = ET.fromstring(svg)
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "line":
            continue
        segments.append(
            (
                (float(element.attrib["x1"]), float(element.attrib["y1"])),
                (float(element.attrib["x2"]), float(element.attrib["y2"])),
            )
        )

    def key(point: tuple[float, float]) -> tuple[float, float]:
        return (round(point[0], 7), round(point[1], 7))

    adjacency: dict[tuple[float, float], list[int]] = {}
    for index, (start, end) in enumerate(segments):
        adjacency.setdefault(key(start), []).append(index)
        adjacency.setdefault(key(end), []).append(index)

    loops: list[list[tuple[float, float]]] = []
    used: set[int] = set()
    for start_index, (start, end) in enumerate(segments):
        if start_index in used:
            continue
        used.add(start_index)
        points = [start, end]
        current = key(end)
        while current != key(start):
            next_index = next((candidate for candidate in adjacency.get(current, []) if candidate not in used), None)
            if next_index is None:
                break
            used.add(next_index)
            first, second = segments[next_index]
            next_point = second if key(first) == current else first
            points.append(next_point)
            current = key(next_point)
        if len(points) > 2 and current == key(start):
            loops.append(points)

    return loops


def _point_in_loop(point: tuple[float, float], loop: list[tuple[float, float]]) -> bool:
    x_value, y_value = point
    inside = False
    for index, (first, second) in enumerate(zip(loop, loop[1:])):
        x_first, y_first = first
        x_second, y_second = second
        if (y_first > y_value) != (y_second > y_value):
            crossing_x = (x_second - x_first) * (y_value - y_first) / (y_second - y_first) + x_first
            if x_value < crossing_x:
                inside = not inside
    return inside


def _point_in_profile(point: tuple[float, float], loops: list[list[tuple[float, float]]]) -> bool:
    return sum(_point_in_loop(point, loop) for loop in loops) % 2 == 1


def _clipped_hatch_segments(
    start: tuple[float, float],
    end: tuple[float, float],
    loops: list[list[tuple[float, float]]],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    delta_x = end[0] - start[0]
    delta_y = end[1] - start[1]
    parameters = [0.0, 1.0]
    for loop in loops:
        for boundary_start, boundary_end in zip(loop, loop[1:]):
            edge_x = boundary_end[0] - boundary_start[0]
            edge_y = boundary_end[1] - boundary_start[1]
            denominator = delta_x * edge_y - delta_y * edge_x
            if abs(denominator) < 1e-9:
                continue
            offset_x = boundary_start[0] - start[0]
            offset_y = boundary_start[1] - start[1]
            line_parameter = (offset_x * edge_y - offset_y * edge_x) / denominator
            edge_parameter = (offset_x * delta_y - offset_y * delta_x) / denominator
            if 0.0 < line_parameter < 1.0 and 0.0 <= edge_parameter <= 1.0:
                parameters.append(line_parameter)

    parameters = sorted(set(round(value, 10) for value in parameters))
    segments = []
    for first_parameter, second_parameter in zip(parameters, parameters[1:]):
        midpoint_parameter = (first_parameter + second_parameter) / 2
        midpoint = (start[0] + delta_x * midpoint_parameter, start[1] + delta_y * midpoint_parameter)
        if _point_in_profile(midpoint, loops):
            first_point = (start[0] + delta_x * first_parameter, start[1] + delta_y * first_parameter)
            second_point = (start[0] + delta_x * second_parameter, start[1] + delta_y * second_parameter)
            if math.dist(first_point, second_point) > 1e-7:
                segments.append((first_point, second_point))
    return segments


def render_section(step_path: str, plane: Any, output_dir: str) -> str:
    """Render a deterministic section profile with conventional diagonal hatching."""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / "section.svg"

    shape = import_step(step_path)
    cutting_plane = _section_plane(shape, plane)
    section_shape = section(shape, section_by=cutting_plane)
    view = Drawing(section_shape, look_from=tuple(cutting_plane.z_dir), look_up=(0.0, 0.0, 1.0), with_hidden=False)

    exporter = ExportSVG(unit=Unit.MM, margin=5, fit_to_stroke=True, line_weight=0.2)
    exporter.add_shape(view.visible_lines)
    exporter.write(str(output_path))

    svg = output_path.read_text(encoding="utf-8")
    root = ET.fromstring(svg)
    view_box = [float(value) for value in root.attrib["viewBox"].replace(",", " ").split()]
    min_x, min_y, width, height = view_box
    span = max(width, height) * 2
    spacing = max(width, height) / 20
    profile_loops = _section_profile_loops(svg)
    hatch_segments = []
    for x_value in [min_x - span + spacing * index for index in range(int((width + 2 * span) / spacing) + 1)]:
        start = (x_value, min_y - span)
        end = (x_value - span, min_y + height + span)
        hatch_segments.extend(_clipped_hatch_segments(start, end, profile_loops))
    hatch_lines = "".join(
        f'<path d="M {start[0]:g} {start[1]:g} L {end[0]:g} {end[1]:g}" stroke="#777" stroke-width="0.35" />'
        for start, end in hatch_segments
    )
    hatch_markup = f'<g aria-label="section hatching">{hatch_lines}</g>'
    svg = svg.replace("</svg>", f"{hatch_markup}</svg>")
    output_path.write_text(svg, encoding="utf-8")
    return str(output_path)
