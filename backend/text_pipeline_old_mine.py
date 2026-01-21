
# !pip install -q sympy numpy nltk sentence-transformers latex2sympy2 pint chempy

# !pip uninstall -y google-generativeai
# !pip install -q google-generativeai networkx

# Imports & model load
import numpy as np
import re
import streamlit as st
from sympy.core.sympify import SympifyError
from latex2sympy2 import latex2sympy
from sentence_transformers import SentenceTransformer, util
from sympy import sympify, simplify, Eq, Symbol
semantic_model = SentenceTransformer("all-mpnet-base-v2")

from sympy import sympify, simplify, Eq
from pint import UnitRegistry
from chempy import balance_stoichiometry
try:
    # Attempt to import the library
    from latex2sympy2 import latex2sympy
except Exception as e:
    print(f"⚠️ Warning: latex2sympy2 could not be imported ({e}).")
    print("⚠️ App is running in 'Safe Mode'. LaTeX parsing will be limited.")
    
    # Create a dummy function so the app doesn't crash later
    def latex2sympy(expr):
        # Return a placeholder symbol so SymPy logic doesn't break
        return Symbol("LatexParsingError")
ureg = UnitRegistry()
from transformers import pipeline
# import google.generativeai as genai

nli_pipeline = pipeline(
    "text-classification",
    model="roberta-large-mnli",
    return_all_scores=True
)

embedder = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

def evaluate_text_evidence(student_texts, key_point):
    student_text = " ".join(student_texts).strip()
    concept = key_point["concept"]
    evidence_phrases = key_point.get("evidence_phrases", [])
    max_marks = key_point["marks"]

    if not student_text:
        return {
            "matched": False,
            "awarded_marks": 0,
            "reason": "No text provided"
        }

    # ---------- STEP 1: Coverage ----------
    coverage_hits = sum(
        1 for p in evidence_phrases if p.lower() in student_text.lower()
    )
    coverage_score = 1.0 if coverage_hits > 0 else 0.0

    # ---------- STEP 2: NLI (gatekeeper) ----------
    pair = f"{student_text} </s></s> {concept}"
    nli_result = nli_pipeline(pair)[0]
    scores = {r["label"].lower(): r["score"] for r in nli_result}

    entail = scores.get("entailment", 0)
    contra = scores.get("contradiction", 0)

    # Hard fail on contradiction
    if contra > 0.6:
        return {
            "matched": False,
            "awarded_marks": 0,
            "reason": "Contradiction detected via NLI"
        }

    if entail < 0.3:
        return {
            "matched": False,
            "awarded_marks": 0,
            "reason": "No entailment with rubric concept"
        }

    entailment_score = 1.0 if entail > 0.7 else 0.5

    # ---------- STEP 3: Semantic similarity ----------
    emb_student = embedder.encode(student_text, convert_to_tensor=True)
    emb_concept = embedder.encode(concept, convert_to_tensor=True)
    similarity_score = util.cos_sim(emb_student, emb_concept).item()
    similarity_score = max(0.0, min(similarity_score, 1.0))

    # ---------- STEP 4: Weighted aggregation ----------
    if entailment_score >= 0.5 and similarity_score >= 0.65:
      entailment_score = 1.0
    final_fraction = (
        0.3 * coverage_score +
        0.4 * entailment_score +
        0.3 * similarity_score
    )

    awarded = round(final_fraction * max_marks, 2)

    return {
        "matched": awarded > 0,
        "awarded_marks": awarded,
        "source": "text",
        "reason": (
            f"coverage={coverage_score:.2f}, "
            f"entailment={entailment_score:.2f}, "
            f"similarity={similarity_score:.2f}"
        )
    }


def parse_expression(expr):
    expr = expr.replace(" ", "")

    # Handle equations: LHS = RHS → RHS only (for computation)
    if "=" in expr:
        lhs, rhs = expr.split("=", 1)
        expr = rhs

    try:
        return simplify(sympify(expr))
    except:
        try:
            return simplify(latex2sympy(expr))
        except:
            return None
