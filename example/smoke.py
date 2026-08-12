"""End-to-end smoke test: build a DB in memory, hit every endpoint via the test client."""
import json
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example.settings")
django.setup()

from django.core.management import call_command  # noqa: E402
from django.test import Client  # noqa: E402

call_command("migrate", run_syncdb=True, verbosity=0)

from blog.models import Article, Author, Tag  # noqa: E402

ada = Author.objects.create(name="Ada Lovelace", email="ada@example.com")
python, web = Tag.objects.create(label="python"), Tag.objects.create(label="web")
hello = Article.objects.create(title="Hello", body="world", published=True, author=ada)
hello.tags.set([python, web])
Article.objects.create(title="Draft", body="", published=False, author=ada)

client = Client()
JSONAPI = "application/vnd.api+json"


def show(label, resp):
    print(f"\n=== {label} -> {resp.status_code} {resp.get('content-type')} ===")
    body = resp.content
    if body:
        try:
            print(json.dumps(resp.json(), indent=2, default=str))
        except ValueError:
            print(body[:400])


show("LIST articles", client.get("/api/articles/"))
show("RETRIEVE article", client.get(f"/api/articles/{hello.pk}/"))
show("FILTER published=true", client.get("/api/articles/?filter[published]=true"))
show("FILTER title__icontains=hel", client.get("/api/articles/?filter[title__icontains]=hel"))
show("SORT -title", client.get("/api/articles/?sort=-title"))
show("SPARSE fields[articles]=title", client.get("/api/articles/?fields[articles]=title"))
show("PAGINATE size=1", client.get("/api/articles/?page[size]=1&page[number]=1"))

create = {
    "data": {
        "type": "articles",
        "attributes": {"title": "Created via API", "body": "b", "published": True},
        "relationships": {"author": {"data": {"type": "authors", "id": str(ada.pk)}}},
    }
}
show("CREATE", client.post("/api/articles/", data=json.dumps(create), content_type=JSONAPI))

patch = {"data": {"type": "articles", "id": str(hello.pk),
                  "attributes": {"title": "Hello (edited)"}}}
show("PATCH", client.patch(f"/api/articles/{hello.pk}/", data=json.dumps(patch),
                           content_type=JSONAPI))

show("DELETE", client.delete(f"/api/articles/{hello.pk}/"))
show("BAD sort", client.get("/api/articles/?sort=nope"))
show("404", client.get("/api/articles/999999/"))


def show_meta(label, resp, *, snippet=200):
    ok = "OK" if resp.status_code == 200 else "FAIL"
    print(f"\n=== {label} -> {resp.status_code} {resp.get('content-type')} [{ok}] ===")
    print(resp.content[:snippet].decode(errors="replace"))


# Browsable API: a browser (Accept: text/html) gets HTML, not JSON.
show_meta("BROWSABLE list (Accept text/html)",
          client.get("/api/articles/", HTTP_ACCEPT="text/html"))
# OpenAPI schema, generated from the registry.
openapi = client.get("/api/openapi.json")
print(f"\n=== OPENAPI /api/openapi.json -> {openapi.status_code} ===")
spec = openapi.json()
print("openapi:", spec["openapi"], "| title:", spec["info"]["title"])
print("paths:", sorted(spec["paths"]))
print("schemas:", sorted(spec["components"]["schemas"]))
print("article attribute types:",
      {k: v.get("format", v["type"])
       for k, v in spec["components"]["schemas"]["articles"]["properties"]["attributes"]["properties"].items()})
print("article list filter params:",
      [p["name"] for p in spec["paths"]["/articles/"]["get"]["parameters"] if p["name"].startswith("filter")])
# Swagger UI page.
show_meta("SWAGGER UI /api/docs/", client.get("/api/docs/"), snippet=120)

print("\nSMOKE DONE")
