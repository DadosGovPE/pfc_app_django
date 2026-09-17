from django.urls import path

from .views import catalog, my_products, place_bid, product_create


app_name = "leilao"

urlpatterns = [
    path("", catalog, name="catalog"),
    path("produto/novo/", product_create, name="product_create"),
    path("produto/<int:pk>/lance/", place_bid, name="place_bid"),
    path("meus-produtos/", my_products, name="my_products"),
]
