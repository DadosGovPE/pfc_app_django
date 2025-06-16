from django.urls import path
from . import views

urlpatterns = [
    path('responder/<int:pesquisa_id>/', views.responder_pesquisa, name='responder_pesquisa'),
    path('duplicar/', views.escolher_e_duplicar_pesquisa, name='duplicar_pesquisa_form'),
]
