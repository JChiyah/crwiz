from flask import g, make_response, jsonify, Blueprint, request
from flask_httpauth import HTTPTokenAuth

from sqlalchemy.exc import StatementError, IntegrityError

from ..models.token import Token
from ..models.layout import Layout
from ..models.task import Task
from ..models.permission import Permissions


from .log import log_event
from .room import *
from .user import *
from ..crwiz import game_token, fake_actions
from ..crwiz.utils import constants
from ..crwiz.socket_connection import *
from ..crwiz.task_manager import task_manager, emit_dialogue_choices


auth = HTTPTokenAuth(scheme='Token')
api = Blueprint('api', __name__, url_prefix="/api/v2/")


@auth.error_handler
def unauthorized():
    return make_response(jsonify({'error': 'Unauthorized access'}), 401)


@auth.verify_token
def verify_token(token):
    try:
        token = Token.query.get(token)
    except StatementError:
        return False
    if token:
        g.current_permissions = token.permissions
        g.current_user = token.user
        return True
    return False


@api.route('/layouts', methods=['GET'])
@auth.login_required
def get_layouts():
    if not g.current_permissions.layout_query:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    return make_response(jsonify([dict(uri="/layout/"+str(layout.id), **layout.as_dict()) for layout in Layout.query.all()]))


@api.route('/layout/<int:id>', methods=['GET'])
@auth.login_required
def get_layout(id):
    if not g.current_permissions.layout_query:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    layout = Layout.query.get(id)
    if layout:
        return make_response(jsonify(layout.as_dict()))
    else:
        return make_response(jsonify({'error': 'layout not found'}), 404)


@api.route('/layout', methods=['POST'])
@auth.login_required
def post_layout():
    if not g.current_permissions.layout_create:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    data = request.get_json(force=True) if request.is_json else None
    if not data:
        return make_response(jsonify({'error': 'bad request'}, 400))

    try:
        name = data.get("title")
        if not name:
            name = data.get("subtitle", "Unnamed")
        layout = Layout.from_json_data(name, data)
        db.session.add(layout)
        db.session.commit()
        return make_response(jsonify(layout.as_dict()))
    except (IntegrityError, StatementError) as e:
        return make_response(jsonify({'error': str(e)}), 400)


@api.route('/layout/<int:id>', methods=['PUT'])
@auth.login_required
def put_layout(id):
    if not g.current_permissions.layout_update:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    data = request.get_json(force=True) if request.is_json else None
    if not data:
        return make_response(jsonify({'error': 'bad request'}, 400))

    layout = Layout.query.get(id)
    if not layout:
        return make_response(jsonify({'error': 'layout not found'}), 404)

    new_layout = Layout.from_json_data("", data)
    if 'css' in data:
        layout.css = new_layout.css
    if 'html' in data:
        layout.html = new_layout.html
    if 'name' in data:
        layout.name = data['name']
    if 'scripts' in data:
        layout.script = new_layout.script
    if 'subtitle' in data:
        layout.subtitle = new_layout.subtitle
    if 'title' in data:
        layout.title = new_layout.title

    try:
        db.session.commit()
        return make_response(jsonify(layout.as_dict()))
    except (IntegrityError, StatementError) as e:
        return make_response(jsonify({'error': str(e)}), 400)


@api.route('/tokens', methods=['GET'])
@auth.login_required
def get_tokens():
    if not g.current_permissions.token_query:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    return make_response(jsonify([dict(uri="/token/"+str(token.id), **token.as_dict()) for token in Token.query.all()]))


@api.route('/token/<string:id>', methods=['GET'])
@auth.login_required
def get_token(id):
    if not g.current_permissions.token_query and str(g.current_user.token) != id:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    token = Token.query.get(id)
    if token:
        return make_response(jsonify(token.as_dict()))
    else:
        return make_response(jsonify({'error': 'token not found'}), 404)


