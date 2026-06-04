from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from sqlalchemy import text
from database.db import db
import random

public_bp = Blueprint("public", __name__)

PER_PAGE = 12

# Genre → verified working TMDB poster paths (w500 size)
GENRE_POSTERS = {
    "Action": [
        "https://image.tmdb.org/t/p/w500/8YFL5QQVPy3AgrEQxNYVSgiPEbe.jpg",  # Mad Max
        "https://image.tmdb.org/t/p/w500/A4j8S6moJS2zNtRR8T9ByKSQkp.jpg",  # John Wick 4
        "https://image.tmdb.org/t/p/w500/1E5baAaEse26fej7uHcjOgEE2t2.jpg",  # The Dark Knight
        "https://image.tmdb.org/t/p/w500/qNBAXBIQlnOThrVvA6mA2B5ggV6.jpg",  # Mission Impossible
        "https://image.tmdb.org/t/p/w500/t6HIqrRAclMCA60NsSmeqe9RmNV.jpg",  # Top Gun Maverick
        "https://image.tmdb.org/t/p/w500/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",  # Fight Club
    ],
    "Drama": [
        "https://image.tmdb.org/t/p/w500/3bhkrj58Vtu7enYsLLeQiw0vZ2u.jpg",  # Godfather
        "https://image.tmdb.org/t/p/w500/arw2vcBveWOVZr6pxd9XTd1TdQa.jpg",  # Shawshank
        "https://image.tmdb.org/t/p/w500/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg",  # Joker
        "https://image.tmdb.org/t/p/w500/q6y0Go1tsGEsmtFryDOJo3dEmqu.jpg",  # Schindler's List
        "https://image.tmdb.org/t/p/w500/39wmItIWsg5sZMyRUHLkWBcuVCM.jpg",  # Parasite
    ],
    "Comedy": [
        "https://image.tmdb.org/t/p/w500/rXMWOZiCt6eMX22jWuTOSdQ98bY.jpg",  # Grand Budapest Hotel
        "https://image.tmdb.org/t/p/w500/zMkPPShOXkQ6QHkNPmRnb3sCCgR.jpg",  # Superbad
        "https://image.tmdb.org/t/p/w500/vZloFAK7NmvMGKE7VkF5UHaz0I.jpg",  # Home Alone
        "https://image.tmdb.org/t/p/w500/tl9MowiKm7ggFoJaxJouPJBxuTk.jpg",  # Knives Out
    ],
    "Thriller": [
        "https://image.tmdb.org/t/p/w500/q719jXXEzOoYaps6babgKnONONX.jpg",  # Se7en
        "https://image.tmdb.org/t/p/w500/jYEW5xZkZk2WTrdbMGAPFuBqbDc.jpg",  # Inception
        "https://image.tmdb.org/t/p/w500/AmR3JfkerDef6MhEjWIziWDMpey.jpg",  # Gone Girl
        "https://image.tmdb.org/t/p/w500/hO7KbdvGOtDdejBgnD7LFnCuAI7.jpg",  # Prisoners
    ],
    "Romance": [
        "https://image.tmdb.org/t/p/w500/mMtUybQ6hL24FXo0F3Z4j2KG7kZ.jpg",  # La La Land
        "https://image.tmdb.org/t/p/w500/eMMiyXHlEFqqnVSfKS0wSBpAfnL.jpg",  # Titanic
        "https://image.tmdb.org/t/p/w500/lvhE6EBAsys8XktkuvcuBg2DKJF.jpg",  # Before Sunrise
        "https://image.tmdb.org/t/p/w500/5gzzkR7y3hnY8AD1wXjCnVlHba5.jpg",  # Eternal Sunshine
    ],
    "Sci-Fi": [
        "https://image.tmdb.org/t/p/w500/d5NXSklpcuveIZBv5v0TBzDIPPk.jpg",  # Dune
        "https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg",  # Interstellar
        "https://image.tmdb.org/t/p/w500/8IB2e4r4oVhHnANbnm7O3Tj6tF8.jpg",  # Blade Runner 2049
        "https://image.tmdb.org/t/p/w500/vfrQk5IPloGg1v9Rzbh2Eg3VGyM.jpg",  # The Matrix
        "https://image.tmdb.org/t/p/w500/6MKr3KgOLmzOP6MSuZERO41Lpbb.jpg",  # Arrival
    ],
    "Horror": [
        "https://image.tmdb.org/t/p/w500/bQXAqRx2Fgc46uCVWgoPz5L5Dtr.jpg",  # The Shining
        "https://image.tmdb.org/t/p/w500/xbb7rjCVqmnJDLkk8q4DP7MoAB4.jpg",  # Get Out
        "https://image.tmdb.org/t/p/w500/7uoiKOEjCQgOTBMSCnmqDPOQzqn.jpg",  # Hereditary
    ],
    "Animation": [
        "https://image.tmdb.org/t/p/w500/vc8bCGjdVp0UbMNLzHnHSLRbBWQ.jpg",  # Spirited Away
        "https://image.tmdb.org/t/p/w500/jtsG0TXjERNQuz53o2dUv7yDL0U.jpg",  # Up
        "https://image.tmdb.org/t/p/w500/pjeMs3yqRmFL3giJy4PMXWZTRwx.jpg",  # Spider-Verse
    ],
    "default": [
        "https://image.tmdb.org/t/p/w500/kG3vKNMJHSJoNbASS4nRb0cHAHR.jpg",
        "https://image.tmdb.org/t/p/w500/cjEcqdRdFRRCGSBQ5E8BKJC3QDY.jpg",
        "https://image.tmdb.org/t/p/w500/9Gtg2DzBhmYamXBS1hKAhiwbBKS.jpg",
        "https://image.tmdb.org/t/p/w500/mGVrXeIjyecj6TKmwPVpHkCVmvP.jpg",
        "https://image.tmdb.org/t/p/w500/or06FN3Dka5tukK1e9sl16pB3iy.jpg",
    ],
}

