from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("expenses.urls")),
    path("", include("django.contrib.auth.urls")),
]
