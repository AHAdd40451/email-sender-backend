from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from models import User, SmtpSettings, JSONEncoder
from email_utils import EmailSender
from logger_utils import save_log, get_user_logs, clear_user_logs, init_socketio
import logging
import os
from datetime import datetime
from flask_socketio import SocketIO, emit, join_room

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.json_encoder = JSONEncoder

# Setup CORS and Socket.IO
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"]
    }
})

socketio = SocketIO(app,
    cors_allowed_origins=["http://localhost:3000", "https://your-frontend-domain.com"],
    async_mode='eventlet',
    ping_timeout=60,
    ping_interval=25
)
init_socketio(socketio)  # Initialize socketio in logger_utils

jwt = JWTManager(app)

@socketio.on('join')
def on_join(data):
    user_id = data.get('userId')
    if user_id:
        room = f'user_{user_id}'
        join_room(room)
        # Send initial connection message
        emit('log_update', {
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'connection',
            'message': 'Connected to log stream',
            'level': 'info',
            'user_id': user_id
        }, room=room)

@app.route('/smtp-settings', methods=['GET'])
@jwt_required()
def get_smtp_settings():
    try:
        user_id = get_jwt_identity()
        settings = SmtpSettings.get_by_user_id(user_id)
        
        return jsonify({
            'status': 'success',
            'settings': settings.to_dict() if settings else None
        })

    except Exception as e:
        logger.error(f"Error fetching SMTP settings: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/smtp-settings', methods=['POST'])
@jwt_required()
def save_smtp_settings():
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400

        # Validate required fields
        required_fields = ['smtp_server', 'smtp_port', 'username', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'status': 'error',
                    'message': f'{field} is required'
                }), 400

        settings = SmtpSettings.save_settings(
            user_id=user_id,
            smtp_server=data['smtp_server'],
            smtp_port=int(data['smtp_port']),
            username=data['username'],
            password=data['password'],
            sender_name=data.get('sender_name', ''),
            delay=int(data.get('delay', 5))
        )

        return jsonify({
            'status': 'success',
            'message': 'Settings saved successfully',
            'settings': settings.to_dict()
        })

    except Exception as e:
        logger.error(f"Error saving SMTP settings: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({
                'status': 'error',
                'message': 'Email and password are required'
            }), 400

        user = User.get_by_email(email)
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'Invalid email or password'
            }), 401

        # Add debug logging
        print(f"Stored password: {user.password}")
        print(f"Provided password: {password}")
        
        if user.check_password(password):
            token = create_access_token(identity=str(user._id))
            return jsonify({
                'status': 'success',
                'token': token,
                'user': user.to_dict()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Invalid email or password'
            }), 401

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred during login'
        }), 500

@app.route('/send-emails', methods=['POST'])
@jwt_required()
def send_emails():
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        save_log(
            user_id=user_id,
            action='send_emails',
            message=f"Starting email send to {len(data['emails'])} recipients",
            details={'user_id': user_id}
        )
        
        # Validate input
        if not data.get('emails') or not data.get('subject') or not data.get('body'):
            return jsonify({
                'status': 'error',
                'message': 'Emails, subject, and body are required'
            }), 400

        # Get SMTP settings
        smtp_settings = SmtpSettings.get_by_user_id(user_id)
        if not smtp_settings:
            return jsonify({
                'status': 'error',
                'message': 'Please configure SMTP settings first'
            }), 400

        # Initialize email sender with user_id
        email_sender = EmailSender(smtp_settings, user_id)
        
        # Send emails
        result = email_sender.send_bulk_emails(
            email_list=data['emails'],
            subject=data['subject'],
            body_text=data['body'],
            attachments=data.get('attachments')
        )

        # Create a summary message
        summary = f"Sent {result['success_count']} emails successfully, {result['failed_count']} failed"

        save_log(
            user_id=user_id,
            action='send_emails',
            message=f"Email sending completed. Success: {result['success_count']}, Failed: {result['failed_count']}",
            details={'user_id': user_id}
        )
        
        return jsonify({
            'status': 'success',
            'message': summary,
            'details': {
                'successful': result['success_count'],
                'failed': result['failed_count'],
                'total': len(data['emails']),
                'results': result['results']
            }
        })

    except Exception as e:
        save_log(
            user_id=user_id,
            action='send_emails',
            message=f"Error sending emails: {str(e)}",
            level='error',
            details={'user_id': user_id}
        )
        return jsonify({
            'status': 'error',
            'message': f'Failed to send emails: {str(e)}'
        }), 500

@app.route('/logs', methods=['GET'])
@jwt_required()
def get_logs():
    try:
        user_id = get_jwt_identity()
        limit = request.args.get('limit', 100, type=int)
        
        # Get logs specific to this user
        logs = get_user_logs(user_id, limit)
        
        # Filter logs to ensure only user's own logs are returned
        filtered_logs = [
            log for log in logs 
            if log.get('user_id') == user_id
        ]
        
        return jsonify({
            'status': 'success',
            'logs': filtered_logs
        })

    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/logs/clear', methods=['POST'])
@jwt_required()
def clear_logs():
    try:
        user_id = get_jwt_identity()
        success = clear_user_logs(user_id)
        
        return jsonify({
            'status': 'success' if success else 'error',
            'message': 'Logs cleared successfully' if success else 'Failed to clear logs'
        })

    except Exception as e:
        logger.error(f"Error clearing logs: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({
                'status': 'error',
                'message': 'Email and password are required'
            }), 400

        user = User.create_user(email=email, password=password)
        
        return jsonify({
            'status': 'success',
            'message': 'Registration successful'
        })

    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred during registration'
        }), 500

# Add error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({
        'status': 'error',
        'message': 'Resource not found'
    }), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)
