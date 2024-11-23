from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from models import User, SmtpSettings, Log, JSONEncoder
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bson import ObjectId
from email_utils import EmailSender
from datetime import datetime
from queue_config import high_priority_queue, default_queue, low_priority_queue
from rq.job import Job
from redis import Redis

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.json_encoder = JSONEncoder  # Use custom JSON encoder

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

        # Convert password to bytes before checking
        try:
            if isinstance(password, str):
                password = password.encode('utf-8')
            
            if user.check_password(password):
                access_token = create_access_token(identity=str(user._id))
                return jsonify({
                    'status': 'success',
                    'token': access_token
                })
        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            
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
        
        if not data.get('emails') or not data.get('subject') or not data.get('body'):
            return jsonify({
                'status': 'error',
                'message': 'Emails, subject, and body are required'
            }), 400
            
        # Validate SMTP settings
        smtp_settings = SmtpSettings.get_by_user_id(user_id)
        if not smtp_settings:
            return jsonify({
                'status': 'error',
                'message': 'Please configure SMTP settings first'
            }), 400
            
        # Split emails into batches
        batch_size = 50
        email_list = data['emails']
        batches = [email_list[i:i + batch_size] 
                  for i in range(0, len(email_list), batch_size)]
                  
        # Queue jobs for each batch
        jobs = []
        for batch in batches:
            # Choose queue based on user priority or other factors
            queue = default_queue
            
            job = queue.enqueue(
                'tasks.send_email_batch',
                args=(
                    user_id,
                    batch,
                    data['subject'],
                    data['body'],
                    data.get('attachments')
                ),
                job_timeout='1h',
                result_ttl=86400  # Keep results for 24 hours
            )
            jobs.append(job.id)
            
        return jsonify({
            'status': 'success',
            'message': f'Queued {len(email_list)} emails for sending',
            'job_ids': jobs
        })
        
    except Exception as e:
        logger.error(f"Error queuing emails: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/job-status/<job_id>', methods=['GET'])
@jwt_required()
def get_job_status(job_id):
    try:
        redis_conn = Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379))
        )
        
        job = Job.fetch(job_id, connection=redis_conn)
        
        status = {
            'id': job.id,
            'status': job.get_status(),
            'progress': job.meta.get('progress', {}),
            'result': job.result if job.is_finished else None,
            'error': str(job.exc_info) if job.is_failed else None
        }
        
        return jsonify(status)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/logs', methods=['GET'])
@jwt_required()
def get_logs():
    try:
        user_id = get_jwt_identity()
        limit = request.args.get('limit', 100, type=int)
        
        logger.info(f"Fetching logs for user {user_id}")
        logs = Log.get_by_user(user_id, limit)
        
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
        deleted_count = Log.clear_user_logs(user_id)
        
        return jsonify({
            'status': 'success',
            'message': f'Cleared {deleted_count} log entries',
            'deleted_count': deleted_count
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
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
