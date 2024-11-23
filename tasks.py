from email_utils import EmailSender
from models import SmtpSettings, Log
import time
from rq import get_current_job

def send_email_batch(user_id, batch_emails, subject, body_text, attachments=None):
    """Background task to send a batch of emails"""
    job = get_current_job()
    
    try:
        # Get SMTP settings for the user
        smtp_settings = SmtpSettings.get_by_user_id(user_id)
        if not smtp_settings:
            raise Exception("SMTP settings not found")
            
        email_sender = EmailSender(smtp_settings, user_id)
        
        results = {
            'successful': 0,
            'failed': 0,
            'details': []
        }
        
        # Process each email in the batch
        for email in batch_emails:
            try:
                # Update job meta to track progress
                job.meta['progress'] = {
                    'current': batch_emails.index(email) + 1,
                    'total': len(batch_emails)
                }
                job.save_meta()
                
                # Send individual email
                success = email_sender.send_single_email(
                    email,
                    subject,
                    body_text,
                    attachments
                )
                
                if success:
                    results['successful'] += 1
                    status = 'success'
                else:
                    results['failed'] += 1
                    status = 'failed'
                    
                results['details'].append({
                    'email': email,
                    'status': status
                })
                
                # Add delay between emails
                time.sleep(smtp_settings.delay or 5)
                
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'email': email,
                    'status': 'error',
                    'error': str(e)
                })
                
        return results
        
    except Exception as e:
        Log.create(
            user_id=user_id,
            message=f"Error in email batch: {str(e)}",
            level='error'
        )
        raise