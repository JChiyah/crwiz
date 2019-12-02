
import datetime

from ...api.log import log_event

from ...models.log import get_room_logs_for_event, get_user_logs_for_event
from ...models.user import User, get_user_messages
from ...models.room import Room, get_room_user_messages

from . import constants


_HELPER_BOT_ID = 2


def perform_post_task_analysis(room_name: str):
	start_log = get_room_logs_for_event(room_name, constants.EVENT_START_TASK)
	end_log = get_room_logs_for_event(room_name, constants.EVENT_END_TASK)
	participants = _get_room_participants(room_name)

	if len(start_log) == len(end_log) == len(participants.keys()) == 0:
		log_event(
			'post_task_analysis_room_not_found', user=User.query.get(_HELPER_BOT_ID),
			data={
				'error': 'Cannot find room to perform post-task analysis',
				'room_name': room_name})
		return {}

	data = {
		'mission_start_time':
			start_log[0]['date_created'] if len(start_log) > 0 else '',
		'mission_end_time':
			end_log[0]['date_created'] if len(end_log) > 0 else '',
		'mission_elapsed_time':
			end_log[0]['date_created'] - start_log[0]['date_created']
			if len(start_log) + len(end_log) > 1 else 0,
		'subtask_inspect': _get_subtask_information(room_name, 'inspect'),
		'subtask_extinguish': _get_subtask_information(room_name, 'extinguish'),
		'subtask_assess_damage': _get_subtask_information(room_name, 'assess_damage'),
		'mission_end_reason': {
			'id': end_log[0]['data']['reason_id'] if len(end_log) > 0 else '',
			'description': end_log[0]['data']['reason'] if len(end_log) > 0 else ''
		},
		'participant_wizard': _get_user_message_information(
			participants['fred']) if 'fred' in participants else None,
		'participant_operator': _get_user_message_information(
			participants['operator']) if 'operator' in participants else None,
		# 'quiz_operator': _get_operator_quiz_information(
		# 	participants['operator']) if 'operator' in participants else None,
		'dialogue_summary': _get_dialogue_summary(room_name)
	}

	mission_subtask = get_room_logs_for_event(
		room_name, constants.EVENT_ADVANCE_SUBTASK)
	data['mission_subtask'] = mission_subtask[0]['data']['current_subtask'] \
		if len(mission_subtask) > 0 else 'inspect'
	data['mission_successful'] = data['mission_subtask'] == 'assess_damage'

	first_ever_msg = data['participant_wizard']
	if 'last_message' in data['participant_wizard'] \
		and data['participant_operator'] \
		and 'last_message' not in data['participant_operator']:
		last_ever_msg = data['participant_wizard']
	elif 'last_message' in data['participant_wizard'] \
		and data['participant_operator'] \
		and 'last_message' in data['participant_operator']:
		last_ever_msg = data['participant_wizard'] \
			if data['participant_wizard']['last_message']['message_log_id'] \
				> data['participant_operator']['last_message']['message_log_id'] \
			else data['participant_operator']
	else:
		last_ever_msg = first_ever_msg

	# get analysis for all messages
	if 'first_message' in first_ever_msg:
		data['overall_messages'] = {
			'first_message': {
				'user_id': first_ever_msg['user_id'],
				**first_ever_msg['first_message']
			},
			'last_message': {
				'user_id': last_ever_msg['user_id'],
				**last_ever_msg['last_message']
			},
			'first_last_elapsed_time': last_ever_msg['last_message']['timestamp']
			- first_ever_msg['first_message']['timestamp'],
			'total_turns': data['participant_wizard']['total_turns']
			+ (data['participant_operator']['total_turns']
						if data['participant_operator'] else 0)
		}

	# perform adjustment to the wizard turns in inspect subtask
	# the first message ("Hi! I'm Fred...") does not count for
	# the inspect subtask, it initiates it
	if data['subtask_inspect'] and 'messages' in data['subtask_inspect']:
		data['subtask_inspect']['messages']['wizard_turns'] += 1

	log_event(
		constants.EVENT_POST_TASK_ANALYSIS,
		user=User.query.get(_HELPER_BOT_ID),
		room=Room.query.get(room_name),
		data=data)

	return data


