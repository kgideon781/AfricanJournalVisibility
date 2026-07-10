from django.shortcuts import render
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Journal,Feedback,Manuscript,ReviewerAssignment,EditorialDecision
from .serializers import JournalSerializer,JournalSerializer1,LanguageSerializer,PlatformSerializer,CountrySerializer,ThematicAreaSerializer,VolumeSerializer,ArticleSerializer,VolumeSerializer1
from .serializers import FeedBackSerializer
from .serializers import ManuscriptSerializer,ReviewSerializer,ReviewerAssignmentSerializer
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from .filters import JournalFilter,ArticleFilter
from rest_framework import generics
from rest_framework.decorators import api_view
import google.generativeai as genai
from rest_framework import viewsets  # This imports viewsets
from rest_framework.permissions import IsAuthenticated 
from .models import Language,Platform,Country,ThematicArea,Volume,Article,ReviewerAssignment,Review
from django.conf import settings
from .serializers import CountsSerializer
from rest_framework.decorators import permission_classes
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
# from django.db.models import Count
from rest_framework.permissions import BasePermission
# from rest_framework.views import APIView
# from rest_framework.response import Response
from django.db.models import Count, Q
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
# from .models import Journal
# from .filters import JournalFilter
# from rest_framework.pagination import PageNumberPagination

from drf_spectacular.utils import extend_schema, extend_schema_view
# ─── Pagination ───────────────────────────────────────────────────────────────
class JournalPagination(PageNumberPagination):
    # Set the page size here or in settings.py
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_size = 10 
    
class ArticlePagination(PageNumberPagination):
    # Set the page size here or in settings.py
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_size = 10 


# ─── Journals ─────────────────────────────────────────────────────────────────
@extend_schema(
    tags=['Journals'],
    summary="List all journals (paginated)",
    description="Returns a paginated list of all approved journals. Use `page` and `page_size` query params to control pagination.",
)
class JournalPaginationListView(APIView):
    def get(self, request):
        # Retrieve all journals from the database
        # journals = Journal.objects.all()
        journals = Journal.objects.filter(approved=True)

        # Instantiate the pagination class
        paginator = JournalPagination()
        
        # Paginate the queryset
        paginated_journals = paginator.paginate_queryset(journals, request)
        
        # Serialize the journals
        serializer = JournalSerializer(paginated_journals, many=True)
        
        # Return the serialized data with pagination information
        return paginator.get_paginated_response(serializer.data)
    

@extend_schema(
    tags=['Journals'],
    summary="List journals uploaded by the authenticated user",
    description="Returns all journals uploaded by the currently authenticated user. Requires a valid JWT token.",
)    
class JournalPaginationListUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Retrieve the authenticated user's ID
        authenticated_user_id = request.user.id
        print(authenticated_user_id)
        
        # Retrieve journals uploaded by the specific user
        journals = Journal.objects.filter(user_id=authenticated_user_id)

        # Check if journals exist for the user
        if not journals.exists():
            return Response({'detail': 'No journals found for the authenticated user.'}, status=status.HTTP_404_NOT_FOUND)
        
        # Serialize the journals
        serializer = JournalSerializer(journals, many=True)
        
        # Return the serialized data
        return Response(serializer.data)


@extend_schema(
    tags=['Journals'],
    summary="Search and filter journals",
    description=(
        "Search and filter journals using query parameters. "
        "Supports full-text search across title, country, language, thematic area, publisher, ISSN, platform and summary. "
        "Results are paginated and ordered by journal title."
    ),
)
class JournalSearchView(generics.ListAPIView):
    # queryset = Journal.objects.all()
    serializer_class = JournalSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = JournalFilter
    pagination_class = JournalPagination

    def get_queryset(self):
        # Annotate journals with the number of related volumes
        # queryset = Journal.objects.annotate(volume_count=Count('volumes')).order_by('journal_title')
        ####################################################################################
        queryset = Journal.objects.filter(approved=True).annotate(volume_count=Count('volumes')).order_by('journal_title')
        ####################################################################################
        # Apply filters if requested
        filtered_queryset = self.filter_queryset(queryset)

        # Return static list if no filters match
        if not filtered_queryset.exists():
            return queryset
        return filtered_queryset



@extend_schema(
    tags=['Journals'],
    summary="Get journal by ID",
    description="Retrieve full details of a single journal by its numeric ID.",
)
class JournalDetailView(APIView):
    def get(self, request, journal_id):
        # Retrieve the article with the specified ID
        #journal = get_object_or_404(Journal, id=journal_id)
        ##########################################################################################
        # After
        journal = get_object_or_404(Journal, id=journal_id, approved=True)
        ##########################################################################################
        # Serialize the article
        serializer = JournalSerializer(journal)
        
        # Return the serialized article data
        return Response(serializer.data)

@extend_schema(exclude=True)
def getJournals(Request):
    pass


