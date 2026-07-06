# Security Policy

## Secrets

Do not commit real API keys, `.env` files, SQLite databases, runtime logs, or uploaded tender/qualification files.

API keys are encrypted before being stored in SQLite. The encryption master key is read from:

```text
RAG_TENDER_SECRET_KEY
```

If you reuse an existing database on another machine, configure the same `RAG_TENDER_SECRET_KEY`. If the key is lost, previously saved API keys cannot be decrypted and must be entered again.

## Deployment Notes

- Keep the backend on a trusted private machine or protected server.
- Do not expose the backend directly to the public internet without authentication and access control.
- Treat `data/`, `backend/output/`, logs, and uploaded files as sensitive runtime data.
- Rotate provider API keys if you suspect a database, log, environment variable, or machine compromise.

## Reporting

If you find a security issue, do not publish real secrets in an issue. Open a minimal report that describes the affected component and reproduction steps using fake credentials.
