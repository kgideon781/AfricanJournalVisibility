from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
   
class Language(models.Model):
    language=models.CharField(max_length=1000)
    created_at=models.DateTimeField(auto_now_add=True)

    def __str__(self):
         return f" {self.language}"
     
class Platform(models.Model):
    platform=models.CharField(max_length=1000)
    created_at=models.DateTimeField(auto_now_add=True)

    def __str__(self):
         return f" {self.platform}"
    
class Country(models.Model):
     country=models.CharField(max_length=1000)
     created_at=models.DateTimeField(auto_now_add=True)

     def __str__(self):
        return f" {self.country}"
     
class ThematicArea(models.Model):  
     thematic_area=models.CharField(max_length=1000)
     created_at=models.DateTimeField(auto_now_add=True)

     def __str__(self):
        return f" {self.thematic_area}"
     
class Journal(models.Model):
     journal_title=models.CharField(max_length=1055)
     slug = models.SlugField(max_length=200, unique=True, null=True, blank=True)
     #platform=models.ForeignKey(Platform,on_delete=models.CASCADE,unique=True,null=True, blank=True)
     platform = models.ForeignKey(Platform, on_delete=models.CASCADE, null=True, blank=True)
     #country=models.ForeignKey(Country,on_delete=models.CASCADE,unique=True,null=True, blank=True)
     country=models.ForeignKey(Country,on_delete=models.CASCADE,null=True, blank=True)
     publishers_name=models.CharField(max_length=1055,null=True, blank=True)
     #language=models.ForeignKey(Language,on_delete=models.CASCADE,unique=True,null=True, blank=True)
     language=models.ForeignKey(Language,on_delete=models.CASCADE,null=True, blank=True)
     #thematic_area=models.ForeignKey(ThematicArea,on_delete=models.CASCADE,unique=True,null=True, blank=True)
     thematic_area=models.ForeignKey(ThematicArea,on_delete=models.CASCADE,null=True, blank=True)
     issn_number=models.CharField(max_length=100, null=True, blank=True)
     #link = models.URLField(max_length=2048, blank=True, null=True)
     link = models.TextField(blank=True, null=True)
     aim_identifier = models.BooleanField(blank=True, null=True)
     medline=models.BooleanField(blank=True, null=True)
     google_scholar_index=models.BooleanField(blank=True, null=True)
     impact_factor=models.FloatField(blank=True, null=True)
     sjr=models.BooleanField(blank=True, null=True)
     h_index=models.FloatField(blank=True, null=True)
     eigen_factor=models.BooleanField(blank=True, null=True)
     eigen_metrix=models.CharField(max_length=1055,null=True, blank=True)
     snip=models.BooleanField(blank=True, null=True)
     snip_metrix=models.FloatField(blank=True, null=True)
     open_access_journal=models.BooleanField(blank=True, null=True)
     listed_in_doaj=models.BooleanField(blank=True, null=True)
     present_issn=models.BooleanField(blank=True, null=True)
     publisher_in_cope=models.BooleanField(blank=True, null=True)
     online_publisher_africa=models.BooleanField(blank=True, null=True)
     hosted_on_inasps=models.BooleanField(blank=True, null=True)
     summary = models.TextField(null=True, blank=True)
     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
     approved = models.BooleanField(default=False, null=True, blank=True)
     created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

     class Meta:
        indexes = [
            # Composite index on platform, country, language, and thematic_area
            models.Index(fields=['journal_title','platform','country', 'language', 'thematic_area','issn_number','summary']),
            # You can also add indexes for other frequently filtered fields if needed
            models.Index(fields=['aim_identifier']),
            models.Index(fields=['sjr']),
            models.Index(fields=['listed_in_doaj']),
            models.Index(fields=['present_issn']),
            models.Index(fields=['open_access_journal']),
            models.Index(fields=['publisher_in_cope']),
            models.Index(fields=['online_publisher_africa']),
            models.Index(fields=['impact_factor']),
            models.Index(fields=['h_index']),
            models.Index(fields=['hosted_on_inasps']),
            models.Index(fields=['google_scholar_index']),
        ]
     def __str__(self):
            return f"{self.id}-{self.journal_title}"

