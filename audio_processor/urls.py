from django.urls import path
from . import views

app_name = 'audio_processor'

urlpatterns = [
    path('upload/', views.AudioUploadView.as_view(), name='upload'),
    path('status/<str:task_id>/', views.TaskStatusView.as_view(), name='status'),
    path('download/<str:audio_id>/', views.DownloadView.as_view(), name='download'),
    path('detail/<str:audio_id>/', views.AudioDetailView.as_view(), name='detail'),
]