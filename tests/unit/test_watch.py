from pathlib import Path

import pytest

from vizreel.errors import RenderError, SpecError, ThemeError, VizreelError
from vizreel.render.engine import RenderOptions
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import Spec
from vizreel.watch import FileState, FileWatcher, charts_to_render, watch_spec

SPEC = Path("spec.yaml")
THEME = Path("theme.yaml")


class FakeFiles:
    """File states and a clock that tests move by hand."""

    def __init__(self) -> None:
        self.states: dict[Path, FileState] = {SPEC: (1, 100), THEME: (1, 50)}
        self.now = 0.0

    def state(self, path: Path) -> FileState:
        return self.states.get(path)

    def clock(self) -> float:
        return self.now

    def watcher(self, *paths: Path) -> FileWatcher:
        return FileWatcher(paths or [SPEC], settle=0.3, state=self.state, clock=self.clock)


def test_no_change_is_not_reported() -> None:
    files = FakeFiles()
    watcher = files.watcher()

    files.now = 10.0

    assert not watcher.poll()


def test_a_change_is_reported_once_after_it_settles() -> None:
    files = FakeFiles()
    watcher = files.watcher()

    files.states[SPEC] = (2, 120)
    assert not watcher.poll()
    files.now = 0.2
    assert not watcher.poll()
    files.now = 0.3
    assert watcher.poll()
    files.now = 5.0
    assert not watcher.poll()


def test_a_file_that_keeps_changing_is_not_reported_until_it_stops() -> None:
    files = FakeFiles()
    watcher = files.watcher()

    for step in range(5):
        files.states[SPEC] = (2 + step, 100)
        files.now = step * 0.2
        assert not watcher.poll()
    files.now = 0.8 + 0.3

    assert watcher.poll()


def test_a_file_missing_in_the_middle_of_a_save_is_waited_for() -> None:
    files = FakeFiles()
    watcher = files.watcher()

    del files.states[SPEC]
    assert not watcher.poll()
    files.now = 1.0
    assert not watcher.poll()
    files.states[SPEC] = (3, 100)
    assert not watcher.poll()
    files.now = 1.3

    assert watcher.poll()


def test_watch_keeps_known_files_and_adds_new_ones() -> None:
    files = FakeFiles()
    watcher = files.watcher()
    files.states[SPEC] = (2, 100)

    watcher.watch([SPEC, THEME])

    assert watcher.paths == [SPEC, THEME]
    assert not watcher.poll()
    files.now = 0.3
    assert watcher.poll()


def spec(charts: str, meta: str = "{}") -> Spec:
    return parse_spec(f"version: 1\nmeta: {meta}\ncharts:\n{charts}", "spec.yaml")


STAT_A = "  - { id: a, type: stat, value: 1 }\n"
STAT_B = "  - { id: b, type: stat, value: 2 }\n"


def test_every_chart_renders_the_first_time() -> None:
    assert charts_to_render(None, spec(STAT_A + STAT_B), theme_changed=False) == ["a", "b"]


def test_unchanged_charts_do_not_render_again() -> None:
    before = spec(STAT_A + STAT_B)

    assert charts_to_render(before, spec(STAT_A + STAT_B), theme_changed=False) == []


def test_changed_and_new_charts_render() -> None:
    before = spec(STAT_A + STAT_B)
    after = spec(
        STAT_A + "  - { id: b, type: stat, value: 3 }\n  - { id: c, type: stat, value: 4 }\n"
    )

    assert charts_to_render(before, after, theme_changed=False) == ["b", "c"]


@pytest.mark.parametrize(("meta", "theme_changed"), [("{ theme: light }", False), ("{}", True)])
def test_a_meta_or_theme_change_renders_every_chart(meta: str, theme_changed: bool) -> None:
    before = spec(STAT_A + STAT_B)

    assert charts_to_render(before, spec(STAT_A + STAT_B, meta), theme_changed) == ["a", "b"]


def watch_errors(spec_path: Path, options: RenderOptions | None = None) -> list[VizreelError]:
    """Run watch_spec for one poll on a spec that fails before rendering."""
    errors: list[VizreelError] = []
    polls = iter([False, True])
    watch_spec(
        spec_path,
        options or RenderOptions(),
        on_render=lambda ids: pytest.fail(f"rendered {ids}"),
        on_result=lambda result: pytest.fail("rendered"),
        on_error=errors.append,
        on_wait=lambda: None,
        stop=lambda: next(polls),
        poll_seconds=0,
    )
    return errors


def test_an_invalid_spec_is_reported_and_watching_goes_on(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text("version: 1\ncharts: []\n", encoding="utf-8")

    [error] = watch_errors(spec_path)

    assert isinstance(error, SpecError)


def test_an_invalid_theme_is_reported(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(
        "version: 1\nmeta: { theme: brand.yaml }\ncharts: [{ id: a, type: stat, value: 1 }]\n",
        encoding="utf-8",
    )
    (tmp_path / "brand.yaml").write_text("colors: {}\n", encoding="utf-8")

    [error] = watch_errors(spec_path)

    assert isinstance(error, ThemeError)


def test_an_unknown_only_id_is_reported(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(
        "version: 1\ncharts: [{ id: a, type: stat, value: 1 }]\n", encoding="utf-8"
    )

    [error] = watch_errors(spec_path, RenderOptions(only=("nope",)))

    assert isinstance(error, RenderError)
