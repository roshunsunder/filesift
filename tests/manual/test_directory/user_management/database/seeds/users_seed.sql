-- Seed data for users table
-- Note: These passwords are hashed versions of 'Password123!'

INSERT INTO users (username, email, password_hash, is_active, created_at) VALUES
('admin', 'admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLaOhWju', true, '2024-01-01 10:00:00'),
('johndoe', 'john.doe@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLaOhWju', true, '2024-01-05 14:30:00'),
('janedoe', 'jane.doe@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLaOhWju', true, '2024-01-07 09:15:00'),
('bobsmith', 'bob.smith@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLaOhWju', false, '2024-01-10 16:45:00'),
('alicejones', 'alice.jones@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLaOhWju', true, '2024-01-12 11:20:00');
