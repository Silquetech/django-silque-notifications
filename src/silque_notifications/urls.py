from django.urls import path

from . import views

app_name = "silque_notifications"

urlpatterns = [
    path("get_model_fields/", views.get_model_fields, name="get_model_fields"),
    path("get_model_date_fields/", views.get_model_date_fields, name="get_model_date_fields"),
    path("get_model_relational_recipients/", views.get_model_relational_recipients, name="get_model_relational_recipients"),
    path("save_notification/", views.save_notification, name="save_notification"),
    path("upload_file/", views.upload_file, name="upload_file"),
    path("media_library/", views.media_library, name="media_library"),
]
