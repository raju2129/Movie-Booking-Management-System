from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash, make_response, current_app
from routes.auth import login_required, role_required
from models.models import AppUser, UserBooking, db
from sqlalchemy import text
import random, string, io, base64, os, smtplib
from datetime import date, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

try:
    import qrcode
    from PIL import Image
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

user_bp = Blueprint("user", __name__, url_prefix="/user")


def gen_booking_ref():
    return "BMS" + "".join(random.choices(string.digits, k=8))


def generate_upi_qr(amount, movie_title, booking_ref):
    """Generate a UPI QR code for the given amount and return as base64 PNG."""
    # Standard UPI deep-link format
    upi_id  = "9014139i40@ybl"
    payee   = "CineBook Cinemas"
    note    = f"Tickets: {movie_title[:30]}"
    upi_url = (
        f"upi://pay?pa={upi_id}&pn={payee}"
        f"&am={amount:.2f}&cu=INR"
        f"&tn={note}&tr={booking_ref}"
    )

    if not QR_AVAILABLE:
        return None, upi_url

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(upi_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}", upi_url


def generate_ticket_pdf(booking, user):
    """Generate a premium cinema-style PDF ticket using reportlab canvas for pixel-perfect layout."""
    try:
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader

        buf = io.BytesIO()
        W, H = A4  # 595 x 842 pt
        c = rl_canvas.Canvas(buf, pagesize=A4)

        # ── Colour palette ──
        BG      = colors.HexColor('#060d1a')
        CARD    = colors.HexColor('#0f1c2e')
        ACCENT  = colors.HexColor('#e5383b')
        GOLD    = colors.HexColor('#ffd60a')
        WHITE   = colors.white
        MUTED   = colors.HexColor('#6b85a8')
        GREEN   = colors.HexColor('#22c55e')
        BORDER  = colors.HexColor('#1a2d45')
        STRIP   = colors.HexColor('#141f30')
        DARK_RED= colors.HexColor('#1f0608')

        # ── Full page background ──
        c.setFillColor(BG)
        c.rect(0, 0, W, H, fill=1, stroke=0)

        # ── Subtle dot grid pattern ──
        c.setFillColor(colors.HexColor('#0c1525'))
        for gx in range(int(W / (6*mm)) + 1):
            for gy in range(int(H / (6*mm)) + 1):
                c.circle(gx * 6*mm, gy * 6*mm, 0.6, fill=1, stroke=0)

        # ── Outer card ──
        margin = 16*mm
        card_w = W - 2 * margin
        card_h = H - 2 * margin
        card_x = margin
        card_y = margin
        c.setFillColor(CARD)
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.6)
        c.roundRect(card_x, card_y, card_w, card_h, 10, fill=1, stroke=1)

        # ── Red header strip ──
        header_h = 58 * mm
        c.setFillColor(ACCENT)
        c.roundRect(card_x, card_y + card_h - header_h, card_w, header_h, 10, fill=1, stroke=0)
        c.setFillColor(ACCENT)
        c.rect(card_x, card_y + card_h - header_h, card_w, 10, fill=1, stroke=0)

        # Decorative diagonal stripes on header
        c.saveState()
        c.clipPath(
            c.beginPath(),
        )
        c.setFillColor(colors.HexColor('#cc2f32'))
        for si in range(0, int(card_w + 40*mm), 12):
            c.setLineWidth(0)
            pts = [(card_x + si, card_y + card_h),
                   (card_x + si + 8*mm, card_y + card_h),
                   (card_x + si + 8*mm - header_h, card_y + card_h - header_h),
                   (card_x + si - header_h, card_y + card_h - header_h)]
            p = c.beginPath()
            p.moveTo(*pts[0])
            for pt in pts[1:]:
                p.lineTo(*pt)
            p.close()
            c.drawPath(p, fill=1, stroke=0)
        c.restoreState()

        # ── CINEBOOK brand ──
        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 28)
        c.drawCentredString(W / 2, card_y + card_h - 18*mm, 'CINEBOOK')

        c.setFont('Helvetica', 8)
        c.setFillColor(colors.HexColor('#ffcccc'))
        c.drawCentredString(W / 2, card_y + card_h - 26*mm, 'YOUR OFFICIAL E-TICKET')

        # Horizontal rule under brand
        c.setStrokeColor(colors.HexColor('#ff6e71'))
        c.setLineWidth(0.5)
        c.line(W/2 - 25*mm, card_y + card_h - 28.5*mm, W/2 + 25*mm, card_y + card_h - 28.5*mm)

        # ── Confirmed badge ──
        badge_w = 52*mm
        badge_h = 9*mm
        badge_x = W/2 - badge_w/2
        badge_y = card_y + card_h - 44*mm
        c.setFillColor(colors.HexColor('#0d2b0d'))
        c.roundRect(badge_x, badge_y, badge_w, badge_h, 4, fill=1, stroke=0)
        c.setStrokeColor(colors.HexColor('#1a5c1a'))
        c.setLineWidth(0.5)
        c.roundRect(badge_x, badge_y, badge_w, badge_h, 4, fill=0, stroke=1)
        c.setFillColor(GREEN)
        c.setFont('Helvetica-Bold', 8.5)
        c.drawCentredString(W/2, badge_y + 2.5*mm, 'BOOKING CONFIRMED')

        # ── Movie Title ──
        title_top = card_y + card_h - header_h - 14*mm
        title = str(booking.movie_title or '—')
        c.setFillColor(WHITE)
        # Auto-shrink font if title is very long
        font_size = 20
        while c.stringWidth(title, 'Helvetica-Bold', font_size) > card_w - 18*mm and font_size > 12:
            font_size -= 1
        c.setFont('Helvetica-Bold', font_size)
        c.drawCentredString(W/2, title_top, title)

        c.setFillColor(MUTED)
        c.setFont('Helvetica', 9)
        theatre_line = f"{booking.theatre_name or '—'}    |    {booking.theatre_city or '—'}"
        c.drawCentredString(W/2, title_top - 8*mm, theatre_line)

        # ── Tear-line perforation ──
        tear_y = card_y + card_h - header_h - 28*mm
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.5)
        c.setDash([3, 5])
        c.line(card_x + 7*mm, tear_y, card_x + card_w - 7*mm, tear_y)
        c.setDash([])
        # Semicircle notches
        for nx in [card_x, card_x + card_w]:
            c.setFillColor(BG)
            c.setStrokeColor(BG)
            c.circle(nx, tear_y, 4*mm, fill=1, stroke=1)

        # Scissors icon hint
        c.setFillColor(MUTED)
        c.setFont('Helvetica', 6.5)
        c.drawCentredString(W/2, tear_y + 2*mm, 'TEAR HERE')

        # ── Booking Reference block ──
        ref_blk_y = tear_y - 20*mm
        ref_blk_h = 14*mm
        c.setFillColor(STRIP)
        c.roundRect(card_x + 6*mm, ref_blk_y - ref_blk_h/2,
                    card_w - 12*mm, ref_blk_h, 5, fill=1, stroke=0)
        c.setFillColor(MUTED)
        c.setFont('Helvetica', 7)
        c.drawString(card_x + 12*mm, ref_blk_y + 3*mm, 'BOOKING REFERENCE')
        c.setFillColor(GOLD)
        c.setFont('Helvetica-Bold', 20)
        c.drawCentredString(W/2, ref_blk_y - 5*mm, str(booking.booking_ref or '—'))

        # ── 2-column detail grid ──
        grid_top = ref_blk_y - 22*mm
        row_h    = 17*mm
        cell_gap = 4*mm
        col_w    = (card_w - 14*mm) / 2
        col1_x   = card_x + 6*mm
        col2_x   = col1_x + col_w + cell_gap

        def detail_cell(x, y, label, value):
            c.setFillColor(STRIP)
            c.roundRect(x, y - row_h + 2*mm, col_w, row_h - 2*mm, 5, fill=1, stroke=0)
            c.setStrokeColor(BORDER)
            c.setLineWidth(0.3)
            c.roundRect(x, y - row_h + 2*mm, col_w, row_h - 2*mm, 5, fill=0, stroke=1)
            c.setFillColor(MUTED)
            c.setFont('Helvetica', 6.5)
            c.drawString(x + 4*mm, y - 3.5*mm, label)
            val_str = str(value) if value else '—'
            # Truncate if too wide
            fs = 10
            while c.stringWidth(val_str, 'Helvetica-Bold', fs) > col_w - 8*mm and fs > 7:
                fs -= 0.5
            c.setFillColor(WHITE)
            c.setFont('Helvetica-Bold', fs)
            c.drawString(x + 4*mm, y - row_h + 6*mm, val_str)

        show_date_str = booking.show_date.strftime('%A, %d %B %Y') if booking.show_date else '—'
        booked_by     = user.name if user else session.get('user_name', '—')
        seats_str     = booking.seat_numbers or f'{booking.num_tickets} Ticket(s)'

        rows = [
            ('DATE',           show_date_str,                  col1_x, grid_top),
            ('SHOW TIME',      booking.show_time or '—',       col2_x, grid_top),
            ('NO. OF TICKETS', str(booking.num_tickets or 1),  col1_x, grid_top - row_h),
            ('PAYMENT METHOD', booking.payment_method or '—',  col2_x, grid_top - row_h),
            ('BOOKED BY',      booked_by,                      col1_x, grid_top - 2*row_h),
            ('SEATS',          seats_str,                      col2_x, grid_top - 2*row_h),
        ]
        for lbl_txt, val_txt, cx, cy in rows:
            detail_cell(cx, cy, lbl_txt, val_txt)

        # ── Total amount bar ──
        total_bar_y = grid_top - 3*row_h - 2*mm
        total_bar_h = 14*mm
        c.setFillColor(DARK_RED)
        c.roundRect(card_x + 6*mm, total_bar_y, card_w - 12*mm, total_bar_h, 5, fill=1, stroke=0)
        c.setStrokeColor(ACCENT)
        c.setLineWidth(1.2)
        c.line(card_x + 6*mm, total_bar_y + total_bar_h,
               card_x + card_w - 6*mm, total_bar_y + total_bar_h)
        c.setFillColor(MUTED)
        c.setFont('Helvetica', 8)
        c.drawString(card_x + 12*mm, total_bar_y + 4.5*mm, 'TOTAL AMOUNT PAID')
        c.setFillColor(ACCENT)
        c.setFont('Helvetica-Bold', 17)
        c.drawRightString(card_x + card_w - 12*mm, total_bar_y + 3.5*mm,
                          f'Rs. {int(booking.total_amount or 0)}')

        # ── QR Code ──
        qr_size  = 30*mm
        qr_pad   = 3.5*mm
        qr_blk_w = qr_size + 2*qr_pad
        qr_blk_h = qr_size + 2*qr_pad + 7*mm
        qr_blk_x = W/2 - qr_blk_w/2
        qr_blk_y = total_bar_y - qr_blk_h - 6*mm

        c.setFillColor(STRIP)
        c.roundRect(qr_blk_x, qr_blk_y, qr_blk_w, qr_blk_h, 6, fill=1, stroke=0)

        qr_data = (f"CINEBOOK|{booking.booking_ref}|{booking.movie_title}|"
                   f"{show_date_str}|{booking.show_time}")
        try:
            qr_obj = qrcode.QRCode(version=2,
                                   error_correction=qrcode.constants.ERROR_CORRECT_M,
                                   box_size=8, border=2)
            qr_obj.add_data(qr_data)
            qr_obj.make(fit=True)
            qr_img = qr_obj.make_image(fill_color='black', back_color='white')
            qr_buf = io.BytesIO()
            qr_img.save(qr_buf, format='PNG')
            qr_buf.seek(0)
            c.setFillColor(WHITE)
            c.roundRect(qr_blk_x + qr_pad - 1, qr_blk_y + 6*mm + qr_pad - 1,
                        qr_size + 2, qr_size + 2, 2, fill=1, stroke=0)
            c.drawImage(ImageReader(qr_buf),
                        qr_blk_x + qr_pad, qr_blk_y + 6*mm + qr_pad,
                        width=qr_size, height=qr_size)
        except Exception:
            c.setFillColor(MUTED)
            c.setFont('Helvetica', 8)
            c.drawCentredString(W/2, qr_blk_y + qr_blk_h/2, 'QR unavailable')

        c.setFillColor(MUTED)
        c.setFont('Helvetica', 6.5)
        c.drawCentredString(W/2, qr_blk_y + 3.5*mm, 'Scan at theatre entrance for entry')

        # ── Bottom terms strip ──
        terms_y = card_y + 6*mm
        terms_h = 11*mm
        c.setFillColor(STRIP)
        c.roundRect(card_x + 6*mm, terms_y, card_w - 12*mm, terms_h, 4, fill=1, stroke=0)
        booked_at_str = (booking.booked_at.strftime('%d %b %Y, %I:%M %p')
                         if booking.booked_at else '—')
        c.setFillColor(MUTED)
        c.setFont('Helvetica', 6)
        c.drawCentredString(W/2, terms_y + 6.5*mm,
                            f'Generated: {booked_at_str}   |   Present this ticket at the theatre entrance')
        c.drawCentredString(W/2, terms_y + 2.5*mm,
                            'Non-transferable   |   No refunds after show start   |   cinebook.in')

        c.save()
        buf.seek(0)
        return buf.read()
    except Exception as e:
        print(f"PDF generation error: {e}")
        import traceback; traceback.print_exc()
        return None


