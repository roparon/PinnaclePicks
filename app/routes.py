# app/routes.py

import os
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import (
    current_user,
    login_required,
)

from werkzeug.utils import secure_filename

from .models import (
    ComboTicket,
    Match,
    MediaProof,
    db,
)


main = Blueprint("main", __name__)


# ============================================================================
# Configuration
# ============================================================================

ALLOWED_IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "gif",
}

DEFAULT_MAX_UPLOAD_MB = 8


# ============================================================================
# Utility functions
# ============================================================================

def utc_now():
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def normalize_datetime(value):
    """
    Make a datetime timezone-aware.

    SQLite may return naive datetime values.
    Treat naive values as UTC.
    """

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def is_allowed_image(filename):
    """Check whether an uploaded filename has an allowed extension."""

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_IMAGE_EXTENSIONS


# ============================================================================
# Match helpers
# ============================================================================

def archive_expired_matches(commit=False):
    """
    Move an upcoming match to finished only when:

    1. Kickoff has passed.
    2. A home score exists.
    3. An away score exists.

    We never invent match results.
    """

    now = utc_now()

    candidates = (
        Match.query
        .filter(
            Match.status == "upcoming",
            Match.kickoff_time <= now,
        )
        .all()
    )

    changed = []

    for match in candidates:

        if (
            match.home_score is not None
            and match.away_score is not None
        ):
            match.status = "finished"
            changed.append(match)

    if commit and changed:
        db.session.commit()

    return changed


def get_upcoming_matches(limit=30):
    """Return upcoming matches in chronological order."""

    now = utc_now()

    return (
        Match.query
        .filter(
            Match.status == "upcoming",
            Match.kickoff_time > now,
        )
        .order_by(Match.kickoff_time.asc())
        .limit(limit)
        .all()
    )


def get_finished_history(days=30, limit=100):
    """Return finished matches from the previous N days."""

    now = utc_now()
    cutoff = now - timedelta(days=days)

    return (
        Match.query
        .filter(
            Match.status == "finished",
            Match.kickoff_time >= cutoff,
            Match.kickoff_time <= now,
        )
        .order_by(Match.kickoff_time.desc())
        .limit(limit)
        .all()
    )


def get_active_combos(limit=20):
    """Return pending combo tickets."""

    return (
        ComboTicket.query
        .filter(
            ComboTicket.outcome_status == "pending"
        )
        .order_by(
            ComboTicket.created_at.desc()
        )
        .limit(limit)
        .all()
    )


def get_recent_proofs(limit=24):
    """Return the latest transparency proof uploads."""

    return (
        MediaProof.query
        .order_by(
            MediaProof.uploaded_at.desc()
        )
        .limit(limit)
        .all()
    )


# ============================================================================
# Access control
# ============================================================================

def premium_required(view_function):
    """
    Require a logged-in user with an active premium subscription.

    Anonymous users go to the login page.

    Logged-in users without an active subscription go to /subscribe.
    """

    @wraps(view_function)
    @login_required
    def wrapped_view(*args, **kwargs):

        if not current_user.has_active_subscription:

            flash(
                "An active weekly or monthly subscription is required "
                "to access premium combos.",
                "warning",
            )

            return redirect(
                url_for(
                    "main.subscription_page",
                    next=request.path,
                )
            )

        return view_function(*args, **kwargs)

    return wrapped_view


def admin_required(view_function):
    """Require an authenticated administrator."""

    @wraps(view_function)
    @login_required
    def wrapped_view(*args, **kwargs):

        if not current_user.is_admin:
            abort(403)

        return view_function(*args, **kwargs)

    return wrapped_view


# ============================================================================
# HOME PAGE
# ============================================================================

@main.route("/", methods=["GET"])
def index():
    """
    Main PinnaclePicks homepage.

    Renders:
        app/templates/index.html
    """

    # Only archives matches when an actual score already exists.
    archive_expired_matches(commit=True)

    upcoming_matches = get_upcoming_matches(
        limit=30
    )

    finished_matches = get_finished_history(
        days=30,
        limit=100,
    )

    combo_tickets = get_active_combos(
        limit=20
    )

    media_proofs = get_recent_proofs(
        limit=24
    )

    return render_template(
        "index.html",
        upcoming_matches=upcoming_matches,
        finished_matches=finished_matches,
        combo_tickets=combo_tickets,
        media_proofs=media_proofs,
    )


# ============================================================================
# PREMIUM COMBO
# ============================================================================

