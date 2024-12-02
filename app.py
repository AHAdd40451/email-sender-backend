from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from models import User, SmtpSettings, JSONEncoder, EmailList, EmailTemplate
import logging
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bson import ObjectId
from email_utils import EmailSender
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create logs directory
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

def save_log(user_id, action, message, level='info', details=None):
    """Save log to user-specific file"""
    try:
        timestamp = datetime.utcnow().isoformat()
        log_entry = {
            'timestamp': timestamp,
            'action': action,
            'message': message,
            'level': level,
            'details': details
        }
        
        # Save to file
        log_file = os.path.join(LOG_DIR, f"{user_id}.log")
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            
        logger.info(f"[{user_id}] {level.upper()}: {message}")
        
    except Exception as e:
        logger.error(f"Error saving log: {e}")

def get_user_logs(user_id, limit=100):
    """Retrieve logs for specific user"""
    try:
        log_file = os.path.join(LOG_DIR, f"{user_id}.log")
        logs = []
        
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = [json.loads(line) for line in f.readlines()]
            
            # Return only the latest logs based on limit
            logs = sorted(logs, key=lambda x: x['timestamp'], reverse=True)[:limit]
            
        return logs
        
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return []

def clear_user_logs(user_id):
    """Clear logs for specific user"""
    try:
        log_file = os.path.join(LOG_DIR, f"{user_id}.log")
        if os.path.exists(log_file):
            os.remove(log_file)
            return True
        return False
    except Exception as e:
        logger.error(f"Error clearing logs: {e}")
        return False

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.json_encoder = JSONEncoder

# Setup CORS
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"]
    }
})

jwt = JWTManager(app)

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
        
        save_log(user_id, 'send_emails', f"Starting email send to {len(data['emails'])} recipients")
        
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
        
        # Send emails and get result
        result = email_sender.send_bulk_emails(
            email_list=data['emails'],
            subject=data['subject'],
            body_text=data['body'],
            attachments=data.get('attachments')
        )

        # Create a summary message
        summary = f"Sent {result['success_count']} emails successfully, {result['failed_count']} failed"
        
        save_log(user_id, 'send_emails', summary)
        
        # Return a proper response with all necessary information
        return jsonify({
            'status': 'success',
            'message': summary,
            'details': {
                'successful': result['success_count'],
                'failed': result['failed_count'],
                'total': len(data['emails']),
                'errors': result.get('errors', [])
            }
        }), 200

    except Exception as e:
        error_message = str(e)
        save_log(user_id, 'send_emails', f"Error sending emails: {error_message}", 'error')
        return jsonify({
            'status': 'error',
            'message': f'Failed to send emails: {error_message}'
        }), 500

@app.route('/logs', methods=['GET'])
@jwt_required()
def get_logs():
    try:
        user_id = get_jwt_identity()
        limit = request.args.get('limit', 100, type=int)
        
        log_file = os.path.join(LOG_DIR, f"{user_id}.log")
        logs = []
        
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = [json.loads(line) for line in f.readlines()]
            
            # Return only the latest logs based on limit
            logs = sorted(logs, key=lambda x: x['timestamp'], reverse=True)[:limit]
        
        return jsonify({
            'status': 'success',
            'logs': logs
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
        log_file = os.path.join(LOG_DIR, f"{user_id}.log")
        
        if os.path.exists(log_file):
            os.remove(log_file)
        
        return jsonify({
            'status': 'success',
            'message': 'Logs cleared successfully'
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

@app.route('/email-list', methods=['GET'])
@jwt_required()
def get_email_list():
    try:
        user_id = get_jwt_identity()
        email_list = EmailList.get_by_user_id(user_id)
        
        return jsonify({
            'status': 'success',
            'emails': email_list.emails if email_list else []
        })

    except Exception as e:
        logger.error(f"Error fetching email list: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/email-list', methods=['POST'])
@jwt_required()
def save_email_list():
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        if not data or 'emails' not in data:
            return jsonify({
                'status': 'error',
                'message': 'No emails provided'
            }), 400

        email_list = EmailList(user_id=user_id, emails=data['emails'])
        email_list.save()
        
        return jsonify({
            'status': 'success',
            'message': 'Email list saved successfully'
        })

    except Exception as e:
        logger.error(f"Error saving email list: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/email-template', methods=['GET'])
@jwt_required()
def get_email_template():
    try:
        user_id = get_jwt_identity()
        template = EmailTemplate.get_by_user_id(user_id)
        
        return jsonify({
            'status': 'success',
            'template': template[0] if template else None
        })

    except Exception as e:
        logger.error(f"Error fetching email template: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/email-template', methods=['POST'])
@jwt_required()
def save_email_template():
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        if not data or 'subject' not in data or 'body' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Subject and body are required'
            }), 400

        template = EmailTemplate.create(
            user_id=user_id,
            name='default',  # Using default as the template name
            subject=data['subject'],
            body=data['body']
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Email template saved successfully'
        })

    except Exception as e:
        logger.error(f"Error saving email template: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
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
    logger.info("Starting server on port 5000")
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
