from django.urls import path
from chat import views
urlpatterns = [
 path('',views.home), path('s',views.home),
 path('login/',views.sign_in), path('signup/',views.sign_up), path('logout/',views.sign_out),
 path('api/conversations',views.conversations),
 path('api/conversations/<uuid:conversation_id>',views.conversation),
 path('api/chat',views.chat), path('api/media',views.media),
]
