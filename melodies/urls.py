from django.conf.urls import url 
from melodies import views 
 
urlpatterns = [ 
    url(r'^api/melodies$', views.melody_list),
    url(r'^api/melodies/(?P<pk>[0-9]+)$', views.melody_detail),
    url(r'^api/melodies/(?P<pk>[0-9]+)/detail$', views.chant_display),
    url(r'^api/melodies/align/$', views.chant_align),
    url(r'^api/melodies/upload/$', views.upload_data)
]
