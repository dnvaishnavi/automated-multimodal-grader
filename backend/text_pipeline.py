import numpy as np
import re
import streamlit as st
import json
import time
from sympy import sympify, simplify, Eq, Symbol
from sympy.core.sympify import SympifyError
from sentence_transformers import SentenceTransformer, util
from transformers import pipeline
from fractions import Fraction
from openai import OpenAI
# from latex2sympy2 import latex2sympy
# =========================================================
# 1. SAFE IMPORTS & CONFIG
# =========================================================

# Attempt to import latex2sympy2 safely
try:
    from latex2sympy2 import latex2sympy
except Exception as e:
    print(f"⚠️ Warning: latex2sympy2 could not be imported ({e}).")
    def latex2sympy(expr):
        return Symbol("LatexParsingError")

# =========================================================
# 2. CACHED MODEL LOADING (CRITICAL FOR STREAMLIT)
# =========================================================

@st.cache_resource
def load_models():
    """
    Loads heavy models only ONCE and caches them.
    """
    print("⏳ Loading AI Models... (This happens once)")
    
    # 1. Semantic Search Model
    embedder = SentenceTransformer("all-mpnet-base-v2")
    
    # 2. NLI Model (Entailment Checker)
    nli_pipeline = pipeline(
        "text-classification",
        model="roberta-large-mnli",
        top_k=None # Modern replacement for return_all_scores
    )
    
    print("✅ Models Loaded!")
    return embedder, nli_pipeline

# Load models securely
embedder, nli_pipeline = load_models()

# =========================================================
# 3. TEXT EVALUATION LOGIC
# =========================================================

def evaluate_text_evidence(student_texts, key_point):
    student_text = " ".join(student_texts).strip()
    concept = key_point["concept"]
    evidence_phrases = key_point.get("evidence_phrases", [])
    max_marks = key_point["marks"]

    if not student_text:
        return {"matched": False, "awarded_marks": 0, "reason": "No text provided"}

    # A. Coverage
    coverage_hits = sum(1 for p in evidence_phrases if p.lower() in student_text.lower())
    coverage_score = 1.0 if coverage_hits > 0 else 0.0

    # B. NLI (Logic Check)
    try:
        pair = f"{student_text} </s></s> {concept}"
        nli_result = nli_pipeline(pair)[0]
        scores = {r["label"].lower(): r["score"] for r in nli_result}
        
        entail = scores.get("entailment", 0)
        contra = scores.get("contradiction", 0)

        if contra > 0.6:
            return {"matched": False, "awarded_marks": 0, "reason": "Contradiction detected"}
        
        entailment_score = 1.0 if entail > 0.7 else (0.5 if entail > 0.3 else 0.0)
    except:
        entailment_score = 0.5 # Fallback

    # C. Semantic Similarity
    emb_student = embedder.encode(student_text, convert_to_tensor=True)
    emb_concept = embedder.encode(concept, convert_to_tensor=True)
    similarity_score = util.cos_sim(emb_student, emb_concept).item()
    similarity_score = max(0.0, min(similarity_score, 1.0))

    # D. Aggregation
    if entailment_score >= 0.8 and similarity_score >= 0.7:
        final_fraction = 1.0
    else:
        final_fraction = (0.3 * coverage_score + 0.4 * entailment_score + 0.3 * similarity_score)

    awarded = round(final_fraction * max_marks, 2)

    return {
        "matched": awarded > 0,
        "awarded_marks": awarded,
        "source": "text",
        "reason": f" Content Similarity: {int(final_fraction*100)}%"
    }

# =========================================================
# 4. EQUATION & MATH LOGIC
# =========================================================

def parse_expression(expr):
    """Converts string/latex to SymPy object"""
    expr = str(expr).replace(" ", "")
    if "=" in expr:
        _, rhs = expr.split("=", 1)
        expr = rhs
    try:
        return simplify(sympify(expr))
    except:
        try:
            return simplify(latex2sympy(expr))
        except:
            return None

def parse_reaction(eq):
    """Simple parser for Chemical Equations"""
    eq = eq.replace("→", "->")
    if "->" not in eq: return None
    lhs, rhs = eq.split("->")
    # Extract element counts (Very basic regex)
    reactants = set(re.findall(r"[A-Z][a-z]?\d*", lhs))
    products = set(re.findall(r"[A-Z][a-z]?\d*", rhs))
    return reactants, products

def detect_equation_type(eq):
    if "->" in eq or "→" in eq: return "reaction"
    rhs = eq.split("=")[1] if "=" in eq else eq
    try:
        if sympify(rhs).is_number: return "computation"
    except: pass
    return "law"
