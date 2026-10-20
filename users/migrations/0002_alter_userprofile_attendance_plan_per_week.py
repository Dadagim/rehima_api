from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='attendance_plan_per_week',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='role',
            field=models.CharField(
                choices=[
                    ('member', 'Member'),
                    ('coach', 'coach'),
                    ('casher', 'casher'),
                    ('admin', 'Admin'),
                ],
                default='member',
                max_length=20,
            ),
        ),
    ]
