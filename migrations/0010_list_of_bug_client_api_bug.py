# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-04-06 07:40
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('NearBeach', '0009_auto_20180406_1734'),
    ]

    operations = [
        migrations.AddField(
            model_name='list_of_bug_client',
            name='api_bug',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
    ]
