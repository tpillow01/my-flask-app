# app.py
import os
from datetime import datetime
from functools import wraps
from hmac import compare_digest

from flask import (
    Flask, render_template, request, jsonify, send_from_directory,
    redirect, url_for, session, flash
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

# ── App setup ─────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "dev-insecure-change-me")

# ── Admin credentials (hard-coded) ───────────────────────────────────────
ADMIN_USERNAME = "tynanfleetadmin"
ADMIN_PASSWORD = "Tynanvans2025"

# ── Vehicle numbers (edit this list when vans change) ────────────────────
VAN_NUMBERS = [
    131, 138, 156, 159, 166, 169, 172, 174, 175, 176, 177,
    179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189,
    190, 191, 192, 193, 194, 195, 196, 198, 199, 200, 201,
    202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212,
    213, 214, 215, 217, 218, 219, 220, 221, 222, 223, 224,
    225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235,
    236, 237, 238, 239, 240
]

# ── Database ──────────────────────────────────────────────────────────────
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///checklist.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ── Models ────────────────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = "users"
    id         = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    name       = db.Column(db.String(120), nullable=False)
    username   = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(255), nullable=False)

class ChecklistEntry(db.Model):
    __tablename__ = "checklist_entries"
    id         = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    shift      = db.Column(db.String(16),  nullable=False)  # Start/End
    mechanic   = db.Column(db.String(120), nullable=False)
    van_id     = db.Column(db.String(64),  nullable=False)
    odometer   = db.Column(db.Integer,     nullable=True)
    fuel_level = db.Column(db.Integer,     nullable=True)   # 0–100

    # Core checks
    interior_clean = db.Column(db.Boolean, default=False)
    trash_removed  = db.Column(db.Boolean, default=False)
    tools_secured  = db.Column(db.Boolean, default=False)
    tires_ok       = db.Column(db.Boolean, default=False)
    lights_ok      = db.Column(db.Boolean, default=False)
    fluids_ok      = db.Column(db.Boolean, default=False)

    # Extra checks
    windshield_clean          = db.Column(db.Boolean, default=False)
    wiper_fluid_ok            = db.Column(db.Boolean, default=False)
    horn_ok                   = db.Column(db.Boolean, default=False)
    seatbelts_ok              = db.Column(db.Boolean, default=False)
    first_aid_present         = db.Column(db.Boolean, default=False)
    fire_extinguisher_present = db.Column(db.Boolean, default=False)
    backup_camera_ok          = db.Column(db.Boolean, default=False)
    registration_present      = db.Column(db.Boolean, default=False)
    turn_signals_ok           = db.Column(db.Boolean, default=False)
    brake_lights_ok           = db.Column(db.Boolean, default=False)
    spare_tire_present        = db.Column(db.Boolean, default=False)
    jack_present              = db.Column(db.Boolean, default=False)

    notes      = db.Column(db.Text, nullable=True)

# ── Startup: create tables + add any missing columns (SQLite safe) ────────
def _ensure_columns():
    try:
        cols = {row[1] for row in db.session.execute(text("PRAGMA table_info(checklist_entries)"))}
    except Exception:
        cols = set()

    if "user_id" not in cols:
        try:
            db.session.execute(text("ALTER TABLE checklist_entries ADD COLUMN user_id INTEGER"))
        except Exception as e:
            print(f"[MIGRATION] Could not add column user_id: {e}")

    needed = [
        ("interior_clean","BOOLEAN","0"), ("trash_removed","BOOLEAN","0"),
        ("tools_secured","BOOLEAN","0"), ("tires_ok","BOOLEAN","0"),
        ("lights_ok","BOOLEAN","0"), ("fluids_ok","BOOLEAN","0"),
        ("windshield_clean","BOOLEAN","0"), ("wiper_fluid_ok","BOOLEAN","0"),
        ("horn_ok","BOOLEAN","0"), ("seatbelts_ok","BOOLEAN","0"),
        ("first_aid_present","BOOLEAN","0"), ("fire_extinguisher_present","BOOLEAN","0"),
        ("backup_camera_ok","BOOLEAN","0"), ("registration_present","BOOLEAN","0"),
        ("turn_signals_ok","BOOLEAN","0"), ("brake_lights_ok","BOOLEAN","0"),
        ("spare_tire_present","BOOLEAN","0"), ("jack_present","BOOLEAN","0"),
    ]
    for name, typ, default in needed:
        if name not in cols:
            try:
                db.session.execute(text(f"ALTER TABLE checklist_entries ADD COLUMN {name} {typ} DEFAULT {default}"))
            except Exception as e:
                print(f"[MIGRATION] Could not add column {name}: {e}")

    try:
        db.session.commit()
    except Exception as e:
        print(f"[MIGRATION] Commit error: {e}")
        db.session.rollback()

