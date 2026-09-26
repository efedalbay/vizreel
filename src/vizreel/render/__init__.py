"""Rendering with Manim.

pydub, a Manim dependency, has regular expressions with invalid escape sequences. Python
reports them when it first compiles pydub, so a fresh install would print a screen of
warnings on its first render. They are harmless and not ours to fix, so they are hidden here,
before anything imports Manim.
"""

import warnings

warnings.filterwarnings(
    "ignore",
    message="invalid escape sequence",
    category=SyntaxWarning,
    module=r".*[\\/]pydub[\\/]",
)
