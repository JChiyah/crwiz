# -*- coding: utf-8 -*-

"""
CRWIZ
----

Creates the layouts, rooms, tasks and other stuff needed for CRWIZ when slurk
is initialised (if these things do not exist)

Author: Javier Chiyah, Heriot-Watt University, 2019
"""

import os
import sys
import logging
import subprocess

from .. import db, DEBUG

from ..models.room import Room, ROOM_NAME_TASK
from ..models.user import User, UserRole
from ..models.layout import Layout
from ..models.task import TASK_NAME_WIZARD

from app.crwiz.utils.token_utils import *


logger_crwiz: logging.Logger = logging.getLogger('crwiz')


root_folder = os.path.join(os.path.split(os.path.abspath(__file__))[0], "..", "..")
# list of bots to automatically start with the server
BOT_LIST = [
	os.path.join(root_folder, "bots", "concierge", "concierge.py"),
	os.path.join(root_folder, "bots", "helper", "helperbot.py")
]

_bot_processes = []


_wizard_task = None
_bot_tokens = []


def init_crwiz():
	_create_rooms()
	_create_tasks()
	db.session.commit()

	_generate_bot_tokens()
	_generate_user_tokens()
	db.session.commit()

	_start_bots()


def _create_rooms():
	# create layout first
	waiting_layout = Layout.query.filter(Layout.name == ROOM_NAME_WAITING).first()
	if not waiting_layout:
		waiting_layout = Layout.from_json_file(ROOM_NAME_WAITING)
		db.session.add(waiting_layout)
		db.session.flush()

	if not Room.query.get(ROOM_NAME_WAITING):
		db.session.add(Room(
			name=ROOM_NAME_WAITING,
			label="Waiting Room",
			# read_only=True,
			static=True,
			layout_id=waiting_layout.id))
		db.session.commit()

	# check all rooms
	# print([room.as_dict() for room in Room.query.all()])


def _create_tasks():
	global _wizard_task
	# create layout first
	task_layout = Layout.query.filter(Layout.name == ROOM_NAME_TASK).first()
	if not task_layout:
		task_layout = Layout.from_json_file(ROOM_NAME_TASK)
		db.session.add(task_layout)
		db.session.flush()

	if not Task.query.get(TASK_NAME_WIZARD):
		_wizard_task = Task(
			name=TASK_NAME_WIZARD,
			num_users=2,
			layout_id=task_layout.id)
		db.session.add(_wizard_task)
		db.session.flush()

	# check all tasks
	# print([task.as_dict() for task in Task.query.all()])
	# get wizard task id from the database
	_wizard_task = get_wizard_task()
	logger_crwiz.debug(f"Wizard task id: {_wizard_task.id}")


def _generate_bot_tokens():
	for i in range(len(BOT_LIST)):
		# check if a token for the bot already exists
		bot_token = Token.query.filter(Token.user_id == i+1).first()
		if not bot_token:
			# does not exists -> create new
			_bot_tokens.append(Token(
				room_name=ROOM_NAME_WAITING,
				id=None,
				user_id=None,
				permissions=Permissions(
					user_query=True,
					user_log_event=True,
					user_room_join=True,
					user_room_leave=True,
					message_text=True,
					message_image=True,
					message_command=True,
					message_broadcast=True,
					room_query=True,
					room_log_query=True,
					room_create=True,
					room_update=True,
					room_delete=True,
					layout_query=True,
					layout_create=True,
					layout_update=True,
					task_create=True,
					task_query=True,
					task_update=True,
					token_generate=True,
					token_query=True,
					token_invalidate=True,
					token_update=True,
				)))

			# add the token to the DB
			db.session.add(_bot_tokens[-1])
			# commit the token so it generates the token id
			db.session.commit()

			# create user now so the bots always have the smallest IDs
			user = User(
				name="HelperBot" if i > 0 else "ConciergeBot",
				token=_bot_tokens[-1],
				_role=UserRole.bot)
			db.session.add(user)

			# link the token with the newly created user
			_bot_tokens[-1].user_id = user.id
			db.session.add(_bot_tokens[-1])

		else:
			# bot token exists -> reuse previous one
			_bot_tokens.append(bot_token)

	logger_crwiz.debug(f"Bot tokens:  {[str(bot.id) for bot in _bot_tokens]}")


def _generate_user_tokens():
	# only generate if DEBUG, the others are generated through the portal
	if DEBUG:
		user_tokens = []
		for i in range(2):
			user_tokens.append(generate_user_token(
				db,
				user_id=f"00000000-0000-0000-0000-00000000000{i}",
				start_room=ROOM_NAME_WAITING,
				task=_wizard_task
			))

		logger_crwiz.debug(f"User tokens: {[str(user.id) for user in user_tokens]}")


def _start_bots():
	logger_crwiz.info("Starting bots...")
	for index in range(len(BOT_LIST)):
		_start_bot(BOT_LIST[index], _bot_tokens[index].id)

	sys.stdout.flush()


def _start_bot(bot_script, bot_token):
	_bot_processes.append(subprocess.Popen(
		["python3", bot_script, "-t", str(bot_token), "-p", "5000"]
	))


def stop_bots():
	"""
	Stops all the subprocesses with bots sending a TERMINATE signal.
	The bots will handle the signal and terminate gracefully,
	closing all connections.
	You MUST call this function when closing the program to avoid loose threads.

	:return: None
	"""
	logger_crwiz.info(f"Terminating {len(_bot_processes)} bot processes...")
	for bot_process in _bot_processes:
		bot_process.terminate()
