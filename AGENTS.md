# Repository Guide

## Project

- This is a Python command-line assistant that recommends statistical methods from a research description.
- The web app is `server.py` (FastAPI) serving the page in `static/`; `main.py` is the CLI entry point and holds the OpenAI helpers both use. All decision logic lives in `stat_engine.py`.
- Runtime dependencies are listed in `requirements.txt`: OpenAI, Pydantic, python-dotenv, FastAPI and Uvicorn.
- The application expects `OPENAI_API_KEY` in a local `.env` file beside `main.py` (or as a real environment variable when deployed, e.g. on Render) and calls the OpenAI API.

## Working In This Repository

- Keep changes focused on the active root-level application unless the task explicitly targets another path.
- Preserve the existing decision-tree behavior and structured Pydantic extraction models when changing recommendation logic.
- Do not hardcode, print, or commit API keys or other secrets. Keep credentials in the local environment.
- There is no configured test suite or project-level test command. For Python edits, at minimum run `python -m py_compile main.py server.py stat_engine.py`; use focused tests when adding them or when a task defines a test command.
- To run the web app, install dependencies with `pip install -r requirements.txt` and run `uvicorn server:app --reload` from the repository root. To run the CLI, execute `python main.py`. A valid OpenAI API key is required for the advisor chat and the CLI.