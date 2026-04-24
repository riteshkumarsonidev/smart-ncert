from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_session import Session
from config import Config
from utils.pdf_reader import extract_text_from_pdf
from utils.ai_generator import generate_questions
from utils.data_manager import db  # Local file-based DB
import os
from bson.objectid import ObjectId
from datetime import datetime
from flask_cors import CORS
from dotenv import load_dotenv

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

load_dotenv()  # read .env file

app.config["GEMINI_API_KEY"] = (
    os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
)

if not app.config.get("GEMINI_API_KEY"):
    print("⚠️ WARNING: GEMINI_API_KEY is missing. AI Quiz generation will not work.")
else:
    key = str(app.config["GEMINI_API_KEY"])
    if len(key) > 8:
        masked = key[:4] + "..." + key[-4:]
    else:
        masked = "*****"
    print(f"# GEMINI_API_KEY is active: {masked}")

# Set maximum upload size to 50MB
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# Session setup
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Local Storage setup
print("✅ Local File-based Storage (JSON) Initialized Successfully!")
print("💡 Tip: All your data is now saved in the 'data' folder as JSON files.")

# Ensure upload folder exists
if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

# Check for API Key
load_dotenv()

app.config["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")

if not app.config.get("GEMINI_API_KEY"):
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        app.config["GEMINI_API_KEY"] = api_key
        print("# Using GOOGLE_API_KEY as fallback")

@app.route("/debug-pdfs")
def debug_pdfs():
    if session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(list(db.pdfs.find()))

@app.route("/check-config")
def check_config():
    return jsonify({
        "gemini_api_key_present": bool(app.config.get("GEMINI_API_KEY")),
        "secret_key_present": bool(app.config.get("SECRET_KEY")),
        "upload_folder": app.config.get("UPLOAD_FOLDER"),
        "data_dir_exists": os.path.exists("data"),
        "uploads_dir_exists": os.path.exists("uploads")
    })

# Routes
@app.context_processor
def inject_enumerate():
    return dict(enumerate=enumerate)

@app.template_filter('format_date')
def format_date(value):
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    try:
        # Try to parse ISO format string
        dt = datetime.fromisoformat(value)
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return str(value)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login/student", methods=["GET", "POST"])
def login_student():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        user = db.users.find_one({"username": username, "password": password})
        if user:
            session["role"] = "student"
            session["username"] = user["username"]
            session["user_id"] = str(user["_id"])
            session["class"] = user["class"]
            return redirect(url_for("student_dashboard"))
        
        flash("Invalid student credentials", "danger")
    return render_template("login_student.html")

