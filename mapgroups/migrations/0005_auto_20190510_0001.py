# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2019-05-10 00:01
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.manager


class Migration(migrations.Migration):

    dependencies = [
        ('mapgroups', '0004_auto_20150430_1729'),
    ]

    operations = [
        migrations.AlterModelManagers(
            name='activitylog',
            managers=[
                ('recent', django.db.models.manager.Manager()),
            ],
        ),
        migrations.AlterField(
            model_name='emailinvitation',
            name='to_address',
            field=models.EmailField(max_length=254),
        ),
    ]
