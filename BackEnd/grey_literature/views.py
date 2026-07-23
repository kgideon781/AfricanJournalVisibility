from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import GreyLiteratureFilter
from .models import GreyLiterature
from .serializers import GreyLiteratureSerializer


class GreyLiteraturePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class IsOwnerOrStaffOrReadOnly(permissions.BasePermission):
    """Read: anyone (list is scoped in the view).
    Write: authenticated user must own the record, or be staff.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user and request.user.is_authenticated
            and (request.user.is_staff or obj.user_id == request.user.id)
        )


@extend_schema_view(
    list=extend_schema(tags=["Grey Literature"], summary="List approved grey-literature items"),
    create=extend_schema(tags=["Grey Literature"], summary="Submit a grey-literature item (authenticated)"),
    retrieve=extend_schema(tags=["Grey Literature"], summary="Get a grey-literature item by id"),
    update=extend_schema(tags=["Grey Literature"], summary="Update a grey-literature item (owner/staff)"),
    partial_update=extend_schema(tags=["Grey Literature"], summary="Partial update (owner/staff)"),
    destroy=extend_schema(tags=["Grey Literature"], summary="Delete (owner/staff)"),
)
class GreyLiteratureViewSet(viewsets.ModelViewSet):
    """Public list/detail is scoped to `approved=True`. Owners see their own
    unapproved submissions when authenticated; staff see everything.
    """

    serializer_class = GreyLiteratureSerializer
    permission_classes = [IsOwnerOrStaffOrReadOnly]
    pagination_class = GreyLiteraturePagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    lookup_field = "pk"

    def get_queryset(self):
        qs = GreyLiterature.objects.select_related("country", "user").all()
        user = self.request.user
        if not (user and user.is_authenticated and user.is_staff):
            if user and user.is_authenticated:
                qs = qs.filter(Q(approved=True) | Q(user=user))
            else:
                qs = qs.filter(approved=True)
        return qs

    def perform_create(self, serializer):
        # Force submitter + start unapproved regardless of what client sent.
        serializer.save(user=self.request.user, approved=False)


@extend_schema(
    tags=["Grey Literature"],
    summary="Search + filter approved grey-literature items",
    description="Filters via query, item_type, country, language, publication_date_range.",
)
class GreyLiteratureSearchView(generics.ListAPIView):
    serializer_class = GreyLiteratureSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = GreyLiteratureFilter
    pagination_class = GreyLiteraturePagination

    def get_queryset(self):
        return GreyLiterature.objects.select_related("country").filter(approved=True)


@extend_schema(
    tags=["Grey Literature"],
    summary="Approve a grey-literature item (staff only)",
)
class ApproveGreyLiteratureView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        try:
            item = GreyLiterature.objects.get(pk=pk)
        except GreyLiterature.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        item.approved = True
        item.save(update_fields=["approved", "updated_at"])
        return Response({"id": item.id, "approved": item.approved})


@extend_schema(
    tags=["Grey Literature"],
    summary="List unapproved grey-literature items (staff only)",
)
class UnapprovedGreyLiteratureListView(generics.ListAPIView):
    serializer_class = GreyLiteratureSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = GreyLiteraturePagination

    def get_queryset(self):
        return GreyLiterature.objects.select_related("country", "user").filter(approved=False).order_by("-created_at")
