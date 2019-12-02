
import json
from typing import Dict

from flask import Response

from .. import db, socketio

from ..api import log

from ..models.user import User
from ..models.room import Room

from ..socket_logic import user_logic
from ..socket_logic import room_logic

from . import logger_crwiz, finite_state_machine, game_token
from .active_room import Subtask, ActiveRoom
from .utils import constants, post_task_analysis


class JSONResponse(Response):
	"""
	Template for a HTTP JSON Response that Flask will send back.
	This is the output of the TaskManager for the public-facing functions.
	"""

	def __init__(self, response_dict: dict = None, status=200, **kwargs):
		if 'mimetype' not in kwargs and 'contenttype' not in kwargs:
			kwargs['mimetype'] = 'application/json'

		if not response_dict:
			response_dict = {}

		super(JSONResponse, self).__init__(
			response=json.dumps(response_dict),
			status=status,
			**kwargs
		)

	@property
	def response_dict(self):
		return json.loads(self.response[0])

	def add_data(self, additional_data: dict, status: int = None):
		"""
		Add additional data to the TaskManager's response

		:param additional_data: dict with additional information
		:param status: status code (e.g. 200 for OK and 400 for BAD REQUEST)
		:return: None
		"""
		if status:
			self.set_status(status)

		if ('result' in additional_data and not additional_data['result']) \
			or ('success' in additional_data and not additional_data['success']):
			if self.status_code == 200:
				self.set_status(400)
			# raise ValueError("Trying to add data to response with invalid attribute")

		# load current response
		tmp_response = self.response_dict  # json.loads(self.response[0])
		# extend it with the additional data
		tmp_response.update(additional_data)
		# modify the response content
		self.set_data(json.dumps(tmp_response))

	def set_status(self, status_code: int):
		"""
		Sets the status code of the request.

		:param status_code: code (e.g. 200 for OK and 400 for BAD REQUEST)
		:return: None
		"""
		self.status_code = status_code


