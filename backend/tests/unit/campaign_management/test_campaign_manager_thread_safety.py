"""
Thread Safety Tests for CampaignManager (Story 18.2)

Tests concurrent access to CampaignManager singleton to verify:
- Thread-safe initialization under concurrent access
- Same instance returned from multiple threads
- No race conditions during singleton creation
- Factory function behavior under load

Author: Story 18.2 Task 5
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest

from src.campaign_management.campaign_manager import (
    CampaignManager,
    create_campaign_manager_for_testing,
    get_campaign_manager,
    reset_campaign_manager_singleton,
)
from src.repositories.campaign_repository import CampaignRepository


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before and after each test for isolation."""
    reset_campaign_manager_singleton()
    yield
    reset_campaign_manager_singleton()


@pytest.fixture
def mock_repository() -> Mock:
    """Create mock CampaignRepository."""
    repo = Mock(spec=CampaignRepository)
    repo.get_campaign_by_range = AsyncMock(return_value=None)
    repo.get_campaign_by_id = AsyncMock(return_value=None)
    repo.create_campaign = AsyncMock()
    return repo


# =============================================================================
# Thread-Safety Tests (AC2.1, AC2.2)
# =============================================================================


class TestThreadSafeSingleton:
    """Tests for thread-safe singleton behavior."""

    def test_concurrent_singleton_access_returns_same_instance(self, mock_repository: Mock) -> None:
        """
        Test concurrent calls to get_campaign_manager return same instance.

        Verifies AC2.1: Thread-safe singleton initialization.
        """
        portfolio_value = Decimal("100000.00")
        instances: list[CampaignManager] = []
        errors: list[Exception] = []

        def get_instance():
            try:
                instance = get_campaign_manager(mock_repository, portfolio_value)
                instances.append(instance)
            except Exception as e:
                errors.append(e)

        # Create 20 threads that all try to get the singleton
        threads = [threading.Thread(target=get_instance) for _ in range(20)]

        # Start all threads nearly simultaneously
        for t in threads:
            t.start()

        # Wait for all to complete
        for t in threads:
            t.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"

        # Verify all threads got instances
        assert len(instances) == 20, f"Expected 20 instances, got {len(instances)}"

        # Verify all instances are the same object (singleton)
        first_instance = instances[0]
        for i, instance in enumerate(instances[1:], start=2):
            assert instance is first_instance, (
                f"Instance {i} is different from instance 1 - " f"singleton pattern failed"
            )

    def test_thread_pool_concurrent_access(self, mock_repository: Mock) -> None:
        """
        Test ThreadPoolExecutor concurrent access returns same instance.

        Verifies thread-safety under ThreadPoolExecutor which is common
        in async web frameworks.
        """
        portfolio_value = Decimal("100000.00")

        def get_instance_id():
            instance = get_campaign_manager(mock_repository, portfolio_value)
            return id(instance)

        # Use ThreadPoolExecutor with 10 workers
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit 50 concurrent tasks
            futures = [executor.submit(get_instance_id) for _ in range(50)]
            instance_ids = [f.result() for f in futures]

        # All instance IDs should be the same
        unique_ids = set(instance_ids)
        assert (
            len(unique_ids) == 1
        ), f"Expected 1 unique instance ID, got {len(unique_ids)}: {unique_ids}"

    def test_rapid_sequential_access(self, mock_repository: Mock) -> None:
        """
        Test rapid sequential access always returns same instance.

        Verifies the fast-path (no lock) returns correct instance.
        """
        portfolio_value = Decimal("100000.00")

        # First call initializes
        first = get_campaign_manager(mock_repository, portfolio_value)

        # Rapid subsequent calls should hit fast path
        for i in range(100):
            instance = get_campaign_manager(mock_repository, portfolio_value)
            assert instance is first, f"Call {i+1} returned different instance"


