import os
import tempfile
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

from vercel import blob

from .models import (
    ComboTicket,
    Match,
    MediaProof,
    Notification,
    MARKETS,
    normalize_market_type,
    db,
)


main = Blueprint("main", __name__)


@main.route("/googleaaeb185e1a9c2151.html")
def google_site_verification():
    return "google-site-verification: googleaaeb185e1a9c2151.html"


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
        return value.replace(
            tzinfo=timezone.utc
        )

    return value


def is_allowed_image(filename):
    """Check whether an uploaded filename has an allowed extension."""

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(
        ".",
        1,
    )[1].lower()

    return extension in ALLOWED_IMAGE_EXTENSIONS


# ============================================================================
# Match helpers
# ============================================================================

def archive_expired_matches(commit=False):
    """
    Reconcile upcoming matches that have already passed their kickoff time.

    A match is moved from upcoming to finished only when:

    1. Kickoff has passed.
    2. A home score exists.
    3. An away score exists.

    We never invent match results.

    If the match has no finished_at timestamp, the current UTC time is used
    as the reconciliation/completion timestamp.
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

            if match.finished_at is None:
                match.finished_at = now

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
        .order_by(
            Match.kickoff_time.asc()
        )
        .limit(limit)
        .all()
    )


def get_finished_history(days=30, limit=100):
    """Return finished matches from the previous N days."""

    now = utc_now()
    cutoff = now - timedelta(
        days=days
    )

    return (
        Match.query
        .filter(
            Match.status == "finished",
            Match.kickoff_time >= cutoff,
            Match.kickoff_time <= now,
        )
        .order_by(
            Match.kickoff_time.desc()
        )
        .limit(limit)
        .all()
    )


def get_weekly_finished_matches(limit=50):
    """Return finished matches from the previous 7 days."""

    return get_finished_history(
        days=7,
        limit=limit,
    )


def get_historical_matches(page=1, per_page=25):
    """Return paginated finished-match history."""

    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1

    try:
        per_page = int(per_page)
    except (TypeError, ValueError):
        per_page = 25

    page = max(1, page)
    per_page = min(max(1, per_page), 100)

    query = Match.query.filter(
        Match.status == "finished"
    )

    total = query.count()

    pages = max(
        1,
        (total + per_page - 1) // per_page,
    )

    if total == 0:
        page = 1
    else:
        page = min(page, pages)

    items = (
        query
        .order_by(
            Match.kickoff_time.desc(),
            Match.id.desc(),
        )
        .offset(
            (page - 1) * per_page
        )
        .limit(per_page)
        .all()
    )

    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages,
    }


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


def get_live_notification():
    """
    Return the most recent live notification, or None.

    A notification is considered live when:

    1. is_active is True
    2. The current time falls within the optional
       starts_at / ends_at window.
    """

    now = utc_now()

    candidates = (
        Notification.query
        .filter(
            Notification.is_active.is_(True)
        )
        .order_by(
            Notification.created_at.desc()
        )
        .all()
    )

    for notification in candidates:

        if notification.is_live:
            return notification

    return None


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

        return view_function(
            *args,
            **kwargs,
        )

    return wrapped_view


def admin_required(view_function):
    """Require an authenticated administrator."""

    @wraps(view_function)
    @login_required
    def wrapped_view(*args, **kwargs):

        if not current_user.is_admin:
            abort(403)

        return view_function(
            *args,
            **kwargs,
        )

    return wrapped_view


# ============================================================================
# HOME PAGE (single-page app: homepage + embedded match history archive)
# ============================================================================

@main.route(
    "/",
    methods=["GET"],
)
def index():
    """
    Main PinnaclePicks homepage.

    Renders:
        app/templates/index.html

    Also embeds the full paginated Match History archive on the SAME page.
    Pagination is driven by ?page=N&per_page=M query parameters — no
    redirect to /previous-results is required.
    """

    # ------------------------------------------------------------------
    # Reconcile matches that already have final scores.
    # ------------------------------------------------------------------

    archive_expired_matches(
        commit=True
    )

    # ------------------------------------------------------------------
    # Pagination inputs for the embedded archive.
    # ------------------------------------------------------------------

    archive_page = request.args.get(
        "page",
        1,
        type=int,
    )

    archive_per_page = request.args.get(
        "per_page",
        10,
        type=int,
    )

    archive = get_historical_matches(
        page=archive_page,
        per_page=archive_per_page,
    )

    # ------------------------------------------------------------------
    # Homepage sections.
    # ------------------------------------------------------------------

    upcoming_matches = get_upcoming_matches(
        limit=30
    )

    finished_matches = get_finished_history(
        days=30,
        limit=100,
    )

    weekly_finished_matches = get_weekly_finished_matches(
        limit=50,
    )

    combo_tickets = get_active_combos(
        limit=20
    )

    media_proofs = get_recent_proofs(
        limit=24
    )

    # ------------------------------------------------------------------
    # Live notification banner (admin-managed).
    # ------------------------------------------------------------------

    notification = get_live_notification()

    return render_template(
        "index.html",
        upcoming_matches=upcoming_matches,
        finished_matches=finished_matches,
        weekly_finished_matches=weekly_finished_matches,
        combo_tickets=combo_tickets,
        media_proofs=media_proofs,
        historical_matches=archive["items"],
        archive=archive,
        notification=notification,
    )


# ============================================================================
# STANDALONE MATCH HISTORY (kept for direct links / fallbacks)
# ============================================================================

@main.route(
    "/previous-results",
    methods=["GET"],
)
def previous_results():
    """
    Display the full paginated finished-match archive on its own page.

    This route is kept so that any existing external links to
    /previous-results continue to work. The homepage now embeds the same
    archive inline, so this route is optional.
    """

    page = request.args.get(
        "page",
        1,
        type=int,
    )

    per_page = request.args.get(
        "per_page",
        25,
        type=int,
    )

    archive = get_historical_matches(
        page=page,
        per_page=per_page,
    )

    return render_template(
        "previous_results.html",
        historical_matches=archive["items"],
        archive=archive,
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
# TRANSPARENCY PROOF UPLOAD
# ============================================================================

@main.route(
    "/admin/upload-proof",
    methods=["GET", "POST"],
)
@admin_required
def upload_proof():
    """Administrator-only transparency screenshot upload."""

    # ------------------------------------------------------------------
    # GET — show upload form + existing proofs
    # ------------------------------------------------------------------

    if request.method == "GET":

        proofs = (
            MediaProof.query
            .order_by(
                MediaProof.uploaded_at.desc()
            )
            .all()
        )

        return render_template(
            "admin/upload_proof.html",
            proofs=proofs,
        )

    image = request.files.get(
        "image"
    )

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

        return redirect(
            request.url
        )

    if not image.filename:

        flash(
            "Please select an image to upload.",
            "danger",
        )

        return redirect(
            request.url
        )

    if not is_allowed_image(
        image.filename
    ):

        flash(
            "Unsupported image format. "
            "Allowed formats: JPG, JPEG, PNG, WEBP and GIF.",
            "danger",
        )

        return redirect(
            request.url
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

        return redirect(
            request.url
        )

    if "." not in original_name:

        flash(
            "Invalid image filename.",
            "danger",
        )

        return redirect(
            request.url
        )

    extension = (
        original_name
        .rsplit(
            ".",
            1,
        )[1]
        .lower()
    )

    filename = (
        f"pinnaclepicks-proofs/"
        f"{uuid.uuid4().hex}"
        f".{extension}"
    )

    # ------------------------------------------------------------------
    # Upload to Vercel Blob using a temporary filesystem file.
    #
    # Vercel's production filesystem is ephemeral, so the temporary
    # file exists only long enough for Blob storage to receive it.
    # ------------------------------------------------------------------

    temporary_path = None
    blob_url = None

    try:

        with tempfile.NamedTemporaryFile(
            prefix="pinnaclepicks-proof-",
            suffix=f".{extension}",
            delete=False,
        ) as temporary_file:

            temporary_path = temporary_file.name

        image.save(
            temporary_path
        )

        result = blob.upload_file(
            temporary_path,
            filename,
            access="public",
            content_type=image.mimetype or None,
        )

        blob_url = result.url

    except Exception:

        current_app.logger.exception(
            "Unable to upload proof image to Vercel Blob."
        )

        flash(
            "The image could not be uploaded. Please try again.",
            "danger",
        )

        return redirect(
            request.url
        )

    finally:

        if temporary_path:

            try:

                if os.path.exists(
                    temporary_path
                ):
                    os.remove(
                        temporary_path
                    )

            except OSError:

                current_app.logger.exception(
                    "Could not remove temporary proof image."
                )

    # ------------------------------------------------------------------
    # Store the public Blob URL in the existing MediaProof record.
    # No database migration is required.
    # ------------------------------------------------------------------

    proof = MediaProof(
        image_path=blob_url,
        caption=caption or None,
    )

    db.session.add(
        proof
    )

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        # The Blob was already uploaded. Remove it if the database
        # transaction fails so we do not leave an orphaned object.
        if blob_url:

            try:

                blob.delete(
                    blob_url
                )

            except Exception:

                current_app.logger.exception(
                    "Could not clean up proof Blob after "
                    "database failure."
                )

        current_app.logger.exception(
            "Could not create MediaProof record."
        )

        flash(
            "The upload could not be saved.",
            "danger",
        )

        return redirect(
            request.url
        )

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
# DELETE TRANSPARENCY PROOF
# ============================================================================

@main.route(
    "/admin/upload-proof/<int:proof_id>/delete",
    methods=["POST"],
)
@admin_required
def delete_proof(proof_id):
    """Administrator-only deletion of a transparency proof."""

    proof = db.session.get(
        MediaProof,
        proof_id,
    )

    if proof is None:

        flash(
            "The transparency proof was not found.",
            "warning",
        )

        return redirect(
            url_for(
                "main.upload_proof"
            )
        )

    image_path = proof.image_path or ""

    # ------------------------------------------------------------------
    # Vercel Blob image
    # ------------------------------------------------------------------

    if image_path.startswith(
        ("http://", "https://")
    ):

        try:

            blob.delete(
                image_path
            )

        except Exception:

            current_app.logger.exception(
                "Could not delete proof image from Vercel Blob."
            )

            flash(
                "The transparency proof could not be deleted "
                "from image storage.",
                "danger",
            )

            return redirect(
                url_for(
                    "main.upload_proof"
                )
            )

        # --------------------------------------------------------------
        # Delete database record after Blob deletion succeeds.
        # --------------------------------------------------------------

        try:

            db.session.delete(
                proof
            )

            db.session.commit()

        except Exception:

            db.session.rollback()

            current_app.logger.exception(
                "Could not delete MediaProof record."
            )

            flash(
                "The image was removed from storage, but the "
                "proof record could not be deleted.",
                "danger",
            )

            return redirect(
                url_for(
                    "main.upload_proof"
                )
            )

        flash(
            "Transparency proof deleted successfully.",
            "success",
        )

        return redirect(
            url_for(
                "main.upload_proof"
            )
        )

    # ------------------------------------------------------------------
    # Legacy local filesystem image
    #
    # Keep support for proofs uploaded before Vercel Blob storage.
    # ------------------------------------------------------------------

    local_image_path = None

    if image_path:

        static_root = os.path.abspath(
            current_app.static_folder
        )

        candidate_path = os.path.abspath(
            os.path.join(
                current_app.static_folder,
                image_path,
            )
        )

        if candidate_path.startswith(
            static_root + os.sep
        ):
            local_image_path = candidate_path

    # ------------------------------------------------------------------
    # Delete database record
    # ------------------------------------------------------------------

    try:

        db.session.delete(
            proof
        )

        db.session.commit()

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Could not delete MediaProof record."
        )

        flash(
            "The transparency proof could not be deleted.",
            "danger",
        )

        return redirect(
            url_for(
                "main.upload_proof"
            )
        )

    # ------------------------------------------------------------------
    # Delete legacy local image if one exists.
    # ------------------------------------------------------------------

    if local_image_path:

        try:

            if os.path.isfile(
                local_image_path
            ):
                os.remove(
                    local_image_path
                )

        except OSError:

            current_app.logger.exception(
                "The proof record was deleted, "
                "but the legacy image file could not be removed."
            )

            flash(
                "Proof deleted, but the image file could not "
                "be removed from storage.",
                "warning",
            )

            return redirect(
                url_for(
                    "main.upload_proof"
                )
            )

    flash(
        "Transparency proof deleted successfully.",
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

@main.route(
    "/admin",
    methods=["GET"],
)
@admin_required
def admin_dashboard():
    """Main administrator dashboard."""

    # Keep dashboard data fresh.
    archive_expired_matches(
        commit=True
    )

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
        .order_by(
            Match.kickoff_time.desc()
        )
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


# ============================================================================
# CREATE MATCH
# ============================================================================

@main.route(
    "/admin/matches/create",
    methods=["GET", "POST"],
)
@admin_required
def admin_create_match():
    """Create a new match."""

    if request.method == "GET":

        return render_template(
            "admin/match_form.html",
            match=None,
            page_title="Create Match",
            markets=MARKETS,
        )

    home_team = request.form.get(
        "home_team",
        "",
    ).strip()

    away_team = request.form.get(
        "away_team",
        "",
    ).strip()

    league = request.form.get(
        "league",
        "",
    ).strip()

    kickoff_raw = request.form.get(
        "kickoff_time",
        "",
    ).strip()

    market_type = request.form.get(
        "market_type",
        "",
    ).strip()

    market_type = normalize_market_type(
        market_type
    )

    pick_selection = request.form.get(
        "pick_selection",
        "",
    ).strip()

    odds_raw = request.form.get(
        "odds",
        "",
    ).strip()

    status = request.form.get(
        "status",
        "upcoming",
    ).strip().lower()

    errors = []

    if not home_team:
        errors.append(
            "Home team is required."
        )

    if not away_team:
        errors.append(
            "Away team is required."
        )

    if (
        home_team
        and away_team
        and home_team.lower() == away_team.lower()
    ):
        errors.append(
            "Home and away teams cannot be the same."
        )

    if not league:
        errors.append(
            "League is required."
        )

    if not kickoff_raw:
        errors.append(
            "Kickoff date and time is required."
        )

    if not market_type:
        errors.append(
            "Market is required."
        )

    elif market_type not in MARKETS:
        errors.append(
            "Please select a valid market."
        )

    if not pick_selection:
        errors.append(
            "Pick selection is required."
        )

    if status not in {
        "upcoming",
        "void",
    }:
        if status == "finished":
            errors.append(
                "A new match cannot be created as finished. "
                "Create it as upcoming, then use Save Result "
                "when the final result is available."
            )
        else:
            errors.append(
                "Invalid match status."
            )

    kickoff_time = None

    if kickoff_raw:

        try:

            kickoff_time = datetime.fromisoformat(
                kickoff_raw
            )

            if kickoff_time.tzinfo is None:

                kickoff_time = kickoff_time.replace(
                    tzinfo=timezone.utc
                )

            else:

                kickoff_time = kickoff_time.astimezone(
                    timezone.utc
                )

        except ValueError:

            errors.append(
                "Invalid kickoff date and time."
            )

    odds = None

    if not odds_raw:

        errors.append(
            "Odds are required."
        )

    else:

        try:

            odds = float(
                odds_raw
            )

            if odds <= 0:
                errors.append(
                    "Odds must be greater than 0."
                )

        except ValueError:

            errors.append(
                "Odds must be a valid number."
            )

    if errors:

        for error in errors:

            flash(
                error,
                "danger",
            )

        return render_template(
            "admin/match_form.html",
            match=None,
            page_title="Create Match",
            markets=MARKETS,
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

    # New void matches are immediately considered completed.
    if status == "void":

        match.is_win = None
        match.finished_at = utc_now()

    else:

        match.is_win = None
        match.finished_at = None

    db.session.add(
        match
    )

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
            markets=MARKETS,
        )

    flash(
        f"{home_team} vs {away_team} was created successfully.",
        "success",
    )

    return redirect(
        url_for(
            "main.admin_dashboard"
        )
    )


# ============================================================================
# EDIT MATCH
# ============================================================================

@main.route(
    "/admin/matches/<int:match_id>/edit",
    methods=["GET", "POST"],
)
@admin_required
def admin_edit_match(match_id):
    """Edit an existing match."""

    match = db.session.get(
        Match,
        match_id,
    )

    if match is None:
        abort(404)

    if request.method == "GET":

        return render_template(
            "admin/match_form.html",
            match=match,
            page_title="Edit Match",
            markets=MARKETS,
        )

    home_team = request.form.get(
        "home_team",
        "",
    ).strip()

    away_team = request.form.get(
        "away_team",
        "",
    ).strip()

    league = request.form.get(
        "league",
        "",
    ).strip()

    kickoff_raw = request.form.get(
        "kickoff_time",
        "",
    ).strip()

    market_type = request.form.get(
        "market_type",
        "",
    ).strip()

    market_type = normalize_market_type(
        market_type
    )

    pick_selection = request.form.get(
        "pick_selection",
        "",
    ).strip()

    odds_raw = request.form.get(
        "odds",
        "",
    ).strip()

    status = request.form.get(
        "status",
        "upcoming",
    ).strip().lower()

    errors = []

    if not home_team:

        errors.append(
            "Home team is required."
        )

    if not away_team:

        errors.append(
            "Away team is required."
        )

    if (
        home_team
        and away_team
        and home_team.lower() == away_team.lower()
    ):

        errors.append(
            "Home and away teams cannot be the same."
        )

    if not league:

        errors.append(
            "League is required."
        )

    if not kickoff_raw:

        errors.append(
            "Kickoff date and time is required."
        )

    if not market_type:

        errors.append(
            "Market is required."
        )

    elif market_type not in MARKETS:

        errors.append(
            "Please select a valid market."
        )

    if not pick_selection:

        errors.append(
            "Pick selection is required."
        )

    if status not in {
        "upcoming",
        "finished",
        "void",
    }:

        errors.append(
            "Invalid match status."
        )

    kickoff_time = None

    if kickoff_raw:

        try:

            kickoff_time = datetime.fromisoformat(
                kickoff_raw
            )

            if kickoff_time.tzinfo is None:

                kickoff_time = kickoff_time.replace(
                    tzinfo=timezone.utc
                )

            else:

                kickoff_time = kickoff_time.astimezone(
                    timezone.utc
                )

        except ValueError:

            errors.append(
                "Invalid kickoff date and time."
            )

    odds = None

    if not odds_raw:

        errors.append(
            "Odds are required."
        )

    else:

        try:

            odds = float(
                odds_raw
            )

            if odds <= 0:

                errors.append(
                    "Odds must be greater than 0."
                )

        except ValueError:

            errors.append(
                "Odds must be a valid number."
            )

    # ------------------------------------------------------------------
    # Finished-state integrity
    # ------------------------------------------------------------------

    if status == "finished":

        if (
            match.home_score is None
            or match.away_score is None
        ):

            errors.append(
                "A finished match must have final scores. "
                "Use the Save Result form to record the final result."
            )

        if match.is_win is None:

            errors.append(
                "A finished match must have a Won or Lost result. "
                "Use the Save Result form to record the final result."
            )

    if errors:

        for error in errors:

            flash(
                error,
                "danger",
            )

        return render_template(
            "admin/match_form.html",
            match=match,
            page_title="Edit Match",
            markets=MARKETS,
        )

    # ------------------------------------------------------------------
    # Update basic match information
    # ------------------------------------------------------------------

    match.home_team = home_team
    match.away_team = away_team
    match.league = league
    match.kickoff_time = kickoff_time
    match.market_type = market_type
    match.pick_selection = pick_selection
    match.odds = odds

    # ------------------------------------------------------------------
    # Synchronize lifecycle state
    # ------------------------------------------------------------------

    if status == "upcoming":

        # Returning a match to upcoming means its previous
        # final result is no longer considered valid.
        match.status = "upcoming"
        match.home_score = None
        match.away_score = None
        match.is_win = None
        match.finished_at = None

    elif status == "void":

        # A void match has no Won/Lost prediction result.
        match.status = "void"
        match.is_win = None

        if match.finished_at is None:

            match.finished_at = utc_now()

    else:

        # "finished" has already been validated above.
        match.status = "finished"

        if match.finished_at is None:

            match.finished_at = utc_now()

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
            markets=MARKETS,
        )

    flash(
        f"{home_team} vs {away_team} updated successfully.",
        "success",
    )

    return redirect(
        url_for(
            "main.admin_dashboard"
        )
    )


# ============================================================================
# RECORD FINAL MATCH RESULT
# ============================================================================

@main.route(
    "/admin/matches/<int:match_id>/result",
    methods=["POST"],
)
@admin_required
def admin_update_match_result(match_id):
    """Record or update a final match result."""

    match = db.session.get(
        Match,
        match_id,
    )

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

        home_score = int(
            home_score_raw
        )

        away_score = int(
            away_score_raw
        )

        if (
            home_score < 0
            or away_score < 0
        ):
            raise ValueError

    except (
        TypeError,
        ValueError,
    ):

        flash(
            "Scores must be valid non-negative numbers.",
            "danger",
        )

        return redirect(
            url_for(
                "main.admin_dashboard"
            )
        )

    if result not in {
        "won",
        "lost",
        "void",
    }:

        flash(
            "Please select a valid result.",
            "danger",
        )

        return redirect(
            url_for(
                "main.admin_dashboard"
            )
        )

    # ------------------------------------------------------------------
    # Save final score
    # ------------------------------------------------------------------

    match.home_score = home_score
    match.away_score = away_score

    # ------------------------------------------------------------------
    # Save authoritative result state
    # ------------------------------------------------------------------

    completion_time = utc_now()

    if result == "won":

        match.is_win = True
        match.status = "finished"
        match.finished_at = completion_time

    elif result == "lost":

        match.is_win = False
        match.status = "finished"
        match.finished_at = completion_time

    else:

        match.is_win = None
        match.status = "void"
        match.finished_at = completion_time

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
            url_for(
                "main.admin_dashboard"
            )
        )

    flash(
        f"Result saved for {match.home_team} vs {match.away_team}.",
        "success",
    )

    return redirect(
        url_for(
            "main.admin_dashboard"
        )
    )


# ============================================================================
# DELETE MATCH
# ============================================================================

@main.route(
    "/admin/matches/<int:match_id>/delete",
    methods=["POST"],
)
@admin_required
def admin_delete_match(match_id):
    """Delete a match."""

    match = db.session.get(
        Match,
        match_id,
    )

    if match is None:
        abort(404)

    match_name = (
        f"{match.home_team} vs {match.away_team}"
    )

    try:

        db.session.delete(
            match
        )

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
            url_for(
                "main.admin_dashboard"
            )
        )

    flash(
        f"{match_name} was deleted.",
        "success",
    )

    return redirect(
        url_for(
            "main.admin_dashboard"
        )
    )


# ============================================================================
# ADMIN — NOTIFICATIONS
# ============================================================================

@main.route(
    "/admin/notifications",
    methods=["GET"],
)
@admin_required
def admin_notifications():
    """List all notifications."""

    notifications = (
        Notification.query
        .order_by(
            Notification.is_active.desc(),
            Notification.created_at.desc(),
        )
        .all()
    )

    return render_template(
        "admin/notifications.html",
        notifications=notifications,
    )


@main.route(
    "/admin/notifications/create",
    methods=["GET", "POST"],
)
@admin_required
def admin_notification_create():
    """Create a new notification."""

    if request.method == "GET":
        return render_template(
            "admin/notification_form.html",
            notification=None,
            page_title="Create Notification",
        )

    title = request.form.get("title", "").strip()
    headline = request.form.get("headline", "").strip()
    body = request.form.get("body", "").strip()
    warning = request.form.get("warning", "").strip()
    footer = request.form.get("footer", "").strip()
    style = request.form.get("style", "blue").strip().lower()
    is_active = request.form.get("is_active") == "on"

    starts_raw = request.form.get("starts_at", "").strip()
    ends_raw = request.form.get("ends_at", "").strip()

    errors = []

    if not title:
        errors.append("Title is required.")

    if not headline:
        errors.append("Headline is required.")

    if style not in {"blue", "dark", "green"}:
        style = "blue"

    starts_at = None
    if starts_raw:
        try:
            starts_at = datetime.fromisoformat(starts_raw)
            if starts_at.tzinfo is None:
                starts_at = starts_at.replace(tzinfo=timezone.utc)
        except ValueError:
            errors.append("Invalid 'starts at' date.")

    ends_at = None
    if ends_raw:
        try:
            ends_at = datetime.fromisoformat(ends_raw)
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=timezone.utc)
        except ValueError:
            errors.append("Invalid 'ends at' date.")

    if errors:
        for error in errors:
            flash(error, "danger")

        return render_template(
            "admin/notification_form.html",
            notification=None,
            page_title="Create Notification",
        )

    notification = Notification(
        title=title,
        headline=headline,
        body=body,
        warning=warning,
        footer=footer,
        style=style,
        is_active=is_active,
        starts_at=starts_at,
        ends_at=ends_at,
    )

    db.session.add(notification)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Could not create notification.")
        flash("The notification could not be created.", "danger")
        return render_template(
            "admin/notification_form.html",
            notification=None,
            page_title="Create Notification",
        )

    flash("Notification created successfully.", "success")
    return redirect(url_for("main.admin_notifications"))


@main.route(
    "/admin/notifications/<int:notification_id>/edit",
    methods=["GET", "POST"],
)
@admin_required
def admin_notification_edit(notification_id):
    """Edit an existing notification."""

    notification = db.session.get(Notification, notification_id)

    if notification is None:
        abort(404)

    if request.method == "GET":
        return render_template(
            "admin/notification_form.html",
            notification=notification,
            page_title="Edit Notification",
        )

    notification.title = request.form.get("title", "").strip()
    notification.headline = request.form.get("headline", "").strip()
    notification.body = request.form.get("body", "").strip()
    notification.warning = request.form.get("warning", "").strip()
    notification.footer = request.form.get("footer", "").strip()

    style = request.form.get("style", "blue").strip().lower()
    notification.style = style if style in {"blue", "dark", "green"} else "blue"

    notification.is_active = request.form.get("is_active") == "on"

    starts_raw = request.form.get("starts_at", "").strip()
    ends_raw = request.form.get("ends_at", "").strip()

    notification.starts_at = None
    if starts_raw:
        try:
            dt = datetime.fromisoformat(starts_raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            notification.starts_at = dt
        except ValueError:
            flash("Invalid 'starts at' date.", "danger")
            return redirect(
                url_for("main.admin_notification_edit", notification_id=notification.id)
            )

    notification.ends_at = None
    if ends_raw:
        try:
            dt = datetime.fromisoformat(ends_raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            notification.ends_at = dt
        except ValueError:
            flash("Invalid 'ends at' date.", "danger")
            return redirect(
                url_for("main.admin_notification_edit", notification_id=notification.id)
            )

    if not notification.title:
        flash("Title is required.", "danger")
        return redirect(
            url_for("main.admin_notification_edit", notification_id=notification.id)
        )

    if not notification.headline:
        flash("Headline is required.", "danger")
        return redirect(
            url_for("main.admin_notification_edit", notification_id=notification.id)
        )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Could not update notification.")
        flash("The notification could not be updated.", "danger")

    flash("Notification updated successfully.", "success")
    return redirect(url_for("main.admin_notifications"))


@main.route(
    "/admin/notifications/<int:notification_id>/toggle",
    methods=["POST"],
)
@admin_required
def admin_notification_toggle(notification_id):
    """Toggle a notification's active state."""

    notification = db.session.get(Notification, notification_id)

    if notification is None:
        abort(404)

    notification.is_active = not notification.is_active

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Could not toggle notification.")
        flash("The notification could not be updated.", "danger")
        return redirect(url_for("main.admin_notifications"))

    state = "activated" if notification.is_active else "deactivated"
    flash(f"Notification {state}.", "success")

    return redirect(url_for("main.admin_notifications"))


@main.route(
    "/admin/notifications/<int:notification_id>/delete",
    methods=["POST"],
)
@admin_required
def admin_notification_delete(notification_id):
    """Delete a notification."""

    notification = db.session.get(Notification, notification_id)

    if notification is None:
        abort(404)

    try:
        db.session.delete(notification)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Could not delete notification.")
        flash("The notification could not be deleted.", "danger")
        return redirect(url_for("main.admin_notifications"))

    flash("Notification deleted.", "success")
    return redirect(url_for("main.admin_notifications"))