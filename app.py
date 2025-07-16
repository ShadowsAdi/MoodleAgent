from flask import Flask, render_template, request, jsonify, redirect, url_for
import threading
import os
from automation_agent import run_moodle_automation
import markdown

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

task = {
    'running': False,
    'progress': 0,
    'message': '',
    'result': str(),
    'error': str(),
    'action_type': None
}

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/start_automation', methods=['POST'])
def start_automation():
    global task

    if task['running']:
        return jsonify({'error': 'Task is already running'}), 400

    course_name = request.form.get('course_name', '').strip()
    subject_name = request.form.get('subject_name', '').strip()
    action_type = request.form.get('action_type', 'summary')
    ai_provider = request.form.get('ai_provider', 'google')

    if not course_name or not subject_name:
        return jsonify({'error': 'Course name and subject name are required'}), 400

    task = {
        'running': True,
        'progress': 0,
        'message': 'Starting automation...',
        'result': None,
        'error': None,
        'action_type': action_type
    }

    thread = threading.Thread(
        target=run_automation,
        args=(course_name, subject_name, action_type, ai_provider)
    )
    thread.start()

    return jsonify({'message': 'Started successfully'})

def run_automation(course_name, subject_name, action_type, ai_provider):
    global task

    try:
        task['message'] = "Initializing moodle agent..."
        task['progress'] = 10

        result = run_moodle_automation(
            course_name=course_name,
            subject_name=subject_name,
            action_type=action_type,
            ai_provider=ai_provider,
            status_callback=update_task
        )

        task['progress'] = 100
        task['message'] = "Task completed successfully"
        if action_type == "summary":
            md = result.get('summary', '')
            task['result'] = markdown.markdown(md, extensions=["fenced_code", "tables"])
        elif action_type == "flashcards":
            task['result'] = result
        elif action_type == "quiz":
            task['result'] = result
        else:
            task['result'] = "<p>Unknown action type</p>"

    except Exception as e:
        task['error'] = str(e)
        task['message'] = f"Error: {str(e)}"
    finally:
        task['running'] = False

def update_task(message, progress):
    global task
    task['message'] = message
    task['progress'] = progress

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify(task)

@app.route('/result', methods=['GET'])
def show_result():
    if not task['result'] and not task['error']:
        return redirect(url_for('index'))

    return render_template(
        'result.html',
        result=task['result'],
        error=task['error'],
        action_type=task['action_type']
    )

def reset_task():
    global task
    task.update({
        'running': False,
        'progress': 0,
        'message': '',
        'result': None,
        'error': None,
        'action_type': None
    })

@app.route('/reset', methods=['POST'])
def reset_status():
    reset_task()
    return jsonify({'message': 'Data reset successfully'})

if __name__ == '__main__':
    app.run(debug=True, port=8000)