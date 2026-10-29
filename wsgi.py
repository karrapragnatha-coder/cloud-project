"""
WSGI entry point for production deployment of the MFA Token Simulator.
Works with production WSGI servers such as Gunicorn, uWSGI, Waitress, or AWS Elastic Beanstalk.
"""

from app import create_app
from config import Config

# Create the production application instance
application = create_app(Config)
app = application

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", "5000"))
    application.run(host="0.0.0.0", port=port)

