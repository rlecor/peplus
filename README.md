# PE+ Phase 1 MVP

PE+ is a Phase 1 MVP for an instant preliminary business acquisition offer website.

A seller enters business and financial details. The app calculates normalized earnings, estimates a valuation range, applies a buyer discount, and either shows a preliminary offer range or routes the deal to manual review.

## Features

- Landing page
- Seller/business intake form
- Financial intake form
- Normalized earnings calculation
- Deal score
- Preliminary valuation range
- Preliminary offer range
- Manual review routing for red flags
- SQLite database
- Password-protected admin dashboard

## Local Setup

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

Admin:

```text
http://127.0.0.1:5000/admin
```

Default admin password:

```text
admin123
```

For production, set environment variables:

```bash
SECRET_KEY=your-secure-secret
ADMIN_PASSWORD=your-secure-admin-password
```

## Important Disclaimer

This MVP is for testing and demonstration only. The offer shown is a preliminary non-binding indication based on user-submitted information. It should not be treated as legal, tax, financial, investment, or acquisition advice.