def normalize_chemical_equation(eq):
    """
    Normalizes chemical equation for robust comparison.
    Fixed Regex to handle (aq) correctly.
    """
    if not eq: return ""
    
    # 1. Unicode Subscript Map (₂ -> 2)
    subscript_map = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
    eq = eq.translate(subscript_map)
    
    # 2. Normalize Arrow
    eq = eq.replace("→", "->").replace("=>", "->")
    
    # 3. Remove State Symbols (aq), (s), (l), (g) 
    # FIX: Changed regex from [aslg] to [a-z] to capture 'aq'
    eq = re.sub(r"\([a-z]{1,3}\)", "", eq, flags=re.IGNORECASE)
    
    # 4. Remove all whitespace to handle "2 NaCl" vs "2NaCl"
    eq = eq.replace(" ", "")
    
    return eq
def evaluate_equation_evidence(student_equations, key_point):
    expected_eq = key_point.get("expected_equation")
    if not expected_eq: return {"matched": False, "reason": "No expected equation"}

    eq_type = detect_equation_type(expected_eq)

    # 1. Chemistry
    if eq_type == "reaction":
        expected_eq = key_point.get("expected_equation")
        if not expected_eq: return {"matched": False, "reason": "No expected equation"}

        # Normalize Teacher Key
        norm_expected = normalize_chemical_equation(expected_eq)
        
        # Pre-calculate Teacher's Reactants/Products for comparison
        try:
            if "->" in norm_expected:
                exp_lhs, exp_rhs = norm_expected.split("->")
                # Sort to handle order difference (A+B vs B+A)
                exp_reactants = sorted(exp_lhs.split("+"))
                exp_products = sorted(exp_rhs.split("+"))
            else:
                exp_reactants, exp_products = [norm_expected], []
        except:
            return {"matched": False, "reason": "Invalid Key Format"}

        for eq in student_equations:
            norm_student = normalize_chemical_equation(eq)
            
            # LEVEL 1: Exact String Match (Fastest)
            if norm_student == norm_expected:
                return {"matched": True, "reason": "✅ Correct balanced equation (Exact Match)."}
                
            # LEVEL 2: Component Match (Handles Balancing & Order)
            try:
                if "->" in norm_student:
                    stu_lhs, stu_rhs = norm_student.split("->")
                    stu_reactants = sorted(stu_lhs.split("+"))
                    stu_products = sorted(stu_rhs.split("+"))
                    
                    # STRICT MATCH: If lists are equal, it implies coefficients (balancing) are also equal.
                    # Example: ['BaSO4', '2NaCl'] == ['BaSO4', '2NaCl']
                    if stu_reactants == exp_reactants and stu_products == exp_products:
                        return {"matched": True, "reason": "✅ Correct balanced equation."}
            except:
                continue

        return {"matched": False, "reason": "Equation mismatch or unbalanced."}

    # 2. Math/Physics
    expected = parse_expression(expected_eq)
    for eq in student_equations:
        student = parse_expression(eq)
        if student is not None and expected is not None:
            try:
                # Algebraically Equivalent (Difference is zero)
                if simplify(student - expected) == 0:
                     return {"matched": True, "reason": "Correct equation."}
            except: pass
            
    return {"matched": False, "reason": "Equation mismatch."}

def evaluate_final_answer(student_final, key_point):
    expected_str = str(key_point.get("expected_final_answer")).strip()
    student_str = str(student_final).strip()

    if not expected_str or not student_str:
        return {"matched": False, "reason": "Missing answer"}

    # 1. Symbolic Match (Handles x^2+C == C+x^2)
    try:
        if simplify(sympify(student_str) - sympify(expected_str)) == 0:
            return {"matched": True, "reason": "Correct value (Symbolic Match)"}
    except: pass

    # 2. Exact Match
    if student_str.lower() == expected_str.lower():
         return {"matched": True, "reason": "Correct value (Exact Match)"}

    return {"matched": False, "reason": "Final answer incorrect"}

# =========================================================
# 5. LLM REFINEMENT (The "Smart" Layer)
# =========================================================


def get_openai_client():
    """Lazy load client to avoid errors if key is missing initially"""
    api_key = st.secrets.get("OPENROUTER_API_KEY") or st.secrets.get("OPENROUTER_LLAMA_API_KEY")
    if not api_key: return None
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

