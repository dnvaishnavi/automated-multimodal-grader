import streamlit as st
from PIL import Image
import time
import pandas as pd

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Student Dashboard", page_icon="🎓", layout="wide")

# -----------------------------------------------------------------------------
# 2. SESSION STATE (Mock Data)
# -----------------------------------------------------------------------------
if 'username' not in st.session_state:
    st.session_state['username'] = "Alex Doe"
if 'student_id' not in st.session_state:
    st.session_state['student_id'] = "ST-2024-001"

student_name = st.session_state['username']
student_id = st.session_state['student_id']

# -----------------------------------------------------------------------------
# 3. CSS STYLING (Identical to Teacher Dashboard)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* HIDE SIDEBAR & DEFAULT HEADER */
    section[data-testid="stSidebar"] { display: none; }
    div[data-testid="collapsedControl"] { display: none; }
    header[data-testid="stHeader"] { display: none; }
    
    /* REMOVE PADDING (Flush to top) */
    .block-container {
        padding-top: 0rem !important;
        padding-bottom: 2rem !important;
    }

    /* STICKY HEADER CONTAINER */
    /* Targets the first container (Navbar) to make it sticky */
    div[data-testid="stVerticalBlock"] > div:first-child {
        position: sticky;
        top: 0;
        z-index: 999;
        background-color: white;
        padding-top: 1rem;
        padding-bottom: 1rem;
        # border-bottom: 2px solid #f0f2f6;
    }

    /* HEADER TYPOGRAPHY */
    .student-header {
        font-size: 2.5rem;
        font-weight: 800;
        color: #1E1E1E;
        margin: 0;
        line-height: 1;
    }
    .student-id {
        font-size: 0.9rem;
        color: #666;
        font-weight: 500;
        margin-top: 2px;
    }

    /* BUTTON STYLES */
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #007bff !important;
        border-color: #007bff !important;
        color: white !important;
    }
    
    /* Small Logout Button */
    div[data-testid="stButton"] button:not([kind="primary"]) {
        font-size: 0.8rem;
        min-height: 0px;
        height: auto;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 4. STICKY NAVBAR
# -----------------------------------------------------------------------------
with st.container():
    # Using exact same ratio as Teacher Dashboard for alignment
    col_head, col_log = st.columns([0.8, 0.2])
    
    with col_head:
        # Tighter line-height to keep it compact
        st.markdown(f'''
                <div class="student-header">Hi, {student_name} 👋</div>
                <div class="student-id">ID: {student_id}</div>
        ''', unsafe_allow_html=True)
    
    with col_log:
        if st.button("🚪 Logout", use_container_width=True):
            st.switch_page("Home.py")

# Spacer after header
st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 5. MAIN CONTENT
# -----------------------------------------------------------------------------

# Helper: Check if exam is active
has_exam = 'rubric_data' in st.session_state and st.session_state['rubric_data'] is not None

# if not has_exam:
#     st.warning("⚠️ No active exam found. Waiting for teacher configuration...")
#     st.stop()

col_left, col_right = st.columns([1, 1], gap="large")

# --- LEFT: SUBMISSION ---
with col_left:
    st.subheader("📤 Submit Assignment")
    
    with st.container(border=True):
        st.info("Upload your Answer Sheet.")
        uploaded_file = st.file_uploader("Upload", type=['png', 'jpg', 'jpeg'], label_visibility="collapsed")
        
        if uploaded_file:
            st.image(uploaded_file, caption="Preview", use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("✨ Grade My Submission", type="primary", use_container_width=True):
                with st.spinner("🤖 AI is analyzing logic flow..."):
                    time.sleep(2) # Simulating AI delay
                    st.session_state['graded'] = True
                    st.toast("Grading Complete!", icon="🎉")

# --- RIGHT: RESULTS ---
with col_right:
    st.subheader("📊 Evaluation Report")
    
    if 'graded' in st.session_state and st.session_state['graded']:
        with st.container(border=True):
            # Score Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Score", "3.5 / 5.0")
            c2.metric("Accuracy", "70%")
            c3.metric("Grade", "B+")
            
            st.divider()
            
            # Detailed Feedback
            st.markdown("#### 📝 Detailed Feedback")
            
            data = [
                {"Criteria": "Start Node", "Status": "✅", "Marks": "0.5/0.5"},
                {"Criteria": "Input Step", "Status": "✅", "Marks": "1.0/1.0"},
                {"Criteria": "Loop Logic", "Status": "⚠️", "Marks": "1.0/2.0"},
                {"Criteria": "End Node", "Status": "✅", "Marks": "0.5/0.5"},
                {"Criteria": "Connections", "Status": "❌", "Marks": "0.5/1.0"}
            ]
            df = pd.DataFrame(data)
            
            st.dataframe(
                df, 
                hide_index=True, 
                use_container_width=True,
                column_config={
                    "Status": st.column_config.TextColumn("Status", width="small"),
                }
            )
            st.info("💡 **Tip:** Ensure your decision diamond connects back to the loop start clearly.")
            
    else:
        st.markdown(
            """
            <div style='display: flex; flex-direction: column; align-items: center; 
                        justify-content: center; height: 350px; color: #aaa; 
                        border: 2px dashed #e0e0e0; border-radius: 10px;'>
                <div style="font-size: 3rem;">📊</div>
                <p style="margin-top: 10px;">Results will appear here</p>
            </div>
            """, 
            unsafe_allow_html=True
        )