# ─── Stats ────────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['Stats'],
    summary="Get journal statistics",
    description=(
        "Returns aggregate counts across all journals including: "
        "open access journals, INASPS hosted, online publishers in Africa, "
        "DOAJ listings, COPE memberships, and journals with an ISSN."
    ),
)
@api_view(['GET'])
def journal_stats(request):
    # Count total number of journals with specific attributes
    # open_access_count = Journal.objects.filter(open_access_journal=True).count()
    # hosted_on_inasps_count = Journal.objects.filter(hosted_on_inasps=True).count()
    # online_publisher_africa_count = Journal.objects.filter(online_publisher_africa=True).count()
    # doaj_count = Journal.objects.filter(listed_in_doaj=True).count()
    # cope_count = Journal.objects.filter(publisher_in_cope=True).count()
    # issn_count = Journal.objects.filter(present_issn=True).count()

    ###############################################################################################
    open_access_count = Journal.objects.filter(approved=True, open_access_journal=True).count()
    hosted_on_inasps_count = Journal.objects.filter(approved=True, hosted_on_inasps=True).count()
    online_publisher_africa_count = Journal.objects.filter(approved=True, online_publisher_africa=True).count()
    doaj_count = Journal.objects.filter(approved=True, listed_in_doaj=True).count()
    cope_count = Journal.objects.filter(approved=True, publisher_in_cope=True).count()
    issn_count = Journal.objects.filter(approved=True, present_issn=True).count()
    
    # Create response dictionary
    stats = {
        'open_access_journal_count': open_access_count,
        'hosted_on_inasps_count': hosted_on_inasps_count,
        'online_publisher_africa_count': online_publisher_africa_count,
        'doaj_count': doaj_count,
        'cope_count': cope_count,
        'issn_count': issn_count,
    }

    return Response(stats)





