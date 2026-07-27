"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap as sitemap_view
from drf_spectacular.views import SpectacularAPIView,SpectacularSwaggerView,SpectacularRedocView
from public_pages.sitemaps import SITEMAPS as _JOURNAL_SITEMAPS
from grey_literature.sitemaps import GreyLiteratureSitemap
SITEMAPS = {**_JOURNAL_SITEMAPS, 'grey_literature': GreyLiteratureSitemap}
from public_pages.views import robots_txt
urlpatterns = [
    path('admin/', admin.site.urls),
    path('journal_api/',include('journalApis.urls')),
    path('api/',include('authApi.urls')),
    path('news/',include('news.urls')),
    path('funding/',include('funding.urls')),
    path('blog/',include('blog.urls')),
    path('oai', include('oai_pmh.urls')),
    path('journals/', include('public_pages.urls')),
    path('grey_api/', include('grey_literature.urls')),
    path('sitemap.xml', sitemap_view, {'sitemaps': SITEMAPS}, name='sitemap'),
    path('robots.txt', robots_txt, name='robots-txt'),
    path('schema/',SpectacularAPIView.as_view(),name="schema"),
    path('',SpectacularSwaggerView.as_view(url_name='schema')),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),  
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # DEBUG-only no-op

# Production media serving: signed URL for /media/manuscripts/*, open otherwise.
# See journalApis/media_views.py.
from django.urls import re_path
from journalApis.media_views import serve_media
urlpatterns += [
    re_path(r'^media/(?P<media_path>.+)$', serve_media),
]
