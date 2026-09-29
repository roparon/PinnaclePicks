from datetime import datetime, timezone

from flask import Blueprint, Response, render_template, request, url_for

from .models import Match, db


seo_bp = Blueprint("seo", __name__)


# ============================================================================
# ROBOTS.TXT
# ============================================================================

@seo_bp.route("/robots.txt")
def robots_txt():
    sitemap_url = url_for(
        "seo.sitemap_xml",
        _external=True,
    )

    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin/",
            "Disallow: /account",
            "Disallow: /login",
            "Disallow: /register",
            "Disallow: /logout",
            "Disallow: /subscribe",
            "Disallow: /combos/",
            "",
            f"Sitemap: {sitemap_url}",
            "",
        ]
    )

    return Response(
        content,
        mimetype="text/plain",
    )


# ============================================================================
# XML SITEMAP
# ============================================================================

@seo_bp.route("/sitemap.xml")
def sitemap_xml():
    """
    Dynamic sitemap generated from the public PinnaclePicks database.

    Important:
    - No database migration required.
    - Match URLs are generated from existing Match IDs.
    - Only public pages are included.
    """

    pages = [
        {
            "loc": url_for(
                "main.index",
                _external=True,
            ),
            "priority": "1.0",
            "changefreq": "daily",
        },
        {
            "loc": url_for(
                "main.previous_results",
                _external=True,
            ),
            "priority": "0.9",
            "changefreq": "daily",
        },
    ]

    matches = (
        Match.query
        .order_by(
            Match.updated_at.desc(),
            Match.id.desc(),
        )
        .all()
    )

    for match in matches:
        pages.append(
            {
                "loc": url_for(
                    "seo.match_detail",
                    match_id=match.id,
                    _external=True,
                ),
                "lastmod": (
                    match.updated_at
                    or match.finished_at
                    or match.kickoff_time
                    or match.created_at
                ),
                "priority": (
                    "0.8"
                    if match.status == "upcoming"
                    else "0.7"
                ),
                "changefreq": (
                    "hourly"
                    if match.status == "upcoming"
                    else "weekly"
                ),
            }
        )

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for page in pages:

        xml_lines.append("  <url>")

        xml_lines.append(
            f"    <loc>{page['loc']}</loc>"
        )

        if page.get("lastmod"):
            lastmod = page["lastmod"]

            if isinstance(lastmod, datetime):
                if lastmod.tzinfo is None:
                    lastmod = lastmod.replace(
                        tzinfo=timezone.utc
                    )

                lastmod = lastmod.date().isoformat()

            xml_lines.append(
                f"    <lastmod>{lastmod}</lastmod>"
            )

        xml_lines.append(
            f"    <changefreq>{page['changefreq']}</changefreq>"
        )

        xml_lines.append(
            f"    <priority>{page['priority']}</priority>"
        )

        xml_lines.append("  </url>")

    xml_lines.append("</urlset>")

    return Response(
        "\n".join(xml_lines),
        mimetype="application/xml",
    )


# ============================================================================
# PUBLIC INDIVIDUAL MATCH PAGE
# ============================================================================

@seo_bp.route(
    "/matches/<int:match_id>",
    methods=["GET"],
)
def match_detail(match_id):
    """
    Public SEO-friendly page for an individual PinnaclePicks match.

    Uses the existing Match record directly.
    No new database columns are required.
    """

    match = db.session.get(
        Match,
        match_id,
    )

    if match is None:
        from flask import abort
        abort(404)

    if match.status == "finished":
        page_title = (
            f"{match.home_team} vs {match.away_team} "
            f"Result & Prediction | PinnaclePicks"
        )
    elif match.status == "void":
        page_title = (
            f"{match.home_team} vs {match.away_team} "
            f"Match Record | PinnaclePicks"
        )
    else:
        page_title = (
            f"{match.home_team} vs {match.away_team} "
            f"Prediction & Match Analysis | PinnaclePicks"
        )

    description = (
        f"{match.home_team} vs {match.away_team} "
        f"{match.league} match information, prediction, "
        f"market selection, odds and statistical record from PinnaclePicks."
    )

    if match.status == "finished":
        description = (
            f"{match.home_team} vs {match.away_team} "
            f"{match.league} result, final score, prediction and "
            f"historical match record from PinnaclePicks."
        )

    return render_template(
        "match_detail.html",
        match=match,
        page_title=page_title,
        page_description=description,
    )
