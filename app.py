from flask import Flask, render_template, request, redirect, session, send_file
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.resnet50 import preprocess_input
import numpy as np
import os
import sqlite3
from datetime import datetime

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

app = Flask(__name__)
app.secret_key = "bloodprint_secret_key"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("database", exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect("database/project.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS results(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT,
        prediction TEXT,
        confidence REAL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

init_db()


# ================= LOAD MODEL =================

model = load_model("model_blood_group_detection.h5")

labels = ['A+', 'A-', 'AB+', 'AB-', 'B+', 'B-', 'O+', 'O-']


# ================= PREDICTION =================

def predict_image(img_path):
    img = image.load_img(img_path, target_size=(256,256))
    img = image.img_to_array(img)
    img = np.expand_dims(img, axis=0)
    img = preprocess_input(img)

    pred = model.predict(img)

    class_index = np.argmax(pred)
    result = labels[class_index]
    confidence = round(float(pred[0][class_index]) * 100, 2)

    return result, confidence


# ================= HOME =================

@app.route("/", methods=["GET","POST"])
def index():

    prediction = None
    confidence = None
    last_id = None

    if request.method == "POST":

        if "user_id" not in session:
            return redirect("/login")

        file = request.files["file"]

        if file.filename != "":
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(filepath)

            prediction, confidence = predict_image(filepath)

            conn = sqlite3.connect("database/project.db")
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO results(user_id, filename, prediction, confidence) VALUES (?, ?, ?, ?)",
                (session["user_id"], file.filename, prediction, confidence)
            )

            conn.commit()
            last_id = cursor.lastrowid
            conn.close()

    return render_template(
        "index.html",
        prediction=prediction,
        confidence=confidence,
        last_id=last_id
    )


# ================= DOWNLOAD REPORT =================

@app.route("/download_report/<int:result_id>")
def download_report(result_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database/project.db")

    data = conn.execute("""
        SELECT results.*, users.name 
        FROM results 
        JOIN users ON results.user_id = users.id
        WHERE results.id=? AND results.user_id=?
    """, (result_id, session["user_id"])).fetchone()

    conn.close()

    if not data:
        return "No report found"

    # ✅ FORMAT DATE + TIME
    dt = datetime.strptime(data[5], "%Y-%m-%d %H:%M:%S")
    formatted_datetime = dt.strftime("%d-%m-%Y %I:%M %p")

    filename = f"report_{result_id}.pdf"

    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()

    content = []

    # ===== HEADER =====
    content.append(Paragraph("<b>BLOODPRINT DIAGNOSTIC LAB</b>", styles["Title"]))
    content.append(Spacer(1, 10))
    content.append(Paragraph("AI-Based Blood Group Detection Report", styles["Normal"]))
    content.append(Spacer(1, 20))

    # ===== TABLE =====
    table_data = [
        ["Patient Name", data[6]],
        ["Report ID", str(data[0])],
        ["Date & Time", formatted_datetime],
        ["Blood Group", data[3]],
        ["Confidence", f"{data[4]} %"]
    ]

    table = Table(table_data, colWidths=[150, 300])

    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold')
    ]))

    content.append(table)
    content.append(Spacer(1, 30))

    # ===== NOTE =====
    content.append(Paragraph(
        "Note: This report is generated using AI-based fingerprint analysis. "
        "Please consult a certified medical professional for confirmation.",
        styles["Italic"]
    ))

    content.append(Spacer(1, 40))

    content.append(Paragraph("Authorized Signature", styles["Normal"]))
    content.append(Spacer(1, 20))
    content.append(Paragraph("__________________________", styles["Normal"]))

    doc.build(content)

    return send_file(filename, as_attachment=True)


# ================= SIGNUP =================

@app.route("/signup", methods=["GET","POST"])
def signup():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database/project.db")

        try:
            conn.execute(
                "INSERT INTO users(name,email,password) VALUES(?,?,?)",
                (name,email,password)
            )
            conn.commit()
        except:
            return "User already exists"

        conn.close()
        return redirect("/login")

    return render_template("signup.html")


# ================= LOGIN =================

@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database/project.db")

        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email,password)
        ).fetchone()

        conn.close()

        if user:
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            return redirect("/")
        else:
            return "Invalid Login"

    return render_template("login.html")


# ================= LOGOUT =================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ================= HISTORY =================

@app.route("/history")
def history():

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database/project.db")

    data = conn.execute(
        "SELECT * FROM results WHERE user_id=? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template("history.html", data=data)


# ================= ABOUT =================

@app.route("/about")
def about():
    return render_template("about.html")


# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)