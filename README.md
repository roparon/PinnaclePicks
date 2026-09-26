# PinnaclePicks

### Educational Sports Analytics & Historical Match Data Platform

PinnaclePicks is a modern, mobile-first sports analytics platform built with **Python and Flask**. It is designed to organize historical match data, upcoming fixtures, prediction selections, accumulator combinations, match outcomes, subscription-based premium content, and administrator-managed sports data in one professional interface.

The platform focuses on presenting sports data in a clear and structured way for **educational, analytical, and historical purposes**.

---

## ✨ Features

### 🏟️ Match Data Management

PinnaclePicks provides a structured system for managing sports matches and their outcomes.

* Upcoming matches
* Historical match results
* Home and away teams
* League information
* Kickoff dates and times
* Market types
* Match selections
* Decimal odds
* Final scores
* Won / Lost / Void outcomes
* Automatic archival of completed fixtures
* Match status tracking

---

### 🎯 Prediction & Selection Data

Each match can contain structured prediction information, including:

* 1X2
* Over / Under
* GG / NG
* Custom selections
* Decimal odds
* Prediction outcome
* Historical performance tracking

The system separates match information from presentation, making it easier to expand the platform with additional markets and analytical features in the future.

---

### 🎟️ Accumulator / Combo Tickets

PinnaclePicks supports multiple-match combinations through its combo ticket system.

Each combo can contain:

* Multiple matches
* Combined odds
* Ticket title
* Outcome status
* Required subscription tier
* Creation and update timestamps

Supported outcomes include:

* Pending
* Won
* Lost
* Void

Premium combinations can be restricted to users with an active subscription.

---

### 💎 Subscription System

PinnaclePicks includes a subscription architecture designed to support premium sports content.

Current subscription tiers include:

* Free
* Weekly
* Monthly

The application tracks:

* Subscription tier
* Subscription expiration
* Active subscription status
* Premium access
* Expired subscriptions

Premium routes are protected so users without an active premium subscription cannot access restricted content.

> Payment processing can be integrated separately when the platform is ready for production payments.

---

### 👤 User Accounts

Users can create and manage their own accounts.

Authentication includes:

* Registration
* Login
* Logout
* Password hashing
* Account page
* Subscription status
* Premium access control

Passwords are never stored in plain text. Passwords are securely hashed using Werkzeug's password hashing utilities.

---

### 🔐 Administrator System

PinnaclePicks includes protected administrator functionality.

Administrators can manage platform content without exposing administrative controls to normal users.

Current administrative capabilities include:

* Admin dashboard
* Match creation
* Match editing
* Match deletion
* Match result management
* Score management
* Match status management
* Prediction outcome management
* Media proof uploads
* Dashboard statistics

Administrative pages are protected using authentication and administrator authorization.

---

### 📊 Admin Dashboard

The administrator dashboard provides a central management interface for the platform.

Dashboard statistics include:

* Total matches
* Upcoming matches
* Finished matches
* Won selections
* Lost selections
* Void selections

Administrators can quickly review recent matches and manage their status from the dashboard.

---

### 🖼️ Media Proofs

The platform supports administrator-managed image uploads.

Media proofs can be used to publish supporting visual material associated with platform content.

The upload system includes:

* Secure filenames
* Image extension validation
* File size limits
* Dedicated upload storage
* Administrator-only access

---

## 📱 Mobile-First Design

PinnaclePicks is designed with mobile devices as a primary target.

The interface emphasizes:

* Responsive layouts
* Touch-friendly controls
* Compact information cards
* Mobile navigation
* Minimal unnecessary JavaScript
* Lightweight CSS
* Responsive tables and cards
* Small-screen usability
* Clean typography
* Fast page rendering

The interface is designed to remain usable on small screens without requiring users to zoom or horizontally scroll through the main application.

---

## ⚡ Performance Philosophy

PinnaclePicks intentionally avoids unnecessary heavy frontend frameworks and excessive client-side processing.

The application primarily uses:

* Server-rendered Jinja templates
* Flask
* Bootstrap
* Lightweight CSS
* Minimal JavaScript

