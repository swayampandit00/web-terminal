# DevilShell Web Interface

A web-based interface for the DevilShell command-line tool.

## Features

- Web-based terminal interface
- User authentication
- Execute DevilShell commands remotely
- Real-time command output

## Prerequisites

- Python 3.7+
- Flask
- Colorama
- Cryptography

## Installation

1. Navigate to the devilshell_website directory:
   ```
   cd devilshell_website
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Make sure the `devilshell_v5.py` file is in the parent directory or adjust the import path in `app.py`.

## Running the Application

1. Start the Flask development server:
   ```
   python app.py
   ```

2. Open your web browser and go to `http://localhost:5000`

3. Log in with a valid DevilShell username and password (default: admin/devil123 or guest/0000)

4. Start executing commands in the web interface!

## Usage

- Type commands in the input field and press Enter or click Execute
- The output will appear in the terminal area above
- Use 'help' to see available commands
- Click Logout to end the session

## Security Note

This is a basic implementation for demonstration purposes. In a production environment, implement proper security measures such as:
- HTTPS
- Strong session management
- Input validation and sanitization
- Rate limiting

## Troubleshooting

- If you encounter import errors, ensure `devilshell_v5.py` is in the correct path
- Make sure all dependencies are installed
- Check that the Flask app is running on the correct port
