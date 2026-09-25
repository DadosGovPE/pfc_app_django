from django.urls import path

from . import views

app_name = "classificados"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("novo/", views.product_create, name="product_create"),
    path("produto/<int:pk>/", views.product_detail, name="product_detail"),
    path("produto/<int:pk>/curtir/", views.toggle_like, name="toggle_like"),
    path("produto/<int:pk>/comentar/", views.add_comment, name="add_comment"),
]
