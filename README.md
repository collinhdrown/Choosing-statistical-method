# Choosing-statistical-method
Tool to leverage LLM to help user find the best statistical tool for their data

## Run the web app

```sh
pip install -r requirements.txt
uvicorn server:app --reload
```

Then open http://127.0.0.1:8000. The questions work without an API key; the "Describe your study" advisor needs `OPENAI_API_KEY` in a `.env` file beside `main.py`.

- `stat_engine.py` holds the questions, the test catalog and the decision logic.
- `server.py` is a small FastAPI app that serves the page in `static/` and wraps the engine and the OpenAI helpers in `main.py`.
- `python main.py` still runs the command-line advisor.
