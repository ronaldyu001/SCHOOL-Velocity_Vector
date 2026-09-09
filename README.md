# SCHOOL-Velocity_Vector

AWS DeepRacer project work. Each area of the repo has its own README with the
detailed instructions; this page is the directory that points at them.

## Directory

| Area | What it covers | Docs |
| --- | --- | --- |
| [`track_selection/`](track_selection) | Track verification and selection — converting DeepRacer `.npy` tracks to printable SVGs, fitting them to the room, and scoring which ones stay at or above 80% of their original size | [track_selection/README.md](track_selection/README.md) |

## Repository root

| Path | Purpose |
| --- | --- |
| [`requirements.in`](requirements.in) | Top-level dependencies |
| [`requirements.txt`](requirements.txt) | Pinned versions, compiled with `pip-compile` |

Setup instructions live in each area's README — start with
[track_selection/README.md](track_selection/README.md#0-prerequisites).
