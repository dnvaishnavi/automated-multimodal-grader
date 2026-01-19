# ==========================================================
# FLOWCHART PIPELINE
# Image → JSON → HUMAN-EXAMINER CORRECT EVALUATION
# ==========================================================

import os
import re
import json
from collections import defaultdict, deque
from PIL import Image

from google import genai
from google.genai import types  # type: ignore

# ==========================================================
# CONFIGURATION & PROMPTS
# ==========================================================

MODEL_ID = "models/gemini-2.5-flash"

STUDENT_PROMPT = """
Analyze this flowchart carefully.

If some text is unclear, make your best reasonable guess.
DO NOT return an empty response.

Return ONLY a RAW JSON object (no markdown).

Schema:
{
  "question_id": "Q7",
  "student_id": "std_01",
  "graph": {
    "nodes": [
      {"id": "node_1", "text": "exact text", "shape": "oval/rect/diamond"}
    ],
    "edges": [
      {"source": "node_1", "target": "node_2", "label": "Yes/No"}
    ]
  }
}
"""

TEACHER_PROMPT = """
Analyze this correct flowchart carefully.

If some text is unclear, make your best reasonable guess.
DO NOT return an empty response.

Return ONLY a RAW JSON object (no markdown).

Schema:
{
  "question_id": "Q7",
  "max_marks": 5,
  "key_points": [
    {
      "id": "k1",
      "concept": "Start Node",
      "type": "node_check",
      "expected_text": "Start",
      "marks": 1
    }
  ]
}
"""

# ==========================================================
# ROBUST GEMINI RESPONSE EXTRACTION
# ==========================================================

def extract_text_from_response(response):
    # Case 1: shortcut
    if hasattr(response, "text") and response.text:
        return response.text.strip()

    # Case 2: candidates structure
    try:
        parts = response.candidates[0].content.parts
        texts = [p.text for p in parts if hasattr(p, "text") and p.text]
        return "\n".join(texts).strip()
    except Exception:
        return ""

# ==========================================================
# INTENT CLASSIFIER (HUMAN-EXAMINER LOGIC)
# ==========================================================

def normalize(t):
    return re.sub(r"\s+", " ", str(t).lower().strip())

def classify_intent(text):
    t = normalize(text)

    if any(k in t for k in ["start", "begin", "init"]):
        return "START"
    if any(k in t for k in ["end", "stop", "exit", "finish"]):
        return "END"
    if any(k in t for k in ["print", "output", "display", "show", "write"]):
        return "OUTPUT"
    if any(k in t for k in ["input", "read", "get", "scan", "enter"]):
        return "INPUT"

    if "++" in t or re.search(r"\w+\s*=\s*\w+\s*\+\s*1", t):
        return "INCREMENT"
    if "--" in t or re.search(r"\w+\s*=\s*\w+\s*-\s*1", t):
        return "DECREMENT"

    if re.search(r"[<>]=?|==|!=", t):
        return "CONDITION"
    if "=" in t:
        return "ASSIGNMENT"

    return "UNKNOWN"

# ==========================================================
# GRAPH UTILITIES
# ==========================================================

def build_graph(student_graph):
    intents = {}
    adj = defaultdict(list)

    for n in student_graph.get("nodes", []):
        intents[n["id"]] = classify_intent(n["text"])

    for e in student_graph.get("edges", []):
        adj[e["source"]].append(e["target"])

    return intents, adj

def has_path(start_nodes, target_nodes, adj):
    visited = set()
    q = deque(start_nodes)

    while q:
        cur = q.popleft()
        if cur in target_nodes:
            return True
        for nxt in adj.get(cur, []):
            if nxt not in visited:
                visited.add(nxt)
                q.append(nxt)
    return False

# ==========================================================
# GEMINI IMAGE → JSON
# ==========================================================

def generate_json_from_image(image, mode, api_key):
    for k in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
        os.environ.pop(k, None)

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(api_version="v1beta")
    )

    prompt = STUDENT_PROMPT if mode == "student" else TEACHER_PROMPT

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[prompt, image]
    )

    raw_text = extract_text_from_response(response)

    if not raw_text:
        raise RuntimeError(
            "Gemini returned empty response. Image unclear or prompt too strict."
        )

    clean = re.sub(r"```json|```", "", raw_text).strip()
    return json.loads(clean)

# ==========================================================
# SCORING ENGINE
# ==========================================================

def score_node_check(key, node_intents):
    expected_intent = classify_intent(key["expected_text"])

    if expected_intent in node_intents.values():
        return key["marks"], f"Intent matched: {expected_intent}"

    return 0, f"Missing concept: {key['concept']}"

def score_connection_check(key, node_intents, adj):
    from_intent = classify_intent(key["from_text"])
    to_intent = classify_intent(key["to_text"])

    from_nodes = [n for n, i in node_intents.items() if i == from_intent]
    to_nodes = [n for n, i in node_intents.items() if i == to_intent]

    if not from_nodes or not to_nodes:
        return 0, f"Missing nodes for logical flow"

    if has_path(from_nodes, set(to_nodes), adj):
        return key["marks"], f"Logical flow confirmed"

    return 0, f"Logic break between {from_intent} → {to_intent}"

# ==========================================================
# MAIN ENTRY POINT (STREAMLIT)
# ==========================================================

def evaluate_submission(student_img, rubric_img, api_key):
    student_json = generate_json_from_image(student_img, "student", api_key)
    rubric_json = generate_json_from_image(rubric_img, "teacher", api_key)

    node_intents, adj = build_graph(student_json["graph"])

    total_score = 0
    breakdown = []

    for kp in rubric_json.get("key_points", []):
        if kp["type"] == "node_check":
            score, reason = score_node_check(kp, node_intents)
        else:
            score, reason = score_connection_check(kp, node_intents, adj)

        total_score += score
        breakdown.append({
            "criteria": kp["concept"],
            "awarded": score,
            "max": kp["marks"],
            "status": "✅" if score > 0 else "❌",
            "feedback": reason
        })

    return {
        "final_score": total_score,
        "max_score": rubric_json.get("max_marks", 0),
        "breakdown": breakdown,
        "debug_student_json": student_json,
        "debug_rubric_json": rubric_json
    }
