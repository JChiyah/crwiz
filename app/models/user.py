
import enum
from logging import getLogger
from sqlalchemy import Enum

from .. import db, login_manager

from . import Base, user_room, current_user_room

from .token import Token
from .log import Log


class UserRole(enum.Enum):
    general = 1
    operator = 2
    wizard = 3
    bot = 4

    @classmethod
    def get_from_value(cls, value):
        for item in cls:
            if value == item.value:
                return item

    @classmethod
    def has_name(cls, name):
        return name in UserRole.__members__


class User(Base):
    __tablename__ = 'User'

    _name = db.Column("name", db.String(100), default="User", nullable=False)
    token = db.relationship("Token", backref="user", uselist=False)
    rooms = db.relationship("Room", secondary=user_room, back_populates="users", lazy='dynamic')
    current_rooms = db.relationship("Room", secondary=current_user_room, back_populates="current_users", lazy='dynamic')
    session_id = db.Column(db.String(100), unique=True)
    logs = db.relationship("Log", backref="user", order_by=db.asc("date_modified"))
    _role = db.Column("role", Enum(UserRole), default=UserRole.general, nullable=False)
    # task_finished = db.Column(db.Boolean, default=False, nullable=False)
    task_finished = db.Column(db.DateTime, default=None)
    game_token = db.Column(db.String(10), unique=False)

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def role(self):
        return self._role

    @role.setter
    def role(self, value):
        self._role = value
        self.name = "Fred" \
            if self._role == UserRole.wizard else value.name.capitalize()

    def as_dict(self):
        return dict({
            'name': self.name,
            'token': str(self.token.id),
            'rooms': [room.name for room in self.rooms],
            'session_id': self.session_id,
            'role_id': self.role.value,
            'game_token': self.game_token
        }, **super(User, self).as_dict())

    def get_id(self):
        return self.id

    def get_task_room(self):
        """
        Gets the task room for the user (wizard task).

        :return: Room
        """
        for room in self.rooms:
            if room.name.startswith("wizard_task"):
                return room

        getLogger("orca-slurk").critical(
            f"Error: Cannot find the task room for user {self.id}")
        return None


@login_manager.user_loader
def load_user(user_id):
    this_user = User.query.get(int(user_id))
    # log the user out if its token is not valid anymore
    return this_user if this_user and this_user.token.valid else None
    # return this_user if this_user and not this_user.task_finished else None


@login_manager.request_loader
def load_user_from_request(request):
    token = None
    token_id = request.headers.get('Authorization')

    if token_id:
        try:
            token = Token.query.get(token_id)
        except:
            return None
    if not token:
        token_id = request.args.get('token')
        if token_id:
            token = Token.query.get(token_id)

    if token and token.valid:
        if not token.user:
            name = request.headers.get('name')
            if not name:
                name = request.args.get('name')
            if not name:
                name = "User"
            token.user = User(name=name)
            db.session.commit()
        return token.user
    return None


def get_user_messages(user_id, order_desc: bool = True) -> list:
    order_by = Log.id.desc() if order_desc else Log.id.asc()
    logs = Log.query.order_by(order_by).filter(Log.user_id == user_id)\
        .filter(Log.event == "text_message").all()
    if logs:
        return [log.as_dict() for log in logs]
    return []


def get_user_last_message(user_id):
    logs = get_user_messages(user_id)
    if len(logs) > 0:
        return logs[0]['data']['message']
    return None