@main.route(
    "/combos/<int:combo_id>",
    methods=["GET"],
)
@premium_required
def premium_combo(combo_id):
    """Display a premium combo."""

    combo = db.session.get(
        ComboTicket,
        combo_id,
    )

    if combo is None:
        abort(404)

    # Premium route should only expose premium combos.
    if combo.required_tier != "premium":
        return redirect(
            url_for("main.index")
        )

    return render_template(
        "premium_combo.html",
        combo=combo,
    )


# ============================================================================
# SUBSCRIPTION
# ============================================================================

@main.route(
    "/subscribe",
    methods=["GET"],
)
@login_required
def subscription_page():
    """
    Subscription page.

    IMPORTANT:
    This page does not activate subscriptions.
    Actual payment verification should later update the User record.
    """

    requested_plan = request.args.get(
        "plan",
        "monthly",
    ).lower()

    if requested_plan not in {
        "weekly",
        "monthly",
    }:
        requested_plan = "monthly"

    # Your current file is named subscriptions.html.
    #
    # Therefore we render that exact existing filename.
    return render_template(
        "subscriptions.html",
        requested_plan=requested_plan,
        current_subscription=current_user.subscription_tier,
        subscription_status=current_user.subscription_status,
        subscription_expires_at=(
            current_user.subscription_expires_at
        ),
    )


# ============================================================================
# ADMIN PROOF UPLOAD
# ============================================================================

@main.route(
    "/admin/upload-proof",
    methods=["GET", "POST"],
)
@admin_required
def upload_proof():
    """Administrator-only transparency screenshot upload."""

    if request.method == "GET":

        return render_template(
            "admin/upload_proof.html"
        )

    image = request.files.get("image")

    caption = request.form.get(
        "caption",
        "",
    ).strip()

    # ------------------------------------------------------------------
    # Validate file
    # ------------------------------------------------------------------

    if image is None:

        flash(
            "Please select an image to upload.",
            "danger",
        )

        return redirect(request.url)

    if not image.filename:

        flash(
            "Please select an image to upload.",
            "danger",
        )

        return redirect(request.url)

    if not is_allowed_image(
        image.filename
    ):

        flash(
            "Unsupported image format. "
            "Allowed formats: JPG, JPEG, PNG, WEBP and GIF.",
            "danger",
        )

        return redirect(request.url)

    # ------------------------------------------------------------------
    # Upload directory
    # ------------------------------------------------------------------

    upload_directory = current_app.config.get(
        "PROOF_UPLOAD_FOLDER"
    )

    if not upload_directory:

        upload_directory = os.path.join(
            current_app.static_folder,
            "uploads",
            "proofs",
        )

    os.makedirs(
        upload_directory,
        exist_ok=True,
    )

    # ------------------------------------------------------------------
    # Secure filename
    # ------------------------------------------------------------------

    original_name = secure_filename(
        image.filename
    )

    if not original_name:

        flash(
            "Invalid filename.",
            "danger",
        )

        return redirect(request.url)

    if "." not in original_name:

        flash(
            "Invalid image filename.",
            "danger",
        )

        return redirect(request.url)

    extension = (
        original_name
        .rsplit(".", 1)[1]
        .lower()
    )

    filename = (
        f"{uuid.uuid4().hex}"
        f".{extension}"
    )

    destination = os.path.abspath(
        os.path.join(
            upload_directory,
            filename,
        )
    )

    upload_root = os.path.abspath(
        upload_directory
    )

    # ------------------------------------------------------------------
    # Path traversal protection
    # ------------------------------------------------------------------

    if not destination.startswith(
        upload_root + os.sep
    ):
        abort(400)

    # ------------------------------------------------------------------
    # Save file
    # ------------------------------------------------------------------

    try:

        image.save(destination)

    except OSError:

        current_app.logger.exception(
            "Unable to save proof image."
        )

        flash(
            "The image could not be saved. Please try again.",
            "danger",
        )

        return redirect(request.url)

    # ------------------------------------------------------------------
    # Store path relative to /static/
    # ------------------------------------------------------------------

    relative_path = os.path.relpath(
        destination,
        current_app.static_folder,
    ).replace(
        os.sep,
        "/",
    )

    proof = MediaProof(
        image_path=relative_path,
        caption=caption or None,
    )

    db.session.add(proof)

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        try:

            if os.path.exists(destination):
                os.remove(destination)

        except OSError:

            current_app.logger.exception(
                "Could not clean up uploaded proof."
            )

        current_app.logger.exception(
            "Could not create MediaProof record."
        )

        flash(
            "The upload could not be saved.",
            "danger",
        )

        return redirect(request.url)

    flash(
        "Transparency proof uploaded successfully.",
        "success",
    )

    return redirect(
        url_for(
            "main.upload_proof"
        )
    )

