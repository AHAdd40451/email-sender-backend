from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from models import User, SmtpSettings, Log
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bson import ObjectId

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')

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
        logger.info(f"Fetching SMTP settings for user {user_id}")
        
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
        logger.info(f"Saving SMTP settings for user {user_id}")
        
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
        if user and user.check_password(password):
            # Create token with string ID
            access_token = create_access_token(identity=str(user._id))
            return jsonify({
                'status': 'success',
                'token': access_token
            })
        
        return jsonify({
            'status': 'error',
            'message': 'Invalid email or password'
        }), 401

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/send-emails', methods=['POST'])
@jwt_required()
def send_emails():
    try:
        user_id = get_jwt_identity()
        data = request.json
        logger.info(f"Received email request for user {user_id}")
        
        # Validate input
        if not data.get('emails') or not data.get('subject') or not data.get('body'):
            logger.error("Missing required fields in email request")
            return jsonify({
                'status': 'error',
                'message': 'Emails, subject, and body are required'
            }), 400

        # Get SMTP settings
        smtp_settings = SmtpSettings.get_by_user_id(user_id)
        if not smtp_settings:
            logger.error(f"No SMTP settings found for user {user_id}")
            return jsonify({
                'status': 'error',
                'message': 'Please configure SMTP settings first'
            }), 400

        successful_sends = 0
        failed_sends = 0
        errors = []
        
        logger.info(f"Attempting to send emails to {len(data['emails'])} recipients")

        try:
            # Connect to SMTP server
            server = smtplib.SMTP(smtp_settings.smtp_server, smtp_settings.smtp_port)
            server.starttls()
            server.login(smtp_settings.username, smtp_settings.password)
            
            for recipient in data['emails']:
                try:
                    # Create message
                    msg = MIMEMultipart()
                    msg['From'] = f"{smtp_settings.sender_name} <{smtp_settings.username}>" if smtp_settings.sender_name else smtp_settings.username
                    msg['To'] = recipient
                    msg['Subject'] = data['subject']
                    
                    # Add body
                    msg.attach(MIMEText(data['body'], 'html'))
                    
                    # Send email
                    server.send_message(msg)
                    successful_sends += 1
                    logger.info(f"Successfully sent email to {recipient}")
                    
                except Exception as e:
                    failed_sends += 1
                    error_msg = f"Failed to send to {recipient}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            server.quit()

        except Exception as smtp_error:
            logger.error(f"SMTP connection error: {smtp_error}")
            return jsonify({
                'status': 'error',
                'message': f'SMTP connection failed: {str(smtp_error)}'
            }), 500

        result_message = f'Sent {successful_sends} emails successfully'
        if failed_sends > 0:
            result_message += f', {failed_sends} failed'

        logger.info(result_message)
        return jsonify({
            'status': 'success',
            'message': result_message,
            'details': {
                'successful': successful_sends,
                'failed': failed_sends,
                'errors': errors
            }
        })

    except Exception as e:
        logger.error(f"Error in send_emails: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to send emails: {str(e)}'
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
    app.run(debug=True, port=5000)
