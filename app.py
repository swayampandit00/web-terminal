from flask import Flask, render_template, request, session, redirect, url_for
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from devilshell_v5 import DevilShell, verify_password

app = Flask(__name__)
app.secret_key = 'devilshell_secret_key'  # Change this in production

shell = DevilShell()

@app.route('/')
def index():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Simple auth for demo
        if username in shell.users and verify_password(password, shell.users[username]['salt'], shell.users[username]['hash']):
            session['logged_in'] = True
            session['username'] = username
            shell.current_user = username
            shell.theme = shell.users[username].get('theme', 'X')
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/execute', methods=['POST'])
def execute():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    cmd = request.form['command']
    output = shell.execute_single_command(cmd)
    return output

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    shell.current_user = None
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
