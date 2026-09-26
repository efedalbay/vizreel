# Changelog

All notable changes to vizreel are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

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

[0.1.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.1.0