def check_physics_units(student_eq, expected_eq):
    try:
        student_val = ureg(student_eq)
        expected_val = ureg(expected_eq)
        return student_val.dimensionality == expected_val.dimensionality
    except:
        return False
def parse_reaction(eq):
    # Example: "H2 + O2 -> H2O"
    eq = eq.replace("→", "->")
    if "->" not in eq:
        return None

    lhs, rhs = eq.split("->")
    reactants = set(re.findall(r"[A-Z][a-z]?\d*", lhs))
    products = set(re.findall(r"[A-Z][a-z]?\d*", rhs))
    return reactants, products

def detect_equation_type(equation):
    eq = equation.replace(" ", "")

    # ⚗️ Chemistry reaction
    if "->" in eq or "→" in eq:
        return "reaction"

    # Split equation if exists
    if "=" in eq:
        _, rhs = eq.split("=", 1)
    else:
        rhs = eq

    # 🧮 Try numeric computation
    try:
        val = sympify(rhs)
        if val.is_number:
            return "computation"
    except:
        pass

    # 📐 Otherwise → symbolic law
    return "law"

def evaluate_equation_evidence(student_equations, key_point):
    expected_eq = key_point.get("expected_equation")
    if not expected_eq:
        return {"matched": False, "reason": "No expected equation provided"}

    eq_type = detect_equation_type(expected_eq)

    # ----------------------------
    # 🧮 COMPUTATION
    # ----------------------------
    if eq_type == "computation":
        expected = parse_expression(expected_eq)

        for eq in student_equations:
            student = parse_expression(eq)
            if student is None:
                continue

            if simplify(student - expected) == 0:
                return {
                    "matched": True,
                    "reason": "Correct numerical computation."
                }

        return {
            "matched": False,
            "reason": "Incorrect computation."
        }

    # ----------------------------
    # 📐 PHYSICS / MATH LAW
    # ----------------------------
    if eq_type == "law":
        expected = parse_expression(expected_eq)

        for eq in student_equations:
            student = parse_expression(eq)
            if student is None:
                continue

            if simplify(student - expected) == 0:
                return {
                    "matched": True,
                    "reason": "Correct symbolic equation."
                }

        return {
            "matched": False,
            "reason": "Incorrect symbolic equation."
        }

    # ----------------------------
    # ⚗️ CHEMISTRY REACTION
    # ----------------------------
    if eq_type == "reaction":
        exp_rxn = parse_reaction(expected_eq)
        if not exp_rxn:
            return {"matched": False, "reason": "Invalid expected reaction"}

        exp_reactants, exp_products = exp_rxn

        for eq in student_equations:
            stu_rxn = parse_reaction(eq)
            if not stu_rxn:
                continue

            stu_reactants, stu_products = stu_rxn

            if exp_reactants == stu_reactants and exp_products == stu_products:
                return {
                    "matched": True,
                    "reason": "Correct chemical reaction."
                }

        return {
            "matched": False,
            "reason": "Incorrect chemical reaction."}


from fractions import Fraction

def normalize_value(val):
    try:
        return float(Fraction(val))
    except:
        try:
            return float(sympify(val))
        except:
            return None



from sympy import simplify, sympify

