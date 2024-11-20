import smtplib
import time
import random
import logging
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
import re
from dns import resolver
from datetime import datetime, timedelta
from flask_socketio import SocketIO

# Set up logging
logging.basicConfig(
    filename='email_sender.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Default settings (will be overridden by frontend)
SMTP_SERVER = "smtp.example.com"
SMTP_PORT = 587
USERNAME = "your@email.com"
PASSWORD = "your_password"
DOMAIN = "yourdomain.com"
DELAY = 5
SENDER_NAME = "Your Name"

# Email verification settings
MAX_VERIFICATION_ATTEMPTS = 3
VERIFICATION_TIMEOUT = 7
VERIFICATION_CACHE = {}
CACHE_DURATION = timedelta(hours=24)

socketio = None  # Will be set by app.py

def create_email(subject, recipient_email, html_content):
    """Create a multipart email"""
    msg = MIMEMultipart('alternative')
    msg['From'] = formataddr((SENDER_NAME, USERNAME))
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg['Message-ID'] = make_msgid(domain=DOMAIN)
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['Reply-To'] = USERNAME
    
    # Attach the HTML content directly
    msg.attach(MIMEText(html_content, 'html'))
    
    return msg

def verify_email(email):
    """Verify email using format check and MX record"""
    try:
        # Check cache
        
        
        # Basic format check
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            emit_log(f"Invalid email format: {email}", 'error')
            return False

        # Split email into local and domain parts
        local, domain = email.split('@')
        emit_log(f"Verifying email domain: {domain}", 'info')

        # Check for disposable email domains
        disposable_domains = {'temp-mail.org', 'tempmail.com', 'throwawaymail.com'}
        if domain.lower() in disposable_domains:
            emit_log(f"Disposable email domain detected: {domain}", 'warning')
            return False

        # Verify MX records
        try:
            mx_records = resolver.resolve(domain, 'MX')
            emit_log(f"MX records found for domain {domain}", 'info')
            return True
        except (resolver.NXDOMAIN, resolver.NoAnswer):
            emit_log(f"No MX records found for domain {domain}", 'error')
            return False

    except Exception as e:
        emit_log(f"Error verifying email {email}: {str(e)}", 'error')
        return False

def send_bulk_emails(email_list, subject, body_text, delay=None):
    if delay is None:
        delay = DELAY
        
    total_emails = len(email_list)
    success_count = 0
    failed_count = 0
    emit_log(f"Starting to send emails to {total_emails} recipients", 'info')
    
    for index, recipient_email in enumerate(email_list, 1):
        try:
            if verify_email(recipient_email):
                with connect_smtp() as smtp:
                    msg = create_email(subject, recipient_email, body_text)
                    smtp.send_message(msg)
                    success_count += 1
                    emit_log(f"[{success_count}/{total_emails}] Successfully sent email to {recipient_email}", 'success')
                    
                    # Calculate and emit the wait time for the next email
                    wait_time = random.uniform(delay, delay + 2)
                    if index < total_emails:  # Only emit if there are more emails to send
                        next_email = email_list[index] if index < len(email_list) else None
                        if next_email:
                            emit_log(f"Waiting {wait_time:.1f} seconds before sending to {next_email}", 'info')
                    
                    time.sleep(wait_time)
            else:
                failed_count += 1
                emit_log(f"[{failed_count}] Failed to verify email: {recipient_email}", 'error')
        except Exception as e:
            failed_count += 1
            emit_log(f"[{failed_count}] Error sending to {recipient_email}: {str(e)}", 'error')
            time.sleep(2)
    
    emit_log(f"Email sending completed. Success: {success_count}, Failed: {failed_count}", 'info')

def emit_log(message, level='info'):
    """Emit log message through socketio in real-time"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
    
    # First emit to socket for real-time updates
    if socketio:
        try:
            socketio.emit('log_update', {
                'timestamp': timestamp,
                'type': level,  # Changed from 'level' to 'type' to match frontend
                'message': message
            }, namespace='/')  # Added namespace
        except Exception as e:
            logging.error(f"Error emitting socket message: {e}")
    
    # Then write to file
    with open('email_sender.log', 'a') as f:
        f.write(f"{timestamp} - {level.upper()} - {message}\n")

def connect_smtp():
    """Create and return a configured SMTP connection"""
    try:
        emit_log(f"Connecting to SMTP server {SMTP_SERVER}:{SMTP_PORT}", 'info')
        smtp_server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        emit_log("Starting TLS connection", 'info')
        smtp_server.starttls()
        emit_log("Logging in to SMTP server", 'info')
        smtp_server.login(USERNAME, PASSWORD)
        emit_log("Successfully connected to SMTP server", 'info')
        return smtp_server
    except Exception as e:
        emit_log(f"Failed to connect to SMTP server: {str(e)}", 'error')
        raise