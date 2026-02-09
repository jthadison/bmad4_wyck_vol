"""
Shared type conversion helpers for the phase_detection facade layer.

Provides mappings between facade types (PhaseType, PhaseEvent) and the
real implementation types (WyckoffPhase, PhaseEvents).
"""

from src.models.phase_classification import PhaseEvents, WyckoffPhase

from .types import EventType, PhaseEvent, PhaseType

# ============================================================================
# Type mapping: Facade PhaseType <-> Real WyckoffPhase
# ============================================================================

PHASE_TYPE_TO_WYCKOFF: dict[PhaseType, WyckoffPhase] = {
    PhaseType.A: WyckoffPhase.A,
    PhaseType.B: WyckoffPhase.B,
    PhaseType.C: WyckoffPhase.C,
    PhaseType.D: WyckoffPhase.D,
    PhaseType.E: WyckoffPhase.E,
}

WYCKOFF_TO_PHASE_TYPE: dict[WyckoffPhase, PhaseType] = {
    v: k for k, v in PHASE_TYPE_TO_WYCKOFF.items()
}


def events_to_phase_events(events: list[PhaseEvent]) -> PhaseEvents:
    """Convert facade PhaseEvent list to real PhaseEvents model.

    Maps each facade PhaseEvent by its EventType into the corresponding
    field on the real PhaseEvents Pydantic model. Confidence is converted
    from 0.0-1.0 (facade) to 0-100 (real).

    Args:
        events: List of facade PhaseEvent objects.

    Returns:
        PhaseEvents model populated with converted event dicts.
    """
    sc = None
    ar = None
    sts: list[dict] = []
    spring = None
    sos = None
    lps = None

    # Reserved keys that must not be overwritten by metadata
    _RESERVED_KEYS = {"bar_index", "confidence", "bar"}

    for event in events:
        event_dict: dict = {
            "bar_index": event.bar_index,
            "confidence": int(event.confidence * 100),  # Convert 0.0-1.0 to 0-100
            "bar": {
                "timestamp": event.timestamp.isoformat(),
                "close": event.price,
                "volume": event.volume,
            },
        }
        # Merge metadata, skipping reserved keys to prevent overwrite (m-3 fix)
        for k, v in event.metadata.items():
            if k not in _RESERVED_KEYS:
                event_dict[k] = v

        if event.event_type == EventType.SELLING_CLIMAX:
            sc = event_dict
        elif event.event_type == EventType.AUTOMATIC_RALLY:
            ar = event_dict
        elif event.event_type == EventType.SECONDARY_TEST:
            sts.append(event_dict)
        elif event.event_type == EventType.SPRING:
            spring = event_dict
        elif event.event_type == EventType.SIGN_OF_STRENGTH:
            sos = event_dict
        elif event.event_type == EventType.LAST_POINT_OF_SUPPORT:
            lps = event_dict

    return PhaseEvents(
        selling_climax=sc,
        automatic_rally=ar,
        secondary_tests=sts,
        spring=spring,
        sos_breakout=sos,
        last_point_of_support=lps,
    )
