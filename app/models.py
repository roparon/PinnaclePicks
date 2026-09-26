# models.py

from datetime import datetime, timezone
from decimal import Decimal

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


db = SQLAlchemy()


# ---------------------------------------------------------------------------
# Association table: ComboTicket <-> Match
# ---------------------------------------------------------------------------

combo_matches = db.Table(
    "combo_matches",
    db.Column(
        "combo_ticket_id",
        db.Integer,
        db.ForeignKey("combo_tickets.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "match_id",
        db.Integer,
        db.ForeignKey("matches.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False,
        index=True,
    )

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False,
    )

    # free / weekly / monthly
    subscription_tier = db.Column(
        db.String(20),
        nullable=False,
        default="free",
        index=True,
    )

    subscription_expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    is_admin = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ------------------------------------------------------------------
    # Flask-Login compatibility
    # ------------------------------------------------------------------

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # ------------------------------------------------------------------
    # Subscription helpers
    # ------------------------------------------------------------------

    @property
    def has_active_subscription(self):
        """
        True only for weekly/monthly subscriptions whose expiry timestamp
        has not passed.
        """

        if self.subscription_tier not in {"weekly", "monthly"}:
            return False

        if not self.subscription_expires_at:
            return False

        expires_at = self.subscription_expires_at

        # Handle old database records containing naive timestamps.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        return expires_at > datetime.now(timezone.utc)

    @property
    def is_premium(self):
        return self.has_active_subscription

    @property
    def subscription_status(self):
        """
        Returns a simple display-friendly state.
        """

        if self.has_active_subscription:
            return "active"

        if self.subscription_tier in {"weekly", "monthly"}:
            return "expired"

        return "free"

    def has_tier_access(self, required_tier):
        """
        Supports:
            free
            premium

        A premium user must have an active paid subscription.
        """

        if required_tier == "free":
            return True

        if required_tier == "premium":
            return self.has_active_subscription

        return False

    def __repr__(self):
        return f"<User {self.username}>"


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------

class Match(db.Model):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)

    home_team = db.Column(
        db.String(150),
        nullable=False,
        index=True,
    )

    away_team = db.Column(
        db.String(150),
        nullable=False,
        index=True,
    )

    league = db.Column(
        db.String(150),
        nullable=False,
        index=True,
    )

    kickoff_time = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # 1X2 / Over/Under / GG/NG
    market_type = db.Column(
        db.String(30),
        nullable=False,
        index=True,
    )

    pick_selection = db.Column(
        db.String(100),
        nullable=False,
    )

    odds = db.Column(
        db.Numeric(10, 3),
        nullable=False,
    )

    # upcoming / finished / void
    status = db.Column(
        db.String(20),
        nullable=False,
        default="upcoming",
        index=True,
    )

    home_score = db.Column(
        db.Integer,
        nullable=True,
    )

    away_score = db.Column(
        db.Integer,
        nullable=True,
    )

    is_win = db.Column(
        db.Boolean,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def score_display(self):
        if self.home_score is None or self.away_score is None:
            return "—"

        return f"{self.home_score} - {self.away_score}"

    @property
    def result_label(self):
        if self.status == "void":
            return "Void"

        if self.status != "finished":
            return "Pending"

        if self.is_win is True:
            return "Won"

        if self.is_win is False:
            return "Lost"

        return "Pending"

    @property
    def result_class(self):
        if self.status == "void":
            return "void"

        if self.is_win is True:
            return "won"

        if self.is_win is False:
            return "lost"

        return "pending"

    @property
    def market_label(self):
        labels = {
            "1X2": "1X2",
            "OVER_UNDER": "Over/Under",
            "Over/Under": "Over/Under",
            "GG_NG": "GG/NG",
            "GG/NG": "GG/NG",
        }

        return labels.get(self.market_type, self.market_type)

    def __repr__(self):
        return f"<Match {self.home_team} vs {self.away_team}>"


# ---------------------------------------------------------------------------
# Combo Ticket
# ---------------------------------------------------------------------------

class ComboTicket(db.Model):
    __tablename__ = "combo_tickets"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(
        db.String(150),
        nullable=False,
        default="Accumulator",
    )

    total_odds = db.Column(
        db.Numeric(12, 3),
        nullable=False,
    )

    # pending / won / lost / void
    outcome_status = db.Column(
        db.String(20),
        nullable=False,
        default="pending",
        index=True,
    )

    # free / premium
    required_tier = db.Column(
        db.String(20),
        nullable=False,
        default="free",
        index=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    matches = db.relationship(
        "Match",
        secondary=combo_matches,
        lazy="selectin",
        backref=db.backref(
            "combo_tickets",
            lazy="selectin",
        ),
    )

    @property
    def selection_count(self):
        return len(self.matches)

    @property
    def is_premium(self):
        return self.required_tier == "premium"

    @property
    def outcome_label(self):
        return self.outcome_status.capitalize()

    def __repr__(self):
        return f"<ComboTicket {self.id} {self.title}>"


# ---------------------------------------------------------------------------
# Media Proof
# ---------------------------------------------------------------------------

class MediaProof(db.Model):
    __tablename__ = "media_proofs"

    id = db.Column(db.Integer, primary_key=True)

    image_path = db.Column(
        db.String(500),
        nullable=False,
    )

    caption = db.Column(
        db.String(500),
        nullable=True,
    )

    uploaded_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self):
        return f"<MediaProof {self.id}>"