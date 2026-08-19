from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('melodies', '0005_user_workspace'),
    ]

    operations = [
        migrations.RenameField(
            model_name='chant',
            old_name='source_id',
            new_name='srclink',
        ),
        migrations.RenameField(
            model_name='chant',
            old_name='drupal_path',
            new_name='chantlink',
        ),
        migrations.RenameField(
            model_name='chant',
            old_name='notes',
            new_name='image',
        ),
        migrations.AddField(
            model_name='chant',
            name='db',
            field=models.TextField(blank=True, null=True),
        ),
    ]
