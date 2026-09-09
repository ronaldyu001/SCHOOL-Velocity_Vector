#!/usr/bin/env python3
"""
deepracer_track_converter_v4.py

DeepRacer track utility with room-aware fitting and print-shop production mode.

Features
--------
- Inspect DeepRacer .npy geometry
- Export true-scale full SVG
- Optional PNG preview
- Optional overlapping panel SVGs
- Production panel annotations:
    * panel number
    * trim/cut guide
    * overlap-zone tint
    * previous/next overlap labels
    * registration crosshairs
    * 1-meter calibration ruler
    * panel dimensions
    * assembly manifest

Expected .npy columns:
    0 center_x, 1 center_y,
    2 inner_x,  3 inner_y,
    4 outer_x,  5 outer_y

Coordinates are assumed to be meters.

Dependencies:
    numpy
Optional:
    matplotlib  (for --preview)

Example:
    python deepracer_track_converter_v4.py track.npy \
        -o track.svg \
        --preview track_preview.png \
        --panel-width 1.2192 \
        --panel-overlap 0.05 \
        --panel-axis auto \
        --production-mode
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Tuple, List

import numpy as np


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def load_track(path: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    try:
        track = np.load(path)
    except Exception as exc:
        raise RuntimeError(f"Could not load '{path}': {exc}") from exc

    if track.ndim != 2 or track.shape[1] < 6:
        raise ValueError(
            f"Expected a 2-D array with at least 6 columns; got shape {track.shape}"
        )

    track = np.asarray(track[:, :6], dtype=float)

    if len(track) < 3:
        raise ValueError("Track must contain at least 3 waypoints.")
    if not np.isfinite(track).all():
        raise ValueError("Track contains NaN or infinite values.")

    center = track[:, 0:2]
    inner = track[:, 2:4]
    outer = track[:, 4:6]
    return track, center, inner, outer


def closed_curve_length(points: np.ndarray) -> float:
    segments = np.roll(points, -1, axis=0) - points
    return float(np.linalg.norm(segments, axis=1).sum())


def inspect_geometry(center, inner, outer) -> Dict[str, float]:
    widths = np.linalg.norm(inner - outer, axis=1)
    all_points = np.vstack([inner, outer])
    xmin, ymin = all_points.min(axis=0)
    xmax, ymax = all_points.max(axis=0)
    midpoint = (inner + outer) / 2.0
    midpoint_error = np.linalg.norm(center - midpoint, axis=1)

    return {
        "waypoints": int(len(center)),
        "mean_track_width_m": float(widths.mean()),
        "min_track_width_m": float(widths.min()),
        "max_track_width_m": float(widths.max()),
        "centerline_length_m": closed_curve_length(center),
        "footprint_width_m": float(xmax - xmin),
        "footprint_height_m": float(ymax - ymin),
        "mean_midpoint_error_m": float(midpoint_error.mean()),
        "max_midpoint_error_m": float(midpoint_error.max()),
    }


def print_report(path, stats):
    M_TO_FT = 3.280839895
    M_TO_IN = 39.37007874
    print(f"\nTrack: {path.name}")
    print("-" * 72)
    print(f"Waypoints                  : {stats['waypoints']}")
    print(
        f"Mean track width           : {stats['mean_track_width_m']:.3f} m "
        f"({stats['mean_track_width_m'] * M_TO_IN:.1f} in)"
    )
    print(
        f"Track width range          : {stats['min_track_width_m']:.3f} - "
        f"{stats['max_track_width_m']:.3f} m"
    )
    print(
        f"Centerline length          : {stats['centerline_length_m']:.3f} m "
        f"({stats['centerline_length_m'] * M_TO_FT:.1f} ft)"
    )
    print(
        f"Geometry footprint         : {stats['footprint_width_m']:.3f} m x "
        f"{stats['footprint_height_m']:.3f} m"
    )
    print(
        f"Geometry footprint         : {stats['footprint_width_m'] * M_TO_FT:.1f} ft x "
        f"{stats['footprint_height_m'] * M_TO_FT:.1f} ft"
    )
    print(
        f"Mean center midpoint error : {stats['mean_midpoint_error_m']:.6f} m"
    )
    print(
        f"Max center midpoint error  : {stats['max_midpoint_error_m']:.6f} m"
    )


# ---------------------------------------------------------------------------
# Scaling and room fitting
# ---------------------------------------------------------------------------

UNIT_TO_M = {"m": 1.0, "ft": 0.3048, "in": 0.0254}


def to_meters(value: float, units: str) -> float:
    return float(value) * UNIT_TO_M[units]


def geometry_extent(inner: np.ndarray, outer: np.ndarray) -> Tuple[float, float]:
    all_points = np.vstack([inner, outer])
    xmin, ymin = all_points.min(axis=0)
    xmax, ymax = all_points.max(axis=0)
    return float(xmax - xmin), float(ymax - ymin)


def rotate_90(points: np.ndarray) -> np.ndarray:
    out = np.empty_like(points, dtype=float)
    out[:, 0] = -points[:, 1]
    out[:, 1] = points[:, 0]
    return out


def transform_track(center, inner, outer, scale: float, rotate: bool):
    c = np.asarray(center, dtype=float) * scale
    i = np.asarray(inner, dtype=float) * scale
    o = np.asarray(outer, dtype=float) * scale
    if rotate:
        c, i, o = rotate_90(c), rotate_90(i), rotate_90(o)
    return c, i, o


def calculate_room_fit(inner, outer, margin_m, room_width_m, room_height_m, clearance_m, allow_rotate):
    if room_width_m <= 0 or room_height_m <= 0:
        raise ValueError('Room width and height must be > 0.')
    if clearance_m < 0:
        raise ValueError('Room clearance must be >= 0.')

    usable_w = room_width_m - 2.0 * clearance_m
    usable_h = room_height_m - 2.0 * clearance_m
    if usable_w <= 0 or usable_h <= 0:
        raise ValueError('Room clearance leaves no usable floor area.')

    geom_w, geom_h = geometry_extent(inner, outer)
    source_w = geom_w + 2.0 * margin_m
    source_h = geom_h + 2.0 * margin_m

    scale_normal = min(usable_w / source_w, usable_h / source_h)
    scale_rotated = min(usable_w / source_h, usable_h / source_w)

    rotate = False
    scale = scale_normal
    if allow_rotate and scale_rotated > scale_normal:
        rotate = True
        scale = scale_rotated

    if rotate:
        fitted_w, fitted_h = source_h * scale, source_w * scale
    else:
        fitted_w, fitted_h = source_w * scale, source_h * scale

    return {
        'scale': float(scale), 'rotate': bool(rotate),
        'room_width_m': float(room_width_m), 'room_height_m': float(room_height_m),
        'clearance_m': float(clearance_m),
        'usable_width_m': float(usable_w), 'usable_height_m': float(usable_h),
        'source_artwork_width_m': float(source_w), 'source_artwork_height_m': float(source_h),
        'fitted_artwork_width_m': float(fitted_w), 'fitted_artwork_height_m': float(fitted_h),
    }


def print_room_fit_report(fit, original_mean_width_m, minimum_width_m):
    M_TO_FT = 3.280839895
    M_TO_IN = 39.37007874
    scaled_lane = original_mean_width_m * fit['scale']
    print('\nRoom-fit analysis')
    print('-' * 72)
    print(f"Room size                  : {fit['room_width_m']:.3f} m x {fit['room_height_m']:.3f} m ({fit['room_width_m']*M_TO_FT:.2f} ft x {fit['room_height_m']*M_TO_FT:.2f} ft)")
    print(f"Requested clearance        : {fit['clearance_m']:.3f} m ({fit['clearance_m']*M_TO_FT:.2f} ft each side)")
    print(f"Usable floor after clearance: {fit['usable_width_m']:.3f} m x {fit['usable_height_m']:.3f} m")
    print(f"Source artwork size        : {fit['source_artwork_width_m']:.3f} m x {fit['source_artwork_height_m']:.3f} m")
    print(f"Rotate 90 degrees          : {'YES' if fit['rotate'] else 'NO'}")
    print(f"Uniform scale factor       : {fit['scale']:.4f} ({fit['scale']*100:.1f}%)")
    print(f"Fitted artwork size        : {fit['fitted_artwork_width_m']:.3f} m x {fit['fitted_artwork_height_m']:.3f} m")
    print(f"Scaled mean lane width     : {scaled_lane:.3f} m ({scaled_lane*M_TO_IN:.1f} in)")
    print(f"Minimum requested lane     : {minimum_width_m:.3f} m ({minimum_width_m*M_TO_IN:.1f} in)")


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def points_string(points: np.ndarray) -> str:
    return " ".join(f"{x:.6f},{y:.6f}" for x, y in points)


def close_curve(points: np.ndarray) -> np.ndarray:
    if np.allclose(points[0], points[-1]):
        return points
    return np.vstack([points, points[0]])


def transform_to_svg(points: np.ndarray, xmin: float, ymax: float) -> np.ndarray:
    out = np.empty_like(points, dtype=float)
    out[:, 0] = points[:, 0] - xmin
    out[:, 1] = ymax - points[:, 1]
    return out


def make_checker_start_line(p1, p2, stripe_width_m, cells=10) -> str:
    pieces = []
    vector = p2 - p1
    for i in range(cells):
        a = p1 + vector * (i / cells)
        b = p1 + vector * ((i + 1) / cells)
        color = "#FFFFFF" if i % 2 == 0 else "#111111"
        pieces.append(
            f'<line x1="{a[0]:.6f}" y1="{a[1]:.6f}" '
            f'x2="{b[0]:.6f}" y2="{b[1]:.6f}" '
            f'stroke="{color}" stroke-width="{stripe_width_m:.6f}" '
            f'stroke-linecap="butt" />'
        )
    return "\n    ".join(pieces)


def build_track_svg_body(
    center_svg, inner_svg, outer_svg, *,
    road_color, field_color, boundary_color, center_color,
    boundary_width_m, center_width_m, dash_m, gap_m,
    draw_centerline, draw_start_line, checker_start_line,
    start_svg, start_line_width_m, page_width_m, page_height_m
) -> str:

    center_closed = close_curve(center_svg)
    inner_closed = close_curve(inner_svg)
    outer_closed = close_curve(outer_svg)
    road_polygon = np.vstack([inner_svg, outer_svg[::-1]])

    centerline_svg = ""
    if draw_centerline:
        centerline_svg = f"""
    <polyline
        points="{points_string(center_closed)}"
        fill="none"
        stroke="{xml_escape(center_color)}"
        stroke-width="{center_width_m:.6f}"
        stroke-dasharray="{dash_m:.6f},{gap_m:.6f}"
        stroke-linecap="butt"
        stroke-linejoin="round"
    />"""

    startline_svg = ""
    if draw_start_line:
        if checker_start_line:
            startline_svg = f"""
    {make_checker_start_line(start_svg[0], start_svg[1], start_line_width_m)}"""
        else:
            startline_svg = f"""
    <line
        x1="{start_svg[0,0]:.6f}"
        y1="{start_svg[0,1]:.6f}"
        x2="{start_svg[1,0]:.6f}"
        y2="{start_svg[1,1]:.6f}"
        stroke="#FFFFFF"
        stroke-width="{start_line_width_m:.6f}"
        stroke-linecap="butt"
    />"""

    return f"""
    <rect x="0" y="0"
          width="{page_width_m:.6f}"
          height="{page_height_m:.6f}"
          fill="{xml_escape(field_color)}" />

    <polygon
        points="{points_string(road_polygon)}"
        fill="{xml_escape(road_color)}"
        stroke="none"
    />

    <polyline
        points="{points_string(inner_closed)}"
        fill="none"
        stroke="{xml_escape(boundary_color)}"
        stroke-width="{boundary_width_m:.6f}"
        stroke-linejoin="round"
    />

    <polyline
        points="{points_string(outer_closed)}"
        fill="none"
        stroke="{xml_escape(boundary_color)}"
        stroke-width="{boundary_width_m:.6f}"
        stroke-linejoin="round"
    />
{centerline_svg}
{startline_svg}
"""


def write_full_svg(
    output_path, center, inner, outer, *,
    title, margin_m, road_color, field_color, boundary_color, center_color,
    boundary_width_m, center_width_m, dash_m, gap_m,
    draw_centerline, draw_start_line, checker_start_line,
    start_index, start_line_width_m
):
    all_points = np.vstack([inner, outer])
    x_min_raw, y_min_raw = all_points.min(axis=0)
    x_max_raw, y_max_raw = all_points.max(axis=0)

    xmin = float(x_min_raw - margin_m)
    xmax = float(x_max_raw + margin_m)
    ymin = float(y_min_raw - margin_m)
    ymax = float(y_max_raw + margin_m)

    width_m = xmax - xmin
    height_m = ymax - ymin

    center_svg = transform_to_svg(center, xmin, ymax)
    inner_svg = transform_to_svg(inner, xmin, ymax)
    outer_svg = transform_to_svg(outer, xmin, ymax)

    start_index %= len(center)
    start_points = np.vstack([inner[start_index], outer[start_index]])
    start_svg = transform_to_svg(start_points, xmin, ymax)

    body = build_track_svg_body(
        center_svg, inner_svg, outer_svg,
        road_color=road_color,
        field_color=field_color,
        boundary_color=boundary_color,
        center_color=center_color,
        boundary_width_m=boundary_width_m,
        center_width_m=center_width_m,
        dash_m=dash_m,
        gap_m=gap_m,
        draw_centerline=draw_centerline,
        draw_start_line=draw_start_line,
        checker_start_line=checker_start_line,
        start_svg=start_svg,
        start_line_width_m=start_line_width_m,
        page_width_m=width_m,
        page_height_m=height_m,
    )

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{width_m*1000:.2f}mm"
     height="{height_m*1000:.2f}mm"
     viewBox="0 0 {width_m:.6f} {height_m:.6f}"
     preserveAspectRatio="xMidYMid meet">
    <title>{xml_escape(title)}</title>
    <desc>DeepRacer track, true physical scale.</desc>
{body}
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")
    return width_m, height_m


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def write_preview_png(output_path, center, inner, outer, start_index):
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError(
            "PNG preview requires matplotlib. Install with: pip install matplotlib"
        ) from exc

    road_polygon = np.vstack([inner, outer[::-1]])
    start_index %= len(center)

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.fill(road_polygon[:, 0], road_polygon[:, 1], alpha=0.6)
    ax.plot(inner[:, 0], inner[:, 1], linewidth=1.4, label="Inner boundary")
    ax.plot(outer[:, 0], outer[:, 1], linewidth=1.4, label="Outer boundary")
    ax.plot(center[:, 0], center[:, 1], "--", linewidth=1.1, label="Centerline")
    ax.plot(
        [inner[start_index,0], outer[start_index,0]],
        [inner[start_index,1], outer[start_index,1]],
        linewidth=3, label=f"Start index {start_index}"
    )
    ax.set_aspect("equal", adjustable="box")
    ax.set_title("DeepRacer Track Geometry Preview")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.legend()
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Panels and production annotations
# ---------------------------------------------------------------------------

def panel_intervals(total_m, panel_width_m, overlap_m):
    if panel_width_m <= 0:
        raise ValueError("--panel-width must be > 0")
    if overlap_m < 0:
        raise ValueError("--panel-overlap must be >= 0")
    if overlap_m >= panel_width_m:
        raise ValueError("--panel-overlap must be smaller than --panel-width")

    if total_m <= panel_width_m:
        return [(0.0, total_m)]

    stride = panel_width_m - overlap_m
    intervals = []
    start = 0.0

    while True:
        end = min(start + panel_width_m, total_m)
        intervals.append((start, end))
        if end >= total_m - 1e-9:
            break

        next_start = start + stride
        if next_start + panel_width_m > total_m:
            next_start = max(0.0, total_m - panel_width_m)

        if abs(next_start - start) < 1e-9:
            break
        start = next_start

    dedup = []
    for iv in intervals:
        if not dedup or abs(iv[0] - dedup[-1][0]) > 1e-9:
            dedup.append(iv)
    return dedup


def registration_cross(x, y, size_m=0.04):
    half = size_m / 2.0
    return (
        f'<g stroke="#FF00FF" stroke-width="0.003">'
        f'<line x1="{x-half:.6f}" y1="{y:.6f}" '
        f'x2="{x+half:.6f}" y2="{y:.6f}" />'
        f'<line x1="{x:.6f}" y1="{y-half:.6f}" '
        f'x2="{x:.6f}" y2="{y+half:.6f}" />'
        f'</g>'
    )


def ruler_svg(x, y, length_m=1.0, height_m=0.025):
    # horizontal 1-meter calibration ruler with 10 cm ticks
    parts = [
        f'<line x1="{x:.6f}" y1="{y:.6f}" '
        f'x2="{x+length_m:.6f}" y2="{y:.6f}" '
        f'stroke="#000000" stroke-width="0.006" />'
    ]
    for i in range(11):
        xx = x + (length_m * i / 10.0)
        tick = height_m if i in (0,10) else height_m * 0.65
        parts.append(
            f'<line x1="{xx:.6f}" y1="{y-tick/2:.6f}" '
            f'x2="{xx:.6f}" y2="{y+tick/2:.6f}" '
            f'stroke="#000000" stroke-width="0.004" />'
        )
    parts.append(
        f'<text x="{x+length_m/2:.6f}" y="{y+0.055:.6f}" '
        f'font-family="Arial, sans-serif" font-size="0.045" '
        f'text-anchor="middle" fill="#000000">1 meter calibration ruler</text>'
    )
    return "\n".join(parts)


def panel_label_svg(panel_num, panel_total, panel_w, panel_h, font_size=0.055):
    return f"""
    <g font-family="Arial, sans-serif" fill="#000000">
      <text x="0.06" y="0.09" font-size="{font_size:.3f}" font-weight="bold">
        PANEL {panel_num} OF {panel_total}
      </text>
      <text x="0.06" y="0.15" font-size="0.040">
        Size: {panel_w:.3f} m × {panel_h:.3f} m
      </text>
    </g>
