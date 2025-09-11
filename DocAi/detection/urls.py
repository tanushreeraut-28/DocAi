from django.urls import path,include
from . import views

urlpatterns = [
    path("upload/", views.upload_view, name="upload"),
     path('reports/', views.reports_history, name='reports'),
    path("history/", views.reports_history, name="reports_history"),
    path("download/<int:detection_id>/", views.download_pdf_report, name="download_report"),
    path("delete/<int:detection_id>/", views.delete_report, name="delete_report"),
    
]
