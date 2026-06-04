from flask import Blueprint, render_template, request, jsonify, session
from routes.auth import login_required, role_required
from models.models import AppUser, TheatreOwnership, db
from sqlalchemy import text
import random

theatre_owner_bp = Blueprint("theatre_owner", __name__, url_prefix="/theatre-owner")


def get_owner_theatre_ids():
    user_id = session.get("user_id")
    ownerships = TheatreOwnership.query.filter_by(owner_id=user_id).all()
    return [o.theatre_db_id for o in ownerships]


@theatre_owner_bp.route("/")
@login_required
@role_required("theatre_owner")
def dashboard():
    theatre_ids = get_owner_theatre_ids()
    stats = {"total_theatres": len(theatre_ids), "total_shows": 0, "total_bookings": 0, "total_revenue": 0}
    theatres = []
    top_shows = []

    if theatre_ids:
        placeholder = ",".join([f"'{tid}'" for tid in theatre_ids])

        try:
            stats["total_shows"] = db.session.execute(text(f"""
                SELECT COUNT(*) FROM shows WHERE theater_id IN ({placeholder})
            """)).scalar() or 0

            # Count real bookings and revenue for this owner's theatres
            booking_stats = db.session.execute(text(f"""
                SELECT COUNT(ub.id) as total_bookings,
                       COALESCE(SUM(ub.total_amount), 0) as total_revenue
                FROM user_bookings ub
                JOIN shows s ON s.show_id = ub.show_id
                WHERE s.theater_id IN ({placeholder})
                  AND ub.status = 'Confirmed'
            """)).fetchone()
            if booking_stats:
                stats["total_bookings"] = booking_stats.total_bookings or 0
                stats["total_revenue"]  = float(booking_stats.total_revenue or 0)

            theatres = db.session.execute(text(f"""
                SELECT t.*, COUNT(DISTINCT s.show_id) as show_count,
                       COUNT(DISTINCT sc.screen_id) as screen_count
                FROM theaters t
                LEFT JOIN shows s ON s.theater_id = t.theater_id
                LEFT JOIN screens sc ON sc.theater_id = t.theater_id
                WHERE t.theater_id IN ({placeholder})
                GROUP BY t.theater_id, t.name, t.location, t.city, t.state
            """)).fetchall()

            top_shows = db.session.execute(text(f"""
                SELECT s.show_id, s.show_date, s.start_time, s.available_seats,
                       s.price_per_ticket, m.title as movie_title,
                       t.name as theatre_name, sc.screen_number
                FROM shows s
                JOIN movies m ON m.movie_id = s.movie_id
                JOIN theaters t ON t.theater_id = s.theater_id
                JOIN screens sc ON sc.screen_id = s.screen_id
                WHERE s.theater_id IN ({placeholder})
                ORDER BY s.show_date DESC LIMIT 10
            """)).fetchall()
        except Exception as e:
            print(f"Error loading theatre owner data: {e}")

    return render_template("theatre_owner/dashboard.html",
        stats=stats, theatres=theatres, top_shows=top_shows)


@theatre_owner_bp.route("/theatres")
@login_required
@role_required("theatre_owner")
def my_theatres():
    theatre_ids = get_owner_theatre_ids()
    theatres = []
    if theatre_ids:
        placeholder = ",".join([f"'{tid}'" for tid in theatre_ids])
        try:
            theatres = db.session.execute(text(f"""
                SELECT t.*, COUNT(DISTINCT sc.screen_id) as screen_count
                FROM theaters t
                LEFT JOIN screens sc ON sc.theater_id = t.theater_id
                WHERE t.theater_id IN ({placeholder})
                GROUP BY t.theater_id, t.name, t.location, t.city, t.state
            """)).fetchall()
        except Exception as e:
            print(f"Error: {e}")

    return render_template("theatre_owner/theatres.html", theatres=theatres)


@theatre_owner_bp.route("/theatres/<theatre_id>")
@login_required
@role_required("theatre_owner")
def theatre_detail(theatre_id):
    theatre_ids = get_owner_theatre_ids()
    if theatre_id not in theatre_ids:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        theatre = db.session.execute(text("SELECT * FROM theaters WHERE theater_id = :tid"), {"tid": theatre_id}).fetchone()
        screens = db.session.execute(text("""
            SELECT sc.*, COUNT(s.show_id) as show_count
            FROM screens sc LEFT JOIN shows s ON s.screen_id = sc.screen_id
            WHERE sc.theater_id = :tid GROUP BY sc.screen_id, sc.theater_id, sc.screen_number, sc.total_seats
        """), {"tid": theatre_id}).fetchall()
        shows = db.session.execute(text("""
            SELECT s.show_id, s.show_date, s.start_time, s.price_per_ticket, s.available_seats,
                   m.title as movie_title, sc.screen_number
            FROM shows s JOIN movies m ON m.movie_id = s.movie_id
            JOIN screens sc ON sc.screen_id = s.screen_id
            WHERE s.theater_id = :tid ORDER BY s.show_date DESC, s.start_time LIMIT 20
        """), {"tid": theatre_id}).fetchall()
    except Exception as e:
        print(f"Error: {e}")
        theatre, screens, shows = None, [], []

    return render_template("theatre_owner/theatre_detail.html",
        theatre=theatre, screens=screens, shows=shows)


