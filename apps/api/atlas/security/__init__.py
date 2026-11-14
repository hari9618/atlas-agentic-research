"""Authentication, authorization and abuse limits for the Atlas API.

* ``passwords`` — Argon2id hashing (OWASP's first choice).
* ``store``     — users, refresh-token families, the shared signing secret.
* ``tokens``    — short-lived JWT access tokens.
* ``service``   — register / login / guest / refresh (rotation + reuse detection) / logout.
* ``deps``      — FastAPI dependencies: ``current_user``, ``require_admin``.
* ``limits``    — per-plan rate limits and run admission (concurrency) control.
"""
