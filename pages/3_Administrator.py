import streamlit as st
import pandas as pd
from backend.db_handler import load_db, assign_paper_to_teacher

st.set_page_config(page_title="Admin Console", page_icon="🛡️", layout="wide")

st.title("🛡️ Administrator Dashboard")
st.markdown("### 🚦 Assignment Mediator")

# --- LOAD DATA ---
db = load_db()
submissions = db.get("submissions", [])
tests = db.get("tests", [])
test_map = {t['test_id']: t['test_name'] for t in tests}

# --- TABS ---
tab_inbox, tab_status = st.tabs(["📥 Pending Assignment", "📊 Global Status"])

# --- TAB 1: ASSIGN PAPERS ---
with tab_inbox:
    st.info("ℹ️ Assign incoming student papers to a specific Teacher ID.")
    
    # Filter: Submissions that have NOT been assigned yet
    unassigned_subs = [s for s in submissions if not s.get("assigned_teacher_id")]

    if not unassigned_subs:
        st.success("✅ All submission have been assigned!", icon="🎉")
    else:
        for idx, sub in enumerate(unassigned_subs):
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                
                test_name = test_map.get(sub['test_id'], "Unknown Test")
                
                with c1:
                    st.markdown(f"**Student:** {sub.get('student_name', 'Unknown')}")
                    st.caption(f"ID: `{sub['student_id']}`")
                
                with c2:
                    st.markdown(f"**Exam:** {test_name}")
                    st.caption(f"Status: {sub.get('status', 'Submitted')}")

                with c3:
                    # Input for Teacher ID (Teacher must use this same ID in their dashboard)
                    t_id = st.text_input("Assign to Teacher ID:", placeholder="e.g. T-MATH-01", key=f"tid_{idx}")

                with c4:
                    st.write("") # Spacer
                    if st.button("👉 Assign", key=f"btn_{idx}", type="primary"):
                        if t_id:
                            assign_paper_to_teacher(sub['student_id'], sub['test_id'], t_id)
                            st.toast(f"Assigned to {t_id}!", icon="🚀")
                            st.rerun()
                        else:
                            st.error("Enter ID")

# --- TAB 2: MONITOR PROGRESS ---
with tab_status:
    if not submissions:
        st.write("No records found.")
    else:
        report_data = []
        for s in submissions:
            # Determine Status
            status = "Pending Admin"
            if s.get("graded_result"): status = "✅ Graded"
            elif s.get("assigned_teacher_id"): status = "⏳ With Teacher"

            # Calculate Score if graded
            score_display = "-"
            if s.get("graded_result"):
                total = sum(q['score'] for q in s['graded_result'])
                maxx = sum(q['max_score'] for q in s['graded_result'])
                score_display = f"{total} / {maxx}"

            report_data.append({
                "Student ID": s['student_id'],
                "Student Name": s.get('student_name'),
                "Test": test_map.get(s['test_id'], s['test_id']),
                "Assigned To": s.get("assigned_teacher_id", "—"),
                "Current Status": status,
                "Score": score_display
            })
        
        st.dataframe(pd.DataFrame(report_data), use_container_width=True)