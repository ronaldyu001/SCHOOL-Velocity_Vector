#!/usr/bin/env python3
"""Batch-convert DeepRacer .npy tracks to SVG and score them by how much of the
original track size survives the room fit.

For every track in --track-dir this runs deepracer_track_converter_v4.py with the
room-fit options, captures the converter's printed report, and records the result
in a CSV.  The percentage of original size is the converter's uniform scale
factor; a track is a candidate for printing only when it stays at or above
--threshold percent AND clears every gate the converter enforces.

Gates recorded in the CSV
-------------------------
track_data_valid       load_track(): array shape, waypoint count, NaN/inf check.
room_fit_valid         calculate_room_fit(): room/clearance leaves usable floor.
meets_min_track_width  scaled mean lane width >= --minimum-track-width.
                       The converter refuses to export when this fails (exit 2).
meets_size_threshold   scale percentage >= --threshold (our own selection rule).

Usage
-----
    python converters/run_batch_convert.py
    python converters/run_batch_convert.py --room-width 20 --room-height 24 --room-units ft
    python converters/run_batch_convert.py --threshold 85 --no-rotate
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent      # track_selection/converters
ROOT = HERE.parent                          # track_selection

CONVERTER = HERE / "deepracer_track_converter_v4.py"
TRACK_DIR = ROOT / "track-data"
SVG_DIR = ROOT / "svg_tracks"
RESULTS_CSV = ROOT / "batch_converter_results.csv"

# Room the printed track has to fit inside.
ROOM_WIDTH = 20.0
ROOM_HEIGHT = 24.0
ROOM_UNITS = "ft"
ROOM_CLEARANCE = 0.0

# A track is only worth printing if it keeps at least this much of its size.
SIZE_THRESHOLD_PCT = 80.0

# Narrowest usable lane once scaled; the converter blocks export below this.
MIN_TRACK_WIDTH = 24.0
MIN_TRACK_WIDTH_UNITS = "in"

CSV_COLUMNS = [
    "map_name",
    "percent_of_original_size",
    "meets_size_threshold",
    "meets_min_track_width",
    "track_data_valid",
    "room_fit_valid",
    "status",
    "error_message",
    "svg_written",
    "scaled_lane_width_in",
    "min_required_lane_width_in",
    "original_lane_width_in",
    "rotated_90",
    "fitted_width_m",
    "fitted_height_m",
    "centerline_length_m",
    "waypoints",
    "svg_path",
]

# ---------------------------------------------------------------------------
# Parsing of the converter's printed report
# ---------------------------------------------------------------------------

# "Uniform scale factor       : 0.8123 (81.2%)"
RE_SCALE = re.compile(r"Uniform scale factor\s*:\s*([0-9.]+)")
# "Scaled mean lane width     : 0.512 m (20.2 in)"
RE_SCALED_LANE = re.compile(r"Scaled mean lane width\s*:\s*[0-9.]+ m \(([0-9.]+) in\)")
# "Minimum requested lane     : 0.610 m (24.0 in)"
RE_MIN_LANE = re.compile(r"Minimum requested lane\s*:\s*[0-9.]+ m \(([0-9.]+) in\)")
# "Mean track width           : 0.760 m (29.9 in)"
RE_MEAN_WIDTH = re.compile(r"Mean track width\s*:\s*[0-9.]+ m \(([0-9.]+) in\)")
# "Rotate 90 degrees          : YES"
RE_ROTATE = re.compile(r"Rotate 90 degrees\s*:\s*(YES|NO)")
# "Fitted artwork size        : 5.900 m x 7.200 m"
RE_FITTED = re.compile(r"Fitted artwork size\s*:\s*([0-9.]+) m x ([0-9.]+) m")
# "Centerline length          : 46.231 m (151.7 ft)"
RE_CENTERLINE = re.compile(r"Centerline length\s*:\s*([0-9.]+) m")
# "Waypoints                  : 240"
RE_WAYPOINTS = re.compile(r"Waypoints\s*:\s*(\d+)")
# "ERROR: Track contains NaN or infinite values."
RE_ERROR = re.compile(r"ERROR:\s*(.+)")

RE_BELOW_MIN = re.compile(r"WARNING: Scaled lane width would be")

# Errors raised before any geometry is loaded vs. by the room-fit maths.
ROOM_FIT_ERROR_MARKERS = (
    "Room width and height must be > 0",
    "Room clearance must be >= 0",
    "Room clearance leaves no usable floor area",
)


def _search_float(pattern: re.Pattern, text: str):
    match = pattern.search(text)
    return float(match.group(1)) if match else None


def parse_output(stdout: str, stderr: str) -> dict:
    """Pull every number we care about out of the converter's printed report."""
    text = stdout + "\n" + stderr
    scale = _search_float(RE_SCALE, text)
    fitted = RE_FITTED.search(text)
    rotate = RE_ROTATE.search(text)
    waypoints = RE_WAYPOINTS.search(text)
    error = RE_ERROR.search(stderr) or RE_ERROR.search(stdout)

    return {
        "percent_of_original_size": round(scale * 100.0, 2) if scale is not None else None,
        "scaled_lane_width_in": _search_float(RE_SCALED_LANE, text),
        "min_required_lane_width_in": _search_float(RE_MIN_LANE, text),
        "original_lane_width_in": _search_float(RE_MEAN_WIDTH, text),
        "rotated_90": (rotate.group(1) == "YES") if rotate else None,
        "fitted_width_m": float(fitted.group(1)) if fitted else None,
        "fitted_height_m": float(fitted.group(2)) if fitted else None,
        "centerline_length_m": _search_float(RE_CENTERLINE, text),
        "waypoints": int(waypoints.group(1)) if waypoints else None,
        "below_min_width": bool(RE_BELOW_MIN.search(text)),
        "error_message": error.group(1).strip() if error else "",
    }


