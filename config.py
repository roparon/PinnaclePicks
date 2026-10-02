
import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///pinnaclepicks.db",
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "change-this-in-production",
    )

    # Maximum upload size: 8 MB
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024

    # Transparency screenshot storage
    PROOF_UPLOAD_FOLDER = os.path.join(
        "static",
        "uploads",
        "proofs",
    )