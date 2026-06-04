from database.db import db
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash


# ──────────────── ROLES ────────────────
class Role(db.Model):
    __tablename__ = "roles"
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    users      = db.relationship("AppUser", back_populates="role", lazy="dynamic")


# ──────────────── APP USERS ────────────────
class AppUser(db.Model):
    __tablename__ = "app_users"
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role_id       = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    is_active     = db.Column(db.Boolean, default=True)
    phone         = db.Column(db.String(20))
    city          = db.Column(db.String(100))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    role           = db.relationship("Role", back_populates="users")
    owned_theatres = db.relationship("TheatreOwnership", back_populates="owner", lazy="dynamic")
    bookings       = db.relationship("UserBooking", back_populates="user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def role_name(self):
        return self.role.name if self.role else None


# ──────────────── THEATRE OWNERSHIP ────────────────
class TheatreOwnership(db.Model):
    __tablename__ = "theatre_ownership"
    id             = db.Column(db.Integer, primary_key=True)
    owner_id       = db.Column(db.Integer, db.ForeignKey("app_users.id"))
    theatre_db_id  = db.Column(db.String(20))
    assigned_at    = db.Column(db.DateTime, default=datetime.utcnow)
    owner          = db.relationship("AppUser", back_populates="owned_theatres")


# ──────────────── USER BOOKINGS ────────────────
class UserBooking(db.Model):
    __tablename__ = "user_bookings"
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("app_users.id"))
    show_id        = db.Column(db.String(20))
    movie_title    = db.Column(db.String(200))
    theatre_name   = db.Column(db.String(200))
    theatre_city   = db.Column(db.String(100))
    show_date      = db.Column(db.Date)
    show_time      = db.Column(db.String(20))
    num_tickets    = db.Column(db.Integer)
    total_amount   = db.Column(db.Float)
    payment_method = db.Column(db.String(50), default="Online")
    status         = db.Column(db.String(30), default="Confirmed")
    booking_ref    = db.Column(db.String(20), unique=True)
    booked_at      = db.Column(db.DateTime, default=datetime.utcnow)
    seat_numbers   = db.Column(db.String(200))
    user           = db.relationship("AppUser", back_populates="bookings")


# ──────────────── OTP TOKENS (forgot password) ────────────────
class OtpToken(db.Model):
    __tablename__ = "otp_tokens"
    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(150), nullable=False)
    otp        = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used       = db.Column(db.Boolean, default=False)


# ══════════════════════════════════════════════════════════════
#  DATASET TABLES  –  fully managed by SQLAlchemy ORM
#  (previously created via raw SQL in app.py)
# ══════════════════════════════════════════════════════════════

class Movie(db.Model):
    __tablename__ = "movies"
    movie_id     = db.Column(db.String(20), primary_key=True)
    title        = db.Column(db.String(200), nullable=False)
    genre        = db.Column(db.String(100))
    language     = db.Column(db.String(50))
    duration     = db.Column(db.Integer)
    rating       = db.Column(db.Numeric(3, 1))
    release_date = db.Column(db.Date)
    description  = db.Column(db.Text)

    shows   = db.relationship("Show",   back_populates="movie",  lazy="dynamic", cascade="all, delete-orphan")
    reviews = db.relationship("Review", back_populates="movie",  lazy="dynamic", cascade="all, delete-orphan")


class Theater(db.Model):
    __tablename__ = "theaters"
    theater_id = db.Column(db.String(20), primary_key=True)
    name       = db.Column(db.String(200), nullable=False)
    city       = db.Column(db.String(100))
    state      = db.Column(db.String(100))
    location   = db.Column(db.Text)

    screens = db.relationship("Screen", back_populates="theater", lazy="dynamic", cascade="all, delete-orphan")
    shows   = db.relationship("Show",   back_populates="theater", lazy="dynamic", cascade="all, delete-orphan")


class Screen(db.Model):
    __tablename__ = "screens"
    screen_id     = db.Column(db.String(20), primary_key=True)
    theater_id    = db.Column(db.String(20), db.ForeignKey("theaters.theater_id", ondelete="CASCADE"))
    screen_number = db.Column(db.Integer)
    total_seats   = db.Column(db.Integer)

    theater = db.relationship("Theater", back_populates="screens")
    shows   = db.relationship("Show",    back_populates="screen",  lazy="dynamic", cascade="all, delete-orphan")


class Show(db.Model):
    __tablename__ = "shows"
    show_id          = db.Column(db.String(20), primary_key=True)
    movie_id         = db.Column(db.String(20), db.ForeignKey("movies.movie_id",   ondelete="CASCADE"))
    theater_id       = db.Column(db.String(20), db.ForeignKey("theaters.theater_id", ondelete="CASCADE"))
    screen_id        = db.Column(db.String(20), db.ForeignKey("screens.screen_id", ondelete="CASCADE"))
    show_date        = db.Column(db.Date)
    start_time       = db.Column(db.String(20))
    price_per_ticket = db.Column(db.Numeric(10, 2))
    available_seats  = db.Column(db.Integer)

    movie   = db.relationship("Movie",   back_populates="shows")
    theater = db.relationship("Theater", back_populates="shows")
    screen  = db.relationship("Screen",  back_populates="shows")


