from django.urls import path
from . import views

urlpatterns = [
    path('responder/<int:pesquisa_id>/', views.responder_pesquisa, name='responder_pesquisa'),
]
