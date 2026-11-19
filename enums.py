"""
Fixed value sets that used to be scattered through the code as plain strings.

A typo such as "maneger" or "wonn" used to be accepted silently and produced a
record that matched no filter. Now such values are rejected by Pydantic on input.

How they are applied:
  * request schemas (Create/Update) accept only enum values;
  * response schemas keep a plain ``str``.
That is deliberate: if the database contains a value from an older version
that is no longer in the enum, reading the record still works instead of
failing with a 500.
"""
from enum import Enum


class Role(str, Enum):
    """Role of an employee in the system."""

    ADMIN = "admin"
    MANAGER = "manager"


class ClientStatus(str, Enum):
    """Stage of the relationship with a client."""

    NEW = "new"
    IN_PROGRESS = "in_progress"
    REGULAR = "regular"
    REJECTED = "rejected"


class DealStage(str, Enum):
    """
    Stage of a deal in the sales pipeline.

    WON and LOST are closed stages; without them the pipeline conversion
    could not be calculated because won and lost deals looked the same.
    """

    NEW = "new"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"

    @property
    def is_closed(self) -> bool:
        """The deal is finished, no matter how."""
        return self in (DealStage.WON, DealStage.LOST)

    @property
    def is_won(self) -> bool:
        return self is DealStage.WON


# Order of the pipeline columns in reports and in the UI.
PIPELINE_ORDER = [stage.value for stage in DealStage]


def stage_flags(stage: str) -> tuple[bool, bool]:
    """
    ``(is_won, is_closed)`` for a stage read from the database.

    The value may be anything, including leftovers from older versions or rows
    written outside the API. An unknown stage counts as open, not as won: the
    report then underestimates the conversion instead of overestimating it.
    """
    try:
        known = DealStage(stage)
    except ValueError:
        return False, False
    return known.is_won, known.is_closed
