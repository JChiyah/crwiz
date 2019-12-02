from .. import db

from . import user_room, current_user_room
from .log import Log


ROOM_NAME_WAITING: str = "waiting_room"
ROOM_NAME_TASK: str = "task_room"


class Room(db.Model):
    __tablename__ = 'Room'

    name = db.Column(db.String(100), primary_key=True)
    label = db.Column(db.String(100), nullable=False)
    layout_id = db.Column(db.Integer, db.ForeignKey("Layout.id"), nullable=False)
    read_only = db.Column(db.Boolean, default=False, nullable=False)
    show_users = db.Column(db.Boolean, default=True, nullable=False)
    show_latency = db.Column(db.Boolean, default=True, nullable=False)
    static = db.Column(db.Boolean, default=False, nullable=False)
    tokens = db.relationship("Token", backref="room")
    users = db.relationship("User", secondary=user_room, back_populates="rooms")
    current_users = db.relationship("User", secondary=current_user_room, back_populates="current_rooms")
    logs = db.relationship("Log", backref="room", order_by=db.asc("date_modified"))

    def as_dict(self):
        return {
            'name': self.name,
            'label': self.label,
            'layout': self.layout_id,
            'read_only': self.read_only,
            'show_users': self.show_users,
            'show_latency': self.show_latency,
            'static': self.static,
            'users': {user.id: user.name for user in self.users},
            'current_users': {user.id: user.name for user in self.current_users},
        }


def get_room_user_messages(room_id, minimum_id=0, bot_msgs=False) -> list:
    logs = Log.query.order_by(Log.id.desc())\
        .filter(
            Log.room_id == room_id,
            Log.event == "text_message",
            Log.id > minimum_id)\
        .all()
    if logs:
        logs = [log.as_dict() for log in logs]
        logs = [log for log in logs if bot_msgs or log['user']['id'] > 2]
        return logs
    return []


def get_room_last_user_message(room_id):
    logs = get_room_user_messages(room_id)
    if len(logs) > 0:
        return logs[0]
    return None