@app.route("/login/admin", methods=["GET", "POST"])
def login_admin():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if username == "mrchitra" and password == "pkok9999":
            session["role"] = "admin"
            session["username"] = "Admin"
            return redirect(url_for("admin_dashboard"))
        
        flash("Invalid admin credentials", "danger")
    return render_template("login_admin.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    return redirect(url_for("index"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        student_class = request.form.get("class")
        
      # Check if username is empty or just spaces
        if not username or not username.strip():
            flash("Username cannot be empty", "danger")
            return render_template("register.html")

        # Check if user exists specifically
        existing_user = db.users.find_one({"username": username})
        
        if existing_user:
            flash("Username already exists", "danger")
        else:
            db.users.insert_one({
                "name": name,
                "username": username,
                "email": email,
                "password": password,
                "class": student_class,
                "date": datetime.now()
            })
            flash("Registration successful", "success")
            return redirect(url_for("login_student"))
            
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/admin-dashboard")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    
    students = list(db.users.find())
    pdfs = list(db.pdfs.find())
    return render_template("admin_dashboard.html", students=students, pdfs=pdfs)

@app.route("/delete-student/<student_id>")
def delete_student(student_id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    
    db.users.delete_one({"_id": ObjectId(student_id)})
    flash("Student deleted successfully", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/delete-pdf/<pdf_id>")
def delete_pdf(pdf_id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    
    # Use string comparison for ID
    pdf = db.pdfs.find_one({"_id": str(pdf_id)})
    if not pdf:
        # Fallback to ObjectId if needed, though LocalDB uses strings
        try:
            pdf = db.pdfs.find_one({"_id": ObjectId(pdf_id)})
        except:
            pass

    if pdf:
        # Delete file from uploads folder
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], pdf["name"])
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Error deleting file: {e}")
        
        db.pdfs.delete_one({"_id": pdf["_id"]})
        flash(f"PDF '{pdf['name']}' deleted successfully", "success")
    else:
        flash("PDF not found", "danger")
    
    return redirect(url_for("admin_dashboard"))

@app.errorhandler(413)
def request_entity_too_large(error):
    flash("File is too large. Maximum size allowed is 50MB.", "danger")
    return redirect(url_for("admin_dashboard")), 413

@app.route("/upload-pdf", methods=["POST"])
def upload_pdf():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    
    if "file" not in request.files:
        flash("No file part", "danger")
        return redirect(url_for("admin_dashboard"))
    
    file = request.files["file"]
    student_class = request.form.get("class")
    subject = request.form.get("subject")
    
    if file.filename == "":
        flash("No selected file", "danger")
        return redirect(url_for("admin_dashboard"))
    
    # Check file size manually for better error message
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)
    if file_length > 50 * 1024 * 1024:
        flash("File is too large. Maximum size allowed is 50MB.", "danger")
        return redirect(url_for("admin_dashboard"))
    
    if file:
        filename = file.filename
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        
        # Ensure filename is unique if it exists on disk but not in DB (unlikely but safe)
        if os.path.exists(filepath):
            base, ext = os.path.splitext(filename)
            filename = f"{base}_{int(datetime.now().timestamp())}{ext}"
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

        file.save(filepath)
        
        # Extract text
        content, language = extract_text_from_pdf(filepath)
        
        if not content or len(content.strip()) < 50:
            if os.path.exists(filepath):
                os.remove(filepath)
            flash("Could not extract enough text from this PDF. It might be an image-based PDF, empty, or too short.", "danger")
            return redirect(url_for("admin_dashboard"))
        
        db.pdfs.insert_one({
            "name": filename,
            "class": student_class,
            "subject": subject,
            "language": language,
            "content": content,
            "date": datetime.now()
        })
        
        flash("PDF uploaded and processed successfully", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/list-models")
def list_models():
    api_key = app.config.get("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return jsonify({"error": "API Key missing"}), 400
    
    import google.generativeai as genai
    try:
        genai.configure(api_key=api_key)
        models = []
        for m in genai.list_models():
            models.append({
                "name": m.name,
                "supported_methods": m.supported_generation_methods,
                "display_name": m.display_name
            })
        return jsonify(models)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/student-dashboard")
def student_dashboard():
    if session.get("role") != "student":
        return redirect(url_for("login"))
    
    student_class = session.get("class")
    quizzes = list(db.quizzes.find({"user_id": session["user_id"]}))
    # Show PDFs uploaded for this student's class
    pdfs = list(db.pdfs.find({"class": student_class}))
    return render_template("student_dashboard.html", quizzes=quizzes, pdfs=pdfs)

@app.route("/generate-quiz-from-pdf/<pdf_id>", methods=["POST"])
def generate_quiz_from_pdf(pdf_id):
    if session.get("role") != "student":
        return jsonify({"error": "Unauthorized"}), 401
    
    # Use robust lookup logic
    pdf = db.pdfs.find_one({"_id": str(pdf_id)})
    if not pdf:
        try:
            pdf = db.pdfs.find_one({"_id": ObjectId(pdf_id)})
        except:
            pass
            
    if not pdf:
        flash("Study material not found", "danger")
        return redirect(url_for("student_dashboard"))
    
    level = request.form.get("level", "Medium")
    number = request.form.get("number", "5")
    student_class = session.get("class")
    
    # Try both GEMINI_API_KEY and GOOGLE_API_KEY
    api_key = app.config.get("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        print(f"DEBUG: Using API Key: {api_key[:5]}...{api_key[-5:]}")
    else:
        print("DEBUG: No API Key found in app.config or environment")
    
    questions_data = generate_questions(student_class, pdf["subject"], level, number, pdf["content"], api_key)
    
    if "error" in questions_data:
        flash(questions_data["error"], "danger")
        return redirect(url_for("student_dashboard"))
    
    session["current_quiz"] = {
        "subject": pdf["subject"],
        "questions": questions_data["questions"],
        "score": 0,
        "total": len(questions_data["questions"])
    }
    
    return redirect(url_for("quiz"))

@app.route("/generate-quiz", methods=["POST"])
def generate_quiz():
    if session.get("role") != "student":
        return jsonify({"error": "Unauthorized"}), 401
    
    subject = request.form.get("subject")
    level = request.form.get("level")
    number = request.form.get("number")
    student_class = session.get("class")
    
    # Find relevant PDF content
    relevant_pdfs = list(db.pdfs.find({"subject": subject, "class": student_class}))
    content = ""
    if relevant_pdfs:
        content = "\n".join([p["content"] for p in relevant_pdfs])
    else:
        content = f"General {subject} knowledge for Class {student_class}"
    
    # Try both GEMINI_API_KEY and GOOGLE_API_KEY
    api_key = app.config.get("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        print(f"DEBUG: Using API Key: {api_key[:5]}...{api_key[-5:]}")
    else:
        print("DEBUG: No API Key found in app.config or environment")
    
    questions_data = generate_questions(student_class, subject, level, number, content, api_key)
    
    if "error" in questions_data:
        return jsonify(questions_data), 500
    
    session["current_quiz"] = {
        "subject": subject,
        "questions": questions_data["questions"],
        "score": 0,
        "total": len(questions_data["questions"])
    }
    
    return redirect(url_for("quiz"))

@app.route("/quiz")
def quiz():
    if session.get("role") != "student" or "current_quiz" not in session:
        return redirect(url_for("student_dashboard"))
    
    return render_template("quiz.html", quiz=session["current_quiz"])

@app.route("/submit-quiz", methods=["POST"])
def submit_quiz():
    if session.get("role") != "student" or "current_quiz" not in session:
        return redirect(url_for("student_dashboard"))
    
    answers = request.form.to_dict()
    quiz_data = session["current_quiz"]
    score = 0
    
    for i, q in enumerate(quiz_data["questions"]):
        user_ans = answers.get(f"q{i}")
        if user_ans is not None and int(user_ans) == q["correctAnswer"]:
            score += 1
    
    percentage = (score / quiz_data["total"]) * 100 if quiz_data["total"] > 0 else 0
    
    result = {
        "user_id": session["user_id"],
        "subject": quiz_data["subject"],
        "score": score,
        "total": quiz_data["total"],
        "percentage": percentage,
        "date": datetime.now()
    }
    
    db.quizzes.insert_one(result)
    session.pop("current_quiz")
    
    return render_template("result.html", result=result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
