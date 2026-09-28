"""
One-shot migration: normalize legacy Match.market_type values
to canonical keys used by the MARKETS dict.

Safe to run multiple times — it only changes rows that need it.
"""

from app import create_app          # ← adjust if your app factory is named differently
from app.models import (
    Match,
    MARKET_ALIASES,
    MARKETS,
    db,
)


def main():
    app = create_app()

    with app.app_context():
        matches = Match.query.all()
        total = len(matches)

        print(f"Scanning {total} match(es)…\n")

        changed = 0
        unknown = []

        for match in matches:
            old = match.market_type
            new = MARKET_ALIASES.get(old, old)

            if new != old:
                match.market_type = new
                changed += 1
                print(f"  #{match.id:>4}  {old!r:>20}  →  {new!r}")

            elif new not in MARKETS:
                unknown.append((match.id, old))

        if changed:
            try:
                db.session.commit()
                print(f"\n✅ Committed {changed} change(s).")
            except Exception as exc:
                db.session.rollback()
                print(f"\n❌ Commit failed: {exc}")
                return
        else:
            print("\nℹ️  No changes required.")

        if unknown:
            print(f"\n⚠️  {len(unknown)} row(s) still have an unknown market key:")
            for mid, val in unknown:
                print(f"     #{mid:>4}  {val!r}")
            print(
                "\n   These were left untouched. Either:"
                "\n     • add them to MARKETS / MARKET_ALIASES in models.py, or"
                "\n     • edit those rows manually in the admin UI."
            )


if __name__ == "__main__":
    main()