"""


def trim_box_svg(panel_w, panel_h, inset=0.012):
    return (
        f'<rect x="{inset:.6f}" y="{inset:.6f}" '
        f'width="{panel_w-2*inset:.6f}" height="{panel_h-2*inset:.6f}" '
        f'fill="none" stroke="#FF00FF" stroke-width="0.002" '
        f'stroke-dasharray="0.02,0.02" />'
    )


def overlap_zone_svg(axis, panel_w, panel_h, overlap_m, side):
    if overlap_m <= 0:
        return ""
    fill = "#FF00FF"
    opacity = "0.10"

    if axis == "x":
        if side == "left":
            x, y, w, h = 0, 0, overlap_m, panel_h
        else:
            x, y, w, h = panel_w-overlap_m, 0, overlap_m, panel_h
    else:
        if side == "top":
            x, y, w, h = 0, 0, panel_w, overlap_m
        else:
            x, y, w, h = 0, panel_h-overlap_m, panel_w, overlap_m

    return (
        f'<rect x="{x:.6f}" y="{y:.6f}" width="{w:.6f}" height="{h:.6f}" '
        f'fill="{fill}" fill-opacity="{opacity}" stroke="none" />'
    )


def overlap_label_svg(axis, panel_w, panel_h, overlap_m, text, side):
    if overlap_m <= 0:
        return ""

    fs = 0.035
    if axis == "x":
        x = overlap_m/2 if side == "left" else panel_w-overlap_m/2
        y = min(0.24, panel_h/2)
        rotate = f' transform="rotate(-90 {x:.6f} {y:.6f})"'
    else:
        x = min(0.40, panel_w/2)
        y = overlap_m/2 if side == "top" else panel_h-overlap_m/2
        rotate = ""

    return (
        f'<text x="{x:.6f}" y="{y:.6f}" font-family="Arial, sans-serif" '
        f'font-size="{fs:.3f}" font-weight="bold" fill="#B000B0" '
        f'text-anchor="middle"{rotate}>{xml_escape(text)}</text>'
    )


def write_panel_svgs(
    full_svg_path, output_dir, *,
    full_width_m, full_height_m,
    axis, panel_width_m, overlap_m,
    production_mode
):
    text = full_svg_path.read_text(encoding="utf-8")
    start = text.find(">", text.find("<svg")) + 1
    end = text.rfind("</svg>")
    inner_content = text[start:end]

    if axis == "auto":
        axis = "x" if full_width_m >= full_height_m else "y"

    total = full_width_m if axis == "x" else full_height_m
    intervals = panel_intervals(total, panel_width_m, overlap_m)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = []

    for idx, (a, b) in enumerate(intervals, start=1):
        if axis == "x":
            panel_w = b-a
            panel_h = full_height_m
            translate = f"translate({-a:.6f},0)"
        else:
            panel_w = full_width_m
            panel_h = b-a
            translate = f"translate(0,{-a:.6f})"

        annotations = []

        # Registration marks
        mark_offset = 0.03
        if axis == "x":
            if idx > 1:
                x = min(overlap_m/2, panel_w/2)
                annotations += [
                    registration_cross(x, mark_offset),
                    registration_cross(x, panel_h-mark_offset),
                ]
            if idx < len(intervals):
                x = panel_w-min(overlap_m/2, panel_w/2)
                annotations += [
                    registration_cross(x, mark_offset),
                    registration_cross(x, panel_h-mark_offset),
                ]
        else:
            if idx > 1:
                y = min(overlap_m/2, panel_h/2)
                annotations += [
                    registration_cross(mark_offset, y),
                    registration_cross(panel_w-mark_offset, y),
                ]
            if idx < len(intervals):
                y = panel_h-min(overlap_m/2, panel_h/2)
                annotations += [
                    registration_cross(mark_offset, y),
                    registration_cross(panel_w-mark_offset, y),
                ]

        if production_mode:
            annotations.append(trim_box_svg(panel_w, panel_h))
            annotations.append(panel_label_svg(idx, len(intervals), panel_w, panel_h))

            # ruler: place near lower-left when it fits
            if panel_w >= 1.15 and panel_h >= 0.20:
                annotations.append(ruler_svg(0.08, panel_h-0.12, 1.0))
            else:
                # shorter 0.5 m fallback
                annotations.append(ruler_svg(0.05, panel_h-0.10, 0.5))

            if axis == "x":
                if idx > 1:
                    annotations.append(overlap_zone_svg(axis, panel_w, panel_h, overlap_m, "left"))
                    annotations.append(
                        overlap_label_svg(
                            axis, panel_w, panel_h, overlap_m,
                            f"OVERLAP WITH PANEL {idx-1}", "left"
                        )
                    )
                if idx < len(intervals):
                    annotations.append(overlap_zone_svg(axis, panel_w, panel_h, overlap_m, "right"))
                    annotations.append(
                        overlap_label_svg(
                            axis, panel_w, panel_h, overlap_m,
                            f"OVERLAP WITH PANEL {idx+1}", "right"
                        )
                    )
            else:
                if idx > 1:
                    annotations.append(overlap_zone_svg(axis, panel_w, panel_h, overlap_m, "top"))
                    annotations.append(
                        overlap_label_svg(
                            axis, panel_w, panel_h, overlap_m,
                            f"OVERLAP WITH PANEL {idx-1}", "top"
                        )
                    )
                if idx < len(intervals):
                    annotations.append(overlap_zone_svg(axis, panel_w, panel_h, overlap_m, "bottom"))
                    annotations.append(
                        overlap_label_svg(
                            axis, panel_w, panel_h, overlap_m,
                            f"OVERLAP WITH PANEL {idx+1}", "bottom"
                        )
                    )

        ann = "\n    ".join(annotations)

        svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{panel_w*1000:.2f}mm"
     height="{panel_h*1000:.2f}mm"
     viewBox="0 0 {panel_w:.6f} {panel_h:.6f}"
     preserveAspectRatio="xMinYMin meet">
    <title>DeepRacer print panel {idx} of {len(intervals)}</title>
    <desc>Print at 100% / Actual Size. Axis={axis}; overlap={overlap_m:.3f} m.</desc>

    <g transform="{translate}">
{inner_content}
    </g>

    {ann}
</svg>
"""

        panel_path = output_dir / f"{full_svg_path.stem}_panel_{idx:02d}.svg"
        panel_path.write_text(svg, encoding="utf-8")

        manifest.append({
            "panel": idx,
            "file": panel_path.name,
            "axis": axis,
            "start_m": a,
            "end_m": b,
            "width_m": panel_w,
            "height_m": panel_h,
        })

    # Assembly manifest
    manifest_path = output_dir / f"{full_svg_path.stem}_ASSEMBLY_MANIFEST.txt"
    overlap_in = overlap_m * 39.37007874
    lines = [
        f"DeepRacer Track Assembly Manifest",
        f"Source: {full_svg_path.name}",
        "",
        f"Full document: {full_width_m:.4f} m x {full_height_m:.4f} m",
        f"Panel axis: {axis}",
        f"Panel width target: {panel_width_m:.4f} m",
        f"Overlap: {overlap_m:.4f} m ({overlap_in:.2f} in)",
        f"Production mode: {'ON' if production_mode else 'OFF'}",
        "",
        "PRINT SHOP:",
        "  - Print every SVG at 100% / Actual Size.",
        "  - Do NOT use Fit to Page or automatic scaling.",
        "  - Preserve the complete overlap zone.",
        "  - Verify the 1-meter ruler measures exactly 1.000 m before production.",
        "",
        "ASSEMBLY:",
        "  - Lay panels in numeric order.",
        "  - Align magenta registration crosshairs.",
        "  - Match the shaded overlap zone with the neighboring panel.",
        "  - Do not trim away the overlap until alignment is verified.",
        "  - Secure panels from the underside or outside the driving surface where possible.",
        "",
        "PANELS:"
    ]
    for item in manifest:
        lines.append(
            f"  Panel {item['panel']:02d}: {item['file']} | "
            f"{item['width_m']:.4f} m x {item['height_m']:.4f} m | "
            f"{axis}: {item['start_m']:.4f} -> {item['end_m']:.4f} m"
        )

    manifest_path.write_text("\n".join(lines), encoding="utf-8")

    # Simple assembly order SVG
    assembly_svg = output_dir / f"{full_svg_path.stem}_ASSEMBLY_ORDER.svg"

    if axis == "x":
        box_w, box_h = 1.0, 0.5
        total_w = max(3.0, len(manifest) * 1.1)
        total_h = 1.2
        boxes = []
        x = 0.1
        for item in manifest:
            boxes.append(
                f'<rect x="{x:.3f}" y="0.30" width="{box_w:.3f}" height="{box_h:.3f}" '
                f'fill="#F2F2F2" stroke="#333333" stroke-width="0.01" />'
                f'<text x="{x+box_w/2:.3f}" y="0.60" text-anchor="middle" '
                f'font-family="Arial" font-size="0.18">P{item["panel"]}</text>'
            )
            x += 1.1
    else:
        box_w, box_h = 1.1, 0.45
        total_w = 1.8
        total_h = max(2.0, len(manifest) * 0.6)
        boxes = []
        y = 0.2
        for item in manifest:
            boxes.append(
                f'<rect x="0.30" y="{y:.3f}" width="{box_w:.3f}" height="{box_h:.3f}" '
                f'fill="#F2F2F2" stroke="#333333" stroke-width="0.01" />'
                f'<text x="0.85" y="{y+0.28:.3f}" text-anchor="middle" '
                f'font-family="Arial" font-size="0.18">P{item["panel"]}</text>'
            )
            y += 0.6

    assembly_svg.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{total_w*100:.0f}mm" height="{total_h*100:.0f}mm"
     viewBox="0 0 {total_w:.3f} {total_h:.3f}">
  <text x="0.1" y="0.18" font-family="Arial" font-size="0.16" font-weight="bold">
    DeepRacer Panel Assembly Order
  </text>
  {''.join(boxes)}
