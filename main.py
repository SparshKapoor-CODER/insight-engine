from flask import Flask
from api.routes import router
from config import DEBUG

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max upload

app.register_blueprint(router)

if __name__ == "__main__":
    app.run(debug=DEBUG, port=5000)