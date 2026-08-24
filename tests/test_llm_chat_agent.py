"""
Unit Tests for LLM Chat Agent (Step 13)

Tests the agentic loop orchestration, tool calling, and conversation management.
Uses mocked Anthropic API to avoid real API calls and costs.

Run with: pytest tests/test_llm_chat_agent.py -v
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import json

from src.llm.chat_agent import ClimateRiskChatAgent
from src.llm.tools import TOOLS_DEFINITIONS


class TestClimateRiskChatAgent:
    """Test suite for ClimateRiskChatAgent."""

    def test_initialization_portfolio_manager(self):
        """Agent initializes with correct Portfolio Manager system prompt."""
        agent = ClimateRiskChatAgent(mode="portfolio_manager")
        assert "portfolio" in agent.system_prompt.lower()
        assert agent.mode == "portfolio_manager"
        assert agent.model == "claude-3-5-sonnet-20241022"

    def test_initialization_underwriter(self):
        """Agent initializes with correct Underwriter system prompt."""
        agent = ClimateRiskChatAgent(mode="underwriter")
        assert "underwriting" in agent.system_prompt.lower()
        assert agent.mode == "underwriter"

    def test_conversation_history_starts_empty(self):
        """Conversation history is empty on initialization."""
        agent = ClimateRiskChatAgent()
        assert agent.conversation_history == []

    def test_reset_conversation_clears_history(self):
        """reset_conversation() clears the history."""
        agent = ClimateRiskChatAgent()
        agent.conversation_history = [{"role": "user", "content": "test"}]
        agent.reset_conversation()
        assert agent.conversation_history == []

    def test_get_conversation_summary(self):
        """get_conversation_summary() returns correct stats."""
        agent = ClimateRiskChatAgent(mode="portfolio_manager")
        agent.conversation_history = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        summary = agent.get_conversation_summary()

        assert summary["messages"] == 2
        assert summary["mode"] == "portfolio_manager"
        assert summary["model"] == "claude-3-5-sonnet-20241022"
        assert summary["sql_fallback_enabled"] == False

    def test_tools_for_api_includes_curated_tools(self):
        """_build_tools_for_api() includes all curated tools."""
        agent = ClimateRiskChatAgent(sql_fallback_enabled=False)
        tools = agent._build_tools_for_api()

        # Should have exactly the curated tools
        tool_names = [t["name"] for t in tools]
        assert len(tool_names) == len(TOOLS_DEFINITIONS)
        assert "get_portfolio_metrics" in tool_names
        assert "get_active_alerts" in tool_names

    def test_tools_for_api_includes_sql_when_enabled(self):
        """_build_tools_for_api() includes SQL query tool when enabled."""
        agent = ClimateRiskChatAgent(sql_fallback_enabled=True)
        tools = agent._build_tools_for_api()

        tool_names = [t["name"] for t in tools]
        assert "query_database" in tool_names
        assert len(tool_names) == len(TOOLS_DEFINITIONS) + 1

    @patch("src.llm.chat_agent.Anthropic")
    def test_chat_adds_user_message_to_history(self, mock_anthropic):
        """chat() adds user message to conversation history."""
        # Mock Claude response: no tool use, just text
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [MagicMock(text="Here's the answer")]
        mock_response.content[0].text = "Here's the answer"

        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        agent = ClimateRiskChatAgent()
        agent.chat("What's the risk level?", context="test")

        # Check history has the user message
        assert len(agent.conversation_history) >= 1
        assert agent.conversation_history[0]["role"] == "user"
        assert agent.conversation_history[0]["content"] == "What's the risk level?"

    @patch("src.llm.chat_agent.Anthropic")
    def test_chat_returns_text_response(self, mock_anthropic):
        """chat() returns text response from Claude."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"

        # Mock a text block
        text_block = MagicMock()
        text_block.text = "Portfolio risk is stable."
        mock_response.content = [text_block]

        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        agent = ClimateRiskChatAgent()
        response_text, tool_calls = agent.chat("Status?", context="test")

        assert response_text == "Portfolio risk is stable."
        assert tool_calls == []

    @patch("src.llm.chat_agent.Anthropic")
    def test_chat_handles_tool_use(self, mock_anthropic):
        """chat() handles tool_use blocks from Claude."""
        mock_client = MagicMock()

        # First response: Claude calls a tool
        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.id = "call_123"
        tool_use_block.name = "get_portfolio_metrics"
        tool_use_block.input = {}

        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_use_block]

        # Second response: Claude returns text after tool result
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Your portfolio has 100 properties."
        second_response = MagicMock()
        second_response.stop_reason = "end_turn"
        second_response.content = [text_block]

        mock_client.messages.create.side_effect = [first_response, second_response]
        mock_anthropic.return_value = mock_client

        agent = ClimateRiskChatAgent()
        response_text, tool_calls = agent.chat("How many properties?", context="test")

        # Should have called tool and gotten response
        assert "100 properties" in response_text
        assert len(tool_calls) >= 1

    def test_sql_fallback_disabled_by_default(self):
        """SQL fallback is disabled by default."""
        agent = ClimateRiskChatAgent()
        assert agent.enable_sql_fallback == False
        assert agent.sql_executor is None

    def test_sql_fallback_can_be_enabled(self):
        """SQL fallback can be enabled at init."""
        agent = ClimateRiskChatAgent(enable_sql_fallback=True)
        assert agent.enable_sql_fallback == True
        assert agent.sql_executor is not None


