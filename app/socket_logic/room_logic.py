
from .. import db, socketio

from ..models.room import Room

from ..crwiz import logger_crwiz


def update_room_properties(
		properties: dict, *, room_name: str = None, room: Room = None):
	"""
	Updates a property of a room.

	:param properties: dict with the property names and the new values
	:param room_name: name of the room
	:param room: Room object
	:return: None
	"""
	if room_name:
		room = Room.query.get(room_name)

	if not room:
		logger_crwiz.warning("No room found to update properties")
		return False

	for key in properties.keys():
		try:
			setattr(room, key, properties[key])
		except Exception as ex:
			logger_crwiz.exception(
				f"Error trying to change room property '{key}': {ex}")

	# log_event("update_room_properties", user=current_user, room=room, data=data)
	db.session.commit()

	socketio.emit("update_room_properties", properties, room=room_name)

	logger_crwiz.info(f"Updated room '{room_name}' properties: '{properties}'")
