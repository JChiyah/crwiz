
import enum
import collections

from .. import socketio

from ..api import log
from ..models.log import get_user_logs_for_event
from ..models.user import User
from ..models.room import get_room_user_messages

from .utils import dialogue_utils
from .active_room import ActiveRoom


_EVENT_ACTION_TRIGGERED = 'perform_action_triggered'
_EVENT_ACTION_RESPONSE = 'perform_action_response'


class ActionTrigger(enum.Enum):
	"""
	A full class to provide syntax highlighting in PyCharm due to Enum bug
	"""
	# no automatic trigger
	no_trigger = 1
	# as soon as state changes
	on_state_change = 2
	# as soon as the operator sends a message whilst on the state
	on_operator_message = 3


FakeAction = collections.namedtuple(
	'FakeAction', 'trigger name title body confirmBtn cancelBtn frontend_callback')


STATES_WITH_ACTIONS = {
	'trigger_popup': FakeAction(
		ActionTrigger.on_operator_message, 'trigger_popup', 'Example Pop-up',
		None, 'Do something', 'Cancel', None)
}


def state_contains_action(state_name: str) -> bool:
	return state_name in STATES_WITH_ACTIONS.keys()


def emit_action(active_room: ActiveRoom, action: FakeAction = None):
	if action is None:
		action = STATES_WITH_ACTIONS[active_room.current_state]

	if _check_action_trigger(active_room, action.name, action.trigger):
		action_data = {
			'action_name': action.name,
			'title': action.title,
			'confirmBtn': action.confirmBtn,
			'cancelBtn': action.cancelBtn,
			'frontend_callback': action.frontend_callback
		}
		if action.body is not None and action.body != "":
			action_data['body'] = action.body

		socketio.emit('perform_action', action_data, room=active_room.name)

		# logs a trigger for an action that requires the wizard's attention
		user = User.query.get(active_room.wizard_id)
		log.log_event(_EVENT_ACTION_TRIGGERED, user, user.get_task_room(), {
			'action_name': action.name,
			'state_name': active_room.current_state,
			'state_count': active_room.state_count,
			'trigger': action.trigger.name,
			'callback': action.frontend_callback
		})


def log_action_response(user_id, action_name: str, action_performed: bool):
	"""
	Logs a response from an action performed by the wizard.

	:param user_id: id of the wizard in the room
	:param action_name: name of the action
	:param action_performed: whether the action was performed
	:return: None
	"""
	user = User.query.get(user_id)
	log.log_event(_EVENT_ACTION_RESPONSE, user, user.get_task_room(), {
		'action_name': action_name,
		'action_performed': action_performed
	})


def _check_action_trigger(
	active_room: ActiveRoom, action_name: str, trigger: ActionTrigger) -> bool:
	if trigger == ActionTrigger.on_state_change \
		or trigger == ActionTrigger.no_trigger:
		return True
	elif trigger == ActionTrigger.on_operator_message:
		# first check if it has already triggered
		action_logs = get_user_logs_for_event(
			active_room.wizard_id, _EVENT_ACTION_TRIGGERED)

		# avoid showing pa announcement twice - hack to fix this bug
		for action_log in action_logs:
			if action_log['data']['action_name'] == 'pa_announcement':
				return False

		if len(action_logs) > 0 \
			and action_logs[0]['data']['action_name'] == action_name \
			and (action_logs[0]['data']['state_count'] == active_room.state_count
					or active_room.current_state == active_room.previous_state) \
			and action_logs[0]['data']['state_name'] == active_room.current_state:
			# action already triggered
			return False

		state_change_log = dialogue_utils.get_state_change_log_data(
			active_room.wizard_id, active_room.current_state)

		room_messages = get_room_user_messages(
			active_room.name, state_change_log['id'])

		for msg in room_messages:
			if msg['data']['message'] is not None \
				and msg['user']['id'] == active_room.operator_id:
				return True

		# no operator messages found

	return False
