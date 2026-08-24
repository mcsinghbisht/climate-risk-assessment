"""
Chat Page (Step 8 integration into Streamlit)

LLM-powered Q&A interface for Portfolio Managers and Underwriters.
Accessible as a separate page in the Streamlit app.

Run the main app.py and select "Chat" from the sidebar.
"""

import streamlit as st
import json
from typing import Optional

from src.config import get_config
from src.llm.chat_agent import ClimateRiskChatAgent
from src.ui.components import render_system_health


def main():
    st.set_page_config(page_title="Ask the AI", layout="wide")
    st.title("💬 Ask About Your Risk Portfolio")

    # Check if LLM is enabled
    config = get_config()
    llm_config = config.get_section("llm")
    if not llm_config.get("enabled", False):
        st.warning(
            "⚠️ LLM features are disabled. To enable:\n\n"
            "1. Set your ANTHROPIC_API_KEY in `.env`\n"
            "2. Set `llm.enabled: true` in `config/settings.json`\n"
            "3. Restart the app\n\n"
            "[Get an API key](https://console.anthropic.com/)"
        )
        st.stop()

    # Initialize session state
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "chat_agent" not in st.session_state:
        # Determine role from parent app's session state
        role = st.session_state.get("role", "Portfolio Manager")
        mode = "portfolio_manager" if role == "Portfolio Manager" else "underwriter"

        sql_fallback = llm_config.get("sql_fallback_enabled", False)

        st.session_state.chat_agent = ClimateRiskChatAgent(
            mode=mode,
            enable_sql_fallback=sql_fallback,
        )

    agent = st.session_state.chat_agent

    # Sidebar: chat settings
    st.sidebar.write("### Chat Settings")
    role = st.session_state.get("role", "Portfolio Manager")
    st.sidebar.write(f"**Mode:** {role}")
    st.sidebar.write(f"**Model:** {agent.model}")

    if st.sidebar.button("Clear Chat History", help="Start a new conversation"):
        st.session_state.chat_history = []
        agent.reset_conversation()
        st.rerun()

    # Display conversation history
    st.write(
        "Ask questions about your portfolio, specific properties, "
        "risk trends, alerts, or geographic hotspots. "
        "The AI has access to all your risk data."
    )

    st.divider()

    # Chat display
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        else:  # assistant
            with st.chat_message("assistant"):
                st.write(msg["content"])
                if "tool_calls" in msg and msg["tool_calls"]:
                    with st.expander(f"🔧 Used {len(msg['tool_calls'])} tool(s)"):
                        for tool_call in msg["tool_calls"]:
                            st.write(f"**{tool_call['tool']}**")
                            st.code(json.dumps(tool_call["input"], indent=2), language="json")

    st.divider()

    # Chat input
    user_input = st.chat_input("Ask about your portfolio or a specific property...")

    if user_input:
        # Add user message to history
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input,
        })

        # Show user message immediately
        with st.chat_message("user"):
            st.write(user_input)

        # Get agent response with loading indicator
        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                try:
                    context = f"{role.lower()}:session_{id(st.session_state.chat_agent)}"
                    response_text, tool_calls = agent.chat(user_input, context=context)

                    # Display response
                    st.write(response_text)

                    # Show tool calls if any
                    if tool_calls:
                        with st.expander(f"🔧 Used {len(tool_calls)} tool(s)"):
                            for tool_call in tool_calls:
                                st.write(f"**{tool_call['tool']}**")
                                st.code(json.dumps(tool_call["input"], indent=2), language="json")
                                st.caption(f"Result preview: {tool_call['result_preview']}")

                    # Add to history
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response_text,
                        "tool_calls": tool_calls,
                    })

                except Exception as e:
                    error_msg = f"❌ Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": error_msg,
                    })

    st.divider()

    # Example questions
    with st.expander("💡 Example Questions"):
        st.write(
            """
            **Portfolio Manager:**
            - "What percentage of our portfolio is in critical risk?"
            - "Which states have the most properties in high or critical risk?"
            - "Where are the geographic hotspots with elevated risk?"
            - "How many active alerts do we have right now?"
            - "Which properties triggered alerts this week?"

            **Underwriter:**
            - "Show me property 42's risk history over the last 10 assessments"
            - "What factors are driving the wildfire risk for property 15?"
            - "Has property 8's risk changed recently and why?"
            - "What alerts are active for property 99?"
            - "Which similar properties in CA have higher flood risk than property 50?"
            """
        )

    st.divider()

    # System health
    render_system_health()


if __name__ == "__main__":
    main()
