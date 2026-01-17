import streamlit as st

st.set_page_config(page_title="Teacher Dashboard", page_icon="👨‍🏫", layout="wide")

# --- CSS: STICKY HEADER, HIDDEN SIDEBAR, & TYPOGRAPHY ---
st.markdown("""
<style>
    /* 1. Hide Sidebar, Collapse Control, and Default Header Decoration */
    section[data-testid="stSidebar"] { display: none; }
    div[data-testid="collapsedControl"] { display: none; }
    header[data-testid="stHeader"] { display: none; }
    
    /* 2. Reset Main Page Padding */
    .block-container {
        padding-top: 0rem;
        padding-bottom: 1rem;
    }

    /* 3. STICKY HEADER CONTAINER */
    /* This targets the first major container in the app to act as a fixed header */
    div[data-testid="stVerticalBlock"] > div:first-child {
        position: sticky;
        top: 0;
        z-index: 999;
        background-color: white;
        padding-top: 1rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #f0f0f0;
    }

    /* 4. Increase Title Size */
    .dashboard-title {
        font-size: 3rem !important;  /* Increased size */
        font-weight: 800;
        color: #1E1E1E;
        margin: 0;
        padding: 0;
        line-height: 1;
    }

    /* 5. Shrink Logout Button */
    /* Target the button inside the specific logout column */
    div[data-testid="stButton"] button {
        height: auto;
        padding-top: 0.2rem;
        padding-bottom: 0.2rem;
        min-height: 0px;
        font-size: 0.9rem;
        border:none;
    }
    button[data-testid="stNumberInputStepDown"], 
    button[data-testid="stNumberInputStepUp"] {
        display: none !important;
    }
    
</style>
""", unsafe_allow_html=True)

# --- STICKY NAVBAR SECTION ---
# We use a container to wrap the header so the CSS can target it for "stickiness"
with st.container():
    col_title, col_logout = st.columns([0.8, 0.2])

    with col_title:
        st.markdown('<p class="dashboard-title">👨‍🏫 Teacher Dashboard</p>', unsafe_allow_html=True)

    with col_logout:
        # Aligning the button vertically
        if st.button("🚪 Logout", use_container_width=True):
            st.switch_page("Home.py")

# --- MAIN CONTENT (Scrollable) ---
# Add a little spacing so content doesn't disappear under the sticky header immediately
#st.markdown("<br>", unsafe_allow_html=True)

# --- EXAM CONFIGURATION ---
with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.selectbox("Subject", ["Computer Science", "Mathematics", "Physics"], label_visibility="collapsed")
    with c2:
        st.text_input("Exam Code", placeholder="Exam Code (e.g. CS-101)", label_visibility="collapsed")
    with c3:
      st.number_input("Marks", value=None, placeholder="Total Marks (e.g. 20)", label_visibility="collapsed")
# --- UPLOAD & PREVIEW AREA ---
st.markdown("#### 📤 Upload & Preview")

col_left, col_right = st.columns([1, 1], gap="medium")

with col_left:
    st.caption("1. Upload Question Paper")
    st.file_uploader("QP", type=['pdf', 'jpg'], key="qp", label_visibility="collapsed")

    st.caption("2. Upload Answer Key (Required)")
    model_ans = st.file_uploader("Key", type=['png', 'jpg'], key="model", label_visibility="collapsed")
    
    st.caption("3. Rubric Notes")
    st.text_area("Rubric", placeholder="- Start Node (1 mark)...", height=80, label_visibility="collapsed")
    
    st.markdown("<br>", unsafe_allow_html=True) 
    
    if st.button("💾 Save Configuration", type="primary", use_container_width=True):
        if model_ans:
            st.toast("Configuration Saved Successfully!", icon="✅")
        else:
            st.toast("Please upload an Answer Key.", icon="⚠️")

with col_right:
    with st.container(border=True):
        if model_ans:
            st.image(model_ans, caption="Master Key Preview", use_container_width=True)
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