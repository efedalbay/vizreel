"""Re-render a spec whenever its files change."""

import dataclasses
import time
from collections.abc import Callable, Iterable
from pathlib import Path

from vizreel.errors import VizreelError
from vizreel.render.engine import ChartResult, RenderOptions, render_spec, select_charts
from vizreel.spec.loader import load_spec, spec_input_files
from vizreel.spec.models import Spec
from vizreel.themes.loader import load_theme, resolve_theme_path
from vizreel.themes.models import Theme

POLL_SECONDS = 0.25
"""How often the watched files are checked."""
SETTLE_SECONDS = 0.3
"""How long a changed file must stay unchanged before it is read.

Some editors save by deleting and rewriting a file, or write it in several steps; reading it
in the middle would report errors that are not really there.
"""

FileState = tuple[int, int] | None
"""A file's modification time in nanoseconds and its size, or None if it does not exist."""


def file_state(path: Path) -> FileState:
    """Return the modification time and size of a file, or None if it does not exist."""
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


class FileWatcher:
    """Tell when watched files have changed and then stayed unchanged for a moment.

    Args:
        paths: The files to watch.
        settle: Seconds a change must last before `poll` reports it.
        state: Returns the state of a file; replaceable in tests.
        clock: Returns the current time in seconds; replaceable in tests.
    """

    def __init__(
        self,
        paths: Iterable[Path],
        *,
        settle: float = SETTLE_SECONDS,
        state: Callable[[Path], FileState] = file_state,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settle = settle
        self._state = state
        self._clock = clock
        self._seen: dict[Path, FileState] = {path: state(path) for path in paths}
        self._changed_at: float | None = None

    @property
    def paths(self) -> list[Path]:
        """The watched files."""
        return list(self._seen)

    def watch(self, paths: Iterable[Path]) -> None:
        """Watch these files from now on. Files already watched keep their last state."""
        self._seen = {path: self._seen.get(path, self._state(path)) for path in paths}

    def poll(self) -> bool:
        """Return True once for each change, when it has settled and every file exists."""
        current = {path: self._state(path) for path in self._seen}
        if current != self._seen:
            self._seen = current
            self._changed_at = self._clock()
            return False
        if self._changed_at is None or self._clock() - self._changed_at < self._settle:
            return False
        if any(state is None for state in current.values()):
            return False
        self._changed_at = None
        return True


def charts_to_render(previous: Spec | None, spec: Spec, theme_changed: bool) -> list[str]:
    """Return the ids of the charts in `spec` that need rendering, in spec order.

    Every chart is rendered the first time, and when `meta` or the theme changed. Otherwise
    only the charts that are new or differ from the chart with the same id in `previous`.
    """
    if previous is None or theme_changed or previous.meta != spec.meta:
        return [chart.id for chart in spec.charts]
    before = {chart.id: chart for chart in previous.charts}
    return [chart.id for chart in spec.charts if before.get(chart.id) != chart]


def watch_spec(
    spec_path: Path,
    options: RenderOptions,
    *,
    on_render: Callable[[list[str]], None],
    on_result: Callable[[ChartResult], None],
    on_error: Callable[[VizreelError], None],
    on_wait: Callable[[], None],
    stop: Callable[[], bool] = lambda: False,
    poll_seconds: float = POLL_SECONDS,
    watcher: FileWatcher | None = None,
) -> None:
    """Render a spec, then render it again whenever it, its theme file or a data file changes.

    Runs until `stop` returns True or the user presses Ctrl+C (KeyboardInterrupt). A spec or
    theme that cannot be loaded is reported and watching goes on; the next render compares
    against the last spec that loaded.

    Args:
        spec_path: The spec file.
        options: As for `render_spec`. `options.only` limits which charts ever render.
        on_render: Called with the ids of the charts about to render; empty when a change
            affects no chart.
        on_result: Called after each chart, with its result.
        on_error: Called when the spec or theme cannot be loaded or rendering cannot start.
        on_wait: Called when watching resumes after a render or an error.
        stop: Checked between polls; watching ends when it returns True.
        poll_seconds: Time between checks of the files.
        watcher: The file watcher to use; replaceable in tests.
    """
    watcher = watcher or FileWatcher([spec_path])
    session = _Session(spec_path, options, watcher)
    session.render(on_render, on_result, on_error)
    on_wait()
    while not stop():
        time.sleep(poll_seconds)
        if watcher.poll():
            session.render(on_render, on_result, on_error)
            on_wait()


@dataclasses.dataclass
class _Session:
    """What watching remembers between renders."""

    spec_path: Path
    options: RenderOptions
    watcher: FileWatcher
    spec: Spec | None = None
    theme: Theme | None = None
    failed: set[str] = dataclasses.field(default_factory=set)

    def render(
        self,
        on_render: Callable[[list[str]], None],
        on_result: Callable[[ChartResult], None],
        on_error: Callable[[VizreelError], None],
    ) -> None:
        data_files = spec_input_files(self.spec_path)
        try:
            spec = load_spec(self.spec_path)
            theme_path = resolve_theme_path(spec.meta.theme, self.spec_path.parent)
            self.watcher.watch([self.spec_path, theme_path, *data_files])
            theme = load_theme(spec.meta.theme, self.spec_path.parent)
            select_charts(spec, self.options.only)
        except VizreelError as exc:
            # A file that is gone would keep the watcher waiting; the spec itself may be
            # in the middle of being saved.
            kept = [path for path in self.watcher.paths if path == self.spec_path or path.exists()]
            self.watcher.watch(dict.fromkeys([*kept, *data_files]))
            on_error(exc)
            return
        wanted = charts_to_render(self.spec, spec, theme != self.theme)
        ids = [
            chart.id
            for chart in spec.charts
            if (chart.id in wanted or chart.id in self.failed)
            and (not self.options.only or chart.id in self.options.only)
        ]
        self.spec, self.theme = spec, theme
        on_render(ids)
        if not ids:
            return
        try:
            results = render_spec(
                self.spec_path,
                dataclasses.replace(self.options, only=tuple(ids)),
                on_done=on_result,
            )
        except VizreelError as exc:
            self.failed.update(ids)
            on_error(exc)
            return
        self.failed = {result.chart_id for result in results if result.error}
