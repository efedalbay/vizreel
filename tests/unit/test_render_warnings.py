import importlib
import warnings
from pathlib import Path

import vizreel.render

INVALID_ESCAPE = "pattern = '\\('\n"


def escape_warnings(filename: Path) -> list[warnings.WarningMessage]:
    """Compile code with an invalid escape sequence and return the warnings about it.

    Python 3.12 reports it as SyntaxWarning, 3.11 as DeprecationWarning, which is hidden by
    default; every warning is shown here except the ones vizreel's filter hides.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # pytest restores the warning filters after collecting tests, so the filter that the
        # package added on import is gone; importing it again adds it inside this block.
        importlib.reload(vizreel.render)
        compile(INVALID_ESCAPE, str(filename), "exec")
    return [w for w in caught if "invalid escape sequence" in str(w.message)]


def test_pydub_escape_warnings_are_hidden(tmp_path: Path) -> None:
    assert escape_warnings(tmp_path / "site-packages" / "pydub" / "utils.py") == []


def test_other_escape_warnings_are_still_shown(tmp_path: Path) -> None:
    assert len(escape_warnings(tmp_path / "mine.py")) == 1