def get_poster_url(movie_id, genre, title):
    """Return a deterministic poster URL based on movie_id and genre."""
    try:
        num = int(''.join(filter(str.isdigit, str(movie_id)))) if movie_id else 0
    except Exception:
        num = hash(str(movie_id)) % 999
    pool = GENRE_POSTERS.get(genre, GENRE_POSTERS["default"])
    return pool[num % len(pool)]


# Genre → wide backdrop images (w1280) for movie detail hero background
GENRE_BACKDROPS = {
    "Action": [
        "https://image.tmdb.org/t/p/w1280/8r5KSqrFJzjWaLIvbh3MHPZ5jqK.jpg",  # Mad Max: Fury Road
        "https://image.tmdb.org/t/p/w1280/fCayJrkfRaCRCTh8GqN30f8oyQF.jpg",  # John Wick
        "https://image.tmdb.org/t/p/w1280/hkBaDkMWbLaf8B1lsWsKX7Ew3Xq.jpg",  # Top Gun Maverick
        "https://image.tmdb.org/t/p/w1280/nMKdUUepR0i5zn0y1T4CejMQBtK.jpg",  # The Dark Knight
        "https://image.tmdb.org/t/p/w1280/qqHQsStV6exghCM7zbObuYBiYxw.jpg",  # Avengers Endgame
    ],
    "Drama": [
        "https://image.tmdb.org/t/p/w1280/kXfqcdQKsToO0OUXHcrrNCHDBzO.jpg",  # The Godfather
        "https://image.tmdb.org/t/p/w1280/xBKGJQh5MoHoTVvFBmDpPHBp5DH.jpg",  # Shawshank Redemption
        "https://image.tmdb.org/t/p/w1280/n6bUvigpRFqSwmPp1m2YADdbRBc.jpg",  # Joker
        "https://image.tmdb.org/t/p/w1280/loRmRzQAdNEV2JrP3AMTW1GKQAS.jpg",  # Parasite
    ],
    "Comedy": [
        "https://image.tmdb.org/t/p/w1280/eWkSeIXgIbHDpRFYeqAcuKmmXTI.jpg",  # Grand Budapest Hotel
        "https://image.tmdb.org/t/p/w1280/4nCJCfGIHWoFoFN5H2quVbssDVh.jpg",  # Knives Out
        "https://image.tmdb.org/t/p/w1280/7RyHsO4yDXtBv1zUU3mTpHeQ0d5.jpg",  # Home Alone
    ],
    "Thriller": [
        "https://image.tmdb.org/t/p/w1280/aCODl3mBGjZsSjSSpEwMGupPdKb.jpg",  # Inception
        "https://image.tmdb.org/t/p/w1280/56v2KjBlU4XaOv9rVYEQypROD7P.jpg",  # Gone Girl
        "https://image.tmdb.org/t/p/w1280/cjUBqDpGrUELqL7NdKIZEWTOiXb.jpg",  # Se7en
    ],
    "Romance": [
        "https://image.tmdb.org/t/p/w1280/oOv2oUXcAaNXakRqUPxYq5lJPqZ.jpg",  # La La Land
        "https://image.tmdb.org/t/p/w1280/wrFpXMNBRj2PBiN4Z5kix51XaIZ.jpg",  # Titanic
        "https://image.tmdb.org/t/p/w1280/jFEvuomOy6vHgBzXJEcbgMMrgpA.jpg",  # Eternal Sunshine
    ],
    "Sci-Fi": [
        "https://image.tmdb.org/t/p/w1280/xOMo8BRK7PfcJv9JCnx7s5hj0PX.jpg",  # Dune
        "https://image.tmdb.org/t/p/w1280/xu9zaAevzQ5nnrsXN6JcahLnG4i.jpg",  # Interstellar
        "https://image.tmdb.org/t/p/w1280/eIi3klFf7mp3oL5EEF4mLIDs26r.jpg",  # Blade Runner 2049
        "https://image.tmdb.org/t/p/w1280/fNG7i7RqMErkcqhohV2a6cV1Ehy.jpg",  # The Matrix
        "https://image.tmdb.org/t/p/w1280/rjkmN1dniUHVYAtwuV3Tji7FsDO.jpg",  # Arrival
    ],
    "Horror": [
        "https://image.tmdb.org/t/p/w1280/2Sg1s3cNbZAMCDSN3Gaz0AZVhqR.jpg",  # The Shining
        "https://image.tmdb.org/t/p/w1280/pdFDpFb8GqDmzJMQAorhPJrNEiA.jpg",  # Get Out
        "https://image.tmdb.org/t/p/w1280/wkPPRIducGfsbaZjKZDHGMDM0N5.jpg",  # Hereditary
    ],
    "Animation": [
        "https://image.tmdb.org/t/p/w1280/Ab8mkyvkiq3zTEhkA7TDObCHJbk.jpg",  # Spirited Away
        "https://image.tmdb.org/t/p/w1280/rXtbAFDHH27MHCRPz1zGfMB3XA.jpg",   # Up
        "https://image.tmdb.org/t/p/w1280/9bHim4CaJAHdBMYYSE7rm0EbzMu.jpg",  # Spider-Verse
    ],
    "default": [
        "https://image.tmdb.org/t/p/w1280/39wmItIWsg5sZMyRUHLkWBcuVCM.jpg",
        "https://image.tmdb.org/t/p/w1280/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg",
        "https://image.tmdb.org/t/p/w1280/xOMo8BRK7PfcJv9JCnx7s5hj0PX.jpg",
        "https://image.tmdb.org/t/p/w1280/aCODl3mBGjZsSjSSpEwMGupPdKb.jpg",
    ],
}

