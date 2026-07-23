from django.urls import path

from .views import (
    ApproveGreyLiteratureView,
    GreyLiteratureSearchView,
    GreyLiteratureViewSet,
    UnapprovedGreyLiteratureListView,
)


grey_list = GreyLiteratureViewSet.as_view({"get": "list", "post": "create"})
grey_detail = GreyLiteratureViewSet.as_view({
    "get": "retrieve",
    "put": "update",
    "patch": "partial_update",
    "delete": "destroy",
})


urlpatterns = [
    path("api/grey/", grey_list, name="grey-list"),
    path("api/grey/<int:pk>/", grey_detail, name="grey-detail"),
    path("api/grey/search/", GreyLiteratureSearchView.as_view(), name="grey-search"),
    path("api/grey/unapproved/", UnapprovedGreyLiteratureListView.as_view(), name="grey-unapproved-list"),
    path("api/grey/<int:pk>/approve/", ApproveGreyLiteratureView.as_view(), name="grey-approve"),
]
