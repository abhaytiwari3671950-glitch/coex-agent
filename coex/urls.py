from django.urls import path
from chat import views, study_views, personal_views, quiz_views
urlpatterns = [
 path('api/quiz/start/<uuid:run_id>',quiz_views.start),
 path('api/quiz/answer/<uuid:session_id>',quiz_views.answer),
 path('api/memory',personal_views.memories),
 path('api/memory/update',personal_views.update_memory),
 path('api/feedback/<int:message_id>',personal_views.feedback),
 path('api/generated-image/<int:message_id>',personal_views.generated_image),
 path('api/search-widget/<int:message_id>',personal_views.search_widget),
 path('study/', study_views.page),
 path('api/study/<uuid:run_id>/reuse',study_views.reuse),
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
