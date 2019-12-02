
import enum
import threading
from typing import List, Tuple, Callable

from .. import socketio

from ..api import log

from ..models.user import User, get_user_messages
from ..models.room import Room

from ..socket_logic import user_logic

from . import logger_crwiz
from .utils import helper, constants


class Subtask(enum.Enum):
	"""
	A full class to provide syntax highlighting in PyCharm due to Enum bug
	"""
	inspect = 1
	extinguish = 2
	assess_damage = 3


SUBTASK_START = Subtask.inspect

MISSION_TIME = 6 * 60   # 6 minutes

# Min number of turns until users can finish the game (if Subtask.assess_damage)
# 14 is the minimum amount of turns to reach that point, so 15 means that they
# sent at least 1 additional message
MINIMUM_USER_TURNS = 15

SUBTASK_THRESHOLD = 30  # means each subtask accounts for 30% of progress


class ActiveRoom:

	def __init__(
		self, room_name: str, wizard_id, timeout_callback: Callable):
		self.name: str = room_name
		self.wizard_id = wizard_id
		self.room_timer_callback = timeout_callback

		self.task_finished = False
		self.start_time = None
		self.end_time = None
		self.set_end_time(MISSION_TIME, start_timer=False)

		self.subtask_stack: List[Tuple[Subtask, float]] = []
		self.last_analysed_msg: int = 0
		self._current_state: str = ""
		self.previous_state_stack: List[str] = []
		self.current_state_hint = None
		self.progress = 0
		self._room_timer = None
		self._token_timer = None
		self._operator_id = None

		room = Room.query.get(room_name)
		self._users = {}
		for user in list(room.users):
			self._users[user.id] = {
				'utterances': 0,
				'name': user.name
			}

	@property
	def operator_id(self) -> int:
		if self._operator_id is not None:
			return self._operator_id
		else:
			# try to resolve the operator id
			try:
				self._operator_id = [
					user for user in self.participants if
					user != self.wizard_id][-1]
				return self.operator_id
			except IndexError:
				logger_crwiz.critical(f"Cannot find the operator in room {self.name}")
				# quick hack for now...
				return self.wizard_id+1

	@property
	def current_state(self) -> str:
		"""
		Returns the current state of the room.

		:return: state name
		"""
		return self._current_state

	@current_state.setter
	def current_state(self, val: str):
		self.previous_state = self.current_state
		self._current_state = val
		if self.previous_state != self.current_state:
			self.check_current_state_for_milestones()
			self.current_state_hint = None

	@property
	def previous_state(self) -> str:
		"""
		Returns the previous state of the room.

		:return: state name
		"""
		if len(self.previous_state_stack) > 0:
			for state in reversed(self.previous_state_stack):
				return state
		return ''

	@previous_state.setter
	def previous_state(self, val: str):
		self.previous_state_stack.append(val)

	@property
	def state_count(self) -> int:
		"""
		Returns the count of states passed up to this point.
		It can be used to compare if we are revisiting a state.

		:return: int, number of states
		"""
		return len(self.previous_state_stack) + 1

	@property
	def remaining_seconds(self) -> int:
		if self.room_timer:
			secs = self.end_time - helper.get_unix_timestamp()
		else:
			secs = MISSION_TIME
		return int(secs) if secs > 0 else 0

	@property
	def elapsed_seconds(self):
		if self.start_time:
			secs = helper.get_unix_timestamp() - self.start_time
		else:
			secs = 0
		return secs if secs > 0 else 0

	@property
	def current_subtask(self) -> Subtask:
		if len(self.subtask_stack) > 0:
			return self.subtask_stack[-1][0]
		else:
			return SUBTASK_START

	def advance_subtask(self, subtask: Subtask):
		if subtask != self.current_subtask or len(self.subtask_stack) == 0:
			self.subtask_stack.append((subtask, helper.get_unix_timestamp()))
			self.log_user_event(constants.EVENT_ADVANCE_SUBTASK, {
				'current_subtask': self.current_subtask.name
			})
		else:
			logger_crwiz.warning(
				f"Trying to advance to the same subtask: {self.current_subtask}")

	@property
	def room_timer(self):
		return self._room_timer

	@room_timer.setter
	def room_timer(self, new_thread):
		if self._room_timer is not None:
			self._room_timer.cancel()
			logger_crwiz.debug(f"Timeout for room '{self.name}' cancelled")
		self._room_timer = new_thread

	@property
	def users(self):
		"""
		Returns all the users in the active room (this includes the bots).

		:return: dict with {'user_id': 'user_name'}
		"""
		tmp = {}
		for user_id in self._users.keys():
			tmp[user_id] = self._users[user_id]['name']
		return tmp

	@property
	def participants(self):
		"""
		Returns the task participants in the active room
		(this does NOT include the bots), only people.

		:return: dict with {'user_id', 'user_name'}
		"""
		users = self.users
		bot_ids = [1, 2]
		for bot_id in bot_ids:
			if bot_id in users:
				del users[bot_id]
			elif str(bot_id) in users:
				del users[str(bot_id)]
		return users

	@property
	def can_finish_task(self):
		self._update_user_utterances()
		return sum([user['utterances'] for user in self._users.values()]) >= \
			MINIMUM_USER_TURNS and self.current_subtask == Subtask.assess_damage

	def _update_user_utterances(self):
		for user_id in self._users.keys():
			self._users[user_id]['utterances'] = max(
				self._users[user_id]['utterances'], len(get_user_messages(user_id)))

	def check_state_for_milestones(self, state_name):
		"""
		Checks if the state of the user in the dialogue is
		a milestone (e.g. has finished the game)

		:param state_name: current state of the user
		:return:
		"""
		if state_name == 'inform_end':
			self.progress = 1
			# trigger the end of the task in 1 second...
			self.set_end_time(1)
		else:
			# increase progress a little if it is not too close to SUBTASK_THRESHOLD
			if int((self.progress + 0.015*1.5) * 100 / SUBTASK_THRESHOLD) == \
				int(self.progress * 100 / SUBTASK_THRESHOLD):
				self.progress += 0.015
			if self.progress > 0.95:
				self.progress = 0.95

	def check_current_state_for_milestones(self):
		"""
		Checks if the current state of the user in the dialogue is
		a milestone (e.g. has passed from extinguish fire to
		assess the damage

		:return:
		"""
		self.check_state_for_milestones(self.current_state)

	def set_end_time(self, seconds, start_timer=True):
		if seconds > 0:
			self.end_time = helper.get_unix_timestamp() + seconds
			if start_timer:
				self.room_timer = threading.Timer(
					seconds+1, self.room_timer_callback, [self.name])
				self.room_timer.start()
				logger_crwiz.debug(
					f"New timeout set for room '{self.name}' in {seconds} seconds")

	def start_task(self):
		self.start_time = helper.get_unix_timestamp()
		self.log_user_event(constants.EVENT_START_TASK, {
			'mission_start': self.start_time,
			'users': self.users
		})
		self.advance_subtask(SUBTASK_START)
		self.set_end_time(MISSION_TIME)

	def start_token_timer(self, timeout_callback: Callable):
		# timeout in 5 minutes
		self._token_timer = threading.Timer(5 * 60, timeout_callback, [self.name])
		self._token_timer.start()

	def invalidate_user_tokens(self):
		"""
		Triggered once the token_timer timeouts. It invalidates
		all the user's token so they cannot log in again.

		:return: None
		"""
		for user_id in self.participants.keys():
			user_logic.update_user_token_validity(False, user_id=user_id)

	def cancel_timers(self):
		"""
		Cancels all the room's timers (possibly due to the program closing).

		:return: None
		"""
		if self.room_timer is not None:
			self.room_timer = None
		if self._token_timer is not None:
			self._token_timer.cancel()
			self._token_timer = None

	def emit_status_update(self, source: str = None, *args, **kwargs):
		"""
		Sends a status_update message to the users in this active room.

		:return: None
		"""
		emit_data = {
			'start_time': self.start_time,
			'remaining_seconds': self.remaining_seconds,
			'can_finish_task': self.can_finish_task,
			'task_progress': self.progress * 100,
			'users': self.users,
			'user_turns': False
		}

		if self.start_time is None:
			emit_data['operator_wait'] = {
				'user_id': self.operator_id,
				'reason': 'Wait for Fred to start the conversation'
			}

		if source is not None:
			self.log_user_event(
				constants.EVENT_STATUS_UPDATE,
				data={
					**emit_data,
					'source': source
				})

		socketio.emit('status_update', emit_data, room=self.name)

	def log_user_event(self, event_name: str, data: dict, user_id=None):
		"""
		Logs an event happening in the current room under the wizard id.

		:param event_name: name of the event to log
		:param data: additional data to log
		:param user_id: optional user id,
			if None, the event is assigned to the wizard of the room
		:return: None
		"""
		data['seconds_since_start'] = self.elapsed_seconds
		if user_id is None:
			user_id = self.wizard_id
		this_user = User.query.get(user_id)
		log.log_event(
			event_name, user=this_user, room=Room.query.get(self.name), data=data)
