from flask import Blueprint, render_template, redirect, url_for, session, request, flash, jsonify, current_app
from models.models import AppUser, Role, OtpToken, db
from functools import wraps
import random, string, smtplib, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

auth_bp = Blueprint("auth", __name__)


# ── decorators ──────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to continue.", "warning")
            return redirect(url_for("public.home"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("public.home"))
            if session.get("role") not in roles:
                flash("Access denied.", "danger")
                return redirect(url_for("public.home"))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── helpers ──────────────────────────────────────────────────────
def _send_otp_email(to_email: str, otp: str) -> bool:
    """Send OTP via Gmail SMTP. Reads credentials from Flask app config.
    Priority: current_app.config → os.environ → dev-mode console fallback.
    """
    # Always pull from app config first (set in config.py / .env)
    mail_user = (
        current_app.config.get("MAIL_USERNAME") or
        os.environ.get("MAIL_USERNAME", "")
    ).strip()
    mail_pass = (
        current_app.config.get("MAIL_PASSWORD") or
        os.environ.get("MAIL_PASSWORD", "")
    ).strip()

    # Dev/fallback mode – no real credentials configured
    if not mail_user or not mail_pass or mail_user == "your_email@gmail.com":
        print(f"\n{'='*50}")
        print(f"  [DEV MODE] OTP for {to_email}:  {otp}")
        print(f"  (Configure MAIL_USERNAME / MAIL_PASSWORD to send real email)")
        print(f"{'='*50}\n")
        return True   # return True so the UI flow continues in dev

    html_body = f"""
    <div style="font-family:'Segoe UI',sans-serif;max-width:480px;margin:auto;
                background:#0e1420;border-radius:14px;overflow:hidden;
                border:1px solid #1a2235;">
      <div style="background:linear-gradient(135deg,#e5383b,#c00);
                  padding:28px;text-align:center;">
        <h2 style="color:#fff;margin:0;font-size:1.5rem;letter-spacing:1px;">
          🎬 CineBook
        </h2>
        <p style="color:rgba(255,255,255,.75);margin:6px 0 0;font-size:.9rem;">
          Password Reset Request
        </p>
      </div>
      <div style="padding:36px;text-align:center;">
        <h3 style="color:#fff;margin:0 0 10px;font-size:1.15rem;">
          Your One-Time Password
        </h3>
        <p style="color:rgba(255,255,255,.5);font-size:.88rem;margin-bottom:28px;
                  line-height:1.6;">
          Enter this code to reset your password.<br>
          It expires in <strong style="color:#e5383b;">10 minutes</strong>.
        </p>
        <div style="background:#1a2235;border:2px dashed #e5383b;
                    border-radius:12px;padding:22px 20px;margin-bottom:26px;
                    letter-spacing:14px;font-size:2.4rem;font-weight:900;
                    color:#e5383b;font-family:monospace;">
          {otp}
        </div>
        <p style="color:rgba(255,255,255,.3);font-size:.78rem;margin:0;">
          If you did not request a password reset, please ignore this email.
        </p>
      </div>
      <div style="background:#070b14;padding:16px;text-align:center;">
        <p style="color:rgba(255,255,255,.25);font-size:.75rem;margin:0;">
          &copy; 2025 CineBook. All rights reserved.
        </p>
      </div>
    </div>"""

    # ── Try STARTTLS on port 587 first (works on most networks) ──
    # ── then fall back to SSL on port 465 ──
    last_error = None
    for method, host, port in [
        ("starttls", "smtp.gmail.com", 587),
        ("ssl",      "smtp.gmail.com", 465),
    ]:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "CineBook – Password Reset OTP"
            msg["From"]    = f"CineBook <{mail_user}>"
            msg["To"]      = to_email
            msg.attach(MIMEText(html_body, "html"))

            if method == "starttls":
                server = smtplib.SMTP(host, port, timeout=15)
                server.ehlo()
                server.starttls()
                server.ehlo()
            else:
                import ssl as _ssl
                ctx = _ssl.create_default_context()
                server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=15)

            server.login(mail_user, mail_pass)
            server.sendmail(mail_user, to_email, msg.as_string())
            server.quit()
            print(f"✅ OTP email sent to {to_email} via {method.upper()}:{port}")
            return True
        except Exception as e:
            last_error = e
            print(f"⚠️  SMTP {method.upper()}:{port} failed: {e}")
            continue

    print(f"❌ All SMTP methods failed for {to_email}: {last_error}")
    return False


def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))


def _get_redirect_url(role):
    if role == "admin":         return url_for("admin.dashboard")
    if role == "theatre_owner": return url_for("theatre_owner.dashboard")
    return url_for("public.home")


