
from logging import getLogger

from flask_login import current_user
from flask_socketio import join_room, leave_room
import sqlalchemy.orm.exc

from .. import socketio, db

from ..models.room import Room
from ..models.user import User, UserRole
from ..api.log import log_event

from ..socket_logic import user_logic


@socketio.on('join_room')
def _join_room(data):
    user_id = data.get('user')
    room = data.get('room')

    if not current_user.get_id():
        return False, "invalid session id"
    if user_id and not current_user.token.permissions.user_room_join:
        return False, "insufficient rights"

    if user_id:
        user = User.query.get(user_id)
    else:
        user = current_user
    if not user or not user.session_id:
        return False, "user does not exist"

    room = Room.query.get(room)
    if not room:
        return False, "room does not exist"

    if room not in user.rooms:
        user.rooms.append(room)
    if room not in user.current_rooms:
        user.current_rooms.append(room)
        socketio.emit('joined_room', {
            'room': room.name,
            'user':  user.id,
        }, room=user.session_id)
        log_event("join", user, room)
    db.session.commit()

    join_room(room.name, user.session_id)

    # getLogger("slurk").info(f"User {user.id} joined room '{room.name}'")

    return True


@socketio.on('leave_room')
def _leave_room(data):
    user_id = data.get('user')
    room = data.get('room')

    if not current_user.get_id():
        return False, "invalid session id"
    if user_id and not current_user.token.permissions.user_room_leave:
        return False, "insufficient rights"

    if user_id:
        user = User.query.get(user_id)
    else:
        user = current_user
    if not user or not user.session_id:
        return False, "user does not exist"

    room = Room.query.get(room)
    if not room:
        return False, "room does not exist"

    try:
        # this will often raise an exception if the user has left the room
        user.rooms.remove(room)
        user.current_rooms.remove(room)
        db.session.commit()
    except sqlalchemy.orm.exc.StaleDataError as ex:
        db.session.rollback()
        getLogger("slurk").warning(f"Error trying to execute statement: {ex}")

    socketio.emit("left_room", room.name, room=user.session_id)
    log_event("leave", user, room)
    leave_room(room.name, user.session_id)

    # getLogger("slurk").info(f"User {user.id} left room '{room.name}'")

    return True


@socketio.on('set_user_role')
def _set_role(data):
    user_id = data.get('user_id')
    role_id = data.get('role_id')

    if not current_user.get_id():
        return False, "invalid session id"
    if user_id and not current_user.token.permissions.token_update:
        return False, "insufficient rights"

    if user_id:
        user = User.query.get(user_id)
    else:
        user = current_user
    if not user or not user.session_id:
        return False, "user does not exist"

    role = UserRole.get_from_value(role_id)
    if not role:
        return False, "role does not exist"

    user.role = role
    log_event("set_user_role", user, data={"role": str(user.role)})
    db.session.commit()

    socketio.emit("set_user_role", str(user.role), room=user.session_id)

    return True


@socketio.on('update_user_permissions')
def _update_permissions(data):
    # pop the id, so we have a dict of only permissions
    user_id = data.pop('user_id', None)

    if not current_user.get_id():
        return False, "invalid session id"
    if user_id and not current_user.token.permissions.token_update:
        return False, "insufficient rights"

    if user_id:
        user = User.query.get(user_id)
    else:
        user = current_user
    if not user or not user.session_id:
        return False, "user does not exist"

    user_logic.update_user_permissions(data, user=user)

    return True


@socketio.on('invalidate_user_token')
def _invalidate_user_token(data):
    raise DeprecationWarning("Deprecated socketio event")
    # user_id = data.get('user_id')
	#
    # if not current_user.get_id():
    #     return False, "invalid session id"
    # if user_id and not current_user.token.permissions.token_invalidate:
    #     return False, "insufficient rights"
	#
    # if user_id:
    #     user = User.query.get(user_id)
    # else:
    #     user = current_user
    # if not user or not user.session_id:
    #     return False, "user does not exist"
	#
    # user.token.valid = False
	#
    # log_event("invalidate_user_token", user, data=data)
    # db.session.commit()
	#
    # getLogger("orca-slurk").info(f"Token invalidated for user {user.id}")
	#
    # return True
