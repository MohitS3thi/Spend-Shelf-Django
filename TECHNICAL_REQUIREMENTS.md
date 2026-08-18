# Technical Requirements Document
## Spend Shelf Expense Tracker

**Version:** 1.0  
**Last Updated:** 2026-08-18  
**Status:** Active  

---

## Table of Contents
1. [Technology Stack](#technology-stack)
2. [System Architecture](#system-architecture)
3. [Database Design](#database-design)
4. [API Specifications](#api-specifications)
5. [Frontend Requirements](#frontend-requirements)
6. [Development Standards](#development-standards)
7. [Testing Requirements](#testing-requirements)
8. [Code Quality](#code-quality)
9. [Integration & Third-Party Services](#integration--third-party-services)
10. [Performance & Scalability](#performance--scalability)
11. [Security Technical Specs](#security-technical-specs)
12. [Development Workflow](#development-workflow)

---

## Technology Stack

### Core Framework
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Web Framework | Django | 5.1.6+ | Python web framework, ORM, admin panel |
| Application Server | Gunicorn | 23.0.0+ | WSGI HTTP server |
| Database | PostgreSQL | 16 | Relational database (production) |
| Database (Dev) | SQLite3 | Latest | Development and testing |
| Reverse Proxy | Nginx | Latest (Alpine) | Static files, SSL termination, compression |
| Static Files | WhiteNoise | 6.9.0 | Efficient static file serving |
| Containerization | Docker | 20.10+ | Application containerization |
| Orchestration | Docker Compose | 2.0+ | Multi-container orchestration |

### Python Package Stack
```
Core Dependencies:
  - Django==5.1.6              # Web framework
  - gunicorn==23.0.0           # Application server
  - whitenoise==6.9.0          # Static file handling
  - psycopg[binary]==3.2.13    # PostgreSQL adapter
  
Data & Reporting:
  - reportlab==4.0.0           # PDF generation
  - matplotlib==3.8.0          # Data visualization/charts
  
Development Dependencies (not in requirements.txt):
  - Django-debug-toolbar       # Development debugging
  - pytest-django              # Testing framework
  - black                      # Code formatting
  - flake8                      # Linting
  - coverage                    # Test coverage reporting
  - factory-boy                # Test fixtures
```

### Frontend Stack
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Template Engine | Django Templates | Server-side rendering |
| CSS | CSS3 + Django Static | Styling (Bootstrap optional) |
| JavaScript | Vanilla JS or jQuery | Client-side interactivity |
| Forms | Django Forms | Form validation and rendering |
| Admin Interface | Django Admin | Built-in admin panel |

### Supporting Tools & Services
| Tool | Purpose | Version |
|------|---------|---------|
| Git | Version control | 2.0+ |
| GitHub | Repository hosting & CI/CD | - |
| Docker Registry | Image storage (Docker Hub/Private) | - |
| SSL/TLS | Let's Encrypt | Certbot 2.0+ |
| Package Manager | pip | Python 3.8+ |

---

## System Architecture

### High-Level Architecture Diagram
```
┌─────────────────────────────────────────────────────┐
│                 Internet / Users                     │
└─────────────────┬───────────────────────────────────┘
                  │ HTTPS (Port 443)
                  ▼
        ┌─────────────────────┐
        │   Nginx Reverse     │
        │   Proxy + SSL       │
        │   - Static Files    │
        │   - Compression     │
        │   - Caching         │
        └──────────┬──────────┘
                   │ HTTP (Port 8000)
        ┌──────────▼──────────┐
        │  Docker Network     │
        │  (spend-shelf-net)  │
        └──────────┬──────────┘
         ┌─────────┼─────────┐
         │         │         │
    ┌────▼───┐ ┌──▼────┐ ┌─▼──────┐
    │ Gunicorn│ │Static │ │Database│
    │ Django  │ │Files  │ │Postgres│
    │App      │ │Volume │ │ Port   │
    │4 Workers│ └───────┘ │ 5432   │
    └─────────┘            └────────┘
```

### Container Architecture
```
docker-compose.prod.yml:
├── Service: db
│   ├── Image: postgres:16-alpine
│   ├── Container: spend-shelf-db
│   ├── Ports: 5432:5432 (internal)
│   ├── Volumes: db_data:/var/lib/postgresql/data
│   ├── Health Check: pg_isready
│   └── Resources: 2CPU / 2GB RAM limit
│
├── Service: web
│   ├── Image: spend-shelf:prod (custom Dockerfile)
│   ├── Container: spend-shelf-app
│   ├── Ports: 8000:8000 (exposed to nginx)
│   ├── Volumes: 
│   │   - app_static:/app/staticfiles
│   │   - app_data:/app/data
│   ├── Health Check: HTTP GET http://localhost:8000/
│   ├── Resources: 1CPU / 1GB RAM limit
│   ├── Workers: 4 gunicorn sync workers
│   └── Env Variables: DJANGO_*, DATABASE_URL, SECURE_*
│
└── Service: nginx
    ├── Image: nginx:latest (alpine)
    ├── Container: spend-shelf-nginx
    ├── Ports: 80:80, 443:443 (external)
    ├── Volumes:
    │   - nginx.conf:/etc/nginx/nginx.conf
    │   - app_static:/app/staticfiles
    │   - ssl/:/etc/nginx/ssl/
    ├── Health Check: curl localhost
    └── Resources: 0.5CPU / 256MB RAM limit

Persistent Volumes:
├── db_data (~50GB)
├── app_static (~100MB)
└── app_data (user uploads/media)
```

### Application Directory Structure
```
expense_tracker/
├── __init__.py
├── asgi.py                 # ASGI configuration
├── wsgi.py                 # WSGI configuration
├── settings.py             # Django settings
├── urls.py                 # URL routing (project-level)
└── [middleware & utilities]

expenses/
├── __init__.py
├── admin.py                # Django admin configuration
├── apps.py                 # App configuration
├── models.py               # Database models
├── views.py                # View logic
├── forms.py                # Form definitions
├── urls.py                 # URL routing (app-level)
├── migrations/
│   ├── __init__.py
│   ├── 0001_initial.py
│   └── [subsequent migrations]
└── tests.py                # Unit and integration tests

templates/
├── base.html               # Base template
├── expenses/
│   ├── dashboard.html
│   ├── expense_list.html
│   ├── expense_form.html
│   ├── expense_confirm_delete.html
│   ├── analysis.html
│   ├── recurring_transactions.html
│   ├── report_monthly.html
│   └── import_csv.html
└── registration/
    ├── login.html
    └── signup.html

static/
└── css/
    └── styles.css          # Application styling

staticfiles/                # Generated by collectstatic
├── admin/
├── css/
└── [compiled static assets]
```

---

## Database Design

### Database Schema

#### Users & Authentication
```sql
-- Handled by Django's built-in auth system
django.contrib.auth.User
├── id (PK)
├── username (UNIQUE)
├── email (UNIQUE)
├── password (hashed with PBKDF2)
├── is_active (Boolean)
├── is_staff (Boolean)
├── date_joined (DateTime)
└── last_login (DateTime)

-- FinancialProfile (1-to-1 with User)
expenses.FinancialProfile
├── id (PK)
├── user_id (FK to User)
├── currency (CharField, default "USD")
├── budget (DecimalField)
├── created_at (DateTime)
└── updated_at (DateTime)
```

#### Core Expense Records
```sql
-- Expense (main transaction table)
expenses.Expense
├── id (PK)
├── user_id (FK to User)
├── category (CharField)
├── amount (DecimalField, 2 decimal places)
├── date (DateField)
├── description (TextField)
├── tags (TextField, comma-separated)
├── is_recurring (Boolean)
├── created_at (DateTime)
├── updated_at (DateTime)
└── deleted (BooleanField, soft-delete flag)

-- RecurringTransaction
expenses.RecurringTransaction
├── id (PK)
├── user_id (FK to User)
├── expense_id (FK to Expense, nullable)
├── frequency (CharField: DAILY, WEEKLY, MONTHLY, YEARLY)
├── next_due_date (DateField)
├── last_processed (DateField)
├── is_active (Boolean)
├── created_at (DateTime)
└── updated_at (DateTime)
```

### Database Indexes
```sql
-- Performance critical indexes
CREATE INDEX idx_expense_user_date ON expenses_expense(user_id, date DESC);
CREATE INDEX idx_expense_created_at ON expenses_expense(created_at DESC);
CREATE INDEX idx_expense_category ON expenses_expense(category);
CREATE INDEX idx_recurring_user_active ON expenses_recurringtransaction(user_id, is_active);
CREATE INDEX idx_financial_profile_user ON expenses_financialprofile(user_id);
```

### Constraints & Validation
```sql
-- Not Null Constraints
Expense:
  ✓ user_id NOT NULL
  ✓ amount NOT NULL (> 0)
  ✓ date NOT NULL
  ✓ created_at NOT NULL
  
RecurringTransaction:
  ✓ user_id NOT NULL
  ✓ frequency NOT NULL (IN 'DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY')
  ✓ is_active NOT NULL (DEFAULT true)
  
FinancialProfile:
  ✓ user_id NOT NULL (UNIQUE)
  ✓ currency NOT NULL (DEFAULT 'USD')

-- Check Constraints
Expense.amount > 0
RecurringTransaction.next_due_date >= CURRENT_DATE
```

### Data Types
| Field | Type | PostgreSQL Type | Size | Notes |
|-------|------|-----------------|------|-------|
| amount | DecimalField(10,2) | NUMERIC(10,2) | 10 bytes | Up to $9,999,999.99 |
| date | DateField | DATE | 4 bytes | YYYY-MM-DD |
| category | CharField(50) | VARCHAR(50) | 50 bytes | Fixed category list |
| description | TextField | TEXT | Variable | Up to 1GB practical limit |
| created_at | DateTimeField | TIMESTAMP | 8 bytes | UTC with timezone |
| is_active | BooleanField | BOOLEAN | 1 byte | True/False |

### Relationships
```
User (1) ──────────────► (N) Expense
  └─ (1) ─► (1) FinancialProfile
  
User (1) ──────────────► (N) RecurringTransaction
  └─ Optional link to Expense template
```

### Query Patterns & Optimization
```python
# Frequently used queries requiring optimization:

# 1. User's expenses for date range
Expense.objects.filter(
    user=request.user,
    date__gte=start_date,
    date__lte=end_date
).order_by('-date')
# Index: (user_id, date DESC)

# 2. Monthly spending summary by category
Expense.objects.filter(
    user=request.user,
    date__year=year,
    date__month=month
).values('category').annotate(total=Sum('amount'))
# Index: (user_id, date DESC)

# 3. Recurring transactions due today
RecurringTransaction.objects.filter(
    user=request.user,
    is_active=True,
    next_due_date__lte=today
)
# Index: (user_id, is_active, next_due_date)

# 4. User's budget and total expenses
FinancialProfile.objects.get(user=request.user)
Expense.objects.filter(
    user=request.user,
    date__year=current_year,
    date__month=current_month
).aggregate(total=Sum('amount'))
```

### Backup & Recovery
- **Full Backup:** Daily automated SQL dumps via pg_dump
- **Point-in-Time Recovery:** PostgreSQL WAL archiving (if enabled)
- **Backup Size:** ~50-100MB compressed per month of data
- **Retention:** Minimum 30 days, 90 days recommended

---

## API Specifications

### RESTful Endpoints

#### Authentication
```
POST   /auth/login/              - User login
POST   /auth/logout/             - User logout
POST   /auth/signup/             - User registration
POST   /auth/password-reset/     - Password reset
GET    /auth/user/               - Get current user profile
```

#### Expenses (Core)
```
GET    /expenses/                - List user's expenses (paginated)
POST   /expenses/                - Create new expense
GET    /expenses/<id>/           - Retrieve specific expense
PUT    /expenses/<id>/           - Update expense
DELETE /expenses/<id>/           - Delete expense (soft delete)
GET    /expenses/search/         - Search expenses by criteria
GET    /expenses/export/         - Export expenses (CSV/PDF)
```

#### Dashboard & Analytics
```
GET    /dashboard/               - Dashboard summary
GET    /analytics/summary/       - Spending summary
GET    /analytics/trends/        - Spending trends (charts)
GET    /analytics/by-category/   - Breakdown by category
GET    /analytics/monthly-report/ - Monthly report
```

#### Recurring Transactions
```
GET    /recurring/               - List recurring transactions
POST   /recurring/               - Create recurring transaction
PUT    /recurring/<id>/          - Update recurring transaction
DELETE /recurring/<id>/          - Delete recurring transaction
POST   /recurring/<id>/process/  - Manually process recurring
```

#### User Profile
```
GET    /profile/                 - Get user profile
PUT    /profile/                 - Update user profile
GET    /profile/financial/       - Get financial profile
PUT    /profile/financial/       - Update financial profile (budget, currency)
POST   /profile/password-change/ - Change password
```

#### Admin (Django Admin)
```
/admin/                          - Django admin interface
/admin/auth/user/                - User management
/admin/expenses/expense/         - Expense management
/admin/expenses/financialprofile/ - Financial profiles
```

### Request/Response Format

#### Content Types
- **Request:** application/x-www-form-urlencoded (forms), application/json (API)
- **Response:** text/html (templates), application/json (API endpoints)

#### Status Codes
```
200 OK              - Successful GET/PUT
201 Created         - Successful POST (resource created)
204 No Content      - Successful DELETE
400 Bad Request     - Validation error
401 Unauthorized    - Authentication required
403 Forbidden       - User lacks permission
404 Not Found       - Resource not found
405 Method Not Allowed - HTTP method not supported
500 Internal Server Error - Server error
503 Service Unavailable - Maintenance/overload
```

#### Error Response Format
```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    "field_name": ["Error for this field"]
  }
}
```

#### Pagination
```
GET /expenses/?page=1&limit=25

Response Headers:
  X-Total-Count: 150
  X-Page-Count: 6
  X-Current-Page: 1
  
Response Body:
{
  "count": 150,
  "next": "/expenses/?page=2",
  "previous": null,
  "results": [...]
}
```

### Authentication & Authorization

#### Session-Based Authentication (Default)
- Django session framework with secure cookies
- CSRF token required for POST/PUT/DELETE requests
- Session timeout: Configurable (default 2 weeks)
- Secure cookie flags: HttpOnly, Secure (HTTPS only), SameSite=Strict

#### Authorization Levels
```
Anonymous User:
  ✗ Cannot access any expense data
  ✓ Can access login/signup pages

Authenticated User:
  ✓ Can view own expenses
  ✓ Can manage own expenses
  ✗ Cannot view other users' data
  ✗ Cannot access admin interface

Staff User:
  ✓ Can access Django admin panel
  ✓ Can manage all users' data
  ✓ Can view system metrics

Superuser:
  ✓ Full system access
  ✓ Can modify users and permissions
  ✓ Can access all data
```

---

## Frontend Requirements

### HTML Templates

#### Base Template (base.html)
- Django static tag for CSS/JS loading
- Navigation bar with user menu
- CSRF token in all forms
- Responsive meta tags
- Error/success message display
- Footer with links

#### Expense Management Templates
```
expense_list.html
  ├── Table of user's expenses
  ├── Filters: date range, category, amount range
  ├── Pagination controls
  ├── Delete confirmation
  └── Create/Edit action buttons

expense_form.html
  ├── Form fields:
  │   ├── amount (number, required)
  │   ├── date (date picker, required)
  │   ├── category (dropdown)
  │   ├── description (textarea)
  │   └── tags (text input)
  ├── Django form validation
  └── Submit/Cancel buttons

expense_confirm_delete.html
  ├── Warning message
  └── Delete/Cancel buttons
```

#### Dashboard & Analysis Templates
```
dashboard.html
  ├── Current month summary
  ├── Spending by category (pie chart)
  ├── Recent transactions (table)
  ├── Budget vs actual (progress bar)
  └── Quick action buttons

analysis.html
  ├── Date range selector
  ├── Category breakdown (bar chart)
  ├── Trend analysis (line chart)
  ├── Export options (CSV/PDF)
  └── Filter controls

recurring_transactions.html
  ├── List of recurring expenses
  ├── Next due date
  ├── Frequency information
  └── Edit/Delete actions

report_monthly.html
  ├── Month selector
  ├── PDF download option
  ├── Category summary table
  ├── Total spending
  └── Comparison to previous month
```

#### User Management Templates
```
login.html
  ├── Username/email field
  ├── Password field
  ├── Remember me checkbox
  ├── Forgot password link
  └── Sign up link

signup.html
  ├── Username field
  ├── Email field
  ├── Password field (with strength indicator)
  ├── Password confirmation
  ├── Terms & conditions checkbox
  └── Sign up button

profile.html
  ├── User information form
  ├── Email change option
  ├── Password change link
  └── Delete account (admin approval)
```

### Frontend Validation
```javascript
// Client-side validation (for UX, not security)
- Amount: must be > 0, max 10 digits
- Date: must be valid date, not future
- Category: required, must be valid option
- Email: must be valid email format
- Form CSRF token validation

// Server-side validation (security)
- All inputs validated on server
- Type checking and range validation
- Authorization checks before any modification
```

### CSS & Styling
```
static/css/styles.css:
  ├── Global styles (fonts, colors)
  ├── Layout & grid system
  ├── Component styles
  │   ├── Buttons
  │   ├── Forms
  │   ├── Tables
  │   ├── Navigation
  │   └── Cards
  ├── Responsive breakpoints (mobile, tablet, desktop)
  └── Print styles (for PDF export)

Bootstrap Framework (Optional):
  - Version 5.x recommended
  - Responsive grid system
  - Pre-built components
  - Utility classes
```

### Accessibility Requirements
- ✓ WCAG 2.1 AA compliance target
- ✓ Semantic HTML5 elements
- ✓ ARIA labels for screen readers
- ✓ Color contrast ratios >= 4.5:1
- ✓ Keyboard navigation support
- ✓ Form labels associated with inputs
- ✓ Alt text for images

---

## Development Standards

### Code Style & Formatting

#### Python (Django)
```
Style Guide: PEP 8 with Django conventions
Line Length: 100 characters (configurable)
Indentation: 4 spaces (no tabs)
Naming Conventions:
  - Classes: PascalCase
  - Functions/Methods: snake_case
  - Constants: UPPER_SNAKE_CASE
  - Private members: _leading_underscore
  
Tools:
  - black: Code formatter (enforced in CI/CD)
  - flake8: Linting
  - isort: Import sorting
```

#### Example Django Model
```python
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal


class Expense(models.Model):
    """User expense record."""
    
    CATEGORY_CHOICES = [
        ('food', 'Food'),
        ('transport', 'Transport'),
        ('entertainment', 'Entertainment'),
        ('utilities', 'Utilities'),
        ('other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    date = models.DateField()
    description = models.TextField(blank=True)
    is_recurring = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(
                fields=['user', '-date'],
                name='idx_expense_user_date'
            ),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.amount} ({self.date})"
    
    def is_past_date(self):
        """Check if expense is for past date."""
        from datetime import date
        return self.date < date.today()
```

#### Views Best Practices
```python
# Use class-based views where appropriate
from django.views import View
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.http import JsonResponse


class ExpenseListView(LoginRequiredMixin, ListView):
    """Display user's expense list."""
    
    model = Expense
    template_name = 'expenses/expense_list.html'
    context_object_name = 'expenses'
    paginate_by = 25
    
    def get_queryset(self):
        """Filter expenses to current user."""
        return Expense.objects.filter(
            user=self.request.user
        ).order_by('-date')
    
    def get_context_data(self, **kwargs):
        """Add filters to context."""
        context = super().get_context_data(**kwargs)
        context['categories'] = Expense.CATEGORY_CHOICES
        return context


class ExpenseDeleteView(LoginRequiredMixin, View):
    """Delete expense with soft-delete."""
    
    def post(self, request, pk):
        """Mark expense as deleted."""
        expense = get_object_or_404(
            Expense,
            pk=pk,
            user=request.user
        )
        expense.deleted = True
        expense.save()
        return JsonResponse({'status': 'deleted'})
```

### File Organization
```
Project Root:
├── expense_tracker/          # Django project package
│   ├── __init__.py
│   ├── settings.py           # Main settings (1500+ lines)
│   ├── urls.py               # Root URL config
│   ├── wsgi.py               # WSGI config
│   └── asgi.py               # ASGI config
│
├── expenses/                 # Main Django app
│   ├── migrations/           # Database migrations
│   ├── templates/            # App templates
│   ├── static/               # App static files
│   ├── __init__.py
│   ├── admin.py              # Admin customization
│   ├── apps.py               # App config
│   ├── forms.py              # Form definitions
│   ├── models.py             # Database models
│   ├── tests.py              # Unit tests
│   ├── urls.py               # App URL routing
│   └── views.py              # View logic
│
├── templates/                # Project-level templates
├── static/                   # Project-level static files
├── staticfiles/              # Collected static files (generated)
│
├── Dockerfile                # Production image
├── docker-compose.yml        # Local dev stack
├── docker-compose.prod.yml   # Production stack
├── manage.py                 # Django CLI
├── requirements.txt          # Python dependencies
├── .gitignore
├── README.md
└── [config files]
```

### Naming Conventions
```
Models: Singular, PascalCase
  - User, Expense, FinancialProfile, RecurringTransaction

Views: PascalCase with 'View' suffix
  - ExpenseListView, ExpenseDetailView, ExpenseCreateView

URLs: snake_case, descriptive
  - /expenses/
  - /expenses/<id>/
  - /analytics/by-category/
  - /recurring/process/

Templates: snake_case, match model name
  - expense_list.html
  - expense_form.html
  - expense_confirm_delete.html

CSS Classes: kebab-case
  - .expense-item
  - .category-filter
  - .btn-submit

Database Columns: snake_case (automatic in Django ORM)
  - created_at, updated_at, is_recurring
```

---

## Testing Requirements

### Test Coverage Targets
- **Minimum Coverage:** 80% (enforced in CI/CD)
- **Target Coverage:** 90%+
- **Critical Paths:** 100% (authentication, data modification)

### Testing Framework
```
pytest with pytest-django plugin
Coverage: coverage.py
Mocking: unittest.mock
Fixtures: factory-boy

Requirements (add to dev dependencies):
  pytest==7.4.0
  pytest-django==4.5.0
  pytest-cov==4.1.0
  factory-boy==3.3.0
  faker==19.0.0
```

### Test Categories

#### Unit Tests
```python
# tests/test_models.py
import pytest
from decimal import Decimal
from datetime import date
from faker import Faker
from factory import DjangoModelFactory
from expenses.models import Expense, User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Faker('email')


class ExpenseFactory(DjangoModelFactory):
    class Meta:
        model = Expense
    
    user = factory.SubFactory(UserFactory)
    amount = Decimal('50.00')
    date = date.today()
    category = 'food'


@pytest.mark.django_db
class TestExpenseModel:
    """Test Expense model logic."""
    
    def test_expense_creation(self):
        """Test expense can be created."""
        expense = ExpenseFactory(amount=Decimal('25.50'))
        assert expense.amount == Decimal('25.50')
        assert expense.user.username is not None
    
    def test_expense_amount_validation(self):
        """Test expense amount must be positive."""
        with pytest.raises(ValidationError):
            expense = ExpenseFactory(amount=Decimal('-10.00'))
            expense.full_clean()
    
    def test_expense_str_representation(self):
        """Test expense string representation."""
        expense = ExpenseFactory(amount=Decimal('100.00'))
        assert 'user' in str(expense).lower()
        assert '100' in str(expense)
```

#### Integration Tests
```python
# tests/test_views.py
import pytest
from django.urls import reverse
from django.contrib.auth.models import User


@pytest.mark.django_db
class TestExpenseListView:
    """Test expense list view."""
    
    def test_view_requires_login(self, client):
        """Test unauthenticated access redirects."""
        response = client.get(reverse('expense-list'))
        assert response.status_code == 302  # Redirect to login
    
    def test_view_shows_only_user_expenses(self, client):
        """Test view filters expenses to current user."""
        user1 = UserFactory()
        user2 = UserFactory()
        ExpenseFactory(user=user1, amount=Decimal('50.00'))
        ExpenseFactory(user=user2, amount=Decimal('100.00'))
        
        client.login(username=user1.username, password='password')
        response = client.get(reverse('expense-list'))
        
        assert len(response.context['expenses']) == 1
        assert response.context['expenses'][0].user == user1
    
    def test_view_paginates_results(self, client):
        """Test pagination works correctly."""
        user = UserFactory()
        for i in range(30):
            ExpenseFactory(user=user)
        
        client.login(username=user.username, password='password')
        response = client.get(reverse('expense-list'))
        
        assert len(response.context['expenses']) == 25
        assert response.context['page_obj'].number == 1
        assert response.context['is_paginated'] is True
```

#### Functional/End-to-End Tests
```python
# tests/test_user_flows.py
import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestUserWorkflows:
    """Test complete user workflows."""
    
    def test_user_can_create_and_view_expense(self, client):
        """Test user can create expense and view it."""
        user = UserFactory()
        client.login(username=user.username, password='password')
        
        # Create expense
        response = client.post(
            reverse('expense-create'),
            {
                'amount': '50.00',
                'date': '2026-08-18',
                'category': 'food',
                'description': 'Lunch'
            }
        )
        assert response.status_code == 302  # Redirect after success
        
        # View expense
        response = client.get(reverse('expense-list'))
        assert Expense.objects.filter(user=user).count() == 1
```

### Test Execution
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=expenses --cov-report=html

# Run specific test
pytest tests/test_models.py::TestExpenseModel::test_expense_creation

# Run tests matching pattern
pytest -k "test_expense"

# Run tests in verbose mode
pytest -v

# CI/CD pipeline requirement
pytest --cov=expenses --cov-report=term-missing --cov-fail-under=80
```

---

## Code Quality

### Linting & Static Analysis

#### flake8 Configuration
```ini
# .flake8
[flake8]
max-line-length = 100
exclude = .git,__pycache__,venv,migrations
ignore = E203,W503

# E203: whitespace before ':'
# W503: line break before binary operator
```

#### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
  
  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
  
  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort
```

### Code Review Standards

#### Minimum Review Requirements
- ✓ At least one approval from senior developer
- ✓ All tests passing (100% of test suite)
- ✓ Coverage maintained or improved
- ✓ No new linting warnings
- ✓ Security review for auth/database changes
- ✓ Documentation updated

#### Review Checklist
```
Code Style:
  ☐ Follows PEP 8
  ☐ Consistent naming
  ☐ No commented-out code
  ☐ Docstrings for public methods

Functionality:
  ☐ Requirements met
  ☐ Edge cases handled
  ☐ Error handling appropriate
  ☐ Logging adequate

Testing:
  ☐ Tests included
  ☐ All tests pass
  ☐ Coverage maintained
  ☐ Edge cases tested

Security:
  ☐ No hardcoded secrets
  ☐ Input validation
  ☐ CSRF/XSS protection
  ☐ SQL injection prevention (ORM used)
  ☐ Authentication/authorization checked

Performance:
  ☐ No N+1 queries
  ☐ Appropriate caching
  ☐ No large loops
  ☐ Database migrations efficient

Documentation:
  ☐ Code comments for complex logic
  ☐ Docstrings present
  ☐ README updated if needed
  ☐ API documentation updated
```

---

## Integration & Third-Party Services

### External Service Requirements

#### Email Service (Optional)
- **Purpose:** Password reset, notifications
- **Recommended:** SendGrid, Mailgun, AWS SES
- **Configuration:** Via Django settings
- **Fallback:** Console email backend for development

#### File Storage (Future)
- **Purpose:** User uploads, invoice storage
- **Recommended:** AWS S3, Azure Blob Storage
- **Django Package:** django-storages
- **Local Alternative:** File system storage

#### Reporting & PDF Generation
- **Library:** reportlab
- **Purpose:** Generate expense reports, invoices
- **Formats:** PDF, CSV export
- **No external API required (local processing)

#### Data Visualization
- **Library:** matplotlib
- **Purpose:** Charts and graphs in reports
- **Integration:** Server-side rendering to images
- **Alternative:** JavaScript charting library (future)

### External API Integrations

#### Currency Exchange (Optional)
- **Purpose:** Multi-currency support
- **API Options:**
  - Open Exchange Rates
  - Fixer.io
  - CurrencyAPI
- **Caching:** 24-hour cache to minimize API calls
- **Fallback:** Static rates if API unavailable

#### Banking Integration (Future)
- **Purpose:** Automatic transaction importing
- **API Options:**
  - Plaid
  - Yodlee
  - Open Banking APIs
- **Security:** Separate authentication layer

---

## Performance & Scalability

### Performance Targets
| Metric | Target | Measurement |
|--------|--------|-------------|
| Page Load | < 2 sec | 95th percentile |
| API Response | < 500ms | Average |
| Database Query | < 100ms | Average |
| Concurrent Users | 100+ | Simultaneous |
| Uptime | 99.5% | Monthly SLA |

### Optimization Strategies

#### Database Optimization
```python
# Query Optimization
# ❌ BAD: N+1 query problem
expenses = Expense.objects.filter(user=request.user)
for expense in expenses:
    print(expense.user.username)  # Extra query per expense!

# ✅ GOOD: Use select_related
expenses = Expense.objects.filter(
    user=request.user
).select_related('user')

# ✅ GOOD: Use prefetch_related for reverse FK
from django.db.models import Prefetch
users = User.objects.prefetch_related(
    Prefetch('expense_set', Expense.objects.all())
)
```

#### Caching Strategy
```python
# Django cache framework
from django.views.decorators.cache import cache_page

@cache_page(60 * 5)  # Cache for 5 minutes
def expense_summary(request):
    """Expensive calculation cached."""
    ...

# Low-level cache
from django.core.cache import cache

category_summary = cache.get('category_summary')
if category_summary is None:
    category_summary = Expense.objects.values('category').annotate(...)
    cache.set('category_summary', category_summary, 60 * 60)  # 1 hour
```

#### Static File Optimization
- WhiteNoise middleware for efficient serving
- Gzip compression enabled in Nginx
- Browser caching: 30-day expiry headers
- Minified CSS/JS in production

### Scalability Considerations

#### Horizontal Scaling
```
Current: Single container deployment
Future: Multiple Gunicorn containers

docker-compose.prod.yml changes:
  services:
    web:
      deploy:
        replicas: 3  # Run 3 instances
      
    # Add load balancer configuration
    # Sticky sessions for authenticated requests
```

#### Vertical Scaling
- Increase CPU/memory allocations
- Tune Gunicorn worker count
- Optimize database queries
- Enable database connection pooling

#### Database Scaling (Future)
```
Current: Single PostgreSQL container
Future: Master-slave replication / Read replicas

Implementation:
  - Master (write) and read replicas (read-only)
  - Route SELECT queries to replicas
  - Route INSERT/UPDATE/DELETE to master
  - Replication lag monitoring
```

---

## Security Technical Specs

### Authentication Implementation

#### Session-Based Authentication
```python
# settings.py
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_COOKIE_SECURE = True   # HTTPS only
SESSION_COOKIE_HTTPONLY = True # No JavaScript access
SESSION_COOKIE_SAMESITE = 'Strict'
```

#### Password Requirements
```python
# In forms.py
from django.contrib.auth.password_validation import (
    validate_password,
    MinimumLengthValidator,
    CommonPasswordValidator,
    NumericPasswordValidator
)

# Minimum 8 characters
# Cannot be entirely numeric
# Cannot be common password
# Should include uppercase and special characters
```

### CSRF Protection
```html
<!-- All forms must include CSRF token -->
<form method="post">
  {% csrf_token %}
  <!-- form fields -->
</form>

<!-- AJAX requests -->
<script>
  const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
  fetch('/api/endpoint/', {
    method: 'POST',
    headers: {
      'X-CSRFToken': csrftoken,
      'Content-Type': 'application/json'
    }
  });
</script>
```

### SQL Injection Prevention
```python
# ✅ SAFE: Django ORM parameterizes queries
Expense.objects.filter(user=user, date__gte=start_date)

# ❌ UNSAFE: String interpolation (NEVER do this)
# Expense.objects.raw(f"SELECT * FROM expenses WHERE user_id = {user.id}")

# ✅ SAFE: If raw SQL needed, use parameters
Expense.objects.raw(
    "SELECT * FROM expenses WHERE user_id = %s",
    [user.id]
)
```

### XSS Prevention
```html
<!-- Django template auto-escapes by default -->
<p>{{ user.bio }}</p>  <!-- Safe: <script> tags rendered as text -->

<!-- Only use |safe for trusted content -->
<div>{{ trusted_html|safe }}</div>

<!-- Manual escaping if needed -->
from django.utils.html import escape
safe_text = escape(user_input)
```

### Encryption & Hashing
```python
# Passwords: PBKDF2 (Django default)
from django.contrib.auth.models import User
user = User.objects.create_user(
    username='username',
    password='plaintext'  # Automatically hashed
)

# Verify password
user.check_password('plaintext')  # True if matches

# Sensitive data: Use encryption
from cryptography.fernet import Fernet
cipher = Fernet(key)
encrypted = cipher.encrypt(b'sensitive_data')
decrypted = cipher.decrypt(encrypted)
```

### Security Headers
```python
# settings.py
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

### Secrets Management
```
Environment Variables (Recommended):
  - DJANGO_SECRET_KEY
  - DATABASE_URL
  - DB_PASSWORD
  
Source:
  - .env.production file (permissions: 600)
  - Never commit to git
  - Cloud provider secrets manager (production)

Rotation:
  - SECRET_KEY: Never (would invalidate all sessions)
  - DB_PASSWORD: Every 90 days (planned downtime)
```

---

## Development Workflow

### Local Development Setup
```bash
# 1. Clone repository
git clone <repository-url>
cd spend-shelf

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Configure local environment
cp .env.example .env
# Edit .env with local settings

# 5. Run migrations
python manage.py migrate

# 6. Create superuser
python manage.py createsuperuser

# 7. Collect static files (development)
python manage.py collectstatic --noinput

# 8. Run development server
python manage.py runserver

# 9. Access application
# Application: http://localhost:8000
# Admin: http://localhost:8000/admin
```

### Git Workflow
```
Branch Strategy: Git Flow
  
main (production-ready)
  ├── hotfix/* (emergency fixes)
  │
develop (staging)
  ├── feature/* (new features)
  ├── bugfix/* (bug fixes)
  └── test/* (experimental)

Naming Convention:
  feature/add-recurring-expenses
  bugfix/fix-date-validation
  hotfix/security-patch
  
Commit Messages:
  [FEATURE] Add recurring expense support
  [BUGFIX] Fix date validation edge case
  [SECURITY] Prevent SQL injection in search
  [DOCS] Update API documentation
  [TEST] Add unit tests for expense model
  [PERF] Optimize expense list query
  [CHORE] Update dependencies
```

### Code Deployment Pipeline
```
Local Development
  ↓
Feature Branch
  ↓
Code Review (GitHub)
  ↓
Automated Tests (GitHub Actions)
  ├─ Unit tests (pytest)
  ├─ Linting (flake8)
  ├─ Coverage check (80%+)
  └─ Security scan
  ↓
Merge to develop
  ↓
Staging Deployment
  ├─ Run full test suite
  ├─ Manual QA
  └─ Performance testing
  ↓
Release Tag
  ↓
Production Deployment
  ├─ Blue-green deployment
  ├─ Health checks
  └─ Rollback capability
```

### Django Management Commands (Development)
```bash
# Database
python manage.py migrate                # Apply migrations
python manage.py makemigrations         # Create migration files
python manage.py sqlmigrate app_name 0001  # Preview SQL
python manage.py dbshell                # PostgreSQL shell
python manage.py dumpdata > backup.json # Export data
python manage.py loaddata backup.json   # Import data

# Development
python manage.py runserver              # Start dev server
python manage.py createsuperuser        # Create admin user
python manage.py changepassword username # Change password
python manage.py collectstatic          # Collect static files
python manage.py test                   # Run tests (Django runner)
python manage.py shell                  # Python shell with Django context

# Debugging
python manage.py check                  # System check
python manage.py showmigrations         # Display migration status
python manage.py sqlsequencereset       # Reset sequences
```

---

## Appendix A: Technology Decision Rationale

### Why Django?
- Batteries-included framework (ORM, admin, auth)
- Built-in security features (CSRF, SQL injection prevention)
- Large ecosystem and community
- Suitable for rapid development
- Scales well with proper architecture

### Why PostgreSQL?
- Superior to SQLite for production
- ACID compliance and data integrity
- Advanced query capabilities
- Full-text search support (future)
- Better concurrent access handling

### Why Docker?
- Environment consistency (dev ≈ production)
- Easy deployment and scaling
- Container orchestration ready
- Simplified dependency management
- Industry standard

### Why Gunicorn?
- Lightweight WSGI server
- Easy to configure and deploy
- Multiple worker support
- Active maintenance
- Production-proven

### Why Nginx?
- High-performance reverse proxy
- Efficient static file serving
- Built-in SSL/TLS support
- Low resource consumption
- Easy configuration

---


