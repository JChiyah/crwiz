from .. import db

from . import Base
from .token import Token


TASK_NAME_WIZARD: str = "wizard_task"


class Task(Base):
    __tablename__ = 'Task'

    name = db.Column(db.String(100), nullable=False)
    num_users = db.Column(db.Integer)
    layout_id = db.Column(db.ForeignKey("Layout.id"))
    tokens = db.relationship(Token.__tablename__, backref="task")

    def as_dict(self):
        return dict({
            'name': self.name,
            'num_users': self.num_users,
            'layout': self.layout_id,
            'tokens': [str(token) for token in self.tokens]
        }, **super(Task, self).as_dict())


def get_wizard_task() -> Task:
    """
    Gets the task for the wizard study (the one with the TASK_NAME_WIZARD).

    :return: Task for the study
    """
    return Task.query.filter(Task.name == TASK_NAME_WIZARD).first()
