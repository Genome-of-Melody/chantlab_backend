from django.conf.urls import url 
from melodies import views 
 
urlpatterns = [ 
    url(r'^api/chants/$', views.chant_list),
    url(r'^api/chants/(?P<pk>[0-9]+)$', views.chant_display),
    url(r'^api/chants/align/$', views.chant_align),
    url(r'^api/chants/align-text/$', views.chant_align_text),
    url(r'^api/chants/upload/$', views.upload_data),
    url(r'^api/chants/sources', views.get_sources)
]
