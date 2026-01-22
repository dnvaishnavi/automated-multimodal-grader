import streamlit as st
import pandas as pd
import json
import uuid
from PIL import Image

from backend.flowchart_pipeline import generate_json_from_image

# --- IMPORT BACKEND HANDLERS ---
try:
    from backend.db_handler import get_submissions_for_teacher, load_db, save_db
    from backend.master_grader import auto_grade_submission
    from backend.flowchart_pipeline import extract_teacher_graph
except ImportError as e:
    st.error(f"Backend Import Error: {e}")
    def get_submissions_for_teacher(): return []
    def load_db(): return {"tests": [], "submissions": []}
    def save_db(data): pass
    def auto_grade_submission(ans, rubric): return []
    def extract_teacher_graph(img, key): return {}

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Teacher Dashboard", page_icon="👨‍🏫", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
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
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #007bff;
        border-color: #007bff;
    }
    .status-submitted { color: #28a745; font-weight: bold; background-color: #d4edda; padding: 2px 8px; border-radius: 4px; }
    .grade-badge { font-weight: bold; color: #333; }
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
    db_data = load_db()
    st.session_state['all_tests'] = db_data.get("tests", [])

if 'current_test_builder' not in st.session_state:
    st.session_state['current_test_builder'] = {
        "test_id": str(uuid.uuid4())[:8],
        "test_name": "",
        "total_marks": 20,
        "questions": {} 
    }

# -----------------------------------------------------------------------------
# 3. HELPER FUNCTIONS (MODALS & DIALOGS)
# -----------------------------------------------------------------------------

# ✅ ADDED width="large" HERE
@st.dialog("🔍 Review & Verify Submission", width="large")
def review_submission_dialog(student_id, test_id):
    """
    Pop-up to view, grade, and edit a specific student's submission.
    """
    db = load_db()
    
    # 1. Fetch Submission and Test Data
    submission = next((s for s in db.get("submissions", []) 
                       if s["student_id"] == student_id and s["test_id"] == test_id), None)
    
    active_test = next((t for t in db.get("tests", []) if t["test_id"] == test_id), None)

    if not submission:
        st.error("Submission data not found.")
        return

    st.caption(f"Student: **{submission.get('student_name', student_id)}** | Test: **{active_test['test_name']}**")
    
    is_graded = submission.get("graded_result") is not None
    
    # --- A. AUTO-GRADE (IF NOT GRADED) ---
    if not is_graded:
        st.warning("⚠️ Status: Pending Grading")
        if st.button("⚡ Run Auto-Grader Now", key=f"dlg_grade_{student_id}"):
            with st.spinner("Running AI Analysis..."):
                try:
                    results = auto_grade_submission(submission['answers'], active_test)
                    
                    # Update DB
                    db = load_db()
                    for i, s in enumerate(db["submissions"]):
                        if s["student_id"] == student_id and s["test_id"] == test_id:
                            db["submissions"][i]["graded_result"] = results
                            break
                    save_db(db)
                    st.rerun()
                except Exception as e:
                    st.error(f"Grading Failed: {e}")

    # --- B. VIEW & EDIT SCORES (IF GRADED) ---
    else:
        # Calculate Scores
        total_score = sum([q['score'] for q in submission['graded_result']])
        max_total = sum([q['max_score'] for q in submission['graded_result']])
        
        c1, c2 = st.columns(2)
        c1.metric("Total Grade", f"{total_score} / {max_total}")
        c2.progress(min(total_score / max_total, 1.0) if max_total > 0 else 0)
        
        st.divider()
        
        # Display Breakdown per Question
        for q_idx, q_res in enumerate(submission['graded_result']):
            with st.container(border=True):
                st.markdown(f"#### 📄 {q_res['question_id']} (Score: {q_res['score']})")
                
                # Editable Table
                breakdown_df = pd.DataFrame(q_res['breakdown'])
                edited_df = st.data_editor(
                    breakdown_df,
                    column_config={
                        "awarded_marks": st.column_config.NumberColumn("Marks", min_value=0, max_value=10, step=0.5),
                        "reason": st.column_config.TextColumn("Feedback", width="large"),
                        "key_id": st.column_config.TextColumn("ID", disabled=True),
                        "criteria": st.column_config.TextColumn("Criteria", disabled=True)
                    },
                    key=f"dlg_edit_{student_id}_{q_idx}",
                    use_container_width=True
                )
                
                if st.button("💾 Update Score", key=f"dlg_save_{student_id}_{q_idx}"):
                    new_breakdown = edited_df.to_dict('records')
                    new_score = sum(item['awarded_marks'] for item in new_breakdown)
                    
                    # Update DB
                    db = load_db()
                    for i, s in enumerate(db["submissions"]):
                        if s["student_id"] == student_id and s["test_id"] == test_id:
                            db["submissions"][i]["graded_result"][q_idx]['breakdown'] = new_breakdown
                            db["submissions"][i]["graded_result"][q_idx]['score'] = new_score
                            break
                    save_db(db)
                    st.toast("Score Updated Successfully!", icon="✅")
                    st.rerun()

@st.dialog("✅ Assessment Published")
def publish_success_modal():
    st.write("The test has been successfully saved to the database.")
    st.write("It is now **safe to close this tab**.")
    st.markdown("---")
    if st.button("Create Another Assessment", type="primary"):
        st.rerun()


@st.dialog("📤 Upload for Student", width="large")
def upload_for_student_dialog(student_id, test_id):
    st.write(f"Uploading submission for **{student_id}**")
    st.info("ℹ️ This will extract answers from the image and save to the DB.")
    
    uploaded_file = st.file_uploader("Upload Answer Script", type=['png', 'jpg', 'jpeg'])
    
    if st.button("Submit Paper", type="primary"):
        if uploaded_file:
            try:
                api_key = st.secrets.get("GEMINI_API_KEY", "")
                if not api_key:
                    st.error("GEMINI_API_KEY not found.")
                    st.stop()

                img = Image.open(uploaded_file)
                with st.spinner("🤖 AI is reading the student's answer..."):
                    extracted_data = generate_json_from_image(img, "student", api_key)
                
                if not extracted_data:
                    st.error("Failed to extract data from image.")
                    st.stop()

                submission = {
                    "student_id": student_id,
                    "test_id": test_id,
                    "answers": [extracted_data],
                    "graded_result": None,
                    "student_name": student_id # Fallback name
                }
                
                db = load_db()
                db["submissions"] = [s for s in db.get("submissions", []) 
                                   if not (s["student_id"] == student_id and s.get("test_id") == test_id)]
                db["submissions"].append(submission)
                save_db(db)
                
                st.success("✅ Submission uploaded, extracted, and saved!")
                st.rerun()
            except Exception as e:
                st.error(f"Error processing file: {e}")
        else:
            st.error("Please select a file.")


@st.dialog("📝 Edit Assessment JSON", width="large")
def edit_json_dialog(test_index):
    test_data = st.session_state['all_tests'][test_index]
    test_id = test_data['test_id']
    st.caption(f"Editing: **{test_data['test_name']}**")
    current_json_str = json.dumps(test_data['rubric'], indent=4)
    edited_json_str = st.text_area("JSON Editor", value=current_json_str, height=500)
    
    col_cancel, col_save = st.columns([1, 1])
    with col_save:
        if st.button("💾 Save Changes", type="primary"):
            try:
                new_rubric = json.loads(edited_json_str)
                db = load_db()
                for t in db.get("tests", []):
                    if t["test_id"] == test_id:
                        t["rubric"] = new_rubric
                        break
                save_db(db)
                st.session_state['all_tests'][test_index]['rubric'] = new_rubric
                st.success("Saved!")
                st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")

def delete_test_from_db(test_index):
    target_id = st.session_state['all_tests'][test_index]['test_id']
    db = load_db()
    db["tests"] = [t for t in db["tests"] if t["test_id"] != target_id]
    save_db(db)
    st.session_state['all_tests'].pop(test_index)
    st.toast("Deleted!", icon="🗑️")
    st.rerun()

def bulk_grade_exam(test_id):
    db = load_db()
    active_test = next((t for t in db["tests"] if t["test_id"] == test_id), None)
    if not active_test: return
    
    count = 0
    with st.spinner("Batch Grading in Progress..."):
        for sub in db.get("submissions", []):
            if sub.get("test_id") == test_id and not sub.get("graded_result"):
                try:
                    sub["graded_result"] = auto_grade_submission(sub.get("answers", []), active_test)
                    count += 1
                except Exception as e:
                    print(f"Error grading {sub['student_id']}: {e}")
    
    save_db(db)
    if count > 0:
        st.toast(f"✅ Graded {count} papers.", icon="🚀")
    else:
        st.toast("No pending papers to grade.", icon="ℹ️")
    st.rerun()

def toggle_publish_status(test_id):
    db = load_db()
    status = False
    for t in db["tests"]:
        if t["test_id"] == test_id:
            t["published"] = not t.get("published", False)
            status = t["published"]
            break
    save_db(db)
    st.toast("Status updated!", icon="📢")
    st.rerun()

# -----------------------------------------------------------------------------
# 4. MAIN LAYOUT
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
    st.title("Teacher Profile")
    st.session_state['teacher_profile']['name'] = st.text_input("Name", st.session_state['teacher_profile']['name'])
    st.session_state['teacher_profile']['subject'] = st.text_input("Subject", st.session_state['teacher_profile']['subject'])
    if st.button("🚪 Logout", use_container_width=True):
        st.switch_page("Home.py")

st.title("👨‍🏫 Teacher Dashboard")

tab_create, tab_manage, tab_control = st.tabs(["➕ Create Assessment", "📂 Manage Assessments", "📝 Grade / Exam Control"])

# =============================================================================
# TAB 1: CREATE TEST
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

    with col2:
        st.subheader(f"3. Rubric for {current_q_id}")
        curr_q_data = st.session_state['current_test_builder']['questions'][current_q_id]
        
        with st.expander("➕ Add New Key Point", expanded=True):
            c_a, c_b = st.columns([2, 1])
            with c_a:
                kp_concept = st.text_input("Concept / Description", key=f"con_{current_q_id}")
            with c_b:
                kp_marks = st.number_input("Marks", min_value=0.5, step=0.5, value=1.0, key=f"mk_{current_q_id}")

            kp_type = st.selectbox("Response Type", ["Text / Theory", "Equation / Math", "Flowchart / Diagram", "Final Answer"], key=f"type_{current_q_id}")
            
            uploaded_flowchart = None
            evidence_phrases = ""
            expected_eq = ""
            expected_final = ""

            if kp_type == "Text / Theory":
                evidence_phrases = st.text_area("Evidence Phrases", key=f"evi_{current_q_id}")
            elif kp_type == "Equation / Math":
                expected_eq = st.text_input("Expected Equation", key=f"eqn_{current_q_id}")
            elif kp_type == "Final Answer":
                expected_final = st.text_input("Expected Final Value", key=f"fin_{current_q_id}")
            elif kp_type == "Flowchart / Diagram":
                st.info("ℹ️ Upload Answer Key")
                uploaded_flowchart = st.file_uploader("Upload Solution", type=['png', 'jpg'], key=f"file_{current_q_id}")
            
            if st.button("Add Key Point", type="primary", key=f"btn_{current_q_id}"):
                if not kp_concept:
                    st.error("Concept required")
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
                    
                    # --- FLOWCHART LOGIC (WITH SCALING) ---
                    elif kp_type == "Flowchart / Diagram":
                        if not uploaded_flowchart:
                            st.error("Upload a file first.")
                            st.stop()
                        
                        with st.spinner("🧠 Analyzing diagram..."):
                            try:
                                api_key = st.secrets.get("GEMINI_API_KEY", "")
                                teacher_response = extract_teacher_graph(uploaded_flowchart, api_key)
                                rules = teacher_response.get("key_points", [])
                                
                                if rules:
                                    # Marks Scaling Logic
                                    raw_total = sum(r.get("marks", 1) for r in rules)
                                    if raw_total > 0 and kp_marks > 0:
                                        factor = kp_marks / raw_total
                                        running = 0
                                        for i, r in enumerate(rules):
                                            if i == len(rules) - 1:
                                                r["marks"] = round(kp_marks - running, 3)
                                            else:
                                                val = round(r.get("marks", 1) * factor, 3)
                                                r["marks"] = val
                                                running += val
                                        st.toast(f"Scaled rules to match {kp_marks} marks.", icon="⚖️")
                                
                                new_kp["acceptable_modalities"] = ["flowchart"]
                                new_kp["type"] = "flowchart_analysis"
                                new_kp["evaluation_rules"] = rules
                            except Exception as e:
                                st.error(str(e)); st.stop()

                    curr_q_data['key_points'].append(new_kp)
                    st.success("Added!")
                    st.rerun()

        if curr_q_data['key_points']:
            total_kp = sum(kp['marks'] for kp in curr_q_data['key_points'])
            for idx, kp in enumerate(curr_q_data['key_points']):
                with st.container():
                    c_info, c_del = st.columns([0.9, 0.1])
                    with c_info:
                        st.markdown(f"""
                        <div class="keypoint-card">
                            <div class="keypoint-header">{kp['id']}: {kp['concept']} ({kp['marks']})</div>
                            <div class="keypoint-meta">{kp['acceptable_modalities']}</div>
                        </div>""", unsafe_allow_html=True)
                    with c_del:
                        if st.button("Delete", key=f"del_{current_q_id}_{idx}"):
                            curr_q_data['key_points'].pop(idx); st.rerun()
            
            if abs(total_kp - curr_q_data['max_marks']) > 0.01:
                st.warning(f"⚠️ Mismatch: Key points total **{total_kp}**, but Question Marks set to **{curr_q_data['max_marks']}**.")
            else:
                st.success("✅ Marks Matched")

    st.divider()
    if st.button("💾 Save & Publish Test", type="primary", use_container_width=True):
        if not st.session_state['current_test_builder']['test_name']:
            st.error("Test Name required.")
        else:
            final_obj = {
                "test_id": st.session_state['current_test_builder']['test_id'],
                "test_name": st.session_state['current_test_builder']['test_name'],
                "subject": st.session_state['teacher_profile']['subject'],
                "total_marks": st.session_state['current_test_builder']['total_marks'],
                "rubric": list(st.session_state['current_test_builder']['questions'].values())
            }
            
            st.session_state['all_tests'].append(final_obj)
            db = load_db()
            db['tests'].append(final_obj)
            save_db(db)
            
            # Reset ID for next test
            st.session_state['current_test_builder'] = {
                "test_id": str(uuid.uuid4())[:8],
                "test_name": "",
                "total_marks": 20,
                "questions": {} 
            }
            
            publish_success_modal()

# =============================================================================
# TAB 2: MANAGE ASSESSMENTS
# =============================================================================
with tab_manage:
    st.subheader("📂 Assessments")
    db = load_db()
    st.session_state['all_tests'] = db.get("tests", [])
    if not st.session_state['all_tests']: st.info("Empty")
    else:
        for idx, t in enumerate(st.session_state['all_tests']):
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                c1.markdown(f"**{t['test_name']}**"); c2.markdown(f"{t['total_marks']} marks")
                if c3.button("📝 Edit", key=f"v_{idx}"): edit_json_dialog(idx)
                if c4.button("🗑️ Delete", key=f"d_{idx}"): delete_test_from_db(idx)

# =============================================================================
# TAB 3: GRADE / EXAM CONTROL (Merged Logic)
# =============================================================================
with tab_control:
    st.subheader("🚀 Active Exam Control")
    
    # 1. Load Data from Real DB
    db = load_db()
    st.session_state['all_tests'] = db.get("tests", [])
    
    if not st.session_state['all_tests']:
        st.info("No exams created yet.")
    else:
        # --- SELECTOR ---
        test_opts = {f"{t['test_name']}": t['test_id'] for t in st.session_state['all_tests']}
        selected_label = st.selectbox("Select Exam:", list(test_opts.keys()))
        active_tid = test_opts[selected_label]
        
        active_test = next(t for t in st.session_state['all_tests'] if t['test_id'] == active_tid)
        
        # --- CONTROL BAR ---
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            if st.button("⚡ Grade All Pending", type="primary", use_container_width=True):
                bulk_grade_exam(active_tid)
        with c2:
            is_pub = active_test.get("published", False)
            btn_label = "Unpublish Results" if is_pub else "Publish Results"
            if st.button(f"📢 {btn_label}", use_container_width=True):
                toggle_publish_status(active_tid)
        with c3:
            if is_pub:
                st.success("✅ **Status: Live** (Students can see grades)")
            else:
                st.warning("🔒 **Status: Hidden** (Grading in progress)")

        st.divider()

        # --- STUDENT LIST ---
        test_submissions = [s for s in db.get("submissions", []) if s.get("test_id") == active_tid]
        
        if not test_submissions:
            st.info(f"No students have submitted work for '{selected_label}' yet.")
        else:
            cols = st.columns([1, 2, 1, 1, 2])
            headers = ["ID", "Name", "Status", "Grade", "Actions"]
            for c, h in zip(cols, headers): c.markdown(f"**{h}**")
            st.markdown("---")

            for sub in test_submissions:
                sid = sub.get("student_id", "Unknown")
                name = sub.get("student_name", "Unknown")
                is_graded = sub.get("graded_result") is not None
                
                grade_str = "-"
                if is_graded:
                    score = sum(q['score'] for q in sub['graded_result'])
                    max_score = sum(q['max_score'] for q in sub['graded_result'])
                    grade_str = f"{score} / {max_score}"

                c1, c2, c3, c4, c5 = st.columns([1, 2, 1, 1, 2])
                c1.write(sid)
                c2.write(name)
                
                with c3:
                    st.markdown('<span class="status-submitted">Submitted</span>', unsafe_allow_html=True)
                
                with c4:
                    st.markdown(f'<span class="grade-badge">{grade_str}</span>', unsafe_allow_html=True)
                
                with c5:
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("Upload", key=f"up_{sid}_{active_tid}"): 
                            upload_for_student_dialog(sid, active_tid)
                    with b2:
                        # --- VERIFY BUTTON OPENS REVIEW DIALOG ---
                        if st.button("Review", key=f"ver_{sid}_{active_tid}"):
                            review_submission_dialog(sid, active_tid)
                
                st.markdown("---")