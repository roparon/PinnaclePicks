from urllib.parse import urlparse, urljoin

from flask import (
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)

from ..models import db, User
from . import auth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_safe_redirect_url(target):
    """
    Prevent open-redirect vulnerabilities.

    Only allow redirects back to this same application.
    """

    if not target:
        return False

    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))

    return (
        test_url.scheme in {"http", "https"}
        and ref_url.netloc == test_url.netloc
    )


def get_safe_next_url():
    """
    Return a safe next URL or None.
    """

    target = request.args.get("next")

    if target and is_safe_redirect_url(target):
        return target

    return None


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    next_url = request.args.get("next", "")

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        if not identifier or not password:
            flash("Please enter your username/email and password.", "error")
            return render_template(
                "login.html",
                next_url=next_url,
            )

        # Allow login using either username or email.
        user = User.query.filter(
            db.or_(
                User.username.ilike(identifier),
                User.email.ilike(identifier),
            )
        ).first()

        if user is None or not user.check_password(password):
            flash("Invalid username/email or password.", "error")
            return render_template(
                "login.html",
                next_url=next_url,
            )

        login_user(user)

        flash(f"Welcome back, {user.username}!", "success")

        if next_url and is_safe_redirect_url(next_url):
            return redirect(next_url)

        return redirect(url_for("main.index"))

    return render_template(
        "login.html",
        next_url=next_url,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@auth.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Basic validation.
        if not username:
            flash("Please enter a username.", "error")
            return render_template("register.html")

        if len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
            return render_template("register.html")

        if len(username) > 80:
            flash("Username is too long.", "error")
            return render_template("register.html")

        if not email or "@" not in email:
            flash("Please enter a valid email address.", "error")
            return render_template("register.html")

        if len(email) > 255:
            flash("Email address is too long.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        # Check for existing username.
        existing_username = User.query.filter(
            db.func.lower(User.username) == username.lower()
        ).first()

        if existing_username:
            flash("That username is already registered.", "error")
            return render_template("register.html")

        # Check for existing email.
        existing_email = User.query.filter(
            db.func.lower(User.email) == email.lower()
        ).first()

        if existing_email:
            flash("That email address is already registered.", "error")
            return render_template("register.html")

        # Create the user.
        user = User(
            username=username,
            email=email,
            subscription_tier="free",
            is_admin=False,
        )

        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()

        except Exception:
            db.session.rollback()
            flash(
                "Registration could not be completed. Please try again.",
                "error",
            )
            return render_template("register.html")

        login_user(user)

        flash(
            "Your account has been created successfully.",
            "success",
        )

        return redirect(url_for("main.index"))

    return render_template("register.html")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@auth.route("/logout")
@login_required
def logout():
    logout_user()

    flash("You have been logged out.", "success")

    return redirect(url_for("main.index"))


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

@auth.route("/account")
@login_required
def account():
    return render_template(
        "account.html",
        user=current_user,
    )