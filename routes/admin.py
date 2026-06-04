from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from routes.auth import login_required, role_required
from models.models import AppUser, Role, TheatreOwnership, db
from sqlalchemy import text
import random, string, secrets, uuid

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def gen_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(chars) for _ in range(length))


def send_email_credentials(to_email, owner_name, password):
    """Send credentials email to theatre owner. Returns (success, message)."""
    try:
        from flask import current_app
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        mail_user = current_app.config.get('MAIL_USERNAME', '')
        mail_pass = current_app.config.get('MAIL_PASSWORD', '')

        if not mail_user or not mail_pass or mail_user == 'your_email@gmail.com':
            return False, "Email not configured (see .env)"

        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Your CineBook Theatre Owner Account Credentials"
        msg['From'] = mail_user
        msg['To'] = to_email

        html = f"""
        <html><body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px">
        <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.1)">
          <div style="background:#e5383b;padding:24px;text-align:center">
            <h2 style="color:#fff;margin:0">🎬 CineBook</h2>
            <p style="color:rgba(255,255,255,.85);margin:6px 0 0">Theatre Owner Account Created</p>
          </div>
          <div style="padding:28px">
            <p>Hello <strong>{owner_name}</strong>,</p>
            <p>Your Theatre Owner account has been created. Use the credentials below to login:</p>
            <div style="background:#f8f9fa;border-radius:8px;padding:16px;margin:16px 0;border-left:4px solid #e5383b">
              <p style="margin:0 0 8px"><strong>Login URL:</strong> <a href="#">https://bookmyshow.com/login</a></p>
              <p style="margin:0 0 8px"><strong>Email:</strong> {to_email}</p>
              <p style="margin:0"><strong>Password:</strong> <span style="font-family:monospace;background:#fff;padding:2px 8px;border-radius:4px;border:1px solid #dee2e6">{password}</span></p>
            </div>
            <p style="color:#666;font-size:14px">Please change your password after first login for security.</p>
            <p style="color:#666;font-size:14px">If you have questions, contact your administrator.</p>
          </div>
          <div style="background:#f8f9fa;padding:16px;text-align:center">
            <p style="color:#999;font-size:12px;margin:0">&copy; 2024 CineBook. All rights reserved.</p>
          </div>
        </div>
        </body></html>
        """
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(mail_user, mail_pass)
            server.sendmail(mail_user, to_email, msg.as_string())

        return True, "Email sent successfully"
    except Exception as e:
        return False, str(e)


# ── Dashboard ────────────────────────────────────────────────
@admin_bp.route("/")
@login_required
@role_required("admin")
def dashboard():
    stats = {}
    try:
        stats["total_movies"]   = db.session.execute(text("SELECT COUNT(*) FROM movies")).scalar() or 0
        stats["total_theatres"] = db.session.execute(text("SELECT COUNT(*) FROM theaters")).scalar() or 0
        stats["total_shows"]    = db.session.execute(text("SELECT COUNT(*) FROM shows")).scalar() or 0
        stats["total_users"]    = db.session.execute(text("SELECT COUNT(*) FROM dataset_users")).scalar() or 0
    except:
        stats = {"total_movies": 0, "total_theatres": 0, "total_shows": 0, "total_users": 0}
    stats["app_users"] = AppUser.query.count()

    try:
        top_movies = db.session.execute(text("""
            SELECT m.title, COUNT(s.show_id) as show_count
            FROM movies m JOIN shows s ON s.movie_id = m.movie_id
            GROUP BY m.title ORDER BY show_count DESC LIMIT 5
        """)).fetchall()
    except:
        top_movies = []

    try:
        top_cities = db.session.execute(text("""
            SELECT city, COUNT(*) as cnt FROM theaters GROUP BY city ORDER BY cnt DESC LIMIT 5
        """)).fetchall()
    except:
        top_cities = []

    try:
        genre_dist = db.session.execute(text("""
            SELECT genre, COUNT(*) as cnt FROM movies WHERE genre IS NOT NULL GROUP BY genre ORDER BY cnt DESC LIMIT 8
        """)).fetchall()
    except:
        genre_dist = []

    theatre_owners = AppUser.query.join(Role).filter(Role.name == "theatre_owner").all()

    # Recent contact messages for dashboard preview
    from models.models import ContactMessage
    try:
        recent_messages  = ContactMessage.query.order_by(ContactMessage.created_at.desc()).limit(5).all()
        unread_msg_count = ContactMessage.query.filter_by(status="unread").count()
    except Exception:
        recent_messages  = []
        unread_msg_count = 0

    return render_template("admin/dashboard.html",
        stats=stats, top_movies=top_movies, top_cities=top_cities,
        genre_dist=genre_dist, theatre_owners=theatre_owners,
        recent_messages=recent_messages, unread_msg_count=unread_msg_count)


# ── Movies Management ────────────────────────────────────────
@admin_bp.route("/movies")
@login_required
@role_required("admin")
def movies():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "")
    per_page = 15
    offset = (page - 1) * per_page
    params = {"limit": per_page, "offset": offset}
    where = "WHERE 1=1"
    if search:
        where += " AND title ILIKE :search"
        params["search"] = f"%{search}%"
    total = db.session.execute(text(f"SELECT COUNT(*) FROM movies {where}"), params).scalar() or 0
    movie_list = db.session.execute(
        text(f"SELECT * FROM movies {where} ORDER BY title LIMIT :limit OFFSET :offset"), params
    ).fetchall()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template("admin/movies.html", movies=movie_list, total=total,
        page=page, total_pages=total_pages, search=search)


