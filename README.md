# Django Expense Tracker (Spend Shelf)

A production-ready Django expense tracker covering:
- Authentication (signup/login/logout)
- Expense CRUD (create, read, update, delete)
- Financial profile (savings, salary, monthly budget)
- Dashboard with 6-month trend chart
- Budget alerts and usage insights
- Recurring transactions processing
- CSV expense imports
- Monthly reports with category breakdown
- Form validation and user-scoped data
- Deployment-ready configuration for cloud hosting

## Features

- User auth via Django auth system
- User-specific categories and expenses
- Dashboard metrics:
  - Current month total
  - Lifetime total
  - Recent expenses
  - 6-month line chart
  - Budget usage alerts
  - Spending insights (top category, avg daily spend, salary ratio)
- Reports:
  - Select month
  - Total monthly spend
  - Category breakdown
  - Detailed entries
- Recurring:
  - Weekly/monthly recurring setup
  - Manual processing of due recurring expenses
- Imports:
  - CSV upload for bulk expense import
- Exports:
  - CSV export of all spending and financial profile
- Secure user data filtering in every query

## Tech Stack

- Django 5
- SQLite for local development
- PostgreSQL-ready via `DATABASE_URL`
- WhiteNoise for static files
- Gunicorn for production

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment variables (copy `.env.example` to `.env`).
4. Run migrations:

```bash
python manage.py makemigrations
python manage.py migrate
```

5. Create a superuser (optional):

```bash
python manage.py createsuperuser
```

6. Start the server:

```bash
python manage.py runserver
```

7. Open `http://127.0.0.1:8000/`

## Deployment (Render/Heroku-like)

1. Set environment variables:
   - `DJANGO_SECRET_KEY`
   - `DJANGO_DEBUG=False`
   - `DJANGO_ALLOWED_HOSTS=<your-domain>`
   - `DJANGO_CSRF_TRUSTED_ORIGINS=https://<your-domain>`
   - `DATABASE_URL=<postgres-url>`

2. Ensure install command includes:

```bash
pip install -r requirements.txt
```

3. Run DB migrations in a release step or once after deploy:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

4. App starts with Procfile:

```text
web: gunicorn expense_tracker.wsgi --log-file -
```

## URLs

- `/signup/` - registration
- `/login/` - login
- `/` - dashboard
- `/expenses/` - list expenses
- `/expenses/add/` - add expense
- `/profile/financial/` - savings/salary/budget profile
- `/recurring/` - recurring transactions
- `/imports/csv/` - import expenses from CSV
- `/exports/spending.csv` - export spending and profile as CSV
- `/reports/monthly/` - monthly reports
- `/admin/` - admin site

## Notes

- Click `Setup Categories` after signup to create starter categories.
- All expense and report views are login-protected.
- Each user can only view and manage their own data.