with app.app_context():
    db.create_all()
    _ensure_columns()

# ── Helpers & guards ─────────────────────────────────────────────────────
def current_user():
    uid = session.get("user_id")
    return User.query.get(uid) if uid else None

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("user_id") and not session.get("admin_authed"):
            return redirect(url_for("auth", view="login", next=request.path))
        return f(*a, **k)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin_authed"):
            return redirect(url_for("auth", view="login", next=request.path))
        return f(*a, **k)
    return w

def api_login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("user_id") and not session.get("admin_authed"):
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return f(*a, **k)
    return w

@app.context_processor
def inject_ctx():
    return {"current_user": current_user(), "admin_authed": bool(session.get("admin_authed"))}

# ── Auth (single page with toggle) ────────────────────────────────────────
@app.get("/auth")
def auth():
    view = request.args.get("view", "login")
    return render_template("auth.html", title="Sign In", view=view)

@app.post("/auth/login")
def auth_login():
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "")

    if compare_digest(username, ADMIN_USERNAME) and compare_digest(password, ADMIN_PASSWORD):
        session["admin_authed"] = True
        flash("Admin signed in.", "ok")
        return redirect(request.args.get("next") or url_for("index"))

    u = User.query.filter_by(username=username.lower()).first()
    if not u or not check_password_hash(u.password, password):
        flash("Invalid username or password.", "error")
        return redirect(url_for("auth", view="login"))
    session["user_id"] = u.id
    flash("Signed in.", "ok")
    return redirect(request.args.get("next") or url_for("index"))

@app.post("/auth/create")
def auth_create():
    name = (request.form.get("name") or "").strip()
    username = (request.form.get("username") or "").strip().lower()
    password = request.form.get("password") or ""
    if not name or not username or not password:
        flash("Please fill out all fields to create an account.", "error")
        return redirect(url_for("auth", view="create"))
    if compare_digest(username, ADMIN_USERNAME):
        flash("That username is reserved.", "error")
        return redirect(url_for("auth", view="create"))
    if User.query.filter_by(username=username).first():
        flash("That username already exists. Try signing in.", "error")
        return redirect(url_for("auth", view="login"))

    u = User(name=name, username=username, password=generate_password_hash(password))
    db.session.add(u); db.session.commit()
    session["user_id"] = u.id
    flash("Account created and signed in.", "ok")
    return redirect(url_for("index"))

