# Choosing-statistical-method
Tool to leverage LLM to help user find the best statistical tool for their data

## Run the web app

```sh
pip install -r requirements.txt
uvicorn server:app --reload
```

Then open http://127.0.0.1:8000. The questions work without an API key; the "Describe your study" advisor needs `OPENAI_API_KEY` in a `.env` file beside `main.py`. The `.env` file is gitignored, so on a host such as Render set `OPENAI_API_KEY` as an environment variable in the service settings instead.

- `stat_engine.py` holds the questions, the test catalog and the decision logic.
- `quiz_bank.py` holds the Quiz yourself questions; its Pick the Method answers are checked against the engine at import.
- `server.py` is a small FastAPI app that serves the page in `static/` and wraps the engine and the OpenAI helpers in `main.py`.
- `python main.py` still runs the command-line advisor.
