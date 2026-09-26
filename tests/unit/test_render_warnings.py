import importlib
import warnings
from pathlib import Path

import vizreel.render

INVALID_ESCAPE = "pattern = '\\('\n"


def syntax_warnings(filename: Path) -> list[warnings.WarningMessage]:
    with warnings.catch_warnings(record=True) as caught:
        # pytest restores the warning filters after collecting tests, so the filter that the
        # package added on import is gone; importing it again adds it inside this block.
        importlib.reload(vizreel.render)
        compile(INVALID_ESCAPE, str(filename), "exec")
    return [w for w in caught if issubclass(w.category, SyntaxWarning)]


def test_pydub_escape_warnings_are_hidden(tmp_path: Path) -> None:
    assert syntax_warnings(tmp_path / "site-packages" / "pydub" / "utils.py") == []


def test_other_escape_warnings_are_still_shown(tmp_path: Path) -> None:
    assert len(syntax_warnings(tmp_path / "mine.py")) == 1