# ============================================================================
# ADMIN DASHBOARD
# ============================================================================

@main.route("/admin", methods=["GET"])
@admin_required
def admin_dashboard():
    """Main administrator dashboard."""

    # Keep the dashboard data fresh.
    archive_expired_matches(commit=True)

    total_matches = Match.query.count()

    upcoming_count = Match.query.filter_by(
        status="upcoming"
    ).count()

    finished_count = Match.query.filter_by(
        status="finished"
    ).count()

    won_count = Match.query.filter(
        Match.status == "finished",
        Match.is_win.is_(True),
    ).count()

    lost_count = Match.query.filter(
        Match.status == "finished",
        Match.is_win.is_(False),
    ).count()

    void_count = Match.query.filter_by(
        status="void"
    ).count()

    matches = (
        Match.query
        .order_by(Match.kickoff_time.desc())
        .limit(100)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        total_matches=total_matches,
        upcoming_count=upcoming_count,
        finished_count=finished_count,
        won_count=won_count,
        lost_count=lost_count,
        void_count=void_count,
        matches=matches,
    )


@main.route("/admin/matches/create", methods=["GET", "POST"])
@admin_required
def admin_create_match():
    """Create a new match."""

    if request.method == "GET":
        return render_template(
            "admin/match_form.html",
            match=None,
            page_title="Create Match",
        )

    home_team = request.form.get("home_team", "").strip()
    away_team = request.form.get("away_team", "").strip()
    league = request.form.get("league", "").strip()
    kickoff_raw = request.form.get("kickoff_time", "").strip()
    market_type = request.form.get("market_type", "").strip()
    pick_selection = request.form.get("pick_selection", "").strip()
    odds_raw = request.form.get("odds", "").strip()
    status = request.form.get("status", "upcoming").strip().lower()

    errors = []

    if not home_team:
        errors.append("Home team is required.")

    if not away_team:
        errors.append("Away team is required.")

    if home_team and away_team and home_team.lower() == away_team.lower():
        errors.append("Home and away teams cannot be the same.")

    if not league:
        errors.append("League is required.")

    if not kickoff_raw:
        errors.append("Kickoff date and time is required.")

    if not market_type:
        errors.append("Market type is required.")

    if not pick_selection:
        errors.append("Pick selection is required.")

    if status not in {"upcoming", "finished", "void"}:
        errors.append("Invalid match status.")

    kickoff_time = None

    if kickoff_raw:
        try:
            kickoff_time = datetime.fromisoformat(kickoff_raw)

            if kickoff_time.tzinfo is None:
                kickoff_time = kickoff_time.replace(
                    tzinfo=timezone.utc
                )
            else:
                kickoff_time = kickoff_time.astimezone(timezone.utc)

        except ValueError:
            errors.append("Invalid kickoff date and time.")

    odds = None

    if not odds_raw:
        errors.append("Odds are required.")
    else:
        try:
            odds = float(odds_raw)

            if odds <= 0:
                errors.append("Odds must be greater than 0.")

        except ValueError:
            errors.append("Odds must be a valid number.")

    if errors:
        for error in errors:
            flash(error, "danger")

        return render_template(
            "admin/match_form.html",
            match=None,
            page_title="Create Match",
        )

    match = Match(
        home_team=home_team,
        away_team=away_team,
        league=league,
        kickoff_time=kickoff_time,
        market_type=market_type,
        pick_selection=pick_selection,
        odds=odds,
        status=status,
    )

    db.session.add(match)

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Could not create match."
        )

        flash(
            "The match could not be created. Please try again.",
            "danger",
        )

        return render_template(
            "admin/match_form.html",
            match=None,
            page_title="Create Match",
        )

    flash(
        f"{home_team} vs {away_team} was created successfully.",
        "success",
    )

    return redirect(
        url_for("main.admin_dashboard")
    )


