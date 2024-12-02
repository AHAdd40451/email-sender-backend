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
        email_statuses = []

        # Log start of bulk email operation
        self.log_message(
            f"Starting bulk email operation for {len(email_list)} recipients",
            'info',
            details={
                'total_emails': len(email_list),
                'subject': subject,
                'has_attachments': bool(attachments),
                'attachment_count': len(attachments) if attachments else 0
            }
        )

        try:
            with smtplib.SMTP(self.settings.smtp_server, self.settings.smtp_port) as server:
                server.starttls()
                server.login(self.settings.username, self.settings.password)
                self.log_message("SMTP connection established successfully", 'info')

                total_emails = len(email_list)
                for index, email in enumerate(email_list, 1):
                    start_time = time.time()
                    try:
                        # Log attempt to send email
                        self.log_message(
                            f"Attempting to send email to {email} ({index}/{total_emails})",
                            'info'
                        )

                        msg = MIMEMultipart()
                        msg['From'] = f"{self.settings.sender_name} <{self.settings.username}>"
                        msg['To'] = email
                        msg['Subject'] = subject

                        # Add HTML body
                        msg.attach(MIMEText(body_text, 'html'))

                        # Log attachment processing
                        if attachments:
                            self.log_message(
                                f"Processing {len(attachments)} attachments for {email}",
                                'info'
                            )
                            for attachment in attachments:
                                try:
                                    part = MIMEBase('application', 'octet-stream')
                                    part.set_payload(attachment['content'])
                                    encoders.encode_base64(part)
                                    part.add_header(
                                        'Content-Disposition',
                                        f'attachment; filename="{attachment["filename"]}"'
                                    )
                                    msg.attach(part)
                                    self.log_message(
                                        f"Successfully attached {attachment['filename']}",
                                        'info'
                                    )
                                except Exception as attach_err:
                                    self.log_message(
                                        f"Failed to attach {attachment['filename']}: {str(attach_err)}",
                                        'error'
                                    )

                        # Send the email
                        server.send_message(msg)
                        success_count += 1
                        status = 'success'
                        error_msg = None

                        # Log successful send
                        self.log_message(
                            f"Successfully sent email to {email}",
                            'info',
                            details={
                                'email': email,
                                'time_taken': f"{time.time() - start_time:.2f}s"
                            }
                        )

                    except Exception as e:
                        failed_count += 1
                        status = 'failed'
                        error_msg = str(e)
                        
                        # Log failed send
                        self.log_message(
                            f"Failed to send email to {email}",
                            'error',
                            details={
                                'error': str(e),
                                'email': email,
                                'time_taken': f"{time.time() - start_time:.2f}s"
                            }
                        )
                        errors.append(f"Failed to send to {email}: {str(e)}")

                    email_statuses.append({
                        'email': email,
                        'status': status,
                        'error': error_msg,
                        'timestamp': datetime.utcnow().isoformat(),
                        'time_taken': f"{time.time() - start_time:.2f}s"
                    })

                    # Progress logging
                    if index % 10 == 0 or index in [1, total_emails] or (index / total_emails) in [0.25, 0.5, 0.75]:
                        progress_msg = (
                            f"Progress: {index}/{total_emails} emails processed. "
                            f"Success: {success_count}, Failed: {failed_count}"
                        )
                        self.log_message(
                            progress_msg,
                            'info',
                            details={
                                'progress_percentage': f"{(index/total_emails)*100:.1f}%",
                                'success_rate': f"{(success_count/index)*100:.1f}%",
                                'current_success_count': success_count,
                                'current_failed_count': failed_count
                            }
                        )

                    # Apply sending delay
                    time.sleep(self.settings.delay)

                # Generate final summary
                summary = {
                    'total_sent': total_emails,
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'success_rate': f"{(success_count/total_emails)*100:.1f}%",
                    'failed_emails': [status['email'] for status in email_statuses if status['status'] == 'failed'],
                    'successful_emails': [status['email'] for status in email_statuses if status['status'] == 'success']
                }

                # Log final summary
                self.log_message(
                    "Bulk email operation completed",
                    'info',
                    details={
                        'summary': summary,
                        'failed_details': [
                            {'email': status['email'], 'error': status['error']}
                            for status in email_statuses
                            if status['status'] == 'failed'
                        ]
                    }
                )

        except Exception as e:
            self.log_message(
                "SMTP connection error",
                'error',
                details={
                    'error': str(e),
                    'smtp_server': self.settings.smtp_server,
                    'smtp_port': self.settings.smtp_port
                }
            )
            raise

        return {
            'success_count': success_count,
            'failed_count': failed_count,
            'errors': errors,
            'summary': summary,
            'email_statuses': email_statuses
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