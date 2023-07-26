from app import db
from datetime import datetime


class Todo(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    desc = db.Column(db.String(500), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    completed = db.Column(db.Boolean, default=False)

    def __repr__(self) -> str:
        return f"{self.sno} - {self.title}"


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    todo_id = db.Column(db.Integer, db.ForeignKey('todo.sno'), nullable=False)
    todo = db.relationship('Todo', backref=db.backref('comments', lazy=True))

    def __repr__(self):
        return f"{self.id} - {self.content}"
