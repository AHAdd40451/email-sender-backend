from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, PyMongoError
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from dotenv import load_dotenv
import os
import json
from bson.binary import Binary
import base64

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    # Use MongoDB URI from environment variable
    MONGODB_URI = os.getenv('MONGODB_URI')
    if not MONGODB_URI:
        raise ValueError("MongoDB URI not found in environment variables")

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    # Test the connection
    client.server_info()
    db = client['email_sender']  # Use the database name from your URI
    logger.info("Successfully connected to MongoDB Atlas")
except ServerSelectionTimeoutError as e:
    logger.error(f"Failed to connect to MongoDB (timeout): {e}")
    raise
except PyMongoError as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise

def setup_collections():
    try:
        # Create smtp_settings collection with schema validation
        db.create_collection('smtp_settings')
        db.command({
            'collMod': 'smtp_settings',
            'validator': {
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['user_id', 'smtp_server', 'smtp_port', 'username', 'password'],
                    'properties': {
                        'user_id': {'bsonType': 'objectId'},
                        'smtp_server': {'bsonType': 'string'},
                        'smtp_port': {'bsonType': 'int'},
                        'username': {'bsonType': 'string'},
                        'password': {'bsonType': 'string'},
                        'sender_name': {'bsonType': 'string'},
                        'delay': {'bsonType': 'int'},
                        'updated_at': {'bsonType': 'date'}
                    }
                }
            }
        })
        logger.info("Collections setup completed")
    except Exception as e:
        if 'already exists' not in str(e):
            logger.error(f"Error setting up collections: {e}")
            raise

    try:
        # Create users collection with updated schema validation
        db.create_collection('users')
        db.command({
            'collMod': 'users',
            'validator': {
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['email', 'password', 'created_at'],
                    'properties': {
                        'email': {'bsonType': 'string'},
                        'password': {'bsonType': 'string'},
                        'created_at': {'bsonType': 'date'}
                    }
                }
            }
        })
        logger.info("Collections setup completed")
    except Exception as e:
        if 'already exists' not in str(e):
            logger.error(f"Error setting up collections: {e}")
            raise

# Call setup_collections after establishing connection
setup_collections()

class SmtpSettings:
    collection = db['smtp_settings']

    def __init__(self, user_id, smtp_server, smtp_port, username, password, sender_name=None, delay=5):
        self.user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender_name = sender_name
        self.delay = delay

    @classmethod
    def get_by_user_id(cls, user_id):
        try:
            # Convert string ID to ObjectId if necessary
            user_id_obj = ObjectId(user_id) if isinstance(user_id, str) else user_id
            settings = cls.collection.find_one({'user_id': user_id_obj})
            if settings:
                return cls(
                    user_id=settings['user_id'],
                    smtp_server=settings['smtp_server'],
                    smtp_port=settings['smtp_port'],
                    username=settings['username'],
                    password=settings['password'],
                    sender_name=settings.get('sender_name'),
                    delay=settings.get('delay', 5)
                )
            return None
        except Exception as e:
            logger.error(f"Error retrieving SMTP settings: {e}")
            raise

    def save(self):
        try:
            settings_data = {
                'user_id': self.user_id,
                'smtp_server': self.smtp_server,
                'smtp_port': self.smtp_port,
                'username': self.username,
                'password': self.password,
                'sender_name': self.sender_name,
                'delay': self.delay,
                'updated_at': datetime.utcnow()
            }
            
            result = self.collection.update_one(
                {'user_id': self.user_id},
                {'$set': settings_data},
                upsert=True
            )
            
            from app import save_log
            save_log(str(self.user_id), 'smtp_settings', f"SMTP settings saved for user {self.user_id}")
            return self
        except Exception as e:
            from app import save_log
            save_log(str(self.user_id), 'smtp_settings', f"Error saving SMTP settings: {e}", 'error')
            raise

    def to_dict(self):
        return {
            'smtp_server': self.smtp_server,
            'smtp_port': self.smtp_port,
            'username': self.username,
            'password': self.password,
            'sender_name': self.sender_name,
            'delay': self.delay
        }

    @classmethod
    def save_settings(cls, user_id, smtp_server, smtp_port, username, password, sender_name=None, delay=5):
        # Convert string ID to ObjectId if necessary
        user_id_obj = ObjectId(user_id) if isinstance(user_id, str) else user_id
        settings = cls(
            user_id=user_id_obj,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            username=username,
            password=password,
            sender_name=sender_name,
            delay=delay
        )
        return settings.save()