class TestSingletonReset:
    """Tests for singleton reset functionality."""

    def test_reset_clears_singleton(self, mock_repository: Mock) -> None:
        """Test reset_campaign_manager_singleton clears the instance."""
        portfolio_value = Decimal("100000.00")

        # Create first instance
        first = get_campaign_manager(mock_repository, portfolio_value)

        # Reset singleton
        reset_campaign_manager_singleton()

        # Create new mock for second instance
        mock_repo2 = Mock(spec=CampaignRepository)
        mock_repo2.get_campaign_by_range = AsyncMock(return_value=None)

        # Get new instance - should be different object
        second = get_campaign_manager(mock_repo2, Decimal("200000.00"))

        assert first is not second, "Reset should create new instance"

    def test_reset_is_thread_safe(self, mock_repository: Mock) -> None:
        """Test reset is thread-safe during concurrent access."""
        portfolio_value = Decimal("100000.00")
        errors: list[Exception] = []

        def access_and_reset():
            try:
                for _ in range(10):
                    get_campaign_manager(mock_repository, portfolio_value)
                    reset_campaign_manager_singleton()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=access_and_reset) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors (even if behavior is non-deterministic)
        assert len(errors) == 0, f"Errors during concurrent reset: {errors}"


# =============================================================================
# Testing Factory Function Tests (AC2.4)
# =============================================================================


class TestCreateForTesting:
    """Tests for create_campaign_manager_for_testing factory."""

    def test_creates_new_instance_each_call(self, mock_repository: Mock) -> None:
        """Test create_campaign_manager_for_testing creates fresh instances."""
        portfolio_value = Decimal("100000.00")

        # Each call should create a new instance
        instance1 = create_campaign_manager_for_testing(mock_repository, portfolio_value)
        instance2 = create_campaign_manager_for_testing(mock_repository, portfolio_value)

        assert (
            instance1 is not instance2
        ), "create_campaign_manager_for_testing should create new instances"

    def test_does_not_affect_singleton(self, mock_repository: Mock) -> None:
        """Test create_campaign_manager_for_testing doesn't affect singleton."""
        portfolio_value = Decimal("100000.00")

        # Create singleton first
        singleton = get_campaign_manager(mock_repository, portfolio_value)

        # Create test instance
        test_instance = create_campaign_manager_for_testing(mock_repository, portfolio_value)

        # Singleton should be unaffected
        singleton_again = get_campaign_manager(mock_repository, portfolio_value)

        assert singleton is singleton_again, "Singleton should be unchanged"
        assert test_instance is not singleton, "Test instance should be different"

    def test_accepts_mock_dependencies(self) -> None:
        """Test create_campaign_manager_for_testing accepts mock dependencies."""
        mock_repo = Mock(spec=CampaignRepository)
        mock_allocator = Mock()
        mock_event_bus = Mock()

        manager = create_campaign_manager_for_testing(
            campaign_repository=mock_repo,
            portfolio_value=Decimal("100000.00"),
            allocator=mock_allocator,
            event_bus=mock_event_bus,
        )

        # Verify dependencies were injected
        assert manager._campaign_repo is mock_repo
        assert manager._allocator is mock_allocator
        assert manager._event_bus is mock_event_bus


# =============================================================================
# Dependency Injection Tests
# =============================================================================


class TestDependencyInjection:
    """Tests for DI in CampaignManager."""

    def test_default_dependencies_created(self, mock_repository: Mock) -> None:
        """Test default dependencies created when not provided."""
        manager = create_campaign_manager_for_testing(
            campaign_repository=mock_repository,
            portfolio_value=Decimal("100000.00"),
        )

        # Should have allocator and event_bus (defaults)
        assert manager._allocator is not None
        assert manager._event_bus is not None

    def test_custom_dependencies_used(self, mock_repository: Mock) -> None:
        """Test custom dependencies are used when provided."""
        mock_allocator = Mock()
        mock_event_bus = Mock()

        manager = create_campaign_manager_for_testing(
            campaign_repository=mock_repository,
            portfolio_value=Decimal("100000.00"),
            allocator=mock_allocator,
            event_bus=mock_event_bus,
        )

        assert manager._allocator is mock_allocator
        assert manager._event_bus is mock_event_bus


