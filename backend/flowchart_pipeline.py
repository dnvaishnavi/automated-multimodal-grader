import re
import json
from difflib import SequenceMatcher
from google import genai
from google.genai import types
from PIL import Image

# ---------------- 1. CORE MATCHING LOGIC ----------------

# def calculate_similarity(text_a, text_b):
#     if not text_a or not text_b: return 0.0
#     a = str(text_a).lower().strip().replace(" ", "")
#     b = str(text_b).lower().strip().replace(" ", "")
#     if a == b: return 1.0
#     return SequenceMatcher(None, a, b).ratio()
# ---------------- 1. CORE LOGIC (GRADER) ----------------

def calculate_similarity(text_a, text_b):
    """
    Compares two texts with normalization and synonym handling.
    """
    if not text_a or not text_b: return 0.0
    
    # 1. Normalize (Lowercase, remove spaces/punctuation)
    a = str(text_a).lower().strip().replace(" ", "").replace("_", "")
    b = str(text_b).lower().strip().replace(" ", "").replace("_", "")
    
    # 2. Exact Match
    if a == b: return 1.0
    
    # 3. Synonym Check (The "Smart" part)
    synonyms = [
        {"start", "begin", "init", "initiate"},
        {"stop", "end", "finish", "terminate", "exit", "halt"},
        {"print", "output", "display", "show", "write"},
        {"read", "input", "get", "scan", "enter"},
        {"true", "yes", "y"},
        {"false", "no", "n"},
        {"inc", "increment", "add"},
        {"dec", "decrement", "sub", "subtract"}
    ]
    
    for group in synonyms:
        # Check if both words are in the same synonym group
        # (Using 'in' allows partial matches like "print x" matching "output")
        a_base = next((word for word in group if word in a), None)
        b_base = next((word for word in group if word in b), None)
        
        if a_base and b_base:
            return 0.95  # High score for synonym match
            
    # 4. Fallback to standard string similarity
    return SequenceMatcher(None, a, b).ratio()

class FlowchartGrader:
    def __init__(self, rubric, student_data):
        self.rubric = rubric
        self.student_data = student_data
        
        # Safe access to nodes/edges
        self.s_nodes = {n['id']: n for n in student_data.get('graph', {}).get('nodes', [])}
        self.s_edges = student_data.get('graph', {}).get('edges', [])
        self.concept_map = {} 

    def _find_best_match_node(self, target_text):
        best_id, best_score = None, 0.0
        for s_id, node in self.s_nodes.items():
            score = calculate_similarity(target_text, node.get('text', ''))
            if score > best_score:
                best_score = score
                best_id = s_id
        return best_id, best_score

    def grade(self):
        total_score = 0
        breakdown = []
        
        # Sort keys so we map nodes before checking edges
        if 'key_points' not in self.rubric: return {"error": "Invalid Rubric"}

        sorted_keys = sorted(self.rubric['key_points'], key=lambda x: x['type'] == 'connection_check')

        for kp in sorted_keys:
            awarded = 0.0
            reason = ""
            
            # --- NODE CHECK ---
            if kp['type'] == 'node_check':
                expected = kp['expected_text']
                s_id, score = self._find_best_match_node(expected)
                
                if score > 0.6: # Threshold
                    self.concept_map[expected] = s_id
                    if score > 0.85:
                        awarded = kp['marks']
                        reason = f"Perfect match (Confidence: {int(score*100)}%)"
                    else:
                        awarded = kp['marks'] * score
                        reason = f"Partial match (Confidence: {int(score*100)}%)"
                else:
                    reason = f"Concept missing or unclear"

            # --- CONNECTION CHECK ---
            elif kp['type'] == 'connection_check':
                from_txt = kp['from_text']
                to_txt = kp['to_text']
                
                s_from = self.concept_map.get(from_txt)
                s_to = self.concept_map.get(to_txt)
                
                if s_from and s_to:
                    edge_exists = any(
                        e['source'] == s_from and e['target'] == s_to 
                        for e in self.s_edges
                    )
                    if edge_exists:
                        awarded = kp['marks']
                        reason = "Logic flow verified"
                    else:
                        reason = f"Missing connection: {from_txt} -> {to_txt}"
                else:
                    reason = "Cannot verify logic (nodes missing)"

            total_score += awarded
            breakdown.append({
                "Criteria": kp['concept'],
                "Status": "✅" if awarded == kp['marks'] else ("⚠️" if awarded > 0 else "❌"),
                "Marks": f"{awarded:.1f}/{kp['marks']}",
                "Comment": reason
            })

        return {
            "total_score": round(total_score, 2),
            "max_marks": self.rubric.get('max_marks', 0),
            "breakdown": breakdown
        }

# ---------------- 2. GEMINI VISION WRAPPER ----------------

STUDENT_PROMPT = """
Analyze this handwritten flowchart. Return ONLY a RAW JSON object.
Schema: { "graph": { "nodes": [{"id": "n1", "text": "Start", "shape": "oval"}], "edges": [{"source": "n1", "target": "n2"}] } }
"""

TEACHER_PROMPT = """
Analyze this correct answer key. Return ONLY a RAW JSON object.
Schema: { "max_marks": 5, "key_points": [ {"id": "k1", "concept": "Start Node", "type": "node_check", "expected_text": "Start", "marks": 1}, {"id": "k2", "concept": "Flow", "type": "connection_check", "from_text": "Start", "to_text": "Next", "marks": 1} ] }
"""

def image_to_json(image_file, mode, api_key):
    try:
        client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1beta"))
        img = Image.open(image_file)
        prompt = STUDENT_PROMPT if mode == "student" else TEACHER_PROMPT
        
        response = client.models.generate_content(
            model="models/gemini-2.5-flash", # Or gemini-1.5-flash
            contents=[prompt, img]
        )
        
        clean = re.sub(r"```json|```", "", response.text).strip()
        return json.loads(clean)
    except Exception as e:
        print(f"Pipeline Error: {e}")
        return None