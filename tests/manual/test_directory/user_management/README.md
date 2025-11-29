# User Management Application

A full-stack user management application built with React, TypeScript, Flask, and PostgreSQL.

## Features

- User authentication with JWT
- User CRUD operations
- RESTful API
- Responsive UI with React
- PostgreSQL database with migrations
- Docker support

## Tech Stack

### Frontend
- React 18
- TypeScript
- Axios for API calls
- CSS3 for styling

### Backend
- Flask (Python)
- SQLAlchemy ORM
- JWT for authentication
- PostgreSQL database
- Bcrypt for password hashing

## Getting Started

### Prerequisites

- Node.js 16+
- Python 3.9+
- PostgreSQL 15+
- Docker (optional)

### Installation

1. Clone the repository
```bash
git clone https://github.com/yourorg/user-management-app.git
cd user-management-app
```

2. Install dependencies
```bash
make install
```

3. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run database migrations
```bash
make migrate
make seed
```

### Running the Application

#### Using Docker
```bash
docker-compose up
```

#### Manual Start
```bash
# Terminal 1 - Backend
cd backend
python app.py

# Terminal 2 - Frontend
cd frontend
npm start
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:5000

## API Documentation

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration

### Users
- `GET /api/users` - Get all users (paginated)
- `GET /api/users/:id` - Get user by ID
- `POST /api/users` - Create new user
- `PUT /api/users/:id` - Update user
- `DELETE /api/users/:id` - Delete user

## Testing

```bash
make test
```

## Project Structure

```
.
├── backend/
│   ├── src/
│   │   ├── api/          # API routes
│   │   ├── models/       # Database models
│   │   ├── services/     # Business logic
│   │   └── utils/        # Helper functions
│   └── tests/            # Backend tests
├── frontend/
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── pages/        # Page components
│   │   ├── hooks/        # Custom hooks
│   │   ├── utils/        # Utility functions
│   │   └── types/        # TypeScript types
│   └── public/           # Static assets
├── database/
│   ├── migrations/       # SQL migrations
│   └── seeds/            # Seed data
└── config/               # Configuration files

```

## License

MIT
