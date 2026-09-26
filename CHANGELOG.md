# Changelog

All notable changes to vizreel are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `vizreel render --watch` renders again whenever the spec or its theme file is saved. Only the charts that changed are rendered, an invalid spec prints its errors without stopping, and Ctrl+C stops watching.

## [0.1.1] - 2026-09-27

Fixes found while making the first real clips with 0.1.0.

### Changed

- `--quality preview` writes `ID.preview.mov` (and `ID.preview.png` with `--still`), so a preview no longer replaces a final clip of the same chart.

### Fixed

- The first render after installing no longer prints `SyntaxWarning: invalid escape sequence` warnings from pydub, a Manim dependency.
- Timeline labels sit on a common baseline. A dotted capital İ, an accent or a descender used to move a label a few pixels off its row.
- The same holds for bar labels, the x labels of line charts and the series names next to their values. The gap between a title and its subtitle no longer depends on whether the title has descenders.
- The first-value labels of a line chart no longer overlap each other or a line. Each goes above or below its point, wherever it is clear of labels and lines; if neither side is clear, the labels stack above the lines.

## [0.1.0] - 2026-09-26

The first release.

### Added

- Four chart types, each rendered to its own clip: `stat` (a number that counts to its value), `line` (up to three series drawn from left to right), `bar` (up to eight bars with one highlighted) and `timeline` (up to seven events with one emphasized).
- The YAML spec format, version 1, validated with every error reported at once and its location. `vizreel validate` checks a spec; `vizreel schema` writes its JSON Schema for editors and tools.
- `vizreel render` with `--out`, `--only`, `--quality preview|final`, `--format mov|webm|mp4` and `--still`. Clips are exactly as long as their `duration`; `mov` and `webm` keep a transparent background.
- Number formatting with prefixes, suffixes, fixed or automatic decimals, compact units (K, M, B, T) and consistent decimals within a chart.
- Two built-in themes, `default` and `light`, and custom themes loaded by path. `vizreel themes list` lists the built-in themes; `vizreel theme check` tests a theme's contrast (WCAG) and its colors for color vision deficiency.
- `vizreel new TYPE` prints a commented template for each chart type.
- The Inter typeface, bundled so that output looks the same on every machine.

[0.1.1]: https://github.com/efedalbay/vizreel/releases/tag/v0.1.1
[0.1.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.1.0
