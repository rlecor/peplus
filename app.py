from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
DATABASE = "peplus.db"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

INDUSTRY_MULTIPLES = {
    "home_services": (2.2, 3.2),
    "professional_services": (2.3, 3.5),
    "healthcare_services": (3.0, 5.0),
    "ecommerce": (2.0, 3.5),
    "saas": (3.5, 6.0),
    "manufacturing": (3.0, 5.0),
    "restaurant_food": (1.5, 2.8),
    "retail": (1.8, 3.0),
    "other": (2.0, 3.0),
}

EXCLUDED_INDUSTRIES = {"cannabis", "gambling", "adult", "firearms"}


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            phone TEXT,
            business_name TEXT,
            industry TEXT,
            location TEXT,
            year_founded INTEGER,
            employees INTEGER,
            owner_hours INTEGER,
            has_manager TEXT,
            recurring_revenue_pct REAL,
            top_customer_pct REAL,
            revenue_trend TEXT,
            legal_or_tax_issues TEXT,
            debt_issues TEXT,
            reason_for_selling TEXT,
            annual_revenue REAL,
            gross_profit REAL,
            net_income REAL,
            owner_salary REAL,
            interest REAL,
            taxes REAL,
            depreciation REAL,
            amortization REAL,
            add_backs REAL,
            replacement_manager_cost REAL,
            normalized_earnings REAL,
            deal_score INTEGER,
            valuation_low REAL,
            valuation_high REAL,
            offer_low REAL,
            offer_high REAL,
            result_type TEXT,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()


def money(value):
    try:
        return "${:,.0f}".format(float(value))
    except (TypeError, ValueError):
        return "$0"

app.jinja_env.filters["money"] = money


def parse_float(name, default=0.0):
    value = request.form.get(name, "").replace(",", "").strip()
    if value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_int(name, default=0):
    value = request.form.get(name, "").strip()
    if value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def years_in_business(year_founded):
    current_year = datetime.now().year
    if not year_founded or year_founded > current_year:
        return 0
    return current_year - year_founded


def score_submission(data):
    score = 50

    # Financial quality
    if data["normalized_earnings"] >= 500000:
        score += 15
    elif data["normalized_earnings"] >= 250000:
        score += 10
    elif data["normalized_earnings"] >= 100000:
        score += 5
    elif data["normalized_earnings"] <= 0:
        score -= 30

    # Revenue trend
    if data["revenue_trend"] == "growing":
        score += 10
    elif data["revenue_trend"] == "flat":
        score += 2
    elif data["revenue_trend"] == "declining":
        score -= 12

    # Owner dependence
    if data["has_manager"] == "yes":
        score += 8
    if data["owner_hours"] > 50:
        score -= 10
    elif data["owner_hours"] > 30:
        score -= 5
    elif data["owner_hours"] <= 15:
        score += 6

    # Customer concentration
    if data["top_customer_pct"] >= 50:
        score -= 18
    elif data["top_customer_pct"] >= 30:
        score -= 10
    elif data["top_customer_pct"] <= 15:
        score += 6

    # Recurring revenue
    if data["recurring_revenue_pct"] >= 70:
        score += 10
    elif data["recurring_revenue_pct"] >= 40:
        score += 5

    # Operating history
    if data["years_in_business"] >= 10:
        score += 8
    elif data["years_in_business"] >= 5:
        score += 4
    elif data["years_in_business"] < 2:
        score -= 15

    # Legal, tax, and debt issues
    if data["legal_or_tax_issues"] == "yes":
        score -= 15
    if data["debt_issues"] == "yes":
        score -= 8

    return max(0, min(100, score))


