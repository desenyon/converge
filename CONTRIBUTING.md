## Contributing to Converge

First off, thank you for considering contributing to Converge. It's people like you that make Converge such a great tool.

### 1. Where do I go from here?

If you've noticed a bug or have a feature request, make one! It's generally best if you get confirmation of your bug or approval for your feature request this way before starting to code.

### 2. Fork & create a branch

If this is something you think you can fix, then fork Converge and create a branch with a descriptive name.

### 3. Get the test suite running

Make sure you have `uv` installed.
```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Now, run the tests:
```bash
pytest tests/
ruf check src/ tests/
mypy src/ tests/
```

### 4. Implement your fix or feature

At this point, you're ready to make your changes. Feel free to ask for help; everyone is a beginner at first.

### 5. Create a Pull Request

Create a pull request with a clear list of what you've done. We can always help you review.
