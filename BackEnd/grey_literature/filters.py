import django_filters
from django.contrib.postgres.search import (
    SearchHeadline,
    SearchQuery,
    SearchRank,
)
from django.db.models import F, Q

from .models import GreyLiterature


class GreyLiteratureFilter(django_filters.FilterSet):
    query = django_filters.CharFilter(method="custom_search", label="Search")
    item_type = django_filters.CharFilter(field_name="item_type", lookup_expr="iexact")
    country = django_filters.CharFilter(
        field_name="country__country", lookup_expr="icontains", label="Country",
    )
    language = django_filters.CharFilter(field_name="language", lookup_expr="iexact")
    issuing_organization = django_filters.CharFilter(
        field_name="issuing_organization", lookup_expr="icontains",
    )
    publication_date = django_filters.DateFilter(field_name="publication_date")
    publication_date_range = django_filters.DateFromToRangeFilter(field_name="publication_date")

    class Meta:
        model = GreyLiterature
        fields = []

    def custom_search(self, queryset, name, value):
        if not value:
            return queryset

        words = value.split()[:10]
        search_query = SearchQuery(words[0], search_type="websearch", config="english")
        for word in words[1:]:
            search_query |= SearchQuery(word, search_type="websearch", config="english")

        queryset = queryset.annotate(
            rank=SearchRank(F("search_vector"), search_query),
            highlight=SearchHeadline(
                "abstract", search_query,
                start_sel="<mark>", stop_sel="</mark>",
                max_words=35, min_words=15,
            ),
        )

        return queryset.filter(
            Q(search_vector=search_query)
            | Q(title__icontains=value)
            | Q(abstract__icontains=value)
            | Q(keywords__icontains=value)
            | Q(authors__icontains=value)
            | Q(issuing_organization__icontains=value)
            | Q(sub_region__icontains=value)
            | Q(country__country__icontains=value)
            | Q(source__icontains=value)
        ).order_by("-rank")
