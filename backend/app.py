"""Flask application factory for the Chicago spending investigation API."""

import sys
from pathlib import Path

# Ensure project root is on sys.path so 'backend.*' imports work
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from flask import Flask, jsonify
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


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Enable CORS for the Vite dev server
    CORS(app, origins=["http://localhost:5173", "http://localhost:5174"])

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

    # --- Error handlers ---

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    # Health check
    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=True)