def classify(parsed: dict, returncode: int, geometry_loaded: bool) -> dict:
    """Turn the parsed report into the CSV's gate columns."""
    error = parsed["error_message"]
    room_fit_error = any(marker in error for marker in ROOM_FIT_ERROR_MARKERS)

    if returncode == 0:
        status = "ok"
    elif returncode == 2 or parsed["below_min_width"]:
        status = "below_min_track_width"
    elif room_fit_error:
        status = "room_fit_error"
    elif not geometry_loaded:
        status = "invalid_track_data"
    else:
        status = "converter_error"

    track_data_valid = geometry_loaded
    room_fit_valid = geometry_loaded and not room_fit_error

    if status == "below_min_track_width":
        meets_min_width = False
    elif status == "ok":
        meets_min_width = True
    else:
        meets_min_width = None

    return {
        "track_data_valid": track_data_valid,
        "room_fit_valid": room_fit_valid,
        "meets_min_track_width": meets_min_width,
        "status": status,
    }


def display_path(path: Path) -> str:
    """Path relative to track_selection when it lives there, else absolute."""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def fmt(value) -> str:
    """CSV-friendly rendering: booleans as PASS/FAIL, unknowns as blank."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    return str(value)


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def convert_one(npy_path: Path, svg_path: Path, args) -> dict:
    cmd = [
        sys.executable,
        str(args.converter),
        str(npy_path),
        "--output", str(svg_path),
        "--fit-room-width", str(args.room_width),
        "--fit-room-height", str(args.room_height),
        "--room-units", args.room_units,
        "--room-clearance", str(args.room_clearance),
        "--margin", str(args.margin),
        "--minimum-track-width", str(args.minimum_track_width),
        "--minimum-track-width-units", args.minimum_track_width_units,
    ]
    if args.rotate_to_fit:
        cmd.append("--rotate-to-fit")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    parsed = parse_output(proc.stdout, proc.stderr)

    # print_report() only runs after load_track() succeeded, so a waypoint count
    # in the output means the .npy itself was valid.
    geometry_loaded = parsed["waypoints"] is not None
    gates = classify(parsed, proc.returncode, geometry_loaded)

    svg_written = gates["status"] == "ok" and svg_path.exists()
    scale_pct = parsed["percent_of_original_size"]
    meets_threshold = (scale_pct >= args.threshold) if scale_pct is not None else None

    row = {
        "map_name": npy_path.stem,
        "percent_of_original_size": scale_pct,
        "meets_size_threshold": meets_threshold,
        "meets_min_track_width": gates["meets_min_track_width"],
        "track_data_valid": gates["track_data_valid"],
        "room_fit_valid": gates["room_fit_valid"],
        "status": gates["status"],
        "error_message": parsed["error_message"],
        "svg_written": svg_written,
        "scaled_lane_width_in": parsed["scaled_lane_width_in"],
        "min_required_lane_width_in": parsed["min_required_lane_width_in"],
        "original_lane_width_in": parsed["original_lane_width_in"],
        "rotated_90": parsed["rotated_90"],
        "fitted_width_m": parsed["fitted_width_m"],
        "fitted_height_m": parsed["fitted_height_m"],
        "centerline_length_m": parsed["centerline_length_m"],
        "waypoints": parsed["waypoints"],
        "svg_path": display_path(svg_path) if svg_written else "",
    }
    return row


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Batch-convert .npy tracks to SVG and record the percentage of original size for each."
    )
    p.add_argument("--track-dir", type=Path, default=TRACK_DIR)
    p.add_argument("--svg-dir", type=Path, default=SVG_DIR)
    p.add_argument("--results-csv", type=Path, default=RESULTS_CSV)
    p.add_argument("--converter", type=Path, default=CONVERTER)

    p.add_argument("--room-width", type=float, default=ROOM_WIDTH)
    p.add_argument("--room-height", type=float, default=ROOM_HEIGHT)
    p.add_argument("--room-units", choices=["m", "ft"], default=ROOM_UNITS)
    p.add_argument("--room-clearance", type=float, default=ROOM_CLEARANCE)
    p.add_argument("--margin", type=float, default=0.50,
                   help="Surrounding margin in meters, passed through to the converter.")

    p.add_argument("--threshold", type=float, default=SIZE_THRESHOLD_PCT,
                   help="Minimum percentage of original size for a track to be a candidate.")
    p.add_argument("--minimum-track-width", type=float, default=MIN_TRACK_WIDTH)
    p.add_argument("--minimum-track-width-units", choices=["m", "ft", "in"],
                   default=MIN_TRACK_WIDTH_UNITS)

    p.add_argument("--no-rotate", dest="rotate_to_fit", action="store_false",
                   help="Do not allow a 90-degree rotation to gain scale.")
    p.set_defaults(rotate_to_fit=True)
    return p


def main() -> int:
    args = build_parser().parse_args()

    if not args.converter.exists():
        print(f"ERROR: converter not found: {args.converter}", file=sys.stderr)
        return 1
    if not args.track_dir.is_dir():
        print(f"ERROR: track directory not found: {args.track_dir}", file=sys.stderr)
        return 1

    tracks = sorted(args.track_dir.glob("*.npy"))
    if not tracks:
        print(f"ERROR: no .npy files in {args.track_dir}", file=sys.stderr)
        return 1

    args.svg_dir.mkdir(parents=True, exist_ok=True)

    print(f"Converter   : {args.converter.name}")
    print(f"Tracks      : {len(tracks)} in {args.track_dir}")
    print(f"Room        : {args.room_width} x {args.room_height} {args.room_units} "
          f"(clearance {args.room_clearance} {args.room_units} per side)")
    print(f"Rotate to fit: {'YES' if args.rotate_to_fit else 'NO'}")
    print(f"Threshold   : >= {args.threshold:.1f}% of original size")
    print("-" * 72)

    rows = []
    for index, npy_path in enumerate(tracks, start=1):
        svg_path = args.svg_dir / f"{npy_path.stem}.svg"
        row = convert_one(npy_path, svg_path, args)
        rows.append(row)

        pct = row["percent_of_original_size"]
        pct_text = f"{pct:6.2f}%" if pct is not None else "     --"
        flag = "OK " if row["meets_size_threshold"] else "-- "
        if row["status"] != "ok":
            flag = "!! "
        print(f"[{index:3d}/{len(tracks)}] {flag}{pct_text}  {row['map_name']}"
              + (f"  ({row['status']})" if row["status"] != "ok" else ""))

    # Best candidates first; anything the converter could not scale sorts last.
    rows.sort(key=lambda r: (r["percent_of_original_size"] is None,
                             -(r["percent_of_original_size"] or 0.0),
                             r["map_name"]))

    args.results_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.results_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: fmt(row[key]) for key in CSV_COLUMNS})

    candidates = [r for r in rows if r["meets_size_threshold"] and r["status"] == "ok"]
    below_threshold = [r for r in rows if r["meets_size_threshold"] is False and r["status"] == "ok"]
    failed_width = [r for r in rows if r["status"] == "below_min_track_width"]
    errored = [r for r in rows if r["status"] not in ("ok", "below_min_track_width")]

    print("-" * 72)
    print(f"Candidates (>= {args.threshold:.1f}% and all gates passed): {len(candidates)}")
    print(f"Below size threshold                              : {len(below_threshold)}")
    print(f"Failed minimum track width                        : {len(failed_width)}")
    print(f"Errored                                           : {len(errored)}")
    print(f"SVGs written                                      : {sum(1 for r in rows if r['svg_written'])} -> {args.svg_dir}")
    print(f"Results CSV                                       : {args.results_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
