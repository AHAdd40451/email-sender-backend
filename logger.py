import os
import json
from datetime import datetime
import logging

# Setup logging directory
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        
        # Create user-specific log file
        log_file = os.path.join(LOG_DIR, f"{user_id}.log")
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            
        # Also log to console for debugging
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