class DatasetUser(db.Model):
    """Dataset users – separate from app_users (the portal auth users)."""
    __tablename__ = "dataset_users"
    user_id    = db.Column(db.String(20), primary_key=True)
    name       = db.Column(db.String(200))
    email      = db.Column(db.String(150))
    city       = db.Column(db.String(100))
    phone      = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviews = db.relationship("Review", back_populates="dataset_user", lazy="dynamic", cascade="all, delete-orphan")


class Review(db.Model):
    __tablename__ = "reviews"
    review_id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    movie_id    = db.Column(db.String(20), db.ForeignKey("movies.movie_id",        ondelete="CASCADE"))
    user_id     = db.Column(db.String(20), db.ForeignKey("dataset_users.user_id",  ondelete="CASCADE"))
    rating      = db.Column(db.Numeric(3, 1))
    review_text = db.Column(db.Text)
    review_date = db.Column(db.Date, default=date.today)

    movie       = db.relationship("Movie",       back_populates="reviews")
    dataset_user = db.relationship("DatasetUser", back_populates="reviews")


# ──────────────── CONTACT MESSAGES ────────────────
class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("app_users.id"), nullable=True)
    name         = db.Column(db.String(100), nullable=False)
    email        = db.Column(db.String(150), nullable=False)
    category     = db.Column(db.String(50), default="General")
    subject      = db.Column(db.String(200))
    message      = db.Column(db.Text, nullable=False)
    rating       = db.Column(db.Integer)          # 1-5 star rating
    status       = db.Column(db.String(20), default="unread")  # unread / read / replied
    admin_reply  = db.Column(db.Text)
    replied_at   = db.Column(db.DateTime)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("AppUser", backref=db.backref("contact_messages", lazy="dynamic"), foreign_keys=[user_id])


# ──────────────── CAROUSEL SLIDES ────────────────
# NOTE: movie_id is intentionally stored as plain VARCHAR (no FK constraint)
# because the 'movies' table is populated via raw SQL / Excel import and
# PostgreSQL requires an explicit PRIMARY KEY or UNIQUE index on the referenced
# column before a FOREIGN KEY can be added.  We enforce the relationship at the
# application layer instead (JOIN in raw SQL queries inside the routes).
class CarouselSlide(db.Model):
    __tablename__ = "carousel_slides"
    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    movie_id      = db.Column(db.String(20), nullable=False)   # no FK – see note above
    badge_label   = db.Column(db.String(80), default="NOW SHOWING")
    image_url     = db.Column(db.Text)          # external URL
    image_data    = db.Column(db.Text)          # base64 data-URI for uploaded images
    trailer_url   = db.Column(db.Text)          # YouTube trailer URL
    display_order = db.Column(db.Integer, default=0)
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)


# ──────────────── SEAT LOCKS (temporary holds during booking) ────────────────
class SeatLock(db.Model):
    """
    Temporarily locks a seat for a user while they are in the booking flow.
    Lock expires automatically after LOCK_MINUTES (default 10 min).
    On confirmed booking the seat is marked permanently booked in BookedSeat.
    """
    __tablename__ = "seat_locks"
    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    show_id    = db.Column(db.String(20), nullable=False, index=True)
    seat_id    = db.Column(db.String(10), nullable=False)   # e.g. "A01"
    user_id    = db.Column(db.Integer, db.ForeignKey("app_users.id"), nullable=False)
    session_id = db.Column(db.String(64), nullable=False)   # Flask session sid
    locked_at  = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    status     = db.Column(db.String(20), default="locked")  # locked | confirmed | released

    __table_args__ = (
        db.UniqueConstraint("show_id", "seat_id", name="uq_show_seat"),
    )


# ──────────────── BOOKED SEATS (permanent after payment) ────────────────
class BookedSeat(db.Model):
    """
    Permanently marks a seat as booked after successful payment.
    Survives booking cancellations only when the user explicitly cancels.
    """
    __tablename__ = "booked_seats"
    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    show_id    = db.Column(db.String(20), nullable=False, index=True)
    seat_id    = db.Column(db.String(10), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey("user_bookings.id"), nullable=False)
    booked_at  = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("show_id", "seat_id", name="uq_booked_show_seat"),
    )


# ──────────────── UPCOMING MOVIES (homepage section) ────────────────
class UpcomingMovie(db.Model):
    """
    Movies showcased in the 'Coming Soon' section of the homepage.
    Admin manages these from the Upcoming Movies manager (separate from carousel).
    """
    __tablename__ = "upcoming_movies"
    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    movie_id      = db.Column(db.String(20), nullable=False)   # references movies.movie_id
    poster_url    = db.Column(db.Text)          # external URL
    poster_data   = db.Column(db.Text)          # base64 data-URI for uploaded images
    release_label = db.Column(db.String(80), default="Coming Soon")  # e.g. "June 2025"
    display_order = db.Column(db.Integer, default=0)
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