def _redirect_by_role(role):
    return redirect(_get_redirect_url(role))


# ── login (JSON only – page shows modal) ────────────────────────
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return _redirect_by_role(session.get("role"))
    # GET → redirect home (modal is embedded in base.html)
    if request.method == "GET":
        return redirect(url_for("public.home") + "?showLogin=1")
    # POST (AJAX)
    data     = request.get_json() if request.is_json else request.form
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    user     = AppUser.query.filter_by(email=email, is_active=True).first()
    if user and user.check_password(password):
        session["user_id"]    = user.id
        session["user_name"]  = user.name
        session["role"]       = user.role_name
        session["user_email"] = user.email
        return jsonify({"success": True, "role": user.role_name,
                        "redirect": _get_redirect_url(user.role_name)})
    return jsonify({"success": False, "message": "Invalid email or password."}), 401


# ── signup ───────────────────────────────────────────────────────
@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        # Redirect to home and trigger signup modal via query param
        return redirect(url_for("public.home") + "?showSignup=1")
    data     = request.get_json() if request.is_json else request.form
    name     = data.get("name", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    phone    = data.get("phone", "")
    city     = data.get("city", "")
    if AppUser.query.filter_by(email=email).first():
        msg = "Email already registered."
        if request.is_json:
            return jsonify({"success": False, "message": msg}), 400
        flash(msg, "danger")
        return render_template("auth/signup.html")
    user_role = Role.query.filter_by(name="user").first()
    user = AppUser(name=name, email=email, role_id=user_role.id, phone=phone, city=city)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    session["user_id"]    = user.id
    session["user_name"]  = user.name
    session["role"]       = "user"
    session["user_email"] = user.email
    if request.is_json:
        return jsonify({"success": True, "redirect": url_for("public.home")})
    return redirect(url_for("public.home"))


# ── logout ───────────────────────────────────────────────────────
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("public.home"))


# ════════════════════════════════════════════════════════════════
#  FORGOT PASSWORD – 3-step API
#  Step 1: POST /forgot-password/send-otp   { email }
#  Step 2: POST /forgot-password/verify-otp { email, otp }
#  Step 3: POST /forgot-password/reset      { email, otp, password }
# ════════════════════════════════════════════════════════════════

@auth_bp.route("/forgot-password/send-otp", methods=["POST"])
def fp_send_otp():
    data  = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"success": False, "message": "Email is required."}), 400
    user = AppUser.query.filter_by(email=email, is_active=True).first()
    if not user:
        # Don't reveal whether email exists – always return success
        return jsonify({"success": True,
                        "message": "If that email is registered, an OTP has been sent."})
    # Invalidate old OTPs for this email
    OtpToken.query.filter_by(email=email, used=False).update({"used": True})
    db.session.commit()
    otp   = _generate_otp()
    token = OtpToken(email=email, otp=otp)
    db.session.add(token)
    db.session.commit()
    sent = _send_otp_email(email, otp)
    if not sent:
        return jsonify({"success": False, "message": "Failed to send email. Try again."}), 500
    return jsonify({"success": True, "message": "OTP sent to your email."})


@auth_bp.route("/forgot-password/verify-otp", methods=["POST"])
def fp_verify_otp():
    data  = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    otp   = data.get("otp", "").strip()
    if not email or not otp:
        return jsonify({"success": False, "message": "Email and OTP are required."}), 400
    cutoff = datetime.utcnow() - timedelta(minutes=10)
    token  = OtpToken.query.filter_by(email=email, otp=otp, used=False).filter(
                 OtpToken.created_at >= cutoff).first()
    if not token:
        return jsonify({"success": False, "message": "Invalid or expired OTP."}), 400
    return jsonify({"success": True, "message": "OTP verified."})


@auth_bp.route("/forgot-password/reset", methods=["POST"])
def fp_reset():
    data     = request.get_json(silent=True) or {}
    email    = data.get("email", "").strip().lower()
    otp      = data.get("otp", "").strip()
    password = data.get("password", "")
    if not email or not otp or not password:
        return jsonify({"success": False, "message": "All fields are required."}), 400
    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters."}), 400
    cutoff = datetime.utcnow() - timedelta(minutes=10)
    token  = OtpToken.query.filter_by(email=email, otp=otp, used=False).filter(
                 OtpToken.created_at >= cutoff).first()
    if not token:
        return jsonify({"success": False, "message": "Invalid or expired OTP."}), 400
    user = AppUser.query.filter_by(email=email, is_active=True).first()
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404
    user.set_password(password)
    token.used = True
    db.session.commit()
    return jsonify({"success": True, "message": "Password reset successfully! You can now login."})
