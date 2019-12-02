
import bson
from logging import getLogger

from ..crwiz.utils import constants


EVENTS_TO_IGNORE = [constants.EVENT_STATUS_UPDATE]


def log_event(event, user, room=None, data=None):
    from .. import db, Log

    if not data:
        data = {}

    if event == "join":
        message = f"User {user.id} '{user.name}' joined '{room.label}'"
    elif event == "leave":
        message = f"User {user.id} '{user.name}' left '{room.label}'"
    elif event == "connect":
        message = f"User {user.id} '{user.name}' connected"
    elif event == "disconnect":
        message = f"User {user.id} '{user.name}' disconnected"
    elif event == "set_user_role":
        message = f"User {user.id} '{user.name}' changed role to {data['role']}"
    elif event == "update_user_permissions":
        message = f"User {user.id} '{user.name}' has updated permissions"
    elif event == constants.EVENT_GENERATE_GAME_TOKEN:
        message = f"Game token {data['game_token']} generated for user {user.id}"
    else:
        # generic message
        user_id = data.get("user_id", None) \
            if "user_id" in data else data.get("user", None)
        message = f"Event {event} {'for' if user_id else 'from'} " \
                  f"user {user_id if user_id else user.id }"

    if 'message' in data \
            and ('\n' in data['message'] or '\t' in data['message']):
        getLogger("crwiz").warning(
            f"Message has invalid character(s): {data}")

    if event not in EVENTS_TO_IGNORE:
        getLogger("slurk").info(message)

    log = Log(event=event, user=user, room=room, data=bson.dumps(data))
    db.session.add(log)
    db.session.commit()
    return log
