
from flask_login import current_user

from .. import socketio, db

from ..models.room import Room
from ..models.user import User
from ..api import log


@socketio.on('status_update')
def _status_update(data):
	"""
	This redirects to the front-end several things about the status of the task,
	room and user
	E.g.: the user allowed to go for the next turn, the time left
	on the timer, etc.

	:param data:
	:return:
	"""
	room_id = data.get('room_id')

	if not current_user.get_id():
		return False, "invalid session id"
	if room_id and not current_user.token.permissions.user_room_leave:
		return False, "insufficient rights"

	room = Room.query.get(room_id)
	if not room:
		return False, "room does not exist"

	# log_event("status_update", user=current_user, room=room, data=data)

	socketio.emit("status_update", data, room=room_id)

	return True


@socketio.on('disable_user_input')
def _disable_user_input(data):
	"""
	This stops a user from being able to send a message to the other user in
	the chat room temporarily.

	:param data:
	:return:
	"""
	room_name = data.get("room_name")
	user_id = data.get("user_id")

	if not current_user.get_id():
		return False, "invalid session id"
	if room_name and not current_user.token.permissions.token_update:
		return False, "insufficient rights"

	room = Room.query.get(room_name)
	if not room:
		return False, "room does not exist"

	user = User.query.get(user_id)
	if not user:
		return False, "user does not exist"

	log.log_event("disable_user_input", user=current_user, room=room, data=data)

	socketio.emit("disable_user_input", data, room=room_name, user=user_id)

	return True


@socketio.on('enable_user_input')
def _enables_user_input(data):
	"""
	This allows a user to send chat messages to the other user
	again in the chat room.

	:param data:
	:return:
	"""
	room_name = data.get("room_name")
	user_id = data.get("user_id")

	if not current_user.get_id():
		return False, "invalid session id"
	if room_name and not current_user.token.permissions.token_update:
		return False, "insufficient rights"

	room = Room.query.get(room_name)
	if not room:
		return False, "room does not exist"

	user = User.query.get(user_id)
	if not user:
		return False, "user does not exist"

	log.log_event("enable_user_input", user=current_user, room=room, data=data)

	socketio.emit("enable_user_input", data, room=room_name, user=user_id)

	return True


@socketio.on('user_finished_task')
def _user_finished_task(data):
	"""
	This marks the user as finished with its task

	:param data:
	:return:
	"""
	room_name = data.get("room_name")
	user_id = data.get("user_id")

	if not current_user.get_id():
		return False, "invalid session id"
	if room_name and not current_user.token.permissions.token_update:
		return False, "insufficient rights"

	room = Room.query.get(room_name)
	if not room:
		return False, "room does not exist"

	user = User.query.get(user_id)
	if not user:
		return False, "user does not exist"

	user.task_finished = db.func.current_timestamp()

	log.log_event("user_finished_task", user=current_user, room=room, data=data)
	db.session.commit()

	return True