class JournalsWithoutVolumesManager(models.Manager):
    def get_queryset(self):
        # Return journals with no associated volumes
        return super().get_queryset().filter(volumes__isnull=True)

class JournalsWithoutVolumes(Journal):
    objects = JournalsWithoutVolumesManager()

    class Meta:
        proxy = True  # Define this model as a proxy
        verbose_name = "Journal (No Volume)"
        verbose_name_plural = "Journals (No Volumes)"



class JournalImage(models.Model):
    journal = models.OneToOneField(Journal, on_delete=models.CASCADE, related_name="image")
    image = models.ImageField(upload_to='journals/images/', blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)  # Optional description of the image
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes=[models.Index(fields=['image','description'])]

    def __str__(self):
        return f"Image for {self.journal.journal_title} uploaded on {self.uploaded_at}"


class JournalsWithoutImagesManager(models.Manager):
    def get_queryset(self):
        # Return journals with no associated JournalImage
        return super().get_queryset().filter(image__isnull=True)

class JournalsWithoutImages(Journal):
    objects = JournalsWithoutImagesManager()

    class Meta:
        proxy = True  # Define this model as a proxy
        verbose_name = "Journal (No Image)"
        verbose_name_plural = "Journals (No Images)"



'''
class LastProcessedJournal(models.Model):
    last_processed_id = models.PositiveIntegerField(default=0)
'''
class LastProcessedJournal(models.Model):
    last_processed_id = models.PositiveIntegerField(default=0)
    date_processed = models.DateTimeField(default=timezone.now)

    class Meta:
        # Ensures there's only one entry in this table
        unique_together = ['last_processed_id']


class Volume(models.Model):
    journal = models.ForeignKey('Journal', on_delete=models.CASCADE, related_name="volumes")
    volume_number = models.PositiveIntegerField(verbose_name="Volume Number")
    issue_number = models.PositiveIntegerField(verbose_name="Issue Number", default=1)
    year = models.PositiveIntegerField(verbose_name="Year of Publication")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [ models.Index(fields=['volume_number','issue_number','year'])]
        
        constraints = [
            models.UniqueConstraint(fields=['journal', 'volume_number', 'issue_number'], name='unique_journal_volume_issue')
        ]

    def __str__(self):
        return f"Volume {self.volume_number} No. {self.issue_number} of {self.journal.journal_title} ({self.year})"