def evaluate_final_answer(student_final, key_point):
    expected_str = key_point.get("expected_final_answer")
    student_str = str(student_final)

    if not expected_str or not student_str:
        return {"matched": False, "reason": "Missing answer"}

    # --- ATTEMPT 1: Numeric Comparison (Existing Logic) ---
    expected_val = normalize_value(expected_str)
    student_val = normalize_value(student_str)

    if expected_val is not None and student_val is not None:
        if abs(expected_val - student_val) < 1e-6:
            return {"matched": True, "reason": "Final answer value is correct."}

    # --- ATTEMPT 2: Symbolic/Algebraic Comparison (NEW LOGIC) ---
    try:
        # Convert both strings to SymPy math expressions
        exp_expr = sympify(expected_str)
        stu_expr = sympify(student_str)

        # Check if they are mathematically equivalent (Difference is 0)
        # This handles "x^2 + C" vs "C + x^2" automatically
        if simplify(stu_expr - exp_expr) == 0:
             return {"matched": True, "reason": "Final answer matches symbolically."}
    except:
        pass # If symbolic math fails, we just move on

    # --- ATTEMPT 3: Exact String Match (Fallback) ---
    if student_str.strip().lower() == expected_str.strip().lower():
        return {"matched": True, "reason": "Exact string match."}

    return {"matched": False, "reason": "Final answer is incorrect."}

# ==========================================================
# GEMINI LIVE REFINEMENT (TOOLS + JSON FIXED, SINGLE BLOCK)
# ==========================================================
import time
import json
# from google.api_core import exceptions
from openai import OpenAI
import re
api_key = st.secrets.get("OPENROUTER_LLAMA_API_KEY")
if not api_key:
    st.error("⚠️ OpenRouter API Key missing in secrets.toml")
    st.stop()
client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=api_key,
)
def clean_json_text(text):
    """
    Extracts JSON object from LLM response, handling markdown blocks.
    """
    # Remove ```json and ``` wrapping if present
    text = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)
    return text.strip()