def _send_booking_email(user, booking):
    """Send booking confirmation email with PDF attachment."""
    mail_user = (current_app.config.get("MAIL_USERNAME") or os.environ.get("MAIL_USERNAME", "")).strip()
    mail_pass = (current_app.config.get("MAIL_PASSWORD") or os.environ.get("MAIL_PASSWORD", "")).strip()

    to_email = user.email

    # Always log in dev mode
    print(f"\n{'='*56}")
    print(f"  [BOOKING EMAIL] To: {to_email}")
    print(f"  Booking Ref: {booking.booking_ref}  |  Movie: {booking.movie_title}")
    print(f"{'='*56}\n")

    if not mail_user or not mail_pass or mail_user == "your_email@gmail.com":
        return True  # dev mode – skip real send

    show_date_str = booking.show_date.strftime('%A, %d %B %Y') if booking.show_date else '—'

    html_body = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:560px;margin:auto;
                background:#06080f;border-radius:16px;overflow:hidden;
                border:1px solid #1e2d48;">
      <!-- Header -->
      <div style="background:linear-gradient(135deg,#e5383b,#c00);padding:28px 32px;text-align:center;">
        <h1 style="color:#fff;margin:0;font-size:1.7rem;letter-spacing:1px;">🎬 CineBook</h1>
        <p style="color:rgba(255,255,255,.8);margin:6px 0 0;font-size:.9rem;">Your booking is confirmed!</p>
      </div>
      <!-- Green badge -->
      <div style="background:#0f2a1a;padding:14px;text-align:center;border-bottom:1px solid #1e2d48;">
        <span style="color:#22c55e;font-size:1.1rem;font-weight:800;">✅ BOOKING CONFIRMED</span>
      </div>
      <!-- Body -->
      <div style="padding:32px;">
        <p style="color:#f0f4ff;font-size:1rem;margin:0 0 20px;">Hi <strong>{user.name}</strong>, your tickets are booked!</p>

        <!-- Movie title -->
        <div style="background:#141c2e;border-radius:12px;padding:20px;margin-bottom:16px;text-align:center;">
          <div style="color:#fff;font-size:1.4rem;font-weight:900;margin-bottom:6px;">{booking.movie_title}</div>
          <div style="color:#8899bb;font-size:.88rem;">{booking.theatre_name} &nbsp;·&nbsp; {booking.theatre_city}</div>
        </div>

        <!-- Booking ref -->
        <div style="background:#141c2e;border-radius:10px;padding:16px;margin-bottom:16px;
                    border:1.5px dashed #ffd60a;text-align:center;">
          <div style="color:#8899bb;font-size:.75rem;font-weight:700;text-transform:uppercase;
                      letter-spacing:1px;margin-bottom:6px;">Booking Reference</div>
          <div style="color:#ffd60a;font-size:1.7rem;font-weight:900;letter-spacing:4px;">
            {booking.booking_ref}
          </div>
        </div>

        <!-- Details table -->
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse;background:#141c2e;border-radius:10px;overflow:hidden;">
          <tr style="background:#0f1826;">
            <td style="padding:10px 16px;color:#8899bb;font-size:.8rem;font-weight:700;width:40%;">DATE</td>
            <td style="padding:10px 16px;color:#f0f4ff;font-size:.88rem;font-weight:700;">{show_date_str}</td>
          </tr>
          <tr>
            <td style="padding:10px 16px;color:#8899bb;font-size:.8rem;font-weight:700;">SHOW TIME</td>
            <td style="padding:10px 16px;color:#f0f4ff;font-size:.88rem;font-weight:700;">{booking.show_time or '—'}</td>
          </tr>
          <tr style="background:#0f1826;">
            <td style="padding:10px 16px;color:#8899bb;font-size:.8rem;font-weight:700;">TICKETS</td>
            <td style="padding:10px 16px;color:#f0f4ff;font-size:.88rem;font-weight:700;">{booking.num_tickets}</td>
          </tr>
          <tr>
            <td style="padding:10px 16px;color:#8899bb;font-size:.8rem;font-weight:700;">SEATS</td>
            <td style="padding:10px 16px;color:#f0f4ff;font-size:.88rem;font-weight:700;">{booking.seat_numbers or '—'}</td>
          </tr>
          <tr style="background:#0f1826;">
            <td style="padding:10px 16px;color:#8899bb;font-size:.8rem;font-weight:700;">PAYMENT</td>
            <td style="padding:10px 16px;color:#f0f4ff;font-size:.88rem;font-weight:700;">{booking.payment_method or '—'}</td>
          </tr>
          <tr style="background:#1a0508;">
            <td style="padding:12px 16px;color:#8899bb;font-size:.85rem;font-weight:800;border-top:2px solid #e5383b;">TOTAL PAID</td>
            <td style="padding:12px 16px;color:#e5383b;font-size:1.1rem;font-weight:900;border-top:2px solid #e5383b;">
              &#8377;{int(booking.total_amount)}
            </td>
          </tr>
        </table>

        <p style="color:#8899bb;font-size:.78rem;margin-top:20px;text-align:center;">
          📎 Your e-ticket PDF is attached. Please show it at the theatre entrance.
        </p>
      </div>
      <!-- Footer -->
      <div style="background:#030508;padding:16px 32px;text-align:center;border-top:1px solid #1e2d48;">
        <p style="color:#4a5568;font-size:.74rem;margin:0;">
          © 2025 CineBook Cinemas &nbsp;·&nbsp; This is an automated email, please do not reply.
        </p>
      </div>
    </div>"""

    # Generate PDF attachment
    pdf_bytes = generate_ticket_pdf(booking, user)

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"🎬 Booking Confirmed – {booking.movie_title} [{booking.booking_ref}]"
        msg["From"]    = f"CineBook <{mail_user}>"
        msg["To"]      = to_email

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(html_body, "html"))
        msg.attach(alt)

        if pdf_bytes:
            part = MIMEBase("application", "pdf")
            part.set_payload(pdf_bytes)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment",
                            filename=f"CineBook_Ticket_{booking.booking_ref}.pdf")
            msg.attach(part)

        for method, host, port in [("starttls", "smtp.gmail.com", 587), ("ssl", "smtp.gmail.com", 465)]:
            try:
                if method == "starttls":
                    server = smtplib.SMTP(host, port, timeout=15)
                    server.ehlo(); server.starttls(); server.ehlo()
                else:
                    import ssl as _ssl
                    server = smtplib.SMTP_SSL(host, port, context=_ssl.create_default_context(), timeout=15)
                server.login(mail_user, mail_pass)
                server.sendmail(mail_user, to_email, msg.as_string())
                server.quit()
                print(f"✅ Booking email sent to {to_email}")
                return True
            except Exception as e:
                print(f"⚠️ SMTP {method}:{port} failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Email send error: {e}")
        return False


@user_bp.route("/dashboard")
@login_required
@role_required("user")
def dashboard():
    user_id = session.get("user_id")
    user = AppUser.query.get(user_id)
    bookings = UserBooking.query.filter_by(user_id=user_id).order_by(UserBooking.booked_at.desc()).limit(5).all()
    total_bookings = UserBooking.query.filter_by(user_id=user_id).count()
    confirmed = UserBooking.query.filter_by(user_id=user_id, status="Confirmed").count()
    cancelled = UserBooking.query.filter_by(user_id=user_id, status="Cancelled").count()

    return render_template("user/dashboard.html", user=user, bookings=bookings,
        total_bookings=total_bookings, confirmed=confirmed, cancelled=cancelled)


@user_bp.route("/bookings")
@login_required
@role_required("user")
def my_bookings():
    user_id = session.get("user_id")
    tab = request.args.get("tab", "upcoming")
    today = date.today()

    base_query = UserBooking.query.filter_by(user_id=user_id)

    # Tab counts for badges
    upcoming_count  = base_query.filter(
        (UserBooking.show_date >= today) | (UserBooking.show_date == None),
        UserBooking.status == "Confirmed"
    ).count()
    past_count      = base_query.filter(UserBooking.show_date < today).count()
    cancelled_count = base_query.filter_by(status="Cancelled").count()
    all_count       = base_query.count()

    if tab == "upcoming":
        bookings = base_query.filter(
            (UserBooking.show_date >= today) | (UserBooking.show_date == None),
            UserBooking.status == "Confirmed"
        ).order_by(UserBooking.show_date.asc().nullsfirst()).all()
    elif tab == "past":
        bookings = base_query.filter(UserBooking.show_date < today).order_by(UserBooking.show_date.desc()).all()
    elif tab == "cancelled":
        bookings = base_query.filter_by(status="Cancelled").order_by(UserBooking.booked_at.desc()).all()
    else:
        bookings = base_query.order_by(UserBooking.booked_at.desc()).all()

    return render_template("user/bookings.html", bookings=bookings, tab=tab,
                           upcoming_count=upcoming_count, past_count=past_count,
                           cancelled_count=cancelled_count, all_count=all_count,
                           today=today)


@user_bp.route("/payment-qr", methods=["POST"])
@login_required
@role_required("user")
def payment_qr():
    """Generate a UPI QR code for a pending payment."""
    data = request.get_json() or {}
    amount      = float(data.get("amount", 0))
    movie_title = data.get("movie_title", "Movie")
    booking_ref = data.get("booking_ref", gen_booking_ref())

    if amount <= 0:
        return jsonify({"success": False, "message": "Invalid amount."}), 400

    qr_image, upi_url = generate_upi_qr(amount, movie_title, booking_ref)
    return jsonify({
        "success": True,
        "qr_image": qr_image,
        "upi_url": upi_url,
        "amount": amount,
        "booking_ref": booking_ref,
    })


@user_bp.route("/book/<show_id>", methods=["GET", "POST"])
@login_required
@role_required("user")
def book_ticket(show_id):
    try:
        show = db.session.execute(text("""
            SELECT s.show_id, s.show_date, s.start_time, s.price_per_ticket, s.available_seats,
                   m.title as movie_title, m.language, m.genre, m.duration,
                   t.name as theatre_name, t.city, t.location, sc.screen_number
            FROM shows s
            JOIN movies m ON m.movie_id = s.movie_id
            JOIN theaters t ON t.theater_id = s.theater_id
            JOIN screens sc ON sc.screen_id = s.screen_id
            WHERE s.show_id = :sid
        """), {"sid": show_id}).fetchone()
    except:
        show = None

    if not show:
        flash("Show not found.", "danger")
        return redirect(url_for("public.home"))

    if request.method == "POST":
        data = request.get_json() if request.is_json else request.form
        num_tickets    = int(data.get("num_tickets", 1))
        payment_method = data.get("payment_method", "Online")
        seat_numbers   = data.get("seat_numbers", "")

        if num_tickets < 1 or num_tickets > 10:
            msg = "Invalid number of tickets (1-10 allowed)."
            if request.is_json:
                return jsonify({"success": False, "message": msg}), 400
            flash(msg, "danger")

        # Use total_amount from frontend (includes ticket price + ₹30/ticket convenience fee)
        # Fallback: calculate with convenience fee if not sent
        passed_total = data.get("total_amount")
        if passed_total:
            total_amount = float(passed_total)
        else:
            ticket_subtotal = num_tickets * (show.price_per_ticket or 150)
            convenience_fee = num_tickets * 30
            total_amount = ticket_subtotal + convenience_fee

        booking = UserBooking(
            user_id=session.get("user_id"),
            show_id=show_id,
            movie_title=show.movie_title,
            theatre_name=show.theatre_name,
            theatre_city=show.city,
            show_date=show.show_date,
            show_time=show.start_time,
            num_tickets=num_tickets,
            total_amount=total_amount,
            payment_method=payment_method,
            status="Confirmed",
            booking_ref=gen_booking_ref(),
            seat_numbers=seat_numbers
        )
        db.session.add(booking)
        db.session.commit()

        # ── Confirm seat locks → permanent BookedSeat records ──
        seat_list = [s.strip() for s in seat_numbers.split(",") if s.strip()] if seat_numbers else []
        if seat_list:
            try:
                from models.models import SeatLock, BookedSeat
                from datetime import datetime as _dt
                for seat_id in seat_list:
                    SeatLock.query.filter_by(
                        show_id=show_id, seat_id=seat_id, user_id=session.get("user_id")
                    ).update({"status": "confirmed"})
                    try:
                        bs = BookedSeat(show_id=show_id, seat_id=seat_id, booking_id=booking.id,
                                        booked_at=_dt.utcnow())
                        db.session.add(bs)
                        db.session.flush()
                    except Exception:
                        db.session.rollback()
                db.session.commit()
            except Exception as _se:
                print(f"Seat confirm error (non-fatal): {_se}")

        # ── Decrement available_seats on the show ──
        try:
            db.session.execute(
                text("UPDATE shows SET available_seats = GREATEST(available_seats - :n, 0) WHERE show_id = :sid"),
                {"n": num_tickets, "sid": show_id}
            )
            db.session.commit()
        except Exception as _de:
            print(f"available_seats decrement error (non-fatal): {_de}")

        # Send confirmation email with PDF (best-effort, non-blocking)
        try:
            user_obj = AppUser.query.get(session.get("user_id"))
            _send_booking_email(user_obj, booking)
        except Exception as e:
            print(f"Email send error (non-fatal): {e}")

        show_date_str = booking.show_date.strftime('%d %b %Y') if booking.show_date else '—'

        user_obj2 = AppUser.query.get(session.get("user_id"))
        user_email = user_obj2.email if user_obj2 else session.get("user_email", "")

        if request.is_json:
            return jsonify({
                "success": True,
                "booking_ref": booking.booking_ref,
                "booking_id":  booking.id,
                "movie_title": booking.movie_title,
                "theatre_name": booking.theatre_name,
                "theatre_city": booking.theatre_city,
                "show_date":   show_date_str,
                "show_time":   str(booking.show_time) if booking.show_time else '—',
                "num_tickets": booking.num_tickets,
                "seat_numbers": booking.seat_numbers or '—',
                "payment_method": booking.payment_method,
                "total_amount": int(booking.total_amount),
                "user_email": user_email,
                "pdf_url": url_for("user.download_ticket_pdf", booking_id=booking.id),
                "redirect": url_for("public.home")
            })
        return redirect(url_for("user.booking_confirmation", booking_id=booking.id))

    return render_template("user/book_ticket.html", show=show)


@user_bp.route("/booking/confirmation/<int:booking_id>")
@login_required
@role_required("user")
def booking_confirmation(booking_id):
    booking = UserBooking.query.filter_by(id=booking_id, user_id=session.get("user_id")).first_or_404()
    return render_template("user/confirmation.html", booking=booking)


@user_bp.route("/booking/<int:booking_id>/download-pdf")
@login_required
@role_required("user")
def download_ticket_pdf(booking_id):
    booking = UserBooking.query.filter_by(id=booking_id, user_id=session.get("user_id")).first_or_404()
    user_obj = AppUser.query.get(session.get("user_id"))
    pdf_bytes = generate_ticket_pdf(booking, user_obj)
    if not pdf_bytes:
        return "PDF generation failed.", 500
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'attachment; filename="CineBook_Ticket_{booking.booking_ref}.pdf"'
    return resp


@user_bp.route("/booking/<int:booking_id>/cancel", methods=["POST"])
@login_required
@role_required("user")
def cancel_booking(booking_id):
    booking = UserBooking.query.filter_by(id=booking_id, user_id=session.get("user_id")).first_or_404()
    if booking.status == "Cancelled":
        return jsonify({"success": False, "message": "Already cancelled."}), 400

    # ── Block cancellation if show has already started or passed ──
    if booking.show_date and booking.show_time:
        try:
            from datetime import datetime as _dt, timedelta
            # Combine show_date + show_time into a datetime
            if isinstance(booking.show_time, str):
                for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p"):
                    try:
                        show_dt = _dt.combine(booking.show_date, _dt.strptime(booking.show_time, fmt).time())
                        break
                    except ValueError:
                        continue
                else:
                    show_dt = None
            else:
                # show_time is already a timedelta (common in MySQL)
                show_dt = _dt.combine(booking.show_date, (_dt.min + booking.show_time).time())

            if show_dt and _dt.now() >= show_dt:
                return jsonify({
                    "success": False,
                    "message": "This show has already started or ended. Cancellation is not allowed."
                }), 400
        except Exception as _te:
            print(f"Show time check error (non-fatal): {_te}")

    booking.status = "Cancelled"
    db.session.commit()

    # ── Release permanent seat holds so others can book ──
    try:
        from models.models import BookedSeat
        BookedSeat.query.filter_by(booking_id=booking_id).delete()
        # Restore available_seats count
        seat_count = booking.num_tickets or 0
        if seat_count:
            db.session.execute(
                text("UPDATE shows SET available_seats = available_seats + :n WHERE show_id = :sid"),
                {"n": seat_count, "sid": booking.show_id}
            )
        db.session.commit()
    except Exception as _ce:
        print(f"Seat release on cancel error (non-fatal): {_ce}")

    return jsonify({"success": True, "message": "Booking cancelled successfully."})


@user_bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("user")
def profile():
    user = AppUser.query.get(session.get("user_id"))
    if request.method == "POST":
        data = request.get_json() if request.is_json else request.form
        user.name  = data.get("name",  user.name)
        user.phone = data.get("phone", user.phone)
        user.city  = data.get("city",  user.city)
        db.session.commit()
        session["user_name"] = user.name
        if request.is_json:
            return jsonify({"success": True, "message": "Profile updated."})
        flash("Profile updated.", "success")
    return render_template("user/profile.html", user=user)