@app.post("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("admin_authed", None)
    flash("Signed out.", "ok")
    return redirect(url_for("auth", view="login"))

@app.get("/login")
def _alias_login():
    return redirect(url_for("auth", view="login"))

@app.get("/signup")
def _alias_signup():
    return redirect(url_for("auth", view="create"))

# ── Pages ────────────────────────────────────────────────────────────────
@app.get("/")
@login_required
def index():
    vans = [str(n) for n in VAN_NUMBERS]  # make strings for select values
    return render_template("index.html", vans=vans, me=current_user(), title="Van Daily Checklist")

@app.get("/admin/submissions")
@admin_required
def admin_submissions():
    return render_template("admin_submissions.html", title="Recent Submissions")

# ── APIs ─────────────────────────────────────────────────────────────────
def _to_bool(v):
    return str(v).lower() in {"1","true","on","yes"} if v is not None else False

def _to_int(v):
    if v in (None, "", "null"): return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

@app.get("/api/entries")
@admin_required
def api_entries():
    rows = ChecklistEntry.query.order_by(ChecklistEntry.created_at.desc()).limit(300).all()
    def as_dict(r):
        return {
            "id": r.id, "created_at": r.created_at.isoformat(),
            "shift": r.shift, "mechanic": r.mechanic, "van_id": r.van_id,
            "odometer": r.odometer, "fuel_level": r.fuel_level,
            "interior_clean": r.interior_clean, "trash_removed": r.trash_removed,
            "tools_secured": r.tools_secured, "tires_ok": r.tires_ok,
            "lights_ok": r.lights_ok, "fluids_ok": r.fluids_ok,
            "windshield_clean": r.windshield_clean, "wiper_fluid_ok": r.wiper_fluid_ok,
            "horn_ok": r.horn_ok, "seatbelts_ok": r.seatbelts_ok,
            "first_aid_present": r.first_aid_present, "fire_extinguisher_present": r.fire_extinguisher_present,
            "backup_camera_ok": r.backup_camera_ok, "registration_present": r.registration_present,
            "turn_signals_ok": r.turn_signals_ok, "brake_lights_ok": r.brake_lights_ok,
            "spare_tire_present": r.spare_tire_present, "jack_present": r.jack_present,
            "notes": r.notes or ""
        }
    return jsonify([as_dict(r) for r in rows])

@app.post("/api/submit")
@api_login_required
def api_submit():
    try:
        d = request.get_json(force=True) or {}

        for k in ("shift","mechanic","van_id"):
            if not d.get(k):
                return jsonify({"ok": False, "error": f"Missing field: {k}"}), 400

        entry = ChecklistEntry(
            user_id = (current_user().id if current_user() else None),
            shift = d.get("shift"),
            mechanic = d.get("mechanic"),
            van_id = d.get("van_id"),
            odometer = _to_int(d.get("odometer")),
            fuel_level = _to_int(d.get("fuel_level")),

            interior_clean = _to_bool(d.get("interior_clean")),
            trash_removed  = _to_bool(d.get("trash_removed")),
            tools_secured  = _to_bool(d.get("tools_secured")),
            tires_ok       = _to_bool(d.get("tires_ok")),
            lights_ok      = _to_bool(d.get("lights_ok")),
            fluids_ok      = _to_bool(d.get("fluids_ok")),

            windshield_clean          = _to_bool(d.get("windshield_clean")),
            wiper_fluid_ok            = _to_bool(d.get("wiper_fluid_ok")),
            horn_ok                   = _to_bool(d.get("horn_ok")),
            seatbelts_ok              = _to_bool(d.get("seatbelts_ok")),
            first_aid_present         = _to_bool(d.get("first_aid_present")),
            fire_extinguisher_present = _to_bool(d.get("fire_extinguisher_present")),
            backup_camera_ok          = _to_bool(d.get("backup_camera_ok")),
            registration_present      = _to_bool(d.get("registration_present")),
            turn_signals_ok           = _to_bool(d.get("turn_signals_ok")),
            brake_lights_ok           = _to_bool(d.get("brake_lights_ok")),
            spare_tire_present        = _to_bool(d.get("spare_tire_present")),
            jack_present              = _to_bool(d.get("jack_present")),

            notes = (d.get("notes") or "").strip()
        )

        db.session.add(entry)
        db.session.commit()
        return jsonify({"ok": True, "id": entry.id})

    except Exception as e:
        import traceback; traceback.print_exc()
        db.session.rollback()
        return jsonify({"ok": False, "error": f"server_error: {e.__class__.__name__}"}), 500

# ── PWA assets & health ──────────────────────────────────────────────────
@app.get("/service-worker.js")
def sw():
    return send_from_directory("static", "service-worker.js", mimetype="text/javascript")

@app.get("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")

@app.get("/health")
def health():
    return "ok", 200

# ── Entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
