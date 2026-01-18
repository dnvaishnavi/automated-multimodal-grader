import streamlit as st
import tempfile
from backend.flowchart_pipeline import image_to_json

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Teacher Dashboard", page_icon="👨‍🏫", layout="wide")

# -----------------------------------------------------------------------------
# 2. CSS STYLING (Sticky Header, Blue Buttons, Clean UI)
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
    .dashboard-title {
        font-size: 3rem;
        font-weight: 800;
        color: #1E1E1E;
        margin: 0;
        line-height: 1;
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

    /* Hide Number Input Steppers */
    button[data-testid="stNumberInputStepDown"], 
    button[data-testid="stNumberInputStepUp"] {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. STICKY NAVBAR
# -----------------------------------------------------------------------------
with st.container():
    col_head, col_log = st.columns([0.9, 0.1])
    
    with col_head:
        st.markdown('<p class="dashboard-title">👨‍🏫 Teacher Dashboard</p>', unsafe_allow_html=True)
    
    with col_log:
        # Align button vertically
        st.markdown('<div style="margin-top: 10px;"></div>', unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True):
            st.switch_page("Home.py")

    # The "Line" that bridges the gap
    st.markdown("""
        <div style='height: 2px; background-color: #f0f2f6; margin-top: 1rem; width: 100%;'></div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 4. EXAM CONFIGURATION
# -----------------------------------------------------------------------------
st.subheader("⚙️ Exam Configuration")

with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.selectbox("Subject", ["Computer Science", "Mathematics", "Physics"], label_visibility="collapsed")
    with c2:
        st.text_input("Exam Code", placeholder="Exam Code (e.g. CS-101)", label_visibility="collapsed")
    with c3:
        st.number_input("Marks", value=None, placeholder="Total Marks", label_visibility="collapsed")

# -----------------------------------------------------------------------------
# 5. UPLOAD & PREVIEW AREA
# -----------------------------------------------------------------------------
st.markdown("#### 📤 Upload & Preview")

col_left, col_right = st.columns([1, 1], gap="medium")

# --- LEFT: UPLOADS ---
with col_left:
    st.caption("1. Upload Question Paper")
    st.file_uploader("QP", type=['pdf', 'jpg'], label_visibility="collapsed")

    st.caption("2. Upload Correct Flowchart (Answer Key)")
    model_ans = st.file_uploader("Key", type=['png', 'jpg'], label_visibility="collapsed")

    st.caption("3. Rubric Notes (Optional)")
    st.text_area("Rubric", placeholder="- Start Node (1 mark)...", height=80, label_visibility="collapsed")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- SAVE ACTION ---
    if st.button("💾 Save Configuration", type="primary", use_container_width=True):
        if not model_ans:
            st.toast("Please upload an Answer Key first.", icon="⚠️")
        else:
            api_key = st.secrets.get("GEMINI_API_KEY")
            if not api_key:
                st.error("API Key missing in secrets.toml")
                st.stop()

            # Process Image
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(model_ans.getbuffer())
                teacher_image_path = tmp.name

            with st.spinner("🧠 Generating rubric from flowchart..."):
                # Call Backend
                rubric_data = image_to_json(
                    image_file=teacher_image_path, # Passed as path or file object depending on backend implementation
                    mode="teacher",
                    api_key=api_key
                )

            if rubric_data:
                # Save to session so Student Dashboard can see it
                st.session_state["rubric_data"] = rubric_data
                st.session_state["exam_active"] = True
                st.toast("Configuration Saved Successfully!", icon="✅")
            else:
                st.error("Failed to generate rubric. Please try a clearer image.")

# --- RIGHT: PREVIEW ---
with col_right:
    with st.container(border=True):
        if model_ans:
            st.image(model_ans, caption="Answer Key Preview", use_container_width=True)
            if "rubric_data" in st.session_state:
                st.success("✅ Rubric Generated & Ready")
        else:
            st.markdown(
                """
                <div style='display: flex; flex-direction: column; align-items: center; 
                            justify-content: center; height: 300px; color: #aaa;'>
                    <div style="font-size: 3rem;">🖼️</div>
                    <p style="margin-top: 10px;">Answer Key Preview</p>
                </div>
                """, 
                unsafe_allow_html=True
            )