@admin_bp.route("/movies/add", methods=["POST"])
@login_required
@role_required("admin")
def add_movie():
    d = request.get_json()
    title       = d.get("title", "").strip()
    genre       = d.get("genre", "").strip()
    language    = d.get("language", "").strip()
    duration    = d.get("duration", 0)
    rating      = d.get("rating", None)
    release_date = d.get("release_date", None)
    description = d.get("description", "").strip()

    if not title:
        return jsonify({"success": False, "message": "Title is required."}), 400

    movie_id = "M" + str(random.randint(100000, 999999))
    # Ensure unique
    while True:
        try:
            existing = db.session.execute(text("SELECT movie_id FROM movies WHERE movie_id=:id"), {"id": movie_id}).fetchone()
            if not existing:
                break
            movie_id = "M" + str(random.randint(100000, 999999))
        except:
            break

    try:
        db.session.execute(text("""
            INSERT INTO movies (movie_id, title, genre, language, duration, rating, release_date, description)
            VALUES (:movie_id, :title, :genre, :language, :duration, :rating, :release_date, :description)
        """), {
            "movie_id": movie_id, "title": title, "genre": genre or None,
            "language": language or None, "duration": int(duration) if duration else None,
            "rating": float(rating) if rating else None,
            "release_date": release_date or None, "description": description or None
        })
        db.session.commit()
        return jsonify({"success": True, "message": f"Movie '{title}' added successfully!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/movies/delete/<movie_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_movie(movie_id):
    try:
        db.session.execute(text("DELETE FROM movies WHERE movie_id=:id"), {"id": movie_id})
        db.session.commit()
        return jsonify({"success": True, "message": "Movie deleted."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


# ── Theatres Management ──────────────────────────────────────
@admin_bp.route("/theatres")
@login_required
@role_required("admin")
def theatres():
    page = request.args.get("page", 1, type=int)
    city_filter = request.args.get("city", "")
    per_page = 15
    offset = (page - 1) * per_page
    params = {"limit": per_page, "offset": offset}
    where = "WHERE 1=1"
    if city_filter:
        where += " AND t.city ILIKE :city"
        params["city"] = f"%{city_filter}%"
    total = db.session.execute(text(f"SELECT COUNT(*) FROM theaters t {where}"), params).scalar() or 0
    theatre_list = db.session.execute(text(f"""
        SELECT t.*, COUNT(DISTINCT s.screen_id) as screen_count,
               COUNT(DISTINCT sh.show_id) as show_count
        FROM theaters t
        LEFT JOIN screens s ON s.theater_id = t.theater_id
        LEFT JOIN shows sh ON sh.theater_id = t.theater_id
        {where}
        GROUP BY t.theater_id, t.name, t.location, t.city, t.state
        ORDER BY t.name LIMIT :limit OFFSET :offset
    """), params).fetchall()
    total_pages = max(1, (total + per_page - 1) // per_page)
    cities = [r[0] for r in db.session.execute(text("SELECT DISTINCT city FROM theaters WHERE city IS NOT NULL ORDER BY city")).fetchall()]
    theatre_owners = AppUser.query.join(Role).filter(Role.name == "theatre_owner").all()
    return render_template("admin/theatres.html", theatres=theatre_list, total=total,
        page=page, total_pages=total_pages, cities=cities, city_filter=city_filter,
        theatre_owners=theatre_owners)


@admin_bp.route("/theatres/add", methods=["POST"])
@login_required
@role_required("admin")
def add_theatre():
    d = request.get_json()
    name     = d.get("name", "").strip()
    city     = d.get("city", "").strip()
    state    = d.get("state", "").strip()
    location = d.get("location", "").strip()

    if not name or not city:
        return jsonify({"success": False, "message": "Name and City are required."}), 400

    theater_id = "T" + str(random.randint(100000, 999999))
    try:
        db.session.execute(text("""
            INSERT INTO theaters (theater_id, name, city, state, location)
            VALUES (:theater_id, :name, :city, :state, :location)
        """), {"theater_id": theater_id, "name": name, "city": city,
               "state": state or None, "location": location or None})
        db.session.commit()
        return jsonify({"success": True, "message": f"Theatre '{name}' added successfully!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/theatres/delete/<theatre_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_theatre(theatre_id):
    try:
        db.session.execute(text("DELETE FROM theaters WHERE theater_id=:id"), {"id": theatre_id})
        db.session.commit()
        return jsonify({"success": True, "message": "Theatre deleted."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


# ── Shows Management ─────────────────────────────────────────
@admin_bp.route("/shows")
@login_required
@role_required("admin")
def shows():
    page = request.args.get("page", 1, type=int)
    per_page = 15
    offset = (page - 1) * per_page
    total = db.session.execute(text("SELECT COUNT(*) FROM shows")).scalar() or 0
    show_list = db.session.execute(text("""
        SELECT s.show_id, s.show_date, s.start_time, s.price_per_ticket, s.available_seats,
               m.title as movie_title, t.name as theatre_name, t.city, sc.screen_number
        FROM shows s
        JOIN movies m ON m.movie_id = s.movie_id
        JOIN theaters t ON t.theater_id = s.theater_id
        JOIN screens sc ON sc.screen_id = s.screen_id
        ORDER BY s.show_date DESC, s.start_time
        LIMIT :limit OFFSET :offset
    """), {"limit": per_page, "offset": offset}).fetchall()
    total_pages = max(1, (total + per_page - 1) // per_page)

    # Theatre list for dropdowns (movies now use autocomplete search)
    theatre_list = db.session.execute(text("SELECT theater_id, name, city FROM theaters ORDER BY name")).fetchall()

    return render_template("admin/shows.html", shows=show_list, total=total,
        page=page, total_pages=total_pages,
        theatre_list=theatre_list)


@admin_bp.route("/shows/add", methods=["POST"])
@login_required
@role_required("admin")
def add_show():
    d = request.get_json()
    movie_id    = d.get("movie_id")
    theater_id  = d.get("theater_id")
    show_date   = d.get("show_date")
    start_time  = d.get("start_time")
    price       = d.get("price_per_ticket", 150)
    avail_seats = d.get("available_seats", 100)

    if not all([movie_id, theater_id, show_date, start_time]):
        return jsonify({"success": False, "message": "Movie, Theatre, Date and Time are required."}), 400

    # Get first screen of the theatre
    screen = db.session.execute(text(
        "SELECT screen_id FROM screens WHERE theater_id=:tid LIMIT 1"
    ), {"tid": theater_id}).fetchone()

    if not screen:
        return jsonify({"success": False, "message": "No screen found for this theatre. Add a screen first."}), 400

    show_id = "SH" + str(random.randint(100000, 999999))
    try:
        db.session.execute(text("""
            INSERT INTO shows (show_id, movie_id, theater_id, screen_id, show_date, start_time, price_per_ticket, available_seats)
            VALUES (:show_id, :movie_id, :theater_id, :screen_id, :show_date, :start_time, :price, :seats)
        """), {
            "show_id": show_id, "movie_id": movie_id, "theater_id": theater_id,
            "screen_id": screen.screen_id, "show_date": show_date,
            "start_time": start_time, "price": float(price), "seats": int(avail_seats)
        })
        db.session.commit()
        return jsonify({"success": True, "message": "Show added successfully!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/shows/delete/<show_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_show(show_id):
    try:
        db.session.execute(text("DELETE FROM shows WHERE show_id=:id"), {"id": show_id})
        db.session.commit()
        return jsonify({"success": True, "message": "Show deleted."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


# ── Theatre Owners ───────────────────────────────────────────
@admin_bp.route("/theatre-owners")
@login_required
@role_required("admin")
def theatre_owners():
    owners = AppUser.query.join(Role).filter(Role.name == "theatre_owner").all()
    return render_template("admin/theatre_owners.html", owners=owners)


@admin_bp.route("/theatre-owners/create", methods=["POST"])
@login_required
@role_required("admin")
def create_theatre_owner():
    data  = request.get_json()
    name  = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "")
    city  = data.get("city", "")

    if not name or not email:
        return jsonify({"success": False, "message": "Name and email are required."}), 400

    if AppUser.query.filter_by(email=email).first():
        return jsonify({"success": False, "message": "Email already exists."}), 400

    owner_role = Role.query.filter_by(name="theatre_owner").first()
    if not owner_role:
        owner_role = Role(name="theatre_owner")
        db.session.add(owner_role)
        db.session.commit()

    password = gen_password()
    user = AppUser(name=name, email=email, role_id=owner_role.id, phone=phone, city=city)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # Try to send email
    email_sent, email_msg = send_email_credentials(email, name, password)

    return jsonify({
        "success": True,
        "message": "Theatre owner created successfully!",
        "email_sent": email_sent,
        "email_status": email_msg
    })


@admin_bp.route("/theatre-owners/<int:owner_id>/assign-theatre", methods=["POST"])
@login_required
@role_required("admin")
def assign_theatre(owner_id):
    data = request.get_json()
    theatre_id = data.get("theatre_id")
    existing = TheatreOwnership.query.filter_by(owner_id=owner_id, theatre_db_id=theatre_id).first()
    if existing:
        return jsonify({"success": False, "message": "Theatre already assigned."})
    ownership = TheatreOwnership(owner_id=owner_id, theatre_db_id=theatre_id)
    db.session.add(ownership)
    db.session.commit()
    return jsonify({"success": True, "message": "Theatre assigned successfully."})


@admin_bp.route("/theatre-owners/<int:owner_id>/deactivate", methods=["POST"])
@login_required
@role_required("admin")
def deactivate_owner(owner_id):
    user = AppUser.query.get_or_404(owner_id)
    user.is_active = not user.is_active
    db.session.commit()
    status = "activated" if user.is_active else "deactivated"
    return jsonify({"success": True, "message": f"Owner {status}.", "is_active": user.is_active})


@admin_bp.route("/theatre-owners/<int:owner_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_owner(owner_id):
    user = AppUser.query.get_or_404(owner_id)
    name = user.name
    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"success": True, "message": f"Owner '{name}' deleted successfully."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


# ── Users ─────────────────────────────────────────────────────
@admin_bp.route("/users")
@login_required
@role_required("admin")
def users():
    app_users = AppUser.query.order_by(AppUser.created_at.desc()).all()
    return render_template("admin/users.html", users=app_users)


# ── API helpers ───────────────────────────────────────────────
@admin_bp.route("/api/theatres-list")
@login_required
@role_required("admin")
def api_theatres_list():
    theatres = db.session.execute(text("SELECT theater_id, name, city FROM theaters ORDER BY name")).fetchall()
    return jsonify([{"id": t.theater_id, "name": t.name, "city": t.city} for t in theatres])


@admin_bp.route("/api/theatre-brands")
@login_required
@role_required("admin")
def api_theatre_brands():
    rows = db.session.execute(text(
        "SELECT theater_id, name, city FROM theaters ORDER BY name"
    )).fetchall()
    from collections import defaultdict
    brands = defaultdict(lambda: {"count": 0, "cities": set()})
    for r in rows:
        parts = (r.name or "").split()
        brand = " ".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else "Unknown")
        brands[brand]["count"] += 1
        if r.city:
            brands[brand]["cities"].add(r.city)
    result = []
    for brand, info in sorted(brands.items()):
        result.append({
            "brand": brand,
            "count": info["count"],
            "sample_cities": sorted(info["cities"])[:4],
        })
    return jsonify(result)


@admin_bp.route("/theatre-owners/<int:owner_id>/assign-brand", methods=["POST"])
@login_required
@role_required("admin")
def assign_brand(owner_id):
    data = request.get_json() or {}
    brand = data.get("brand", "").strip()
    if not brand:
        return jsonify({"success": False, "message": "Brand name required."}), 400
    rows = db.session.execute(text(
        "SELECT theater_id FROM theaters WHERE name LIKE :prefix ORDER BY theater_id"
    ), {"prefix": brand + "%"}).fetchall()
    theatre_ids = [r.theater_id for r in rows]
    if not theatre_ids:
        return jsonify({"success": False, "message": "No theatres found for brand."}), 404
    existing = {o.theatre_db_id for o in TheatreOwnership.query.filter_by(owner_id=owner_id).all()}
    new_count = 0
    try:
        for tid in theatre_ids:
            if tid not in existing:
                db.session.add(TheatreOwnership(owner_id=owner_id, theatre_db_id=tid))
                new_count += 1
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Assigned {new_count} '{brand}' theatres ({len(theatre_ids) - new_count} already assigned).",
            "assigned": new_count,
            "total": len(theatre_ids)
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/theatre-owners/<int:owner_id>/unassign-brand", methods=["POST"])
@login_required
@role_required("admin")
def unassign_brand(owner_id):
    data = request.get_json() or {}
    brand = data.get("brand", "").strip()
    if not brand:
        return jsonify({"success": False, "message": "Brand name required."}), 400
    rows = db.session.execute(text(
        "SELECT theater_id FROM theaters WHERE name LIKE :prefix"
    ), {"prefix": brand + "%"}).fetchall()
    theatre_ids = {r.theater_id for r in rows}
    try:
        removed = 0
        for o in TheatreOwnership.query.filter_by(owner_id=owner_id).all():
            if o.theatre_db_id in theatre_ids:
                db.session.delete(o)
                removed += 1
        db.session.commit()
        return jsonify({"success": True, "message": f"Removed {removed} '{brand}' theatres from owner."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/api/screens-by-theatre/<theatre_id>")
@login_required
@role_required("admin")
def api_screens_by_theatre(theatre_id):
    screens = db.session.execute(text(
        "SELECT screen_id, screen_number, total_seats FROM screens WHERE theater_id=:tid ORDER BY screen_number"
    ), {"tid": theatre_id}).fetchall()
    return jsonify([{"id": s.screen_id, "number": s.screen_number, "seats": s.total_seats} for s in screens])


# ── Carousel Management ──────────────────────────────────────
# All carousel routes use raw SQL only – no ORM FKs to the movies table.
import base64

@admin_bp.route("/carousel")
@login_required
@role_required("admin")
def carousel():
    try:
        slides = db.session.execute(text("""
            SELECT cs.id, cs.movie_id, cs.badge_label, cs.image_url, cs.image_data,
                   cs.trailer_url, cs.display_order, cs.is_active, cs.created_at, m.title, m.genre, m.rating
            FROM carousel_slides cs
            JOIN movies m ON m.movie_id = cs.movie_id
            ORDER BY cs.display_order ASC, cs.id ASC
        """)).fetchall()
    except Exception:
        slides = []

    try:
        movie_list = db.session.execute(text(
            "SELECT movie_id, title, genre FROM movies ORDER BY title LIMIT 500"
        )).fetchall()
    except Exception:
        movie_list = []

    return render_template("admin/carousel.html", slides=slides, movie_list=movie_list)


@admin_bp.route("/carousel/add", methods=["POST"])
@login_required
@role_required("admin")
def carousel_add():
    try:
        movie_id      = request.form.get("movie_id", "").strip()
        badge_label   = request.form.get("badge_label", "NOW SHOWING").strip()
        image_url     = request.form.get("image_url", "").strip()
        trailer_url   = request.form.get("trailer_url", "").strip() or None
        display_order = int(request.form.get("display_order", 0) or 0)

        if not movie_id:
            return jsonify({"success": False, "message": "Please select a movie."}), 400

        mv = db.session.execute(text("SELECT movie_id FROM movies WHERE movie_id=:id"), {"id": movie_id}).fetchone()
        if not mv:
            return jsonify({"success": False, "message": "Movie not found."}), 404

        image_data = None
        file = request.files.get("image_file")
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in {"jpg", "jpeg", "png", "gif", "webp"}:
                return jsonify({"success": False, "message": "Only JPG, PNG, GIF, WEBP images allowed."}), 400
            raw = file.read()
            if len(raw) > 5 * 1024 * 1024:
                return jsonify({"success": False, "message": "Image must be under 5 MB."}), 400
            mime = f"image/{'jpeg' if ext == 'jpg' else ext}"
            image_data = "data:" + mime + ";base64," + base64.b64encode(raw).decode()
            image_url  = None

        db.session.execute(text("""
            INSERT INTO carousel_slides
                (movie_id, badge_label, image_url, image_data, trailer_url, display_order, is_active, created_at)
            VALUES
                (:movie_id, :badge_label, :image_url, :image_data, :trailer_url, :display_order, TRUE, NOW())
        """), {
            "movie_id": movie_id,
            "badge_label": badge_label or "NOW SHOWING",
            "image_url": image_url or None,
            "image_data": image_data,
            "trailer_url": trailer_url,
            "display_order": display_order,
        })
        db.session.commit()
        return jsonify({"success": True, "message": "Slide added to carousel!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/carousel/<int:slide_id>/toggle", methods=["POST"])
@login_required
@role_required("admin")
def carousel_toggle(slide_id):
    try:
        row = db.session.execute(
            text("SELECT id, is_active FROM carousel_slides WHERE id=:id"), {"id": slide_id}
        ).fetchone()
        if not row:
            return jsonify({"success": False, "message": "Slide not found."}), 404
        new_state = not row.is_active
        db.session.execute(
            text("UPDATE carousel_slides SET is_active=:s WHERE id=:id"),
            {"s": new_state, "id": slide_id}
        )
        db.session.commit()
        status = "activated" if new_state else "deactivated"
        return jsonify({"success": True, "message": f"Slide {status}.", "is_active": new_state})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/carousel/<int:slide_id>/reorder", methods=["POST"])
@login_required
@role_required("admin")
def carousel_reorder(slide_id):
    try:
        data  = request.get_json()
        order = int(data.get("display_order", 0))
        db.session.execute(
            text("UPDATE carousel_slides SET display_order=:o WHERE id=:id"),
            {"o": order, "id": slide_id}
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Order updated."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/carousel/<int:slide_id>/edit", methods=["POST"])
@login_required
@role_required("admin")
def carousel_edit(slide_id):
    try:
        row = db.session.execute(
            text("SELECT id, badge_label, display_order, trailer_url FROM carousel_slides WHERE id=:id"), {"id": slide_id}
        ).fetchone()
        if not row:
            return jsonify({"success": False, "message": "Slide not found."}), 404

        badge_label   = (request.form.get("badge_label") or row.badge_label or "NOW SHOWING").strip()
        display_order = int(request.form.get("display_order") or row.display_order or 0)
        image_url     = request.form.get("image_url", "").strip()
        trailer_url   = request.form.get("trailer_url", "").strip() or None
        image_data    = None

        file = request.files.get("image_file")
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            raw = file.read()
            mime = f"image/{'jpeg' if ext == 'jpg' else ext}"
            image_data = "data:" + mime + ";base64," + base64.b64encode(raw).decode()
            image_url  = None

        if image_data:
            db.session.execute(text("""
                UPDATE carousel_slides
                SET badge_label=:b, display_order=:o, image_data=:d, image_url=NULL, trailer_url=:t
                WHERE id=:id
            """), {"b": badge_label, "o": display_order, "d": image_data, "t": trailer_url, "id": slide_id})
        elif image_url:
            db.session.execute(text("""
                UPDATE carousel_slides
                SET badge_label=:b, display_order=:o, image_url=:u, image_data=NULL, trailer_url=:t
                WHERE id=:id
            """), {"b": badge_label, "o": display_order, "u": image_url, "t": trailer_url, "id": slide_id})
        else:
            db.session.execute(text("""
                UPDATE carousel_slides
                SET badge_label=:b, display_order=:o, trailer_url=:t
                WHERE id=:id
            """), {"b": badge_label, "o": display_order, "t": trailer_url, "id": slide_id})

        db.session.commit()
        return jsonify({"success": True, "message": "Slide updated."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/carousel/<int:slide_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def carousel_delete(slide_id):
    try:
        db.session.execute(
            text("DELETE FROM carousel_slides WHERE id=:id"), {"id": slide_id}
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Slide removed from carousel."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/api/movie-search")
@login_required
@role_required("admin")
def api_movie_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    try:
        rows = db.session.execute(text(
            "SELECT movie_id, title, genre, language FROM movies WHERE title ILIKE :q ORDER BY title LIMIT 20"
        ), {"q": f"%{q}%"}).fetchall()
        return jsonify([{"movie_id": r.movie_id, "title": r.title, "genre": r.genre or "", "language": r.language or ""} for r in rows])
    except Exception as e:
        return jsonify([])


@admin_bp.route("/api/owner-theatres/<int:owner_id>")
@login_required
@role_required("admin")
def api_owner_theatres(owner_id):
    ownerships = TheatreOwnership.query.filter_by(owner_id=owner_id).all()
    theatre_ids = [o.theatre_db_id for o in ownerships]
    if not theatre_ids:
        return jsonify([])
    placeholder = ",".join([f"'{tid}'" for tid in theatre_ids])
    try:
        theatres = db.session.execute(text(f"""
            SELECT t.theater_id, t.name, t.city, t.state, t.location,
                   COUNT(DISTINCT sc.screen_id) as screen_count,
                   COUNT(DISTINCT sh.show_id) as show_count
            FROM theaters t
            LEFT JOIN screens sc ON sc.theater_id = t.theater_id
            LEFT JOIN shows sh ON sh.theater_id = t.theater_id
            WHERE t.theater_id IN ({placeholder})
            GROUP BY t.theater_id, t.name, t.city, t.state, t.location
            ORDER BY t.name
        """)).fetchall()
        return jsonify([{
            "theater_id": r.theater_id, "name": r.name, "city": r.city or "",
            "state": r.state or "", "location": r.location or "",
            "screen_count": r.screen_count, "show_count": r.show_count
        } for r in theatres])
    except Exception as e:
        return jsonify([])


@admin_bp.route("/theatre-owners/<int:owner_id>/remove-theatre", methods=["POST"])
@login_required
@role_required("admin")
def remove_theatre_from_owner(owner_id):
    data = request.get_json()
    theatre_id = data.get("theatre_id")
    ownership = TheatreOwnership.query.filter_by(owner_id=owner_id, theatre_db_id=theatre_id).first()
    if not ownership:
        return jsonify({"success": False, "message": "Assignment not found."})
    db.session.delete(ownership)
    db.session.commit()
    return jsonify({"success": True, "message": "Theatre removed from owner."})


# ── Screens Management ───────────────────────────────────────
@admin_bp.route("/screens")
@login_required
@role_required("admin")
def screens():
    theatre_filter = request.args.get("theatre_id", "")
    params = {}
    where = "WHERE 1=1"
    if theatre_filter:
        where += " AND sc.theater_id = :tid"
        params["tid"] = theatre_filter

    screen_list = db.session.execute(text(f"""
        SELECT sc.screen_id, sc.screen_number, sc.total_seats,
               t.name as theatre_name, t.city, t.theater_id,
               COUNT(s.show_id) as show_count
        FROM screens sc
        JOIN theaters t ON t.theater_id = sc.theater_id
        LEFT JOIN shows s ON s.screen_id = sc.screen_id
        {where}
        GROUP BY sc.screen_id, sc.screen_number, sc.total_seats, t.name, t.city, t.theater_id
        ORDER BY t.name, sc.screen_number
    """), params).fetchall()

    theatre_list = db.session.execute(text("SELECT theater_id, name, city FROM theaters ORDER BY name")).fetchall()
    total = len(screen_list)
    return render_template("admin/screens.html", screens=screen_list, total=total,
        theatre_list=theatre_list, theatre_filter=theatre_filter)


@admin_bp.route("/screens/add", methods=["POST"])
@login_required
@role_required("admin")
def add_screen():
    d = request.get_json()
    theater_id    = d.get("theater_id", "").strip()
    screen_number = d.get("screen_number")
    total_seats   = d.get("total_seats", 100)

    if not theater_id or not screen_number:
        return jsonify({"success": False, "message": "Theatre and Screen Number are required."}), 400

    # Check duplicate screen number in same theatre
    existing = db.session.execute(text(
        "SELECT screen_id FROM screens WHERE theater_id=:tid AND screen_number=:num"
    ), {"tid": theater_id, "num": int(screen_number)}).fetchone()
    if existing:
        return jsonify({"success": False, "message": f"Screen #{screen_number} already exists in this theatre."}), 400

    screen_id = "SC" + str(random.randint(100000, 999999))
    try:
        db.session.execute(text("""
            INSERT INTO screens (screen_id, theater_id, screen_number, total_seats)
            VALUES (:screen_id, :theater_id, :screen_number, :total_seats)
        """), {
            "screen_id": screen_id, "theater_id": theater_id,
            "screen_number": int(screen_number), "total_seats": int(total_seats)
        })
        db.session.commit()
        return jsonify({"success": True, "message": f"Screen #{screen_number} added successfully!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/screens/delete/<screen_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_screen(screen_id):
    # Check if screen has shows
    show_count = db.session.execute(text(
        "SELECT COUNT(*) FROM shows WHERE screen_id=:id"
    ), {"id": screen_id}).scalar() or 0
    if show_count > 0:
        return jsonify({"success": False, "message": f"Cannot delete: {show_count} show(s) are linked to this screen."}), 400
    try:
        db.session.execute(text("DELETE FROM screens WHERE screen_id=:id"), {"id": screen_id})
        db.session.commit()
        return jsonify({"success": True, "message": "Screen deleted."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/api/screens-summary")
@login_required
@role_required("admin")
def api_screens_summary():
    """Return screen count per theatre for dashboard use"""
    rows = db.session.execute(text("""
        SELECT t.theater_id, t.name, COUNT(sc.screen_id) as screen_count
        FROM theaters t
        LEFT JOIN screens sc ON sc.theater_id = t.theater_id
        GROUP BY t.theater_id, t.name ORDER BY t.name
    """)).fetchall()
    return jsonify([{"id": r.theater_id, "name": r.name, "screens": r.screen_count} for r in rows])


# ── Messages / Contact Inbox ──────────────────────────────────
@admin_bp.route("/messages")
@login_required
@role_required("admin")
def messages():
    from models.models import ContactMessage
    status_filter = request.args.get("status", "")
    category_filter = request.args.get("category", "")
    page = request.args.get("page", 1, type=int)
    per_page = 15

    q = ContactMessage.query.order_by(ContactMessage.created_at.desc())
    if status_filter:
        q = q.filter_by(status=status_filter)
    if category_filter:
        q = q.filter_by(category=category_filter)

    total = q.count()
    msgs  = q.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = max(1, (total + per_page - 1) // per_page)

    unread_count = ContactMessage.query.filter_by(status="unread").count()
    categories   = [r[0] for r in ContactMessage.query.with_entities(ContactMessage.category).distinct().all()]

    return render_template("admin/messages.html",
        msgs=msgs, total=total, page=page, total_pages=total_pages,
        status_filter=status_filter, category_filter=category_filter,
        unread_count=unread_count, categories=categories)


@admin_bp.route("/messages/<int:msg_id>/read", methods=["POST"])
@login_required
@role_required("admin")
def message_mark_read(msg_id):
    from models.models import ContactMessage
    m = ContactMessage.query.get_or_404(msg_id)
    if m.status == "unread":
        m.status = "read"
        db.session.commit()
    return jsonify({"success": True, "status": m.status})


@admin_bp.route("/messages/<int:msg_id>/reply", methods=["POST"])
@login_required
@role_required("admin")
def message_reply(msg_id):
    from models.models import ContactMessage
    from datetime import datetime
    m = ContactMessage.query.get_or_404(msg_id)
    data = request.get_json() or {}
    reply_text = (data.get("reply") or "").strip()
    if not reply_text:
        return jsonify({"success": False, "message": "Reply cannot be empty."}), 400
    m.admin_reply = reply_text
    m.replied_at  = datetime.utcnow()
    m.status      = "replied"
    db.session.commit()
    return jsonify({"success": True, "message": "Reply saved."})


@admin_bp.route("/messages/<int:msg_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def message_delete(msg_id):
    from models.models import ContactMessage
    m = ContactMessage.query.get_or_404(msg_id)
    db.session.delete(m)
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/api/messages/unread-count")
@login_required
@role_required("admin")
def api_unread_count():
    from models.models import ContactMessage
    count = ContactMessage.query.filter_by(status="unread").count()
    return jsonify({"count": count})


# ── Analytics Dashboard ──────────────────────────────────────
@admin_bp.route("/analytics")
@login_required
@role_required("admin")
def analytics():
    return render_template("admin/analytics.html")


@admin_bp.route("/api/analytics/bookings-trend")
@login_required
@role_required("admin")
def api_bookings_trend():
    """Daily booking trend for last 90 days (from shows table)."""
    try:
        rows = db.session.execute(text("""
            SELECT show_date::text AS day, COUNT(*) AS cnt
            FROM shows
            WHERE show_date IS NOT NULL
            GROUP BY show_date
            ORDER BY show_date DESC
            LIMIT 90
        """)).fetchall()
        data = [{"day": r.day, "cnt": r.cnt} for r in reversed(rows)]
    except Exception as e:
        data = []
    return jsonify(data)


@admin_bp.route("/api/analytics/bookings-by-city")
@login_required
@role_required("admin")
def api_bookings_by_city():
    """Total shows per city (proxy for booking volume by city)."""
    try:
        rows = db.session.execute(text("""
            SELECT t.city, COUNT(s.show_id) AS cnt
            FROM shows s
            JOIN theaters t ON t.theater_id = s.theater_id
            WHERE t.city IS NOT NULL
            GROUP BY t.city
            ORDER BY cnt DESC
            LIMIT 15
        """)).fetchall()
        data = [{"city": r.city, "cnt": r.cnt} for r in rows]
    except:
        data = []
    return jsonify(data)


@admin_bp.route("/api/analytics/peak-periods")
@login_required
@role_required("admin")
def api_peak_periods():
    """Shows count grouped by month and weekday."""
    try:
        month_rows = db.session.execute(text("""
            SELECT TO_CHAR(show_date, 'Mon') AS label,
                   EXTRACT(MONTH FROM show_date) AS month_num,
                   COUNT(*) AS cnt
            FROM shows WHERE show_date IS NOT NULL
            GROUP BY label, month_num ORDER BY month_num
        """)).fetchall()
        months = [{"label": r.label, "cnt": r.cnt} for r in month_rows]

        day_rows = db.session.execute(text("""
            SELECT TO_CHAR(show_date, 'Dy') AS label,
                   EXTRACT(DOW FROM show_date) AS dow,
                   COUNT(*) AS cnt
            FROM shows WHERE show_date IS NOT NULL
            GROUP BY label, dow ORDER BY dow
        """)).fetchall()
        days = [{"label": r.label, "cnt": r.cnt} for r in day_rows]
    except:
        months, days = [], []
    return jsonify({"months": months, "days": days})


@admin_bp.route("/api/analytics/time-slots")
@login_required
@role_required("admin")
def api_time_slots():
    """Shows by time slot: morning, afternoon, evening, night."""
    try:
        rows = db.session.execute(text("""
            SELECT
              CASE
                WHEN start_time::time < '12:00' THEN 'Morning'
                WHEN start_time::time < '16:00' THEN 'Afternoon'
                WHEN start_time::time < '20:00' THEN 'Evening'
                ELSE 'Night'
              END AS slot,
              COUNT(*) AS cnt
            FROM shows
            WHERE start_time IS NOT NULL
            GROUP BY slot ORDER BY MIN(start_time)
        """)).fetchall()
        data = [{"slot": r.slot, "cnt": r.cnt} for r in rows]
    except:
        data = []
    return jsonify(data)


@admin_bp.route("/api/analytics/top-movies")
@login_required
@role_required("admin")
def api_top_movies():
    """Top 10 movies by number of shows."""
    try:
        rows = db.session.execute(text("""
            SELECT m.title, COUNT(s.show_id) AS cnt
            FROM movies m JOIN shows s ON s.movie_id = m.movie_id
            GROUP BY m.title ORDER BY cnt DESC LIMIT 10
        """)).fetchall()
        data = [{"title": r.title, "cnt": r.cnt} for r in rows]
    except:
        data = []
    return jsonify(data)


@admin_bp.route("/api/analytics/genre-performance")
@login_required
@role_required("admin")
def api_genre_performance():
    """Shows per genre."""
    try:
        rows = db.session.execute(text("""
            SELECT m.genre, COUNT(s.show_id) AS shows,
                   COALESCE(SUM(s.price_per_ticket), 0) AS revenue
            FROM movies m JOIN shows s ON s.movie_id = m.movie_id
            WHERE m.genre IS NOT NULL
            GROUP BY m.genre ORDER BY shows DESC LIMIT 12
        """)).fetchall()
        data = [{"genre": r.genre, "shows": r.shows, "revenue": float(r.revenue)} for r in rows]
    except:
        data = []
    return jsonify(data)


@admin_bp.route("/api/analytics/movie-trends")
@login_required
@role_required("admin")
def api_movie_trends():
    """Monthly show trend for top 5 movies."""
    try:
        top5 = db.session.execute(text("""
            SELECT m.movie_id, m.title, COUNT(*) AS cnt
            FROM movies m JOIN shows s ON s.movie_id = m.movie_id
            GROUP BY m.movie_id, m.title ORDER BY cnt DESC LIMIT 5
        """)).fetchall()
        result = {}
        for row in top5:
            months = db.session.execute(text("""
                SELECT TO_CHAR(show_date,'YYYY-MM') AS ym, COUNT(*) AS cnt
                FROM shows WHERE movie_id = :mid AND show_date IS NOT NULL
                GROUP BY ym ORDER BY ym
            """), {"mid": row.movie_id}).fetchall()
            result[row.title] = [{"ym": m.ym, "cnt": m.cnt} for m in months]
    except:
        result = {}
    return jsonify(result)


@admin_bp.route("/api/analytics/ratings-bookings")
@login_required
@role_required("admin")
def api_ratings_bookings():
    """Movie rating vs show count scatter data."""
    try:
        rows = db.session.execute(text("""
            SELECT m.title, CAST(m.rating AS FLOAT) AS rating, COUNT(s.show_id) AS shows
            FROM movies m JOIN shows s ON s.movie_id = m.movie_id
            WHERE m.rating IS NOT NULL
            GROUP BY m.title, m.rating ORDER BY shows DESC LIMIT 50
        """)).fetchall()
        data = [{"title": r.title, "rating": r.rating, "shows": r.shows} for r in rows]
    except:
        data = []
    return jsonify(data)


@admin_bp.route("/api/analytics/top-theatres")
@login_required
@role_required("admin")
def api_top_theatres():
    """Top theatres by show count."""
    try:
        rows = db.session.execute(text("""
            SELECT t.name, COUNT(s.show_id) AS cnt
            FROM theaters t JOIN shows s ON s.theater_id = t.theater_id
            GROUP BY t.name ORDER BY cnt DESC LIMIT 10
        """)).fetchall()
        data = [{"name": r.name, "cnt": r.cnt} for r in rows]
    except:
        data = []
    return jsonify(data)


@admin_bp.route("/api/analytics/theatre-by-city")
@login_required
@role_required("admin")
def api_theatre_by_city():
    """Theatre performance by city (grouped bar)."""
    try:
        rows = db.session.execute(text("""
            SELECT t.city, t.name, COUNT(s.show_id) AS shows
            FROM theaters t JOIN shows s ON s.theater_id = t.theater_id
            WHERE t.city IS NOT NULL
            GROUP BY t.city, t.name ORDER BY t.city, shows DESC
        """)).fetchall()
        from collections import defaultdict
        city_map = defaultdict(list)
        for r in rows:
            city_map[r.city].append({"name": r.name, "shows": r.shows})
        # Keep top 6 cities for readability
        top_cities = sorted(city_map.items(), key=lambda x: sum(t["shows"] for t in x[1]), reverse=True)[:6]
        data = [{"city": city, "theatres": theatres[:5]} for city, theatres in top_cities]
    except:
        data = []
    return jsonify(data)


@admin_bp.route("/api/analytics/seat-occupancy")
@login_required
@role_required("admin")
def api_seat_occupancy():
    """Seat occupancy: available vs total per theatre."""
    try:
        rows = db.session.execute(text("""
            SELECT t.name,
                   SUM(sc.total_seats) AS total_seats,
                   SUM(s.available_seats) AS available_seats
            FROM shows s
            JOIN theaters t ON t.theater_id = s.theater_id
            JOIN screens sc ON sc.screen_id = s.screen_id
            WHERE sc.total_seats IS NOT NULL AND s.available_seats IS NOT NULL
            GROUP BY t.name ORDER BY total_seats DESC LIMIT 10
        """)).fetchall()
        data = []
        for r in rows:
            total = r.total_seats or 0
            avail = r.available_seats or 0
            booked = max(0, total - avail)
            pct = round((booked / total * 100), 1) if total > 0 else 0
            data.append({"name": r.name, "total": total, "booked": booked, "available": avail, "pct": pct})
    except:
        data = []
    return jsonify(data)


@admin_bp.route("/api/analytics/screen-type")
@login_required
@role_required("admin")
def api_screen_type():
    """Shows by screen number (as proxy for screen tier)."""
    try:
        rows = db.session.execute(text("""
            SELECT sc.screen_number, COUNT(s.show_id) AS shows,
                   COALESCE(SUM(s.price_per_ticket),0) AS revenue
            FROM shows s JOIN screens sc ON sc.screen_id = s.screen_id
            WHERE sc.screen_number IS NOT NULL
            GROUP BY sc.screen_number ORDER BY sc.screen_number
        """)).fetchall()
        data = [{"screen": f"Screen {r.screen_number}", "shows": r.shows, "revenue": float(r.revenue)} for r in rows]
    except:
        data = []
    return jsonify(data)


# ═══════════════════════════════════════════════════════════════
#  UPCOMING MOVIES MANAGER
# ═══════════════════════════════════════════════════════════════

def _ensure_upcoming_table():
    """Create upcoming_movies table if it doesn't exist yet."""
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS upcoming_movies (
                id            SERIAL PRIMARY KEY,
                movie_id      VARCHAR(20) NOT NULL,
                poster_url    TEXT,
                poster_data   TEXT,
                release_label VARCHAR(80) DEFAULT 'Coming Soon',
                display_order INTEGER DEFAULT 0,
                is_active     BOOLEAN DEFAULT TRUE,
                created_at    TIMESTAMP DEFAULT NOW()
            )
        """))
        db.session.commit()
    except Exception:
        db.session.rollback()


@admin_bp.route("/upcoming")
@login_required
@role_required("admin")
def upcoming():
    _ensure_upcoming_table()
    try:
        items = db.session.execute(text("""
            SELECT u.id, u.movie_id, u.poster_url, u.poster_data,
                   u.release_label, u.display_order, u.is_active, u.created_at,
                   m.title, m.genre, m.rating, m.release_date
            FROM upcoming_movies u
            JOIN movies m ON m.movie_id = u.movie_id
            ORDER BY u.display_order ASC, u.id ASC
        """)).fetchall()
    except Exception:
        items = []

    try:
        movie_list = db.session.execute(text(
            "SELECT movie_id, title, genre FROM movies ORDER BY title LIMIT 500"
        )).fetchall()
    except Exception:
        movie_list = []

    # IDs already in upcoming (so we can mark them in the dropdown)
    already_added_ids = {it.movie_id for it in items}

    return render_template("admin/upcoming.html", items=items, movie_list=movie_list,
                           already_added_ids=already_added_ids)


@admin_bp.route("/upcoming/add", methods=["POST"])
@login_required
@role_required("admin")
def upcoming_add():
    _ensure_upcoming_table()
    try:
        movie_id      = request.form.get("movie_id", "").strip()
        release_label = request.form.get("release_label", "Coming Soon").strip()
        poster_url    = request.form.get("poster_url", "").strip()
        display_order = int(request.form.get("display_order", 0) or 0)

        if not movie_id:
            return jsonify({"success": False, "message": "Please select a movie."}), 400

        mv = db.session.execute(text("SELECT movie_id FROM movies WHERE movie_id=:id"), {"id": movie_id}).fetchone()
        if not mv:
            return jsonify({"success": False, "message": "Movie not found."}), 404

        # Check for duplicate
        existing = db.session.execute(text(
            "SELECT id FROM upcoming_movies WHERE movie_id=:mid"
        ), {"mid": movie_id}).fetchone()
        if existing:
            return jsonify({"success": False, "message": "This movie is already in the upcoming section."}), 400

        poster_data = None
        file = request.files.get("poster_file")
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in {"jpg", "jpeg", "png", "gif", "webp"}:
                return jsonify({"success": False, "message": "Only JPG, PNG, GIF, WEBP images allowed."}), 400
            raw = file.read()
            if len(raw) > 5 * 1024 * 1024:
                return jsonify({"success": False, "message": "Image must be under 5 MB."}), 400
            mime = f"image/{'jpeg' if ext == 'jpg' else ext}"
            poster_data = "data:" + mime + ";base64," + base64.b64encode(raw).decode()
            poster_url  = None

        db.session.execute(text("""
            INSERT INTO upcoming_movies
                (movie_id, poster_url, poster_data, release_label, display_order, is_active, created_at)
            VALUES
                (:movie_id, :poster_url, :poster_data, :release_label, :display_order, TRUE, NOW())
        """), {
            "movie_id": movie_id,
            "poster_url": poster_url or None,
            "poster_data": poster_data,
            "release_label": release_label or "Coming Soon",
            "display_order": display_order,
        })
        db.session.commit()
        return jsonify({"success": True, "message": "Movie added to Upcoming section!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/upcoming/<int:item_id>/toggle", methods=["POST"])
@login_required
@role_required("admin")
def upcoming_toggle(item_id):
    try:
        row = db.session.execute(
            text("SELECT id, is_active FROM upcoming_movies WHERE id=:id"), {"id": item_id}
        ).fetchone()
        if not row:
            return jsonify({"success": False, "message": "Not found."}), 404
        new_state = not row.is_active
        db.session.execute(
            text("UPDATE upcoming_movies SET is_active=:s WHERE id=:id"),
            {"s": new_state, "id": item_id}
        )
        db.session.commit()
        return jsonify({"success": True, "active": new_state})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/upcoming/<int:item_id>/edit", methods=["POST"])
@login_required
@role_required("admin")
def upcoming_edit(item_id):
    try:
        row = db.session.execute(
            text("SELECT id FROM upcoming_movies WHERE id=:id"), {"id": item_id}
        ).fetchone()
        if not row:
            return jsonify({"success": False, "message": "Not found."}), 404

        release_label = request.form.get("release_label", "").strip()
        display_order = int(request.form.get("display_order", 0) or 0)
        poster_url    = request.form.get("poster_url", "").strip()

        if release_label:
            db.session.execute(
                text("UPDATE upcoming_movies SET release_label=:l WHERE id=:id"),
                {"l": release_label, "id": item_id}
            )
        db.session.execute(
            text("UPDATE upcoming_movies SET display_order=:o WHERE id=:id"),
            {"o": display_order, "id": item_id}
        )

        file = request.files.get("poster_file")
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in {"jpg", "jpeg", "png", "gif", "webp"}:
                return jsonify({"success": False, "message": "Only JPG, PNG, GIF, WEBP images."}), 400
            raw = file.read()
            if len(raw) > 5 * 1024 * 1024:
                return jsonify({"success": False, "message": "Image under 5 MB only."}), 400
            mime = f"image/{'jpeg' if ext == 'jpg' else ext}"
            pdata = "data:" + mime + ";base64," + base64.b64encode(raw).decode()
            db.session.execute(
                text("UPDATE upcoming_movies SET poster_data=:d, poster_url=NULL WHERE id=:id"),
                {"d": pdata, "id": item_id}
            )
        elif poster_url:
            db.session.execute(
                text("UPDATE upcoming_movies SET poster_url=:u, poster_data=NULL WHERE id=:id"),
                {"u": poster_url, "id": item_id}
            )

        db.session.commit()
        return jsonify({"success": True, "message": "Updated successfully."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/upcoming/<int:item_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def upcoming_delete(item_id):
    try:
        db.session.execute(
            text("DELETE FROM upcoming_movies WHERE id=:id"), {"id": item_id}
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Removed from Upcoming section."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
