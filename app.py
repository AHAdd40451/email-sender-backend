from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import bulk_email
from datetime import datetime
import os
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Pass socketio instance to bulk_email module
bulk_email.socketio = socketio

def emit_log(message, level='info'):
    with open('email_sender.log', 'a') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        log_line = f"{timestamp} - {level.upper()} - {message}\n"
        f.write(log_line)
    
    socketio.emit('log_update', {
        'timestamp': timestamp,
        'type': level,
        'message': message
    })

@app.route('/send-emails', methods=['POST'])
def send_emails():
    try:
        data = request.json
        emit_log('Starting email process...', 'info')

        # Update bulk_email configuration
        bulk_email.SMTP_SERVER = data['smtpServer']
        bulk_email.SMTP_PORT = int(data['smtpPort'])
        bulk_email.USERNAME = data['username']
        bulk_email.PASSWORD = data['password']
        bulk_email.DELAY = int(data['delay'])
        bulk_email.SENDER_NAME = data['senderName']
        
        # Process emails with attachments
        body_text = data['emailTemplate']
        subject = data['emailSubject']
        attachments = data.get('attachments', None)
        
        bulk_email.send_bulk_emails(
            data['emailList'], 
            subject, 
            body_text, 
            attachments=attachments
        )

        emit_log(f'Successfully processed {len(data["emailList"])} emails', 'success')
        return jsonify({
            'status': 'success',
            'message': f'Successfully processed {len(data["emailList"])} emails'
        })

    except Exception as e:
        emit_log(f'Error: {str(e)}', 'error')
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/get-logs', methods=['GET'])
def get_logs():
    try:
        with open('email_sender.log', 'r') as f:
            logs = []
            email_counter = 1
            for line in f:
                if any(skip in line for skip in ['Debugger', 'Running on', 'Press CTRL+C', 'Restarting', 'PIN:', 'Detected change']):
                    continue
                    
                parts = line.strip().split(' - ', 2)
                if len(parts) == 3:
                    timestamp, level, message = parts
                    
                    if 'Successfully sent email to' in message:
                        log_type = 'success'
                        message = f"[{email_counter}] {message}"
                        email_counter += 1
                    elif 'error' in level.lower():
                        log_type = 'error'
                    elif 'warning' in level.lower():
                        log_type = 'warning'
                    else:
                        log_type = 'info'
                        
                    logs.append({
                        'timestamp': timestamp,
                        'type': log_type,
                        'message': message.strip()
                    })
            return jsonify({'logs': logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clear-logs', methods=['POST'])
def clear_logs():
    try:
        with open('email_sender.log', 'w') as f:
            f.write('')
        
        socketio.emit('logs_cleared', {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3],
            'message': 'Logs cleared'
        })
        
        return jsonify({
            'status': 'success',
            'message': 'Logs cleared successfully'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
