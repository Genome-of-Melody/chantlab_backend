from django.conf import settings
from django.db import models


class Chant(models.Model):
    id = models.AutoField(primary_key=True)
    corpus_id = models.TextField(blank=True, null=True)
    incipit = models.TextField(blank=True, null=True)
    cantus_id = models.TextField(blank=True, null=True)
    mode = models.TextField(blank=True, null=True)
    finalis = models.TextField(blank=True, null=True)
    differentia = models.TextField(blank=True, null=True)
    siglum = models.TextField(blank=True, null=True)
    position = models.TextField(blank=True, null=True)
    folio = models.TextField(blank=True, null=True)
    sequence = models.FloatField(blank=True, null=True)
    marginalia = models.TextField(blank=True, null=True)
    cao_concordances = models.FloatField(blank=True, null=True)
    feast_id = models.TextField(blank=True, null=True)
    genre_id = models.TextField(blank=True, null=True)
    office_id = models.TextField(blank=True, null=True)
    srclink = models.TextField(blank=True, null=True)
    melody_id = models.TextField(blank=True, null=True)
    chantlink = models.TextField(blank=True, null=True)
    db = models.TextField(blank=True, null=True)
    full_text = models.TextField(blank=True, null=True)
    full_text_manuscript = models.TextField(blank=True, null=True)
    volpiano = models.TextField(blank=True, null=True)
    image = models.TextField(blank=True, null=True)
    dataset_name = models.TextField(blank=True, null=True)
    dataset_idx = models.IntegerField(blank=True, null=True)
    century_code = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chants',
        blank=True,
        null=True,
    )

    class Meta:
        managed = True
        db_table = 'chant'


class SavedAlignment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_alignments',
    )
    name = models.CharField(max_length=255)
    data = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'saved_alignment'
        unique_together = ('user', 'name')


class UserSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chantlab_settings',
    )
    data = models.TextField(default='{}')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_settings'
