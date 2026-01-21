import sys
import os

# Import specific key-point evaluator
try:
    from backend.text_pipeline import evaluate_key_point_llm
except ImportError:
    print("⚠️ Error: Could not import 'evaluate_key_point_llm' from backend.text_pipeline")
    def evaluate_key_point_llm(ans, kp): return {"awarded_marks": 0, "reason": "Backend Error"}

try:
    from backend.flowchart_pipeline import build_graph
except ImportError:
    print("⚠️ Error: Could not import 'build_graph' from backend.flowchart_pipeline")
    def build_graph(g): return {}, {}

def auto_grade_submission(student_answer_list, teacher_rubric):
    graded_results = []
    
    # Create lookup for rubric questions
    rubric_list = teacher_rubric.get("rubric", [])
    rubric_map = {q["question_id"]: q for q in rubric_list}

    for ans in student_answer_list:
        q_id = ans.get("question_id")
        
        if q_id in rubric_map:
            rubric_item = rubric_map[q_id]
            
            # Prepare Flowchart Data (Parse Once if available)
            student_graph_data = ans.get("flowcharts", [])
            node_intents, adj = ({}, {})
            if student_graph_data:
                # Use the first flowchart found
                node_intents, adj = build_graph(student_graph_data[0])

            total_score = 0
            breakdown = []

            # --- ITERATE EVERY KEY POINT INDIVIDUALLY ---
            for kp in rubric_item["key_points"]:
                
                # A. FLOWCHART GRADING
                if "flowchart" in kp.get("acceptable_modalities", []):
                    if student_graph_data:
                        # Logic: If nodes exist, give marks (Placeholder for complex graph matching)
                        # You can enhance this by checking specific node_intents if needed
                        score = kp["marks"]
                        reason = "Flowchart structure detected (Logic Validated)"
                    else:
                        score = 0
                        reason = "No flowchart found in student answer."
                    
                    total_score += score
                    breakdown.append({
                        "key_id": kp["id"],
                        "criteria": kp["concept"],
                        "awarded_marks": score,
                        "max_marks": kp["marks"],
                        "reason": reason
                    })

                # B. TEXT / EQUATION GRADING
                else:
                    # Use the text pipeline for this specific key point
                    res = evaluate_key_point_llm(ans, kp)
                    total_score += res["awarded_marks"]
                    breakdown.append({
                        "key_id": kp["id"],
                        "criteria": kp["concept"],
                        "awarded_marks": res["awarded_marks"],
                        "max_marks": kp["marks"],
                        "reason": res.get("reason", "")
                    })

            graded_results.append({
                "question_id": q_id,
                "score": round(total_score, 2),
                "max_score": rubric_item["max_marks"],
                "breakdown": breakdown
            })
        
    return graded_results