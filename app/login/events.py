from calendar import timegm
from datetime import datetime

from flask import request
from flask_socketio import join_room, leave_room
from flask_login import login_required, current_user, logout_user

from .. import db, socketio
from ..api.log import log_event


@socketio.on('connect')
@login_required
def connect():
    current_user.session_id = request.sid
    log_event("connect", current_user)
    db.session.commit()
    if current_user.rooms.count() == 0:
        current_user.rooms.append(current_user.token.room)
    for room in current_user.rooms:
        join_room(room.name)
        if current_user not in room.current_users:
            # fixes bug where we try to insert to the wrong table, crashing
            # current_user.current_rooms.append(current_user.token.room)
            room.current_users.append(current_user)

        if room.name.startswith("wizard_task"):
            # user has connected back, let the bot know
            socketio.emit('user_connect', {
                'user': {
                    'id': current_user.id,
                    'name': current_user.name,
                },
                'room': {
                    'name': room.name,
                    'users': [user.id for user in room.current_users]
                }
            }, room=room.name)

        socketio.emit('status', {
            'type': 'join',
            'user': {
                'id': current_user.id,
                'name': current_user.name,
            },
            'room': room.name,
            'timestamp': timegm(datetime.now().utctimetuple())
        }, room=room.name)

        log_event("join", current_user, room)

    db.session.commit()


@socketio.on('ready')
@login_required
def ready():
    for room in current_user.current_rooms:
        socketio.emit(
            "joined_room", dict(user=current_user.id, room=room.name),
            room=request.sid)


@socketio.on('disconnect')
@login_required
def disconnect():
    for room in current_user.current_rooms:
        socketio.emit('status', {
            'type': 'leave',
            'user': {
                'id': current_user.id,
                'name': current_user.name,
            },
            'room': room.name,
            'timestamp': timegm(datetime.now().utctimetuple())
        }, room=room.name)
        if current_user.session_id:
            socketio.emit('left_room', room.name, room=current_user.session_id)

        if room.name.startswith("wizard_task"):
            # user has disconnected, let the bot know
            socketio.emit('user_disconnect', {
                'user': {
                    'id': current_user.id,
                    'name': current_user.name,
                },
                'room': {
                    'name': room.name,
                    'users': [user.id for user in room.current_users]
                }
            }, room=room.name)

        leave_room(room.name)
        log_event("leave", current_user, room)
        if current_user.token.room in current_user.current_rooms:
            current_user.current_rooms.remove(current_user.token.room)
    db.session.commit()
    log_event("disconnect", current_user)
    logout_user()
