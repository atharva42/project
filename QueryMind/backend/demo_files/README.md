# Demo files (TEMPORARY)

Drop `.csv` and `.pdf` files here. On the first request to `GET /demo/datasets`
(the frontend calls this automatically on load), each file is seeded as a
**shared, preloaded session** that any logged-in user can query without
uploading anything.

- One session is created per file.
- Sessions are created with `user_id=None`, so they're accessible to everyone.
- A registry is written to `../demo_sessions.json` so files aren't re-seeded
  on restart. Delete that file (and re-hit the endpoint) to force a re-seed.

This whole feature is temporary — see the removal steps in `routes/demo.py`.
