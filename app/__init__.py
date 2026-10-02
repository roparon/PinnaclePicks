import os
from sqlalchemy import event

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate

from .models import db, User


login_manager = LoginManager()
migrate = Migrate()


def create_app(config_object=None):
    app = Flask(__name__)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    if config_object:
        app.config.from_object(config_object)
    else:
        from config import Config
        app.config.from_object(Config)

    # ------------------------------------------------------------------
    # Extensions
    # ------------------------------------------------------------------

    db.init_app(app)

    # Neon PostgreSQL pooler may provide an empty search_path.
    # Set the application schema after each database connection.
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith(
        ("postgresql://", "postgresql+psycopg://")
    ):
        with app.app_context():
            @event.listens_for(db.engine, "connect")
            def set_postgres_search_path(dbapi_connection, connection_record):
                with dbapi_connection.cursor() as cursor:
                    cursor.execute("SET search_path TO public")
    migrate.init_app(app, db)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # ------------------------------------------------------------------
    # Flask-Login user loader
    # ------------------------------------------------------------------

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Proof upload folder
    # ------------------------------------------------------------------

    upload_folder = app.config.get("PROOF_UPLOAD_FOLDER")

    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(
            app.root_path,
            upload_folder,
        )

    app.config["PROOF_UPLOAD_FOLDER"] = upload_folder

    os.makedirs(upload_folder, exist_ok=True)

    # ------------------------------------------------------------------
    # Blueprints
    # ------------------------------------------------------------------

    from .routes import main
    from .auth import auth
    from .seo import seo_bp

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(seo_bp)

    return app