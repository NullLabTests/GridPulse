# Changelog

## 0.1.0 — 2026-10-10

- Initial implementation of GridPulse M1.
- Source inspection and CC BY 4.0 verification for OpenEI Event-correlated Outage Dataset.
- Preregistration document committed.
- Ingestion, schema validation, MAD and trailing-window detectors, chronological evaluation, CLI, HTML report, and unit tests.
- Synthetic fixture for fully offline smoke tests.
- No methodological changes from preregistration yet.

## 0.2.0 — 2026-10-10

- Added **GridPulse Studio**: a Tkinter desktop GUI (`gridpulse gui`) for interactive detector tuning, flag inspection, and proxy-agreement metrics.
- Added `--demo` tour mode (scripted parameter walk) used to produce README screenshots and video.
- Added a `gui` optional dependency group (`pillow` for `ImageTk`).
- README now includes a GUI screenshot, a looping demo GIF, an MP4 video, and an explicit comparison against existing outage maps, dashboards, and generic anomaly libraries.
- No methodological changes from preregistration; the GUI reuses the same detector and evaluation code as the CLI.