This keeps the platform relatively lightweight while allowing the interface to remain modern and responsive.

---

# 🏗️ Technology Stack

## Backend

* **Python 3**
* **Flask**
* **Flask-SQLAlchemy**
* **Flask-Migrate**
* **Flask-Login**
* **Werkzeug**

## Frontend

* **HTML5**
* **CSS3**
* **Jinja2**
* **Bootstrap 5**

## Database

The application is designed to support:

* SQLite for local development
* PostgreSQL for production deployments

Database migrations are managed using **Alembic through Flask-Migrate**.

---

# 📂 Project Structure

```text
PinnaclePicks/
│
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── routes.py
│   │
│   ├── auth/
│   │   ├── __init__.py
│   │   └── routes.py
│   │
│   └── templates/
│       ├── base.html
│       ├── index.html
│       ├── login.html
│       ├── register.html
│       ├── account.html
│       ├── subscriptions.html
│       ├── premium_combo.html
│       │
│       └── admin/
│           ├── dashboard.html
│           └── match_form.html
│
├── migrations/
│
├── static/
│   └── uploads/
│       └── proofs/
│
├── instance/
│
├── config.py
├── requirements.txt
├── run.py
└── README.md
```

---

# 🗃️ Database Models

The current application includes the following primary models.

### User

Stores registered user accounts and subscription information.

Important fields include:

* `username`
* `email`
* `password_hash`
* `subscription_tier`
* `subscription_expires_at`
* `is_admin`
* `created_at`
* `updated_at`

---

### Match

Stores individual sports fixtures and prediction information.

Important fields include:

* `home_team`
* `away_team`
* `league`
* `kickoff_time`
* `market_type`
* `pick_selection`
* `odds`
* `status`
* `home_score`
* `away_score`
* `is_win`

---

### ComboTicket

Represents a multi-match combination.

Important fields include:

* `title`
* `total_odds`
* `outcome_status`
* `required_tier`
* `created_at`
* `updated_at`

A combo ticket can contain multiple matches through the `combo_matches` association table.

---

### MediaProof

Stores administrator-uploaded supporting images.

Fields include:

* `image_path`
* `caption`
* `uploaded_at`

---

# 🔒 Security

PinnaclePicks includes several basic security measures.

### Password Security

User passwords are hashed before being stored in the database.

Plain-text passwords are not stored.

### Authentication

Protected pages require users to be authenticated.

### Authorization

Administrative functionality requires both:

1. An authenticated user account
2. Administrator privileges

### File Upload Protection

Uploaded images are validated and stored using secure filenames.

### Environment Configuration

Sensitive configuration such as the application's secret key and production database connection should be provided through environment variables rather than committed to source control.

---

# 🚀 Local Development

## 1. Clone the repository

```bash
git clone YOUR_REPOSITORY_URL
cd PinnaclePicks
```

---

## 2. Create a virtual environment

Linux/macOS:

```bash
python3 -m venv .Pinna
source .Pinna/bin/activate
```

Windows:

```powershell
python -m venv .Pinna
.Pinna\Scripts\activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure environment variables

Create a `.env` file for local development if your environment loads it, or export the variables directly.

Example:

```env
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=sqlite:///pinnaclepicks.db
```

For production, use a secure PostgreSQL connection string instead of SQLite.

> Never commit passwords, database credentials, API keys, or production secrets to Git.

---

# 🗄️ Database Setup

Initialize the database using the existing migration system.

```bash
flask --app "app:create_app" db upgrade
```

To inspect migration status:

```bash
flask --app "app:create_app" db current
```

To view migration heads:

```bash
flask --app "app:create_app" db heads
```

---

# 👑 Creating an Administrator

Administrator privileges should be granted to an existing trusted account rather than exposed through a public registration option.

Using the Flask shell:

```bash
flask --app "app:create_app" shell
```

Then:

```python
from app.models import db, User

