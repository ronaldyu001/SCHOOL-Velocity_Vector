## Converting npy track file into vector (svg) file

### Basic usage

Install NumPy if needed:

```bash
pip install numpy
```

Inspect a track without generating anything:

```bash
python deepracer_track_converter.py \
    2024_reinvent_champ_cw.npy \
    --inspect-only
```

Generate the default SVG:

```bash
python deepracer_track_converter.py \
    2024_reinvent_champ_cw.npy
```

That automatically produces:

```text
2024_reinvent_champ_cw.svg
```

Or choose the output filename:

```bash
python deepracer_track_converter.py \
    2024_reinvent_champ_cw.npy \
    --output reinvention_track.svg
```

### Useful options

Change the surrounding margin:

```bash
--margin 0.75
```

Change the start waypoint:

```bash
--start-index 12
```

Use a plain white start line rather than the checker-style version:

```bash
--simple-start-line
```

Remove the centerline:

```bash
--no-centerline
```

Remove the start line:

```bash
--no-start-line
```

Control physical line widths:

```bash
--boundary-width 0.05 \
--center-width 0.04 \
--start-line-width 0.10
```

Control the dashed centerline:

```bash
--dash 0.20 \
--gap 0.20
```

You can also change colors, for example:

```bash
python deepracer_track_converter.py track.npy \
    --output track.svg \
    --field-color "#00A98F" \
    --road-color "#333F48" \
    --boundary-color "#FFFFFF" \
    --center-color "#F5A800"
```

### Most important printing detail

The utility writes real physical dimensions into the SVG. For example, the SVG generated from your uploaded track contains a physical page size corresponding to about:

```text
11.817 m × 5.156 m
```

So your print-shop instruction should be:

> **Print at 100% / Actual Size. Do not use Fit to Page, Scale to Media, or automatic resizing.**

The next enhancement I would recommend is adding a `--preview` option and a **multi-panel export mode**, e.g.:

```bash
python deepracer_track_converter.py track.npy \
    --panels 4 \
    --panel-overlap 0.05
```

That would divide a 30–40 ft track into manageable printable strips with alignment marks, which may be much more practical for your CU Denver large-format printer.
