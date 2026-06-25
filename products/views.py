from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, inline_serializer

from .models import Product
from .serializers import ProductCreateSerializer, ProductSerializer


# ---------------------------------------------------------------------------
# Search ranking helpers
# ---------------------------------------------------------------------------

def _compute_relevance(product, query):
    """Return (relevance_score, rank_reason) for a single product.

    Tier 1  (0.85 – 1.00): category matches the query
    Tier 2  (0.50 – 0.80): a tag matches the query (category does not)
    Tier 3  (0.10 – 0.45): product_name or description contains the query
    """
    query_lower = query.lower()
    category_lower = product.category.lower()
    name_lower = product.product_name.lower()
    desc_lower = product.product_description.lower()

    # Pre-fetch tag names (already loaded if prefetch_related was used)
    tag_names = list(product.tags.values_list('name', flat=True))

    # ---- Tier 1: Category match ----
    if query_lower in category_lower or category_lower in query_lower:
        # Base score 0.85; bonus up to 0.15 based on how many tags also match
        matching_tags = sum(1 for t in tag_names if query_lower in t or t in query_lower)
        tag_bonus = min(matching_tags * 0.03, 0.15)
        score = round(0.85 + tag_bonus, 2)
        return score, "Category match"

    # ---- Tier 2: Tag match ----
    exact_tag_match = any(t == query_lower for t in tag_names)
    partial_tag_match = any(query_lower in t or t in query_lower for t in tag_names)

    if exact_tag_match:
        # Exact tag match: 0.70 – 0.80
        matching_count = sum(1 for t in tag_names if t == query_lower)
        bonus = min(matching_count * 0.05, 0.10)
        score = round(0.70 + bonus, 2)
        return score, f"Tag match ({query})"
    elif partial_tag_match:
        # Partial tag match: 0.50 – 0.65
        matching_count = sum(1 for t in tag_names if query_lower in t or t in query_lower)
        bonus = min(matching_count * 0.05, 0.15)
        score = round(0.50 + bonus, 2)
        return score, f"Tag match (partial: {query})"

    # ---- Tier 3: Name or description match ----
    name_match = query_lower in name_lower
    desc_match = query_lower in desc_lower

    if name_match and desc_match:
        return 0.45, "Name and description match"
    elif name_match:
        return 0.40, "Name match"
    elif desc_match:
        return 0.20, "Description match"

    # Fallback (shouldn't normally be reached if we pre-filter)
    return 0.0, "No match"


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@extend_schema(
    summary="Search and Rank Products",
    description=(
        "Search products with a 3-tier relevance engine:\n\n"
        "1. **Tier 1 (0.85 - 1.00)**: Category match (boosted if tags match)\n"
        "2. **Tier 2 (0.50 - 0.80)**: Tag match (exact matches higher than partial)\n"
        "3. **Tier 3 (0.10 - 0.45)**: Product name/description match\n\n"
        "Results are sorted by relevance_score descending, then by name."
    ),
    parameters=[
        OpenApiParameter(name='q', description='Search query term', required=True, type=str),
        OpenApiParameter(name='limit', description='Max results to return (1-100, default 20)', required=False, type=int),
        OpenApiParameter(name='category_filter', description='Optional exact filter by category name', required=False, type=str),
    ],
    responses={
        200: inline_serializer(
            name="SearchSuccessResponse",
            fields={
                "query": serializers.CharField(),
                "total_results": serializers.IntegerField(),
                "limit": serializers.IntegerField(),
                "results": ProductSerializer(many=True),
            }
        ),
        400: inline_serializer(
            name="SearchErrorResponse",
            fields={
                "detail": serializers.CharField()
            }
        )
    }
)
class ProductSearchView(APIView):
    """GET /api/products/search?q=<query>&limit=20&category_filter=<cat>

    Returns products ranked by a three-tier relevance system:
      Tier 1 – category match  |  Tier 2 – tag match  |  Tier 3 – name/desc match
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response(
                {'detail': 'Query parameter "q" is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse limit (default 20, max 100)
        try:
            limit = int(request.query_params.get('limit', 20))
            limit = max(1, min(limit, 100))
        except (ValueError, TypeError):
            limit = 20

        category_filter = request.query_params.get('category_filter', '').strip()

        # ----- Build broad queryset -----
        q_lower = query.lower()
        qs = Product.objects.prefetch_related('tags').filter(
            Q(category__icontains=q_lower)
            | Q(tags__name__icontains=q_lower)
            | Q(product_name__icontains=q_lower)
            | Q(product_description__icontains=q_lower)
        ).distinct()

        # Optional hard filter by category
        if category_filter:
            qs = qs.filter(category__iexact=category_filter)

        # ----- Score every matching product -----
        scored = []
        for product in qs:
            score, reason = _compute_relevance(product, query)
            product.relevance_score = score
            product.rank_reason = reason
            scored.append(product)

        # Sort descending by score, then by product name as tiebreaker
        scored.sort(key=lambda p: (-p.relevance_score, p.product_name))

        total = len(scored)
        page = scored[:limit]

        serializer = ProductSerializer(page, many=True)
        return Response({
            'query': query,
            'total_results': total,
            'limit': limit,
            'results': serializer.data,
        })


@extend_schema(
    summary="Retrieve Product Details",
    description="Retrieve a single product's details by its ID.",
    responses={
        200: ProductSerializer,
        404: inline_serializer(
            name="NotFoundErrorResponse",
            fields={"detail": serializers.CharField()}
        )
    }
)
class ProductDetailView(APIView):
    """GET /api/products/<id>/ — Retrieve a single product by its primary key."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        product = get_object_or_404(Product.objects.prefetch_related('tags'), pk=pk)
        serializer = ProductSerializer(product)
        return Response(serializer.data)


@extend_schema(
    summary="List Products by Category",
    description="Retrieve all products belonging to a specific category.",
    responses={
        200: inline_serializer(
            name="CategoryProductsSuccessResponse",
            fields={
                "category": serializers.CharField(),
                "total_results": serializers.IntegerField(),
                "results": ProductSerializer(many=True)
            }
        ),
        404: inline_serializer(
            name="CategoryNotFoundErrorResponse",
            fields={"detail": serializers.CharField()}
        )
    }
)
class ProductByCategoryView(APIView):
    """GET /api/products/category/<category>/ — List all products in a category."""
    permission_classes = [IsAuthenticated]

    def get(self, request, category):
        products = Product.objects.prefetch_related('tags').filter(
            category__iexact=category
        )
        if not products.exists():
            return Response(
                {'detail': f'No products found in category "{category}".'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProductSerializer(products, many=True)
        return Response({
            'category': category,
            'total_results': products.count(),
            'results': serializer.data,
        })


@extend_schema(
    summary="Create a Product (Admin Only)",
    description="Create a new product with custom tags. Access is restricted to Admin users.",
    request=ProductCreateSerializer,
    responses={
        201: ProductSerializer,
        400: OpenApiResponse(description="Validation error"),
        403: OpenApiResponse(description="Forbidden - Admin rights required")
    }
)
class ProductCreateView(APIView):
    """POST /api/products/ — Create a new product (admin only)."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = ProductCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        product = serializer.save()

        # Return the full product representation
        output = ProductSerializer(product)
        return Response(output.data, status=status.HTTP_201_CREATED)

