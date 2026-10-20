from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_alter_userprofile_attendance_plan_per_week'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='clerk_id',
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='full_name',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='phone_number',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='profile',
            field=models.ImageField(blank=True, upload_to='profile_pics'),
        ),
    ]
