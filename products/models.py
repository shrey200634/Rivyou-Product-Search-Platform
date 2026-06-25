from django.db import models


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, db_index=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    product_name = models.CharField(max_length=255, db_index=True)
    product_description = models.TextField()
    category = models.CharField(max_length=100, db_index=True)
    tags = models.ManyToManyField(Tag, related_name='products', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['product_name']

    def __str__(self):
        return self.product_name