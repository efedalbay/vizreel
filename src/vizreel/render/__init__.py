"""Rendering with Manim.

pydub, a Manim dependency, has regular expressions with invalid escape sequences. Python
reports them when it first compiles pydub, so a fresh install would print a screen of
warnings on its first render. They are harmless and not ours to fix, so they are hidden here,
before anything imports Manim. Python 3.12 reports them as SyntaxWarning, 3.11 as
DeprecationWarning.
"""

import warnings

for _category in (SyntaxWarning, DeprecationWarning):
    warnings.filterwarnings(
        "ignore",
        message="invalid escape sequence",
        category=_category,
        module=r".*[\\/]pydub[\\/]",
    )
