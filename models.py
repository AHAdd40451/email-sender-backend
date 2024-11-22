from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, PyMongoError
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from dotenv import load_dotenv
import os

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
            logger.info(f"SMTP settings saved for user {self.user_id}")
            return self
        except Exception as e:
            logger.error(f"Error saving SMTP settings: {e}")
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

    def __init__(self, email, password_hash, _id=None):
        self.email = email
        self.password_hash = password_hash
        self._id = ObjectId(_id) if _id else None

    @classmethod
    def create(cls, email, password):
        if cls.collection.find_one({'email': email}):
            raise ValueError('Email already exists')
        
        password_hash = generate_password_hash(password)
        user_data = {
            'email': email,
            'password_hash': password_hash,
            'created_at': datetime.utcnow()
        }
        result = cls.collection.insert_one(user_data)
        return cls(email=email, password_hash=password_hash, _id=result.inserted_id)

    @classmethod
    def get_by_email(cls, email):
        user_data = cls.collection.find_one({'email': email})
        if user_data:
            return cls(
                email=user_data['email'],
                password_hash=user_data['password_hash'],
                _id=user_data['_id']
            )
        return None

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def id(self):
        return str(self._id) if self._id else None

class Log:
    collection = db['logs']

    @classmethod
    def add(cls, user_id, message, level='info'):
        log_data = {
            'user_id': user_id,
            'message': message,
            'level': level,
            'timestamp': datetime.utcnow()
        }
        cls.collection.insert_one(log_data)

    @classmethod
    def get_by_user(cls, user_id, limit=100):
        return list(cls.collection.find(
            {'user_id': user_id},
            {'_id': 0}
        ).sort('timestamp', -1).limit(limit))

    @classmethod
    def clear_user_logs(cls, user_id):
        cls.collection.delete_many({'user_id': user_id})

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