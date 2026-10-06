import uuid

from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)


class Tag(models.Model):
    label = models.CharField(max_length=50)


class Article(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    published = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(Author, related_name="articles", on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag, related_name="articles", blank=True)


class Widget(models.Model):
    name = models.CharField(max_length=100)
    visible = models.BooleanField(default=True)


class Currency(models.Model):
    """A natural primary key: clients must supply the id."""
    code = models.CharField(max_length=3, primary_key=True)
    name = models.CharField(max_length=50)

    class Meta:
        verbose_name_plural = "currencies"


class Token(models.Model):
    """A primary key with a default: clients may supply the id."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    label = models.CharField(max_length=50)
