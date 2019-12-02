
from logging import getLogger

from flask_sqlalchemy import SQLAlchemy

from app.models.room import ROOM_NAME_WAITING
from app.models.task import Task, get_wizard_task
from app.models.token import Token
from app.models.permission import Permissions


def generate_user_task_token(db: SQLAlchemy, user_id: str = None) -> Token:
	"""
	Shortcut to generate a new token for a participant of the study.

	:param db: SQLAlchemy database
	:param user_id: the id of the user if known, defaults to generate new id
	:return: the new Token generated
	"""
	return generate_user_token(
		db,
		user_id=user_id,
		start_room=ROOM_NAME_WAITING,
		task=get_wizard_task()
	)


def generate_user_token(
	db: SQLAlchemy, *,
	user_id: str = None,
	start_room: str = ROOM_NAME_WAITING,
	task: Task = None) -> Token:
	"""
	Generates a new user token in the database with the default user permissions
	(as participants in the study).

	:param db: SQLAlchemy database
	:param user_id: the id of the user if known, defaults to generate new id
	:param start_room: the starting room for the user, defaults to waiting room
	:param task: the task to assign to this user, defaults to None
	:return: the new Token generated
	"""
	user_token = Token(
		room_name=start_room,
		id=user_id,
		task=task,
		permissions=Permissions(
			user_query=False,
			user_log_event=False,
			user_room_join=False,
			user_room_leave=False,
			message_text=True,
			message_image=True,
			message_command=False,
			message_broadcast=False,
			room_query=True,
			room_log_query=True,
			room_create=False,
			room_update=False,
			room_delete=False,
			layout_query=True,
			layout_create=False,
			layout_update=False,
			task_create=False,
			task_query=True,
			task_update=False,
			token_generate=False,
			token_query=False,
			token_invalidate=False,
			token_update=False,
		)
	)

	db.session.add(user_token)
	db.session.flush()
	db.session.commit()

	getLogger('crwiz').info(f"New user token generated: {user_token.id}")

	return user_token
