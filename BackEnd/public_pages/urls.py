from django.urls import path

from . import views

app_name = 'public_pages'

urlpatterns = [
    path('<slug:slug>/', views.journal_landing, name='journal-landing'),
    path(
        '<slug:slug>/articles/<int:article_id>/',
        views.article_landing,
        name='article-landing',
    ),
]
