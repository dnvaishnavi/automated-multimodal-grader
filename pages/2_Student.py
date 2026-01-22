import streamlit as st
from PIL import Image
import io
import fitz  # PyMuPDF
import base64
import re
import json
import pandas as pd
from openai import OpenAI

# IMPORT THE DATABASE HANDLER
try:
    # Added load_db here 
    from backend.db_handler import submit_student_answers, load_db
except ImportError:
    st.error("⚠️ Error: Could not import 'backend/db_handler.py'. Make sure the file exists.")
    st.stop()

# -----------------------------------------------------------------------------
# 1. BACKEND LOGIC
# -----------------------------------------------------------------------------

def get_openai_client():
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    if not api_key:
        st.error("⚠️ OpenRouter API Key missing in secrets.toml")
        st.stop()
    
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

def pdf_to_images(pdf_file, dpi=200):
    """Converts uploaded PDF file (bytes) to PIL Images."""
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)
    return images

def image_to_base64(image: Image.Image):
    """Converts PIL Image to Base64 string."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def clean_json_text(text):
    """Cleans Markdown code blocks from LLM response."""
    text = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)
    return text.strip()

def extract_answer_obj_from_image(image: Image.Image, question_id: str):
    """Sends image to LLM to extract student answer as JSON."""
    client = get_openai_client()
    img_base64 = image_to_base64(image)

    prompt = f"""
    You are an academic answer extractor.
    The image contains a QUESTION and its ANSWER.

    TASK:
    1. Extract ONLY the student's answer for Question ID: {question_id}.
    2. Separate content into:
       "text": ["List all and any sentences or text explanations written by the student.",
            "Split distinct points into separate strings."],
       "equations": [" - Write ALL chemical formulas and equations in STANDARD ASCII TEXT.
        - DO NOT use Unicode subscripts or superscripts.
        - Convert subscripts explicitly to numbers.

      Examples:
        H₂SO₄ → H2SO4
        CH₃COOH → CH3COOH
        C₂H₅OH → C2H5OH
        H₂O → H2O
      Use standard text representation (e.g., 'x^2 + 2x = 5', 'H2 + O2 -> H2O').
      - Use '->' for reactions (do NOT use →).
      - If a catalyst is written above the arrow, format as:
          Reactants -(<catalyst that is written above arrow in equation>)-> Products
      - Write ions as:
          Fe3+, Fe2+, e-, Fe3e+
      - Preserve equation structure, but normalize symbols.

      If the student writes unclear chemistry, make the closest reasonable interpretation."],
       "flowcharts/graph": [" Analyze the flowchart carefully.
          If some text is unclear, make your best reasonable guess. " return in format:
            {{
                "nodes": [{{"id": "n1", "text": "Start", "shape": "oval/rect/diamond"}}],
                "edges": [{{"source": "n1", "target": "n2", "label": "Yes/No"}}]
            }}
       ],
       "final_answer": "Extract final result (e.g., 'x=5'). Return null if not found."

    3. Do NOT hallucinate. If section is empty, return empty list [].
    4. OUTPUT STRICT JSON ONLY.

    {{
      "question_id": "{question_id}",
      "text": [],
      "equations": [],
      "flowcharts": [],
      "final_answer": null
    }}
    """

    try:
        response = client.chat.completions.create(
            model="qwen/qwen-2.5-vl-7b-instruct:free",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                    ]
                }
            ],
            temperature=0
        )
        raw_text = response.choices[0].message.content
        cleaned = clean_json_text(raw_text)
        return json.loads(cleaned)
    except Exception as e:
        return {"error": str(e), "question_id": question_id}

# -----------------------------------------------------------------------------
# 2. PAGE CONFIGURATION & STYLING
# -----------------------------------------------------------------------------

st.set_page_config(page_title="Student Dashboard", page_icon="🎓", layout="wide")

st.markdown("""
<style>
    .student-header { font-size: 2.2rem; font-weight: 800; color: #333; margin-bottom: 0px; }
    .sub-header { font-size: 1rem; color: #666; margin-bottom: 20px; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3rem; }
    .success-box { padding: 15px; background-color: #d4edda; color: #155724; border-radius: 5px; margin-bottom: 10px; }
    .json-box { background-color: #f8f9fa; border: 1px solid #ddd; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. SIDEBAR & SESSION
# -----------------------------------------------------------------------------
if 'student_name' not in st.session_state: st.session_state['student_name'] = "Alex Doe"
if 'student_id' not in st.session_state: st.session_state['student_id'] = "ST-2025-001"
if 'extracted_data' not in st.session_state: st.session_state['extracted_data'] = []

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135810.png", width=80)
    st.title(f"Hi, {st.session_state['student_name']}")
    st.write(f"**ID:** {st.session_state['student_id']}")
    st.divider()
    if st.button("🚪 Logout"):
        st.switch_page("Home.py")

# -----------------------------------------------------------------------------
# 4. MAIN CONTENT
# -----------------------------------------------------------------------------

# Create Tabs
tab_submit, tab_results = st.tabs(["📤 Submit Assignment", "🏆 View Results"])

# =============================================================================
# TAB 1: YOUR EXISTING CODE (Wrapped)
# =============================================================================
with tab_submit:
    # --- 1. SELECT EXAM (NEW SNIPPET) ---
    # Load available tests from the database
    db = load_db()
    available_tests = db.get("tests", [])

    if not available_tests:
        st.warning("⚠️ No active exams found. Please ask your teacher to publish a test.")
        st.stop()
    else:
        # Create a dictionary: "Test Name" -> "Test ID"
        test_options = {f"{t['test_name']}": t['test_id'] for t in available_tests}
        selected_test_name = st.selectbox("Select Exam:", list(test_options.keys()))
        selected_test_id = test_options[selected_test_name]

        st.markdown(f'<p class="sub-header">Submit work for: <strong>{selected_test_name}</strong></p>', unsafe_allow_html=True)
        st.markdown('<p class="student-header">📤 Submit Assignment</p>', unsafe_allow_html=True)
        st.markdown('<p class="sub-header">Upload your handwritten answer script (PDF or Images) for AI analysis.</p>', unsafe_allow_html=True)

        col1, col2 = st.columns([1, 1], gap="large")

        # --- LEFT COLUMN: UPLOAD ---
        with col1:
            with st.container(border=True):
                st.subheader("1. Upload File")
                uploaded_file = st.file_uploader("Choose a file", type=['pdf', 'png', 'jpg', 'jpeg'])

                # Helper: If image, ask for Question ID (Since images don't have page numbers)
                q_id_input = "Q1"
                if uploaded_file and uploaded_file.type != "application/pdf":
                    q_id_input = st.text_input("Which Question is this?", value="Q1", help="e.g. Q1, Q2, Q3")

                if uploaded_file:
                    if st.button("🚀 Process & Extract Answers", type="primary"):
                        st.session_state['extracted_data'] = [] # Clear previous

                        with st.spinner("🤖 Reading handwriting, diagrams, and equations..."):
                            try:
                                extracted_results = []
                                
                                # CASE A: PDF Processing (Multi-page)
                                if uploaded_file.type == "application/pdf":
                                    images = pdf_to_images(uploaded_file)
                                    progress_bar = st.progress(0)
                                    
                                    for i, img in enumerate(images):
                                        # Assumption: Page 1 = Q1, Page 2 = Q2, etc.
                                        current_qid = f"Q{i+1}"
                                        st.toast(f"Processing Page {i+1} ({current_qid})...")
                                        
                                        data = extract_answer_obj_from_image(img, current_qid)
                                        extracted_results.append(data)
                                        progress_bar.progress((i + 1) / len(images))
                                        
                                    progress_bar.empty()
                                
                                # CASE B: Image Processing (Single Question)
                                else:
                                    image = Image.open(uploaded_file)
                                    data = extract_answer_obj_from_image(image, q_id_input)
                                    extracted_results.append(data)
                                
                                # Save to session
                                st.session_state['extracted_data'] = extracted_results
                                st.success("✅ Extraction Complete!")
                                st.rerun()

                            except Exception as e:
                                st.error(f"Error during processing: {e}")

        # --- RIGHT COLUMN: PREVIEW & RESULTS ---
        # --- RIGHT COLUMN: PREVIEW & EDIT ---
        with col2:
            c_head, c_tog = st.columns([0.7, 0.3])
            with c_head:
                st.subheader("2. AI Analysis Result")
            with c_tog:
                # Toggle to switch between View and Edit modes
                edit_mode = st.toggle("✏️ Enable Editing", value=False)

            if not st.session_state['extracted_data']:
                st.info("👈 Upload a file and click 'Process' to see the extracted data here.")
                
                # Placeholder Image
                st.markdown("""
                <div style="border: 2px dashed #ddd; padding: 40px; text-align: center; color: #aaa; border-radius: 10px;">
                    📄 Extracted text, equations & flowcharts will appear here.
                </div>
                """, unsafe_allow_html=True)

            else:
                # TABS for multiple extracted answers (e.g. Q1, Q2 from PDF)
                tabs = st.tabs([f"📄 {item.get('question_id', 'Unknown')}" for item in st.session_state['extracted_data']])
                
                for i, tab in enumerate(tabs):
                    # We use a direct reference to the list item so updates persist in session_state
                    data = st.session_state['extracted_data'][i]
                    
                    with tab:
                        if "error" in data:
                            st.error(f"Failed to extract: {data['error']}")
                        else:
                            # =========================================================
                            # 🅰️ VIEW MODE (Your Original Code)
                            # =========================================================
                            if not edit_mode:
                                with st.container(border=True):
                                    st.caption("Values below are Read-Only. Toggle 'Enable Editing' above to fix mistakes.")
                                    st.markdown(f"**Question ID:** `{data.get('question_id')}`")
                                    
                                    # Text
                                    if data.get("text"):
                                        st.markdown("##### 📝 Text Content")
                                        for line in data["text"]:
                                            st.write(f"- {line}")
                                    
                                    # Equations
                                    if data.get("equations"):
                                        st.markdown("##### 🧮 Equations")
                                        for eq in data["equations"]:
                                            st.latex(eq) 
                                            st.caption(f"Raw: `{eq}`")

                                    # Flowcharts
                                    if data.get("flowcharts"):
                                        st.markdown("##### 🔀 Flowcharts Detected")
                                        st.warning(f"Found {len(data['flowcharts'])} flowchart structure(s).")
                                    
                                    # Final Answer
                                    if data.get("final_answer"):
                                        st.markdown("##### 🏁 Final Answer")
                                        st.success(data["final_answer"])
                                
                                with st.expander("🔍 View Raw JSON Object"):
                                    st.json(data)

                            # =========================================================
                            # 🅱️ EDIT MODE (New Feature)
                            # =========================================================
                            else:
                                st.warning("⚠️ You are in Edit Mode. Changes are saved automatically.")
                                
                                # 1. EDIT TEXT (List of Strings)
                                st.markdown("##### 📝 Edit Text Points")
                                if "text" not in data or not isinstance(data["text"], list):
                                    data["text"] = []
                                
                                # We use DataEditor for easy list manipulation (Add/Delete rows)
                                df_text = pd.DataFrame(data["text"], columns=["Text Content"])
                                edited_text_df = st.data_editor(
                                    df_text, 
                                    num_rows="dynamic", 
                                    width="stretch",
                                    key=f"edit_text_{i}"
                                )
                                # Save back to session state
                                data["text"] = edited_text_df["Text Content"].dropna().astype(str).tolist()

                                # 2. EDIT EQUATIONS (List of Strings)
                                st.markdown("##### 🧮 Edit Equations (LaTeX/Math)")
                                if "equations" not in data or not isinstance(data["equations"], list):
                                    data["equations"] = []

                                df_eq = pd.DataFrame(data["equations"], columns=["Equation"])
                                edited_eq_df = st.data_editor(
                                    df_eq, 
                                    num_rows="dynamic", 
                                    width="stretch",
                                    key=f"edit_eq_{i}"
                                )
                                data["equations"] = edited_eq_df["Equation"].dropna().astype(str).tolist()

                                # 3. EDIT FINAL ANSWER (String)
                                st.markdown("##### 🏁 Edit Final Answer")
                                data["final_answer"] = st.text_input(
                                    "Final Result", 
                                    value=data.get("final_answer") or "",
                                    key=f"edit_final_{i}"
                                )

                                # 4. EDIT FLOWCHART (Raw JSON)
                                # Editing nodes/edges graphically is hard, so we edit the JSON structure directly.
                                if data.get("flowcharts"):
                                    st.markdown("##### 🔀 Edit Flowchart Data (JSON)")
                                    st.info("Edit the 'nodes' and 'edges' text directly below.")
                                    
                                    # Convert dict list to string for editing
                                    fc_str = json.dumps(data["flowcharts"], indent=2)
                                    edited_fc_str = st.text_area(
                                        "Flowchart JSON", 
                                        value=fc_str, 
                                        height=200,
                                        key=f"edit_fc_{i}"
                                    )
                                    
                                    # Try to save back if valid JSON
                                    try:
                                        data["flowcharts"] = json.loads(edited_fc_str)
                                    except json.JSONDecodeError:
                                        st.error("Invalid JSON format in Flowchart editor.")

                st.markdown("---")
                # Ensure we are submitting the LATEST session state data (which includes edits)
                if st.button("✅ Confirm & Submit for Grading", type="primary", use_container_width=True):            
                    submission_package = {
                        "student_name": st.session_state['student_name'],
                        "student_id": st.session_state['student_id'],
                        "test_id": selected_test_id, # <--- THIS LINKS THE EXAM
                        "answers": st.session_state['extracted_data'],
                        "status": "Submitted",
                        "graded_result": None 
                    }
                    
                    if submit_student_answers(submission_package):
                        st.balloons()
                        st.success(f"Submitted to {selected_test_name} successfully!")
                    else:
                        st.error("Failed to save submission.")

# =============================================================================
# TAB 2: VIEW RESULTS (NEW FEATURE)
# =============================================================================
with tab_results:
    st.subheader("🏆 Your Graded Results")
    
    # Load latest DB data
    db = load_db()
    current_student_id = st.session_state['student_id']
    
    # 1. Filter submissions for this specific student
    my_submissions = [s for s in db.get("submissions", []) if s.get("student_id") == current_student_id]
    
    if not my_submissions:
        st.info("You haven't submitted any assignments yet.")
    else:
        for sub in my_submissions:
            # 2. Get Test Info (Name & Published Status)
            test_id = sub.get("test_id")
            test_meta = next((t for t in db.get("tests", []) if t["test_id"] == test_id), None)
            
            if test_meta:
                test_name = test_meta.get("test_name", "Unknown Assessment")
                is_published = test_meta.get("published", False)
                
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    c1.markdown(f"### {test_name}")
                    
                    # 3. Check Publishing Status
                    if is_published:
                        if sub.get("graded_result"):
                            # Calculate Total Score
                            user_score = sum(q['score'] for q in sub['graded_result'])
                            total_max = sum(q['max_score'] for q in sub['graded_result'])
                            
                            c2.success("✅ Released")
                            c3.metric("Grade", f"{user_score} / {total_max}")
                            
                            # 4. Detailed Breakdown Expander
                            with st.expander("📄 View Feedback & Breakdown"):
                                for q_res in sub['graded_result']:
                                    st.markdown(f"**{q_res['question_id']}** ({q_res['score']} marks)")
                                    
                                    if 'breakdown' in q_res:
                                        for rule in q_res['breakdown']:
                                            status_icon = "✅" if rule['awarded_marks'] > 0 else "❌"
                                            st.caption(f"{status_icon} {rule['criteria']} — **{rule['awarded_marks']} marks**")
                                            if rule.get('reason'):
                                                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;*Feedback: {rule['reason']}*")
                                    st.divider()
                        else:
                            c2.warning("⏳ Grading in Progress")
                            c3.write("-- / --")
                            st.caption("Your teacher hasn't graded this yet.")
                    else:
                        c2.info("🔒 Results Hidden")
                        c3.write("-- / --")
                        st.caption("Grades will be available once the teacher publishes them.")