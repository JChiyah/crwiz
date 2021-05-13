from .. import db

from . import Base

import bson


class Log(Base):
    __tablename__ = 'Log'

    event = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("User.id"), nullable=False)
    room_id = db.Column(db.String(100), db.ForeignKey("Room.name"))
    data = db.Column(db.LargeBinary, nullable=False)

    def as_dict(self):
        base = dict({
            'event': self.event,
            'user': {
                'id': self.user_id,
                'name': self.user.name,
            },
            'room': self.room_id,
            'data': bson.loads(self.data),
        }, **super(Log, self).as_dict())
        return dict(base)


def get_user_logs_for_event(
    user_id, event_name: str, order_desc: bool = True) -> list:
    """
    Gets all the logs for a particular user event starting from
    the most recent one.

    :param user_id: id of the user responsible for the event
    :param event_name: name of the event
    :return: list with logs as dict
    """
    order_by = Log.id.desc() if order_desc else Log.id.asc()
    logs = Log.query.order_by(order_by).filter(
        Log.user_id == user_id,
        Log.event == event_name
    ).all()
    if logs:
        return [log.as_dict() for log in logs]
    else:
        return []


def get_room_logs_for_event(
    room_name: str, event_name: str, order_desc: bool = True) -> list:
    """
    Gets all the logs for a particular room event starting from
    the most recent one.

    :param room_name: room id to search for events
    :param event_name: name of the event
    :return: list with logs as dict
    """
    order_by = Log.id.desc() if order_desc else Log.id.asc()
    logs = Log.query.order_by(order_by).filter(
        Log.room_id == room_name,
        Log.event == event_name
    ).all()
    if logs:
        return [log.as_dict() for log in logs]
    else:
        return []
