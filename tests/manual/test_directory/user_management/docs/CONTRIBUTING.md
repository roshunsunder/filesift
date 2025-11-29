# Contributing Guidelines

Thank you for considering contributing to this project! Here are some guidelines to help you get started.

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on what is best for the community
- Show empathy towards other community members

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported
2. Create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, browser, versions)
   - Screenshots if applicable

### Suggesting Features

1. Check if the feature has already been suggested
2. Create a new issue explaining:
   - The problem it solves
   - Proposed solution
   - Alternative solutions considered
   - Additional context

### Pull Requests

1. Fork the repository
2. Create a new branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Write or update tests
5. Ensure all tests pass
6. Update documentation
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to your branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## Development Guidelines

### Code Style

#### Python
- Follow PEP 8
- Use type hints where applicable
- Maximum line length: 100 characters
- Use meaningful variable names

#### TypeScript/React
- Follow Airbnb style guide
- Use functional components with hooks
- Use TypeScript strict mode
- Prefer const over let

### Testing

- Write tests for all new features
- Maintain test coverage above 80%
- Include both unit and integration tests
- Test edge cases and error conditions

### Commit Messages

Format:
```
<type>: <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Build/tooling changes

Example:
```
feat: Add user profile avatar upload

- Add file upload endpoint
- Update user model with avatar field
- Add frontend component for avatar selection

Closes #123
```

## Questions?

Feel free to open an issue for any questions or concerns!
