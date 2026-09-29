# Repository Guide

## Project

- This is a Python command-line assistant that recommends statistical methods from a research description.
- The active application entry point is the root-level `main.py`.
- Runtime dependencies are listed in `requirements.txt`: OpenAI, Pydantic, and python-dotenv.
- The application expects `OPENAI_API_KEY` in a local `.env` file beside `main.py` and calls the OpenAI API.

## Working In This Repository

- Keep changes focused on the active root-level application unless the task explicitly targets another path.
- Preserve the existing decision-tree behavior and structured Pydantic extraction models when changing recommendation logic.
- Do not hardcode, print, or commit API keys or other secrets. Keep credentials in the local environment.
- There is no configured test suite or project-level test command. For Python edits, at minimum run `python -m py_compile main.py`; use focused tests when adding them or when a task defines a test command.
- To run the CLI, install dependencies with `pip install -r requirements.txt` and execute `python main.py` from the repository root. A valid OpenAI API key is required for interactive use.