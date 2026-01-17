# ==========================================================
# FLOWCHART PIPELINE
# Image → JSON → Semantic + Logical Evaluation
# ==========================================================

import os, re, json
from PIL import Image
from difflib import SequenceMatcher
from collections import defaultdict, deque

from google import genai
from google.genai import types # type: ignore

# ---------------- CONFIG ----------------

MODEL_ID = "models/gemini-2.5-flash"

STUDENT_PROMPT = """
Analyze this flowchart and return ONLY a RAW JSON object.

Schema:
{
  "question_id": "Q1",
  "student_id": "std_01",
  "graph": {
    "nodes": [
      {"id": "n1", "text": "exact text", "shape": "oval/rect/diamond"}
    ],
    "edges": [
      {"source": "n1", "target": "n2", "label": "Yes/No"}
    ]
  }
}
"""

TEACHER_PROMPT = """
Analyze this correct flowchart and return ONLY a RAW JSON object.

Schema:
{
  "question_id": "Q1",
  "max_marks": 5,
  "key_points": [
    {
      "id": "k1",
      "concept": "Start node",
      "type": "node_check",
      "expected_text": "Start",
      "marks": 1
    }
  ]
}
"""

# ---------------- GEMINI IMAGE → JSON ----------------

def image_to_json(image_path, mode, api_key):
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(api_version="v1beta")
    )

    prompt = STUDENT_PROMPT if mode == "student" else TEACHER_PROMPT
    img = Image.open(image_path)

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[prompt, img]
    )

    clean = re.sub(r"```json|```", "", response.text).strip()
    return json.loads(clean)

# ---------------- TEXT METRICS ----------------

def semantic_metrics(a, b):
    a, b = a.lower().strip(), b.lower().strip()
    m = SequenceMatcher(None, a, b)
    similarity = m.ratio()
    coverage = m.find_longest_match(0, len(a), 0, len(b)).size / max(len(a), 1)
    entailment = 0.6 * similarity + 0.4 * coverage
    return entailment

# ---------------- INTENT CLASSIFIER ----------------

def classify_intent(text):
    t = text.lower()
    if "start" in t: return "START"
    if "end" in t or "stop" in t: return "END"
    if "print" in t or "output" in t: return "OUTPUT"
    if "=" in t and "+" in t: return "INCREMENT"
    if "=" in t: return "ASSIGNMENT"
    if ">" in t or "<" in t or "==" in t: return "CONDITION"
    return "UNKNOWN"

# ---------------- GRAPH UTILS ----------------

def build_graph(student_graph):
    intents = {}
    adj = defaultdict(list)

    for n in student_graph["nodes"]:
        intents[n["id"]] = classify_intent(n["text"])

    for e in student_graph["edges"]:
        adj[e["source"]].append(e["target"])

    return intents, adj

def has_path(start_nodes, target_nodes, adj):
    q, visited = deque(start_nodes), set(start_nodes)
    while q:
        cur = q.popleft()
        if cur in target_nodes:
            return True
        for nxt in adj.get(cur, []):
            if nxt not in visited:
                visited.add(nxt)
                q.append(nxt)
    return False

# ---------------- GRADER ----------------

def grade_flowchart(student_obj, rubric_obj):
    total, max_total = 0, rubric_obj["max_marks"]
    breakdown = []

    node_intents, adj = build_graph(student_obj["graph"])

    for kp in rubric_obj["key_points"]:
        awarded = 0
        reason = ""

        if kp["type"] == "node_check":
            expected = classify_intent(kp["expected_text"])
            if expected in node_intents.values():
                awarded = kp["marks"]
                reason = "Intent matched"
            else:
                reason = "Concept missing"

        elif kp["type"] == "connection_check":
            from_i = classify_intent(kp["from_text"])
            to_i = classify_intent(kp["to_text"])

            from_nodes = [n for n,i in node_intents.items() if i == from_i]
            to_nodes = [n for n,i in node_intents.items() if i == to_i]

            if has_path(from_nodes, set(to_nodes), adj):
                awarded = kp["marks"]
                reason = "Logical flow correct"
            else:
                reason = "Logical flow incorrect"

        total += awarded
        breakdown.append({
            "key_id": kp["id"],
            "awarded_marks": awarded,
            "max_marks": kp["marks"],
            "reason": reason
        })

    return {
        "question_id": rubric_obj["question_id"],
        "score": total,
        "max_score": max_total,
        "breakdown": breakdown
    }

# ---------------- PIPELINE ENTRY ----------------

def evaluate_flowchart(student_image, teacher_image, api_key):
    student_obj = image_to_json(student_image, "student", api_key)
    rubric_obj = image_to_json(teacher_image, "teacher", api_key)
    return grade_flowchart(student_obj, rubric_obj)
