import os
from flask import Flask
from api.routes import router
from config import DEBUG, BASE_DIR

# Create storage folders if they don't exist
# Needed for cloud deployment where filesystem is fresh on every boot
for folder in ["uploads", "charts", "reports", "logs"]:
    os.makedirs(os.path.join(BASE_DIR, "storage", folder), exist_ok=True)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

app.register_blueprint(router)

if __name__ == "__main__":
    app.run(debug=DEBUG, port=5000)