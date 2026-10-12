from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.api.auth import bp as auth_bp
    from app.api.jobs import bp as jobs_bp
    from app.api.matches import bp as matches_bp
    from app.api.resumes import bp as resumes_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(jobs_bp, url_prefix="/api/jobs")
    app.register_blueprint(resumes_bp, url_prefix="/api/resumes")
    app.register_blueprint(matches_bp, url_prefix="/api")
