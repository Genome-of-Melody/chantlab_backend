from rest_framework import serializers
from melodies.models import Chant


class ChantSerializer(serializers.ModelSerializer):
    is_owned = serializers.SerializerMethodField()

    class Meta:
        model = Chant
        fields = ('id', 'corpus_id', 'incipit', 'cantus_id',
            'mode', 'finalis', 'differentia', 'siglum', 'position',
            'folio', 'sequence', 'marginalia', 'cao_concordances',
            'feast_id', 'genre_id', 'office_id', 'source_id', 'melody_id',
            'drupal_path', 'full_text', 'full_text_manuscript', 'volpiano', 'notes',
            'dataset_name', 'dataset_idx', 'century_code', 'is_owned')

    def get_is_owned(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.owner_id == request.user.id
