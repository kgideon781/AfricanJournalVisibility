from rest_framework import serializers
from authApi.models import NewUser



class RegisterUserSerializer(serializers.ModelSerializer):
    """
    Currently unused in preference of the below.
    """
    # email = serializers.EmailField(required=True)
    # user_name = serializers.CharField(required=True)
    # password = serializers.CharField(min_length=8, write_only=True)

    class Meta:
        model = NewUser
        fields = ( 'user_name','location','email','phone_number', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        # as long as the fields are the same, we can just use this
        instance = self.Meta.model(**validated_data)
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance
class UserListSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = NewUser
        fields = (
            'id',
            'email',
            'user_name',
            'phone_number',
            'location',
            'start_date',
            'is_staff',
            'is_superuser',
            'is_active',
            'approved',
            'roles',
        )

    def get_roles(self, obj):
        return list(obj.groups.values_list('name', flat=True))


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

class SetNewPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=6, max_length=68, write_only=True)
    password_confirm = serializers.CharField(min_length=6, max_length=68, write_only=True)

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Passwords do not match.")
        return data   