@theatre_owner_bp.route("/shows")
@login_required
@role_required("theatre_owner")
def my_shows():
    theatre_ids = get_owner_theatre_ids()
    shows = []
    theatres = []
    if theatre_ids:
        placeholder = ",".join([f"'{tid}'" for tid in theatre_ids])
        try:
            shows = db.session.execute(text(f"""
                SELECT s.show_id, s.show_date, s.start_time, s.price_per_ticket, s.available_seats,
                       m.title as movie_title, t.name as theatre_name, t.city, sc.screen_number,
                       t.theater_id
                FROM shows s
                JOIN movies m ON m.movie_id = s.movie_id
                JOIN theaters t ON t.theater_id = s.theater_id
                JOIN screens sc ON sc.screen_id = s.screen_id
                WHERE s.theater_id IN ({placeholder})
                ORDER BY s.show_date DESC, s.start_time
            """)).fetchall()

            theatres = db.session.execute(text(f"""
                SELECT t.theater_id, t.name, t.city
                FROM theaters t
                WHERE t.theater_id IN ({placeholder})
                ORDER BY t.name
            """)).fetchall()
        except Exception as e:
            print(f"Error: {e}")

    return render_template("theatre_owner/shows.html", shows=shows, theatres=theatres)


@theatre_owner_bp.route("/shows/add", methods=["POST"])
@login_required
@role_required("theatre_owner")
def add_show():
    theatre_ids = get_owner_theatre_ids()
    data = request.get_json()
    movie_id    = data.get("movie_id")
    theater_id  = data.get("theater_id")
    show_date   = data.get("show_date")
    start_time  = data.get("start_time")
    price       = data.get("price_per_ticket", 150)
    avail_seats = data.get("available_seats", 100)

    if not all([movie_id, theater_id, show_date, start_time]):
        return jsonify({"success": False, "message": "Movie, Theatre, Date and Time are required."}), 400

    if theater_id not in theatre_ids:
        return jsonify({"success": False, "message": "Unauthorized: Theatre not assigned to you."}), 403

    # Check how many shows already on this date for this theatre
    existing_count = db.session.execute(text("""
        SELECT COUNT(*) FROM shows WHERE theater_id=:tid AND show_date=:dt
    """), {"tid": theater_id, "dt": show_date}).scalar() or 0

    max_shows_per_day = int(data.get("max_shows_per_day", 99))
    if existing_count >= max_shows_per_day:
        return jsonify({"success": False, "message": f"This theatre already has {existing_count} show(s) on {show_date}. Limit reached."}), 400

    # Get first screen
    screen = db.session.execute(text(
        "SELECT screen_id FROM screens WHERE theater_id=:tid LIMIT 1"
    ), {"tid": theater_id}).fetchone()

    if not screen:
        return jsonify({"success": False, "message": "No screen found for this theatre."}), 400

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


