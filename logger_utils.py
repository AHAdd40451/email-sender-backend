import os
import json
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create logs directory
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# This will be set by the app
socketio = None

def init_socketio(socket_instance):
    global socketio
    socketio = socket_instance

def save_log(user_id, action, message, level='info', details=None):
    """Save log to user-specific file and emit via socket"""
    try:
        timestamp = datetime.utcnow().isoformat()
        log_entry = {
            'timestamp': timestamp,
            'action': action,
            'message': message,
            'level': level,
            'details': details or {},
            'user_id': user_id
        }
        
        # Save to file
        log_file = os.path.join(LOG_DIR, f"{user_id}.log")
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            
        # Emit via socket if available
        if socketio:
            socketio.emit('log_update', log_entry, room=f'user_{user_id}')
        
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
            
            # Filter logs to ensure they belong to the requesting user
            logs = [
                log for log in logs 
                if log.get('user_id') == user_id
            ]
            
            # Sort and limit logs
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