import os
import sys
import time
import subprocess
import logging.config
from logging import getLogger

from flask import Flask, request, flash, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
import flask_socketio
from flask_socketio import SocketIO

# print(flask_socketio.__version__)
# exit()
import pymysql.err
import sqlalchemy.exc
from sqlalchemy import event
from sqlalchemy.engine import Engine

from .settings import Settings


root_folder = os.path.join(os.path.split(os.path.abspath(__file__))[0], "..")
logging.config.fileConfig(
    fname=os.path.join(root_folder, "app", "logging.conf"),
    disable_existing_loggers=False,
    defaults={'logfilename': os.path.join(root_folder, "logs", "app", "crwiz.log")}
)
getLogger("slurk").info("Logging config loaded. Starting up Slurk...")

DEBUG = False

socketio = SocketIO(ping_interval=5, ping_timeout=120, async_mode="gevent")


app = Flask(__name__)
app.config.from_object('config')

db = SQLAlchemy(app)
settings = Settings.from_object('config')
login_manager = LoginManager()


from .models.room import Room
from .models.token import Token
from .models.layout import Layout
from .models.permission import Permissions
from .models.state_history import StateHistory
from .models.task import Task
from .models.log import Log


# Try to connect to the database. If it cannot succeed after a
# few attempts then the program will finish
connected_to_db = False
attempts = 0
while not connected_to_db:
    try:
        if settings.drop_database_on_startup:
            db.drop_all()
        db.create_all()
        connected_to_db = True
    except (pymysql.err.OperationalError, pymysql.err.InternalError,
            sqlalchemy.exc.InternalError, sqlalchemy.exc.OperationalError,
            ConnectionRefusedError):
        if attempts >= 10:
            getLogger("crwiz").critical(
                f"Unable to connect to database at {settings.database_url} "
                f"after {attempts} attempts. Shutting down the program...")
            sys.exit(4)
        else:
            getLogger("crwiz").warning(
                f"Unable to connect to database at '{settings.database_url}'. "
                f"Retrying...")
            time.sleep(1)
            attempts += 1
    except Exception as ex:
        getLogger("crwiz").critical(
            f"There was an unexpected exception: {ex}", exc_info=True)
        getLogger("crwiz").critical(f"Shutting down the program...")
        sys.exit(4)


from .api import api as api_blueprint
from .api import close_rooms
from .login import login as login_blueprint
from .chat import chat as chat_blueprint
from .portal import portal as portal_blueprint

app.register_blueprint(api_blueprint)
app.register_blueprint(portal_blueprint)
app.register_blueprint(login_blueprint)
app.register_blueprint(chat_blueprint)


login_manager.init_app(app)
login_manager.login_view = 'login.index'
socketio.init_app(app)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, _connection_record):
    if settings.database_url.startswith('sqlite://'):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@app.before_request
def before_request():
    if request.endpoint and request.endpoint.startswith("api."):
        return

    if not current_user.is_authenticated \
        and request.endpoint not in ["login.index", "static", "portal.index", "admin.index"]:
        # if DEBUG, then redirect to the portal to perform an auto login
        if DEBUG:
            return redirect(url_for("portal.index"))
        # otherwise say it's unauthorised
        return login_manager.unauthorized()


if not Room.query.get("admin_room"):
    db.session.add(Room(name="admin_room",
                        label="Admin Room",
                        layout=Layout.from_json_file("default"),
                        static=True))
    db.session.add(Token(room_name='admin_room',
                         id='00000000-0000-0000-0000-000000000000' if settings.debug else None,
                         permissions=Permissions(
                             user_query=True,
                             user_log_event=True,
                             user_room_join=True,
                             user_room_leave=True,
                             message_text=True,
                             message_image=True,
                             message_command=True,
                             message_broadcast=True,
                             room_query=True,
                             room_log_query=True,
                             room_create=True,
                             room_update=True,
                             room_delete=True,
                             layout_query=True,
                             layout_create=True,
                             layout_update=True,
                             task_create=True,
                             task_query=True,
                             task_update=True,
                             token_generate=True,
                             token_query=True,
                             token_invalidate=True,
                             token_update=True,
                         )))
    db.session.commit()
    getLogger("slurk").debug("Generating admin room and token...")

admin_token = Token.query.order_by(Token.date_created).first().id

getLogger("slurk").debug(f"Admin token: ['{admin_token}']")

sys.stdout.flush()

from .crwiz import init_crwiz, logger_crwiz, stop_bots
init_crwiz()

logger_crwiz.info("Ready")
