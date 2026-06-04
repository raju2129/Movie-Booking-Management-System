from flask import Flask, render_template
from database.db import db
from flask_migrate import Migrate
from config import config_map
import os
import threading
import time as _time
from dotenv import load_dotenv

# Load .env file so MAIL_USERNAME / MAIL_PASSWORD etc. are available via os.environ
load_dotenv()

migrate = Migrate()


def _start_seat_auto_unlock_worker(app):
    """
    Background thread: runs every 60 seconds.
    Automatically releases booked seats whose show ended > 3 hours ago.
    This mirrors real-world behaviour: after a movie finishes, seats
    are freed for the next booking cycle.
    """
    def worker():
        _time.sleep(30)  # initial grace delay on startup
        while True:
            try:
                with app.app_context():
                    from sqlalchemy import text as _text
                    # Find booked_seats whose show ended more than 3 hours ago.
                    # show end ≈ show.show_date + show.start_time + 3 hours
                    db.session.execute(_text("""
                        DELETE FROM booked_seats
                        WHERE show_id IN (
                            SELECT s.show_id FROM shows s
                            WHERE (s.show_date + s.start_time + INTERVAL '3 hours') <= NOW()
                        )
                    """))
                    # Also clear confirmed/locked seat_locks for ended shows
                    db.session.execute(_text("""
                        UPDATE seat_locks SET status = 'released'
                        WHERE status IN ('confirmed','locked')
                          AND show_id IN (
                              SELECT s.show_id FROM shows s
                              WHERE (s.show_date + s.start_time + INTERVAL '3 hours') <= NOW()
                          )
                    """))
                    db.session.commit()
            except Exception as _e:
                try:
                    db.session.rollback()
                except Exception:
                    pass
            _time.sleep(60)  # check every 60 seconds

    t = threading.Thread(target=worker, daemon=True, name="seat-auto-unlock")
    t.start()
    print("✅ Seat auto-unlock background worker started (3-hour show window).")


def create_app(env=None):
    app = Flask(__name__)
    env = env or os.environ.get("FLASK_ENV", "development")
    app.config.from_object(config_map[env])

    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        # Import ALL models so SQLAlchemy knows every table before create_all()
        from models.models import (
            Role, AppUser, TheatreOwnership, UserBooking, OtpToken,
            Movie, Theater, Screen, Show, DatasetUser, Review, CarouselSlide,
            ContactMessage, SeatLock, BookedSeat
        )

        # Register blueprints
        from routes.auth          import auth_bp
        from routes.public        import public_bp
        from routes.admin         import admin_bp
        from routes.theatre_owner import theatre_owner_bp
        from routes.user          import user_bp
        from routes.seats         import seats_bp

        app.register_blueprint(auth_bp)
        app.register_blueprint(public_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(theatre_owner_bp)
        app.register_blueprint(user_bp)
        app.register_blueprint(seats_bp)

        # Create ORM-managed tables (roles, app_users, user_bookings, etc.)
        # carousel_slides has NO FK to movies so it is safe to create via ORM.
        db.create_all()

        # Ensure carousel_slides exists even if DB was set up before this version
        _ensure_carousel_table()

        # Migrate contact_messages: add all new columns that may be missing in old DBs
        _migrate_contact_messages()

        _seed_initial_data()

    # Start background worker that auto-releases seats 3 hours after show end
    _start_seat_auto_unlock_worker(app)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("public/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("public/500.html"), 500

    @app.context_processor
    def inject_nav_cities():
        """Inject cities list and selected city into every template for navbar."""
        from flask import request as _req, session as _sess
        try:
            from sqlalchemy import text as _text
            # Pull cities directly from the dataset theaters table
            nav_cities = [r[0] for r in db.session.execute(_text(
                "SELECT DISTINCT city FROM theaters WHERE city IS NOT NULL ORDER BY city"
            )).fetchall()]
        except Exception:
            nav_cities = []

        # Priority: query param > session > default empty
        nav_selected_city = (
            _req.args.get("city", "")
            or _sess.get("selected_city", "")
        )
        # Persist city choice in session
        if _req.args.get("city"):
            _sess["selected_city"] = _req.args.get("city")

        return dict(nav_cities=nav_cities, nav_selected_city=nav_selected_city)

    return app


def _migrate_contact_messages():
    """
    Safely add ALL columns that were introduced in newer versions of the model
    but may not exist in databases created from older versions.
    Each ALTER is wrapped individually so one failure never blocks the rest.
    """
    new_columns = [
        ("user_id",     "INTEGER"),          # FK enforced at app level
        ("category",    "VARCHAR(50) DEFAULT 'General'"),
        ("subject",     "VARCHAR(200)"),
        ("rating",      "INTEGER"),
        ("status",      "VARCHAR(20) DEFAULT 'unread'"),
        ("admin_reply", "TEXT"),
        ("replied_at",  "TIMESTAMP"),
    ]
    for col_name, col_def in new_columns:
        try:
            db.session.execute(db.text(
                f"ALTER TABLE contact_messages ADD COLUMN IF NOT EXISTS {col_name} {col_def}"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
    print("✅ contact_messages columns migration done.")


def _ensure_carousel_table():
    """Safely create carousel_slides table using raw SQL if it doesn't exist yet.
    This avoids any SQLAlchemy FK resolution issue with the raw-SQL-managed movies table."""
    try:
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS carousel_slides (
                id            SERIAL PRIMARY KEY,
                movie_id      VARCHAR(20) NOT NULL,
                badge_label   VARCHAR(80) DEFAULT 'NOW SHOWING',
                image_url     TEXT,
                image_data    TEXT,
                display_order INTEGER DEFAULT 0,
                is_active     BOOLEAN DEFAULT TRUE,
                created_at    TIMESTAMP DEFAULT NOW()
            )
        """))
        db.session.commit()
        # Add trailer_url column if it doesn't exist (migration for existing DBs)
        try:
            db.session.execute(db.text("""
                ALTER TABLE carousel_slides ADD COLUMN IF NOT EXISTS trailer_url TEXT
            """))
            db.session.commit()
        except Exception:
            db.session.rollback()
        print("✅ carousel_slides table ready.")
    except Exception as e:
        db.session.rollback()
        print(f"⚠️  carousel_slides table check: {e}")


def _seed_initial_data():
    from models.models import Role, AppUser
    for rname in ["admin", "theatre_owner", "user"]:
        if not Role.query.filter_by(name=rname).first():
            db.session.add(Role(name=rname))
    db.session.commit()

    admin_role = Role.query.filter_by(name="admin").first()
    if not AppUser.query.filter_by(email="admin@bookmyshow.com").first():
        admin = AppUser(
            name="Super Admin",
            email="admin@bookmyshow.com",
            role_id=admin_role.id,
            phone="9999999999",
            city="Mumbai",
            is_active=True,
        )
        admin.set_password("Admin@123")
        db.session.add(admin)
        db.session.commit()
        print("✅ Default admin created: admin@bookmyshow.com / Admin@123")


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