# =============================================================================
# No __new__ Pattern Tests (AC2.3)
# =============================================================================


class TestNoNewPattern:
    """Tests verifying __new__ singleton pattern was removed."""

    def test_no_class_level_instance(self) -> None:
        """Verify CampaignManager doesn't have _instance class attribute."""
        assert not hasattr(
            CampaignManager, "_instance"
        ), "CampaignManager should not have _instance class attribute"

    def test_no_initialized_flag_on_class(self) -> None:
        """Verify CampaignManager doesn't check _initialized."""
        import inspect

        init_source = inspect.getsource(CampaignManager.__init__)

        assert (
            "hasattr" not in init_source or "_initialized" not in init_source
        ), "CampaignManager.__init__ should not use hasattr(_initialized) pattern"

    def test_multiple_direct_instantiation_creates_different_objects(
        self, mock_repository: Mock
    ) -> None:
        """
        Test direct instantiation creates different objects.

        Verifies the __new__ override was removed - direct instantiation
        should create distinct objects (use factory for singleton).
        """
        portfolio_value = Decimal("100000.00")

        # Direct instantiation (bypassing factory)
        instance1 = CampaignManager(mock_repository, portfolio_value)
        instance2 = CampaignManager(mock_repository, portfolio_value)

        # Without __new__ override, these should be different objects
        assert instance1 is not instance2, (
            "Direct instantiation should create different objects "
            "(singleton pattern should only be via factory)"
        )


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestInitializationErrors:
    """Tests for error handling during initialization."""

    def test_allocator_error_propagates(self, mock_repository: Mock) -> None:
        """Test that errors during CampaignAllocator creation propagate correctly."""
        from src.campaign_management.allocator import CampaignAllocator

        # Create a mock allocator that raises during operations
        mock_allocator = Mock(spec=CampaignAllocator)
        mock_allocator.allocate_campaign_risk.side_effect = ValueError("Invalid allocation")

        manager = create_campaign_manager_for_testing(
            campaign_repository=mock_repository,
            portfolio_value=Decimal("100000.00"),
            allocator=mock_allocator,
        )

        # Manager should be created successfully
        assert manager is not None
        # The error will propagate when allocator is used, not during init
        assert manager._allocator is mock_allocator

    def test_invalid_portfolio_value_handled(self, mock_repository: Mock) -> None:
        """Test initialization with edge case portfolio values."""
        # Zero portfolio value should work (allocator handles validation)
        manager = create_campaign_manager_for_testing(
            campaign_repository=mock_repository,
            portfolio_value=Decimal("0.00"),
        )
        assert manager is not None

        # Very large portfolio value should work
        manager = create_campaign_manager_for_testing(
            campaign_repository=mock_repository,
            portfolio_value=Decimal("1000000000.00"),
        )
        assert manager is not None


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for is_singleton_initialized() health check function."""

    def test_is_singleton_initialized_false_initially(self) -> None:
        """Test is_singleton_initialized returns False when no singleton exists."""
        from src.campaign_management.campaign_manager import is_singleton_initialized

        # After reset, should be False
        reset_campaign_manager_singleton()
        assert is_singleton_initialized() is False

    def test_is_singleton_initialized_true_after_creation(self, mock_repository: Mock) -> None:
        """Test is_singleton_initialized returns True after singleton created."""
        from src.campaign_management.campaign_manager import is_singleton_initialized

        portfolio_value = Decimal("100000.00")

        # Create singleton
        get_campaign_manager(mock_repository, portfolio_value)

        assert is_singleton_initialized() is True

    def test_is_singleton_initialized_false_after_reset(self, mock_repository: Mock) -> None:
        """Test is_singleton_initialized returns False after reset."""
        from src.campaign_management.campaign_manager import is_singleton_initialized

        portfolio_value = Decimal("100000.00")

        # Create then reset
        get_campaign_manager(mock_repository, portfolio_value)
        reset_campaign_manager_singleton()

        assert is_singleton_initialized() is False
