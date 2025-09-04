from django.urls import path
from material_app.views import *
from django.conf.urls.static import static
from django.conf import settings

app_name = 'material_app'

urlpatterns = [
    path('', index, name='index'),
    path('daftar_materials', daftar_materials, name='daftar_material'),
    path('data_produksi', data_produksi, name='data_produksi'),
    path('traceability_by_machine', traceability_by_machine, name='traceability_by_machine'),
    path('traceability_by_cu', traceability_by_cu, name='traceability_by_cu'),
    path('traceability_by_materials', traceability_by_materials, name='traceability_by_materials'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)