@theatre_owner_bp.route("/shows/delete/<show_id>", methods=["POST"])
@login_required
@role_required("theatre_owner")
def delete_show(show_id):
    theatre_ids = get_owner_theatre_ids()
    show = db.session.execute(text("SELECT theater_id FROM shows WHERE show_id=:sid"), {"sid": show_id}).fetchone()
    if not show or show.theater_id not in theatre_ids:
        return jsonify({"success": False, "message": "Unauthorized."}), 403
    try:
        db.session.execute(text("DELETE FROM shows WHERE show_id=:id"), {"id": show_id})
        db.session.commit()
        return jsonify({"success": True, "message": "Show deleted."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@theatre_owner_bp.route("/api/movies-list")
@login_required
@role_required("theatre_owner")
def api_movies():
    movies = db.session.execute(text("SELECT movie_id, title, genre, language FROM movies ORDER BY title")).fetchall()
    return jsonify([{"id": m.movie_id, "title": m.title, "genre": m.genre or "", "language": m.language or ""} for m in movies])


@theatre_owner_bp.route("/api/movie-search")
@login_required
@role_required("theatre_owner")
def api_movie_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    try:
        rows = db.session.execute(text(
            "SELECT movie_id, title, genre, language FROM movies WHERE title ILIKE :q ORDER BY title LIMIT 20"
        ), {"q": f"%{q}%"}).fetchall()
        return jsonify([{"movie_id": r.movie_id, "title": r.title, "genre": r.genre or "", "language": r.language or ""} for r in rows])
    except Exception:
        return jsonify([])


@theatre_owner_bp.route("/api/screens/<theatre_id>")
@login_required
@role_required("theatre_owner")
def api_screens(theatre_id):
    screens = db.session.execute(text("""
        SELECT screen_id, screen_number, total_seats FROM screens WHERE theater_id = :tid
    """), {"tid": theatre_id}).fetchall()
    return jsonify([{"id": s.screen_id, "number": s.screen_number, "seats": s.total_seats} for s in screens])


@theatre_owner_bp.route("/api/shows-count")
@login_required
@role_required("theatre_owner")
def api_shows_count():
    """Return show count for a theatre on a specific date"""
    theatre_id = request.args.get("theatre_id", "")
    date = request.args.get("date", "")
    theatre_ids = get_owner_theatre_ids()
    if not theatre_id or not date or theatre_id not in theatre_ids:
        return jsonify({"count": 0})
    try:
        count = db.session.execute(text("""
            SELECT COUNT(*) FROM shows WHERE theater_id=:tid AND show_date=:dt
        """), {"tid": theatre_id, "dt": date}).scalar() or 0
        return jsonify({"count": count})
    except Exception:
        return jsonify({"count": 0})


# ── Screens Management (Theatre Owner) ───────────────────────
@theatre_owner_bp.route("/screens")
@login_required
@role_required("theatre_owner")
def my_screens():
    theatre_ids = get_owner_theatre_ids()
    screens = []
    theatres = []
    if theatre_ids:
        placeholder = ",".join([f"'{tid}'" for tid in theatre_ids])
        try:
            screens = db.session.execute(text(f"""
                SELECT sc.screen_id, sc.screen_number, sc.total_seats,
                       t.name as theatre_name, t.city, t.theater_id,
                       COUNT(s.show_id) as show_count
                FROM screens sc
                JOIN theaters t ON t.theater_id = sc.theater_id
                LEFT JOIN shows s ON s.screen_id = sc.screen_id
                WHERE sc.theater_id IN ({placeholder})
                GROUP BY sc.screen_id, sc.screen_number, sc.total_seats, t.name, t.city, t.theater_id
                ORDER BY t.name, sc.screen_number
            """)).fetchall()

            theatres = db.session.execute(text(f"""
                SELECT theater_id, name, city FROM theaters
                WHERE theater_id IN ({placeholder}) ORDER BY name
            """)).fetchall()
        except Exception as e:
            print(f"Error: {e}")

    return render_template("theatre_owner/screens.html", screens=screens, theatres=theatres)


@theatre_owner_bp.route("/screens/add", methods=["POST"])
@login_required
@role_required("theatre_owner")
def add_screen():
    theatre_ids = get_owner_theatre_ids()
    d = request.get_json()
    theater_id    = d.get("theater_id", "").strip()
    screen_number = d.get("screen_number")
    total_seats   = d.get("total_seats", 100)

    if not theater_id or not screen_number:
        return jsonify({"success": False, "message": "Theatre and Screen Number are required."}), 400

    if theater_id not in theatre_ids:
        return jsonify({"success": False, "message": "Unauthorized: Theatre not assigned to you."}), 403

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


@theatre_owner_bp.route("/screens/delete/<screen_id>", methods=["POST"])
@login_required
@role_required("theatre_owner")
def delete_screen(screen_id):
    theatre_ids = get_owner_theatre_ids()
    screen = db.session.execute(text(
        "SELECT theater_id FROM screens WHERE screen_id=:id"
    ), {"id": screen_id}).fetchone()
    if not screen or screen.theater_id not in theatre_ids:
        return jsonify({"success": False, "message": "Unauthorized."}), 403

    show_count = db.session.execute(text(
        "SELECT COUNT(*) FROM shows WHERE screen_id=:id"
    ), {"id": screen_id}).scalar() or 0
    if show_count > 0:
        return jsonify({"success": False, "message": f"Cannot delete: {show_count} show(s) linked to this screen."}), 400

    try:
        db.session.execute(text("DELETE FROM screens WHERE screen_id=:id"), {"id": screen_id})
        db.session.commit()
        return jsonify({"success": True, "message": "Screen deleted."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@theatre_owner_bp.route("/change-password", methods=["POST"])
@login_required
@role_required("theatre_owner")
def change_password():
    data = request.get_json() or {}
    current_password = data.get("current_password", "").strip()
    new_password = data.get("new_password", "").strip()
    confirm_password = data.get("confirm_password", "").strip()

    if not current_password or not new_password or not confirm_password:
        return jsonify({"success": False, "message": "All fields are required."}), 400

    if len(new_password) < 6:
        return jsonify({"success": False, "message": "New password must be at least 6 characters."}), 400

    if new_password != confirm_password:
        return jsonify({"success": False, "message": "New passwords do not match."}), 400

    user_id = session.get("user_id")
    user = AppUser.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    if not user.check_password(current_password):
        return jsonify({"success": False, "message": "Current password is incorrect."}), 401

    if current_password == new_password:
        return jsonify({"success": False, "message": "New password must be different from current password."}), 400

    try:
        user.set_password(new_password)
        db.session.commit()
        return jsonify({"success": True, "message": "Password updated successfully!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


# ── Movies Management (Theatre Owner) ────────────────────────
@theatre_owner_bp.route("/movies")
@login_required
@role_required("theatre_owner")
def my_movies():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()
    city_filter = request.args.get("city", "").strip()
    per_page = 15
    offset = (page - 1) * per_page
    params = {"limit": per_page, "offset": offset}

    # Fetch all distinct cities for the dropdown
    try:
        city_rows = db.session.execute(
            text("SELECT DISTINCT city FROM theaters WHERE city IS NOT NULL AND city != '' ORDER BY city")
        ).fetchall()
        all_cities = [r.city for r in city_rows]
    except Exception:
        all_cities = []

    # Build WHERE clause
    if city_filter:
        # Show only movies that are showing in theatres in the selected city
        where = """
            WHERE movie_id IN (
                SELECT DISTINCT s.movie_id FROM shows s
                JOIN theaters t ON t.theater_id = s.theater_id
                WHERE LOWER(t.city) = LOWER(:city_filter)
            )
        """
        params["city_filter"] = city_filter
        if search:
            where += " AND title ILIKE :search"
            params["search"] = f"%{search}%"
    else:
        where = "WHERE 1=1"
        if search:
            where += " AND title ILIKE :search"
            params["search"] = f"%{search}%"

    total = db.session.execute(
        text(f"SELECT COUNT(*) FROM movies {where}"), params
    ).scalar() or 0

    movie_list = db.session.execute(
        text(f"SELECT * FROM movies {where} ORDER BY title LIMIT :limit OFFSET :offset"),
        params
    ).fetchall()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template("theatre_owner/movies.html",
        movies=movie_list, total=total,
        page=page, total_pages=total_pages, search=search,
        all_cities=all_cities, city_filter=city_filter)


@theatre_owner_bp.route("/movies/add", methods=["POST"])
@login_required
@role_required("theatre_owner")
def add_movie():
    d = request.get_json() or {}
    title        = d.get("title", "").strip()
    genre        = d.get("genre", "").strip()
    language     = d.get("language", "").strip()
    duration     = d.get("duration", 0)
    rating       = d.get("rating", None)
    release_date = d.get("release_date", None)
    description  = d.get("description", "").strip()

    if not title:
        return jsonify({"success": False, "message": "Movie title is required."}), 400

    # Generate unique movie_id
    movie_id = "M" + str(random.randint(100000, 999999))
    for _ in range(10):
        try:
            if not db.session.execute(
                text("SELECT movie_id FROM movies WHERE movie_id=:id"), {"id": movie_id}
            ).fetchone():
                break
            movie_id = "M" + str(random.randint(100000, 999999))
        except Exception:
            break

    try:
        db.session.execute(text("""
            INSERT INTO movies (movie_id, title, genre, language, duration, rating, release_date, description)
            VALUES (:movie_id, :title, :genre, :language, :duration, :rating, :release_date, :description)
        """), {
            "movie_id": movie_id,
            "title": title,
            "genre": genre or None,
            "language": language or None,
            "duration": int(duration) if duration else None,
            "rating": float(rating) if rating else None,
            "release_date": release_date or None,
            "description": description or None,
        })
        db.session.commit()
        return jsonify({"success": True, "message": f"Movie '{title}' added successfully! (ID: {movie_id})"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@theatre_owner_bp.route("/movies/delete/<movie_id>", methods=["POST"])
@login_required
@role_required("theatre_owner")
def delete_movie(movie_id):
    try:
        db.session.execute(text("DELETE FROM movies WHERE movie_id=:id"), {"id": movie_id})
        db.session.commit()
        return jsonify({"success": True, "message": "Movie deleted successfully."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
