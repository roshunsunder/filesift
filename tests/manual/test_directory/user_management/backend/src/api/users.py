from flask import Blueprint, request, jsonify
from models.user import User
from services.auth_service import AuthService
from utils.validators import validate_email

users_bp = Blueprint('users', __name__)

@users_bp.route('/api/users', methods=['GET'])
def get_users():
    """Retrieve all users with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    users = User.query.paginate(page=page, per_page=per_page)
    return jsonify({
        'users': [u.to_dict() for u in users.items],
        'total': users.total,
        'page': page,
        'per_page': per_page
    })

@users_bp.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get a specific user by ID"""
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())

@users_bp.route('/api/users', methods=['POST'])
def create_user():
    """Create a new user"""
    data = request.get_json()

    if not validate_email(data.get('email')):
        return jsonify({'error': 'Invalid email'}), 400

    user = User(
        username=data['username'],
        email=data['email'],
        password_hash=AuthService.hash_password(data['password'])
    )

    user.save()
    return jsonify(user.to_dict()), 201
