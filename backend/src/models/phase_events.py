"""
Phase Events data structure for Wyckoff phase confidence scoring.

⚠️ DEPRECATED: This module is deprecated as of Story 4.8.
Use src.models.phase_classification.PhaseEvents instead.

Migration Path:
    OLD (deprecated):
        from src.models.phase_events import PhaseEvents
        events = PhaseEvents(sc=sc, ar=ar, st_list=[st1, st2])

    NEW (canonical):
        from src.models.phase_classification import PhaseEvents
        events = PhaseEvents(
            selling_climax=sc.model_dump(),
            automatic_rally=ar.model_dump(),
            secondary_tests=[st1.model_dump(), st2.model_dump()]
        )

Container for all detected Wyckoff events (SC, AR, ST, Spring, SOS, LPS)
used in phase classification and confidence scoring (Story 4.5).

Events are optional because not all phases require all events:
- Phase A: requires SC + AR
- Phase B: requires Phase A + 1+ ST
- Phase C: requires Phase B + Spring
- Phase D: requires SOS (optionally LPS)
- Phase E: requires Phase D + continuation
"""

import warnings

# Issue deprecation warning on module import
warnings.warn(
    "src.models.phase_events is deprecated. "
    "Use src.models.phase_classification.PhaseEvents instead. "
    "See module docstring for migration path.",
    DeprecationWarning,
    stacklevel=2,
)

from typing import Any, Optional

from pydantic import BaseModel, Field

from src.models.automatic_rally import AutomaticRally
from src.models.secondary_test import SecondaryTest
from src.models.selling_climax import SellingClimax


class PhaseEvents(BaseModel):
    """
    Container for all detected Wyckoff events used in phase confidence scoring.

    Events are optional because not all phases require all events.
    Phase A: requires SC + AR
    Phase B: requires Phase A + 1+ ST
    Phase C: requires Phase B + Spring
    Phase D: requires SOS (optionally LPS)
    Phase E: requires Phase D + continuation

    Attributes:
        sc: Selling Climax (Phase A)
        ar: Automatic Rally (Phase A)
        st_list: List of Secondary Tests (Phase B, can be multiple)
        spring: Spring (Phase C, from Epic 5)
        sos: Sign of Strength (Phase D, from Epic 5)
        lps: Last Point of Support (Phase D, from Epic 5)

    Example:
        >>> events = PhaseEvents(
        ...     sc=detected_sc,
        ...     ar=detected_ar,
        ...     st_list=[st1, st2]
        ... )
        >>> print(f"Phase A complete: {events.has_phase_a()}")
        >>> print(f"Phase B complete: {events.has_phase_b()}")
        >>> print(f"ST count: {events.get_st_count()}")
    """

    # Phase A events
    sc: Optional[SellingClimax] = Field(
        None, description="Selling Climax marking Phase A beginning"
    )
    ar: Optional[AutomaticRally] = Field(
        None, description="Automatic Rally marking Phase A completion"
    )

    # Phase B events
    st_list: list[SecondaryTest] = Field(
        default_factory=list, description="Secondary Tests (Phase B cause building)"
    )

    # Phase C events (from Epic 5)
    spring: Optional[Any] = Field(None, description="Spring (final test, from Epic 5)")

    # Phase D events (from Epic 5)
    sos: Optional[Any] = Field(None, description="Sign of Strength (breakout, from Epic 5)")
    lps: Optional[Any] = Field(None, description="Last Point of Support (pullback, from Epic 5)")

    def has_phase_a(self) -> bool:
        """
        Check if Phase A events are complete (SC + AR).

        Returns:
            bool: True if both SC and AR are present, False otherwise

        Example:
            >>> events = PhaseEvents(sc=detected_sc, ar=detected_ar)
            >>> events.has_phase_a()
            True
        """
        return self.sc is not None and self.ar is not None

    def has_phase_b(self) -> bool:
        """
        Check if Phase B events are complete (Phase A + 1+ ST).

        Returns:
            bool: True if Phase A is complete and at least 1 ST detected

        Example:
            >>> events = PhaseEvents(sc=sc, ar=ar, st_list=[st1])
            >>> events.has_phase_b()
            True
        """
        return self.has_phase_a() and len(self.st_list) > 0

    def has_phase_c(self) -> bool:
        """
        Check if Phase C events are complete (Phase B + Spring).

        Returns:
            bool: True if Phase B is complete and Spring is present

        Example:
            >>> events = PhaseEvents(sc=sc, ar=ar, st_list=[st1], spring=spring)
            >>> events.has_phase_c()
            True
        """
        return self.has_phase_b() and self.spring is not None

    def has_phase_d(self) -> bool:
        """
        Check if Phase D events are present (SOS).

        Phase D is defined by Sign of Strength (SOS) breaking above Ice.
        LPS is optional confirmation but not required.

        Returns:
            bool: True if SOS is present

        Example:
            >>> events = PhaseEvents(sos=sos)
            >>> events.has_phase_d()
            True
        """
        return self.sos is not None

    def get_st_count(self) -> int:
        """
        Get count of Secondary Tests.

        Returns:
            int: Number of STs detected (0 if none)

        Example:
            >>> events = PhaseEvents(st_list=[st1, st2, st3])
            >>> events.get_st_count()
            3
        """
        return len(self.st_list)

    class Config:
        """Pydantic model configuration."""

        # Allow Any type for future Epic 5 models (Spring, SOS, LPS)
        arbitrary_types_allowed = True
