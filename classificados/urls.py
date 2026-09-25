from django.urls import path

from . import views

app_name = "classificados"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("comentarios-pendentes/", views.unread_count, name="unread_count"),
    path("novo/", views.product_create, name="product_create"),
    path("meus-produtos/", views.my_products, name="my_products"),
    path("produto/<int:pk>/", views.product_detail, name="product_detail"),
    path("produto/<int:pk>/editar/", views.product_edit, name="product_edit"),
    path("produto/<int:pk>/alternar-ativo/", views.toggle_active, name="toggle_active"),
    path("produto/<int:pk>/excluir/", views.product_delete, name="product_delete"),
    path("produto/<int:pk>/curtir/", views.toggle_like, name="toggle_like"),
    path("produto/<int:pk>/comentar/", views.add_comment, name="add_comment"),
]
