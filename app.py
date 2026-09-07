from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from dotenv import load_dotenv
from functools import wraps
from pathlib import Path
import sqlite3
import os
import smtplib
from email.message import EmailMessage

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "pakpotato.db"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT,
            email TEXT,
            phone TEXT,
            country TEXT,
            product TEXT,
            quantity TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            subject TEXT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            image_url TEXT,
            active INTEGER DEFAULT 1
        )
    """)

    catalog = [
        ("Alverstone", "https://ilyana.pk/wp-content/uploads/2024/02/Alverstone.jpg"),
        ("Mozika", "https://ilyana.pk/wp-content/uploads/2024/02/Mozika.jpg"),
        ("Lady Rosetta", "https://ilyana.pk/wp-content/uploads/2024/02/Lady-Rosetta.jpg"),
        ("Asterix", "https://ilyana.pk/wp-content/uploads/2024/02/Asterix.jpg"),
        ("Sante", "https://ilyana.pk/wp-content/uploads/2024/02/Sante.jpg"),
    ]

    for name, image_url in catalog:
        conn.execute(
            "INSERT OR IGNORE INTO catalog (name, image_url) VALUES (?, ?)",
            (name, image_url)
        )

    conn.commit()
    conn.close()


def catalog_image(name, fallback=""):
    # Always prefer the local image supplied by the template.
    # This prevents old/external catalog URLs from breaking homepage images.
    if fallback:
        return fallback

    conn = get_db()
    row = conn.execute(
        "SELECT image_url FROM catalog WHERE name = ? AND active = 1",
        (name,)
    ).fetchone()
    conn.close()

    if row and row["image_url"]:
        return row["image_url"]

    return ""


app.jinja_env.globals["catalog_image"] = catalog_image


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


def send_notification(subject, body):
    if os.getenv("MAIL_ENABLED", "false").lower() != "true":
        return False

    gmail = os.getenv("GMAIL_ADDRESS", "").strip()
    password = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    notify = os.getenv("NOTIFY_EMAIL", "").strip()

    if not gmail or not password or not notify:
        return False

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = gmail
        msg["To"] = notify
        msg.set_content(body)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(gmail, password)
            smtp.send_message(msg)

        return True
    except Exception as exc:
        print("EMAIL ERROR:", exc)
        return False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form

        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip()
        phone = str(data.get("phone", "")).strip()
        subject = str(data.get("subject", "")).strip()
        message = str(data.get("message", "")).strip()

        if not name or not message:
            if request.is_json:
                return jsonify({"success": False, "message": "Name and message are required."}), 400
            flash("Name and message are required.", "error")
            return redirect(url_for("contact"))

        conn = get_db()
        conn.execute("""
            INSERT INTO contacts
            (name, email, phone, subject, message)
            VALUES (?, ?, ?, ?, ?)
        """, (name, email, phone, subject, message))
        conn.commit()
        conn.close()

        send_notification(
            "New PakPotato Contact Message",
            f"""Name: {name}
Email: {email}
Phone: {phone}
Subject: {subject}

Message:
{message}
"""
        )

        if request.is_json:
            return jsonify({
                "success": True,
                "message": "Thank you. Your message has been received."
            })

        flash("Thank you. Your message has been received.", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")


@app.route("/quote", methods=["POST"])
def quote():
    data = request.get_json(silent=True) or request.form

    name = str(data.get("name", "")).strip()
    company = str(data.get("company", "")).strip()
    email = str(data.get("email", "")).strip()
    phone = str(data.get("phone", "")).strip()
    country = str(data.get("country", "")).strip()
    product = str(data.get("product", "")).strip()
    quantity = str(data.get("quantity", "")).strip()
    message = str(data.get("message", "")).strip()

    if not name:
        return jsonify({
            "success": False,
            "message": "Please enter your name."
        }), 400

    conn = get_db()
    conn.execute("""
        INSERT INTO quotes
        (name, company, email, phone, country, product, quantity, message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name, company, email, phone,
        country, product, quantity, message
    ))
    conn.commit()
    conn.close()

    send_notification(
        "New PakPotato Quote Request",
        f"""Name: {name}
Company: {company}
Email: {email}
Phone: {phone}
Country: {country}
Product: {product}
Quantity: {quantity}

Message:
{message}
"""
    )

    return jsonify({
        "success": True,
        "message": "Your quote request has been received. We will contact you soon."
    })


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if (
            username == os.getenv("ADMIN_USERNAME", "admin")
            and password == os.getenv("ADMIN_PASSWORD", "change-this-password")
        ):
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db()

    quotes = conn.execute(
        "SELECT * FROM quotes ORDER BY id DESC"
    ).fetchall()

    contacts = conn.execute(
        "SELECT * FROM contacts ORDER BY id DESC"
    ).fetchall()

    quote_unread = conn.execute(
        "SELECT COUNT(*) AS count FROM quotes WHERE is_read = 0"
    ).fetchone()["count"]

    contact_unread = conn.execute(
        "SELECT COUNT(*) AS count FROM contacts WHERE is_read = 0"
    ).fetchone()["count"]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        quotes=quotes,
        contacts=contacts,
        quote_unread=quote_unread,
        contact_unread=contact_unread
    )


@app.route("/admin/quote/<int:quote_id>/read", methods=["POST"])
@admin_required
def quote_read(quote_id):
    conn = get_db()
    conn.execute(
        "UPDATE quotes SET is_read = 1 WHERE id = ?",
        (quote_id,)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/contact/<int:contact_id>/read", methods=["POST"])
@admin_required
def contact_read(contact_id):
    conn = get_db()
    conn.execute(
        "UPDATE contacts SET is_read = 1 WHERE id = ?",
        (contact_id,)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/quote/<int:quote_id>/delete", methods=["POST"])
@admin_required
def quote_delete(quote_id):
    conn = get_db()
    conn.execute("DELETE FROM quotes WHERE id = ?", (quote_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/contact/<int:contact_id>/delete", methods=["POST"])
@admin_required
def contact_delete(contact_id):
    conn = get_db()
    conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


init_db()


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)

