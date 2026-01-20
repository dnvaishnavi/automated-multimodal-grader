import streamlit as st
import pandas as pd
import json
import uuid
from PIL import Image

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Teacher Dashboard", page_icon="👨‍🏫", layout="wide")

st.markdown("""
<style>
    /* Clean UI Overrides */
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    
    /* Card Styling for Key Points */
    .keypoint-card {
        background-color: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        border-left: 5px solid #007bff;
    }
    .keypoint-header { font-weight: bold; font-size: 1.05rem; color: #333; }
    .keypoint-meta { font-size: 0.85rem; color: #666; margin-top: 5px; }
    
    /* Success/Action Buttons */
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #007bff;
        border-color: #007bff;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. SESSION STATE INITIALIZATION
# -----------------------------------------------------------------------------
if 'teacher_profile' not in st.session_state:
    st.session_state['teacher_profile'] = {
        "name": "Dr. Sarah Smith",
        "subject": "Mathematics",
        "code": "MATH-101",
        "year": "2025"
    }

# Store all created tests here
if 'all_tests' not in st.session_state:
    st.session_state['all_tests'] = []

# Store the current test being created/edited
if 'current_test_builder' not in st.session_state:
    st.session_state['current_test_builder'] = {
        "test_id": str(uuid.uuid4())[:8],
        "test_name": "",
        "total_marks": 20,
        "questions": {} # Dictionary: { "Q1": { "max_marks": 5, "key_points": [] } }
    }

# -----------------------------------------------------------------------------
# 3. SIDEBAR: PROFILE & ACTIONS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
    st.title("Teacher Profile")
    
    # Editable Profile
    st.session_state['teacher_profile']['name'] = st.text_input("Name", st.session_state['teacher_profile']['name'])
    st.session_state['teacher_profile']['subject'] = st.text_input("Subject", st.session_state['teacher_profile']['subject'])
    st.session_state['teacher_profile']['code'] = st.text_input("Course Code", st.session_state['teacher_profile']['code'])
    st.session_state['teacher_profile']['year'] = st.text_input("Year", st.session_state['teacher_profile']['year'])
    
    st.divider()
    if st.button("🚪 Logout", use_container_width=True):
        st.switch_page("Home.py")

# -----------------------------------------------------------------------------
# 4. MAIN LAYOUT
# -----------------------------------------------------------------------------
st.title("👨‍🏫 Teacher Dashboard")
st.caption(f"Manage Assessments for **{st.session_state['teacher_profile']['subject']} ({st.session_state['teacher_profile']['code']})**")

tab_create, tab_manage = st.tabs(["➕ Create Assessment", "📂 Manage Assessments"])

# =============================================================================
# TAB 1: CREATE TEST & RUBRIC BUILDER
# =============================================================================
with tab_create:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("1. Test Details")
        with st.container(border=True):
            t_name = st.text_input("Test Name", placeholder="e.g. Calculus Mid-Term", key="t_name_in")
            t_marks = st.number_input("Total Marks", min_value=1, value=20, key="t_marks_in")
            
            # Update State
            st.session_state['current_test_builder']['test_name'] = t_name
            st.session_state['current_test_builder']['total_marks'] = t_marks

        st.subheader("2. Select Question")
        with st.container(border=True):
            # Dynamic Question Selector
            q_num = st.number_input("How many questions?", min_value=1, max_value=20, value=1)
            current_q_id = st.selectbox("Editing Question:", [f"Q{i}" for i in range(1, q_num + 1)])
            
            # Initialize this question in state if not exists
            if current_q_id not in st.session_state['current_test_builder']['questions']:
                st.session_state['current_test_builder']['questions'][current_q_id] = {
                    "question_id": current_q_id,
                    "max_marks": 5,
                    "key_points": []
                }
            
            # Set Marks for this specific question
            q_marks = st.number_input(f"Marks for {current_q_id}", min_value=1, 
                                      value=st.session_state['current_test_builder']['questions'][current_q_id]["max_marks"])
            st.session_state['current_test_builder']['questions'][current_q_id]["max_marks"] = q_marks

    # --- RUBRIC BUILDER (The Core Logic) ---
    with col2:
        st.subheader(f"3. Rubric for {current_q_id}")
        st.info("Define the key evaluation criteria for this question.")
        
        # Access current question data
        curr_q_data = st.session_state['current_test_builder']['questions'][current_q_id]
        
        # --- FORM TO ADD NEW KEY POINT ---
        # --- ADD NEW KEY POINT (Dynamic UI - No Form used to allow immediate updates) ---
        with st.expander("➕ Add New Key Point", expanded=True):
            # 1. Concept & Marks
            c_a, c_b = st.columns([2, 1])
            with c_a:
                kp_concept = st.text_input("Concept / Description", placeholder="e.g. Power rule logic", key=f"con_{current_q_id}")
            with c_b:
                kp_marks = st.number_input("Marks", min_value=0.5, step=0.5, value=1.0, key=f"mk_{current_q_id}")

            # 2. Modality Selection (Changing this now triggers an immediate UI update)
            kp_type = st.selectbox(
                "Expected Response Type", 
                ["Text / Theory", "Equation / Math", "Flowchart / Diagram", "Final Answer"],
                key=f"type_{current_q_id}"
            )
            
            # 3. Dynamic Fields based on Selection
            evidence_phrases = ""
            expected_eq = ""
            expected_final = ""
            uploaded_flowchart = None

            if kp_type == "Text / Theory":
                evidence_phrases = st.text_area(
                    "Evidence Phrases (comma separated)", 
                    placeholder="e.g. integration by parts, substitution method",
                    key=f"evi_{current_q_id}"
                )
                st.caption("The AI looks for these keywords or semantic equivalents.")
                
            elif kp_type == "Equation / Math":
                expected_eq = st.text_input(
                    "Expected Equation", 
                    placeholder="e.g. ∫ 2x dx = x^2 + C",
                    key=f"eqn_{current_q_id}"
                )
                st.caption("Supports LaTeX format.")

            elif kp_type == "Final Answer":
                expected_final = st.text_input(
                    "Expected Final Value", 
                    placeholder="e.g. x^2 + C or 42",
                    key=f"fin_{current_q_id}"
                )
            
            elif kp_type == "Flowchart / Diagram":
                st.info("ℹ️ Upload the **Answer Key** image/PDF for the flowchart logic.")
                uploaded_flowchart = st.file_uploader(
                    "Upload Solution Diagram", 
                    type=['png', 'jpg', 'jpeg', 'pdf'], 
                    key=f"file_{current_q_id}"
                )

            # 4. Add Button (Standard button triggers action immediately)
            if st.button("Add Key Point", type="primary", key=f"btn_{current_q_id}"):
                if not kp_concept:
                    st.error("Concept is required.")
                else:
                    # Construct Key Point Object
                    new_kp = {
                        "id": f"k{len(curr_q_data['key_points']) + 1}",
                        "concept": kp_concept,
                        "marks": kp_marks,
                        "acceptable_modalities": []
                    }

                    # Map UI Type to Backend Modality
                    if kp_type == "Text / Theory":
                        new_kp["acceptable_modalities"] = ["text"]
                        new_kp["evidence_phrases"] = [p.strip() for p in evidence_phrases.split(",") if p.strip()]
                    elif kp_type == "Equation / Math":
                        new_kp["acceptable_modalities"] = ["equation"]
                        new_kp["expected_equation"] = expected_eq
                    elif kp_type == "Final Answer":
                        new_kp["acceptable_modalities"] = ["final_answer", "equation"]
                        new_kp["expected_final_answer"] = expected_final
                    elif kp_type == "Flowchart / Diagram":
                        if not uploaded_flowchart:
                            st.error("Please upload the flowchart image/PDF.")
                            st.stop()
                        
                        new_kp["acceptable_modalities"] = ["flowchart"]
                        new_kp["type"] = "flowchart_analysis"
                        new_kp["image_uploaded"] = True
                        new_kp["filename"] = uploaded_flowchart.name
                        # NOTE: In production, save 'uploaded_flowchart' to a 'temp/' folder here

                    curr_q_data['key_points'].append(new_kp)
                    st.success("Key Point Added Successfully!")
                    st.rerun()

        # --- DISPLAY ADDED KEY POINTS ---
        st.markdown("#### Defined Criteria")
        
        if not curr_q_data['key_points']:
            st.caption("No key points added yet.")
        else:
            total_kp_score = 0
            for idx, kp in enumerate(curr_q_data['key_points']):
                total_kp_score += kp['marks']
                
                # Card Layout for existing points
                with st.container():
                    col_info, col_del = st.columns([0.9, 0.1])
                    with col_info:
                        st.markdown(f"""
                        <div class="keypoint-card">
                            <div class="keypoint-header">{kp['id']}: {kp['concept']} ({kp['marks']} marks)</div>
                            <div class="keypoint-meta">Type: {kp['acceptable_modalities']}</div>
                            {f'<div class="keypoint-meta">Expected: {kp.get("expected_equation") or kp.get("expected_final_answer") or kp.get("evidence_phrases")}</div>' if "flowchart" not in kp['acceptable_modalities'] else '<div class="keypoint-meta">📷 Image Reference</div>'}
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col_del:
                        if st.button("🗑️", key=f"del_{current_q_id}_{idx}"):
                            curr_q_data['key_points'].pop(idx)
                            st.rerun()
            
            # Marks Validation
            if total_kp_score != curr_q_data['max_marks']:
                st.warning(f"⚠️ Marks Mismatch: Key points total **{total_kp_score}**, but Question Marks set to **{curr_q_data['max_marks']}**.")
            else:
                st.success(f"✅ Marks Matched: {total_kp_score}/{curr_q_data['max_marks']}")

    # --- SAVE TEST BUTTON ---
    st.divider()
    if st.button("💾 Save & Publish Test", type="primary", use_container_width=True):
        if not st.session_state['current_test_builder']['test_name']:
            st.error("Please enter a Test Name.")
        else:
            # Convert Dictionary to List structure for Final JSON
            final_questions_list = []
            for qid, qdata in st.session_state['current_test_builder']['questions'].items():
                final_questions_list.append(qdata)
            
            final_test_object = {
                "test_id": st.session_state['current_test_builder']['test_id'],
                "test_name": st.session_state['current_test_builder']['test_name'],
                "subject": st.session_state['teacher_profile']['subject'],
                "total_marks": st.session_state['current_test_builder']['total_marks'],
                "rubric": final_questions_list # This is the array of question objects (rubric7 format)
            }
            
            st.session_state['all_tests'].append(final_test_object)
            st.success("Test Saved Successfully!")
            st.json(final_test_object) # Show the JSON payload

# =============================================================================
# TAB 2: MANAGE ASSESSMENTS
# =============================================================================
with tab_manage:
    st.subheader("📂 Existing Assessments")
    
    if not st.session_state['all_tests']:
        st.info("No tests created yet.")
    else:
        # Create a dataframe for cleaner view
        df_tests = pd.DataFrame(st.session_state['all_tests'])
        
        for index, test in enumerate(st.session_state['all_tests']):
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                with c1:
                    st.markdown(f"### {test['test_name']}")
                    st.caption(f"ID: {test['test_id']} | Questions: {len(test['rubric'])}")
                with c2:
                    st.markdown(f"**Marks:** {test['total_marks']}")
                with c3:
                    if st.button("View JSON", key=f"view_{index}"):
                        st.json(test['rubric'])
                with c4:
                    if st.button("🗑️ Delete", key=f"del_test_{index}"):
                        st.session_state['all_tests'].pop(index)
                        st.rerun()