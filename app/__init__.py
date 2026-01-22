from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS

from .config import Config
from .extensions import db, migrate, login_manager
from .utils.time import fmt_dt_local, fmt_dt_input_local


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    # Extensions
    CORS(app)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Blueprints
    from .auth.routes import bp as auth_bp
    from .admin.routes import bp as admin_bp
    from .public.routes import bp as public_bp
    from .api.routes import bp as api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(api_bp)

    # Jinja filters: Mexico local time
    app.jinja_env.filters["mx_dt"] = lambda dt, fmt="%Y-%m-%d %H:%M": fmt_dt_local(dt, app.config.get("TIME_ZONE"), fmt)
    app.jinja_env.filters["mx_dt_input"] = lambda dt: fmt_dt_input_local(dt, app.config.get("TIME_ZONE"))

    # Health check
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app
