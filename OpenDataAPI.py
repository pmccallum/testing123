import config as CONFIG
from apiv1_2 import api as APIv1_2
from flask import Flask, render_template


# Instantiate app
app = Flask(__name__)

# Load config from config file
app.config.from_object(CONFIG)

# Register all routes from blueprint in views.py
app.register_blueprint(APIv1_2)


@app.route('/')
def index():
    return render_template("index.html")

if __name__ == '__main__':
    # Run app with host accepting requests from all IPs
    app.run(debug=CONFIG.DEBUG, host='0.0.0.0')
