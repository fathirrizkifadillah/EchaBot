"""
EchaBot — entry point.
Run with: python app.py
"""
from api import create_app

app = create_app()

if __name__ == "__main__":
    import os

    app.run(
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
    )
