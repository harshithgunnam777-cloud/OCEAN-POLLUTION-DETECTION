import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from analysis.processor import analyze_image
from geopy.geocoders import Nominatim


def get_region_from_coords(lat, lon):
    try:
        geolocator = Nominatim(user_agent="ocean_guardian")
        location = geolocator.reverse((lat, lon), language="en")
        if location and "display_name" in location.raw:
            return location.raw["display_name"]
    except:
        pass
    return "Unknown Ocean Region"

# --- Flask Setup ---
app = Flask(__name__)
app.secret_key = "supersecret"  # change in production

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "static", "output")
DB_PATH = os.path.join(BASE_DIR, "database.db")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER


# --- Database ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE,
                        password TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS uploads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        filename TEXT,
                        pollution_type TEXT,
                        result TEXT,
                        processed_path TEXT,
                        percent REAL,
                        lat REAL,
                        lon REAL,
                        FOREIGN KEY(user_id) REFERENCES users(id))''')

    conn.commit()
    conn.close()


# --- Routes ---
@app.route("/")
def home():
    return render_template("home.html")





@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            conn.close()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash("Error: " + str(e), "danger")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            flash("Welcome back!", "success")
            return redirect(url_for("upload"))
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

@app.route("/examples")
def examples():
    return render_template("examples.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message")

    model = genai.GenerativeModel("gemini-pro")

    response = model.generate_content(
    f"""
    You are an AI assistant for an Ocean Pollution Detection website.
    
    You help users with:
    - Uploading images
    - Understanding pollution detection
    - Dashboard usage
    - AI model explanation
    
    Keep answers short and simple.

    User question: {user_msg}
    """
    )
    return jsonify({"reply": response.text})



@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            flash("No file selected.", "danger")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)

        # 🔍 Run YOLO processing
        processed_path, result_text, percent, coords = analyze_image(
            save_path, app.config["OUTPUT_FOLDER"]
        )

        # ✅ Safe coordinates
        if coords and coords != (None, None):
            lat, lon = coords
            region = get_region_from_coords(lat, lon)
        else:
            lat, lon = None, None
            region = "Location not available"

        # ✅ Extract output filename
        output_filename = os.path.basename(processed_path)

        # ✅ Build browser URLs (VERY IMPORTANT)
        original_url = url_for('static', filename=f'uploads/{filename}')
        processed_url = url_for('static', filename=f'output/{output_filename}')

        # 💾 Save to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO uploads (user_id, filename, pollution_type, result,
                                 processed_path, percent, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            filename,
            result_text,      # pollution_type no longer needed logically
            result_text,
            processed_path,
            percent,
            lat,
            lon
        ))
        conn.commit()
        conn.close()

        # ✅ Show result page
        return render_template(
            "result.html",
            original=original_url,
            processed=processed_url,
            result_text=result_text,
            percent=percent,
            lat=lat,
            lon=lon,
            region=region
        )

    return render_template("upload.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, filename, pollution_type, result, processed_path,
               percent, lat, lon
        FROM uploads
        WHERE user_id=?
        ORDER BY id DESC
    """, (session["user_id"],))

    uploads = cursor.fetchall()
    conn.close()

    # Ensure lat/lon are safe values
    uploads_fixed = []
    for u in uploads:
        lat = u[6] if u[6] is not None else 0.0
        lon = u[7] if u[7] is not None else 0.0
        uploads_fixed.append(u[:6] + (lat, lon))

    # Dashboard statistics
    total_uploads = len(uploads)

    oil_spills = 0
    algal_blooms = 0
    plastic_waste = 0
    clean_ocean = 0
    
    for u in uploads:
        result = str(u[3]).lower()

        if "oil" in result:
            oil_spills += 1
        elif "algal" in result:
            algal_blooms += 1
        elif "plastic" in result:
            plastic_waste += 1
        else:
            clean_ocean += 1
    
    return render_template(
        "dashboard.html",
        uploads=uploads_fixed,
        total_uploads=total_uploads,
        oil_spills=oil_spills,
        algal_blooms=algal_blooms,
        plastic_waste=plastic_waste,
        clean_ocean=clean_ocean
        
    )

@app.route("/result/<int:upload_id>")
def view_result(upload_id):

    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT filename, processed_path, result, percent, lat, lon
        FROM uploads
        WHERE id=? AND user_id=?
    """, (upload_id, session["user_id"]))

    data = cursor.fetchone()
    conn.close()

    if not data:
        flash("Result not found.", "danger")
        return redirect(url_for("dashboard"))

    filename, processed_path, result_text, percent, lat, lon = data

    original_url = url_for('static', filename=f'uploads/{filename}')
    processed_url = url_for('static', filename=f'output/{os.path.basename(processed_path)}')

    return render_template(
        "result.html",
        original=original_url,
        processed=processed_url,
        result_text=result_text,
        percent=percent,
        lat=lat,
        lon=lon
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000 , debug=True)