def valuation_engine(data):
    normalized_earnings = (
        data["net_income"]
        + data["owner_salary"]
        + data["interest"]
        + data["taxes"]
        + data["depreciation"]
        + data["amortization"]
        + data["add_backs"]
        - data["replacement_manager_cost"]
    )
    data["normalized_earnings"] = normalized_earnings
    data["years_in_business"] = years_in_business(data["year_founded"])

    base_low, base_high = INDUSTRY_MULTIPLES.get(data["industry"], INDUSTRY_MULTIPLES["other"])
    deal_score = score_submission(data)

    if deal_score >= 85:
        adjustment = 1.20
    elif deal_score >= 70:
        adjustment = 1.10
    elif deal_score >= 55:
        adjustment = 1.00
    elif deal_score >= 40:
        adjustment = 0.85
    else:
        adjustment = 0.70

    adjusted_low = base_low * adjustment
    adjusted_high = base_high * adjustment

    valuation_low = max(0, normalized_earnings * adjusted_low)
    valuation_high = max(0, normalized_earnings * adjusted_high)

    # PE+ offer is intentionally below estimated value to account for diligence risk and buyer margin.
    offer_low = valuation_low * 0.70
    offer_high = valuation_high * 0.85

    red_flags = []
    if data["industry"] in EXCLUDED_INDUSTRIES:
        red_flags.append("Industry requires manual review")
    if normalized_earnings <= 0:
        red_flags.append("Normalized earnings are not positive")
    if data["years_in_business"] < 2:
        red_flags.append("Operating history is under 2 years")
    if data["top_customer_pct"] >= 50:
        red_flags.append("Top customer concentration is high")
    if data["legal_or_tax_issues"] == "yes":
        red_flags.append("Legal or tax issues require review")
    if deal_score < 40:
        red_flags.append("Deal score is below auto-offer threshold")

    result_type = "manual_review" if red_flags else "auto_offer"

    return {
        "normalized_earnings": normalized_earnings,
        "deal_score": deal_score,
        "valuation_low": valuation_low,
        "valuation_high": valuation_high,
        "offer_low": offer_low,
        "offer_high": offer_high,
        "result_type": result_type,
        "red_flags": red_flags,
        "base_multiple_low": base_low,
        "base_multiple_high": base_high,
        "adjusted_multiple_low": adjusted_low,
        "adjusted_multiple_high": adjusted_high,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/intake", methods=["GET", "POST"])
def intake():
    if request.method == "POST":
        data = {
            "first_name": request.form.get("first_name", "").strip(),
            "last_name": request.form.get("last_name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "business_name": request.form.get("business_name", "").strip(),
            "industry": request.form.get("industry", "other"),
            "location": request.form.get("location", "").strip(),
            "year_founded": parse_int("year_founded"),
            "employees": parse_int("employees"),
            "owner_hours": parse_int("owner_hours"),
            "has_manager": request.form.get("has_manager", "no"),
            "recurring_revenue_pct": parse_float("recurring_revenue_pct"),
            "top_customer_pct": parse_float("top_customer_pct"),
            "revenue_trend": request.form.get("revenue_trend", "flat"),
            "legal_or_tax_issues": request.form.get("legal_or_tax_issues", "no"),
            "debt_issues": request.form.get("debt_issues", "no"),
            "reason_for_selling": request.form.get("reason_for_selling", "").strip(),
            "annual_revenue": parse_float("annual_revenue"),
            "gross_profit": parse_float("gross_profit"),
            "net_income": parse_float("net_income"),
            "owner_salary": parse_float("owner_salary"),
            "interest": parse_float("interest"),
            "taxes": parse_float("taxes"),
            "depreciation": parse_float("depreciation"),
            "amortization": parse_float("amortization"),
            "add_backs": parse_float("add_backs"),
            "replacement_manager_cost": parse_float("replacement_manager_cost"),
        }
        result = valuation_engine(data)

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO submissions (
                created_at, first_name, last_name, email, phone, business_name, industry, location,
                year_founded, employees, owner_hours, has_manager, recurring_revenue_pct, top_customer_pct,
                revenue_trend, legal_or_tax_issues, debt_issues, reason_for_selling, annual_revenue,
                gross_profit, net_income, owner_salary, interest, taxes, depreciation, amortization,
                add_backs, replacement_manager_cost, normalized_earnings, deal_score, valuation_low,
                valuation_high, offer_low, offer_high, result_type, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat(), data["first_name"], data["last_name"], data["email"], data["phone"],
            data["business_name"], data["industry"], data["location"], data["year_founded"], data["employees"],
            data["owner_hours"], data["has_manager"], data["recurring_revenue_pct"], data["top_customer_pct"],
            data["revenue_trend"], data["legal_or_tax_issues"], data["debt_issues"], data["reason_for_selling"],
            data["annual_revenue"], data["gross_profit"], data["net_income"], data["owner_salary"],
            data["interest"], data["taxes"], data["depreciation"], data["amortization"], data["add_backs"],
            data["replacement_manager_cost"], result["normalized_earnings"], result["deal_score"],
            result["valuation_low"], result["valuation_high"], result["offer_low"], result["offer_high"],
            result["result_type"], "; ".join(result["red_flags"])
        ))
        submission_id = cur.lastrowid
        conn.commit()
        conn.close()
        return redirect(url_for("result", submission_id=submission_id))

    return render_template("intake.html")


@app.route("/result/<int:submission_id>")
def result(submission_id):
    conn = get_db()
    submission = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
    conn.close()
    if not submission:
        flash("Submission not found.")
        return redirect(url_for("index"))
    red_flags = [x.strip() for x in (submission["notes"] or "").split(";") if x.strip()]
    return render_template("result.html", submission=submission, red_flags=red_flags)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Invalid password.")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


def require_admin():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    return None


@app.route("/admin")
def admin_dashboard():
    guard = require_admin()
    if guard:
        return guard
    conn = get_db()
    submissions = conn.execute("SELECT * FROM submissions ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin_dashboard.html", submissions=submissions)


@app.route("/admin/submission/<int:submission_id>")
def admin_submission(submission_id):
    guard = require_admin()
    if guard:
        return guard
    conn = get_db()
    submission = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
    conn.close()
    if not submission:
        flash("Submission not found.")
        return redirect(url_for("admin_dashboard"))
    red_flags = [x.strip() for x in (submission["notes"] or "").split(";") if x.strip()]
    return render_template("admin_submission.html", submission=submission, red_flags=red_flags)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
