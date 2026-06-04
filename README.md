# 🎬 BookMyShow Clone – Movie Booking Management System (v13)

A full-stack web application inspired by BookMyShow, built with **Flask + PostgreSQL + Bootstrap 5**.

## ✅ What's New in v13
- **Screen Management** added to both **Admin** and **Theatre Owner** dashboards
- Proper flow enforced: Theatre → Screen → Show → Booking
- Shows page now shows a live warning + direct link if no screen exists for the selected theatre
- Smart screen number auto-suggestion when adding screens

## 🔄 Correct Application Flow

```
Admin creates Theatre
       ↓
Admin (or Theatre Owner) adds Screen(s) to the Theatre
       ↓
Admin (or Theatre Owner) schedules Shows on that Theatre
       ↓
Users browse & book tickets for Shows
```

### Admin Navigation:
- **Theatres** → Add/manage theatres
- **Screens** *(new)* → Add screens to theatres (e.g. Screen #1 – 150 seats)
- **Shows** → Schedule shows (auto-assigns first available screen)
- **Movies** → Manage movie catalogue

### Theatre Owner Navigation:
- **My Theatres** → View assigned theatres
- **My Screens** *(new)* → Add/manage screens for your theatres
- **My Shows** → Schedule shows across your theatres



A full-stack web application inspired by BookMyShow, built with **Flask + PostgreSQL + Bootstrap 5**.

## 🗂️ Folder Structure

```
movie_booking_app/
├── app.py                    # Flask factory, blueprint registration
├── config.py                 # Dev / Prod / Test configs
├── requirements.txt
├── load_excel.py             # Seeds DB from BookMyShow_Dataset.xlsx
├── .env.example
├── database/
│   └── db.py                 # SQLAlchemy instance
├── models/
│   └── models.py             # Role, AppUser, TheatreOwnership, UserBooking
├── routes/
│   ├── auth.py               # Login, signup, logout, decorators
│   ├── public.py             # Home, movie listing, movie detail
│   ├── admin.py              # Admin dashboard & management
│   ├── theatre_owner.py      # Theatre owner panel
│   └── user.py               # Booking, history, profile
├── templates/
│   ├── base.html             # Public navbar + footer
│   ├── auth/                 # login.html, signup.html
│   ├── public/               # home.html, movie_detail.html, 404/500
│   ├── admin/                # Admin panel (base + pages)
│   ├── theatre_owner/        # Owner panel (base + pages)
│   └── user/                 # User dashboard, bookings, confirmation
└── static/
    ├── css/
    │   ├── style.css         # Global styles
    │   └── admin.css         # Dashboard sidebar layout
    └── js/
        ├── main.js           # Shared sidebar toggle, toasts
        ├── auth.js           # Login / signup async forms
        ├── admin.js          # Admin panel interactions
        ├── booking.js        # Ticket counter, payment, cancellation
        └── public.js         # Home page filters & search
```

## 🚀 Quick Setup

### 1. Create & activate virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your DB credentials
```

### 4. Create PostgreSQL database
```sql
CREATE DATABASE movie_booking_db;
```

### 5. Run migrations
```bash
flask db init       # only first time
flask db migrate -m "initial"
flask db upgrade
```

### 6. Load dataset from Excel
```bash
python load_excel.py --file BookMyShow_Dataset.xlsx
```

### 7. Run the server
```bash
python app.py
```

Visit: **http://localhost:5000**

---

## 👥 Default Credentials

| Role   | Email                    | Password   |
|--------|--------------------------|------------|
| Admin  | admin@bookmyshow.com     | Admin@123  |

> Theatre owner accounts are created by the Admin from the dashboard.  
> Users self-register from the public site.

---

## 🎯 Features by Role

### 🌐 Public (No Login Required)
- Browse all movies with poster cards (BookMyShow-style)
- Filter by **City**, **Genre**, **Language**
- Search by movie title
- Paginated movie listing
- Movie detail page with showtimes grouped by theatre

### 🔴 Admin
- Dashboard with stats (movies, theatres, shows, users)
- Top movies & cities charts
- Manage Movies (list, search, paginate)
- Manage Theatres (list with screen counts)
- Manage Shows (list with full details)
- Manage Users (view all app users)
- **Create Theatre Owners** – modal form → generates credentials → displays email/password
- Assign theatres to theatre owners

### 🟣 Theatre Owner
- Dashboard with owned theatres, show count
- View allocated theatres and screens
- View all shows for their theatres
- Theatre detail with screens and show history

### 🔵 User (Customer)
- Register / Login with secure password
- Browse & search movies
- Book tickets: select show → choose seats count → select payment method → confirm
- Booking confirmation page with reference number
- My Bookings: Upcoming / Past / Cancelled tabs
- Cancel bookings
- Edit profile

---

## 🗄️ Database Models

| Table            | Description                              |
|------------------|------------------------------------------|
| `roles`          | admin, theatre_owner, user               |
| `app_users`      | Portal users with role & auth            |
| `theatre_ownership` | Links theatre owner → dataset theatre |
| `user_bookings`  | All ticket bookings made via portal      |
| `users`          | Dataset: BookMyShow users                |
| `movies`         | Dataset: movie catalog                   |
| `theaters`       | Dataset: theatre list                    |
| `screens`        | Dataset: screens per theatre             |
| `shows`          | Dataset: show schedule                   |
| `seats`          | Dataset: seat inventory                  |
| `bookings`       | Dataset: original bookings               |
| `payments`       | Dataset: payment records                 |
| `reviews`        | Dataset: movie reviews                   |

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10+, Flask 3.0, SQLAlchemy 2.0, Flask-Migrate
- **Database:** PostgreSQL 15+
- **Frontend:** Bootstrap 5.3, Font Awesome 6.5, Vanilla JS (async/await)
- **Data:** BookMyShow SQL Dataset (via Excel import)
