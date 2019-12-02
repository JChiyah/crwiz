from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

chat = Blueprint('chat', __name__)

from .message import *
from .connection import *
from ..api import *


@chat.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if current_user.rooms.count() == 0:
        current_user.rooms.append(current_user.token.room)
        db.session.commit()

    # return template depending on user role (e.g. the wizards get special template with set options)
    return render_template('chat.html', title="Asset Management System", token=current_user.token)
    # not used anymore because it not precise
    # is_wizard=current_user.role == UserRole.wizard)
