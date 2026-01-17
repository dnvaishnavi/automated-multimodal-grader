import streamlit as st
import tempfile
import pandas as pd
from backend.flowchart_pipeline import image_to_json, grade_flowchart

# -----------------------------------------------------------------------------
# PAGE CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Student Dashboard", page_icon="🎓", layout="wide")

# -----------------------------------------------------------------------------
# SESSION STATE (Mock identity)
# -----------------------------------------------------------------------------
st.session_state.setdefault("username", "Alex Doe")
st.session_state.setdefault("student_id", "ST-2024-001")

# -----------------------------------------------------------------------------
# CSS
# -----------------------------------------------------------------------------
st.markdown("""
<style>
section[data-testid="stSidebar"] { display: none; }
div[data-testid="collapsedControl"] { display: none; }
header[data-testid="stHeader"] { display: none; }

.block-container {
    padding-top: 0rem;
    padding-bottom: 2rem;
}

div[data-testid="stVerticalBlock"] > div:first-child {
    position: sticky;
    top: 0;
    z-index: 999;
    background-color: white;
    padding-top: 1rem;
    padding-bottom: 1rem;
}

.student-header {
    font-size: 2.5rem;
    font-weight: 800;
    color: #1E1E1E;
}
.student-id {
    font-size: 0.9rem;
    color: #666;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# STICKY HEADER
# -----------------------------------------------------------------------------
with st.container():
    col_head, col_log = st.columns([0.8, 0.2])

    with col_head:
        st.markdown(f"""
            <div class="student-header">Hi, {st.session_state['username']} 👋</div>
            <div class="student-id">ID: {st.session_state['student_id']}</div>
        """, unsafe_allow_html=True)

    with col_log:
        if st.button("🚪 Logout", use_container_width=True):
            st.switch_page("app.py")

st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# MAIN CONTENT
# -----------------------------------------------------------------------------
if "rubric_obj" not in st.session_state:
    st.warning("⚠️ Exam not yet configured by teacher.")
    st.stop()

col_left, col_right = st.columns(2, gap="large")

# -----------------------------------------------------------------------------
# SUBMISSION
# -----------------------------------------------------------------------------
with col_left:
    st.subheader("📤 Submit Assignment")

    with st.container(border=True):
        uploaded_file = st.file_uploader(
            "Upload Flowchart",
            type=['png', 'jpg', 'jpeg'],
            label_visibility="collapsed"
        )

        if uploaded_file:
            st.image(uploaded_file, caption="Preview", use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)

            if st.button("✨ Grade My Submission", type="primary", use_container_width=True):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(uploaded_file.getbuffer())
                    student_image = tmp.name

                with st.spinner("🤖 AI is analyzing logic flow..."):
                    student_obj = image_to_json(
                        image_path=student_image,
                        mode="student",
                        api_key=st.secrets["GEMINI_API_KEY"]
                    )

                    result = grade_flowchart(
                        student_obj=student_obj,
                        rubric_obj=st.session_state["rubric_obj"]
                    )

                st.session_state["result"] = result
                st.session_state["graded"] = True
                st.toast("Grading Complete!", icon="🎉")

# -----------------------------------------------------------------------------
# RESULTS
# -----------------------------------------------------------------------------
with col_right:
    st.subheader("📊 Evaluation Report")

    if st.session_state.get("graded"):
        result = st.session_state["result"]

        with st.container(border=True):
            c1, c2 = st.columns(2)
            c1.metric("Total Score", f"{result['score']} / {result['max_score']}")
            c2.metric("Accuracy", f"{(result['score']/result['max_score'])*100:.0f}%")

            st.divider()
            st.markdown("#### 📝 Detailed Feedback")

            df = pd.DataFrame(result["breakdown"])
            st.dataframe(df, hide_index=True, use_container_width=True)

    else:
        st.markdown(
            """
            <div style='display:flex;align-items:center;justify-content:center;
                        height:350px;color:#aaa;
                        border:2px dashed #e0e0e0;border-radius:10px;'>
                <div style="font-size:3rem;">📊</div>
            </div>
            """,
            unsafe_allow_html=True
        )
