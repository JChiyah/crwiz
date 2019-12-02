
from app.models.log import get_user_logs_for_event

from . import constants


def get_latest_utterance_data(user_id, utterance_id: str):
	"""
	Gets the latest data for an utterance_id for a given user.
	As the utterance_id is not unique, it will only return the latest
	one from the logs from the event 'fsa_get_state_transitions'.

	:param user_id: id of the user (wizard id)
	:param utterance_id: id of the utterance after preProcess (e.g. intro_0)
	:return: dict with the utterance data
	"""
	logs = get_user_logs_for_event(user_id, constants.EVENT_FSM_GET_TRANSITIONS)

	for log in logs:
		for utterance in log['data']['possible_utterances']:
			if utterance['utterance_id'] == utterance_id:
				return utterance

	return None


def get_utterance_data_from_state(user_id, state_name: str):
	"""
	Gets the latest utterance data for the last time an
	utterance was generated from the state_name.
	For instance, if the state_name is 'inform_moving' then
	it will return the data for the utterance 'inform_moving_0'.

	:param user_id: id of the user (wizard id)
	:param state_name: name for the state
	:return: dict with the utterance data
	"""
	logs = get_user_logs_for_event(user_id, constants.EVENT_FSM_GET_TRANSITIONS)

	for log in logs:
		for utterance in log['data']['possible_utterances']:
			if utterance['utterance_id'][:-2] == state_name:
				return utterance

	return None


def get_state_change_log_data(user_id, state_name: str) -> dict:
	"""
	Gets the logged data for the state change
	of a particular state.
	It will always return the latest log.

	:param user_id: id of the user (wizard id)
	:param state_name: name of the state
	:return: dict with the log data
	"""
	state_logs = get_user_logs_for_event(user_id, constants.EVENT_FSM_CHANGE_STATE)

	for log in state_logs:
		if log['data']['current_state'] == state_name:
			return log


def get_user_dialogue_state(user_id) -> str:
	"""
	Returns the current dialogue state for a user.

	:param user_id: id of the user (wizard id)
	:return: name of the state
	"""
	return get_user_logs_for_event(
		user_id, constants.EVENT_FSM_CHANGE_STATE)[0]['data']['current_state']
