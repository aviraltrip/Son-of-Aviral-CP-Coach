"""Streamlit Web Application for CP Coach.

Multi-Agent Competitive Programming Coach with live Codeforces history sync,
deterministic algorithmic diagnostics, tailored recommendations, and verified 3-tier hints.
"""
import uuid
import streamlit as st

from app.graph import create_coach_graph
from app.ui.components import inject_custom_css

def init_session_state() -> None:
    """Initialize LangGraph state machine and UI session values."""
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
        
    if "graph" not in st.session_state:
        st.session_state.graph = create_coach_graph()
        
    if "config" not in st.session_state:
        st.session_state.config = {"configurable": {"thread_id": st.session_state.thread_id}}
        
    if "handle" not in st.session_state:
        st.session_state.handle = "tourist"
        
    if "initialized" not in st.session_state:
        st.session_state.initialized = False

def main() -> None:
    st.set_page_config(
        page_title="CP Coach | Multi-Agent CP Mentorship",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    inject_custom_css()
    init_session_state()

    st.markdown('<div class="main-header">CP Coach</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Multi-Agent Competitive Programming Coach &bull; Solution-Blind Hints &bull; Data-Driven Diagnostics</div>',
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
