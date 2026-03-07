# tabs/intro_tab.py
from pathlib import Path

import streamlit as st


def render():
    st.subheader("Introduction")

    # repo root = parent of the 'tabs' directory
    intro_path = Path(__file__).parent.parent / "data" / "intro.md"

    try:
        text = intro_path.read_text(encoding="utf-8")
        # Render markdown content
        st.markdown(text, unsafe_allow_html=False)
    except FileNotFoundError:
        st.error("intro.md not found in the repository root.")
    except Exception as e:
        st.error(f"Error reading intro.md: {e}")
