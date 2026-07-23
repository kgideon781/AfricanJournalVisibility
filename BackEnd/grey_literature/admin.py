from django.contrib import admin

from .models import GreyLiterature


@admin.action(description="Approve selected grey-literature items")
def approve_selected(modeladmin, request, queryset):
    queryset.update(approved=True)


@admin.register(GreyLiterature)
class GreyLiteratureAdmin(admin.ModelAdmin):
    list_display = (
        "id", "title", "item_type", "issuing_organization",
        "country", "language", "approved", "publication_date", "created_at",
    )
    list_filter = ("approved", "item_type", "country", "language")
    search_fields = ("title", "authors", "keywords", "abstract", "issuing_organization", "doi")
    readonly_fields = ("slug", "pdf_text", "search_vector", "created_at", "updated_at")
    actions = [approve_selected]
    ordering = ("-created_at",)
