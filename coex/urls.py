from django.urls import path
from chat import views, study_views
urlpatterns = [
 path('study/', study_views.page),
 path('api/study', study_views.create),
 path('api/study/history', study_views.history),
 path('api/study/<uuid:run_id>', study_views.detail),
 path('api/study/<uuid:run_id>/step', study_views.step),
 path('',views.home), path('s',views.home),
 path('login/',views.sign_in), path('signup/',views.sign_up), path('logout/',views.sign_out),
 path('api/conversations',views.conversations),
 path('api/conversations/<uuid:conversation_id>',views.conversation),
 path('api/chat',views.chat), path('api/media',views.media),
]
