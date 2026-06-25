from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import Product, Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['name']


class ProductSerializer(serializers.ModelSerializer):
    """Serializes a Product with its tags as a flat list of strings.

    The optional `relevance_score` and `rank_reason` fields are populated
    dynamically by the search view — they are *not* stored in the database.
    """
    tags = serializers.SerializerMethodField()
    relevance_score = serializers.FloatField(read_only=True, required=False, default=None)
    rank_reason = serializers.CharField(read_only=True, required=False, default=None)

    class Meta:
        model = Product
        fields = [
            'id',
            'product_name',
            'product_description',
            'category',
            'tags',
            'relevance_score',
            'rank_reason',
        ]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_tags(self, obj):
        """Return tags as a flat list of strings instead of nested objects."""
        return list(obj.tags.values_list('name', flat=True))



class ProductCreateSerializer(serializers.ModelSerializer):
    """Used for POST /api/products/ — accepts tags as a list of strings."""
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        write_only=True,
        required=False,
        default=[],
    )

    class Meta:
        model = Product
        fields = ['id', 'product_name', 'product_description', 'category', 'tags']

    def create(self, validated_data):
        tag_names = validated_data.pop('tags', [])
        product = Product.objects.create(**validated_data)

        tag_objects = []
        for name in tag_names:
            tag_obj, _ = Tag.objects.get_or_create(name=name.strip().lower())
            tag_objects.append(tag_obj)
        product.tags.set(tag_objects)

        return product
