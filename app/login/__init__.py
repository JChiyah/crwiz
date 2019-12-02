from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user

from sqlalchemy.exc import StatementError

login = Blueprint('login', __name__, url_prefix="/login")

from ..models.user import User
from ..models.token import Token
from .forms import LoginForm
from .events import *


@login.route('/', methods=['GET', 'POST'])
def index():
    token = request.args.get("token", None) if request.method == 'GET' else ""
    name = request.args.get("name", None) if request.method == 'GET' else None

    form = LoginForm()
    if form.validate_on_submit():
        name = form.name.data
        token = form.token.data if form.token.data is not "" else None

    if token:
        try:
            token = Token.query.get(token)
        except StatementError:
            token = None

        if token and token.valid:
            if token.user is None:
                user = User(name=name, token=token)
                db.session.add(user)
            else:
                user = token.user
            db.session.commit()
            login_user(user)
            return redirect(request.args.get('next') or url_for("chat.index"))
        flash("The token is either expired, was already used, or isn't correct at all.", "error")

    form.token.data = token
    form.name.data = name
    return render_template('login.html', form=form, title="Asset Management System - Login")
