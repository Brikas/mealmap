1) Install Python 3.11
- Install via Homebrew:
  - brew install python@3.11
- Ensure it’s on PATH (zsh):
  - echo 'export PATH="/opt/homebrew/opt/python@3.11/bin:$PATH"' >> ~/.zshrc
  - source ~/.zshrc

Install `poetry`

```bash
pip install poetry
```

Initialize `peotry`

```bash
poetry install
```


Create a new Poetry venv bound to Python 3.11
- Point Poetry at the 3.11 binary:
  - poetry env use /opt/homebrew/bin/python3.11
- Install deps fresh:
  - poetry install
