"""Unit tests for AI series lookup module."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.library_tracker.ai_series import async_ai_series_lookup


@pytest.fixture
def mock_hass() -> HomeAssistant:
    """Fixture for a mock HomeAssistant core object."""
    return MagicMock(spec=HomeAssistant)


@pytest.mark.asyncio
async def test_async_ai_series_lookup_success(mock_hass: HomeAssistant) -> None:
    """Test successful AI series lookup with structured response."""
    fake_ai_task = MagicMock()
    fake_ai_task.async_generate_data = AsyncMock(
        return_value={
            "is_series": True,
            "series_name": "Der Herr der Ringe",
            "books": [
                {"title": "Die Gefährten", "order": 1},
                {"title": "Die zwei Türme", "order": 2},
                {"title": "Die Rückkehr des Königs", "order": 3},
            ],
        }
    )

    with patch.dict(sys.modules, {"homeassistant.components.ai_task": fake_ai_task}):
        result = await async_ai_series_lookup(mock_hass, "Die Gefährten", "J.R.R. Tolkien")

    assert result is not None
    assert result["is_series"] is True
    assert result["series_name"] == "Der Herr der Ringe"
    assert len(result["books"]) == 3
    assert result["books"][0] == {"title": "Die Gefährten", "order": 1}

    fake_ai_task.async_generate_data.assert_called_once()
    call_kwargs = fake_ai_task.async_generate_data.call_args.kwargs
    assert call_kwargs["task_name"] == "library_tracker_series_lookup"
    assert "Die Gefährten" in call_kwargs["instructions"]
    assert "J.R.R. Tolkien" in call_kwargs["instructions"]


@pytest.mark.asyncio
async def test_async_ai_series_lookup_not_a_series(mock_hass: HomeAssistant) -> None:
    """Test AI lookup returning is_series: False for a standalone book."""
    fake_ai_task = MagicMock()
    fake_ai_task.async_generate_data = AsyncMock(
        return_value={
            "is_series": False,
            "series_name": None,
            "books": [],
        }
    )

    with patch.dict(sys.modules, {"homeassistant.components.ai_task": fake_ai_task}):
        result = await async_ai_series_lookup(mock_hass, "Einzelband Titel", "Autor Name")

    assert result is not None
    assert result["is_series"] is False
    assert result["series_name"] is None
    assert result["books"] == []


@pytest.mark.asyncio
async def test_async_ai_series_lookup_ai_task_error(mock_hass: HomeAssistant) -> None:
    """Test handling of HomeAssistantError during AI task execution."""
    fake_ai_task = MagicMock()
    fake_ai_task.async_generate_data = AsyncMock(
        side_effect=Exception("AI task provider error")
    )

    with patch.dict(sys.modules, {"homeassistant.components.ai_task": fake_ai_task}):
        result = await async_ai_series_lookup(mock_hass, "Test Buch", "Test Autor")

    assert result is None


@pytest.mark.asyncio
async def test_async_ai_series_lookup_missing_ai_task_module(mock_hass: HomeAssistant) -> None:
    """Test graceful handling when ai_task module is not available in HA."""
    with patch.dict(sys.modules, {"homeassistant.components.ai_task": None}):
        result = await async_ai_series_lookup(mock_hass, "Test Buch", "Test Autor")

    assert result is None
