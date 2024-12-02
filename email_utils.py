import base64
import re
import random
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr, make_msgid, formatdate
from dns import resolver
import logging
from datetime import datetime
import smtplib
from email.mime.base import MIMEBase
from email import encoders

logger = logging.getLogger(__name__)

class EmailSender:
    def __init__(self, smtp_settings, user_id):
        self.settings = smtp_settings
        self.user_id = user_id
        self.domain = smtp_settings.smtp_server.split('.')[-2:]
        self.domain = '.'.join(self.domain)
        self.logger = logging.getLogger(__name__)

    def create_email(self, subject, recipient_email, html_content, attachments=None):
        """Create a multipart email with optional attachments"""
        msg = MIMEMultipart('mixed')
        msg['From'] = formataddr((self.settings.sender_name or '', self.settings.username))
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg['Message-ID'] = make_msgid(domain=self.domain)
        msg['Date'] = formatdate(localtime=True)
        msg['Reply-To'] = self.settings.username
        
        # Create the HTML part
        html_part = MIMEMultipart('alternative')
        html_part.attach(MIMEText(html_content, 'html'))
        msg.attach(html_part)
        
        # Add attachments if any
        if attachments:
            for attachment in attachments:
                try:
                    part = MIMEApplication(
                        base64.b64decode(attachment['content']),
                        _subtype=attachment['contentType'].split('/')[-1]
                    )
                    part.add_header(
                        'Content-Disposition',
                        'attachment',
                        filename=attachment['filename']
                    )
                    msg.attach(part)
                    self.logger.info(f"Attached file: {attachment['filename']}")
                except Exception as e:
                    self.logger.error(f"Failed to attach file {attachment['filename']}: {str(e)}")
        
        return msg

    def verify_email(self, email):
        """Verify email using format check and MX record"""
        try:
            # Basic format check
            if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
                self.log_message(f"Invalid email format: {email}", 'error')
                return False

            # Split email into local and domain parts
            local, domain = email.split('@')
            self.log_message(f"Verifying email domain: {domain}", 'info')

            # Check for disposable email domains
            disposable_domains = {'temp-mail.org', 'tempmail.com', 'throwawaymail.com'}
            if domain.lower() in disposable_domains:
                self.log_message(f"Disposable email domain detected: {domain}", 'warning')
                return False

            # Verify MX records
            try:
                mx_records = resolver.resolve(domain, 'MX')
                self.log_message(f"MX records found for domain {domain}", 'info')
                return True
            except (resolver.NXDOMAIN, resolver.NoAnswer):
                self.log_message(f"No MX records found for domain {domain}", 'error')
                return False

        except Exception as e:
            self.log_message(f"Error verifying email {email}: {str(e)}", 'error')
            return False

    def connect_smtp(self):
        """Create and return SMTP connection"""
        server = smtplib.SMTP(self.settings.smtp_server, self.settings.smtp_port)
        server.starttls()
        server.login(self.settings.username, self.settings.password)
        return server

    def log_message(self, message, level='info', details=None):
        """Log message to file"""
        from app import save_log  # Import here to avoid circular imports
        save_log(self.user_id, 'email_sender', message, level, details)

    def send_bulk_emails(self, email_list, subject, body_text, attachments=None):
        success_count = 0
        failed_count = 0
        errors = []

        try:
            with smtplib.SMTP(self.settings.smtp_server, self.settings.smtp_port) as server:
                server.starttls()
                server.login(self.settings.username, self.settings.password)

                for email in email_list:
                    try:
                        msg = MIMEMultipart()
                        msg['From'] = f"{self.settings.sender_name} <{self.settings.username}>"
                        msg['To'] = email
                        msg['Subject'] = subject

                        # Add HTML body
                        msg.attach(MIMEText(body_text, 'html'))

                        # Add attachments if present
                        if attachments:
                            for attachment in attachments:
                                part = MIMEBase('application', 'octet-stream')
                                part.set_payload(attachment['content'])
                                encoders.encode_base64(part)
                                part.add_header(
                                    'Content-Disposition',
                                    f'attachment; filename="{attachment["filename"]}"'
                                )
                                msg.attach(part)

                        server.send_message(msg)
                        success_count += 1
                        time.sleep(self.settings.delay)

                    except Exception as e:
                        failed_count += 1
                        errors.append(f"Failed to send to {email}: {str(e)}")
                        logger.error(f"Error sending to {email}: {e}")

        except Exception as e:
            logger.error(f"SMTP connection error: {e}")
            raise

        return {
            'success_count': success_count,
            'failed_count': failed_count,
            'errors': errors
        }

    def _process_batch(self, batch, batch_num, total_batches, subject, body_text, attachments, max_retries):
        """Process a single batch of emails"""
        batch_results = {
            'success_count': 0,
            'failed_count': 0,
            'results': [],
            'batch_summary': {}
        }
        
        start_time = time.time()
        
        for email in batch:
            result = self._send_single_email(
                email=email,
                subject=subject,
                body_text=body_text,
                attachments=attachments,
                max_retries=max_retries
            )
            
            if result['status'] == 'success':
                batch_results['success_count'] += 1
            else:
                batch_results['failed_count'] += 1
            
            batch_results['results'].append(result)
        
        # Calculate batch metrics
        batch_results['batch_summary'] = {
            'batch_num': batch_num,
            'total_batches': total_batches,
            'processed': len(batch),
            'success': batch_results['success_count'],
            'failed': batch_results['failed_count'],
            'time_taken': time.time() - start_time
        }
        
        return batch_results

    def _smart_delay(self, success_count):
        """Implement smart delay based on success rate"""
        base_delay = self.settings.delay or 5
        if success_count < 10:
            return time.sleep(base_delay * 2)  # Longer delay if having issues
        return time.sleep(base_delay)

    def _send_single_email(self, email, subject, body_text, attachments, max_retries):
        """Send single email with retry logic"""
        for attempt in range(max_retries):
            try:
                if self.verify_email(email):
                    with self.connect_smtp() as smtp:
                        msg = self.create_email(subject, email, body_text, attachments)
                        smtp.send_message(msg)
                        return {
                            'email': email,
                            'status': 'success',
                            'attempts': attempt + 1
                        }
                else:
                    return {
                        'email': email,
                        'status': 'error',
                        'message': 'Email verification failed'
                    }
            except Exception as e:
                if attempt == max_retries - 1:
                    return {
                        'email': email,
                        'status': 'error',
                        'message': str(e),
                        'attempts': attempt + 1
                    }
                time.sleep(2 ** attempt)  # Exponential backoff