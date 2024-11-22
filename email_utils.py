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

logger = logging.getLogger(__name__)

class EmailSender:
    def __init__(self, smtp_settings):
        self.settings = smtp_settings
        self.domain = smtp_settings.smtp_server.split('.')[-2:]
        self.domain = '.'.join(self.domain)

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
                    logger.info(f"Attached file: {attachment['filename']}")
                except Exception as e:
                    logger.error(f"Failed to attach file {attachment['filename']}: {str(e)}")
        
        return msg

    def verify_email(self, email):
        """Verify email using format check and MX record"""
        try:
            # Basic format check
            if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
                logger.error(f"Invalid email format: {email}")
                return False

            # Split email into local and domain parts
            local, domain = email.split('@')
            logger.info(f"Verifying email domain: {domain}")

            # Check for disposable email domains
            disposable_domains = {'temp-mail.org', 'tempmail.com', 'throwawaymail.com'}
            if domain.lower() in disposable_domains:
                logger.warning(f"Disposable email domain detected: {domain}")
                return False

            # Verify MX records
            try:
                mx_records = resolver.resolve(domain, 'MX')
                logger.info(f"MX records found for domain {domain}")
                return True
            except (resolver.NXDOMAIN, resolver.NoAnswer):
                logger.error(f"No MX records found for domain {domain}")
                return False

        except Exception as e:
            logger.error(f"Error verifying email {email}: {str(e)}")
            return False

    def connect_smtp(self):
        """Create and return SMTP connection"""
        server = smtplib.SMTP(self.settings.smtp_server, self.settings.smtp_port)
        server.starttls()
        server.login(self.settings.username, self.settings.password)
        return server

    def send_bulk_emails(self, email_list, subject, body_text, attachments=None):
        """Send bulk emails with verification and delay"""
        delay = self.settings.delay or 5
        total_emails = len(email_list)
        success_count = 0
        failed_count = 0
        results = []
        
        logger.info(f"Starting to send emails to {total_emails} recipients")
        
        for index, recipient_email in enumerate(email_list, 1):
            try:
                if self.verify_email(recipient_email):
                    with self.connect_smtp() as smtp:
                        msg = self.create_email(subject, recipient_email, body_text, attachments)
                        smtp.send_message(msg)
                        success_count += 1
                        status = f"[{success_count}/{total_emails}] Successfully sent email to {recipient_email}"
                        logger.info(status)
                        results.append({'email': recipient_email, 'status': 'success', 'message': status})
                        
                        if index < total_emails:
                            wait_time = random.uniform(delay, delay + 2)
                            next_email = email_list[index] if index < len(email_list) else None
                            if next_email:
                                logger.info(f"Waiting {wait_time:.1f} seconds before sending to {next_email}")
                            time.sleep(wait_time)
                else:
                    failed_count += 1
                    status = f"Failed to verify email: {recipient_email}"
                    logger.error(status)
                    results.append({'email': recipient_email, 'status': 'error', 'message': status})
            except Exception as e:
                failed_count += 1
                status = f"Error sending to {recipient_email}: {str(e)}"
                logger.error(status)
                results.append({'email': recipient_email, 'status': 'error', 'message': status})
                time.sleep(2)
        
        summary = f"Email sending completed. Success: {success_count}, Failed: {failed_count}"
        logger.info(summary)
        return {
            'success_count': success_count,
            'failed_count': failed_count,
            'total': total_emails,
            'results': results,
            'summary': summary
        }