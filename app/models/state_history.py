
import bson

from .. import db

from . import Base

from .log import Log
from .user import get_user_messages


class StateHistory(Base):
	__tablename__ = 'StateHistory'

	user_id = db.Column(db.Integer, db.ForeignKey("User.id"), nullable=False)
	previous_state = db.Column(db.String(100), nullable=False)
	utterance = db.Column(db.String(250), nullable=False)
	current_state = db.Column(db.String(100), nullable=False)
	data = db.Column(db.LargeBinary, nullable=True)

	def as_dict(self):
		return {
			'user_id': self.user_id,
			'previous_state': self.previous_state,
			'utterance': self.utterance,
			'current_state': self.current_state,
			'data': bson.loads(self.data)
		}


def get_user_states(user_id):
	"""
	Gets the user states in descending order (newest first)

	:param user_id: id of the user
	:return: None or list of StateHistory
	"""
	return StateHistory.query.order_by(StateHistory.id.desc()).filter(StateHistory.user_id == user_id).all()


def get_user_current_state(user_id):
	user_states = get_user_states(user_id)
	if user_states and len(user_states) > 0:
		return user_states[0]
	return None


def check_used_state(user_id, state_name: str):
	"""
	Checks whether a dialogue state has been used before.

	:param user_id: wizard id
	:param state_name: name of the state
	:return: bool, True if state has been used
	"""
	user_states = get_user_states(user_id)

	for state in user_states:
		if state.current_state == state_name:
			return True

	return False
