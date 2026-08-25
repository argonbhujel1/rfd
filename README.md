# Ratuwamai Food Delivery

Lightweight, mobile-first food delivery MVP built with **Flask + SQLite + Vanilla JS + Leaflet**.

Suitable for a small local business (NPR ~10k budget). No React, no Node, no paid map APIs.

---

## Features

- **Customer**: Browse menu, cart, guest COD checkout, order tracking with live map
- **Admin**: Dashboard, order management, food/category CRUD, image upload, delivery boy management, website settings, banners
- **Delivery boy**: Login, assigned orders, browser GPS sharing, mark delivered
- **Live tracking**: Leaflet + OpenStreetMap, delivery location polled via AJAX

---

## Requirements

- Python 3.10+ (3.11/3.12 recommended)
- pip

---

## Quick Start (Local)

```bash
# 1. Enter project folder
cd ratuwamai-food-delivery

# 2. Create virtual environment
python3 -m venv venv

# 3. Activate
# Linux / macOS:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Environment (optional)
cp .env.example .env
# Edit SECRET_KEY in .env for production

# 6. Run (creates SQLite DB + seed data on first run)
python app.py
```

Open: **http://127.0.0.1:5000**

---

## Demo Accounts (CHANGE IN PRODUCTION)

| Role          | Username   | Password     |
|---------------|------------|--------------|
| Admin         | `admin`    | `admin123`   |
| Delivery Boy  | `delivery1`| `delivery123`|

**URLs**
- Customer site: `/`
- Admin panel: `/admin/login`
- Delivery dashboard: `/delivery/login`
- Track order: `/track` or `/track/RFD-1001`

---

## Seed Data

On first run the app creates:

- Admin user
- Categories (Momo, Chowmein, Khaja, Burger, Pizza, Chicken, Snacks, Drinks, Other)
- Sample Nepali foods with prices
- One delivery boy
- Sample customer reviews
- Default website settings (phone, hero text, delivery charge Rs 50, etc.)

---

## Project Structure

```
ratuwamai-food-delivery/
├── app.py              # Main Flask application
├── config.py
├── models.py
├── requirements.txt
├── .env.example
├── README.md
├── instance/           # SQLite DB (auto-created)
├── static/
│   ├── css/style.css
│   ├── js/ (main, cart, tracking, delivery)
│   ├── images/
│   └── uploads/        # Food & banner images
└── templates/
    ├── base.html, index, menu, cart, checkout, track...
    ├── admin/
    ├── delivery/
    └── errors/
```

---

## Location Tracking Notes

- Delivery boy uses **browser Geolocation API** (`navigator.geolocation.watchPosition`).
- Location is sent only while the delivery page is open and sharing is started.
- **Not** true background GPS (browser/OS restrictions). Keep the phone screen on during delivery.
- Customer tracking page polls `/api/orders/<order_number>/location` every ~8 seconds.
- Map: Leaflet.js + OpenStreetMap (free, no API key).

If permission is denied or GPS is unavailable, the UI shows a clear message.

---

## Image Uploads

- Admin can upload food/banner images (JPG, JPEG, PNG, WEBP, max 5MB).
- Files are stored in `static/uploads/` with safe unique names.
- Ensure the folder is writable by the web server in production.

---

## Production Deployment (simple)

1. Set a strong `SECRET_KEY` in environment / `.env`.
2. Set `FLASK_DEBUG=0` and `FLASK_ENV=production`.
3. Change default admin and delivery passwords immediately.
4. Use a production WSGI server, e.g.:

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

5. Put Nginx (or similar) in front for HTTPS and static files.
6. Keep `instance/` and `static/uploads/` persistent and backed up.
7. For SQLite under concurrent load, consider migrating to PostgreSQL later; for a small local business SQLite is usually fine.

---

## Security Checklist

- [ ] Change `SECRET_KEY`
- [ ] Change admin password
- [ ] Change delivery boy passwords
- [ ] Disable debug mode in production
- [ ] Use HTTPS
- [ ] Restrict file upload size and types (already enforced in code)

---

## Tech Stack

| Layer      | Choice                          |
|------------|---------------------------------|
| Backend    | Python Flask                    |
| Database   | SQLite + SQLAlchemy             |
| Templates  | Jinja2                          |
| Frontend   | HTML5, CSS3, Vanilla JS         |
| Maps       | Leaflet.js + OpenStreetMap      |
| Auth       | Flask-Login + Werkzeug hashing  |

---

## License / Usage

Built as a lightweight MVP for Ratuwamai Food Delivery.  
Replace demo content, upload real food photos, and update contact details before going live.
