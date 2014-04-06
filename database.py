from flask.ext.sqlalchemy import SQLAlchemy
import config as CONFIG

db = SQLAlchemy()


def init_db():
    db.create_all()