import os

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData

app = Flask(__name__, instance_relative_config=True)

app.config.from_pyfile(os.path.join(os.getcwd(), 'config.py'))

metadata = MetaData(
    naming_convention={
        "ix": 'ix_%(column_0_label)s',
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    }
)
db = SQLAlchemy(app, metadata=metadata)
with app.app_context():
    migrate = Migrate(app, db, render_as_batch=True)
from lpg import routes
from lpg import exception_routes
