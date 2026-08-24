"""
LLM Chat Agent (Step 8)

Orchestrates Claude interaction with tool use.
Implements an agentic loop: send message → parse tool_use → execute tool → loop until text response.

Uses the Anthropic SDK to communicate with Claude.
"""

import json
import logging
from typing import Optional, List, Dict, Tuple

# Load .env for API keys
from dotenv import load_dotenv
load_dotenv()

from anthropic import Anthropic

from src.llm.tools import TOOLS_DEFINITIONS, execute_tool
from src.llm.sql_executor import SafeSQLExecutor
from src.config import get_config

logger = logging.getLogger(__name__)


class ClimateRiskChatAgent:
    """
    Claude-powered chat agent for climate risk queries.

    Supports:
    - Portfolio Manager context (portfolio-wide questions)
    - Underwriter context (property-specific questions)
    - Tool use (curated tools + optional SQL fallback)
    - Conversation history
    """

    def __init__(self, mode: str = "assistant", enable_sql_fallback: bool = False):
        """
        Initialize the chat agent.

        Args:
            mode: "portfolio_manager" or "underwriter" (for system prompt context)
            enable_sql_fallback: if True, allow Claude to generate SELECT queries
        """
        config = get_config()
        llm_config = config.get_section("llm")

        self.model = llm_config.get("model", "claude-3-5-sonnet-20241022")
        self.temperature = llm_config.get("temperature", 0.7)
        self.max_tokens = llm_config.get("max_tokens", 1024)
        self.enable_sql_fallback = enable_sql_fallback and llm_config.get("sql_fallback_enabled", False)

        self.mode = mode
        self.client = Anthropic()
        self.conversation_history = []

        # System prompt depends on mode
        if mode == "portfolio_manager":
            self.system_prompt = (
                "You are a climate risk assistant analyzing insurance portfolios. "
                "You have access to tools that query property risk assessments, active alerts, and geographic hotspots. "
                "Answer questions about portfolio exposure, accumulation risk, and geographic clusters. "
                "Always cite specific numbers and dates from your query results. "
                "Be concise but thorough."
            )
        elif mode == "underwriter":
            self.system_prompt = (
                "You are a climate risk assistant supporting property underwriting decisions. "
                "You have access to detailed risk assessments, risk history, nearby hazards, and property comparisons. "
                "Answer questions about a specific property's risk drivers, recent changes, and mitigation considerations. "
                "When relevant, compare to state/national benchmarks. "
                "Be clear and factual."
            )
        else:
            self.system_prompt = (
                "You are a climate risk assistant. Answer questions about property risk assessments, "
                "portfolio exposure, and insurance implications. Be concise and cite data."
            )

        # Initialize SQL executor if enabled
        if self.enable_sql_fallback:
            db_path = get_config().get("database.path", "data/climate_risk.db")
            self.sql_executor = SafeSQLExecutor(db_path)
        else:
            self.sql_executor = None

        logger.debug(f"Chat agent initialized | mode={mode} | sql_fallback={self.enable_sql_fallback}")

    def _build_tools_for_api(self) -> List[Dict]:
        """Build tool definitions for the Anthropic API."""
        tools = TOOLS_DEFINITIONS.copy()

        # Optionally add SQL query tool if enabled
        if self.enable_sql_fallback:
            tools.append({
                "name": "query_database",
                "description": (
                    "Execute a SELECT query against the climate risk database. "
                    "Use this for novel queries not covered by the curated tools. "
                    "Only SELECT queries are allowed. Results limited to 1000 rows."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "A SELECT query (e.g., 'SELECT * FROM properties WHERE state=?')",
                        },
                        "explanation": {
                            "type": "string",
                            "description": "Brief explanation of what this query does",
                        },
                    },
                    "required": ["sql"],
                },
            })

        return tools

    def chat(self, user_message: str, context: str = "unknown") -> Tuple[str, List[Dict]]:
        """
        Send a message and get a response (with tool use).

        Args:
            user_message: the user's question
            context: for logging (e.g., "portfolio_manager:session_123" or "underwriter:property_42")

        Returns:
            (response_text, tool_calls)
            - response_text: the final assistant message
            - tool_calls: list of tools that were called (for UI display)
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
        })

        logger.debug(f"User message | context={context} | msg_len={len(user_message)}")

        tool_calls = []
        max_iterations = 10  # Prevent infinite loops

        for iteration in range(max_iterations):
            # Call Claude with current history and tools
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self.system_prompt,
                tools=self._build_tools_for_api(),
                messages=self.conversation_history,
            )

            logger.debug(f"Claude response | iteration={iteration} | stop_reason={response.stop_reason}")

            # Check if we're done (no more tool use)
            if response.stop_reason == "end_turn":
                # Extract text response
                text_blocks = [block.text for block in response.content if hasattr(block, "text")]
                final_text = "\n".join(text_blocks) if text_blocks else "(no response)"

                # Add to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content,
                })

                logger.info(
                    f"Chat complete | context={context} | iterations={iteration+1} | "
                    f"tool_calls={len(tool_calls)} | response_len={len(final_text)}"
                )

                return final_text, tool_calls

            # Process tool use
            tool_use_blocks = [block for block in response.content if block.type == "tool_use"]

            if not tool_use_blocks:
                # No tool use and not end_turn? Extract what we have
                text_blocks = [block.text for block in response.content if hasattr(block, "text")]
                final_text = "\n".join(text_blocks) if text_blocks else "(no response)"
                return final_text, tool_calls

            # Execute each tool
            tool_results = []

            for tool_block in tool_use_blocks:
                tool_name = tool_block.name
                tool_input = tool_block.input

                logger.debug(f"Tool use | tool={tool_name} | input_keys={list(tool_input.keys())}")

                try:
                    # Curated tools
                    if tool_name != "query_database":
                        result = execute_tool(tool_name, tool_input)
                    else:
                        # SQL fallback tool
                        sql = tool_input.get("sql", "")
                        explanation = tool_input.get("explanation", "")
                        rows, error = self.sql_executor.execute(sql, context)

                        if error:
                            result = json.dumps({"error": error})
                        else:
                            result = json.dumps({
                                "sql": sql,
                                "explanation": explanation,
                                "rows": rows,
                                "row_count": len(rows),
                            })

                    # Record for UI display
                    tool_calls.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "result_preview": result[:200] if len(result) > 200 else result,
                    })

                    # Add to tool results for next iteration
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": result,
                    })

                except Exception as e:
                    error_msg = f"Tool execution failed: {str(e)}"
                    logger.error(f"Tool error | tool={tool_name} | error={error_msg}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": json.dumps({"error": error_msg}),
                        "is_error": True,
                    })

            # Add assistant response and tool results to history
            self.conversation_history.append({
                "role": "assistant",
                "content": response.content,
            })

            self.conversation_history.append({
                "role": "user",
                "content": tool_results,
            })

        logger.error(f"Chat max iterations reached | context={context}")
        return "Max iterations reached. Please try a simpler query.", tool_calls

    def reset_conversation(self) -> None:
        """Clear conversation history (start a new conversation)."""
        self.conversation_history = []
        logger.debug("Conversation history cleared")

    def get_conversation_summary(self) -> Dict:
        """Get a summary of the current conversation."""
        return {
            "messages": len(self.conversation_history),
            "mode": self.mode,
            "model": self.model,
            "sql_fallback_enabled": self.enable_sql_fallback,
        }
