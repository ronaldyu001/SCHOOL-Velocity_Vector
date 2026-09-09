# Track selection

Convert DeepRacer `.npy` tracks into printable SVGs, and score every track by how
much of its original size survives being fitted to the room.

---

## 0. Prerequisites

From the repository root, create a virtual environment and install the pinned
dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then work from this folder:

```bash
cd track_selection
```

---

## 1. Single convert

`converters/deepracer_track_converter_v4.py` converts one track.

Inspect a track without generating anything:

```bash
python converters/deepracer_track_converter_v4.py track-data/2024_reinvent_champ_cw.npy --inspect-only
```

Generate the SVG (defaults to `<input>.svg`, or use `--output`):

```bash
python converters/deepracer_track_converter_v4.py track-data/2024_reinvent_champ_cw.npy --output svg_tracks/champ_cw.svg
```

Fit the track to a room, which is what produces the scale percentage:

```bash
python converters/deepracer_track_converter_v4.py track-data/reinvent_base.npy \
    --fit-room-width 20 --fit-room-height 24 --room-units ft --rotate-to-fit
```

### Useful options

| Option | Purpose |
| --- | --- |
| `--margin 0.75` | Surrounding margin in meters |
| `--start-index 12` | Change the start waypoint |
| `--simple-start-line` | Plain white start line instead of checkered |
| `--no-centerline` / `--no-start-line` | Drop those elements |
| `--boundary-width` / `--center-width` / `--start-line-width` | Physical line widths in meters |
| `--dash 0.20 --gap 0.20` | Dashed centerline spacing |
| `--field-color` / `--road-color` / `--boundary-color` / `--center-color` | Colors, e.g. `"#00A98F"` |
| `--minimum-track-width 24` | Narrowest acceptable scaled lane (inches); export stops below it unless `--force-scale` |
| `--preview out.png` | PNG preview (needs matplotlib) |
| `--panel-width 1.2192 --production-mode` | Split into printable panels with alignment marks |

### Printing

The SVG carries real physical dimensions, so:

> **Print at 100% / Actual Size. Do not use Fit to Page, Scale to Media, or automatic resizing.**

---

## 2. Batch convert

`converters/run_batch_convert.py` runs the converter over every track in `track-data/`,
writes the SVGs to `svg_tracks/`, and records the results in
`batch_converter_results.csv`.

```bash
python converters/run_batch_convert.py
```

Defaults: a **20 x 24 ft** room, 90-degree rotation allowed, and a **>= 80%**
of-original-size threshold for a track to count as a candidate.

```bash
python converters/run_batch_convert.py --room-width 30 --room-height 40 --threshold 85 --no-rotate
```

Other flags: `--room-units`, `--room-clearance`, `--margin`,
`--minimum-track-width`, `--track-dir`, `--svg-dir`, `--results-csv`.

### The CSV

Rows are sorted best-scale-first. `percent_of_original_size` is the driver;
the four gate columns say whether a track is actually usable.

| Column | Gate |
| --- | --- |
| `meets_size_threshold` | Scale >= `--threshold` (our selection rule) |
| `meets_min_track_width` | Scaled lane >= 24 in — the converter refuses to export below this |
| `track_data_valid` | `.npy` shape, waypoint count, no NaN/inf |
| `room_fit_valid` | Room and clearance leave usable floor |

Plus `status`, `error_message`, `svg_written`, and the supporting numbers
(lane widths, `rotated_90`, fitted dimensions, centerline length, waypoints,
`svg_path`).

Tracks that fail a gate are recorded in the CSV but produce no SVG.

Note: the scale factor is not capped at 1.0, so a value above 100% means the
track is smaller than the room and was scaled *up*.