@api.route('/token', methods=['POST'])
@auth.login_required
def post_token():
    if not g.current_permissions.token_generate:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    data = request.get_json(force=True) if request.is_json else None
    if not data:
        return make_response(jsonify({'error': 'bad request'}, 400))

    if 'task' in data and data['task']:
        task = Task.query.get(data['task'])
        if not task:
            return make_response(jsonify({'error': 'task not found'}), 404)
    else:
        task = None

    if 'room' in data and data['room']:
        room = Room.query.get(data['room'])
        if not room:
            return make_response(jsonify({'error': 'room not found'}), 404)
    else:
        room = None

    try:
        token = Token(
            room_name=room.name,
            task=task,
            source=data.get("source", None),
            permissions=Permissions(
                user_query=data.get("user_query", False),
                user_log_event=data.get("user_log_event", False),
                user_room_join=data.get("user_room_join", False),
                user_room_leave=data.get("user_room_leave", False),
                message_text=data.get("message_text", False),
                message_image=data.get("message_image", False),
                message_command=data.get("message_command", False),
                message_broadcast=data.get("message_broadcast", False),
                room_query=data.get("room_query", False),
                room_log_query=data.get("room_log_query", False),
                room_create=data.get("room_create", False),
                room_update=data.get("room_update", False),
                room_delete=data.get("room_delete", False),
                layout_query=data.get("layout_query", False),
                layout_create=data.get("layout_create", False),
                layout_update=data.get("layout_update", False),
                task_create=data.get("task_create", False),
                task_query=data.get("task_query", False),
                task_update=data.get("task_update", False),
                token_generate=data.get("token_generate", False),
                token_query=data.get("token_query", False),
                token_update=data.get("token_update", False),
                token_invalidate=data.get("token_invalidate", False),
            )
        )
        db.session.add(token)
        db.session.commit()
        return make_response(jsonify(token.id))
    except (IntegrityError, StatementError) as e:
        return make_response(jsonify({'error': str(e)}), 400)


@api.route('/token/<string:id>', methods=['DELETE'])
@auth.login_required
def invalidate_token(id):
    if not g.current_permissions.token_invalidate:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    token = Token.query.get(id)
    if token:
        token.valid = False
        db.session.commit()
        return make_response(jsonify(token.as_dict()))
    else:
        return make_response(jsonify({'error': 'token not found'}), 404)


@api.route('/users', methods=['GET'])
@auth.login_required
def get_users():
    return make_response(jsonify([dict(uri="/users/"+str(user.id), **user.as_dict()) for user in User.query.all()]))


@api.route('/user/<int:id>', methods=['GET'])
@auth.login_required
def get_user(id):
    if id != g.current_user.id and not g.current_permissions.user_query:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)
    user = User.query.get(id) if id != g.current_user.id else g.current_user
    if user:
        return make_response(jsonify(user.as_dict()))
    else:
        return make_response(jsonify({'error': 'user not found'}), 404)


@api.route('/tasks', methods=['GET'])
@auth.login_required
def get_tasks():
    if not g.current_permissions.task_query:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    return make_response(jsonify([dict(uri="/task/"+str(task.id), **task.as_dict()) for task in Task.query.all()]))


@api.route('/task/<int:id>', methods=['GET'])
@auth.login_required
def get_task(id):
    if not g.current_permissions.task_query:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    task = Task.query.get(id)
    if task:
        return make_response(jsonify(task.as_dict()))
    else:
        return make_response(jsonify({'error': 'task not found'}), 404)


@api.route('/task', methods=['POST'])
@auth.login_required
def post_task():
    if not g.current_permissions.task_create:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    data = request.get_json(force=True) if request.is_json else None
    if not data:
        return make_response(jsonify({'error': 'bad request'}, 400))

    name = data.get('name')
    num_users = data.get('num_users')
    if not name:
        return make_response(jsonify({'error': 'missing parameter: `name`'}, 400))
    if not num_users:
        return make_response(jsonify({'error': 'missing parameter: `num_users`'}, 400))
    try:
        num_users = int(num_users)
    except ValueError:
        return make_response(jsonify({'error': 'invalid number: `num_users`'}, 400))

    if 'layout' in data and data['layout']:
        layout = Layout.query.get(data['layout'])
        if not layout:
            return make_response(jsonify({'error': 'layout not found'}), 404)
    else:
        layout = Layout.query.filter(Layout.name == "default").first()

    try:
        task = Task(
            name=name,
            num_users=num_users,
            layout=layout,
        )
        db.session.add(task)
        db.session.commit()
        return make_response(jsonify(task.as_dict()))
    except (IntegrityError, StatementError) as e:
        return make_response(jsonify({'error': str(e)}), 400)


@api.route('/task/<int:id>', methods=['PUT'])
@auth.login_required
def put_task(id):
    if not g.current_permissions.task_update:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    data = request.get_json(force=True) if request.is_json else None
    if not data:
        return make_response(jsonify({'error': 'bad request'}, 400))

    task = Task.query.get(id)
    if not task:
        return make_response(jsonify({'error': 'room not found'}), 404)

    try:
        if 'num_users' in data:
            try:
                task.num_users = int(data['num_users'])
            except ValueError:
                return make_response(jsonify({'error': 'invalid number: `num_users`'}, 400))
        if 'name' in data:
            task.name = data['name']
        if 'layout' in data and data['layout']:
            layout = Layout.query.get(data['layout'])
            if not layout:
                return make_response(jsonify({'error': 'layout not found'}), 404)
            task.layout = layout

        db.session.commit()
        return make_response(jsonify(task.as_dict()))
    except (IntegrityError, StatementError, ValueError) as e:
        return make_response(jsonify({'error': str(e)}), 400)


