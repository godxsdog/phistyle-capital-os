# Migrations

Alembic migration scaffold for PhiStyle OS.

Apply migrations from inside the backend container with:

```sh
python -m alembic -c /app/alembic.ini upgrade head
```

Create revisions later with:

```sh
alembic revision --autogenerate -m "message"
```
