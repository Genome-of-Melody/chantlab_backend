from django.conf.urls import url
from django.contrib import admin
from melodies import views
from melodies import account_views

urlpatterns = [
    url(r'admin/', admin.site.urls),  #navigation url for admin page
    url(r'^api/auth/register/$', account_views.register),
    url(r'^api/auth/login/$', account_views.login_view),
    url(r'^api/auth/logout/$', account_views.logout_view),
    url(r'^api/auth/me/$', account_views.me),
    url(r'^api/alignments/$', account_views.alignment_list),
    url(r'^api/alignments/(?P<name>.+)/$', account_views.alignment_detail),
    url(r'^api/settings/$', account_views.user_settings),
    url(r'^api/chants/$', views.chant_list),
    url(r'^api/chants/(?P<pk>[0-9]+)$', views.chant_display),
    url(r'^api/chants/align/$', views.chant_align),
    url(r'^api/chants/upload/$', views.upload_data),
    url(r'^api/chants/data-sources', views.get_data_sources),
    url(r'^api/chants/fontes', views.get_sigla),
    url(r'^api/chants/export/$', views.export_dataset),
    url(r'^api/chants/create-dataset/$', views.create_dataset),
    url(r'^api/chants/add-to-dataset/$', views.add_to_dataset),
    url(r'^api/chants/delete-dataset/$', views.delete_dataset),
    url(r'^api/chants/update-volpiano/$', views.update_volpiano),
    url(r'^api/chants/mrbayes-volpiano/$', views.mrbayes_volpiano),
]