class TaskManager:

	def __init__(self):
		self.state_machine = finite_state_machine.FiniteStateMachine()
		self.active_rooms: Dict[str, ActiveRoom] = {}

	def __del__(self):
		"""
		Destroys the TaskManager, cancelling and cleaning any timeout_threads.

		:return:
		"""
		for room in self.active_rooms.values():
			room.cancel_timers()

	def initialise_room(self, room_name: str, user_id: int):
		"""
		Initialises a new room to manage for this TaskManager.
		It starts the finite state machine for this room too.

		:param room_name: name of the room
		:param user_id: id of the wizard for the room
		:return: None
		"""
		self.active_rooms[room_name] = ActiveRoom(
			room_name, user_id, self.timeout_task_timer)
		self.state_machine.initialise_room_fsa(self.active_rooms[room_name])

	def start_task_timer(self, room_name: str):
		"""
		Starts the countdown for the task in the room
		(e.g. 3 minutes until evacuation).

		:param room_name: name of the room
		:return: None
		"""
		self.active_rooms[room_name].start_task()
		# allow the operator to talk after wizard sends at least 1 message
		user_logic.update_user_permissions(
			{'message_text': True}, user_id=self.active_rooms[room_name].operator_id)

	def timeout_task_timer(self, room_name):
		"""
		Callback that gets triggered when a room has reached a timeout
		(e.g. when the dialogue didn't extinguish the fire so it's
		time to evacuate).

		:param room_name: name of the room
		:return: None
		"""
		if room_name in self.active_rooms:
			logger_crwiz.info(
				f"Timeout triggered for task in room '{room_name}'")
			self.close_active_room(self.active_rooms[room_name])

	def get_dialogue_options(self, user_id) -> JSONResponse:
		"""
		Gets a list of the possible dialogue options that the wizard
		can use in its current dialogue state.

		:param user_id: id of the wizard
		:return: JSONResponse with the list of utterances
		"""
		response = JSONResponse()

		room_name = self.get_room_name(user_id)
		if not room_name:
			logger_crwiz.error(f"Cannot find room for user {user_id}")
			response.add_data(
				{'reason': f"Cannot find room for user {user_id}"}, 400)
			return response

		if room_name not in self.active_rooms:
			self.initialise_room(room_name, user_id)

		elif self.active_rooms[room_name].task_finished:
			response.add_data(
				{'reason': f"Room task has already finished"}, 200)
			return response

		response.add_data(
			self.state_machine.get_current_state_utterances(
				self.active_rooms[room_name]
			))

		self.active_rooms[room_name].emit_status_update()
		return response

	def submit_dialogue_choice(self, user_id, state_name, text) -> JSONResponse:
		"""
		Submits a dialogue choice made by the wizard so the dialogue state
		for its current room can be updated.

		:param user_id: id of the wizard
		:param state_name: new dialogue state (from utterance)
		:param text: text used (e.g. may also be free text)
		:return: JSONResponse with media transitions (if any)
		"""
		response = JSONResponse()

		room_name = self.get_room_name(user_id)
		if not room_name:
			logger_crwiz.error(f"Cannot find room for user {user_id}")
			response.add_data(
				{'reason': f"Cannot find room for user {user_id}"}, 400)
			return response

		if not text or text == "":
			# text empty, so not valid to start with
			response.add_data({'reason': 'text is empty'}, 400)
			return response

		if self.active_rooms[room_name].task_finished:
			response.add_data(
				{'reason': f"Room task has already finished"}, 200)
			return response

		if state_name != "":
			response.add_data(
				self.state_machine.submit_dialogue_choice(
					self.active_rooms[room_name], state_name, text
				))

			if self.active_rooms[room_name].previous_state == \
				finite_state_machine.INITIAL_STATE:
				self.start_task_timer(room_name)

		self.active_rooms[room_name].emit_status_update()
		emit_dialogue_choices(self.active_rooms[room_name])
		return response

	def request_task_hint(self, user_id) -> JSONResponse:
		"""
		Requests a hint for the current user state and dialogue options.
		A hint is a guide to show what the next action should be.
		This hint does not have to be correct all the time, it uses
		probabilities for the most common action at that state.

		:param user_id: id of the wizard
		:return: JSONResponse with hint
		"""
		response = JSONResponse()

		room_name = self.get_room_name(user_id)
		if not room_name:
			logger_crwiz.error(f"Cannot find room for user {user_id}")
			response.add_data(
				{'reason': f"Cannot find room for user {user_id}"}, 400)
			return response

		hint, dialogue_choices = \
			self.state_machine.get_task_hint(self.active_rooms[room_name])

		response.add_data(hint)

		emit_dialogue_choices(
			self.active_rooms[room_name], JSONResponse(dialogue_choices))
		return response

	def close_active_room(
		self, active_room: ActiveRoom, user_triggered=False, **kwargs):
		if active_room.name in self.active_rooms \
				and not active_room.task_finished:
			active_room.task_finished = True
			active_room.timeout_thread = None
			logger_crwiz.info(f"Closing active room '{active_room.name}'")

			active_room.emit_status_update()

			# get a reason for the room closing
			# if reason is not empty, the HelperBot will give it to the participants
			reason = kwargs.get("reason", "")
			reason_id = kwargs.get("reason_id", "")
			if reason_id == "":
				if active_room.current_state == "inform_mission_completed":
					reason_id = constants.TASK_END_DIALOGUE
					# reason = "End of the dialogue reached"
				elif user_triggered:
					reason_id = constants.TASK_END_USER_TRIGGERED
					# reason = "A user decided to finish the game"
				elif active_room.current_subtask != Subtask.assess_damage:
					reason_id = constants.TASK_END_TIME_OUT
					reason = "Time out! The facility needs to evacuate immediately."
				else:
					reason_id = constants.TASK_END_UNSPECIFIED

			active_room.log_user_event(
				constants.EVENT_END_TASK,
				data={
					'reason_id': reason_id,
					'reason': reason
				}, user_id=2)

			# change the permissions of the users in the room
			# so they cannot send any more messages
			participants = {}
			for user_id in active_room.participants.keys():
				user = User.query.get(user_id)
				if not user:
					return False, "user does not exist"

				user_logic.update_user_permissions(
					{'message_text': False}, user=user)

				user.task_finished = db.func.current_timestamp()
				user.game_token = game_token.generate_token()
				db.session.commit()

				logger_crwiz.debug(
					f"User {user.id} '{user.name}' has finished its task")
				active_room.log_user_event(
					constants.EVENT_GENERATE_GAME_TOKEN,
					data={
						'game_token': user.game_token
					}, user_id=user.id)

				# send the game token so the HelperBot can give it away
				participants[user_id] = {
					'name': user.name, 'game_token': user.game_token
				}

			emit_close_room(active_room, participants=participants, reason=reason)

	def get_room_name(self, user_id):
		"""
		Gets the name of the room for the user.

		:param user_id: id of the wizard
		:return: name of the room as string or None
		"""
		for name, room in self.active_rooms.items():
			if room.wizard_id == user_id:
				return name

		# if we are here then it's the first time for this user, get from the DB
		room = User.query.get(user_id).get_task_room()
		# room not found
		if not room:
			return None
		return room.name


task_manager = TaskManager()