@api.route('/rooms', methods=['GET'])
@auth.login_required
def get_rooms():
    if not g.current_permissions.room_query:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    return make_response(jsonify([dict(uri="/room/"+room.name, **room.as_dict()) for room in Room.query.all()]))


@api.route('/room/<string:name>', methods=['GET'])
@auth.login_required
def get_room(name):
    room = Room.query.get(name)
    if room not in g.current_user.current_rooms and not g.current_permissions.room_query:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    if room:
        return make_response(jsonify(room.as_dict()))
    else:
        return make_response(jsonify({'error': 'room not found'}), 404)


@api.route('/room/<string:name>/layout', methods=['GET'])
@auth.login_required
def get_room_layout(name):
    room = Room.query.get(name)
    if room not in g.current_user.current_rooms and (not g.current_permissions.room_query or not g.current_permissions.layout_query):
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    if room:
        return make_response(jsonify(room.layout.as_dict()))
    else:
        return make_response(jsonify({'error': 'room not found'}), 404)


@api.route('/room', methods=['POST'])
@auth.login_required
def post_room():
    if not g.current_permissions.room_create:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    data = request.get_json(force=True) if request.is_json else None
    if not data:
        return make_response(jsonify({'error': 'bad request'}, 400))

    name = data.get('name')
    label = data.get('label')
    if not name:
        return make_response(jsonify({'error': 'missing parameter: `name`'}, 400))
    if not label:
        return make_response(jsonify({'error': 'missing parameter: `label`'}, 400))

    if 'layout' in data and data['layout']:
        layout = Layout.query.get(data['layout'])
        if not layout:
            return make_response(jsonify({'error': 'layout not found'}), 404)
    else:
        layout = Layout.query.filter(Layout.name == "default").first()

    try:
        room = Room(
            name=name,
            label=label,
            layout=layout,
            read_only=data.get('read_only'),
            show_users=data.get('show_users'),
            show_latency=data.get('show_latency'),
            static=data.get('static'),
        )
        db.session.add(room)
        db.session.commit()
        return make_response(jsonify(room.as_dict()))
    except (IntegrityError, StatementError) as e:
        return make_response(jsonify({'error': str(e)}), 400)


@api.route('/room/<string:name>', methods=['PUT'])
@auth.login_required
def put_rooms(name):
    if not g.current_permissions.room_update:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    data = request.get_json(force=True) if request.is_json else None
    if not data:
        return make_response(jsonify({'error': 'bad request'}, 400))

    room = Room.query.get(name)
    if not room:
        return make_response(jsonify({'error': 'room not found'}), 404)

    try:
        if 'label' in data:
            room.label = data['label']
        if 'layout' in data and data['layout']:
            layout = Layout.query.get(data['layout'])
            if not layout:
                return make_response(jsonify({'error': 'layout not found'}), 404)
            room.layout = layout
        if 'read_only' in data:
            room.read_only = data['read_only']
        if 'show_users' in data:
            room.show_users = data['show_users']
        if 'show_latency' in data:
            room.show_users = data['show_latency']
        if 'static' in data:
            room.static = data['static']

        db.session.commit()
        return make_response(jsonify(room.as_dict()))
    except (IntegrityError, StatementError) as e:
        return make_response(jsonify({'error': str(e)}), 400)


@api.route('/room/<string:name>', methods=['DELETE'])
@auth.login_required
def delete_rooms(name):
    if not g.current_permissions.room_delete:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    room = Room.query.get(name)
    if not room:
        return make_response(jsonify({'error': 'room not found'}), 404)

    try:
        for user in room.current_users:
            if user.session_id:
                socketio.emit('left_room', room.name, room=user.session_id)
                log_event("leave", user, room)
        socketio.close_room(room.name)
        Room.query.filter_by(name=room.name).delete()
        db.session.commit()
        return make_response(jsonify({'result': True}))
    except IntegrityError as e:
        return make_response(jsonify({'error': str(e)}), 400)


@api.route('/room/<string:name>/logs', methods=['GET'])
@auth.login_required
def get_room_logs(name):
    if not g.current_permissions.room_log_query:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    room = Room.query.get(name)
    if room:
        return make_response(jsonify([log.as_dict() for log in room.logs]))
    else:
        return make_response(jsonify({'error': 'room not found'}), 404)


