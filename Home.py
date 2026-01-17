import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="GradeWise",
    page_icon="📝",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS to style the buttons as cards
st.markdown("""
<style>
    /* Style the buttons to look like large cards */
    .stButton > button {
        background-color: #f0f2f6;
        color: #31333F;
        padding: 30px 20px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        width: 100%;
        height: 100%;
        text-align: center;
        transition: all 0.3s ease;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    /* Hover effect */
    .stButton > button:hover {
        border-color: #ff4b4b;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        background-color: #ffffff;
    }

    /* Make the text inside the button larger */
    .stButton > button p {
        font-size: 1.2rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.title("📝 GradeWise")
st.markdown(
    """
### Automated Multimodal Assessment System  
Evaluate handwritten answers, diagrams, flowcharts & text.
"""
)
st.markdown("---")

st.info("👋 Welcome! Please select your role to proceed to your dashboard.")

# --- SIDE-BY-SIDE LAYOUT ---
col1, col2 = st.columns(2)

with col1:
    # The label acts as the card content
    if st.button("👨‍🏫 Teacher", use_container_width=True):
        st.session_state['role'] = 'Teacher'
        st.switch_page("pages/1_Evaluator.py")

with col2:
    if st.button("🎓 Student", use_container_width=True):
        st.session_state['role'] = 'Student'
        st.switch_page("pages/2_Student.py")