@extend_schema(
    tags=['Journals'],
    summary="Generate a journal description using AI",
    description=(
        "Accepts a journal title and uses Google Gemini AI to generate a three-paragraph "
        "description. Useful when creating or editing a journal entry."
    ),
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'journal_text': {'type': 'string', 'example': 'African Journal of Public Health'}
            },
            'required': ['journal_text']
        }
    },
)
@api_view(['POST'])
def generate_journal_description(request):
    genai.configure(api_key='AIzaSyBf6hhxPUxOgKFWnPhtgWnRj6htPPbkdWU')
    # Get the journal text from the request data
    journal_text = request.data.get('journal_text')

    if not journal_text:
        return Response({"error": "Journal text is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Initialize the generative model
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Generate a brief description based on the input journal text
        prompt = f"Provide a brief description three paragrahs for the following journal title:'{journal_text}'."
        response = model.generate_content(prompt)

        # Check if the response contains the generated description
        if response and response.text:
            print(response.text)
            return Response({
                'journal_text': journal_text,
                'description': response.text
            }, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Failed to generate a description."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        # Handle errors during the process
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@extend_schema(
    tags=['Journals'],
    summary="Create a new journal",
    description="Submit a new journal entry. All required fields must be provided in the request body.",
)
class JournalCreateView(APIView):
    def post(self, request):
        serializer = JournalSerializer1(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# ─── Reference Data ViewSets ──────────────────────────────────────────────────
 
@extend_schema_view(
    list=extend_schema(tags=['Languages'], summary="List all languages"),
    create=extend_schema(tags=['Languages'], summary="Create a language"),
    retrieve=extend_schema(tags=['Languages'], summary="Get a language by ID"),
    update=extend_schema(tags=['Languages'], summary="Update a language"),
    partial_update=extend_schema(tags=['Languages'], summary="Partially update a language"),
    destroy=extend_schema(tags=['Languages'], summary="Delete a language"),
)
class LanguageViewSet(viewsets.ModelViewSet):
    queryset = Language.objects.all()  # Fetch all languages
    serializer_class = LanguageSerializer
    pagination_class = None  # This disables pagination for this viewset



# ─── User-scoped Reference Data ───────────────────────────────────────────────
 
@extend_schema_view(
    list=extend_schema(
        tags=['Languages'],
        summary="List languages used by authenticated user's journals",
        description="Returns languages associated with the authenticated user's journals, with a journal count per language.",
    ),
    create=extend_schema(tags=['Languages'], summary="Create a language (authenticated user)"),
    retrieve=extend_schema(tags=['Languages'], summary="Get a user language by ID"),
    update=extend_schema(tags=['Languages'], summary="Update a user language"),
    partial_update=extend_schema(tags=['Languages'], summary="Partially update a user language"),
    destroy=extend_schema(tags=['Languages'], summary="Delete a user language"),
)
class UserLanguageViewSet(viewsets.ModelViewSet):
    serializer_class = LanguageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Filtering languages associated with journals authored by the user
        return Language.objects.filter(journal__user=user).distinct()

    def list(self, request, *args, **kwargs):
        user = request.user
        
        # Fetch languages used by the user and count the journals per language
        queryset = Language.objects.filter(journal__user=user).annotate(
            journal_count=Count('journal')
        ).distinct()

        data = []
        for language in queryset:
            data.append({
                'language': language.language,
                'journal_count': language.journal_count
            })

        return Response(data)  


@extend_schema_view(
    list=extend_schema(
        tags=['Articles'],
        summary="List articles for the authenticated user",
        description="Returns all articles belonging to journals owned by the currently authenticated user.",
    ),
    create=extend_schema(tags=['Articles'], summary="Create an article (authenticated user)"),
    retrieve=extend_schema(tags=['Articles'], summary="Get a user article by ID"),
    update=extend_schema(tags=['Articles'], summary="Update a user article"),
    partial_update=extend_schema(tags=['Articles'], summary="Partially update a user article"),
    destroy=extend_schema(tags=['Articles'], summary="Delete a user article"),
)
class UserArticleViewSet(viewsets.ModelViewSet):
    serializer_class = ArticleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Filtering languages associated with journals authored by the user
        return Article.objects.filter(journal__user=user).distinct()


@extend_schema_view(
    list=extend_schema(
        tags=['Journals'],
        summary="List journals for the authenticated user",
        description="Returns all journals submitted by the currently authenticated user.",
    ),
    create=extend_schema(tags=['Journals'], summary="Create a journal (authenticated user)"),
    retrieve=extend_schema(tags=['Journals'], summary="Get a user journal by ID"),
    update=extend_schema(tags=['Journals'], summary="Update a user journal"),
    partial_update=extend_schema(tags=['Journals'], summary="Partially update a user journal"),
    destroy=extend_schema(tags=['Journals'], summary="Delete a user journal"),
)
class UserJournalViewSet(viewsets.ModelViewSet):
    serializer_class = JournalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Staff/superusers can manage any journal via this viewset.
        # "scope=all" on the list endpoint opts them into the all-journals
        # view; without it their default remains "my journals" so the
        # dashboard toggle behaves naturally. Retrieve/update/destroy for
        # staff always resolves against all journals so admin edits of
        # another user's journal work end-to-end.
        if user.is_staff:
            if self.action == 'list':
                if self.request.query_params.get('scope') == 'all':
                    return Journal.objects.all().distinct()
                return Journal.objects.filter(user=user).distinct()
            return Journal.objects.all().distinct()
        return Journal.objects.filter(user=user).distinct()


@extend_schema_view(
    list=extend_schema(
        tags=['Thematic Areas'],
        summary="List thematic areas for the authenticated user's journals",
        description="Returns thematic areas associated with the authenticated user's journals, with a journal count per thematic area.",
    ),
    create=extend_schema(tags=['Thematic Areas'], summary="Create a thematic area (authenticated user)"),
    retrieve=extend_schema(tags=['Thematic Areas'], summary="Get a user thematic area by ID"),
    update=extend_schema(tags=['Thematic Areas'], summary="Update a user thematic area"),
    partial_update=extend_schema(tags=['Thematic Areas'], summary="Partially update a user thematic area"),
    destroy=extend_schema(tags=['Thematic Areas'], summary="Delete a user thematic area"),
)
class UserThematicAreaViewSet(viewsets.ModelViewSet):
    serializer_class = ThematicAreaSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # This disables pagination for this viewset
    def get_queryset(self):
        user = self.request.user
        # Filtering thematic areas associated with journals authored by the user
        return ThematicArea.objects.filter(journal__user=user).distinct()

    def list(self, request, *args, **kwargs):
        user = request.user
        
        # Fetch thematic areas used by the user and count the journals per thematic area
        queryset = ThematicArea.objects.filter(journal__user=user).annotate(
            journal_count=Count('journal')
        ).distinct()

        data = []
        for thematic_area in queryset:
            data.append({
                'thematic_area': thematic_area.thematic_area,
                'journal_count': thematic_area.journal_count
            })

        return Response(data)


@extend_schema_view(
    list=extend_schema(tags=['Platforms'], summary="List all platforms"),
    create=extend_schema(tags=['Platforms'], summary="Create a platform"),
    retrieve=extend_schema(tags=['Platforms'], summary="Get a platform by ID"),
    update=extend_schema(tags=['Platforms'], summary="Update a platform"),
    partial_update=extend_schema(tags=['Platforms'], summary="Partially update a platform"),
    destroy=extend_schema(tags=['Platforms'], summary="Delete a platform"),
)
class PlatformViewSet(viewsets.ModelViewSet):
    queryset = Platform.objects.all()  # Fetch all languages
    serializer_class = PlatformSerializer
    pagination_class = None  # This disables pagination for this viewset


@extend_schema_view(
    list=extend_schema(tags=['Countries'], summary="List all countries"),
    create=extend_schema(tags=['Countries'], summary="Create a country"),
    retrieve=extend_schema(tags=['Countries'], summary="Get a country by ID"),
    update=extend_schema(tags=['Countries'], summary="Update a country"),
    partial_update=extend_schema(tags=['Countries'], summary="Partially update a country"),
    destroy=extend_schema(tags=['Countries'], summary="Delete a country"),
)
class CountryViewSet(viewsets.ModelViewSet):
    queryset = Country.objects.all()  # Fetch all languages
    serializer_class = CountrySerializer
    pagination_class = None  # This disables pagination for this viewset

@extend_schema_view(
    list=extend_schema(tags=['Thematic Areas'], summary="List all thematic areas"),
    create=extend_schema(tags=['Thematic Areas'], summary="Create a thematic area"),
    retrieve=extend_schema(tags=['Thematic Areas'], summary="Get a thematic area by ID"),
    update=extend_schema(tags=['Thematic Areas'], summary="Update a thematic area"),
    partial_update=extend_schema(tags=['Thematic Areas'], summary="Partially update a thematic area"),
    destroy=extend_schema(tags=['Thematic Areas'], summary="Delete a thematic area"),
)
class ThematicAreaViewSet(viewsets.ModelViewSet):
    queryset = ThematicArea.objects.all()  # Fetch all languages
    serializer_class = ThematicAreaSerializer
    pagination_class = None  # This disables pagination for this viewset

# ─── Volumes ──────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(tags=['Volumes'], summary="List all volumes"),
    create=extend_schema(tags=['Volumes'], summary="Create a volume"),
    retrieve=extend_schema(tags=['Volumes'], summary="Get a volume by ID"),
    update=extend_schema(tags=['Volumes'], summary="Update a volume"),
    partial_update=extend_schema(tags=['Volumes'], summary="Partially update a volume"),
    destroy=extend_schema(tags=['Volumes'], summary="Delete a volume"),
)
class VolumeViewSet(viewsets.ModelViewSet):
    queryset = Volume.objects.all()  # Fetch all languages
    serializer_class = VolumeSerializer
    pagination_class = None  # This disables pagination for this viewset

@extend_schema_view(
    list=extend_schema(tags=['Articles'], summary="List all articles"),
    create=extend_schema(tags=['Articles'], summary="Create an article"),
    retrieve=extend_schema(tags=['Articles'], summary="Get an article by ID"),
    update=extend_schema(tags=['Articles'], summary="Update an article"),
    partial_update=extend_schema(tags=['Articles'], summary="Partially update an article"),
    destroy=extend_schema(tags=['Articles'], summary="Delete an article"),
)
class ArticleViewSet(viewsets.ModelViewSet):
    #queryset = Article.objects.all()  # Fetch all languages
    #####################################################################################
    # After
    queryset = Article.objects.filter(volume__journal__approved=True)
    serializer_class = ArticleSerializer
    #pagination_class = None  # This disables pagination for this viewset


@extend_schema(
    tags=['Articles'],
    summary="Search and filter articles",
    description="Search and filter articles using query parameters. Results are paginated.",
)
class ArticleSearchView(generics.ListAPIView):
    """
    API view to search and filter articles.
    """
    # queryset = Article.objects.all()
    #######################################################################################
    # After
    queryset = Article.objects.filter(volume__journal__approved=True)
    serializer_class = ArticleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ArticleFilter
    pagination_class = ArticlePagination  # Replace with DRF's default if no custom pagination

    def get_queryset(self):
        """
        Optionally override the queryset to apply additional filtering logic.
        """
        queryset = super().get_queryset()

        # Add additional filtering logic if necessary
        return queryset


@extend_schema_view(
    list=extend_schema(tags=['Feedback'], summary="List all feedback"),
    create=extend_schema(tags=['Feedback'], summary="Submit feedback"),
    retrieve=extend_schema(tags=['Feedback'], summary="Get feedback by ID"),
    update=extend_schema(tags=['Feedback'], summary="Update feedback"),
    partial_update=extend_schema(tags=['Feedback'], summary="Partially update feedback"),
    destroy=extend_schema(tags=['Feedback'], summary="Delete feedback"),
)
class FeedbackViewSet(viewsets.ModelViewSet):
     queryset = Feedback.objects.all()
     serializer_class = FeedBackSerializer  



# class JournalCountryCountAPIView(APIView):
#     def get(self, request, *args, **kwargs):
#         country_counts = (
#             Journal.objects.values("country__country")  # Fetch country name
#             .annotate(journal_count=Count("id"))
#             .order_by("-journal_count")
#         )

#         # Rename the key for better clarity
#         formatted_data = [
#             {"country": item["country__country"], "journal_count": item["journal_count"]}
#             for item in country_counts
#         ]

#         return Response(formatted_data)


# ─── Country Count ────────────────────────────────────────────────────────────
 
@extend_schema(
    tags=['Countries'],
    summary="Get journal count per country",
    description=(
        "Returns a list of countries with the number of journals per country. "
        "Supports the same search and filter parameters as the journal search endpoint. "
        "Results are ordered by journal count descending."
    ),
)
class JournalCountryCountAPIView(APIView):
    def get(self, request, *args, **kwargs):
        # Apply the same filters as JournalFilter
        #filtered_queryset = JournalFilter(request.GET, queryset=Journal.objects.all()).qs
        ####################################################################################################
        filtered_queryset = JournalFilter(request.GET, queryset=Journal.objects.filter(approved=True)).qs
        ###################################################################################################
        query = request.GET.get("query", "")
        if query:
            search_query = SearchQuery(query)

            search_vector = SearchVector(
                'journal_title',
                'summary',
                'h_index',
                'platform__platform',
                'country__country',
                'publishers_name',
                'thematic_area__thematic_area',
                'issn_number',
                'language__language'
            )

            filtered_queryset = filtered_queryset.annotate(
                rank=SearchRank(search_vector, search_query)
            ).filter(
                Q(rank__gte=0.1) |
                Q(journal_title__icontains=query) |
                Q(platform__platform__icontains=query) |
                Q(country__country__icontains=query) |
                Q(publishers_name__icontains=query) |
                Q(thematic_area__thematic_area__icontains=query) |
                Q(issn_number__icontains=query) |
                Q(language__language__icontains=query) |
                Q(h_index__icontains=query) |
                Q(summary__icontains=query)
            ).order_by('-rank').distinct()

        # Count journals per country
        country_counts = (
            filtered_queryset
            .values("country__country")  # Fetch country name
            .annotate(journal_count=Count("id", distinct=True))  # Ensure correct count
            .order_by("-journal_count")
        )

        # Format the response
        formatted_data = [
            {"country": item["country__country"], "journal_count": item["journal_count"]}
            for item in country_counts
        ]

        return Response(formatted_data)

# @api_view(['GET'])
# def get_all_volumes(request):
#     paginator = PageNumberPagination()
#     paginator.page_size = 10  # You can override the default page size here
#     volumes = Volume.objects.all()
    
#     result_page = paginator.paginate_queryset(volumes, request)
#     serializer = VolumeSerializer1(result_page, many=True)
    
#     return paginator.get_paginated_response(serializer.data)

# @api_view(['DELETE'])
# def delete_volume(request, volume_id):
#     try:
#         volume = Volume.objects.get(id=volume_id)
#         volume.delete()
#         return Response({"message": "Volume deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
#     except Volume.DoesNotExist:
#         return Response({"error": "Volume not found"}, status=status.HTTP_404_NOT_FOUND)


@extend_schema_view(
    list=extend_schema(
        tags=['Volumes'],
        summary="List volumes for the authenticated user",
        description="Returns all volumes belonging to journals owned by the authenticated user, including article count per volume.",
    ),
    destroy=extend_schema(
        tags=['Volumes'],
        summary="Delete a volume (owner only)",
        description="Deletes a volume. The authenticated user must own the journal the volume belongs to.",
    ),
)

class UserVolumeViewSet(viewsets.ModelViewSet):
    serializer_class = VolumeSerializer1
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Filter volumes belonging to journals owned by the logged-in user
        return Volume.objects.filter(journal__user=user).distinct()

    def list(self, request, *args, **kwargs):
        user = request.user
        
        # Fetch volumes linked to journals owned by the user
        queryset = Volume.objects.filter(journal__user=user).annotate(
            article_count=Count('articles')
        ).distinct()

        data = []
        for volume in queryset:
            data.append({
                'id': volume.id,
                'journal': volume.journal.journal_title,
                'volume_number': volume.volume_number,
                'issue_number': volume.issue_number,
                'year': volume.year,
                'article_count': volume.article_count
            })

        return Response(data)

    def destroy(self, request, *args, **kwargs):
        """Allow users to delete only their own volumes."""
        user = request.user
        volume = self.get_object()

        if volume.journal.user != user:
            return Response({"error": "You do not have permission to delete this volume."}, status=403)

        volume.delete()
        return Response({"message": "Volume deleted successfully"}, status=204)



@extend_schema(
    tags=['Volumes'],
    summary="Get volumes and articles for a journal",
    description=(
        "Returns all volumes for a given journal ID, with each volume listing its articles "
        "including title, authors, DOI, publication date, URL, PDF, and ISSN details."
    ),
)
@api_view(['GET'])
def journal_details(request, journal_id):
    try:
        journal = Journal.objects.get(id=journal_id)
    except Journal.DoesNotExist:
        return Response({"error": "Journal not found"}, status=404)

    # Get all volumes for the journal
    volumes = Volume.objects.filter(journal=journal).order_by('volume_number')
    
    journal_data = {}

    for volume in volumes:
        # Get all articles for the volume
        articles = Article.objects.filter(volume=volume).values(
            "id", "title", "authors", "publication_date", "doi","url","pdf","electronic_issn",
            "print_issn","publisher"
        )

        # Convert QuerySet to a list of dictionaries
        articles_list = list(articles)

        # Structure data as {volume_number: {articles: [...], year: year}}
        journal_data[f"Volume {volume.volume_number}"] = {
            "year": volume.year,
            "issue_number":volume.issue_number,
            "articles": articles_list,
        }

    return Response(journal_data) 

@extend_schema(
    tags=['Stats'],
    summary="Get authenticated user's content counts",
    description="Returns the number of journals, volumes and articles uploaded by the currently authenticated user.",
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_counts(request):
    user = request.user

    # Journals uploaded by this user
    journals = Journal.objects.filter(user=user)
    journals_count = journals.count()

    # Volumes under journals owned by this user
    volumes_count = Volume.objects.filter(journal__user=user).count()

    # Articles under journals owned by this user
    articles_count = Article.objects.filter(journal__user=user).count()

    return Response({
        'journals': journals_count,
        'volumes': volumes_count,
        'articles': articles_count
    })






from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework import status
from .models import Journal
from .serializers import JournalSerializer
from rest_framework.pagination import PageNumberPagination


# ─── Custom Permission ────────────────────────────────────────────────────────
# ─── Staff / Approval Views ───────────────────────────────────────────────────
class IsStaffAndActive(BasePermission):
    """
    Allows access only to users who are:
      - Authenticated
      - is_staff = True
      - is_active = True  (not a deactivated account)
    Blocks access to users where is_active = False regardless of staff status.
    """
    message = 'Access denied. You must be an active staff member to view this resource.'

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_staff and
            request.user.is_active
        )


# ─── Pagination ───────────────────────────────────────────────────────────────

class UnapprovedJournalPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


# ─── Views ────────────────────────────────────────────────────────────────────
@extend_schema(
    tags=['Journals'],
    summary="List all unapproved journals (staff only)",
    description="Returns a paginated list of journals that have not yet been approved. Accessible only by active staff members.",
)
class UnapprovedJournalListView(APIView):
    """
    GET /api/journals/unapproved/
    Returns a paginated list of all unapproved journals.
    Only accessible by active staff members.
    """
    permission_classes = [IsStaffAndActive]

    def get(self, request):
        journals = Journal.objects.filter(approved=False).order_by('id')

        paginator = UnapprovedJournalPagination()
        paginated_journals = paginator.paginate_queryset(journals, request)
        serializer = JournalSerializer(paginated_journals, many=True)

        return paginator.get_paginated_response(serializer.data)


@extend_schema(
    tags=['Journals'],
    summary="Get a single unapproved journal (staff only)",
    description="Retrieve details of a specific unapproved journal by ID. Accessible only by active staff members.",
)
class UnapprovedJournalDetailView(APIView):
    """
    GET  /api/journals/unapproved/<journal_id>/  — View a single unapproved journal
    POST /api/journals/unapproved/<journal_id>/approve/  — Approve a journal
    Only accessible by active staff members.
    """
    permission_classes = [IsStaffAndActive]

    def get(self, request, journal_id):
        try:
            journal = Journal.objects.get(id=journal_id, approved=False)
        except Journal.DoesNotExist:
            return Response(
                {'error': 'Unapproved journal not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = JournalSerializer(journal)
        return Response(serializer.data)


@extend_schema(
    tags=['Journals'],
    summary="Approve a journal (staff only)",
    description="Sets a journal's `approved` field to `True`. Can only be performed by active staff members. Returns a confirmation message.",
)
class ApproveJournalView(APIView):
    """
    PATCH /api/journals/<journal_id>/approve/
    Approves a single journal by setting approved=True.
    Only accessible by active staff members.
    """
    permission_classes = [IsStaffAndActive]

    def patch(self, request, journal_id):
        try:
            journal = Journal.objects.get(id=journal_id)
        except Journal.DoesNotExist:
            return Response(
                {'error': 'Journal not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if journal.approved:
            return Response(
                {'message': 'Journal is already approved.'},
                status=status.HTTP_200_OK
            )

        journal.approved = True
        journal.save(update_fields=['approved'])

        return Response(
            {'message': f'Journal "{journal.journal_title}" has been approved successfully.'},
            status=status.HTTP_200_OK
        )
    

###########################################################################


class ManuscriptCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ManuscriptSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(corresponding_author=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserManuscriptViewSet(viewsets.ModelViewSet):
    serializer_class = ManuscriptSerializer
    permission_classes = [IsAuthenticated]

    # def get_queryset(self):
    #     return Manuscript.objects.filter(corresponding_author=self.request.user)
    def get_queryset(self):
        return (
            Manuscript.objects
            .filter(corresponding_author=self.request.user)
            .order_by("-created_at")
        )
    
class ReviewerQueueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        manuscripts = Manuscript.objects.filter(
            reviewerassignment__reviewer=request.user,
            reviewerassignment__is_completed=False
        ).distinct()

        serializer = ManuscriptSerializer(manuscripts, many=True)
        return Response(serializer.data)
    
# class SubmitReviewView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, manuscript_id):
#         manuscript = get_object_or_404(Manuscript, id=manuscript_id)

#         data = request.data.copy()
#         data["reviewer"] = request.user.id
#         data["manuscript"] = manuscript.id

#         serializer = ReviewSerializer(data=data)
#         if serializer.is_valid():
#             serializer.save()

#             return Response(serializer.data, status=status.HTTP_201_CREATED)

#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




# class SubmitReviewView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, manuscript_id):
#         manuscript = get_object_or_404(Manuscript, id=manuscript_id)

#         # CHECK ASSIGNMENT FIRST
#         assignment = ReviewerAssignment.objects.filter(
#             manuscript=manuscript,
#             reviewer=request.user,
#             is_completed=False
#         ).first()

#         if not assignment:
#             return Response(
#                 {"error": "You are not assigned to review this manuscript."},
#                 status=403
#             )

#         data = request.data.copy()
#         data["reviewer"] = request.user.id
#         data["manuscript"] = manuscript.id

#         serializer = ReviewSerializer(data=data)
#         if serializer.is_valid():
#             serializer.save()

#             # mark assignment complete
#             assignment.is_completed = True
#             assignment.save()

#             return Response(serializer.data, status=201)

#         return Response(serializer.errors, status=400)
    




class SubmitReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, manuscript_id):
        manuscript = get_object_or_404(Manuscript, id=manuscript_id)

        # 1. CHECK ASSIGNMENT (CORE RULE)
        assignment = ReviewerAssignment.objects.filter(
            manuscript=manuscript,
            reviewer=request.user,
            is_completed=False
        ).first()

        if not assignment:
            return Response(
                {"error": "You are not assigned to review this manuscript."},
                status=403
            )

        # 2. PREVENT DOUBLE REVIEW
        if Review.objects.filter(manuscript=manuscript, reviewer=request.user).exists():
            return Response(
                {"error": "You already submitted a review."},
                status=400
            )

        # 3. FORCE SAFE DATA (IMPORTANT FIX)
        serializer = ReviewSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(
                reviewer=request.user,
                manuscript=manuscript
            )

            # 4. MARK ASSIGNMENT COMPLETE
            assignment.is_completed = True
            assignment.save()

            return Response(serializer.data, status=201)

        return Response(serializer.errors, status=400)
    
# class EditorialDecisionView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, manuscript_id):
#         manuscript = get_object_or_404(Manuscript, id=manuscript_id)

#         decision = request.data.get("decision")

#         manuscript.status = decision
#         manuscript.save()

#         # if accepted → convert to Article
#         if decision == "accepted":
#             Article.objects.create(
#                 journal=manuscript.journal,
#                 volume=manuscript.volume,
#                 title=manuscript.title,
#                 authors=manuscript.authors,
#                 abstract=manuscript.abstract
#             )

#         return Response({"message": "Decision recorded"})


class EditorialDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, manuscript_id):
        manuscript = get_object_or_404(Manuscript, id=manuscript_id)

        decision = request.data.get("decision")
        notes = request.data.get("notes", "")

        # 1. Validate decision
        valid_map = {
            "accept": "accepted",
            "reject": "rejected",
            "revise": "revision",
        }

        if decision not in valid_map:
            return Response(
                {"error": "Invalid decision. Use accept, reject, or revise."},
                status=400
            )

        # 2. Prevent duplicate decisions
        if hasattr(manuscript, "editorialdecision"):
            return Response(
                {"error": "Decision already made for this manuscript."},
                status=400
            )

        # 3. Save editorial decision
        EditorialDecision.objects.create(
            manuscript=manuscript,
            editor=request.user,
            decision=decision,
            notes=notes
        )

        # 4. Update manuscript status (IMPORTANT FIX)
        manuscript.status = valid_map[decision]
        manuscript.save()

        # 5. If accepted → create Article
        if decision == "accept":
            Article.objects.create(
                journal=manuscript.journal,
                volume=manuscript.volume,
                title=manuscript.title,
                authors=manuscript.authors,
                abstract=manuscript.abstract
            )

        return Response({
            "message": "Editorial decision recorded",
            "status": manuscript.status
        })
    
# class EditorQueueView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         manuscripts = Manuscript.objects.filter(
#             status__in=["under_review", "revision"]
#         ).distinct()

#         return Response(ManuscriptSerializer(manuscripts, many=True).data)

class EditorQueueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        manuscripts = Manuscript.objects.filter(
            # status__in=["under_review", "revision"]
            status__in=["submitted", "under_review", "revision"]
        ).order_by("-created_at")

        serializer = ManuscriptSerializer(manuscripts, many=True)
        return Response(serializer.data)
    
class EditorManuscriptDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, manuscript_id):
        manuscript = get_object_or_404(Manuscript, id=manuscript_id)

        reviews = Review.objects.filter(manuscript=manuscript)
        assignments = ReviewerAssignment.objects.filter(manuscript=manuscript)

        return Response({
            "manuscript": ManuscriptSerializer(manuscript).data,
            "reviews": ReviewSerializer(reviews, many=True).data,
            "assignments": ReviewerAssignmentSerializer(assignments, many=True).data,
        })

class IsEditor(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.groups.filter(name="Editor").exists()
        )
    
# User = get_user_model()
# class AssignReviewerView(APIView):
#     permission_classes = [IsEditor]

#     def post(self, request, manuscript_id):
#         manuscript = get_object_or_404(Manuscript, id=manuscript_id)

#         reviewer_id = request.data.get("reviewer")
#         reviewer = get_object_or_404(User, id=reviewer_id)

#         # prevent duplicates
#         if ReviewerAssignment.objects.filter(
#             manuscript=manuscript,
#             reviewer=reviewer,
#             is_completed=False
#         ).exists():
#             return Response(
#                 {"error": "Reviewer already assigned to this manuscript."},
#                 status=400
#             )

#         # prevent invalid states
#         if manuscript.status in ["accepted", "rejected"]:
#             return Response(
#                 {"error": "Cannot assign reviewers to finalized manuscript."},
#                 status=400
#             )

#         # ensure reviewer role (optional but recommended)
#         if not reviewer.groups.filter(name="Reviewer").exists():
#             return Response(
#                 {"error": "Selected user is not a reviewer."},
#                 status=400
#             )

#         assignment = ReviewerAssignment.objects.create(
#             manuscript=manuscript,
#             reviewer=reviewer
#         )
#         print("MANUSCRIPT STATUS BEFORE:", manuscript.status)
#         if manuscript.status == "submitted":
#             manuscript.status = "under_review"
#             manuscript.save(update_fields=["status"])
#         print("MANUSCRIPT STATUS AFTER:", manuscript.status)

#         return Response({
#             "message": "Reviewer assigned successfully.",
#             "status": manuscript.status,
#             "assignment_id": assignment.id
#         }, status=201)


from django.db import transaction

User = get_user_model()

class AssignReviewerView(APIView):
    permission_classes = [IsEditor]

    @transaction.atomic
    def post(self, request, manuscript_id):
        manuscript = get_object_or_404(Manuscript, id=manuscript_id)

        reviewer_id = request.data.get("reviewer")
        reviewer = get_object_or_404(User, id=reviewer_id)

        # 1. Prevent invalid manuscript states
        if manuscript.status in ["accepted", "rejected"]:
            return Response(
                {"error": "Cannot assign reviewers to finalized manuscript."},
                status=400
            )

        # 2. Ensure reviewer role
        if not reviewer.groups.filter(name="Reviewer").exists():
            return Response(
                {"error": "Selected user is not a reviewer."},
                status=400
            )

        # 3. Prevent duplicate assignment (safer check)
        exists = ReviewerAssignment.objects.select_for_update().filter(
            manuscript=manuscript,
            reviewer=reviewer,
            is_completed=False
        ).exists()

        if exists:
            return Response(
                {"error": "Reviewer already assigned to this manuscript."},
                status=400
            )

        # 4. Create assignment
        assignment = ReviewerAssignment.objects.create(
            manuscript=manuscript,
            reviewer=reviewer
        )

        # 5. Atomic status transition
        if manuscript.status == "submitted":
            manuscript.status = "under_review"
            manuscript.save(update_fields=["status"])

        return Response({
            "message": "Reviewer assigned successfully.",
            "status": manuscript.status,
            "assignment_id": assignment.id
        }, status=201)



# class AssignReviewerView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, manuscript_id):
#         manuscript = get_object_or_404(
#             Manuscript,
#             id=manuscript_id
#         )

#         reviewer_id = request.data.get("reviewer")

#         reviewer = get_object_or_404(
#             User,
#             id=reviewer_id
#         )

#         ReviewerAssignment.objects.create(
#             manuscript=manuscript,
#             reviewer=reviewer
#         )

#         # Automatically move manuscript into review
#         if manuscript.status == "submitted":
#             manuscript.status = "under_review"
#             manuscript.save(update_fields=["status"])

#         return Response(
#             {
#                 "message": "Reviewer assigned successfully.",
#                 "status": manuscript.status
#             },
#             status=201
#         )



User = get_user_model()

class ReviewerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reviewers = User.objects.filter(groups__name="Reviewer")

        data = [
            {
                "id": user.id,
                # "name": user.get_full_name() or user.username,
                "name": user.user_name,
                "email": user.email
            }
            for user in reviewers
        ]

        return Response(data)