def get_backdrop_url(movie_id, genre, title):
    """Return a deterministic wide backdrop URL for the movie detail hero."""
    try:
        num = int(''.join(filter(str.isdigit, str(movie_id)))) if movie_id else 0
    except Exception:
        num = hash(str(movie_id)) % 999
    pool = GENRE_BACKDROPS.get(genre, GENRE_BACKDROPS["default"])
    return pool[num % len(pool)]



# Hard cap: only these 315 movie_ids (with theatre+screen+show+location) are ever shown
# Built once at module level so every request is fast.
# The subquery picks the best 315 distinct movies that have a full chain:
#   movie → show (available_seats>0) → screen → theater (city+location) → booking
_MOVIE_CAP = 315

def _get_movies(page=1, genre=None, language=None, city=None, search=None):
    offset = (page - 1) * PER_PAGE

    filters = []
    params = {"limit": PER_PAGE, "offset": offset, "cap": _MOVIE_CAP}

    # CTE: select the capped pool of valid movie_ids first (with all joins satisfied)
    # then paginate over that pool with optional filters.
    # NOTE: bookings join intentionally removed — movies without bookings yet should still appear.
    cte = """
        WITH capped AS (
            SELECT DISTINCT m.movie_id
            FROM movies m
            INNER JOIN shows s  ON s.movie_id   = m.movie_id AND s.available_seats > 0
            INNER JOIN screens sc ON sc.screen_id = s.screen_id
            INNER JOIN theaters t ON t.theater_id = s.theater_id
                                 AND t.city IS NOT NULL AND t.location IS NOT NULL
            ORDER BY m.movie_id
            LIMIT :cap
        )
    """

    base_q = cte + """
        SELECT DISTINCT ON (m.movie_id)
               m.movie_id, m.title, m.genre, m.language, m.duration,
               m.rating, m.release_date, m.description,
               t.city as show_city, t.name as theatre_name, t.location as theatre_location,
               s.start_time as show_time, s.available_seats, s.price_per_ticket,
               cs.image_url as carousel_image_url, cs.image_data as carousel_image_data
        FROM movies m
        INNER JOIN capped c ON c.movie_id = m.movie_id
        INNER JOIN shows s  ON s.movie_id   = m.movie_id AND s.available_seats > 0
        INNER JOIN screens sc ON sc.screen_id = s.screen_id
        INNER JOIN theaters t ON t.theater_id = s.theater_id
                             AND t.city IS NOT NULL AND t.location IS NOT NULL
        LEFT JOIN carousel_slides cs ON cs.movie_id = m.movie_id
        WHERE 1=1
    """

    count_q = cte + """
        SELECT COUNT(DISTINCT m.movie_id)
        FROM movies m
        INNER JOIN capped c ON c.movie_id = m.movie_id
        INNER JOIN shows s  ON s.movie_id   = m.movie_id AND s.available_seats > 0
        INNER JOIN screens sc ON sc.screen_id = s.screen_id
        INNER JOIN theaters t ON t.theater_id = s.theater_id
                             AND t.city IS NOT NULL AND t.location IS NOT NULL
        WHERE 1=1
    """

    if genre:
        filters.append("AND m.genre ILIKE :genre")
        params["genre"] = f"%{genre}%"
    if language:
        filters.append("AND m.language ILIKE :language")
        params["language"] = f"%{language}%"
    if city:
        filters.append("AND t.city ILIKE :city")
        params["city"] = f"%{city}%"
    if search:
        filters.append("AND m.title ILIKE :search")
        params["search"] = f"%{search}%"

    where_clause = " ".join(filters)
    total_row = db.session.execute(text(count_q + where_clause), params).scalar() or 0
    rows = db.session.execute(
        text(base_q + where_clause + " ORDER BY m.movie_id, m.title LIMIT :limit OFFSET :offset"),
        params
    ).fetchall()

    return rows, total_row


