# Create a file named 'backend/db_handler.py'
import json
import os

DB_FILE = "school_data.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {"tests": [], "submissions": []}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def publish_test(test_obj):
    db = load_db()
    db["tests"].append(test_obj)
    save_db(db)

def get_active_test():
    db = load_db()
    if db["tests"]:
        return db["tests"][-1] # Return the most recent test
    return None

def submit_student_answers(submission_obj):
    db = load_db()
    # Optional: Check if student already submitted to avoid duplicates
    # (Simple logic: remove old submission from same student if exists)
    db["submissions"] = [
        s for s in db["submissions"] 
        if s["student_id"] != submission_obj["student_id"]
    ]
    
    # Add new submission
    db["submissions"].append(submission_obj)
    save_db(db)
    return True

def get_submissions_for_teacher():
    db = load_db()
    return db["submissions"]