class User:
    collection = db['users']

    def __init__(self, _id, email, password):
        self._id = _id
        self.email = email
        self.password = password

    @staticmethod
    def create_user(email, password):
        if db.users.find_one({'email': email}):
            raise ValueError('Email already registered')

        try:
            # Store password as plain text
            result = db.users.insert_one({
                'email': email,
                'password': password,  # Plain text password
                'created_at': datetime.utcnow()
            })
            
            return User(result.inserted_id, email, password)
            
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise ValueError(str(e))

    @staticmethod
    def get_by_email(email):
        user_data = db.users.find_one({'email': email})
        if user_data:
            return User(
                user_data['_id'],
                user_data['email'],
                user_data['password']  # Plain text password
            )
        return None

    def check_password(self, password):
        # Simple plain text comparison
        return self.password == password

    def to_dict(self):
        return {
            'id': str(self._id),
            'email': self.email
        }

class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class EmailTemplate:
    collection = db['email_templates']

    def __init__(self, user_id, name, subject, body):
        self.user_id = user_id
        self.name = name
        self.subject = subject
        self.body = body

    @classmethod
    def create(cls, user_id, name, subject, body):
        template_data = {
            'user_id': user_id,
            'name': name,
            'subject': subject,
            'body': body,
            'created_at': datetime.utcnow()
        }
        cls.collection.insert_one(template_data)
        return cls(user_id=user_id, name=name, subject=subject, body=body)

    @classmethod
    def get_by_user_id(cls, user_id):
        return list(cls.collection.find({'user_id': user_id}, {'_id': 0}))

    @classmethod
    def get_by_id(cls, template_id, user_id):
        template = cls.collection.find_one({
            '_id': ObjectId(template_id),
            'user_id': user_id
        })
        if template:
            return cls(
                user_id=template['user_id'],
                name=template['name'],
                subject=template['subject'],
                body=template['body']
            )
        return None

    def save(self):
        template_data = {
            'user_id': self.user_id,
            'name': self.name,
            'subject': self.subject,
            'body': self.body,
            'updated_at': datetime.utcnow()
        }
        self.collection.update_one(
            {'user_id': self.user_id, 'name': self.name},
            {'$set': template_data},
            upsert=True
        )
        return self

    def to_dict(self):
        return {
            'name': self.name,
            'subject': self.subject,
            'body': self.body
        }

class EmailList:
    collection = db['email_lists']

    def __init__(self, user_id, emails):
        self.user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
        self.emails = emails

    @classmethod
    def get_by_user_id(cls, user_id):
        try:
            user_id_obj = ObjectId(user_id) if isinstance(user_id, str) else user_id
            result = cls.collection.find_one({'user_id': user_id_obj})
            if result:
                return cls(user_id=result['user_id'], emails=result['emails'])
            return None
        except Exception as e:
            logger.error(f"Error retrieving email list: {e}")
            raise

    def save(self):
        try:
            data = {
                'user_id': self.user_id,
                'emails': self.emails,
                'updated_at': datetime.utcnow()
            }
            
            result = self.collection.update_one(
                {'user_id': self.user_id},
                {'$set': data},
                upsert=True
            )
            return self
        except Exception as e:
            logger.error(f"Error saving email list: {e}")
            raise

    def to_dict(self):
        return {
            'emails': self.emails
        }