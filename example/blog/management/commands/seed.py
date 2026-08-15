"""Populate the demo DB with a few rows so the browsable API has data to explore.

Idempotent: clears existing blog rows first, so it's safe to re-run.
"""
from django.core.management.base import BaseCommand

from blog.models import Article, Author, Tag


class Command(BaseCommand):
    help = "Seed the demo database with sample blog data."

    def handle(self, *args, **options):
        Article.objects.all().delete()
        Author.objects.all().delete()
        Tag.objects.all().delete()

        ada = Author.objects.create(name="Ada Lovelace", email="ada@example.com")
        grace = Author.objects.create(name="Grace Hopper", email="grace@example.com")
        python = Tag.objects.create(label="python")
        web = Tag.objects.create(label="web")
        history = Tag.objects.create(label="history")

        hello = Article.objects.create(
            title="Hello, JSON:API", body="A first look at djulia.",
            published=True, author=ada)
        hello.tags.set([python, web])

        compilers = Article.objects.create(
            title="On Compilers", body="Notes from the first compiler.",
            published=True, author=grace)
        compilers.tags.set([history])

        Article.objects.create(
            title="Draft Post", body="", published=False, author=ada)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Author.objects.count()} authors, {Tag.objects.count()} tags, "
            f"{Article.objects.count()} articles."))