# ----------------------------------------------------------
# STEP 1: TOOL-BASED REASONING (NO JSON, SEARCH ENABLED)
# ----------------------------------------------------------
def _classify_alignment(student_text, concept,max_m):
    """
    Asks LLM to classify the student's answer into rigid categories
    and provide specific reasoning for that classification.
    """
    prompt = f"""
    You are a subjective evaluator. Verify if a specific "Target Concept" is present in the "Student Answer".

    Target Concept: "{concept}"
    Student Answer: "{student_text}"

    Task:
    - Award partial credit if key points are semantically correct
    - Do NOT penalize correct answers with different wording
    -follow below rules:
    1. "FULLY_CORRECT": If the student explicitly or implicitly demonstrates the target concept(key concept) correctly (via text, equations, or synonyms) anywhere in the entire student answer.
    2. "PARTIALLY_CORRECT": The student mentions the target concept somewhere in the entire student answer but it is incomplete, vague, or has minor details missing grade proportionally according to correctness.
    3. "CONTRADICTION": The student explicitly states something that is the OPPOSITE or logically incompatible with the target concept or a wrong answer completely marks must be 0 for such answers especially in math  or chemistry related answers and equations.
    4. "MISSING": The concept is completely absent or the text is unrelated also marks are 0.

    Instructions:
    - IGNORE extra information that is not related to the Target Concept.
    - Judge semantic meaning, not wording.
    - Award correctness if meaning matches.
    - Respond ONLY with valid JSON.

    Format:
    {{
      "awarded_marks": "just a suitable mark between (0-{max_m})",
      "reasoning": "Explain where student went wrong in case of marks less than full and if full give reason for that too.Reason must only focus on and explain in context of target concept and nothing else "
    }}
    """

    max_retries = 3

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="meta-llama/llama-3.3-70b-instruct:free",
                messages=[
                    {"role": "system", "content": "You are a fair academic evaluator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            # 🔒 SAFETY CHECKS (ADD HERE)
            assert hasattr(response, "choices"), "Invalid LLM response (no choices)"
            assert len(response.choices) > 0, "Empty LLM response"

            # ✅ CORRECT WAY
            raw_text = response.choices[0].message.content
            cleaned_text = clean_json_text(raw_text)

            return json.loads(cleaned_text)

        except json.JSONDecodeError:
            # Retry if model outputs malformed JSON
            continue

        except Exception as e:
            return {"awarded_marks": "ERROR", "reasoning": str(e)}

    return {"awarded_marks": "ERROR", "reasoning": "LLM failed after retries"}


def evaluate_key_point(answer_obj, key_point):
    evidences = []

    if "text" in key_point["acceptable_modalities"]:
        evidences.append(evaluate_text_evidence(answer_obj.get("text", []), key_point))

    if "equation" in key_point["acceptable_modalities"]:
        evidences.append(evaluate_equation_evidence(answer_obj.get("equations", []), key_point))

    if "final_answer" in key_point["acceptable_modalities"]:
        evidences.append(evaluate_final_answer(answer_obj.get("final_answer"), key_point))

    for ev in evidences:
        if ev.get("matched"):
            return {
                "key_id": key_point["id"],
                "awarded_marks": ev["awarded_marks"] if ev.get("source") == "text"
                else key_point["marks"],
                "max_marks": key_point["marks"],
                "reason": ev["reason"]
            }

    return {
        "key_id": key_point["id"],
        "awarded_marks": 0,
        "max_marks": key_point["marks"],
        "reason": f"Student response does not satisfy concept: {key_point['concept']}"
    }
def evaluate_key_point_llm(answer_obj, key_point, threshold=0.89):
    # 1. Run standard heuristic check first
    result = evaluate_key_point(answer_obj, key_point)

    awarded = result["awarded_marks"]
    max_m = key_point["marks"]

    # 2. Prepare the context string
    text_part = " ".join(answer_obj.get("text", []))
    eq_part = " | ".join(answer_obj.get("equations", []))
    final_part = str(answer_obj.get("final_answer", ""))

    student_content = f"Text: {text_part}\nEquations: {eq_part}\nFinal Answer: {final_part}".strip()

    # 3. Trigger LLM only if heuristic failed AND there is content
    #    or if the initial awarded marks are less than the max possible
    if max_m > 0 and (awarded < max_m) and len(student_content) > 5:
        print(f"🔍 Triggering Live search for {key_point['id']}...")

        llm_output = _classify_alignment(student_content, key_point["concept"], max_m)

        llm_awarded_marks_str = llm_output.get("awarded_marks")
        llm_reasoning = llm_output.get("reasoning", "No reasoning provided by LLM.")

        try:
            # Convert LLM's awarded_marks (string) to float
            llm_awarded_marks = float(llm_awarded_marks_str)

            # Update result only if LLM provides a different or more refined score/reason
            if llm_awarded_marks != awarded:
                result["awarded_marks"] = llm_awarded_marks
                result["reason"] = f"[LLM Refined] {llm_reasoning}"
            elif llm_awarded_marks == awarded and llm_reasoning != "No reasoning provided by LLM.":
                # If scores are the same, but LLM provides more specific reasoning
                result["reason"] = f"[LLM Confirmed] {llm_reasoning}"

        except (ValueError, TypeError):
            # If LLM's awarded_marks is not a valid number or None,
            # we log an error and keep the heuristic result, but update reason.
            result["reason"] = f"[LLM Error] Could not parse LLM awarded_marks '{llm_awarded_marks_str}'. Original reason: {result['reason']} - LLM Raw Reason: {llm_reasoning}"
    # 4. Always return the 'result' dictionary, which is either the initial heuristic
    #    or updated by the LLM if it was triggered.
    return result


def evaluate_answer_llm(answer_obj, rubric_obj):
    total = 0
    breakdown = []

    for kp in rubric_obj["key_points"]:
        res = evaluate_key_point_llm(answer_obj, kp)
        total += res["awarded_marks"]
        breakdown.append(res)

    return {
        "question_id": rubric_obj["question_id"],
        "score": round(total, 2),
        "max_score": rubric_obj["max_marks"],
        "breakdown": breakdown
    }

# output = evaluate_answer_llm(answer2, rubric2)

# print("\n=== FINAL SCORE ===")
# print("Score:", output["score"], "/", output["max_score"])

# print("\n=== BREAKDOWN ===")
# for b in output["breakdown"]:
#     print(b)