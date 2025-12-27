"""
Tests for Main Module
Tests retry logic and game execution helpers.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Set environment variable before importing
os.environ["CREWAI_TRACING_ENABLED"] = "false"

from clue_game.main import retry_with_backoff, get_error_details


class TestGetErrorDetails:
    """Test the get_error_details function."""
    
    def test_basic_exception(self):
        """Should extract type and message from basic exception."""
        exc = ValueError("Something went wrong")
        details = get_error_details(exc)
        
        assert "Type: ValueError" in details
        assert "Message: Something went wrong" in details
    
    def test_exception_with_cause(self):
        """Should include cause information when present."""
        try:
            try:
                raise ConnectionError("Network failed")
            except ConnectionError as e:
                raise ValueError("LLM call failed") from e
        except ValueError as exc:
            details = get_error_details(exc)
        
        assert "Type: ValueError" in details
        assert "Caused by: ConnectionError" in details
    
    def test_exception_with_status_code(self):
        """Should include status code when present."""
        exc = Exception("API error")
        exc.status_code = 429
        details = get_error_details(exc)
        
        assert "Status Code: 429" in details
    
    def test_exception_with_response(self):
        """Should include response details when present."""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        # Ensure candidates is not iterable to avoid Gemini-specific handling
        mock_response.candidates = None
        
        exc = Exception("API error")
        exc.response = mock_response
        details = get_error_details(exc)
        
        assert "Response Status: 503" in details
        assert "Response Body: Service Unavailable" in details
    
    def test_exception_with_error_code(self):
        """Should include error code when present."""
        exc = Exception("API error")
        exc.code = "RATE_LIMIT_EXCEEDED"
        details = get_error_details(exc)
        
        assert "Error Code: RATE_LIMIT_EXCEEDED" in details
    
    def test_exception_with_error_details(self):
        """Should include error details attribute when present."""
        exc = Exception("API error")
        exc.error = {"message": "Quota exceeded", "retry_after": 60}
        details = get_error_details(exc)
        
        assert "Error Details:" in details
        assert "Quota exceeded" in details
    
    def test_long_response_text_truncated(self):
        """Should truncate long response text."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "A" * 1000  # Very long text
        # Ensure candidates is not iterable to avoid Gemini-specific handling
        mock_response.candidates = None
        
        exc = Exception("API error")
        exc.response = mock_response
        details = get_error_details(exc)
        
        # Should be truncated to 500 chars
        assert len(details) < 1000


class TestRetryWithBackoff:
    """Test the retry_with_backoff function."""
    
    def test_success_on_first_attempt(self):
        """Should return result immediately if function succeeds."""
        mock_func = Mock(return_value="success")
        
        result = retry_with_backoff(mock_func, max_retries=3, base_delay=0.01)
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_success_on_second_attempt(self):
        """Should retry and succeed on second attempt."""
        mock_func = Mock(side_effect=[Exception("First fail"), "success"])
        
        result = retry_with_backoff(mock_func, max_retries=3, base_delay=0.01)
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    def test_success_on_third_attempt(self):
        """Should retry and succeed on third attempt."""
        mock_func = Mock(side_effect=[
            Exception("First fail"),
            Exception("Second fail"),
            "success"
        ])
        
        result = retry_with_backoff(mock_func, max_retries=3, base_delay=0.01)
        
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_all_retries_exhausted(self):
        """Should raise last exception after all retries fail."""
        mock_func = Mock(side_effect=Exception("Always fails"))
        
        with pytest.raises(Exception, match="Always fails"):
            retry_with_backoff(mock_func, max_retries=3, base_delay=0.01)
        
        # Initial attempt + 3 retries = 4 calls
        assert mock_func.call_count == 4
    
    def test_none_response_triggers_retry(self):
        """Should retry if function returns None."""
        mock_func = Mock(side_effect=[None, "success"])
        
        result = retry_with_backoff(mock_func, max_retries=3, base_delay=0.01)
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    def test_empty_raw_response_triggers_retry(self):
        """Should retry if response has empty raw attribute."""
        empty_response = Mock()
        empty_response.raw = ""
        
        valid_response = Mock()
        valid_response.raw = "valid content"
        
        mock_func = Mock(side_effect=[empty_response, valid_response])
        
        result = retry_with_backoff(mock_func, max_retries=3, base_delay=0.01)
        
        assert result == valid_response
        assert mock_func.call_count == 2
    
    def test_exponential_backoff_timing(self):
        """Should use exponential backoff between retries."""
        mock_func = Mock(side_effect=[
            Exception("Fail 1"),
            Exception("Fail 2"),
            "success"
        ])
        
        start_time = time.time()
        with patch('clue_game.main.time.sleep') as mock_sleep:
            result = retry_with_backoff(mock_func, max_retries=3, base_delay=5)
        
        # Should have called sleep twice (after 1st and 2nd failures)
        assert mock_sleep.call_count == 2
        # First retry: base_delay * 2^0 = 5
        # Second retry: base_delay * 2^1 = 10
        mock_sleep.assert_any_call(5)
        mock_sleep.assert_any_call(10)
    
    def test_zero_retries(self):
        """Should not retry when max_retries is 0."""
        mock_func = Mock(side_effect=Exception("Fails"))
        
        with pytest.raises(Exception, match="Fails"):
            retry_with_backoff(mock_func, max_retries=0, base_delay=0.01)
        
        assert mock_func.call_count == 1
    
    def test_preserves_exception_type(self):
        """Should preserve the original exception type."""
        class CustomError(Exception):
            pass
        
        mock_func = Mock(side_effect=CustomError("Custom error"))
        
        with pytest.raises(CustomError, match="Custom error"):
            retry_with_backoff(mock_func, max_retries=1, base_delay=0.01)
    
    def test_response_with_valid_raw_attribute(self):
        """Should accept response with non-empty raw attribute."""
        valid_response = Mock()
        valid_response.raw = "Some valid content"
        
        mock_func = Mock(return_value=valid_response)
        
        result = retry_with_backoff(mock_func, max_retries=3, base_delay=0.01)
        
        assert result == valid_response
        assert mock_func.call_count == 1
    
    def test_response_without_raw_attribute(self):
        """Should accept response without raw attribute if not None."""
        result_value = "simple string result"
        mock_func = Mock(return_value=result_value)
        
        result = retry_with_backoff(mock_func, max_retries=3, base_delay=0.01)
        
        assert result == result_value
        assert mock_func.call_count == 1


class TestRetryIntegration:
    """Integration tests for retry behavior with mocked crews."""
    
    def test_retry_handles_llm_empty_response_error(self):
        """Should handle the specific LLM empty response error."""
        # Simulate the actual error pattern from CrewAI
        mock_func = Mock(side_effect=[
            ValueError("Invalid response from LLM call - None or empty"),
            "success"
        ])
        
        result = retry_with_backoff(mock_func, max_retries=3, base_delay=0.01)
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    def test_retry_with_mixed_failures(self):
        """Should handle different types of failures."""
        mock_func = Mock(side_effect=[
            ConnectionError("Network error"),
            TimeoutError("Timeout"),
            "success"
        ])
        
        result = retry_with_backoff(mock_func, max_retries=3, base_delay=0.01)
        
        assert result == "success"
        assert mock_func.call_count == 3