@api.route('/user/<int:id>/logs', methods=['GET'])
@auth.login_required
def get_user_logs(id):
    def filter_private_messages(logs, id):
        for log in logs:
            if log['event'] == "text_message" or log['event'] == "image_message":
                # Filter only messages
                if log['data']['receiver']:
                    # Private message
                    if int(log['data']['receiver']) != id and log['user']['id'] != id:
                        # User not affected, continue the loop
                        continue
            yield log

    user = User.query.get(id)
    if user:
        return make_response(jsonify({room.name: list(filter_private_messages([log.as_dict() for log in room.logs], user.id)) for room in user.rooms}))
    else:
        return make_response(jsonify({'error': 'user not found'}), 404)


@api.route('/user/<int:id>/task', methods=['GET'])
@auth.login_required
def get_user_task(id):
    user = User.query.get(id)
    if user:
        return make_response(jsonify(user.token.task.as_dict() if user.token.task else None))
    else:
        return make_response(jsonify({'error': 'user not found'}), 404)


@api.route('/user/<int:user_id>/log', methods=['POST'])
@auth.login_required
def post_user_logs(user_id):
    if not g.current_permissions.user_log_event:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    this_user = User.query.get(user_id)
    if not this_user:
        return make_response(jsonify({'error': 'user not found'}), 404)

    data = request.get_json(force=True) if request.is_json else None
    if not data:
        return make_response(jsonify({'error': 'bad request'}, 400))

    event = data.get('event')
    if not event:
        return make_response(jsonify(
            {'error': 'missing parameter: `event`'}, 400))

    if 'room' in data:
        this_room = Room.query.get(data['room'])
        if not this_room:
            return make_response(jsonify({'error': 'room not found'}), 404)
    else:
        this_room = None

    try:
        return make_response(jsonify(
            log_event(event, this_user, this_room, data.get('data')).as_dict()))
    except (IntegrityError, StatementError) as e:
        return make_response(jsonify({'error': str(e)}), 400)


@api.route('/user/<int:user_id>/game_token', methods=['POST'])
@auth.login_required
def post_user_game_token(user_id):
    this_user = User.query.get(user_id)
    if not this_user:
        return make_response(jsonify({'error': 'user not found'}), 404)

    try:
        this_user.game_token = game_token.generate_token()
        db.session.commit()

        log_event(
            constants.EVENT_GENERATE_GAME_TOKEN, this_user,
            data={
                'game_token': this_user.game_token
            })

        return make_response(jsonify({'game_token': this_user.game_token}))

    except (IntegrityError, StatementError) as e:
        return make_response(jsonify({'error': str(e)}), 400)


@api.route('/get_wizard_dialogue_choices/<int:user_id>', methods=['POST'])
@auth.login_required
def wizard_text_options(user_id: int):
    if not g.current_user:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    if user_id != g.current_user.id and not g.current_permissions.user_query:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    this_user = User.query.get(user_id) \
        if user_id != g.current_user.id else g.current_user
    if this_user:
        return task_manager.get_dialogue_options(this_user.id)
        # return jsonify(state_machine.get_next_state_transitions(this_user.id))
    else:
        return make_response(jsonify({'error': 'user not found'}), 404)


@api.route('/submit_dialogue_choice/<int:user_id>', methods=['POST'])
@auth.login_required
def submit_dialogue_choice(user_id):
    # make sure that the one who is submitting it is also the wizard
    if not g.current_user or user_id != g.current_user.id:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    this_user = User.query.get(user_id)
    if not this_user:
        return make_response(jsonify({'error': 'user not found'}), 404)

    data = request.get_json(force=True) if request.is_json else None
    if not data or not data.get('text'):
        return make_response(jsonify({'error': 'bad request'}, 400))

    return task_manager.submit_dialogue_choice(
        this_user.id, data.get('state_name'), data.get('text'))


@api.route('/request_task_hint/<int:user_id>', methods=['POST'])
@auth.login_required
def request_task_hint(user_id):
    # make sure that the one who is submitting it is also the wizard
    if not g.current_user or user_id != g.current_user.id:
        return make_response(jsonify({'error': 'insufficient rights'}), 403)

    this_user = User.query.get(user_id)
    if not this_user:
        return make_response(jsonify({'error': 'user not found'}), 404)

    return task_manager.request_task_hint(this_user.id)


def close_rooms():
    task_manager.__del__()
    getLogger("crwiz").debug("Task manager and task rooms closed")
