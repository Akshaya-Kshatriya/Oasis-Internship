# Secure Chat Application

An advanced, real-time chat platform featuring user authentication, multiple rooms, multimedia sharing, emoji support, notifications, message history, and encrypted message storage. The project is implemented with a FastAPI backend and a lightweight HTML/JavaScript frontend for straightforward demos and testing.

## Features

- **User Authentication**: Register and log in with securely hashed passwords and JWT-based sessions.
- **Multiple Chat Rooms**: Pre-seeded rooms plus the ability to create new ones.
- **Real-Time Messaging**: WebSocket-based messaging with presence notifications.
- **Multimedia Sharing**: Upload images, videos, and files; shared assets are available under `/media`.
- **Message History**: Persisted chat history per room powered by SQLite.
- **Emoji Support**: Quick emoji picker in the composer.
- **Notifications**: Browser notifications and visual badges for new messages.
- **Encryption**: Message bodies are encrypted at rest using Fernet symmetric encryption.

## Project Structure

```
backend/           # FastAPI application
  app/
    config.py
    main.py
    models.py
    crud.py
    security.py
    ...
frontend/          # Static frontend (served by FastAPI)
  index.html
  static/
    app.js
    styles.css
media/             # Uploaded user content
requirements.txt   # Python dependencies
```

## Getting Started

1. **Create a virtual environment & install dependencies**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # PowerShell
   pip install -r requirements.txt
   ```

2. **Environment variables**
   - Create a `.env` file in the project root with the values:
     ```env
     SECRET_KEY=super-secret-key
     DATABASE_URL=sqlite:///./chat.db
     ACCESS_TOKEN_EXPIRE_MINUTES=120
     ENCRYPTION_KEY=        # optional; leave blank to auto-generate `.fernet_key`
     CORS_ALLOW_ORIGINS=["http://localhost:8000","http://127.0.0.1:8000"]
     ```
   - If `ENCRYPTION_KEY` is omitted, the app auto-generates a Fernet key and stores it in `.fernet_key`.

3. **Run the server**
   
   For local development only:
   ```bash
   uvicorn backend.app.main:app --reload --port 8000
   ```
   
   For port forwarding / external access:
   ```bash
   uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   
   **Note**: Using `--host 0.0.0.0` allows the server to accept connections from any network interface, which is required for port forwarding. The default `127.0.0.1` only accepts local connections.

4. **Open the frontend**
   - Navigate to [http://localhost:8000](http://localhost:8000) to use the chat client.

## Usage Tips

- Register a user, log in, then pick a room. Message history loads automatically.
- Use the emoji button or keyboard shortcuts (`Shift+Enter` for new lines, `Enter` to send).
- Upload multimedia via the clip icon; the file is stored under `media/` and broadcast to all participants.
- Allow browser notifications to receive alerts while the window is unfocused.
- Use HTTPS in production to secure WebSocket traffic and file uploads end to end.

## Security Notes

- Passwords are hashed with bcrypt using Passlib.
- JWT tokens encode the username and expire based on `ACCESS_TOKEN_EXPIRE_MINUTES`.
- Message bodies are encrypted before being persisted in the database. Set `ENCRYPTION_KEY` in production so the same key is reused across restarts.
- For production hardening, configure proper CORS origins, HTTPS termination, and consider moving media to dedicated object storage.

## Development Tasks

- Run unit/integration tests (not yet included) for authentication and room logic.
- Expand the UI for room creation & management, typing indicators, read receipts, etc.
- Integrate an async task queue (e.g., Celery) for large file processing if necessary.

## Troubleshooting

- **WebSocket disconnects immediately**: Ensure the JWT token is stored and appended to the WebSocket URL. Check for expired logins and restart the session.
- **Encryption errors**: Delete `.fernet_key` (only in development) or set `ENCRYPTION_KEY` explicitly if the key becomes inconsistent.
- **Notifications not appearing**: Confirm the browser has allowed notifications and the tab is not in focus (notifications only fire when hidden).

---

Feel free to extend the application with additional enterprise features such as message search, moderation tools, or mobile-friendly layouts.

