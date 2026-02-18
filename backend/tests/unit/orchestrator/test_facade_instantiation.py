"""
Smoke tests for MasterOrchestratorFacade instantiation.

Story 23.2: Ensures the facade constructor doesn't crash when
building the pipeline coordinator with all 7 stages.
"""


def test_facade_can_instantiate():
    """Smoke test: facade instantiates without TypeError (P0 fix)."""
    from src.orchestrator.orchestrator_facade import MasterOrchestratorFacade

    facade = MasterOrchestratorFacade()
    assert facade is not None


def test_facade_health_reports_healthy():
    """Facade health check returns healthy status after instantiation."""
    from src.orchestrator.orchestrator_facade import MasterOrchestratorFacade

    facade = MasterOrchestratorFacade()
    health = facade.get_health()
    assert health["status"] == "healthy"


def test_facade_coordinator_has_seven_stages():
    """Facade builds coordinator with all 7 pipeline stages."""
    from src.orchestrator.orchestrator_facade import MasterOrchestratorFacade

    facade = MasterOrchestratorFacade()
    stages = facade._coordinator._stages
    assert len(stages) == 7

    stage_names = [s.name for s in stages]
    assert "volume_analysis" in stage_names
    assert "range_detection" in stage_names
    assert "phase_detection" in stage_names
    assert "pattern_detection" in stage_names
    assert "validation" in stage_names
    assert "signal_generation" in stage_names
    assert "risk_assessment" in stage_names


def test_service_get_orchestrator_returns_facade():
    """Service layer returns MasterOrchestratorFacade, not old MasterOrchestrator."""
    from src.orchestrator.orchestrator_facade import MasterOrchestratorFacade
    from src.orchestrator.service import get_orchestrator, reset_orchestrator

    # Reset to get a fresh instance
    reset_orchestrator()
    try:
        orchestrator = get_orchestrator()
        assert isinstance(orchestrator, MasterOrchestratorFacade)
    finally:
        reset_orchestrator()
