# djulia demo

A minimal Django project (`blog` app: authors, tags, articles) wired up with
djulia, so you can click through a live JSON:API — browsable HTML, filtering,
sorting, and auto-generated Swagger docs — against real data.

## Run it

From the **repository root**:

```bash
python3 -m venv venv_djulia
source venv_djulia/bin/activate
pip install -e .            # installs djulia + Django + django-filter

cd example
python manage.py migrate    # creates example.sqlite3
python manage.py seed       # sample authors/tags/articles (idempotent)
python manage.py runserver
```

> Use the venv's Python — `python manage.py ...`. A bare `py`/`python3` outside
> the activated venv won't have Django installed.

## Explore

- **Browsable API** — http://127.0.0.1:8000/api/articles/
  (a browser gets HTML with clickable links; API clients get JSON)
- **Swagger UI** — http://127.0.0.1:8000/api/docs/
- **OpenAPI schema** — http://127.0.0.1:8000/api/openapi.json
- Also `/api/authors/` and `/api/tags/`

Try the query features:

- Filter: `/api/articles/?filter[published]=true`, `/api/articles/?filter[title__icontains]=hello`
- Sort: `/api/articles/?sort=-title`
- Sparse fields: `/api/articles/?fields[articles]=title`
- Paginate: `/api/articles/?page[size]=1&page[number]=2`

## How it's wired

- `blog/models.py` — ordinary Django models.
- `blog/djulia_resources.py` — `api.register(Author)` etc. (autodiscovered on startup).
- `example/settings.py` — `"djulia"` in `INSTALLED_APPS`.
- `example/urls.py` — `path("api/", include("djulia.urls"))`.

Reset the demo data anytime with `python manage.py seed`. To start completely
fresh, delete `example/example.sqlite3` and re-run `migrate` + `seed`.
