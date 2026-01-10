from django.urls import path
from . import views

app_name = 'session_manager'

urlpatterns = [
    path('create/', views.CreateSessionView.as_view(), name='create'),
    path('join/', views.JoinSessionView.as_view(), name='join'),
    path('active/', views.ActiveSessionsView.as_view(), name='active'),
    path('<str:room_code>/', views.SessionDetailView.as_view(), name='detail'),
    path('<str:room_code>/leave/', views.LeaveSessionView.as_view(), name='leave'),
    path('<str:room_code>/messages/', views.SessionMessagesView.as_view(), name='messages'),
]
