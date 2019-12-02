
import json
import time
import logging
import datetime

import requests


LOG_DIR = "logs/task"
PARTNER_NOT_FOUND_LOG = "partner_not_found.json"


def get_room_logs(uri: str, token: str, room_name: str) -> dict:
	logs = requests.get(
		f"{uri}/room/{room_name}/logs",
		headers={'Authorization': f"Token {token}"})
	if not logs.ok:
		logging.warning(f"Could not get logs for room '{room_name}'")
		return {}

	# add metadata fields
	logs = {
		"name": room_name,
		"type": "log_room",
		"description": "Logs of all the events and messages in a room",
		"date_extracted": time.time(),
		"logs": logs.json()
	}

	return logs


def get_user_logs(uri: str, token: str, user_id: int) -> dict:
	logs = requests.get(
		f"{uri}/user/{user_id}/logs",
		headers={'Authorization': f"Token {token}"})
	if not logs.ok:
		logging.warning(f"Could not get logs for user '{user_id}'")
		return {}

	# add metadata fields
	logs = {
		"name": user_id,
		"type": "log_user",
		"description": "Logs of all the events and messages regarding a user",
		"date_extracted": time.time(),
		"logs": logs.json()
	}

	return logs


def export_logs(json_logs: dict, filename: str = None):
	if filename is None:
		date = datetime.datetime.utcfromtimestamp(json_logs['date_extracted'])
		filename = f"{date.strftime('%Y-%m-%d_%H-%M-%S')}_log_{json_logs['name']}"

	if not filename.endswith(".json"):
		filename += ".json"

	with open(f"{LOG_DIR}/{filename}", "w", encoding="utf-8") as f:
		json.dump(json_logs, f, ensure_ascii=False, indent=4)


def export_room_logs(uri: str, token: str, room_name: str):
	"""
	Shortcut to get and export the logs for a given room

	:param uri: uri of the host (e.g. localhost:5000/api/v2/)
	:param token: token of the entity that is retrieving the logs
	:param room_name: name of the room to export the logs
	:return: None
	"""
	export_logs(get_room_logs(uri, token, room_name))


def export_partner_not_found_log(user_id, game_token: str, seconds_waiting):
	try:
		with open(f"{LOG_DIR}/{PARTNER_NOT_FOUND_LOG}") as json_file:
			json_logs = json.load(json_file)
	except (FileNotFoundError, json.decoder.JSONDecodeError):
		json_logs = {}

	if json_logs == {}:
		json_logs = {
			"name": PARTNER_NOT_FOUND_LOG,
			"type": "log_list",
			"description": "Log with a list of users that could not be "
			"paired in the waiting room",
			"date_extracted": time.time(),
			"users": {}
		}

	json_logs['date_modified'] = time.time()
	json_logs['users'][f"{len(json_logs['users']) + 1}_{user_id}"] = {
		'user_id': user_id,
		'game_token': game_token,
		'seconds_waiting': seconds_waiting,
		'timestamp': json_logs['date_modified']
	}

	export_logs(json_logs, PARTNER_NOT_FOUND_LOG)
