import streamlit as st
import pandas as pd
import json
import uuid
from PIL import Image

# --- IMPORT BACKEND HANDLERS (Moved to top) ---
try:
    from backend.db_handler import get_submissions_for_teacher, load_db, save_db
    from backend.master_grader import auto_grade_submission
except ImportError:
    # Fallback to prevent crash if backend files aren't ready yet
    def get_submissions_for_teacher(): return []
    def load_db(): return {}
    def save_db(data): pass
    def auto_grade_submission(ans, rubric): return []

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

if 'all_tests' not in st.session_state:
    st.session_state['all_tests'] = []

if 'current_test_builder' not in st.session_state:
    st.session_state['current_test_builder'] = {
        "test_id": str(uuid.uuid4())[:8],
        "test_name": "",
        "total_marks": 20,
        "questions": {} 
    }

# -----------------------------------------------------------------------------
# 3. SIDEBAR: PROFILE & ACTIONS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
    st.title("Teacher Profile")
    
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

# ✅ DEFINING ALL 3 TABS AT ONCE HERE
tab_create, tab_manage, tab_review = st.tabs(["➕ Create Assessment", "📂 Manage Assessments", "📝 Review Submissions"])

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
            
            st.session_state['current_test_builder']['test_name'] = t_name
            st.session_state['current_test_builder']['total_marks'] = t_marks

        st.subheader("2. Select Question")
        with st.container(border=True):
            q_num = st.number_input("How many questions?", min_value=1, max_value=20, value=1)
            current_q_id = st.selectbox("Editing Question:", [f"Q{i}" for i in range(1, q_num + 1)])
            
            if current_q_id not in st.session_state['current_test_builder']['questions']:
                st.session_state['current_test_builder']['questions'][current_q_id] = {
                    "question_id": current_q_id,
                    "max_marks": 5,
                    "key_points": []
                }
            
            q_marks = st.number_input(f"Marks for {current_q_id}", min_value=1, 
                                      value=st.session_state['current_test_builder']['questions'][current_q_id]["max_marks"])
            st.session_state['current_test_builder']['questions'][current_q_id]["max_marks"] = q_marks

    # --- RUBRIC BUILDER ---
    with col2:
        st.subheader(f"3. Rubric for {current_q_id}")
        st.info("Define the key evaluation criteria for this question.")
        
        curr_q_data = st.session_state['current_test_builder']['questions'][current_q_id]
        
        with st.expander("➕ Add New Key Point", expanded=True):
            c_a, c_b = st.columns([2, 1])
            with c_a:
                kp_concept = st.text_input("Concept / Description", placeholder="e.g. Power rule logic", key=f"con_{current_q_id}")
            with c_b:
                kp_marks = st.number_input("Marks", min_value=0.5, step=0.5, value=1.0, key=f"mk_{current_q_id}")

            kp_type = st.selectbox(
                "Expected Response Type", 
                ["Text / Theory", "Equation / Math", "Flowchart / Diagram", "Final Answer"],
                key=f"type_{current_q_id}"
            )
            
            evidence_phrases = ""
            expected_eq = ""
            expected_final = ""
            uploaded_flowchart = None

            if kp_type == "Text / Theory":
                evidence_phrases = st.text_area("Evidence Phrases (comma separated)", placeholder="e.g. integration by parts", key=f"evi_{current_q_id}")
                st.caption("The AI looks for these keywords or semantic equivalents.")
                
            elif kp_type == "Equation / Math":
                expected_eq = st.text_input("Expected Equation", placeholder="e.g. ∫ 2x dx = x^2 + C", key=f"eqn_{current_q_id}")
                st.caption("Supports LaTeX format.")

            elif kp_type == "Final Answer":
                expected_final = st.text_input("Expected Final Value", placeholder="e.g. x^2 + C or 42", key=f"fin_{current_q_id}")
            
            elif kp_type == "Flowchart / Diagram":
                st.info("ℹ️ Upload the **Answer Key** image/PDF for the flowchart logic.")
                uploaded_flowchart = st.file_uploader("Upload Solution Diagram", type=['png', 'jpg', 'jpeg', 'pdf'], key=f"file_{current_q_id}")

            if st.button("Add Key Point", type="primary", key=f"btn_{current_q_id}"):
                if not kp_concept:
                    st.error("Concept is required.")
                else:
                    new_kp = {
                        "id": f"k{len(curr_q_data['key_points']) + 1}",
                        "concept": kp_concept,
                        "marks": kp_marks,
                        "acceptable_modalities": []
                    }

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

                    curr_q_data['key_points'].append(new_kp)
                    st.success("Key Point Added Successfully!")
                    st.rerun()

        st.markdown("#### Defined Criteria")
        
        if not curr_q_data['key_points']:
            st.caption("No key points added yet.")
        else:
            total_kp_score = 0
            for idx, kp in enumerate(curr_q_data['key_points']):
                total_kp_score += kp['marks']
                with st.container():
                    col_info, col_del = st.columns([0.9, 0.1])
                    with col_info:
                        st.markdown(f"""
                        <div class="keypoint-card">
                            <div class="keypoint-header">{kp['id']}: {kp['concept']} ({kp['marks']} marks)</div>
                            <div class="keypoint-meta">Type: {kp['acceptable_modalities']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_del:
                        if st.button("🗑️", key=f"del_{current_q_id}_{idx}"):
                            curr_q_data['key_points'].pop(idx)
                            st.rerun()
            
            if total_kp_score != curr_q_data['max_marks']:
                st.warning(f"⚠️ Marks Mismatch: Key points total **{total_kp_score}**, but Question Marks set to **{curr_q_data['max_marks']}**.")
            else:
                st.success(f"✅ Marks Matched: {total_kp_score}/{curr_q_data['max_marks']}")

    st.divider()
    if st.button("💾 Save & Publish Test", type="primary", use_container_width=True):
        if not st.session_state['current_test_builder']['test_name']:
            st.error("Please enter a Test Name.")
        else:
            final_questions_list = []
            for qid, qdata in st.session_state['current_test_builder']['questions'].items():
                final_questions_list.append(qdata)
            
            final_test_object = {
                "test_id": st.session_state['current_test_builder']['test_id'],
                "test_name": st.session_state['current_test_builder']['test_name'],
                "subject": st.session_state['teacher_profile']['subject'],
                "total_marks": st.session_state['current_test_builder']['total_marks'],
                "rubric": final_questions_list
            }
            
            # Save to Session State AND Database
            st.session_state['all_tests'].append(final_test_object)
            
            # Mock saving to DB.json
            db = load_db()
            db['tests'].append(final_test_object)
            save_db(db)
            
            st.success("Test Saved & Published Successfully!")
            st.json(final_test_object)

# =============================================================================
# TAB 2: MANAGE ASSESSMENTS
# =============================================================================
with tab_manage:
    st.subheader("📂 Existing Assessments")
    
    if not st.session_state['all_tests']:
        st.info("No tests created yet.")
    else:
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
# =============================================================================
# TAB 3: REVIEW SUBMISSIONS (ROBUST & CRASH-PROOF)
# =============================================================================
with tab_review:
    st.subheader("Student Submissions")
    
    # --- 1. LOAD DATABASE & DIAGNOSTICS ---
    db = load_db()
    
    # Debugging: Show DB Status in Sidebar (Optional)
    with st.sidebar.expander("🛠️ Database Debugger"):
        st.write(f"**Tests Found:** {len(db.get('tests', []))}")
        st.write(f"**Submissions:** {len(db.get('submissions', []))}")
        if st.button("🔄 Force Reload DB"):
            st.cache_data.clear()
            st.rerun()

    # --- 2. SELECT TEST RUBRIC ---
    # This fixes the "IndexError" by forcing a valid selection
    available_tests = db.get("tests", [])
    
    if not available_tests:
        st.error("❌ No Test Rubrics found in Database!")
        st.warning("Please go to the 'Create Assessment' tab and click 'Save & Publish Test' first.")
        st.stop() # Stop execution here to prevent crash
    
    # Create a mapping for the dropdown: "Test Name (ID)" -> Test Object
    test_options = {f"{t['test_name']} ({t['test_id']})": t for t in available_tests}
    selected_test_name = st.selectbox("Select Test to Grade Against:", list(test_options.keys()))
    active_test = test_options[selected_test_name]

    st.info(f"ℹ️ Grading against rubric: **{active_test['test_name']}** (Total Marks: {active_test['total_marks']})")
    
    # --- 3. FETCH SUBMISSIONS ---
    submissions = db.get("submissions", [])
    
    if not submissions:
        st.info("No student submissions received yet.")
    else:
        for i, sub in enumerate(submissions):
            with st.expander(f"🎓 Student: {sub.get('student_name', 'Unknown')} ({sub.get('student_id', 'N/A')})"):
                
                # Check status
                is_graded = "graded_result" in sub and sub['graded_result']
                
                # --- A: AUTO-GRADE ACTION ---
                if not is_graded:
                    st.warning("⚠️ Status: Pending Grading")
                    
                    if st.button(f"⚡ Auto-Grade Submission", key=f"grade_{i}"):
                        with st.spinner("Running AI Evaluation Models..."):
                            try:
                                # Call the Master Grader
                                results = auto_grade_submission(sub['answers'], active_test)
                                
                                # Update Database
                                # We reload DB to ensure we have the latest version before writing
                                current_db = load_db()
                                current_db['submissions'][i]['graded_result'] = results
                                save_db(current_db)
                                
                                st.success("Grading Complete!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error during grading: {e}")
                
                # --- B: REVIEW & EDIT ACTION ---
                else:
                    st.success("✅ Status: Graded")
                    
                    # Calculate Scores
                    total_score = sum([q['score'] for q in sub['graded_result']])
                    max_total = sum([q['max_score'] for q in sub['graded_result']])
                    
                    c1, c2 = st.columns(2)
                    c1.metric("Total Grade", f"{total_score} / {max_total}")
                    c2.progress(min(total_score / max_total, 1.0) if max_total > 0 else 0)
                    
                    st.divider()
                    
                    # Display Breakdown per Question
                    for q_idx, q_res in enumerate(sub['graded_result']):
                        st.markdown(f"#### 📄 Question: {q_res['question_id']} (Score: {q_res['score']})")
                        
                        # Editable Table for Marks
                        breakdown_df = pd.DataFrame(q_res['breakdown'])
                        
                        edited_df = st.data_editor(
                            breakdown_df,
                            column_config={
                                "awarded_marks": st.column_config.NumberColumn("Marks Awarded", min_value=0, max_value=10, step=0.5),
                                "reason": st.column_config.TextColumn("Feedback / Reason", width="large"),
                                "key_id": st.column_config.TextColumn("Criteria ID", disabled=True),
                                "criteria": st.column_config.TextColumn("Criteria", disabled=True)
                            },
                            key=f"edit_grid_{i}_{q_idx}",
                            use_container_width=True
                        )
                        
                        if st.button("💾 Update Score", key=f"save_{i}_{q_idx}"):
                            new_breakdown = edited_df.to_dict('records')
                            new_score = sum(item['awarded_marks'] for item in new_breakdown)
                            
                            # Persist Changes
                            current_db = load_db()
                            current_db['submissions'][i]['graded_result'][q_idx]['breakdown'] = new_breakdown
                            current_db['submissions'][i]['graded_result'][q_idx]['score'] = new_score
                            save_db(current_db)
                            
                            st.toast("Score Updated Successfully!", icon="✅")
                            st.rerun()