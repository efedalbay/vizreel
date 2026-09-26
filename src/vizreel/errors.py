"""Expected failures. Each carries a message a user can act on."""

from dataclasses import dataclass


class VizreelError(Exception):
    """Base class for every expected failure in vizreel."""


@dataclass(frozen=True)
class SpecIssue:
    """One problem found in a spec file.

    Attributes:
        location: Path to the offending field, e.g. ``charts[1].series[0].values``.
            Empty for problems with the file as a whole.
        message: What is wrong and, where possible, how to fix it.
    """

    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.location}: {self.message}" if self.location else self.message


class SpecError(VizreelError):
    """A spec file could not be read or is not valid.

    Attributes:
        source: Name of the spec file, as shown to the user.
        issues: Every problem found, in document order.
    """

    def __init__(self, source: str, issues: list[SpecIssue]) -> None:
        self.source = source
        self.issues = issues
        count = len(issues)
        noun = "error" if count == 1 else "errors"
        super().__init__(f"{source}: {count} {noun}")