class TestChatExampleScenarios:
    """Test realistic chat scenarios."""

    @patch("src.llm.chat_agent.Anthropic")
    @patch("src.llm.chat_agent.execute_tool")
    def test_portfolio_manager_scenario(self, mock_execute_tool, mock_anthropic):
        """Simulate a Portfolio Manager asking about critical properties."""
        # Mock Claude calling get_properties_by_risk_level
        tool_use = MagicMock()
        tool_use.type = "tool_use"
        tool_use.id = "call_1"
        tool_use.name = "get_properties_by_risk_level"
        tool_use.input = {"risk_level": "critical"}

        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_use]

        text_block = MagicMock()
        text_block.text = "Based on the database, 5 properties are in critical risk."
        second_response = MagicMock()
        second_response.stop_reason = "end_turn"
        second_response.content = [text_block]

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [first_response, second_response]
        mock_anthropic.return_value = mock_client

        mock_execute_tool.return_value = json.dumps({
            "properties": [
                {"property_id": 1, "risk_level": "critical"},
                {"property_id": 2, "risk_level": "critical"},
            ]
        })

        agent = ClimateRiskChatAgent(mode="portfolio_manager")
        response, tools = agent.chat(
            "How many properties are in critical risk?",
            context="pm_test"
        )

        assert "critical" in response.lower()

    @patch("src.llm.chat_agent.Anthropic")
    @patch("src.llm.chat_agent.execute_tool")
    def test_underwriter_scenario(self, mock_execute_tool, mock_anthropic):
        """Simulate an Underwriter asking about a property."""
        tool_use = MagicMock()
        tool_use.type = "tool_use"
        tool_use.id = "call_1"
        tool_use.name = "get_property_risk_history"
        tool_use.input = {"property_id": 42, "limit": 5}

        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_use]

        text_block = MagicMock()
        text_block.text = "Property 42 has an overall risk of 45, stable over time."
        second_response = MagicMock()
        second_response.stop_reason = "end_turn"
        second_response.content = [text_block]

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [first_response, second_response]
        mock_anthropic.return_value = mock_client

        mock_execute_tool.return_value = json.dumps({
            "assessments": [
                {"overall_risk_score": 45, "risk_level": "medium"}
            ]
        })

        agent = ClimateRiskChatAgent(mode="underwriter")
        response, tools = agent.chat(
            "What's property 42's risk profile?",
            context="uw_test"
        )

        assert "45" in response or "risk" in response.lower()


class TestErrorHandling:
    """Test error handling in chat agent."""

    @patch("src.llm.chat_agent.Anthropic")
    def test_chat_handles_max_iterations_gracefully(self, mock_anthropic):
        """chat() returns graceful message if max iterations reached."""
        mock_client = MagicMock()

        # Simulate infinite tool use (Claude keeps calling tools)
        tool_use = MagicMock()
        tool_use.type = "tool_use"
        tool_use.id = "call_x"
        tool_use.name = "get_portfolio_metrics"
        tool_use.input = {}

        response = MagicMock()
        response.stop_reason = "tool_use"
        response.content = [tool_use]

        # Keep returning tool_use responses
        mock_client.messages.create.return_value = response
        mock_anthropic.return_value = mock_client

        agent = ClimateRiskChatAgent()
        response_text, _ = agent.chat("Query", context="test")

        # Should return graceful error after hitting max iterations
        assert "Max iterations" in response_text or "simpler" in response_text.lower()

    @patch("src.llm.chat_agent.Anthropic")
    def test_chat_gracefully_handles_empty_response(self, mock_anthropic):
        """chat() handles case where Claude returns no text blocks."""
        mock_client = MagicMock()
        response = MagicMock()
        response.stop_reason = "end_turn"
        response.content = []  # Empty response

        mock_client.messages.create.return_value = response
        mock_anthropic.return_value = mock_client

        agent = ClimateRiskChatAgent()
        response_text, _ = agent.chat("Query", context="test")

        # Should return placeholder
        assert response_text == "(no response)" or response_text == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
