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
from logger_utils import save_log

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
        save_log(self.user_id, 'email_sender', message, level, details)

    def send_bulk_emails(self, email_list, subject, body_text, attachments=None):
        """Send bulk emails with improved handling for concurrent users"""
        batch_size = 50
        max_retries = 3
        total_emails = len(email_list)
        results = {
            'success_count': 0,
            'failed_count': 0,
            'results': [],
            'batches': []
        }
        
        # Split into batches
        batches = [email_list[i:i + batch_size] for i in range(0, total_emails, batch_size)]
        
        for batch_num, batch in enumerate(batches, 1):
            batch_result = self._process_batch(
                batch=batch,
                batch_num=batch_num,
                total_batches=len(batches),
                subject=subject,
                body_text=body_text,
                attachments=attachments,
                max_retries=max_retries
            )
            
            # Update results
            results['success_count'] += batch_result['success_count']
            results['failed_count'] += batch_result['failed_count']
            results['results'].extend(batch_result['results'])
            results['batches'].append(batch_result['batch_summary'])
            
            # Add delay between batches
            if batch_num < len(batches):
                self._smart_delay(batch_result['success_count'])
        
        return results

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

    def verify_domain(self, domain):
        save_log(self.user_id, 'verify_domain', f"Verifying email domain: {domain}")
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            if mx_records:
                save_log(self.user_id, 'verify_domain', f"MX records found for domain {domain}")
                return True
            save_log(self.user_id, 'verify_domain', f"No MX records found for domain {domain}", level='warning')
            return False
        except Exception as e:
            save_log(self.user_id, 'verify_domain', f"Error verifying domain {domain}: {str(e)}", level='error')
            return False