class Article(models.Model):
    journal = models.ForeignKey(
        'Journal',  # Reference to the Journal model
        on_delete=models.CASCADE,  # If the journal is deleted, its articles are also deleted
        related_name="articles",  # Allows reverse access from the Journal model
        blank=True,  # Optional field
        null=True  # Allow null values for existing data
    )
    volume = models.ForeignKey(Volume, on_delete=models.CASCADE, related_name="articles", blank=True,  null=True)  
    #title = models.CharField(max_length=255)
    title = models.TextField()
    authors = models.TextField()  # Comma-separated list of authors
    keywords = models.TextField(blank=True, null=True)
    publication_date = models.DateField(blank=True, null=True)
    pdf = models.FileField(upload_to='articles/pdfs/', blank=True, null=True)

    # CrossRef metadata and publisher information
    #doi = models.CharField(max_length=255, blank=True, null=True)
    doi = models.TextField(blank=True, null=True)
    #url = models.URLField(blank=True, null=True)
    url = models.TextField(blank=True, null=True)
    reference_count = models.PositiveIntegerField(default=0)
    citation_count = models.PositiveIntegerField(default=0)
    #license_url = models.URLField(blank=True, null=True)
    license_url = models.TextField(blank=True, null=True)
    page_start = models.CharField(max_length=10, blank=True, null=True)
    page_end = models.CharField(max_length=10, blank=True, null=True)
    abstract = models.TextField(blank=True, null=True)
    subjects = models.TextField(blank=True, null=True)  # Comma-separated list of subjects
    article_type = models.CharField(max_length=1050, blank=True, null=True)
    electronic_issn = models.CharField(max_length=1050, blank=True, null=True)
    print_issn = models.CharField(max_length=1050, blank=True, null=True)
    publisher = models.CharField(max_length=1255, blank=True, null=True)
    publisher_location = models.CharField(max_length=255, blank=True, null=True)
    language = models.CharField(max_length=8, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    pdf_text = models.TextField(blank=True, null=True)
    search_vector = SearchVectorField(blank=True, null=True)

    class Meta:
        indexes = [
            GinIndex(fields=["search_vector"], name="article_search_vector_gin"),
        ]

    def __str__(self):
        if self.journal:
            return f"{self.title} - {self.journal.journal_title}"
        else:
            return f"{self.title} - No Journal"


class JournalsWithoutArticlesManager(models.Manager):
    def get_queryset(self):
        # Return journals with no associated articles
        return super().get_queryset().filter(articles__isnull=True).distinct()

class JournalsWithoutArticles(Journal):
    objects = JournalsWithoutArticlesManager()

    class Meta:
        proxy = True  # Define this model as a proxy
        verbose_name = "Journal (No Articles)"
        verbose_name_plural = "Journals (No Articles)"

class Feedback(models.Model):
    name=models.CharField(max_length=2000,blank=True,null=True)
    email=models.CharField(max_length=2000,blank=True,null=True)
    question=models.TextField(blank=True,null=True)


######################################################################
#     Manuscript Section   Added                                     #
######################################################################
class Manuscript(models.Model):
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name="manuscripts")
    volume = models.ForeignKey(Volume, on_delete=models.SET_NULL, null=True, blank=True)

    title = models.TextField()
    abstract = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to="manuscripts/")

    authors = models.TextField()

    corresponding_author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submitted_manuscripts"
    )

    status = models.CharField(
        max_length=30,
        choices=[
            ("submitted", "Submitted"),
            ("under_review", "Under Review"),
            ("revision", "Revision Required"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
            ("published", "Published"),
        ],
        default="submitted"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.id} - {self.title}"
    

class Review(models.Model):
    manuscript = models.ForeignKey(Manuscript, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    recommendation = models.CharField(
        max_length=20,
        choices=[
            ("accept", "Accept"),
            ("minor", "Minor Revision"),
            ("major", "Major Revision"),
            ("reject", "Reject"),
        ]
    )

    comments = models.TextField()
    score = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        ReviewerAssignment.objects.filter(
            manuscript=self.manuscript,
            reviewer=self.reviewer
        ).update(is_completed=True)

    def __str__(self):
        return (
            f"Review {self.id}: "
            f"Manuscript {self.manuscript.id} - "
            f"{self.manuscript.title} "
            f"by {self.reviewer.user_name}"
        )


class ReviewerAssignment(models.Model):
    manuscript = models.ForeignKey(Manuscript, on_delete=models.CASCADE)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    assigned_at = models.DateTimeField(auto_now_add=True)

    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return (
            f"{self.id} - "
            f"{self.manuscript.title} → "
            f"{self.reviewer.user_name}"
        )


class EditorialDecision(models.Model):
    manuscript = models.OneToOneField(Manuscript, on_delete=models.CASCADE)

    editor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    decision = models.CharField(
        max_length=20,
        choices=[
            ("accept", "Accept"),
            ("reject", "Reject"),
            ("revise", "Revise"),
        ]
    )

    notes = models.TextField(blank=True, null=True)
    decided_at = models.DateTimeField(auto_now_add=True)

    