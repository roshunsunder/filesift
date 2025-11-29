import pytest
from services.auth_service import AuthService
from models.user import User

class TestAuthService:
    def test_hash_password(self):
        """Test password hashing"""
        password = "TestPassword123"
        hashed = AuthService.hash_password(password)

        assert hashed != password
        assert len(hashed) > 0

    def test_verify_password(self):
        """Test password verification"""
        password = "TestPassword123"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(password, hashed) is True
        assert AuthService.verify_password("WrongPassword", hashed) is False

    def test_generate_token(self):
        """Test JWT token generation"""
        user_id = 1
        token = AuthService.generate_token(user_id)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token(self):
        """Test JWT token verification"""
        user_id = 1
        token = AuthService.generate_token(user_id)
        payload = AuthService.verify_token(token)

        assert payload['user_id'] == user_id
        assert 'exp' in payload
        assert 'iat' in payload

    def test_verify_invalid_token(self):
        """Test verification of invalid token"""
        with pytest.raises(ValueError):
            AuthService.verify_token("invalid_token")