@public_bp.route("/")
def home():
    genre = request.args.get("genre", "")
    language = request.args.get("language", "")
    city = request.args.get("city", "")
    search = request.args.get("search", "")

    # Load only first page on server-side; rest loaded via infinite scroll JS
    movies, total = _get_movies(1, genre or None, language or None, city or None, search or None)
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

    # Attach poster URLs — prefer carousel-uploaded image over generic genre poster
    movies_with_posters = []
    for m in movies:
        # carousel_image_data is a base64 data-URI; carousel_image_url is an external link
        poster = (
            getattr(m, 'carousel_image_data', None)
            or getattr(m, 'carousel_image_url', None)
            or get_poster_url(m.movie_id, m.genre, m.title)
        )
        movies_with_posters.append((m, poster))

    # Filter options — only from the capped 315-movie pool
    # NOTE: bookings join removed so cities/genres/languages with shows but no bookings yet are included
    _capped_q = """
        WITH capped AS (
            SELECT DISTINCT m2.movie_id
            FROM movies m2
            INNER JOIN shows s2  ON s2.movie_id   = m2.movie_id AND s2.available_seats > 0
            INNER JOIN screens sc2 ON sc2.screen_id = s2.screen_id
            INNER JOIN theaters t2 ON t2.theater_id = s2.theater_id
                                   AND t2.city IS NOT NULL AND t2.location IS NOT NULL
            ORDER BY m2.movie_id
            LIMIT :cap
        )
        SELECT DISTINCT {col}
        FROM movies m
        INNER JOIN capped cc ON cc.movie_id = m.movie_id
        INNER JOIN shows s  ON s.movie_id   = m.movie_id AND s.available_seats > 0
        INNER JOIN screens sc ON sc.screen_id = s.screen_id
        INNER JOIN theaters t ON t.theater_id = s.theater_id
                             AND t.city IS NOT NULL AND t.location IS NOT NULL
        WHERE {col} IS NOT NULL
        ORDER BY {col}
    """
    cap_params = {"cap": _MOVIE_CAP}
    genres    = [r[0] for r in db.session.execute(text(_capped_q.format(col="m.genre")),    cap_params).fetchall()]
    languages = [r[0] for r in db.session.execute(text(_capped_q.format(col="m.language")), cap_params).fetchall()]
    cities    = [r[0] for r in db.session.execute(text(_capped_q.format(col="t.city")),     cap_params).fetchall()]

    # Carousel
    try:
        carousel_slides = db.session.execute(text("""
            SELECT cs.id, cs.movie_id, cs.badge_label, cs.image_url, cs.image_data,
                   cs.trailer_url,
                   m.title, m.genre, m.language, m.duration, m.rating, m.description
            FROM carousel_slides cs
            JOIN movies m ON m.movie_id = cs.movie_id
            WHERE cs.is_active = TRUE
            ORDER BY cs.display_order ASC, cs.id ASC
            LIMIT 10
        """)).fetchall()
    except Exception:
        carousel_slides = []

    if not carousel_slides:
        try:
            carousel_slides = db.session.execute(text("""
                SELECT NULL::integer AS id, m.movie_id,
                       'NOW SHOWING'::varchar AS badge_label,
                       NULL::text AS image_url, NULL::text AS image_data,
                       NULL::text AS trailer_url,
                       m.title, m.genre, m.language, m.duration, m.rating, m.description
                FROM movies m
                INNER JOIN shows s ON s.movie_id = m.movie_id AND s.available_seats > 0
                INNER JOIN screens sc ON sc.screen_id = s.screen_id
                INNER JOIN theaters t ON t.theater_id = s.theater_id AND t.city IS NOT NULL
                INNER JOIN bookings b ON b.show_id = s.show_id
                GROUP BY m.movie_id, m.title, m.genre, m.language, m.duration, m.rating, m.description
                ORDER BY RANDOM() LIMIT 10
            """)).fetchall()
        except Exception:
            carousel_slides = []

    # ── Upcoming Movies section ──────────────────────────────────────
    try:
        # Ensure table exists (safe no-op if already there)
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS upcoming_movies (
                id SERIAL PRIMARY KEY,
                movie_id VARCHAR(20) NOT NULL,
                poster_url TEXT,
                poster_data TEXT,
                release_label VARCHAR(80) DEFAULT 'Coming Soon',
                display_order INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        db.session.commit()
        upcoming_movies = db.session.execute(text("""
            SELECT u.id, u.movie_id, u.poster_url, u.poster_data, u.release_label,
                   m.title, m.genre, m.language, m.duration, m.rating, m.description
            FROM upcoming_movies u
            JOIN movies m ON m.movie_id = u.movie_id
            WHERE u.is_active = TRUE
            ORDER BY u.display_order ASC, u.id ASC
        """)).fetchall()
    except Exception:
        upcoming_movies = []

    # auto_scroll: when genre/language/city is active, JS scrolls past carousel to movies grid
    auto_scroll = bool(genre or language or city)

    return render_template("public/home.html",
        movies=movies_with_posters, total=total, page=1, total_pages=total_pages,
        genres=genres, languages=languages, cities=cities,
        selected_genre=genre, selected_language=language,
        selected_city=city, search=search,
        carousel_movies=carousel_slides,
        upcoming_movies=upcoming_movies,
        auto_scroll=auto_scroll
    )


@public_bp.route("/movie/<movie_id>")
def movie_detail(movie_id):
    movie = db.session.execute(
        text("SELECT * FROM movies WHERE movie_id = :mid"), {"mid": movie_id}
    ).fetchone()

    if not movie:
        return render_template("public/404.html"), 404

    shows = db.session.execute(text("""
        SELECT s.show_id, s.show_date, s.start_time, s.price_per_ticket, s.available_seats,
               t.name as theatre_name, t.city, t.location, sc.screen_number
        FROM shows s
        JOIN theaters t ON t.theater_id = s.theater_id
        JOIN screens sc ON sc.screen_id = s.screen_id
        WHERE s.movie_id = :mid
        ORDER BY s.show_date, s.start_time
    """), {"mid": movie_id}).fetchall()

    reviews = db.session.execute(text("""
        SELECT r.rating, r.review_text, r.review_date, u.name as user_name
        FROM reviews r
        JOIN dataset_users u ON u.user_id = r.user_id
        WHERE r.movie_id = :mid
        ORDER BY r.review_date DESC
        LIMIT 10
    """), {"mid": movie_id}).fetchall()

    carousel_img = db.session.execute(text("""
        SELECT image_url, image_data FROM carousel_slides WHERE movie_id = :mid LIMIT 1
    """), {"mid": movie_id}).fetchone()
    movie_image_url = None
    movie_image_data = None
    if carousel_img:
        movie_image_url = carousel_img.image_url
        movie_image_data = carousel_img.image_data

    # Fallback to genre-based poster (portrait, w500)
    if not movie_image_url and not movie_image_data:
        movie_image_url = get_poster_url(movie.movie_id, movie.genre, movie.title)

    # Wide backdrop for the hero background — always use a w1280 landscape image
    movie_backdrop_url = get_backdrop_url(movie.movie_id, movie.genre, movie.title)

    return render_template("public/movie_detail.html", movie=movie, shows=shows, reviews=reviews,
                           movie_image_url=movie_image_url, movie_image_data=movie_image_data,
                           movie_backdrop_url=movie_backdrop_url)


@public_bp.route("/contact")
def contact():
    return render_template("public/contact.html")


@public_bp.route("/contact/submit", methods=["POST"])
def contact_submit():
    from models.models import ContactMessage
    from flask import session as _sess
    data = request.get_json() if request.is_json else request.form

    name     = (data.get("name") or "").strip()
    email    = (data.get("email") or "").strip()
    category = (data.get("category") or "General").strip()
    subject  = (data.get("subject") or "").strip()
    message  = (data.get("message") or "").strip()
    rating   = data.get("rating")

    if not name or not email or not message:
        if request.is_json:
            return jsonify({"success": False, "message": "Name, email and message are required."}), 400
        flash("Please fill in all required fields.", "danger")
        return redirect(url_for("public.contact"))

    try:
        rating_int = int(rating) if rating else None
    except (ValueError, TypeError):
        rating_int = None

    msg = ContactMessage(
        user_id  = _sess.get("user_id"),
        name     = name,
        email    = email,
        category = category,
        subject  = subject or f"{category} enquiry",
        message  = message,
        rating   = rating_int,
        status   = "unread",
    )
    db.session.add(msg)
    db.session.commit()

    if request.is_json:
        return jsonify({"success": True, "message": "Your message has been sent!"})
    flash("Your message has been sent! We'll get back to you soon.", "success")
    return redirect(url_for("public.contact"))


@public_bp.route("/api/movies")
def api_movies():
    """Infinite scroll API — returns movies with theatre, screen, show timings, location and bookings."""
    page = request.args.get("page", 1, type=int)
    genre = request.args.get("genre") or None
    language = request.args.get("language") or None
    city = request.args.get("city") or None
    search = request.args.get("search") or None

    movies, total = _get_movies(page, genre, language, city, search)
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

    data = []
    for m in movies:
        data.append({
            "movie_id": m.movie_id,
            "title": m.title,
            "genre": m.genre,
            "language": m.language,
            "duration": m.duration,
            "rating": float(m.rating) if m.rating else None,
            "release_date": str(m.release_date) if m.release_date else None,
            "description": m.description,
            "city": m.show_city,
            "theatre_name": m.theatre_name,
            "theatre_location": m.theatre_location,
            "show_time": str(m.show_time) if m.show_time else None,
            "available_seats": m.available_seats,
            "price_per_ticket": float(m.price_per_ticket) if m.price_per_ticket else None,
            "poster_url": (
                getattr(m, 'carousel_image_data', None)
                or getattr(m, 'carousel_image_url', None)
                or get_poster_url(m.movie_id, m.genre, m.title)
            ),
        })

    return jsonify({
        "movies": data,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "has_more": page < total_pages,
    })
