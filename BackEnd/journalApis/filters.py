import django_filters
from django.db.models import Q, F
from .models import  Journal,Article
# from django.contrib.postgres.search import SearchVector,SearchQuery, SearchRank
from django.contrib.postgres.search import (
    SearchVector, SearchQuery, SearchRank, SearchHeadline
)


class JournalFilter(django_filters.FilterSet):
    query = django_filters.CharFilter(method='custom_search', label='Search')
    directory_of_african_journals = django_filters.BooleanFilter(field_name='listed_in_doaj')
    present_on_issn = django_filters.BooleanFilter(field_name='present_issn')
    african_index_medicus = django_filters.BooleanFilter(field_name='aim_identifier')
    indexed_on_google_scholar = django_filters.BooleanFilter(field_name='google_scholar_index')
    open_access_journal = django_filters.BooleanFilter(field_name='open_access_journal')
    member_of_committee_on_publication_ethics = django_filters.BooleanFilter(field_name='publisher_in_cope')
    online_publisher_in_africa = django_filters.BooleanFilter(field_name='online_publisher_africa')
    hosted_on_inasps = django_filters.BooleanFilter(field_name='hosted_on_inasps')
    country = django_filters.CharFilter(field_name='country__country', lookup_expr='icontains', label='Country')
    thematic_area = django_filters.CharFilter(field_name='thematic_area__thematic_area', lookup_expr='icontains', label='Thematic Area')
    language = django_filters.CharFilter(field_name='language__language', lookup_expr='icontains', label='Language')



    class Meta:
        model = Journal
        fields = []

    def custom_search(self, queryset, name, value):
        # Per-word AND against journal_title OR publishers_name.
        # Every whitespace-separated word in the query must appear (case-insensitive
        # substring) in the title or publisher. ISSN is checked as a whole-string
        # bypass so users can paste an ISSN directly.
        #
        # SearchRank is annotated for ordering only (not filtering) — the vector
        # is weighted A/B/B/D so title hits rank ahead of publisher/summary hits.
        #
        # Design note: the old code used SearchQuery OR across words + rank>=0.05
        # + a wide icontains OR across every field. Typing a full journal title
        # returned 400-1500 rows because rank 0.05 catches almost everything.
        if not value:
            return queryset

        words = [w for w in value.split() if w.strip()][:10]
        if not words:
            return queryset

        per_word = Q()
        first = True
        for w in words:
            clause = Q(journal_title__icontains=w) | Q(publishers_name__icontains=w)
            per_word = clause if first else (per_word & clause)
            first = False

        # Weighted vector so title matches sort ahead of publisher/summary matches.
        search_vector = (
            SearchVector('journal_title', weight='A')
            + SearchVector('publishers_name', weight='B')
            + SearchVector('issn_number', weight='B')
            + SearchVector('summary', weight='D')
        )
        search_query = SearchQuery(value, search_type='websearch')
        queryset = queryset.annotate(
            rank=SearchRank(search_vector, search_query),
            highlight=SearchHeadline('summary', search_query),
        )
        return queryset.filter(
            per_word | Q(issn_number__icontains=value)
        ).order_by('-rank')



class ArticleFilter(django_filters.FilterSet):
    # Filters for Article fields
    query = django_filters.CharFilter(method='custom_search', label='Search')

    # Filter for a specific publication date
    publication_date = django_filters.DateFilter(field_name="publication_date", label="Publication Date (Specific Day)", lookup_expr="exact")

    # Date range filter
    publication_date_range = django_filters.DateFromToRangeFilter(field_name="publication_date", label="Publication Date Range")

    # Country filter (via related Journal)
    country = django_filters.CharFilter(field_name='journal__country__country', lookup_expr='icontains', label='Country')
   

    thematic_area = django_filters.CharFilter(field_name='journal__thematic_area__thematic_area', lookup_expr='icontains', label='Thematic Area')

    language = django_filters.CharFilter(field_name='journal__language__language', lookup_expr='icontains', label='Language')

    class Meta:
        model = Article
        fields = []

    

    def custom_search(self, queryset, name, value):
        if not value:
            return queryset

        words = value.split()[:10]
        search_query = SearchQuery(words[0], search_type='websearch', config='english')
        for word in words[1:]:
            search_query |= SearchQuery(word, search_type='websearch', config='english')

        # Rank against the stored, PDF-body-inclusive tsvector (populated by
        # journalApis.tasks.extract_article_pdf).
        queryset = queryset.annotate(
            rank=SearchRank(F('search_vector'), search_query),
            highlight=SearchHeadline(
                'abstract', search_query,
                start_sel='<mark>', stop_sel='</mark>',
                max_words=35, min_words=15,
            ),
        )

        return queryset.filter(
            Q(search_vector=search_query) |
            # icontains fallback for related-Journal fields and freshly-created
            # articles whose search_vector has not been computed yet.
            Q(title__icontains=value) |
            Q(abstract__icontains=value) |
            Q(keywords__icontains=value) |
            Q(authors__icontains=value) |
            Q(subjects__icontains=value) |
            Q(article_type__icontains=value) |
            Q(publisher__icontains=value) |
            Q(journal__journal_title__icontains=value) |
            Q(journal__country__country__icontains=value) |
            Q(journal__language__language__icontains=value) |
            Q(journal__thematic_area__thematic_area__icontains=value)
        ).order_by('-rank')