def _get_room_participants(room_name: str) -> dict:
	join_logs = get_room_logs_for_event(room_name, "join")

	participants = {}
	for msg in join_logs:
		if msg['user']['id'] > 2 and msg['user']['id'] not in participants:
			participants[msg['user']['name'].lower()] = msg['user']['id']

	return participants


def _get_user_message_information(user_id) -> dict:
	this_user = User.query.get(user_id)
	user_messages = get_user_messages(user_id, order_desc=False)

	data = {
		'user_id': user_id,
		'game_token': this_user.game_token if this_user else '',
		'total_turns': len(user_messages),
		'total_words': sum([
			len(msg['data']['message'].split(' ')) for msg in user_messages])
	}

	data['mean_words_per_turn'] = data['total_words'] / data['total_turns'] \
		if data['total_turns'] > 0 else 0

	if len(user_messages):
		first_msg = user_messages[0]
		last_msg = user_messages[-1]

		data['first_message'] = {
			'timestamp': first_msg['date_created'],
			'seconds_since_start': first_msg['data']['seconds_since_start'],
			'message': first_msg['data']['message'],
			'message_log_id': first_msg['id']
		}
		data['last_message'] = {
			'timestamp': last_msg['date_created'],
			'seconds_since_start': last_msg['data']['seconds_since_start'],
			'message': last_msg['data']['message'],
			'message_log_id': last_msg['id']
		}

	disconnected_log = get_user_logs_for_event(
		2, constants.EVENT_DISCONNECT_END_TASK)
	data['disconnected'] = len(disconnected_log) > 0 \
		and disconnected_log[0]['data']['disconnected_user_id'] == user_id

	return data


def _get_subtask_information(room_name: str, subtask_name: str) -> dict:
	end_log = get_room_logs_for_event(room_name, constants.EVENT_END_TASK)
	subtask_logs = get_room_logs_for_event(
		room_name, constants.EVENT_ADVANCE_SUBTASK, order_desc=False)

	subtask_start = None
	subtask_end = None
	for subtask_log in subtask_logs:
		if subtask_log['data']['current_subtask'] == subtask_name:
			# trigger at next iteration
			subtask_start = subtask_log
		elif subtask_start is not None:
			subtask_end = subtask_log
			break

	if subtask_start is not None:
		if subtask_end is None:
			subtask_end = end_log[0] if len(end_log) > 0 else subtask_start

		user_messages = get_room_user_messages(room_name, subtask_start['id'])
		user_messages = [
			msg for msg in user_messages if msg['id'] <= subtask_end['id']]

		return {
			'subtask_elapsed_time': subtask_end['data']['seconds_since_start']
			- subtask_start['data']['seconds_since_start'],
			'subtask_start_time': {
				'timestamp': subtask_start['date_created'],
				'seconds_since_start': subtask_start['data']['seconds_since_start']
			},
			'subtask_end_time': {
				'timestamp': subtask_end['date_created'],
				'seconds_since_start': subtask_end['data']['seconds_since_start']
			},
			'messages': {
				'operator_turns': len([
					msg for msg in user_messages if msg['user']['name'] == 'Operator']),
				'wizard_turns': len([
					msg for msg in user_messages if msg['user']['name'] == 'Fred']),
			}
		}

	return {}


def _get_dialogue_summary(room_name: str) -> dict:
	user_messages = get_room_user_messages(room_name, bot_msgs=True)

	dialogue = {}

	for msg in user_messages:
		time_val = datetime.datetime.fromtimestamp(msg['date_created'])\
			.strftime('%H:%M:%S')
		dialogue[f"{time_val}_{msg['user']['name'][:4]}_{msg['id']}"] = \
			msg['data']['message']

	return dialogue