def _classify_alignment_llm(student_context, concept, max_m):
    client = get_openai_client()
    if not client: return {"awarded_marks": 0, "reasoning": "API Key Missing"}

    prompt = f"""
You are an academic grader.
    
    TARGET CRITERIA: "{concept}"
    
    STUDENT ANSWER CONTEXT:
    {student_context}

    INSTRUCTIONS:
    1. Search the "STUDENT ANSWER CONTEXT" for the "TARGET CRITERIA".
    2. If the criteria is a CHEMICAL/MATH EQUATION, check if the student has written it (even with slight formatting differences like '->' instead of '→' or missing states like '(aq)').
    3. If the criteria is TEXT, check for semantic meaning.
    
    SCORING RULES:
    - FULL MARKS ({max_m}): Concept/Equation is present and correct.
    - PARTIAL MARKS: Present but has minor errors (e.g. unbalanced equation).
    - ZERO MARKS: Completely missing or wrong.

    OUTPUT JSON ONLY:
    {{
      "awarded_marks": <number between 0 and {max_m}>,
      "reasoning": "<short explanation>"
    }}
    """
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3.3-70b-instruct:free",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content
        # Clean JSON markdown
        content = re.sub(r"```json|```", "", content).strip()
        return json.loads(content)
    except Exception as e:
        return {"awarded_marks": 0, "reasoning": f"LLM Error: {e}"}

def evaluate_key_point_llm(answer_obj, key_point):
    # 1. Run Heuristics (Fast Checks)
    evidences = []
    if "text" in key_point["acceptable_modalities"]:
        evidences.append(evaluate_text_evidence(answer_obj.get("text", []), key_point))
    if "equation" in key_point["acceptable_modalities"]:
        evidences.append(evaluate_equation_evidence(answer_obj.get("equations", []), key_point))
    if "final_answer" in key_point["acceptable_modalities"]:
        evidences.append(evaluate_final_answer(answer_obj.get("final_answer"), key_point))

    # Pick best heuristic result
    best_res = max(evidences, key=lambda x: x.get("awarded_marks", 0)) if evidences else {"awarded_marks": 0, "reason": "No match"}
    
    # 2. LLM Refinement Logic
    current_score = best_res.get("awarded_marks", 0)
    max_score = key_point["marks"]
    
    # --- FIX 1: INCLUDE EQUATIONS IN CONTEXT FOR LLM ---
    # We must construct a string that contains EVERYTHING the student wrote.
    text_content = " ".join(answer_obj.get("text", []))
    eq_content = " ".join(answer_obj.get("equations", [])) # <--- This was missing!
    final_content = str(answer_obj.get("final_answer", ""))
    
    context_text = f"""
    [Text]: {text_content}
    [Equations]: {eq_content}
    [Final Answer]: {final_content}
    """
    
    # We trigger LLM if heuristics failed to give full marks
    if current_score < max_score:
        print(f"🔍 Refining '{key_point['id']}' with LLM...")
        
        # --- FIX 2: TELL LLM THE EXPECTED EQUATION ---
        # Don't just send the word "equation". Send the actual formula.
        target_concept = key_point["concept"]
        
        if key_point.get("expected_equation"):
            target_concept = f"Equation matching: {key_point['expected_equation']}"
        elif key_point.get("expected_final_answer"):
            target_concept = f"Final Value: {key_point['expected_final_answer']}"

        llm_res = _classify_alignment_llm(context_text, target_concept, max_score)
        
        if isinstance(llm_res.get("awarded_marks"), (int, float)):
             return {
                "key_id": key_point["id"],
                "awarded_marks": float(llm_res["awarded_marks"]),
                "max_marks": max_score,
                "reason": f"[LLM] {llm_res.get('reasoning')}"
            }

    # Default to heuristic result if LLM wasn't needed or failed
    if best_res.get("matched"):
        best_res["awarded_marks"] = max_score # Give full marks if matched strictly
        
    return {
        "key_id": key_point["id"],
        "awarded_marks": best_res.get("awarded_marks", 0),
        "max_marks": max_score,
        "reason": best_res.get("reason", "Criteria not met")
    }

def evaluate_answer_llm(answer_obj, rubric_obj):
    total = 0
    breakdown = []

    for kp in rubric_obj["key_points"]:
        # Skip flowchart points (handled by master_grader)
        if "flowchart" in kp["acceptable_modalities"]:
            continue
            
        res = evaluate_key_point_llm(answer_obj, kp)
        total += res["awarded_marks"]
        breakdown.append(res)

    return {
        "question_id": rubric_obj["question_id"],
        "score": round(total, 2),
        "max_score": rubric_obj["max_marks"],
        "breakdown": breakdown
    }