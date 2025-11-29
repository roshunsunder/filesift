# API Documentation

## Base URL
```
http://localhost:5000/api
```

## Authentication

All authenticated endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <token>
```

### Login
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "username": "johndoe",
    "email": "user@example.com"
  }
}
```

## Users

### Get All Users
```http
GET /users?page=1&per_page=20
Authorization: Bearer <token>
```

**Query Parameters:**
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Items per page (default: 20)

**Response:**
```json
{
  "users": [
    {
      "id": 1,
      "username": "johndoe",
      "email": "john@example.com",
      "is_active": true,
      "created_at": "2024-01-15T10:30:00",
      "updated_at": "2024-01-15T10:30:00"
    }
  ],
  "total": 50,
  "page": 1,
  "per_page": 20
}
```

### Get User by ID
```http
GET /users/:id
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": 1,
  "username": "johndoe",
  "email": "john@example.com",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:00"
}
```

### Create User
```http
POST /users
Content-Type: application/json
Authorization: Bearer <token>

{
  "username": "newuser",
  "email": "newuser@example.com",
  "password": "SecurePass123!"
}
```

**Response:** `201 Created`
```json
{
  "id": 2,
  "username": "newuser",
  "email": "newuser@example.com",
  "is_active": true,
  "created_at": "2024-01-16T14:20:00",
  "updated_at": "2024-01-16T14:20:00"
}
```

### Update User
```http
PUT /users/:id
Content-Type: application/json
Authorization: Bearer <token>

{
  "username": "updateduser",
  "is_active": false
}
```

### Delete User
```http
DELETE /users/:id
Authorization: Bearer <token>
```

**Response:** `204 No Content`

## Error Responses

### 400 Bad Request
```json
{
  "error": "Invalid email format"
}
```

### 401 Unauthorized
```json
{
  "error": "Invalid credentials"
}
```

### 404 Not Found
```json
{
  "error": "User not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error"
}
```
