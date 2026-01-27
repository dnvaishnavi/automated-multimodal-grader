# Create a file named 'backend/db_handler.py'
import json
import os

DB_FILE = "school_data.json"

def load_db():
    """Loads the database from the JSON file."""
    if not os.path.exists(DB_FILE):
        # Create the file if it doesn't exist
        init_data = {"tests": [], "submissions": []}
        with open(DB_FILE, "w") as f:
            json.dump(init_data, f, indent=4)
        return init_data
    
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"tests": [], "submissions": []}

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
# --- ADD THIS FUNCTION TO backend/db_handler.py ---

def assign_paper_to_teacher(student_id, test_id, teacher_id):
    """Updates a submission with an assigned teacher ID."""
    db = load_db()
    for sub in db["submissions"]:
        if sub["student_id"] == student_id and sub["test_id"] == test_id:
            sub["assigned_teacher_id"] = teacher_id
            sub["status"] = "Assigned" # Update status text
            save_db(db)
            return True
    return False