def emit_dialogue_choices(
	active_room: ActiveRoom, dialogue_options: JSONResponse = None, **kwargs):
	"""
	Sends a dialogue_choices message to the front-end to push
	an update of the dialogue choices available to the wizard.

	:param active_room: active room to use information from
	:param dialogue_options: response from the dialogue options
	:return: None
	"""
	# do not compute dialogue choices if they were already given
	if dialogue_options:
		response = dialogue_options
	else:
		response = task_manager.get_dialogue_options(active_room.wizard_id)

	socketio.emit("dialogue_choices", {
		'room_name': active_room.name,
		**response.get_json(),
		**kwargs
	}, room=active_room.name)


def emit_close_room(active_room: ActiveRoom, **kwargs):
	"""
	Sends a close_room message so the HelperBot hands out the Amazon Turk
	codes to the participants.

	:param active_room: active room to close
	:return: None
	"""
	post_task_analysis.perform_post_task_analysis(active_room.name)

	socketio.emit("close_room", {
		'room_name': active_room.name,
		**kwargs
	}, room=active_room.name)


@socketio.on('user_finish_task')
def _user_finish_task(data):
	"""
	Finishes the active room from the TaskManager. This event
	is triggered when either of the participants decide it is time
	to finish the task.

	:param data:
	:return:
	"""
	from flask_login import current_user

	user_id = data.get("user_id", None)
	room_name = data.get("room_name", None)

	if not current_user.get_id():
		logger_crwiz.warning("invalid session id")
		return False, "invalid session id"

	if user_id:
		user = User.query.get(user_id)
	else:
		user = current_user
	if not user or not user.session_id:
		logger_crwiz.warning(f"user does not exist")
		return False, "user does not exist"

	if room_name not in task_manager.active_rooms:
		logger_crwiz.warning(f"room '{room_name}' does not exist")
		return False, "room does not exist"

	if not task_manager.active_rooms[room_name].can_finish_task:
		logger_crwiz.warning(f"task in '{room_name}' cannot finish yet")
		return False, "task cannot finish yet"

	# if we reach this, the user is valid, the room exists and it can be finished
	# add participants, so it is easier for the HelperBot
	data['participants'] = task_manager.active_rooms[room_name].participants

	socketio.emit("user_finish_task", data, room=room_name)

	log.log_event(constants.EVENT_USER_END_TASK, user, Room.query.get(room_name), data={
		'seconds_since_start': task_manager.active_rooms[room_name].elapsed_seconds
	})

	task_manager.close_active_room(
		task_manager.active_rooms[room_name], user_triggered=True)

	return True


@socketio.on('close_room_on_disconnect')
def _close_room_on_user_disconnect(data):
	"""
	Triggered by the HelerBot when a user disconnects for too long

	:param data:
	:return:
	"""
	from flask_login import current_user

	room_name = data.get("room_name")
	user_id = data.get("disconnected_user_id")

	if not current_user.get_id():
		logger_crwiz.warning("invalid session id")
		return False, "invalid session id"

	if user_id:
		user = User.query.get(user_id)
	else:
		user = current_user
	if not user or not user.session_id:
		logger_crwiz.warning(f"user does not exist")
		return False, "user does not exist"

	if room_name not in task_manager.active_rooms:
		logger_crwiz.warning(f"room '{room_name}' does not exist")
		return False, "room does not exist"

	log.log_event(constants.EVENT_DISCONNECT_END_TASK, current_user, Room.query.get(room_name), data={
		'seconds_since_start': task_manager.active_rooms[room_name].elapsed_seconds,
		'disconnected_user_id': user_id
	})

	task_manager.close_active_room(
		task_manager.active_rooms[room_name], False,
		reason_id=constants.TASK_END_USER_DISCONNECTED,
		reason="Your partner has been away for too long, the game cannot continue."
	)

	return True


@socketio.on('close_room_feedback')
def _close_room_feedback(data):
	"""
	After closing the room, the HelperBot will send a close_room_feedback
	event with information that confirms that the room can be closed and
	the logs have been correctly saved.

	:param data:
	:return:
	"""
	room_name = data['room_name']

	# make room read only
	room_logic.update_room_properties({'read_only': True}, room_name=room_name)

	# starts a timer that will invalidate the participant's tokens after X time
	task_manager.active_rooms[room_name].start_token_timer(delete_room_from_task_manager)

	logger_crwiz.debug(f"Finished closing room '{room_name}")


def delete_room_from_task_manager(room_name):
	"""
	Deletes a room from the list of active rooms to free up space.
	This would often be the callback from the token timer.

	:param room_name: name of the room
	:return: None
	"""
	task_manager.active_rooms[room_name].invalidate_user_tokens()
	del task_manager.active_rooms[room_name]
	logger_crwiz.debug(
		f"Room {room_name} deleted from active rooms "
		f"{[room.name for room in task_manager.active_rooms.values()]}")
