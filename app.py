"""
Climate Risk Assessment - Web Dashboard

Streamlit app entry point for the web-based dashboard.
Supports two personas: Portfolio Manager and Underwriter.

Run with:
    streamlit run app.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Load .env file for API keys
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from src.config import setup_logging


def main():
    """Main app entry point with role selection."""

    # Configure page
    st.set_page_config(
        page_title="Climate Risk Assessment",
        page_icon="🌍",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Setup logging once
    if "logging_configured" not in st.session_state:
        setup_logging()
        st.session_state.logging_configured = True

    # Title and description
    st.sidebar.title("🌍 Climate Risk Assessment")
    st.sidebar.write("Continuous monitoring of wildfire and flood exposure")

    st.sidebar.divider()

    # Role selection
    role = st.sidebar.radio(
        "Select your role",
        options=["Portfolio Manager", "Underwriter"],
        index=0,
        help="Choose your view: portfolio-wide or single-property analysis"
    )

    st.session_state.role = role

    st.sidebar.divider()

    # Page selection
    page = st.sidebar.radio(
        "Page",
        options=["Dashboard", "Chat"],
        index=0,
        help="Dashboard or AI Q&A"
    )

    st.sidebar.divider()

    # Route to appropriate page
    if page == "Chat":
        from src.ui.pages import chat
        chat.main()
    elif role == "Portfolio Manager":
        from src.ui.pages import portfolio_manager
        portfolio_manager.main()
    else:  # Underwriter
        from src.ui.pages import underwriter
        underwriter.main()

    # Footer
    st.sidebar.divider()
    st.sidebar.write(
        "<small>Built with 559 passing tests | "
        "[Docs](https://github.com/anthropics/claude-code) | "
        "[GitHub](https://github.com)</small>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
