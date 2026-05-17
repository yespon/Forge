# Contributing

## Development Setup
```bash
git clone https://github.com/your-org/forge.git
cd forge
cd backend && poetry install
cd ../frontend && npm install
```

## Code Style
- Python: Black, isort, flake8
- TypeScript: Prettier, ESLint
- Run `poetry run pre-commit run --all-files` before committing

## Testing
```bash
poetry run pytest backend/tests/
```

## Pull Request Process
1. Create a feature branch
2. Add tests for new functionality
3. Ensure all tests pass
4. Submit PR with description
