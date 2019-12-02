
from sqlalchemy.dialects.mysql import DATETIME

from .. import db


class Base(db.Model):
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)
    date_created = db.Column(DATETIME(fsp=6), default=db.func.now(6))
    date_modified = db.Column(DATETIME(fsp=6), default=db.func.now(6), onupdate=db.func.now(6))

    def as_dict(self):
        return {
            'id': self.id,
            'date_created': self.date_created.timestamp(),
            'date_modified': self.date_modified.timestamp()
        }


user_room = db.Table('User_Room', Base.metadata,
                     db.Column('user_id', db.Integer, db.ForeignKey('User.id', ondelete="CASCADE"), primary_key=True),
                     db.Column('room_name', db.String(100), db.ForeignKey('Room.name', ondelete="CASCADE"), primary_key=True))
current_user_room = db.Table('User_Room_current', Base.metadata,
                             db.Column('user_id', db.Integer, db.ForeignKey('User.id', ondelete="CASCADE"), primary_key=True),
                             db.Column('room_name', db.String(100), db.ForeignKey('Room.name', ondelete="CASCADE"), primary_key=True))

# todo: export the information in current_user_room before dropping it
if current_user_room.exists(db.engine):
    db.session.execute(f"""TRUNCATE TABLE {current_user_room.name}""")
    db.session.commit()
