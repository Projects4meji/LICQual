from django.core.mail.backends.base import BaseEmailBackend
import boto3
from botocore.exceptions import ClientError
from decouple import config
import logging
import email
import boto3

logger = logging.getLogger(__name__)

class SESEmailBackend(BaseEmailBackend):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.debug("Initializing SESEmailBackend...")
        self.client = None

    def open(self):
        logger.debug("Opening SES client connection...")
        if self.client is None:
            try:
                self.client = boto3.client(
                    'ses',
                    region_name=config('AWS_SES_REGION', default='eu-west-2'),
                    aws_access_key_id=config('AWS_SES_ACCESS_KEY_ID'),
                    aws_secret_access_key=config('AWS_SES_SECRET_ACCESS_KEY')
                )
                logger.debug("SES client opened. region=%s endpoint=%s",
                            self.client.meta.region_name, getattr(self.client.meta, "endpoint_url", None))

                return True
            except Exception as e:
                logger.error("Failed to open SES client: %s", str(e))
                return False
        return True

    def close(self):
        logger.debug("Closing SES client connection...")
        self.client = None
        logger.debug("SES client closed.")

    def send_messages(self, email_messages):
        logger.debug("Processing %d email messages...", len(email_messages))
        if not self.open():
            logger.error("Cannot send messages: SES client not initialized.")
            raise ValueError("SES client not initialized.")

        sent_count = 0
        for message in email_messages:
            try:
                logger.debug("Preprocessing email: subject=%s, to=%s", message.subject, message.to)
                # Convert EmailMessage to raw MIME for SES raw sending
                raw_message = message.message().as_string()
                destinations = {'ToAddresses': message.to}
                if getattr(message, 'cc', None):
                    destinations['CcAddresses'] = message.cc
                    logger.debug("CC: %s", message.cc)
                if getattr(message, 'bcc', None):
                    destinations['BccAddresses'] = message.bcc
                    logger.debug("BCC: %s", message.bcc)

                logger.debug("Sending SES API raw request...")
                response = self.client.send_raw_email(
                    Source=message.from_email,
                    Destinations=message.to + (message.cc or []) + (message.bcc or []),
                    RawMessage={'Data': raw_message}
                )
                logger.debug("Email sent, Message ID: %s", response['MessageId'])
                sent_count += 1
            except ClientError as e:
                logger.error("SES API error: %s", e.response['Error']['Message'])
                print(f"Error sending email: {e.response['Error']['Message']}")
                if not self.fail_silently:
                    raise e
            except Exception as e:
                logger.error("Unexpected error: %s", str(e))
                print(f"Unexpected error: {str(e)}")
                if not self.fail_silently:
                    raise e
        logger.debug("Sent %d emails successfully.", sent_count)
        return sent_count


class ReadableConsoleEmailBackend(BaseEmailBackend):
    """
    A console email backend that prints emails in a readable format.
    Extracts plain text and key information from email messages.
    """
    def send_messages(self, email_messages):
        import sys
        from email.utils import formatdate
        
        for message in email_messages:
            print("\n" + "=" * 80)
            print("📧 EMAIL (Console Output - Not Actually Sent)")
            print("=" * 80)
            print(f"To: {', '.join(message.to)}")
            print(f"From: {message.from_email}")
            print(f"Subject: {message.subject}")
            print("-" * 80)
            
            # Try to get plain text body
            if hasattr(message, 'body') and message.body:
                print("\n📄 Email Body:")
                print("-" * 80)
                print(message.body)
            
            # Try to extract HTML body and show key info
            if hasattr(message, 'alternatives') and message.alternatives:
                for content, mimetype in message.alternatives:
                    if mimetype == 'text/html':
                        import re
                        from django.utils.html import strip_tags
                        
                        # Extract password from HTML - try multiple patterns
                        password = None
                        # Pattern 1: <strong>Password</strong></span> value
                        password_match = re.search(r'<strong>Password</strong></span>\s*([^<\n]+)', content, re.IGNORECASE)
                        if password_match:
                            password = password_match.group(1).strip()
                        # Pattern 2: Password: value (in plain text parts)
                        if not password:
                            password_match = re.search(r'Password[:\s]+([^\s<]+)', content, re.IGNORECASE)
                            if password_match:
                                password = password_match.group(1).strip()
                        
                        # Extract email from HTML
                        email_addr = None
                        email_match = re.search(r'<strong>Email</strong></span>\s*([^<\n]+)', content, re.IGNORECASE)
                        if email_match:
                            email_addr = email_match.group(1).strip()
                        
                        # Display extracted information
                        if password:
                            print(f"\n🔑 PASSWORD: {password}")
                            print("⚠️  IMPORTANT: Save this password! It won't be shown again.")
                        
                        if email_addr:
                            print(f"📧 Email Address: {email_addr}")
                        
                        # Try to extract plain text from HTML (simple extraction)
                        plain_text = strip_tags(content)
                        # Remove excessive whitespace
                        plain_text = ' '.join(plain_text.split())
                        if plain_text:
                            print("\n📄 Email Content:")
                            print("-" * 80)
                            # Show first 800 chars
                            print(plain_text[:800] + ("..." if len(plain_text) > 800 else ""))
                        break
            
            # Also check plain text body for password
            if hasattr(message, 'body') and message.body:
                import re
                password_match = re.search(r'Password[:\s]+([^\s\n]+)', message.body, re.IGNORECASE)
                if password_match:
                    password = password_match.group(1).strip()
                    if password and len(password) > 5:  # Valid password length
                        print(f"\n🔑 PASSWORD (from plain text): {password}")
                        print("⚠️  IMPORTANT: Save this password! It won't be shown again.")
            
            print("=" * 80)
            print()
        
        return len(email_messages)