user = User.query.filter_by(username="YOUR_USERNAME").first()
user.is_admin = True
db.session.commit()
```

Verify:

```python
user.is_admin
```

Expected:

```text
True
```

Exit:

```python
exit()
```

---

# ▶️ Running the Application

Start the development server:

```bash
flask --app "app:create_app" run
```

Or, if the project uses `run.py`:

```bash
python run.py
```

The application will normally be available at:

```text
http://127.0.0.1:5000
```

---

# 🧭 Main Application Pages

| Page                       | Purpose                      |
| -------------------------- | ---------------------------- |
| `/`                        | Main PinnaclePicks dashboard |
| `/login`                   | User login                   |
| `/register`                | Account registration         |
| `/account`                 | User account                 |
| `/subscribe`               | Subscription information     |
| `/combos/<id>`             | Combo ticket                 |
| `/admin`                   | Administrator dashboard      |
| `/admin/matches/create`    | Create a match               |
| `/admin/matches/<id>/edit` | Edit a match                 |
| `/admin/upload-proof`      | Upload media proof           |

Some pages require authentication or administrator privileges.

---

# 🔄 Match Lifecycle

A typical match follows this lifecycle:

```text
Create Match
     │
     ▼
  Upcoming
     │
     │ Match kickoff passes
     ▼
  Finished
     │
     ├── Won
     ├── Lost
     └── Void
```

The application can archive expired matches when their kickoff time has passed and the required result information is available.

---

# 🧪 Development Workflow

When modifying the application, the recommended workflow is:

```bash
# Activate environment
source .Pinna/bin/activate

# Run migrations
flask --app "app:create_app" db upgrade

# Start application
flask --app "app:create_app" run
```

Before committing changes:

```bash
git status
git diff
```

Then commit:

```bash
git add .
git commit -m "Describe the change"
git push
```

---

# 🛡️ Production Checklist

Before deploying PinnaclePicks to production, review the following:

* [ ] Set a strong production `SECRET_KEY`
* [ ] Use PostgreSQL or another production-grade database
* [ ] Do not commit `.env` files
* [ ] Do not commit database credentials
* [ ] Enable HTTPS
* [ ] Configure secure cookies
* [ ] Review file upload permissions
* [ ] Add CSRF protection to administrative forms
* [ ] Configure production logging
* [ ] Configure database backups
* [ ] Review administrator accounts
* [ ] Disable Flask debug mode
* [ ] Configure a production WSGI server
* [ ] Configure appropriate upload storage
* [ ] Test database migrations before deployment

---

# 🔮 Planned Improvements

PinnaclePicks is designed to grow into a broader sports analytics platform.

Potential future improvements include:

* Advanced historical statistics
* Team performance analytics
* League statistics
* Head-to-head analysis
* More prediction markets
* Improved result automation
* Subscription payment integration
* User notification system
* Advanced administrator controls
* Search and filtering
* Pagination
* Analytics dashboards
* API integrations
* Automated fixture imports
* Automated result updates
* Improved reporting
* PostgreSQL production deployment
* Cloud media storage

---

# ⚠️ Educational & Informational Purpose

PinnaclePicks is intended for **sports data organization, historical analysis, and educational purposes**.

Predictions, selections, odds, statistics, historical results, and analytical information are provided as data and informational content. They should not be interpreted as guarantees of future results.

Sports outcomes are inherently uncertain.

Users are responsible for complying with the laws, regulations, and applicable rules in their jurisdiction.

---

# 🤝 Contributing

Contributions and improvements are welcome.

A typical contribution workflow is:

1. Fork the repository.
2. Create a feature branch.
3. Make your changes.
4. Test the application.
5. Review database migrations if models changed.
6. Commit your changes.
7. Open a pull request.

Example:

```bash
git checkout -b feature/improved-match-analytics
```

---

# 📄 License

Add the project's chosen license here.

For example:

```text
MIT License
```

If a different license is selected, replace the above with the applicable license and include the complete license text in a `LICENSE` file.

---

# 👨‍💻 Project

**PinnaclePicks**

Educational Sports Analytics & Historical Match Data Platform

Built with:

**Python • Flask • SQLAlchemy • Jinja2 • Bootstrap • SQLite/PostgreSQL**

---

> **PinnaclePicks — structured sports data, historical insights, and analytical tools in one platform.**
