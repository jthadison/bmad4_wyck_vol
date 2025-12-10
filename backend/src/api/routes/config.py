"""
Configuration API routes.

Provides endpoints for retrieving and updating system configuration.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.config import SystemConfiguration
from src.repositories.config_repository import OptimisticLockError
from src.services.config_service import ConfigurationService
from src.services.impact_analysis_service import ImpactAnalysisService

router = APIRouter(prefix="/config", tags=["configuration"])


class ConfigUpdateRequest(BaseModel):
    """Request model for configuration update."""

    configuration: SystemConfiguration
    current_version: int


class StandardResponse(BaseModel):
    """Standard API response wrapper."""

    data: Any
    metadata: dict[str, Any] = {}


@router.get("", response_model=StandardResponse)
async def get_configuration(session: AsyncSession = Depends(get_db)) -> StandardResponse:
    """Get current system configuration.

    Returns:
        Current SystemConfiguration with metadata

    Example response:
        {
            "data": {
                "id": "uuid",
                "version": 5,
                "volume_thresholds": {...},
                "risk_limits": {...},
                "cause_factors": {...},
                "pattern_confidence": {...},
                "applied_at": "2025-12-09T13:00:00Z",
                "applied_by": "trader_001"
            },
            "metadata": {
                "last_modified_at": "2025-12-09T13:00:00Z",
                "version": 5,
                "modified_by": "trader_001"
            }
        }
    """
    service = ConfigurationService(session)
    config = await service.get_current_configuration()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No system configuration found"
        )

    return StandardResponse(
        data=config.model_dump(mode="json"),
        metadata={
            "last_modified_at": config.applied_at.isoformat(),
            "version": config.version,
            "modified_by": config.applied_by or "system",
        },
    )


@router.put("", response_model=StandardResponse)
async def update_configuration(
    request: ConfigUpdateRequest, session: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """Update system configuration with optimistic locking.

    Args:
        request: Configuration update request with current version

    Returns:
        Updated SystemConfiguration with new version

    Raises:
        409 Conflict: If version mismatch (concurrent update detected)
        422 Unprocessable Entity: If validation fails

    Example request:
        {
            "configuration": {
                "volume_thresholds": {...},
                "risk_limits": {...},
                "cause_factors": {...},
                "pattern_confidence": {...}
            },
            "current_version": 5
        }

    Example response:
        {
            "data": {
                "id": "uuid",
                "version": 6,
                ...
            },
            "metadata": {
                "last_modified_at": "2025-12-09T13:05:00Z",
                "version": 6,
                "modified_by": "trader_001"
            }
        }
    """
    service = ConfigurationService(session)

    try:
        updated_config = await service.update_configuration(
            config=request.configuration,
            current_version=request.current_version,
            applied_by=request.configuration.applied_by,
        )

        return StandardResponse(
            data=updated_config.model_dump(mode="json"),
            metadata={
                "last_modified_at": updated_config.applied_at.isoformat(),
                "version": updated_config.version,
                "modified_by": updated_config.applied_by or "system",
                "message": "Configuration updated successfully",
            },
        )

    except OptimisticLockError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "VERSION_CONFLICT",
                "message": str(e),
                "expected_version": request.current_version,
            },
        ) from e

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "VALIDATION_ERROR", "message": str(e)},
        ) from e


@router.post("/analyze-impact", response_model=StandardResponse)
async def analyze_configuration_impact(
    proposed_config: SystemConfiguration, session: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """Analyze impact of proposed configuration changes.

    Evaluates how proposed configuration would affect signal generation
    and performance based on historical pattern data (90 days).

    Args:
        proposed_config: Proposed system configuration to analyze

    Returns:
        ImpactAnalysisResult with metrics and recommendations

    Example request:
        {
            "volume_thresholds": {
                "spring_volume_min": "0.6",  # Lowered from 0.7
                ...
            },
            ...
        }

    Example response:
        {
            "data": {
                "signal_count_delta": 8,
                "current_signal_count": 45,
                "proposed_signal_count": 53,
                "current_win_rate": "0.72",
                "proposed_win_rate": "0.68",
                "win_rate_delta": "-0.04",
                "confidence_range": {"min": "0.65", "max": "0.71"},
                "recommendations": [
                    {
                        "severity": "WARNING",
                        "message": "Lowering spring volume threshold may increase false positives",
                        "category": "volume"
                    }
                ],
                "risk_impact": "No significant risk profile changes"
            },
            "metadata": {
                "analysis_period_days": 90,
                "patterns_evaluated": 900,
                "calculated_at": "2025-12-09T13:10:00Z"
            }
        }
    """
    config_service = ConfigurationService(session)
    impact_service = ImpactAnalysisService(session)

    # Get current configuration
    current_config = await config_service.get_current_configuration()

    if current_config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No current configuration found"
        )

    # Analyze impact
    impact_result = await impact_service.analyze_config_impact(
        current=current_config, proposed=proposed_config
    )

    return StandardResponse(
        data=impact_result.model_dump(mode="json"),
        metadata={
            "analysis_period_days": 90,
            "patterns_evaluated": impact_result.current_signal_count
            + impact_result.proposed_signal_count,
            "calculated_at": datetime.utcnow().isoformat() + "Z",
        },
    )


@router.get("/history", response_model=StandardResponse)
async def get_configuration_history(
    limit: int = 10, session: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """Get configuration change history.

    Args:
        limit: Maximum number of historical configurations to return (default: 10)

    Returns:
        List of historical SystemConfiguration objects

    Example response:
        {
            "data": [
                {"version": 6, ...},
                {"version": 5, ...},
                {"version": 4, ...}
            ],
            "metadata": {
                "count": 3,
                "limit": 10
            }
        }
    """
    service = ConfigurationService(session)
    history = await service.get_configuration_history(limit=limit)

    return StandardResponse(
        data=[config.model_dump(mode="json") for config in history],
        metadata={"count": len(history), "limit": limit},
    )
