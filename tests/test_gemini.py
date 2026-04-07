import json
from unittest.mock import MagicMock, patch

import pytest

from gemini_client import GeminiClient, _extract_json, _normalize_percentages


def test_extract_json_valid():
    """Test extracting JSON from a marked-down string."""
    input_str = """```json
{
  "metal": 50,
  "non_metal": 45,
  "background": 5
}
```"""
    result = _extract_json(input_str)
    assert result == {"metal": 50, "non_metal": 45, "background": 5}


def test_extract_json_no_json():
    """Test extracting JSON from a string without valid JSON."""
    with pytest.raises(ValueError):
        _extract_json("This string has no JSON object.")


def test_normalize_percentages():
    """Test normalizing percentages so they sum to 100."""
    input_data = {"metal": 10, "non_metal": 10, "background": 0}
    # It should scale them to sum to 100
    res = _normalize_percentages(input_data)
    assert res["metal"] == 50.0
    assert res["non_metal"] == 50.0
    assert res["background"] == 0.0


def test_client_exhaustion():
    """Test the GeminiClient falls back cleanly on repeated errors."""
    client = GeminiClient(api_key="fake", models=["model1", "model2"])
    
    # Mock the internal call to always raise a rate limit error
    with patch.object(client, "_call_model", side_effect=Exception("429 Resource Exhausted")):
        res = client.analyze_image(MagicMock())  # pass a mock image
    
    assert not res.is_valid
    assert "exhausted" in res.error
