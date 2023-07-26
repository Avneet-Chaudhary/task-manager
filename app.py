from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_mail import Mail, Message
import schedule
import time
import threading
import configparser

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///my_db.db"
db = SQLAlchemy(app)

# Read configurations from config.ini file
config = configparser.ConfigParser()
config.read("config.ini")

app.config['MAIL_SERVER'] = config.get('DEFAULT', 'MAIL_SERVER')
app.config['MAIL_PORT'] = config.getint('DEFAULT', 'MAIL_PORT')
app.config['MAIL_USE_TLS'] = config.getboolean('DEFAULT', 'MAIL_USE_TLS')
app.config['MAIL_USERNAME'] = config.get('DEFAULT', 'MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = config.get('DEFAULT', 'MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = config.get(
    'DEFAULT', 'MAIL_DEFAULT_SENDER')

mail = Mail(app)


class Todo(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    desc = db.Column(db.String(500), nullable=False)
    date_created = db.Column(
        db.String(8), default=datetime.now().strftime('%H:%M:%S'))
    completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, default=1)  # Add the priority column

    def __repr__(self) -> str:
        return f"{self.sno} - {self.title} (Priority: {self.priority})"


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    todo_id = db.Column(db.Integer, db.ForeignKey('todo.sno'), nullable=False)
    todo = db.relationship('Todo', backref=db.backref('comments', lazy=True))

    def __repr__(self):
        return f"{self.id} - {self.content}"


# Create database tables with the application context
with app.app_context():
    db.create_all()


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['desc']
        # Convert priority to an integer
        priority = int(request.form['priority'])
        # Include priority in the Todo object
        todo = Todo(title=title, desc=desc, priority=priority)
        db.session.add(todo)
        db.session.commit()
    # allTodo = Todo.query.all()
    allTodo = Todo.query.order_by(Todo.priority.desc()).all()
    return render_template("index.html", allTodo=allTodo)
    # if request.method == 'POST':
    #     title = request.form['title']
    #     desc = request.form['desc']
    #     todo = Todo(title=title, desc=desc)
    #     db.session.add(todo)
    #     db.session.commit()
    # allTodo = Todo.query.all()
    # return render_template("index.html", allTodo=allTodo)


@app.route('/tasks/', methods=['GET'])
def tasks():
    # Get the search query from the 'search' parameter in the URL
    search_query = request.args.get('search', '')

    if search_query:
        # Get the task with the matching title (assuming you have a 'title' field in the 'Todo' model)
        matching_task = Todo.query.filter(
            Todo.title.contains(search_query)).first()

        if matching_task:
            # If a matching task is found, render tasks.html with only that task
            return render_template('tasks.html', allTodo=[matching_task])
        else:
            # If no matching task, display the "No tasks found" message and the button to add tasks
            return render_template('tasks.html', allTodo=[])
    else:
        # If no search query, get all tasks and render tasks.html
        all_tasks = Todo.query.all()
        return render_template('tasks.html', allTodo=all_tasks)


@app.route('/search', methods=['GET'])
def task_search():
    # Get the search query from the 'search' parameter in the URL
    search_query = request.args.get('search', '')

    if search_query:
        # Get the tasks with the matching title (assuming you have a 'title' field in the 'Todo' model)
        matching_tasks = Todo.query.filter(
            Todo.title.contains(search_query)).all()
        search_performed = True

        if matching_tasks:
            # If matching tasks are found, render index.html with those tasks
            return render_template('index.html', allTodo=matching_tasks, search_performed=search_performed)
        else:
            # If no matching tasks are found, display a message
            return render_template('index.html', allTodo=[], search_performed=search_performed)

    # If no search query is provided, display all tasks in index.html
    all_tasks = Todo.query.all()
    return render_template('index.html', allTodo=all_tasks, search_performed=False)


@app.route('/update/<int:sno>', methods=['GET', 'POST'])
def update(sno):
    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['desc']
        todo = Todo.query.filter_by(sno=sno).first()
        todo.title = title
        todo.desc = desc
        db.session.add(todo)
        db.session.commit()
        return redirect('/')
    todo = Todo.query.filter_by(sno=sno).first()
    return render_template("update.html", todo=todo)


@app.route('/done/<int:sno>')
def task_done(sno):
    task = Todo.query.get_or_404(sno)
    task.completed = True
    db.session.commit()
    return redirect('/')


@app.route('/pending/<int:sno>')
def task_revert_done_toPending(sno):
    # Get the task with the given sno
    task = Todo.query.get_or_404(sno)

    # Mark the task as pending (assuming you have a 'completed' field in the 'Todo' model)
    task.completed = False

    # Commit the changes to the database
    db.session.commit()

    # Redirect back to the tasks page
    return redirect('/tasks/')


@app.route('/delete/<int:sno>', methods=['GET', 'POST'])
def delete(sno):
    todo = Todo.query.get(sno)
    if request.method == 'POST':
        # Delete associated comments first
        Comment.query.filter_by(todo_id=sno).delete()

        # Now delete the todo
        db.session.delete(todo)
        db.session.commit()
        return redirect("/")
    allTodo = Todo.query.all()
    return render_template('tasks.html', allTodo=allTodo)


@app.route('/comment/<int:sno>', methods=['GET', 'POST'])
def add_comment(sno):
    todo = Todo.query.get(sno)
    if request.method == 'POST':
        content = request.form['content']
        # Pass the correct todo_id here
        comment = Comment(content=content, todo_id=sno)
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('tasks'))
    return render_template('add_comment.html', todo=todo)


# Function to send task reminders
def send_task_reminders():
    with app.app_context():
        # Get the current time
        current_time = datetime.utcnow()

        # Query tasks that are due in the next 24 hours and not completed
        tasks_to_remind = Todo.query.filter(
            Todo.date_created <= (
                current_time - timedelta(hours=24)), Todo.completed == False
        ).all()

        # Replace this with the default email address
        default_email = 'yourgmailid@gmail.com'

        for task in tasks_to_remind:
            # Send an email notification to remind about the task.
            msg = Message('Task Reminder', recipients=[default_email])
            msg.body = f"Task '{task.title}' is due in the next 24 hours. Please complete it on time."
            mail.send(msg)


# Schedule the reminder function to run every minute (for testing purposes)
schedule.every(24).hours.do(send_task_reminders)


# Function to run the scheduling loop
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


# Start the scheduling loop in a separate thread when the app starts
reminder_thread = threading.Thread(target=run_scheduler)
reminder_thread.start()

if __name__ == '__main__':
    app.run(debug=True, port=8000)
