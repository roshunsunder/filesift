#!/bin/bash

# Development environment setup script
set -e

echo "Setting up development environment..."

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required but not installed. Aborting." >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js is required but not installed. Aborting." >&2; exit 1; }
command -v psql >/dev/null 2>&1 || { echo "PostgreSQL is required but not installed. Aborting." >&2; exit 1; }

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install backend dependencies
echo "Installing backend dependencies..."
cd backend
pip install --upgrade pip
pip install -r requirements.txt
cd ..

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..

# Setup environment variables
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env with your configuration"
fi

# Create database
echo "Setting up database..."
DB_NAME="app_db"
if psql -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
    echo "Database $DB_NAME already exists"
else
    createdb $DB_NAME
    echo "Database $DB_NAME created"
fi

# Run migrations
echo "Running database migrations..."
psql $DB_NAME -f database/migrations/001_create_users_table.sql
psql $DB_NAME -f database/migrations/002_create_posts_table.sql

# Seed database
echo "Seeding database..."
psql $DB_NAME -f database/seeds/users_seed.sql

echo "Setup complete!"
echo ""
echo "To start the development server:"
echo "  Backend: cd backend && python app.py"
echo "  Frontend: cd frontend && npm start"
echo ""
echo "Or use Docker: docker-compose up"
