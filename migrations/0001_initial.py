# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-06-23 04:52
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='contact_history',
            fields=[
                ('contact_history_id', models.AutoField(primary_key=True, serialize=False)),
                ('contact_date', models.DateField()),
                ('contact_history', models.TextField()),
                ('audit_date', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
            ],
            options={
                'db_table': 'contact_history',
            },
        ),
        migrations.CreateModel(
            name='costs',
            fields=[
                ('cost_id', models.AutoField(primary_key=True, serialize=False)),
                ('cost_description', models.CharField(max_length=255)),
                ('cost_amount', models.DecimalField(decimal_places=2, max_digits=19)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
            ],
            options={
                'db_table': 'costs',
            },
        ),
        migrations.CreateModel(
            name='customers',
            fields=[
                ('customer_id', models.AutoField(primary_key=True, serialize=False)),
                ('customer_first_name', models.CharField(max_length=50)),
                ('customer_last_name', models.CharField(max_length=50)),
                ('customer_email', models.CharField(max_length=200)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
            ],
            options={
                'db_table': 'customers',
            },
        ),
        migrations.CreateModel(
            name='customers_campus',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('customer_phone', models.CharField(max_length=11)),
                ('customer_fax', models.CharField(max_length=11)),
            ],
            options={
                'db_table': 'customers_campus',
            },
        ),
        migrations.CreateModel(
            name='document_folders',
            fields=[
                ('document_folder_id', models.AutoField(primary_key=True, serialize=False)),
                ('document_folder_description', models.CharField(max_length=255)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
                ('parent_folder_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='NearBeach.document_folders')),
            ],
            options={
                'db_table': 'document_folder',
            },
        ),
        migrations.CreateModel(
            name='documents',
            fields=[
                ('document_id', models.AutoField(primary_key=True, serialize=False)),
                ('document_description', models.CharField(max_length=255)),
                ('document_url_location', models.TextField(blank=True, null=True)),
                ('document', models.FileField(blank=True, null=True, upload_to='documents/')),
                ('document_uploaded_audit', models.DateTimeField(auto_now_add=True)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
                ('document_folder_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='NearBeach.document_folders')),
            ],
            options={
                'db_table': 'documents',
            },
        ),
        migrations.CreateModel(
            name='group_permissions',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(max_length=15)),
            ],
            options={
                'db_table': 'group_permissions',
            },
        ),
        migrations.CreateModel(
            name='groups',
            fields=[
                ('group_id', models.AutoField(primary_key=True, serialize=False)),
                ('group_name', models.CharField(max_length=50, unique=True)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
            ],
            options={
                'db_table': 'groups',
            },
        ),
        migrations.CreateModel(
            name='list_of_contact_types',
            fields=[
                ('contact_type_id', models.AutoField(primary_key=True, serialize=False)),
                ('contact_type', models.CharField(max_length=10)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
            ],
            options={
                'db_table': 'list_of_contact_types',
            },
        ),
        migrations.CreateModel(
            name='list_of_countries',
            fields=[
                ('country_id', models.CharField(max_length=2, primary_key=True, serialize=False)),
                ('country_name', models.CharField(max_length=50)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
            ],
            options={
                'db_table': 'list_of_countries',
            },
        ),
        migrations.CreateModel(
            name='list_of_countries_regions',
            fields=[
                ('region_id', models.AutoField(primary_key=True, serialize=False)),
                ('region_name', models.CharField(max_length=150)),
                ('region_type', models.CharField(max_length=80, null=True)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
                ('country_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.list_of_countries')),
            ],
            options={
                'db_table': 'list_of_countries_regions',
            },
        ),
        migrations.CreateModel(
            name='list_of_titles',
            fields=[
                ('title_id', models.AutoField(primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=10)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
            ],
            options={
                'db_table': 'list_of_titles',
            },
        ),
        migrations.CreateModel(
            name='organisations',
            fields=[
                ('organisations_id', models.AutoField(primary_key=True, serialize=False)),
                ('organisation_name', models.CharField(max_length=255)),
                ('organisation_website', models.CharField(max_length=50)),
                ('organisation_email', models.CharField(max_length=100)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
            ],
            options={
                'db_table': 'organisations',
            },
        ),
        migrations.CreateModel(
            name='organisations_campus',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('campus_nickname', models.CharField(max_length=100)),
                ('campus_phone', models.CharField(max_length=11, null=True)),
                ('campus_fax', models.CharField(max_length=11, null=True)),
                ('campus_address1', models.CharField(max_length=255, null=True)),
                ('campus_address2', models.CharField(max_length=255, null=True)),
                ('campus_address3', models.CharField(max_length=255, null=True)),
                ('campus_suburb', models.CharField(max_length=50)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
                ('campus_country_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.list_of_countries')),
                ('campus_region_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.list_of_countries_regions')),
                ('organisations_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.organisations')),
            ],
            options={
                'db_table': 'organisations_campus',
            },
        ),
        migrations.CreateModel(
            name='project',
            fields=[
                ('project_id', models.AutoField(primary_key=True, serialize=False)),
                ('project_name', models.CharField(max_length=255)),
                ('project_description', models.TextField()),
                ('project_start_date', models.DateTimeField()),
                ('project_end_date', models.DateTimeField()),
                ('project_status', models.CharField(choices=[('New', 'New'), ('Open', 'Open'), ('Resolved', 'Resolved'), ('Closed', 'Closed')], default='New', max_length=15)),
                ('organisations_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.organisations')),
            ],
            options={
                'db_table': 'project',
            },
        ),
        migrations.CreateModel(
            name='project_customers',
            fields=[
                ('project_customers_id', models.AutoField(primary_key=True, serialize=False)),
                ('customer_description', models.CharField(blank=True, max_length=255, null=True)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
                ('audit_date', models.DateTimeField(auto_now=True)),
                ('customer_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.customers')),
                ('project_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.project')),
            ],
            options={
                'db_table': 'project_customers',
            },
        ),
        migrations.CreateModel(
            name='project_groups',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
                ('audit_date', models.DateTimeField(auto_now=True)),
                ('groups_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.groups')),
                ('project_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.project')),
            ],
            options={
                'db_table': 'project_groups',
            },
        ),
        migrations.CreateModel(
            name='project_history',
            fields=[
                ('project_history_id', models.AutoField(primary_key=True, serialize=False)),
                ('user_infomation', models.CharField(max_length=255)),
                ('project_history', models.TextField()),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
                ('audit_date', models.DateTimeField(auto_now=True)),
                ('project_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.project')),
                ('user_id', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'project_history',
            },
        ),
        migrations.CreateModel(
            name='project_stages',
            fields=[
                ('project_stages_id', models.AutoField(primary_key=True, serialize=False)),
                ('audit_date', models.DateTimeField(auto_now=True)),
                ('project_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.project')),
            ],
            options={
                'db_table': 'project_stages',
            },
        ),
        migrations.CreateModel(
            name='project_tasks',
            fields=[
                ('project_tasks', models.AutoField(primary_key=True, serialize=False)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
                ('audit_date', models.DateTimeField(auto_now=True)),
                ('project_id', models.ForeignKey(db_column='project_id', on_delete=django.db.models.deletion.CASCADE, to='NearBeach.project')),
            ],
            options={
                'db_table': 'project_tasks',
            },
        ),
        migrations.CreateModel(
            name='stages',
            fields=[
                ('stages_id', models.AutoField(primary_key=True, serialize=False)),
                ('stage', models.CharField(max_length=45)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
                ('group_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.groups')),
            ],
            options={
                'db_table': 'stages',
            },
        ),
        migrations.CreateModel(
            name='tasks',
            fields=[
                ('tasks_id', models.AutoField(primary_key=True, serialize=False)),
                ('task_short_description', models.CharField(max_length=255)),
                ('task_long_description', models.TextField()),
                ('task_start_date', models.DateTimeField(auto_now=True)),
                ('task_end_date', models.DateTimeField()),
                ('task_status', models.CharField(choices=[('New', 'New'), ('Open', 'Open'), ('Resolved', 'Resolved'), ('Closed', 'Closed')], default='New', max_length=15)),
                ('organisations_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.organisations')),
                ('task_assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'tasks',
            },
        ),
        migrations.CreateModel(
            name='tasks_actions',
            fields=[
                ('tasks_actions_id', models.AutoField(primary_key=True, serialize=False)),
                ('task_action', models.TextField()),
                ('audit_date', models.DateTimeField(auto_now=True)),
                ('submitted_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('tasks_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.tasks')),
            ],
            options={
                'db_table': 'tasks_actions',
            },
        ),
        migrations.CreateModel(
            name='tasks_customers',
            fields=[
                ('tasks_customers_id', models.AutoField(primary_key=True, serialize=False)),
                ('customers_description', models.CharField(blank=True, max_length=155, null=True)),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
                ('audit_date', models.DateTimeField(auto_now=True)),
                ('customer_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.customers')),
                ('tasks_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.tasks')),
            ],
            options={
                'db_table': 'tasks_customers',
            },
        ),
        migrations.CreateModel(
            name='tasks_groups',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
                ('audit_date', models.DateTimeField(auto_now=True)),
                ('groups_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.groups')),
                ('tasks_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.tasks')),
            ],
            options={
                'db_table': 'tasks_groups',
            },
        ),
        migrations.CreateModel(
            name='tasks_history',
            fields=[
                ('tasks_history_id', models.AutoField(primary_key=True, serialize=False)),
                ('user_infomation', models.CharField(max_length=255)),
                ('task_history', models.TextField()),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
                ('audit_date', models.DateTimeField(auto_now=True)),
                ('tasks_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.tasks')),
                ('user_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'tasks_history',
            },
        ),
        migrations.CreateModel(
            name='user_groups',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_deleted', models.CharField(choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')], default='FALSE', max_length=5)),
                ('group_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.groups')),
                ('user_group_permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.group_permissions')),
                ('username', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_groups',
            },
        ),
        migrations.AddField(
            model_name='project_tasks',
            name='task_id',
            field=models.ForeignKey(db_column='task_id', on_delete=django.db.models.deletion.CASCADE, to='NearBeach.tasks'),
        ),
        migrations.AddField(
            model_name='project_stages',
            name='stages_id',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.stages'),
        ),
        migrations.AddField(
            model_name='documents',
            name='project_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='NearBeach.project'),
        ),
        migrations.AddField(
            model_name='documents',
            name='task_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='NearBeach.tasks'),
        ),
        migrations.AddField(
            model_name='document_folders',
            name='project_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='NearBeach.project'),
        ),
        migrations.AddField(
            model_name='document_folders',
            name='task_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='NearBeach.tasks'),
        ),
        migrations.AddField(
            model_name='customers_campus',
            name='campus_id',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.organisations_campus'),
        ),
        migrations.AddField(
            model_name='customers_campus',
            name='customer_id',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.customers'),
        ),
        migrations.AddField(
            model_name='customers',
            name='customer_title',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.list_of_titles'),
        ),
        migrations.AddField(
            model_name='customers',
            name='organisations_id',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.organisations'),
        ),
        migrations.AddField(
            model_name='costs',
            name='project_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='NearBeach.project'),
        ),
        migrations.AddField(
            model_name='costs',
            name='task_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='NearBeach.tasks'),
        ),
        migrations.AddField(
            model_name='contact_history',
            name='contact_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.list_of_contact_types'),
        ),
        migrations.AddField(
            model_name='contact_history',
            name='customer_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='NearBeach.customers'),
        ),
        migrations.AddField(
            model_name='contact_history',
            name='organisations_id',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='NearBeach.organisations'),
        ),
        migrations.AddField(
            model_name='contact_history',
            name='user_id',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]
