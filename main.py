import os
from flask import Flask
from api.routes import router
from api.auth import auth, google_bp, github_bp
from config import DEBUG, BASE_DIR

# Create storage folders
for folder in ["uploads", "charts", "reports", "logs"]:
    os.makedirs(os.path.join(BASE_DIR, "storage", folder), exist_ok=True)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

# Register all blueprints
app.register_blueprint(router)
app.register_blueprint(auth)
app.register_blueprint(google_bp, url_prefix="/auth/google")
app.register_blueprint(github_bp, url_prefix="/auth/github")

# ✅ Debug route – MUST be after all blueprints are registered
@app.route("/debug/routes")
def debug_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append(f"{rule.endpoint} -> {rule.rule}")
    return "<br>".join(routes)

if __name__ == "__main__":
    app.run(debug=DEBUG, port=5000)