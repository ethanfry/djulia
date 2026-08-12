from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)

    def __str__(self):
        return self.name


class Tag(models.Model):
    label = models.CharField(max_length=50)

    def __str__(self):
        return self.label


class Article(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    published = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(Author, related_name="articles", on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag, related_name="articles", blank=True)

    def __str__(self):
        return self.title
