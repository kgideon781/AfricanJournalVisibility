from rest_framework import serializers
from .models import (Journal,Language,Platform,Country,ThematicArea,Volume,Article,JournalImage,Feedback,Manuscript,Review,ReviewerAssignment,EditorialDecision)
import re
from django.utils.html import strip_tags
from bs4 import BeautifulSoup
def strip_tags(value):
    return re.sub(r'<[^>]*>', '', value)

class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ['id','language']

class PlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = Platform
        fields = ['id','platform']

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id','country']

class ThematicAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThematicArea
        fields = ['id','thematic_area']


# Serializer for Article model
class ArticleSerializer(serializers.ModelSerializer):
    journal = serializers.PrimaryKeyRelatedField(queryset=Journal.objects.all(), required=True)
    volume = serializers.PrimaryKeyRelatedField(queryset=Volume.objects.all(), required=True)

    # abstract = serializers.SerializerMethodField()
    # Remove SerializerMethodField
    
    abstract = serializers.CharField(allow_blank=True, required=False)
    journal_title = serializers.CharField(source='journal.journal_title', read_only=True)
    volume_number = serializers.CharField(source='volume.volume_number', read_only=True)  # Flat volume number
    volume_issue_number = serializers.CharField(source='volume.issue_number', read_only=True)  # Flat issue number
    volume_year = serializers.CharField(source='volume.year', read_only=True)
    country=serializers.CharField(source='journal.country', read_only=True)
    thematic_area=serializers.CharField(source='journal.thematic_area', read_only=True)
    language=serializers.CharField(source='journal.language', read_only=True)

    class Meta:
        model = Article
        fields = [
            'id','journal','volume','title','authors','publisher','journal_title','publication_date','doi','license_url','electronic_issn','print_issn','article_type','pdf', 
            'volume_number','volume_issue_number','volume_year','country','language','thematic_area','reference_count','citation_count','abstract'
        ]
        
    def to_representation(self, instance):
        """Customize output to clean abstract tags."""
        data = super().to_representation(instance)

        if data.get('abstract'):
            # Use BeautifulSoup to clean <jats:p> and any other tags
            soup = BeautifulSoup(data['abstract'], 'lxml-xml')
            data['abstract'] = soup.get_text(separator=" ", strip=True)

        return data
   

class VolumeSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField()  # Ensure 'id' is explicitly included
    journal_id = serializers.PrimaryKeyRelatedField(queryset=Journal.objects.all(), source='journal', write_only=False)
    # articles = ArticleSerializer(many=True, read_only=True)  # Nested ArticleSerializer for read-only
    
    class Meta:
        model = Volume
        fields = ['id', 'journal_id', 'volume_number', 'issue_number', 'year']
    
    def create(self, validated_data):
        return Volume.objects.create(**validated_data)



class VolumeSerializer1(serializers.ModelSerializer):
    class Meta:
        model = Volume
        fields = ['id', 'journal', 'volume_number', 'issue_number', 'year']


# Serializer for JournalImage model
class JournalImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalImage
        fields = ['id', 'image', 'description']

class JournalSerializer(serializers.ModelSerializer):
    language=LanguageSerializer()
    platform=PlatformSerializer()
    country=CountrySerializer()
    thematic_area=ThematicAreaSerializer()
    # volumes = VolumeSerializer(many=True, read_only=True)
    # articles=ArticleSerializer(many=True,read_only=True)
    image = JournalImageSerializer(read_only=True)  # Only one image per journal, no 'many=True'
    class Meta:
        model = Journal
        fields = '__all__'  
        
class JournalSerializer1(serializers.ModelSerializer):
    class Meta:
        model = Journal
        fields = '__all__'


class JournalSubmissionSerializer(serializers.ModelSerializer):
    """Author-facing submission serializer. Whitelists the fields an author
    can populate; `approved` and `user` are stamped by the view."""

    volume = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = Journal
        fields = [
            'id',
            'journal_title',
            'publishers_name',
            'issn_number',
            'link',
            'summary',
            'language',
            'platform',
            'country',
            'thematic_area',
            'aim_identifier',
            'open_access_journal',
            'listed_in_doaj',
            'present_issn',
            'publisher_in_cope',
            'online_publisher_africa',
            'hosted_on_inasps',
            'google_scholar_index',
            'volume',
        ]

    def validate_volume(self, value):
        if not value:
            return value
        try:
            volume_number = int(value.get('volume_number'))
            year = int(value.get('year'))
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                "volume.volume_number and volume.year are required integers."
            )
        issue_number = value.get('issue_number', 1)
        try:
            issue_number = int(issue_number)
        except (TypeError, ValueError):
            raise serializers.ValidationError("volume.issue_number must be an integer.")
        return {
            'volume_number': volume_number,
            'issue_number': issue_number,
            'year': year,
        }

# Serializer for Article model
class FeedBackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = '__all__'

class CountsSerializer(serializers.Serializer):
    journals = serializers.IntegerField()
    volumes = serializers.IntegerField()
    articles = serializers.IntegerField()


# Manuscript Serializer
class ManuscriptSerializer(serializers.ModelSerializer):
    journal_title = serializers.CharField(source='journal.journal_title', read_only=True)
    author = serializers.CharField(source='corresponding_author.user_name', read_only=True)

    class Meta:
        model = Manuscript
        fields = [
            'id',
            'journal',
            'journal_title',
            'volume',
            'title',
            'abstract',
            'file',
            'authors',
            'corresponding_author',
            'author',
            'status',
            'created_at'
        ]
        read_only_fields = ['corresponding_author', 'status', 'created_at']

    def to_representation(self, instance):
        # Sensitive manuscript files require a signed URL; see media_views.py.
        ret = super().to_representation(instance)
        from .media_views import make_signed_media_url
        ret['file'] = make_signed_media_url(self.context.get('request'), instance.file)
        return ret


# Review Serializer
class ReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.user_name', read_only=True)

    class Meta:
        model = Review
        fields = [
            'id',
            'manuscript',
            'reviewer',
            'reviewer_name',
            'recommendation',
            'comments',
            'score',
            'created_at'
        ]
        read_only_fields = ['reviewer', 'created_at']

# Review Assignment Serializer
class ReviewerAssignmentSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.user_name', read_only=True)

    class Meta:
        model = ReviewerAssignment
        fields = [
            'id',
            'manuscript',
            'reviewer',
            'reviewer_name',
            'assigned_at',
            'is_completed'
        ]

#Editor Decision Serializer
class EditorialDecisionSerializer(serializers.ModelSerializer):
    editor_name = serializers.CharField(source='editor.user_name', read_only=True)

    class Meta:
        model = EditorialDecision
        fields = [
            'id',
            'manuscript',
            'editor',
            'editor_name',
            'decision',
            'notes',
            'decided_at'
        ]
        read_only_fields = ['editor', 'decided_at']