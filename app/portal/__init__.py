
from logging import getLogger

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user, logout_user

from ..models.user import User

from .. import db
from ..crwiz.utils import token_utils
from ..crwiz.task_manager import task_manager

portal = Blueprint('portal', __name__, url_prefix="/portal")


DEBUG = False


# disable strict_slashes so this maps to both URLs /portal and /portal/
@portal.route('/', methods=['GET'], strict_slashes=False)
def index():
	if current_user.is_authenticated:
		try:
			this_user = User.query.get(current_user.id)
			if not this_user or DEBUG:
				logout_user()
			else:
				return redirect(url_for("chat.index"))
		except Exception as ex:
			getLogger("crwiz").exception(
				f"There was an unexpected exception: {ex}")
			return redirect(url_for("chat.index"))

	# not authenticated -> create new token for user
	user_token = token_utils.generate_user_task_token(db)

	# login user automatically
	return redirect(url_for("login.index", token=user_token.id))
