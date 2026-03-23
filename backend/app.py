"""Flask application factory for the Chicago spending investigation API."""

import sys
from pathlib import Path

# Ensure project root is on sys.path so 'backend.*' imports work
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import os

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from backend.api.routes_overview import overview_bp
from backend.api.routes_payments import payments_bp
from backend.api.routes_vendors import vendors_bp
from backend.api.routes_departments import departments_bp
from backend.api.routes_alerts import alerts_bp
from backend.api.routes_categories import categories_bp
from backend.api.routes_trends import trends_bp
from backend.api.routes_contracts import contracts_bp
from backend.api.routes_network import network_bp
from backend.api.routes_donations import donations_bp


def create_app():
    """Create and configure the Flask application."""
    # In production, serve the built React app
    static_dir = _project_root / "frontend" / "dist"
    if static_dir.exists():
        app = Flask(
            __name__,
            static_folder=str(static_dir),
            static_url_path="",
        )
    else:
        app = Flask(__name__)

    # CORS for dev; in production the frontend is served from same origin
    CORS(app, origins=[
        "http://localhost:5173", "http://localhost:5174",
        os.environ.get("RENDER_EXTERNAL_URL", ""),
    ])

    # Register blueprints
    app.register_blueprint(overview_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(vendors_bp)
    app.register_blueprint(departments_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(trends_bp)
    app.register_blueprint(contracts_bp)
    app.register_blueprint(network_bp)
    app.register_blueprint(donations_bp)

    # --- Error handlers ---

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    # Health check
    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    # Serve React app for all non-API routes (SPA routing)
    @app.errorhandler(404)
    def not_found(e):
        # If it's an API route, return JSON 404
        from flask import request as req
        if req.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        # Otherwise serve the React app
        if app.static_folder and os.path.exists(os.path.join(app.static_folder, "index.html")):
            return send_from_directory(app.static_folder, "index.html")
        return jsonify({"error": "Not found"}), 404

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=True)
