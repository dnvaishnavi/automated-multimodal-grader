import streamlit as st
import pandas as pd
from backend.flowchart_pipeline import image_to_json, FlowchartGrader

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Student Dashboard", page_icon="🎓", layout="wide")

# -----------------------------------------------------------------------------
# 2. SESSION STATE (Mock Identity)
# -----------------------------------------------------------------------------
if 'username' not in st.session_state: st.session_state['username'] = "Alex Doe"
if 'student_id' not in st.session_state: st.session_state['student_id'] = "ST-2024-001"

# -----------------------------------------------------------------------------
# 3. CSS STYLING (Sticky Header & Clean UI)
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
    div[data-testid="stVerticalBlock"] > div:first-child {
        position: sticky;
        top: 0;
        z-index: 999;
        background-color: white;
        padding-top: 1rem;
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
        margin-top: 5px;
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
        padding: 0.2rem 0.6rem;
        min-height: 0px;
        height: auto;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 4. STICKY NAVBAR
# -----------------------------------------------------------------------------
with st.container():
    col_head, col_log = st.columns([0.9, 0.1])
    
    with col_head:
        # User details with tight spacing
        st.markdown(f'''
            <div style="line-height: 1.2;">
                <div class="student-header">Hi, {st.session_state['username']} 👋</div>
                <div class="student-id">ID: {st.session_state['student_id']}</div>
            </div>
        ''', unsafe_allow_html=True)
    
    with col_log:
        # Align button vertically with text center
        st.markdown('<div style="margin-top: 10px;"></div>', unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True):
            st.switch_page("Home.py")

    # The "Line" that bridges the gap
    st.markdown("""
        <div style='height: 2px; background-color: #f0f2f6; margin-top: 1rem; width: 100%;'></div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 5. MAIN CONTENT
# -----------------------------------------------------------------------------

# Check if the teacher has saved a rubric (Exam Config)
if 'rubric_data' not in st.session_state or not st.session_state['rubric_data']:
    st.warning("⚠️ No active exam found. Please wait for the teacher to configure the exam.")
    st.stop()

col_left, col_right = st.columns([1, 1], gap="large")

# --- LEFT: SUBMISSION ---
with col_left:
    st.subheader("📤 Submit Assignment")
    
    with st.container(border=True):
        uploaded_file = st.file_uploader("Upload Flowchart", type=['png', 'jpg', 'jpeg'], label_visibility="collapsed")
        
        if uploaded_file:
            st.image(uploaded_file, caption="Preview", use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            # This triggers the grading pipeline
            if st.button("✨ Grade My Submission", type="primary", use_container_width=True):
                
                # Check for API Key
                api_key = st.secrets.get("GEMINI_API_KEY")
                if not api_key:
                    st.error("API Key missing in secrets.toml")
                    st.stop()

                with st.spinner("🤖 AI is analyzing logic flow..."):
                    # 1. Convert Student Image to JSON
                    # (We pass the uploaded_file directly; backend uses Image.open())
                    student_json = image_to_json(uploaded_file, "student", api_key)
                    
                    if student_json:
                        # 2. Grade using the Class Logic
                        rubric = st.session_state['rubric_data']
                        grader = FlowchartGrader(rubric, student_json)
                        result = grader.grade()
                        
                        # 3. Store Result in Session
                        st.session_state['exam_result'] = result
                        st.session_state['graded'] = True
                        st.toast("Grading Complete!", icon="🎉")
                    else:
                        st.error("Could not analyze image. Please try a clearer photo.")

# --- RIGHT: RESULTS ---
with col_right:
    st.subheader("📊 Evaluation Report")
    
    if st.session_state.get('graded') and 'exam_result' in st.session_state:
        res = st.session_state['exam_result']
        
        # Calculate Metrics
        score = res.get('total_score', 0)
        max_marks = res.get('max_marks', 0)
        percentage = (score / max_marks * 100) if max_marks > 0 else 0
        
        with st.container(border=True):
            # 1. Score Cards
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Score", f"{score} / {max_marks}")
            c2.metric("Accuracy", f"{int(percentage)}%")
            
            # Simple Grade Logic
            grade = "A" if percentage >= 80 else ("B" if percentage >= 60 else "C")
            c3.metric("Grade", grade)
            
            st.divider()
            
            # 2. Feedback Table
            st.markdown("#### 📝 Detailed Feedback")
            
            # Convert breakdown list to DataFrame
            if 'breakdown' in res:
                df = pd.DataFrame(res['breakdown'])
                st.dataframe(
                    df, 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        "Status": st.column_config.TextColumn("Status", width="small"),
                        "Marks": st.column_config.TextColumn("Marks", width="small"),
                    }
                )
            else:
                st.info("No detailed breakdown available.")
            
    else:
        # Empty State
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