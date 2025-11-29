import jwt
import bcrypt
from datetime import datetime, timedelta
from config.settings import SECRET_KEY, TOKEN_EXPIRATION

class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its hash"""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            password_hash.encode('utf-8')
        )

    @staticmethod
    def generate_token(user_id: int) -> str:
        """Generate a JWT token for a user"""
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(seconds=TOKEN_EXPIRATION),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

    @staticmethod
    def verify_token(token: str) -> dict:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError('Token has expired')
        except jwt.InvalidTokenError:
            raise ValueError('Invalid token')