@main.route(
    "/admin/matches/<int:match_id>/edit",
    methods=["GET", "POST"],
)
@admin_required
def admin_edit_match(match_id):
    """Edit an existing match."""

    match = db.session.get(Match, match_id)

    if match is None:
        abort(404)

    if request.method == "GET":
        return render_template(
            "admin/match_form.html",
            match=match,
            page_title="Edit Match",
        )

    home_team = request.form.get("home_team", "").strip()
    away_team = request.form.get("away_team", "").strip()
    league = request.form.get("league", "").strip()
    kickoff_raw = request.form.get("kickoff_time", "").strip()
    market_type = request.form.get("market_type", "").strip()
    pick_selection = request.form.get("pick_selection", "").strip()
    odds_raw = request.form.get("odds", "").strip()
    status = request.form.get("status", "upcoming").strip().lower()

    errors = []

    if not home_team:
        errors.append("Home team is required.")

    if not away_team:
        errors.append("Away team is required.")

    if home_team and away_team and home_team.lower() == away_team.lower():
        errors.append("Home and away teams cannot be the same.")

    if not league:
        errors.append("League is required.")

    if not kickoff_raw:
        errors.append("Kickoff date and time is required.")

    if not market_type:
        errors.append("Market type is required.")

    if not pick_selection:
        errors.append("Pick selection is required.")

    if status not in {"upcoming", "finished", "void"}:
        errors.append("Invalid match status.")

    kickoff_time = None

    if kickoff_raw:
        try:
            kickoff_time = datetime.fromisoformat(kickoff_raw)

            if kickoff_time.tzinfo is None:
                kickoff_time = kickoff_time.replace(
                    tzinfo=timezone.utc
                )
            else:
                kickoff_time = kickoff_time.astimezone(timezone.utc)

        except ValueError:
            errors.append("Invalid kickoff date and time.")

    odds = None

    if not odds_raw:
        errors.append("Odds are required.")
    else:
        try:
            odds = float(odds_raw)

            if odds <= 0:
                errors.append("Odds must be greater than 0.")

        except ValueError:
            errors.append("Odds must be a valid number.")

    if errors:
        for error in errors:
            flash(error, "danger")

        return render_template(
            "admin/match_form.html",
            match=match,
            page_title="Edit Match",
        )

    match.home_team = home_team
    match.away_team = away_team
    match.league = league
    match.kickoff_time = kickoff_time
    match.market_type = market_type
    match.pick_selection = pick_selection
    match.odds = odds
    match.status = status

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Could not update match."
        )

        flash(
            "The match could not be updated. Please try again.",
            "danger",
        )

        return render_template(
            "admin/match_form.html",
            match=match,
            page_title="Edit Match",
        )

    flash(
        f"{home_team} vs {away_team} updated successfully.",
        "success",
    )

    return redirect(
        url_for("main.admin_dashboard")
    )


@main.route(
    "/admin/matches/<int:match_id>/result",
    methods=["POST"],
)
@admin_required
def admin_update_match_result(match_id):
    """Record a final match result."""

    match = db.session.get(Match, match_id)

    if match is None:
        abort(404)

    home_score_raw = request.form.get(
        "home_score",
        "",
    ).strip()

    away_score_raw = request.form.get(
        "away_score",
        "",
    ).strip()

    result = request.form.get(
        "result",
        "",
    ).strip().lower()

    try:
        home_score = int(home_score_raw)
        away_score = int(away_score_raw)

        if home_score < 0 or away_score < 0:
            raise ValueError

    except (TypeError, ValueError):
        flash(
            "Scores must be valid non-negative numbers.",
            "danger",
        )

        return redirect(
            url_for("main.admin_dashboard")
        )

    if result not in {"won", "lost", "void"}:
        flash(
            "Please select a valid result.",
            "danger",
        )

        return redirect(
            url_for("main.admin_dashboard")
        )

    match.home_score = home_score
    match.away_score = away_score

    if result == "won":
        match.is_win = True
        match.status = "finished"

    elif result == "lost":
        match.is_win = False
        match.status = "finished"

    else:
        match.is_win = None
        match.status = "void"

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Could not update match result."
        )

        flash(
            "The match result could not be saved.",
            "danger",
        )

        return redirect(
            url_for("main.admin_dashboard")
        )

    flash(
        f"Result saved for {match.home_team} vs {match.away_team}.",
        "success",
    )

    return redirect(
        url_for("main.admin_dashboard")
    )


@main.route(
    "/admin/matches/<int:match_id>/delete",
    methods=["POST"],
)
@admin_required
def admin_delete_match(match_id):
    """Delete a match."""

    match = db.session.get(Match, match_id)

    if match is None:
        abort(404)

    match_name = (
        f"{match.home_team} vs {match.away_team}"
    )

    try:
        db.session.delete(match)
        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Could not delete match."
        )

        flash(
            "The match could not be deleted.",
            "danger",
        )

        return redirect(
            url_for("main.admin_dashboard")
        )

    flash(
        f"{match_name} was deleted.",
        "success",
    )

    return redirect(
        url_for("main.admin_dashboard")
    )