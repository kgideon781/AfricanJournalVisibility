from rest_framework import serializers

from journalApis.models import Country
from .models import GREY_LIT_TYPES, GreyLiterature


class GreyLiteratureSerializer(serializers.ModelSerializer):
    country = serializers.PrimaryKeyRelatedField(
        queryset=Country.objects.all(), required=False, allow_null=True,
    )
    country_name = serializers.CharField(source="country.country", read_only=True)
    submitted_by = serializers.CharField(source="user.user_name", read_only=True)

    class Meta:
        model = GreyLiterature
        fields = [
            "id", "title", "slug",
            "item_type", "authors", "issuing_organization",
            "abstract", "keywords",
            "country", "country_name", "sub_region",
            "language", "publication_date",
            "source", "doi", "file",
            "approved", "submitted_by",
            "created_at", "updated_at",
        ]
        read_only_fields = ("slug", "approved", "created_at", "updated_at", "submitted_by", "country_name")

    def validate_item_type(self, value):
        valid = {code for code, _ in GREY_LIT_TYPES}
        if value not in valid:
            raise serializers.ValidationError(
                f"item_type must be one of: {', '.join(sorted(valid))}"
            )
        return value
