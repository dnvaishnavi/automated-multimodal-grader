import streamlit as st
import tempfile
from backend.flowchart_pipeline import image_to_json 
# -----------------------------------------------------------------------------
# PAGE CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Teacher Dashboard", page_icon="👨‍🏫", layout="wide")

st.markdown(""" 
    <style> /* 1. Hide Sidebar, Collapse Control, and Default Header Decoration */ section[data-testid="stSidebar"] { display: none; } div[data-testid="collapsedControl"] { display: none; } header[data-testid="stHeader"] { display: none; } /* 2. Reset Main Page Padding */ .block-container { padding-top: 0rem; padding-bottom: 1rem; } /* 3. STICKY HEADER CONTAINER */ /* This targets the first major container in the app to act as a fixed header */ div[data-testid="stVerticalBlock"] > div:first-child { position: sticky; top: 0; z-index: 999; background-color: white; padding-top: 1rem; padding-bottom: 1rem; border-bottom: 1px solid #f0f0f0; } /* 4. Increase Title Size */ .dashboard-title { font-size: 3rem !important; /* Increased size */ font-weight: 800; color: #1E1E1E; margin: 0; padding: 0; line-height: 1; } /* 5. Shrink Logout Button */ /* Target the button inside the specific logout column */ div[data-testid="stButton"] button { height: auto; padding-top: 0.2rem; padding-bottom: 0.2rem; min-height: 0px; font-size: 0.9rem; border:none; } button[data-testid="stNumberInputStepDown"], button[data-testid="stNumberInputStepUp"] { display: none !important; } </style> """, unsafe_allow_html=True) # --- STICKY NAVBAR SECTION --- # We use a container to wrap the header so the CSS can target it for "stickiness"

with st.container(): col_title, col_logout = st.columns([0.8, 0.2])
with col_title: st.markdown('<p class="dashboard-title">👨‍🏫 Teacher Dashboard</p>', unsafe_allow_html=True)
with col_logout: # Aligning the button vertically
    if st.button("🚪 Logout", use_container_width=True): st.switch_page("Home.py")

# -----------------------------------------------------------------------------
# EXAM CONFIG
# -----------------------------------------------------------------------------
with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.selectbox("Subject", ["Computer Science", "Mathematics", "Physics"], label_visibility="collapsed")
    with c2:
        st.text_input("Exam Code", placeholder="Exam Code (e.g. CS-101)", label_visibility="collapsed")
    with c3:
        st.number_input("Marks", value=5, placeholder="Total Marks", label_visibility="collapsed")

# -----------------------------------------------------------------------------
# UPLOAD AREA
# -----------------------------------------------------------------------------
st.markdown("#### 📤 Upload & Preview")

col_left, col_right = st.columns(2, gap="medium")

with col_left:
    st.caption("1. Upload Question Paper")
    st.file_uploader("QP", type=['pdf', 'jpg'], label_visibility="collapsed")

    st.caption("2. Upload Correct Flowchart (Answer Key)")
    model_ans = st.file_uploader("Key", type=['png', 'jpg'], label_visibility="collapsed")

    st.caption("3. Rubric Notes (Optional)")
    st.text_area("Rubric", placeholder="- Start Node (1 mark)...", height=80, label_visibility="collapsed")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("💾 Save Configuration", type="primary", use_container_width=True):
        if not model_ans:
            st.toast("Please upload an Answer Key.", icon="⚠️")
            st.stop()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(model_ans.getbuffer())
            teacher_image = tmp.name

        with st.spinner("🧠 Generating rubric from flowchart..."):
            rubric_obj = image_to_json(
                image_path=teacher_image,
                mode="teacher",
                api_key=st.secrets["GEMINI_API_KEY"]
            )

        st.session_state["rubric_obj"] = rubric_obj
        st.session_state["exam_active"] = True

        st.toast("Configuration Saved Successfully!", icon="✅")

with col_right:
    with st.container(border=True):
        if model_ans:
            st.image(model_ans, caption="Answer Key Preview", use_container_width=True)
        else:
            st.markdown(
                """
                <div style='display:flex;align-items:center;justify-content:center;
                            height:300px;color:#aaa;'>
                    <div style="font-size:3rem;">🖼️</div>
                </div>
                """,
                unsafe_allow_html=True
            )
