import logging
import os
import re
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

from src.database import db

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def create_app():
    app = Flask(__name__, template_folder=str(BASE_DIR / "templates"),
                static_folder=str(BASE_DIR / "static"))
    app.secret_key = os.getenv("SECRET_KEY", os.urandom(32).hex())
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'echabot.db'}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    db.init_app(app)
    with app.app_context():
        db.create_all()

    from api.routes.chat import chat_bp
    from api.routes.sessions import sessions_bp

    app.register_blueprint(chat_bp)
    app.register_blueprint(sessions_bp, url_prefix="/api/sessions")

    return app
