
from .. import db, socketio

from ..models.user import User
from ..models.permission import Permissions

from ..crwiz import logger_crwiz


def update_user_permissions(
		permissions: dict, *, user_id: int = None, user: User = None) -> bool:
	"""
	Updates the permissions of a user.

	:param permissions: dict with the permission names and their new values
	:param user_id: id of the user to apply changes to
	:param user: User object
	:return: bool, True if successful
	"""
	if user_id:
		user = User.query.get(user_id)

	if not user:
		logger_crwiz.warning("No user found to update permissions")
		return False

	user_permissions = Permissions.query\
		.filter(Permissions.token == user.token).first()

	for key in permissions.keys():
		try:
			if getattr(user_permissions, key) is not None:
				setattr(user_permissions, key, permissions[key])
			else:
				logger_crwiz.error(
					f"Error trying to change permission '{key}': not found")
		except Exception as ex:
			logger_crwiz.exception(f"Error trying to change permission '{key}': {ex}")

	# log.log_event("update_user_permissions", user, data=permissions)
	db.session.commit()

	socketio.emit("update_user_permissions", permissions, room=user.session_id)

	logger_crwiz.info(f"Updated permissions for user {user.id}: {permissions}")

	return True


def update_user_token_validity(
	is_token_valid: bool, *, user_id: int = None, user: User = None) -> bool:
	"""
	Updates the validity of the user token. An invalid token does not allow
	the user to log back into the website.

	:param is_token_valid: True if token is valid, False for invalid
	:param user_id: id of the user
	:param user: User object
	:return: bool, True if successful
	"""
	if user_id:
		user = User.query.get(user_id)

	if not user:
		logger_crwiz.warning("No user found to update token validity")
		return False

	user.token.valid = is_token_valid

	# log_event("invalidate_user_token", user, data=data)
	db.session.commit()

	logger_crwiz.info(
		f"User {user.id} token is now {'' if is_token_valid else 'in'}valid")

	return True