</svg>
""",
        encoding="utf-8"
    )

    return manifest, manifest_path, assembly_svg


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        description=(
            "Inspect a DeepRacer .npy track and export full-scale SVG, preview, "
            "and optional production-ready print panels."
        )
    )

    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--inspect-only", action="store_true")

    p.add_argument("--margin", type=float, default=0.50)
    p.add_argument("--road-color", default="#333F48")
    p.add_argument("--field-color", default="#00A98F")
    p.add_argument("--boundary-color", default="#FFFFFF")
    p.add_argument("--center-color", default="#F5A800")
    p.add_argument("--boundary-width", type=float, default=0.050)
    p.add_argument("--center-width", type=float, default=0.040)
    p.add_argument("--dash", type=float, default=0.20)
    p.add_argument("--gap", type=float, default=0.20)

    p.add_argument("--no-centerline", action="store_true")
    p.add_argument("--no-start-line", action="store_true")
    p.add_argument("--simple-start-line", action="store_true")
    p.add_argument("--start-index", type=int, default=0)
    p.add_argument("--start-line-width", type=float, default=0.10)

    p.add_argument("--preview", type=Path, default=None)

    p.add_argument(
        "--panel-width", type=float, default=None, metavar="METERS",
        help="Maximum panel width. Example: 1.2192 for 48 inches."
    )
    p.add_argument(
        "--panel-overlap", type=float, default=0.05, metavar="METERS",
        help="Panel overlap in meters (default: 0.05 ≈ 2 in)."
    )
    p.add_argument(
        "--panel-axis", choices=["auto", "x", "y"], default="auto"
    )
    p.add_argument("--panel-dir", type=Path, default=None)

    p.add_argument(
        "--production-mode", action="store_true",
        help="Add panel labels, trim guides, overlap zones, ruler, and assembly aids."
    )
    # Room-aware fitting / scaling
    p.add_argument('--scale', type=float, default=None,
                   help='Uniform scale factor, e.g. 0.90. Cannot be combined with room fitting.')
    p.add_argument('--fit-room-width', type=float, default=None,
                   help='Room/usable-space width in --room-units.')
    p.add_argument('--fit-room-height', type=float, default=None,
                   help='Room/usable-space height in --room-units.')
    p.add_argument('--room-units', choices=['m','ft'], default='m',
                   help='Units for room width/height/clearance (default: m).')
    p.add_argument('--room-clearance', type=float, default=0.0,
                   help='Clearance on EACH side, in --room-units (default: 0).')
    p.add_argument('--rotate-to-fit', action='store_true',
                   help='Try a 90-degree rotation and use it if it permits a larger scale.')
    p.add_argument('--minimum-track-width', type=float, default=24.0,
                   help='Minimum acceptable scaled lane width (default: 24).')
    p.add_argument('--minimum-track-width-units', choices=['m','ft','in'], default='in',
                   help='Units for --minimum-track-width (default: in).')
    p.add_argument('--force-scale', action='store_true',
                   help='Allow export even when scaled lane width is below the minimum.')

    p.add_argument("--title", default=None)

    return p


def validate_args(args):
    for name in [
        "margin", "boundary_width", "center_width",
        "dash", "gap", "start_line_width", "panel_overlap"
    ]:
        if getattr(args, name) < 0:
            raise ValueError(f"--{name.replace('_','-')} must be non-negative")

    if args.panel_width is not None and args.panel_width <= 0:
        raise ValueError("--panel-width must be > 0")
    if args.panel_width is not None and args.panel_overlap >= args.panel_width:
        raise ValueError("--panel-overlap must be smaller than --panel-width")

    if args.scale is not None and args.scale <= 0:
        raise ValueError('--scale must be > 0')

    room_w_set = args.fit_room_width is not None
    room_h_set = args.fit_room_height is not None
    if room_w_set != room_h_set:
        raise ValueError('Use --fit-room-width and --fit-room-height together.')
    if args.scale is not None and room_w_set:
        raise ValueError('--scale cannot be combined with room fitting.')
    if args.room_clearance < 0:
        raise ValueError('--room-clearance must be >= 0')
    if args.minimum_track_width <= 0:
        raise ValueError('--minimum-track-width must be > 0')


def main():
    args = build_parser().parse_args()

    try:
        validate_args(args)

        if not args.input.exists():
            raise FileNotFoundError(args.input)

        _, center, inner, outer = load_track(args.input)
        stats = inspect_geometry(center, inner, outer)
        print_report(args.input, stats)

        applied_scale = 1.0
        applied_rotate = False
        minimum_width_m = to_meters(args.minimum_track_width, args.minimum_track_width_units)

        if args.fit_room_width is not None:
            room_w_m = to_meters(args.fit_room_width, args.room_units)
            room_h_m = to_meters(args.fit_room_height, args.room_units)
            clearance_m = to_meters(args.room_clearance, args.room_units)
            fit = calculate_room_fit(
                inner, outer, args.margin,
                room_w_m, room_h_m, clearance_m,
                args.rotate_to_fit
            )
            applied_scale = fit['scale']
            applied_rotate = fit['rotate']
            print_room_fit_report(fit, stats['mean_track_width_m'], minimum_width_m)
        elif args.scale is not None:
            applied_scale = args.scale
            print()
            print('Explicit scaling')
            print('-' * 72)
            print(f'Uniform scale factor       : {applied_scale:.4f} ({applied_scale*100:.1f}%)')
            print(f"Scaled mean lane width     : {stats['mean_track_width_m']*applied_scale:.3f} m ({stats['mean_track_width_m']*applied_scale*39.37007874:.1f} in)")

        scaled_lane_width_m = stats['mean_track_width_m'] * applied_scale
        if scaled_lane_width_m < minimum_width_m:
            print()
            print(f"WARNING: Scaled lane width would be {scaled_lane_width_m:.3f} m ({scaled_lane_width_m*39.37007874:.1f} in), below the requested minimum of {minimum_width_m:.3f} m ({minimum_width_m*39.37007874:.1f} in).")
            if not args.force_scale:
                print('Export stopped. Choose a smaller source track, a larger room, lower the minimum, or use --force-scale for a mock-up.')
                return 2
            print('Proceeding because --force-scale was supplied.')

        if args.inspect_only:
            return 0

        center, inner, outer = transform_track(center, inner, outer, applied_scale, applied_rotate)

        scaled_margin = args.margin * applied_scale
        scaled_boundary_width = args.boundary_width * applied_scale
        scaled_center_width = args.center_width * applied_scale
        scaled_dash = args.dash * applied_scale
        scaled_gap = args.gap * applied_scale
        scaled_start_line_width = args.start_line_width * applied_scale

        output = args.output or args.input.with_suffix('.svg')
        output.parent.mkdir(parents=True, exist_ok=True)

        full_w, full_h = write_full_svg(
            output, center, inner, outer,
            title=args.title or args.input.stem,
            margin_m=scaled_margin,
            road_color=args.road_color,
            field_color=args.field_color,
            boundary_color=args.boundary_color,
            center_color=args.center_color,
            boundary_width_m=scaled_boundary_width,
            center_width_m=scaled_center_width,
            dash_m=scaled_dash,
            gap_m=scaled_gap,
            draw_centerline=not args.no_centerline,
            draw_start_line=not args.no_start_line,
            checker_start_line=not args.simple_start_line,
            start_index=args.start_index,
            start_line_width_m=scaled_start_line_width
        )

        print(f"\nFull SVG                   : {output}")
        print(f"Physical document          : {full_w:.3f} m x {full_h:.3f} m")
        print(f"Applied scale              : {applied_scale:.4f} ({applied_scale*100:.1f}%)")
        print(f"Applied 90-degree rotation : {'YES' if applied_rotate else 'NO'}")
        print(f"Final mean lane width      : {stats['mean_track_width_m']*applied_scale:.3f} m ({stats['mean_track_width_m']*applied_scale*39.37007874:.1f} in)")

        if args.preview:
            args.preview.parent.mkdir(parents=True, exist_ok=True)
            write_preview_png(args.preview, center, inner, outer, args.start_index)
            print(f"Preview PNG                : {args.preview}")

        if args.panel_width is not None:
            panel_dir = args.panel_dir or output.with_name(output.stem + "_panels")

            manifest, manifest_path, assembly_svg = write_panel_svgs(
                output, panel_dir,
                full_width_m=full_w,
                full_height_m=full_h,
                axis=args.panel_axis,
                panel_width_m=args.panel_width,
                overlap_m=args.panel_overlap,
                production_mode=args.production_mode
            )

            print(f"Panel directory            : {panel_dir}")
            print(f"Number of panels           : {len(manifest)}")
            print(f"Assembly manifest          : {manifest_path}")
            print(f"Assembly order diagram     : {assembly_svg}")

        print("\nPRINT SHOP:")
        print("  Print at 100% / Actual Size.")
        print("  Do not use Fit to Page.")
        if args.production_mode:
            print("  Verify the printed calibration ruler before the full run.")
            print("  Preserve overlap areas and alignment marks.")

        return 0

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
