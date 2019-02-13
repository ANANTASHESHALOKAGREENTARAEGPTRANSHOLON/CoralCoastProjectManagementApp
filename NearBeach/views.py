#Import NearBeach Modules
from .forms import *
from .models import *
from .private_media import *

#Import django Modules
from django.conf import settings
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core import serializers
from django.core.files.storage import FileSystemStorage
from django.db.models import Sum, Q, Min, Value
from django.db.models.functions import Concat
from django.http import HttpResponse,HttpResponseForbidden, HttpResponseRedirect, Http404, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, render_to_response
from django.template import RequestContext, loader
from django.urls import reverse
from .misc_functions import *
from .user_permissions import return_user_permission_level
from datetime import timedelta
from django.db.models import Max
from django.core.mail import EmailMessage, EmailMultiAlternatives
from geolocation.main import GoogleMaps
from django.http import JsonResponse
#from weasyprint import HTML
from urllib.request import urlopen
from weasyprint import HTML
from django.core.mail import send_mail
from urllib.parse import urlparse, urlencode, quote_plus

#import python modules
import datetime, json, simplejson, urllib.parse


@login_required(login_url='login')
def add_campus_to_customer(request, customer_id, campus_id):
    """
    This function can only exist in POST. It will add a customer to a campus
    :param request:
    :param customer_id: the customer's id
    :param campus_id: the campus's id to add the customer too
    :return: Success or fail - depending if it worked or not
    """
    if request.method == "POST":
        # Get the SQL Instances
        customer_instance = customer.objects.get(customer_id=customer_id)
        campus_instances = campus.objects.get(campus_id=campus_id)

        # Save the new campus
        submit_campus = customer_campus(
            customer_id=customer_instance,
            campus_id=campus_instances,
            customer_phone='',
            customer_fax='',
            change_user=request.user,
        )
        submit_campus.save()

        #Return the JSON data around the customer's new campus.
        response_data = {}
        response_data['customer_campus_id'] = submit_campus.customer_campus_id

        # Go to the form.
        return JsonResponse({'customer_campus_id': submit_campus.customer_campus_id})
    else:
        return HttpResponseBadRequest("Sorry, you can only do this in post.")



@login_required(login_url='login')
def admin_group(request,location_id,destination):
    # Load template
    t = loader.get_template('NearBeach/administration/admin_group.html')

    c = {}

    return HttpResponse(t.render(c,request))


@login_required(login_url='login')
def admin_permission_set(request, group_id):
    """
    Admin permission set will render a list of all permission set's connected to the current group. This admin def
    is only appliciable for the group functionality at the moment. Hence it only contains a "Group ID" as input

    If this is rendering for the group - it will allow users to add more permission sets to the group
    :param request:
    :param group_id: the primary key for the group
    :return: A rendered list of permissions

    Method
    ~~~~~~
    1. Check the user permissions
    2. If post - go through post. Check comments here
    3. Get data for permission sets connected to this group
    4. Render the template :) and return results to user
    """

    # Check user permission
    permission_results = return_user_permission_level(request, [None], ['administration_create_group'])

    if permission_results['administration_create_group'] <= 1:
        # Send them to permission denied!!
        return HttpResponseRedirect(reverse(permission_denied))

    if request.method == "POST" and permission_results['administration_create_group'] >= 3:
        form = add_permission_set_to_group_form(
            request.POST,
            group_id=group_id,
        )
        if form.is_valid():
            group_permission_submit=group_permission(
                group_id=group_id,
                permission_set=form.cleaned_data['add_permission_set'],
                change_user=request.user,
            )
            group_permission_submit.save()
        else:
            print(form.errors)


    permission_set_results = group_permission.objects.filter(
        is_deleted="FALSE",
        group_id=group_id,
    )


    # Load template
    t = loader.get_template('NearBeach/administration/admin_permission_set.html')

    c = {
        'permission_set_results': permission_set_results,
        'add_permission_set_to_group_form': add_permission_set_to_group_form(group_id=group_id),
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def admin_add_user(request, group_id):
    """
    Pulls up a list of users for the group information. This def shows a list and grants you the ability to add new users
    to a group.

    Please note - as a user can have multiple permission sets per group, it does not restrict duplications.
    :param request:
    :param group_id: The group ID we are looking at
    :return: HTML

    Method
    ~~~~~~
    1. Check permissions
    2. If post - do post method - more comments here
    3. Obtain information like users already assigned to the group
    4. Render webpage
    """
    # Check user permission
    permission_results = return_user_permission_level(request, [None], ['administration_create_group'])

    if permission_results['administration_create_group'] <= 1:
        # Send them to permission denied!!
        return HttpResponseRedirect(reverse(permission_denied))

    if request.method == "POST":
        form = add_user_to_group_form(
            request.POST,
            group_id=group_id,
        )
        if form.is_valid():
            user_group_submit = user_group(
                username=form.cleaned_data['add_user'],
                group=group.objects.get(group_id=group_id),
                permission_set=form.cleaned_data['permission_set'],
                change_user=request.user,
            )
            user_group_submit.save()
        else:
            print(form.errors)

    # Get data
    user_group_results = user_group.objects.filter(
        is_deleted="FALSE",
        group_id=group_id,
    )

    # Load template
    t = loader.get_template('NearBeach/administration/admin_user.html')

    c = {
        'add_user_to_group_form': add_user_to_group_form(group_id=group_id),
        'administration_permission': permission_results['administration'],
        'user_group_results': user_group_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def alerts(request):
    """
    Alerts are shown after the user logs in with any outstanding objects, i.e. Projects that have end dates in the past.
    :param request:
    :return: Returns a web page of alerts

    Method
    ~~~~~~
    1. get the compare date, that is 24 hours into the future.
    2. filter projects, tasks, opportunity, and quotes. The filters will be if they are still active (not completed or resolved)
        and if the end date is less than or equal to the campare time.
    3. If there are no results for any of the objects - redirect to dashboard
    4. Loaad the alerts page.
    """
    compare_time = datetime.datetime.now() + datetime.timedelta(hours=24)

    #Get SQL Data for each object
    project_results = project.objects.filter(
        is_deleted="FALSE",
        project_id__in=object_assignment.objects.filter(
            is_deleted="FALSE",
            project_id__isnull=False,
            assigned_user=request.user,
        ).values('project_id'),
        project_end_date__lte=compare_time,
        project_status__in={'New','Open'},
    )

    task_results = task.objects.filter(
        is_deleted="FALSE",
        task_id__in=object_assignment.objects.filter(
            is_deleted="FALSE",
            task_id__isnull=False,
            assigned_user=request.user,
        ).values('task_id'),
        task_end_date__lte=compare_time,
        task_status__in={'New','Open'},
    )

    opportunity_results = opportunity.objects.filter(
        is_deleted="FALSE",
        opportunity_id__in=object_assignment.objects.filter(
            is_deleted="FALSE",
            assigned_user=request.user,
        ).values('opportunity_id'),
        opportunity_expected_close_date__lte=compare_time,
        opportunity_stage_id__in=list_of_opportunity_stage.objects.filter(
            opportunity_closed="FALSE",
        ).values('opportunity_stage_id'),
    )


    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        quote_stage_id__in=list_of_quote_stage.objects.filter(
            quote_closed="FALSE",
        ).values('quote_stage_id'),
        quote_valid_till__lte=compare_time,
    )

    #If there is no data for every object, lets go to the dashboard... because there are no alerts :)
    if not project_results and not task_results and not opportunity_results and not quote_results:
        #There are no alerts, just redirect to dashboard
        return HttpResponseRedirect(reverse('dashboard'))

    # Load the template
    t = loader.get_template('NearBeach/alerts.html')

    # context
    c = {
        'project_results': project_results,
        'task_results': task_results,
        'opportunity_results': opportunity_results,
        'quote_results': quote_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def assign_customer_project_task(request, customer_id):
    """
    This allows the user to allocate multiple projects/tasks to a customer in a single search.
    :param request:
    :param customer_id: The customer's id
    :return: Redirect to the customer's information page

    Method
    ~~~~~~
    1. Check current users permission - are they allowed to do this. If not, send them away
    2. If request is post - create a new row for each project/tasks assigned to the user (read comments in section)
    3. If request is not post - get project/task/customer infromation
    4. Render the page
    """

    #Checking user permission
    user_group_results = user_group.objects.filter(
        is_deleted="FALSE",
        username=request.user.id,
    ).values('group_id')

    permission_results = return_user_permission_level(request, user_group_results, ['task','project'])

    if permission_results['task'] <= 1 or permission_results['project'] <= 1:
        # Send them to permission denied!!
        return HttpResponseRedirect(reverse(permission_denied))

    if request.POST:
        #Get required data from POST - in this case we want to get the list... getlist... getit?
        assign_projects = request.POST.getlist('project_checkbox')
        assign_task = request.POST.getlist('task_checkbox')

        # Instance
        customer_instance = customer.objects.get(customer_id=customer_id)

        """
		We will now assign these projects and task in bulk to the customer.
		This is done in a simple look. It will loop through the data obtained in post
		"""
        for row in assign_projects:
            #Get the project instance
            project_instance = project.objects.get(project_id=row)

            # Project customer - linking projects to customers.
            project_customer_submit = project_customer(
                project_id=project_instance,
                customer_id=customer_instance,
                change_user=request.user,
                # Customer description will have to be programmed in at a later date
            )
            if not project_customer_submit.save():
                print("Error saving")

        """
        Assign the task to a customer by looking through the results submitted through in POST.
        It will look through each submitted option and add them to the task_customer table.
        """
        for row in assign_task:
            #get the task instance
            task_instance = task.objects.get(task_id=row)

            task_customer_submit = task_customer(
                task_id=task_instance,
                customer_id=customer_instance,
                change_user=request.user,
            )
            task_customer_submit.save()

        # Now return to the customer's information
        return HttpResponseRedirect(reverse('customer_information', args={customer_id}))

    # Get Data
    customer_results = customer.objects.get(customer_id=customer_id)

    """
    Projects need to be
    -- NOT DELETED
    -- User has access to the project via groups
    -- Projects need to be either NEW or OPEN
    """
    project_results = project.objects.filter(
        is_deleted="FALSE",
        project_status__in=('New','Open'),
        project_id__in=object_assignment.objects.filter(
            is_deleted="FALSE",
            group_id__in=user_group.objects.filter(
                is_deleted="FALSE",
                username_id = request.user.id,
            ).values('group_id')
        ).values('project_id')
    )

    """
    Tasks need to be
    -- NOT DELETED
    -- User has access to the project via groups
    -- Projects need to be either NEW or OPEN
    """
    task_results = task.objects.filter(
        is_deleted="FALSE",
        task_status__in=('New', 'Open'),
        task_id__in=object_assignment.objects.filter(
            is_deleted="FALSE",
            group_id__in=user_group.objects.filter(
                is_deleted="FALSE",
                username_id= request.user.id,
            ).values('group_id')
        ).values('task_id')
    )

    # Load the template
    t = loader.get_template('NearBeach/assign_customer_project_task.html')

    # context
    c = {
        'project_results': project_results,
        'task_results': task_results,
        'customer_results': customer_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def assigned_group_add(request, location_id, destination):
    """

    :param request:
    :param location_id:
    :param destination:
    :return:
    """
    if request.method == "POST":
        form = assign_group_add_form(
            request.POST,
            location_id=location_id,
            destination=destination,
        )
        if form.is_valid():
            if destination == "project":
                object_assignment_submit = object_assignment(
                    project_id=project.objects.get(project_id=location_id),
                    group_id=form.cleaned_data['add_group'],
                    change_user=request.user,
                )
            elif destination == "task":
                object_assignment_submit = object_assignment(
                    task_id=task.objects.get(task_id=location_id),
                    group_id=form.cleaned_data['add_group'],
                    change_user=request.user,
                )
            elif destination == "requirement":
                object_assignment_submit = object_assignment(
                    requirement_id=requirement.objects.get(requirement_id=location_id),
                    group_id = form.cleaned_data['add_group'],
                    change_user = request.user,
                )
            elif destination == "quote":
                object_assignment_submit = object_assignment(
                    quote_id=quote.objects.get(quote_id=location_id),
                    group_id=form.cleaned_data['add_group'],
                    change_user=request.user,
                )
            elif destination == "kanban_board":
                object_assignment_submit = object_assignment(
                    kanban_board_id=kanban_board.objects.get(kanban_board_id=location_id),
                    group_id=form.cleaned_data['add_group'],
                    change_user=request.user,
                )
            elif destination == "opportunity":
                object_assignment_submit = object_assignment(
                    opportunity_id=opportunity.objects.get(opportunity_id=location_id),
                    group_id=form.cleaned_data['add_group'],
                    change_user=request.user,
                )
            object_assignment_submit.save()


        else:
            print(form.errors)

    # Load the template
    t = loader.get_template('NearBeach/assigned_groups/assigned_groups_add.html')

    # context
    c = {
        'assign_group_add_form': assign_group_add_form(
            location_id=location_id,
            destination=destination,
        )
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def assigned_group_delete(request, object_assignment_id):
    """
    assigned group delete will delete an assigned group against an object. Please note this has to be through
    POST. This is a security measure
    """
    if request.method == "POST":
        object_assignment_update = object_assignment.objects.get(object_assignment_id=object_assignment_id)
        object_assignment_update.is_deleted = "TRUE"
        object_assignment_update.save()

        #Load blank page and send back
        t = loader.get_template('NearBeach/blank.html')

        c = {}

        return HttpResponse(t.render(c, request))
    else:
        return HttpResponseBadRequest("Action can only be done through POST")




@login_required(login_url='login')
def assigned_group_list(request, location_id, destination):
    if destination == "project":
        group_list_results = object_assignment.objects.filter(
            is_deleted="FALSE",
            project_id = location_id
        ).exclude(
            group_id=None,
        )
    elif destination=="task":
        group_list_results = object_assignment.objects.filter(
            is_deleted="FALSE",
            task_id=location_id,
        ).exclude(
            group_id=None,
        )
    elif destination == "requirement":
        group_list_results = object_assignment.objects.filter(
            is_deleted="FALSE",
            requirement_id=location_id,
        ).exclude(
            group_id=None,
        )
    elif destination == "quote":
        group_list_results = object_assignment.objects.filter(
            is_deleted="FALSE",
            quote_id=location_id,
        ).exclude(
            group_id=None,
        )
    elif destination == "kanban_board":
        group_list_results = object_assignment.objects.filter(
            is_deleted="FALSE",
            kanban_board_id=location_id,
        ).exclude(
            group_id=None,
        )
    elif destination == "opportunity":
        group_list_results = object_assignment.objects.filter(
            is_deleted="FALSE",
            opportunity_id=location_id,
        ).exclude(
            group_id=None,
        )
    else:
        group_list_results = ''

    # Load the template
    t = loader.get_template('NearBeach/assigned_groups/assigned_groups_list.html')

    # context
    c = {
        'group_list_results': group_list_results,
        'destination': destination
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def assigned_user_add(request, location_id, destination):
    """
    We want the ability for the User to grant permission to anyone. For example, if a group owns this requirement,
    however we need someone from a different group, i.e. IT, then we can assign them to this requirement as a
    permission and they should be able to access it.
    """
    if request.method == "POST":
        form = assign_user_add_form(
            request.POST,
            location_id=location_id,
            destination=destination,
        )
        if form.is_valid():
            if destination == "project":
                object_assignment_submit = object_assignment(
                    project_id=project.objects.get(project_id=location_id),
                    assigned_user=form.cleaned_data['add_user'],
                    change_user=request.user,
                )
                object_assignment_submit.save()
            elif destination == "task":
                object_assignment_submit = object_assignment(
                    task_id=task.objects.get(task_id=location_id),
                    assigned_user=form.cleaned_data['add_user'],
                    change_user=request.user,
                )
                object_assignment_submit.save()
            elif destination == "requirement":
                object_assignment_submit = object_assignment(
                    requirement_id=requirement.objects.get(requirement_id=location_id),
                    assigned_user=form.cleaned_data['add_user'],
                    change_user=request.user,
                )
                object_assignment_submit.save()
            elif destination == "quote":
                object_assignment_submit = object_assignment(
                    quote_id=quote.objects.get(quote_id=location_id),
                    assigned_user=form.cleaned_data['add_user'],
                    change_user=request.user,
                )
                object_assignment_submit.save()
            elif destination == "kanban_board":
                object_assignment_submit = object_assignment(
                    kanban_board_id=kanban_board.objects.get(kanban_board_id=location_id),
                    assigned_user=form.cleaned_data['add_user'],
                    change_user=request.user,
                )
                object_assignment_submit.save()
            elif destination == "opportunity":
                object_assignment_submit = object_assignment(
                    opportunity_id=opportunity.objects.get(opportunity_id=location_id),
                    assigned_user=form.cleaned_data['add_user'],
                    change_user=request.user,
                )
                object_assignment_submit.save()
        else:
            print(form.errors)

    # Load the template
    t = loader.get_template('NearBeach/assigned_users/assigned_user_add.html')

    # context
    c = {
        'assign_user_add_form': assign_user_add_form(
            location_id=location_id,
            destination=destination,
        )
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def assigned_user_delete(request, object_assignment_id):
    if request.method == "POST":
        object_assignment_update = object_assignment.objects.get(object_assignment_id=object_assignment_id)
        object_assignment_update.change_user=request.user
        object_assignment_update.is_deleted="TRUE"
        object_assignment_update.save()


        #Return blank back
        t = loader.get_template('NearBeach/blank.html')
        c = {}
        return HttpResponse(t.render(c, request))
    else:
        return HttpResponseBadRequest("Sorry - can only do this in POST")



@login_required(login_url='login')
def assigned_user_list(request, location_id, destination):
    permission_results = return_user_permission_level(request, None, destination)

    # Get SQL
    if destination == 'project':
        assigned_user_results = object_assignment.objects.filter(
            is_deleted="FALSE",
            project_id=location_id,
        ).exclude(
            assigned_user =None,
        )
    elif destination == 'task':
        assigned_user_results = object_assignment.objects.filter(
            is_deleted="FALSE",
            task_id=location_id,
        ).exclude(
            assigned_user =None,
        )
    elif destination == 'requirement':
        assigned_user_results = object_assignment.objects.filter(
            is_deleted="FALSE",
            requirement_id=location_id,
        ).exclude(
            assigned_user =None,
        )
    elif destination == 'quote':
        assigned_user_results = object_assignment.objects.filter(
            is_deleted="FALSE",
            quote_id=location_id,
        ).exclude(
            assigned_user =None,
        )
    elif destination == 'opportunity':
        assigned_user_results = object_assignment.objects.filter(
            is_deleted="FALSE",
            opportunity_id=location_id,
        ).exclude(
            assigned_user =None,
        )
    else:
        assigned_user_results = ''

    # Load the template
    t = loader.get_template('NearBeach/assigned_users/assigned_user_list.html')

    # context
    c = {
        'assigned_user_results': assigned_user_results,
        'permissions': permission_results[destination],
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def associate(request, project_id, task_id, project_or_task):
    # Submit the data
    submit_result = project_task(
        project_id_id=project_id,
        task_id_id=task_id,
        change_user=request.user,
    )
    submit_result.save()

    # Once we assign them together, we go back to the original
    if project_or_task == "P":
        return HttpResponseRedirect(reverse('project_information', args={project_id}))
    else:
        return HttpResponseRedirect(reverse('task_information', args={task_id}))



@login_required(login_url='login')
def associated_projects(request, task_id):
    """
	We want the ability for the user to assign any project to the current
	task that their group owns. The user will have the ability to
	check to see if they want only new or open, or if they would like
	to see closed task too.
	"""
    task_groups_results = object_assignment.objects.filter(
        is_deleted="FALSE",
        task_id=task_id,
    ).values('group_id_id')

    permission_results = return_user_permission_level(request, task_groups_results, ['task'])

    if permission_results['task'] == 0:
        # Send them to permission denied!!
        return HttpResponseRedirect(reverse(permission_denied))

    #Get required data
    projects_results = project.objects.filter(
        is_deleted="FALSE",
        project_status__in={'New', 'Open'}
    )

    # Load the template
    t = loader.get_template('NearBeach/associated_project.html')

    # context
    c = {
        'projects_results': projects_results,
        'task_id': task_id,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def associated_task(request, project_id):
    """
	We want the ability for the user to assign any task to the current
	project that their group owns. The user will have the ability to
	check to see if they want only new or open, or if they would like
	to see closed task too.
	"""
    project_groups_results = object_assignment.objects.filter(
        is_deleted="FALSE",
        project_id=project.objects.get(project_id=project_id),
    ).values('group_id_id')


    permission_results = return_user_permission_level(request, project_groups_results,['project'])

    if permission_results['project'] == 0:
        # Send them to permission denied!!
        return HttpResponseRedirect(reverse(permission_denied))

    task_results = task.objects.filter(
        is_deleted="FALSE",
        task_status__in={'New','Open'}
    )

    # Load the template
    t = loader.get_template('NearBeach/associated_task.html')

    # context
    c = {
        'task_results': task_results,
        'project_id': project_id,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def bug_add(request,location_id, destination,bug_id, bug_client_id):
    #add permissions

    if request.method == "POST":
        """
        Method
        ~~~~~~
        1.) Bring in all the data we need via the URL :)
        2.) Extract the bug_client information - we will use this to contact the bug client server
        3.) Extract an up to date bug information. This is done here (even though it is slow), because at a 
            later date, we might require to gather more information about this bug. This will help.
        4.) Write the information collected VIA the JSON into the database :)
        5.) Notify the end user that this has occurred. This might be by changing the text from "ADD" to "ADDING..." to "ADDED :)"
        """

        #Get the bug client instance - we need to reload this
        bug_client_instance = bug_client.objects.get(
            bug_client_id=bug_client_id,
        )

        #https://bugzilla.nearbeach.org/rest/bug?id=12 example of bugzilla rest platform
        #Most of this will be stored in the database, so we can implement more bug clients simply. :) YAY
        url = bug_client_instance.bug_client_url + bug_client_instance.list_of_bug_client.bug_client_api_url + \
                'bug?id=' + bug_id # This will be implemented into the database as a field
        print(url)

        response = urlopen(url)
        json_data = json.load(response)

        #Save the bug
        bug_submit = bug(
            bug_client=bug_client_instance,
            bug_code=bug_id, #I could not have bug_id twice, so the bug's id becomes bug_code
            bug_description=str(json_data['bugs'][0]['summary']),
            bug_status=str(json_data['bugs'][0]['status']),
            change_user=request.user,
        )
        if destination=="project":
            bug_submit.project=project.objects.get(project_id=location_id)
        elif destination=="task":
            bug_submit.task = task.objects.get(task_id=location_id)
        else:
            bug_submit.requirement=requirement.objects.get(requirement_id=location_id)

        #Save the bug
        bug_submit.save()

        # Load the template
        t = loader.get_template('NearBeach/blank.html')

        # context
        c = {}

        return HttpResponse(t.render(c, request))

    else:
        return HttpResponseBadRequest("Only POST requests allowed")


@login_required(login_url='login')
def bug_client_delete(request, bug_client_id):
    permission_results = return_user_permission_level(request, None, 'bug_client')

    if request.method == "POST" and permission_results['bug_client'] == 4:
        bug_client_update = bug_client.objects.get(bug_client_id=bug_client_id)
        bug_client_update.is_deleted = "TRUE"
        bug_client_update.save()

        # Load the template
        t = loader.get_template('NearBeach/blank.html')

        # context
        c = {}

        return HttpResponse(t.render(c, request))

    else:
        return HttpResponseBadRequest("Only POST requests allowed")



@login_required(login_url='login')
def bug_client_information(request, bug_client_id):
    permission_results = return_user_permission_level(request, None, 'bug_client')

    if permission_results['bug_client'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))
    form_errors = ''
    if request.method == "POST":
        form = bug_client_form(request.POST)
        if form.is_valid():
            #Get required data
            bug_client_name = form.cleaned_data['bug_client_name']
            list_of_bug_client = form.cleaned_data['list_of_bug_client']
            bug_client_url = form.cleaned_data['bug_client_url']

            #Test the link first before doing ANYTHING!
            try:
                url = bug_client_url + list_of_bug_client.bug_client_api_url + 'version'
                print(url)
                response = urlopen(url)
                print("Response gotten")
                data = json.load(response)
                print("Got the JSON")

                bug_client_save = bug_client.objects.get(bug_client_id=bug_client_id)
                bug_client_save.bug_client_name = bug_client_name
                bug_client_save.list_of_bug_client = list_of_bug_client
                bug_client_save.bug_client_url = bug_client_url
                bug_client_save.change_user=request.user

                bug_client_save.save()
                return HttpResponseRedirect(reverse('bug_client_list'))
            except:
                form_errors = "Could not connect to the API"
                print("There was an error")


        else:
            print(form.errors)
            form_errors(form.errors)



    #Get Data
    bug_client_results = bug_client.objects.get(bug_client_id=bug_client_id)
    bug_client_initial = {
        'bug_client_name': bug_client_results.bug_client_name,
        'list_of_bug_client': bug_client_results.list_of_bug_client,
        'bug_client_url': bug_client_results.bug_client_url,
    }

    t = loader.get_template('NearBeach/bug_client_information.html')

    # context
    c = {
        'bug_client_form': bug_client_form(initial=bug_client_initial),
        'bug_client_id': bug_client_id,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'form_errors': form_errors,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def bug_client_list(request):
    permission_results = return_user_permission_level(request, None, 'bug_client')
    if permission_results['bug_client'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    #Get Data
    bug_client_results = bug_client.objects.filter(
        is_deleted='FALSE',
    )

    # Load the template
    t = loader.get_template('NearBeach/bug_client_list.html')

    # context
    c = {
        'bug_client_results': bug_client_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'bug_client_permission': permission_results['bug_client'],
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def bug_list(request, location_id=None, destination=None):
    #Add permissions later
    if destination == "project":
        bug_results = bug.objects.filter(
            is_deleted="FALSE",
            project=location_id,
        )
    elif destination == "task":
        bug_results = bug.objects.filter(
            is_deleted="FALSE",
            task=location_id,
        )
    elif destination == "requirement":
        bug_results = bug.objects.filter(
            is_deleted="FALSE",
            requirement=location_id,
        )
    else:
        bug_results = bug.objects.filter(
            is_deleted="FALSE",
        )

    # Load the template
    if destination == None:
        t = loader.get_template('NearBeach/bug_list.html')
    else:
        t = loader.get_template('NearBeach/bug_list_specific.html')

    # context
    c = {
        'bug_results': bug_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def bug_search(request, location_id=None, destination=None):
    #Do permissions later
    bug_results = None
    bug_client_id = None
    if request.method == "POST":
        form = bug_search_form(request.POST)
        if form.is_valid():
            #Get the bug client instance
            bug_client_instance = bug_client.objects.get(bug_client_id=form.data['list_of_bug_client'])
            bug_client_id = bug_client_instance.bug_client_id
            print(bug_client_instance)
            print(bug_client_id)

            #Get bugs ids that we want to remove
            if destination == "project":
                existing_bugs = bug.objects.filter(
                    is_deleted="FALSE",
                    project=location_id,
                    bug_client_id=bug_client_id,
                )
            elif destination == "task":
                existing_bugs = bug.objects.filter(
                    is_deleted="FALSE",
                    task=location_id,
                    bug_client_id=bug_client_id,
                )
            else:
                existing_bugs = bug.objects.filter(
                    is_deleted="FALSE",
                    requirement=location_id,
                    bug_client_id=bug_client_id,
                )
            #The values in the URL
            f_bugs = ''
            o_notequals = ''
            v_values =''

            #The for loop
            for idx, row in enumerate(existing_bugs):
                nidx = str(idx+1)
                f_bugs = f_bugs + "&f" + nidx + "=bug_id"
                o_notequals = o_notequals + "&o" + nidx + "=notequals"
                v_values = v_values + "&v" + nidx + "=" + str(row.bug_code)

            exclude_url = f_bugs + o_notequals + v_values


            url = bug_client_instance.bug_client_url \
                  + bug_client_instance.list_of_bug_client.bug_client_api_url \
                  + bug_client_instance.list_of_bug_client.api_search_bugs + form.cleaned_data['search'] \
                  + exclude_url

            print(url)
            response = urlopen(url)
            json_data = json.load(response)
            bug_results = json_data['bugs'] #This could change depending on the API

        else:
            print(form.errors)

    # Load the template
    t = loader.get_template('NearBeach/bug_search.html')

    # context
    c = {
        'bug_search_form': bug_search_form(request.POST or None),
        'bug_results': bug_results,
        'location_id': location_id,
        'destination': destination,
        'bug_client_id': bug_client_id,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def campus_information(request, campus_information):
    permission_results = return_user_permission_level(request, None, 'organisation_campus')

    if permission_results['organisation_campus'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    # Obtain data (before POST if statement as it is used insude)
    campus_results = campus.objects.get(pk=campus_information)

    if campus_results.campus_longitude == None:
        update_coordinates(campus_information)


    # If instance is in POST
    if request.method == "POST":
        # Other save button must have been pressed
        form = campus_information_form(request.POST)
        if form.is_valid():
            # Save all the data
            campus_results.campus_nickname = form.cleaned_data['campus_nickname']
            campus_results.campus_phone = form.cleaned_data['campus_phone']
            campus_results.campus_fax = form.cleaned_data['campus_fax']
            campus_results.campus_address1 = form.cleaned_data['campus_address1']
            campus_results.campus_address2 = form.cleaned_data['campus_address2']
            campus_results.campus_address3 = form.cleaned_data['campus_address3']
            campus_results.campus_suburb = form.cleaned_data['campus_suburb']
            campus_results.change_user=request.user

            campus_results.save()

            #Update co-ordinates
            update_coordinates(campus_information)

        if 'add_customer_submit' in request.POST:
            # Obtain the ID of the customer
            customer_results = int(request.POST.get("add_customer_select"))

            # Get the SQL Instances
            customer_instance = customer.objects.get(customer_id=customer_results)
            campus_instances = campus.objects.get(campus_id=campus_information)


            # Save the new campus
            submit_campus = customer_campus(
                customer_id=customer_instance,
                campus_id=campus_instances,
                customer_phone='',
                customer_fax='',
                change_user=request.user,
            )
            submit_campus.save()

            # Go to the form.
            return HttpResponseRedirect(reverse('customer_campus_information', args={submit_campus.customer_campus_id,'CAMP'}))


    # Get Data
    customer_campus_results = customer_campus.objects.filter(
        campus_id=campus_information,
        is_deleted='FALSE',
    )
    add_customer_results = customer.objects.filter(organisation_id=campus_results.organisation_id)
    countries_regions_results = list_of_country_region.objects.all()
    countries_results = list_of_country.objects.all()

    #Get one of the MAP keys
    MAPBOX_API_TOKEN = ''
    GOOGLE_MAP_API_TOKEN = ''

    if hasattr(settings, 'MAPBOX_API_TOKEN'):
        MAPBOX_API_TOKEN = settings.MAPBOX_API_TOKEN
        print("Got mapbox API token: " + MAPBOX_API_TOKEN)
    elif hasattr(settings, 'GOOGLE_MAP_API_TOKEN'):
        GOOGLE_MAP_API_TOKEN = settings.GOOGLE_MAP_API_TOKEN
        print("Got Google Maps API token: " + GOOGLE_MAP_API_TOKEN)


        # Load the template
    t = loader.get_template('NearBeach/campus_information.html')

    # context
    c = {
        'campus_results': campus_results,
        'campus_information_form': campus_information_form(
            instance=campus_results,
        ),
        'customer_campus_results': customer_campus_results,
        'add_customer_results': add_customer_results,
        'countries_regions_results': countries_regions_results,
        'countries_results': countries_results,
        'permission': permission_results['organisation_campus'],
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'MAPBOX_API_TOKEN': MAPBOX_API_TOKEN,
        'GOOGLE_MAP_API_TOKEN': GOOGLE_MAP_API_TOKEN,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def campus_readonly(request, campus_information):
    permission_results = return_user_permission_level(request, None, 'organisation_campus')

    if permission_results['organisation_campus'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    # Obtain data (before POST if statement as it is used insude)
    campus_results = campus.objects.get(pk=campus_information)

    if campus_results.campus_longitude == None:
        update_coordinates(campus_information)


    # Get Data
    customer_campus_results = customer_campus.objects.filter(
        campus_id=campus_information,
        is_deleted='FALSE',
    )
    add_customer_results = customer.objects.filter(organisation_id=campus_results.organisation_id)
    countries_regions_results = list_of_country_region.objects.all()
    countries_results = list_of_country.objects.all()

    #Get one of the MAP keys
    MAPBOX_API_TOKEN = ''
    GOOGLE_MAP_API_TOKEN = ''

    if hasattr(settings, 'MAPBOX_API_TOKEN'):
        MAPBOX_API_TOKEN = settings.MAPBOX_API_TOKEN
        print("Got mapbox API token: " + MAPBOX_API_TOKEN)
    elif hasattr(settings, 'GOOGLE_MAP_API_TOKEN'):
        GOOGLE_MAP_API_TOKEN = settings.GOOGLE_MAP_API_TOKEN
        print("Got Google Maps API token: " + GOOGLE_MAP_API_TOKEN)


        # Load the template
    t = loader.get_template('NearBeach/campus_readonly.html')

    # context
    c = {
        'campus_results': campus_results,
        'campus_readonly_form': campus_readonly_form(
            instance=campus_results,
        ),
        'customer_campus_results': customer_campus_results,
        'add_customer_results': add_customer_results,
        'countries_regions_results': countries_regions_results,
        'countries_results': countries_results,
        'permission': permission_results['organisation_campus'],
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'MAPBOX_API_TOKEN': MAPBOX_API_TOKEN,
        'GOOGLE_MAP_API_TOKEN': GOOGLE_MAP_API_TOKEN,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def cost_information(request, location_id, destination):
    if destination == "project":
        groups_results = object_assignment.objects.filter(
            is_deleted="FALSE",
            project_id=project.objects.get(project_id=location_id),
        ).values('group_id_id')
    else:
        groups_results = object_assignment.objects.filter(
            is_deleted="FALSE",
            task_id=task.objects.get(task_id=location_id),
        ).values('group_id_id')

    permission_results = return_user_permission_level(request, groups_results,destination)


    if request.method == "POST":
        form = cost_information_form(request.POST, request.FILES)
        if form.is_valid():
            cost_description = form.cleaned_data['cost_description']
            cost_amount = form.cleaned_data['cost_amount']
            if ((not cost_description == '') and ((cost_amount <= 0) or (cost_amount >= 0))):
                submit_cost = cost(
                    cost_description=cost_description,
                    cost_amount=cost_amount,
                    change_user=request.user,
                )
                if destination == "project":
                    submit_cost.project_id=project.objects.get(project_id=location_id)
                elif destination == "task":
                    submit_cost.task_id=task.objects.get(task_id=location_id)
                submit_cost.save()

    # Get data
    """
    Cost results and running total.
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Due to Django not having the ability to have a runnning total, I needed to extract all the costs and manually create
    the running total as a separate array. Now I need to combine both sets of data into one loop. To do that we use a 
    zip function to bring them together. Then we can just use a simple
    for a,b in zip_results
    """
    if destination == "project":
        costs_results = cost.objects.filter(project_id=location_id, is_deleted='FALSE')
    else:
        costs_results = cost.objects.filter(task_id=location_id, is_deleted="FALSE")

    # Get running totals
    running_total = []
    grand_total = 0  # use to calculate the grand total through the look
    for line_item in costs_results:
        grand_total = grand_total + float(line_item.cost_amount)
        running_total.append(grand_total)

    cost_zip_results = zip(costs_results, running_total)

    # Load template
    t = loader.get_template('NearBeach/costs.html')

    # context
    c = {
        'cost_information_form': cost_information_form(),
        'cost_zip_results': cost_zip_results,
        'cost_permissions': permission_results[destination],
        'grand_total': grand_total,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def customer_campus_information(request, customer_campus_id, customer_or_org):
    permission_results = return_user_permission_level(request, None, 'organisation_campus')

    if permission_results['organisation_campus'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    # IF method is post
    if request.method == "POST" and permission_results['organisation_campus'] > 1:
        form = customer_campus_form(request.POST)
        if form.is_valid():
            # Save the data
            save_data = customer_campus.objects.get(customer_campus_id=customer_campus_id)

            save_data.customer_phone = form.cleaned_data['customer_phone']
            save_data.customer_fax = form.cleaned_data['customer_fax']
            save_data.change_user=request.user

            save_data.save()

            """
			Now direct the user back to where they were from. The default
			will be the customer information
			"""
            if customer_or_org == "CAMP":
                return HttpResponseRedirect(reverse('campus_information', args={save_data.campus_id.campus_id}))
            else:
                return HttpResponseRedirect(reverse('customer_information', args={save_data.customer_id.customer_id}))

    # Get Data
    customer_campus_results = customer_campus.objects.get(customer_campus_id=customer_campus_id)
    campus_results = campus.objects.get(pk=customer_campus_results.campus_id.campus_id)


    # Setup the initial results
    initial = {
        'customer_phone': customer_campus_results.customer_phone,
        'customer_fax': customer_campus_results.customer_fax,
    }

    #Get the mapbox key
    if hasattr(settings, 'MAPBOX_API_TOKEN'):
        MAPBOX_API_TOKEN = settings.MAPBOX_API_TOKEN
        print("Got mapbox API token: " + MAPBOX_API_TOKEN)
    else:
        MAPBOX_API_TOKEN = ''

    #Get one of the MAP keys
    MAPBOX_API_TOKEN = ''
    GOOGLE_MAP_API_TOKEN = ''

    if hasattr(settings, 'MAPBOX_API_TOKEN'):
        MAPBOX_API_TOKEN = settings.MAPBOX_API_TOKEN
        print("Got mapbox API token: " + MAPBOX_API_TOKEN)
    elif hasattr(settings, 'GOOGLE_MAP_API_TOKEN'):
        GOOGLE_MAP_API_TOKEN = settings.GOOGLE_MAP_API_TOKEN
        print("Got Google Maps API token: " + GOOGLE_MAP_API_TOKEN)

    # Load template
    t = loader.get_template('NearBeach/customer_campus.html')

    # context
    c = {
        'customer_campus_form': customer_campus_form(initial=initial),
        'customer_campus_results': customer_campus_results,
        'customer_campus_id': customer_campus_id,
        'customer_or_org': customer_or_org,
        'permission': permission_results['organisation_campus'],
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'campus_results': campus_results,
        'MAPBOX_API_TOKEN': MAPBOX_API_TOKEN,
        'GOOGLE_MAP_API_TOKEN': GOOGLE_MAP_API_TOKEN,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def customer_information(request, customer_id):
    permission_results = return_user_permission_level(request, None,['assign_campus_to_customer','customer'])

    if permission_results['customer'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    #Redirect the user if they only have readonly mode
    if permission_results['customer'] == 1:
        return HttpResponseRedirect(reverse('customer_readonly', args = { customer_id }))

    if request.method == "POST" and permission_results['customer'] > 1:
        # Save everything!
        form = customer_information_form(request.POST, request.FILES)
        if form.is_valid():
            current_user = request.user
            # Save the data
            save_data = customer.objects.get(customer_id=customer_id)

            save_data.customer_title = form.cleaned_data['customer_title']
            save_data.customer_first_name = form.cleaned_data['customer_first_name']
            save_data.customer_last_name = form.cleaned_data['customer_last_name']
            save_data.customer_email = form.cleaned_data['customer_email']
            save_data.change_user=request.user

            # Check to see if the picture has been updated
            update_profile_picture = request.FILES.get('update_profile_picture')
            if not update_profile_picture == None:
                save_data.customer_profile_picture = update_profile_picture

            save_data.save()
        else:
            print(form.errors)

    # Get the instance
    customer_results = customer.objects.get(
        customer_id=customer_id,
        is_deleted="FALSE",
    )
    add_campus_results = campus.objects.filter(
        organisation_id=customer_results.organisation_id,
        is_deleted="FALSE",
    )
    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        customer_id=customer_id,
    )

    # Setup connection to the database and query it
    project_results = project.objects.filter(
        is_deleted="FALSE",
        project_id__in=project_customer.objects.filter(
            is_deleted="FALSE",
            customer_id=customer_id,
        ).values('project_id')
    )

    task_results = task.objects.filter(
        is_deleted="FALSE",
        task_id__in=task_customer.objects.filter(
            is_deleted="FALSE",
            customer_id=customer_id,
        ).values('task_id')
    )

    # The campus the customer is associated to
    """
    We need to limit the amount of opportunities to those that the user has access to.
    """
    user_groups_results = user_group.objects.filter(username=request.user)

    opportunity_permissions_results = object_assignment.objects.filter(
        Q(
            Q(assigned_user=request.user)  # User has permission
            | Q(group_id__in=user_groups_results.values('group_id'))  # User's group have permission
        )
    )
    opportunity_results = opportunity.objects.filter(
        customer_id=customer_id,
        opportunity_id__in=opportunity_permissions_results.values('opportunity_id')
    )
    #For when customer have an organisation
    campus_results = customer_campus.objects.filter(
        customer_id=customer_id,
        is_deleted='FALSE',
    )
    #For when customer do not have an organistion
    customer_campus_results = campus.objects.filter(
        is_deleted="FALSE",
        customer=customer_id,
    )


    try:
        profile_picture = customer_results.customer_profile_picture.url
    except:
        profile_picture = ''


    # load template
    t = loader.get_template('NearBeach/customer_information.html')

    # context
    c = {
        'customer_information_form': customer_information_form(
            instance=customer_results,
            ),
        'campus_results': campus_results,
        'customer_campus_results': customer_campus_results,
        'add_campus_results': add_campus_results,
        'customer_results': customer_results,
        'media_url': settings.MEDIA_URL,
        'profile_picture': profile_picture,
        'project_results': project_results,
        'task_results': task_results,
        'opportunity_results': opportunity_results,
        'PRIVATE_MEDIA_URL': settings.PRIVATE_MEDIA_URL,
        'customer_id': customer_id,
        'customer_permissions': permission_results['customer'],
        'assign_campus_to_customer_permission': permission_results['assign_campus_to_customer'],
        'quote_results':quote_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def customer_readonly(request,customer_id):
    permission_results = return_user_permission_level(request, None,['assign_campus_to_customer','customer'])

    if permission_results['customer'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    # Get the instance
    customer_results = customer.objects.get(
        customer_id=customer_id,
        is_deleted="FALSE",
    )
    add_campus_results = campus.objects.filter(
        organisation_id=customer_results.organisation_id,
        is_deleted="FALSE",
    )
    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        customer_id=customer_id,
    )

    # Setup connection to the database and query it
    project_results = project.objects.filter(
        is_deleted="FALSE",
        project_id__in=project_customer.objects.filter(
            is_deleted="FALSE",
            customer_id=customer_id,
        ).values('project_id')
    )

    task_results = task.objects.filter(
        is_deleted="FALSE",
        task_id__in=task_customer.objects.filter(
            is_deleted="FALSE",
            customer_id=customer_id,
        ).values('task_id')
    )

    contact_history_results = contact_history.objects.filter(
        is_deleted="FALSE",
        customer_id=customer_id,
    )

    """
    We want to bring through the project history's tinyMCE widget as a read only. However there are 
    most likely multiple results so we will create a collective.
    """
    contact_history_collective = []
    for row in contact_history_results:
        # First deal with the datetime
        contact_history_collective.append(
            contact_history_readonly_form(
                initial={
                    'contact_history': row.contact_history,
                    'submit_history': row.user_id.username + " - " + row.date_created.strftime("%d %B %Y %H:%M.%S"),
                },
                contact_history_id=row.contact_history_id,
            ),
        )

    email_results = email_content.objects.filter(
        is_deleted="FALSE",
        email_content_id__in=email_contact.objects.filter(
            (
                    Q(to_customer=customer_id) |
                    Q(cc_customer=customer_id)
            ) &
            Q(is_deleted="FALSE") &
            Q(
                Q(is_private=False) |
                Q(change_user=request.user)
            )
        ).values('email_content_id')
    )
    # The campus the customer is associated to
    """
    We need to limit the amount of opportunities to those that the user has access to.
    """
    user_groups_results = user_group.objects.filter(username=request.user)

    opportunity_permissions_results = object_assignment.objects.filter(
        Q(
            Q(assigned_user=request.user)  # User has permission
            | Q(group_id__in=user_groups_results.values('group_id'))  # User's group have permission
        )
    )
    opportunity_results = opportunity.objects.filter(
        customer_id=customer_id,
        opportunity_id__in=opportunity_permissions_results.values('opportunity_id')
    )
    # For when customer have an organisation
    campus_results = customer_campus.objects.filter(
        customer_id=customer_id,
        is_deleted='FALSE',
    )
    # For when customer do not have an organistion
    customer_campus_results = campus.objects.filter(
        is_deleted="FALSE",
        customer=customer_id,
    )

    try:
        profile_picture = customer_results.customer_profile_picture.url
    except:
        profile_picture = ''

    # load template
    t = loader.get_template('NearBeach/customer_information/customer_readonly.html')

    # context
    c = {
        'customer_readonly_form': customer_readonly_form(
            instance=customer_results,
        ),
        'campus_results': campus_results,
        'customer_campus_results': customer_campus_results,
        'add_campus_results': add_campus_results,
        'customer_results': customer_results,
        'media_url': settings.MEDIA_URL,
        'profile_picture': profile_picture,
        'project_results': project_results,
        'task_results': task_results,
        'opportunity_results': opportunity_results,
        'PRIVATE_MEDIA_URL': settings.PRIVATE_MEDIA_URL,
        'customer_id': customer_id,
        'customer_permissions': permission_results['customer'],
        'assign_campus_to_customer_permission': permission_results['assign_campus_to_customer'],
        'quote_results': quote_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'contact_history_collective': contact_history_collective,
        'email_results': email_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard(request):
    permission_results = return_user_permission_level(request, None, 'project')

    # Load the template
    t = loader.get_template('NearBeach/dashboard.html')

    # context
    c = {
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))

@login_required(login_url='login')
def dashboard_active_projects(request):
    #Get Data
    assigned_users_results = object_assignment.objects.filter(
        is_deleted='FALSE',
        assigned_user=request.user,
        project_id__isnull=False,
    ).exclude(
        project_id__project_status='Resolved'
    ).exclude(
        project_id__project_status='Closed'
    ).values(
        'project_id__project_id',
        'project_id__project_name',
        'project_id__project_end_date',
        'project_id__project_start_date',
    ).distinct()


    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/active_projects.html')

    # context
    c = {
        'assigned_users_results': assigned_users_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard_active_quotes(request):
    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        quote_stage_id__in=list_of_quote_stage.objects.filter(
            #We do not want to remove any quote with deleted stage
            quote_closed="FALSE"
        ).values('quote_stage_id')
    )

    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/active_quotes.html')

    # context
    c = {
        'quote_results': quote_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard_active_requirement(request):
    requirement_results = requirement.objects.filter(
        is_deleted="FALSE",
        requirement_status__in=list_of_requirement_status.objects.filter(
            requirement_status_is_closed="FALSE"
            #Do not worry about deleted status. We want them to appear and hopefully the user will
            #update these requirement_status.
        ).values('requirement_status_id')
    )

    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/active_requirements.html')


    # context
    c = {
        'requirement_results': requirement_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard_active_task(request):
    # Get Data
    assigned_users_results = object_assignment.objects.filter(
        is_deleted='FALSE',
        assigned_user=request.user,
        task_id__isnull=False,
    ).exclude(
        task_id__task_status='Resolved'
    ).exclude(
        task_id__task_status='Completed'
    ).values(
        'task_id__task_id',
        'task_id__task_short_description',
        'task_id__task_end_date',
        'task_id__task_start_date',
    ).distinct()

    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/active_tasks.html')

    # context
    c = {
        'assigned_users_results': assigned_users_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard_group_active_projects(request):
    active_projects_results = project.objects.filter(
        is_deleted="FALSE",
        project_id__in=object_assignment.objects.filter(
            is_deleted="FALSE",
            group_id__in=user_group.objects.filter(
                is_deleted="FALSE",
                username_id=request.user.id
            ).values('group'),
        ).values('project_id'),
    )

    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/group_active_projects.html')

    # context
    c = {
        'active_projects_results': active_projects_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard_group_active_task(request):
    active_task_results = task.objects.filter(
        is_deleted="FALSE",
        task_id__in=object_assignment.objects.filter(
            is_deleted="FALSE",
            group_id__in=user_group.objects.filter(
                is_deleted="FALSE",
                username_id=request.user
            ).values('group_id')
        ).values('task_id')
    )

    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/group_active_tasks.html')

    # context
    c = {
        'active_task_results': active_task_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard_group_opportunities(request):
    active_group_opportunities = opportunity.objects.filter(
        is_deleted="FALSE",
        opportunity_id__in=object_assignment.objects.filter(
            is_deleted="FALSE",
            group_id__in=user_group.objects.filter(
                is_deleted="FALSE",
                username_id=request.user,
            ).values('group_id'),
        ).values('opportunity_id'),
    )

    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/group_opportunities.html')

    # context
    c = {
        'active_group_opportunities': active_group_opportunities,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def dashboard_opportunities(request):
    # Get username_id from User
    #current_user = request.user


    active_opportunities = opportunity.objects.filter(
        is_deleted="FALSE",
        opportunity_stage_id__in=list_of_opportunity_stage.objects.filter(
            opportunity_closed="FALSE",
        ),
        opportunity_id__in=object_assignment.objects.filter(
            Q(is_deleted="FALSE") and
            Q(
                Q(assigned_user=request.user) or
                Q(group_id__in=user_group.objects.filter(
                    username=request.user,
                    is_deleted="FALSE",
                ))
            )

        ).values('opportunity_id')
    )

    # Load the template
    t = loader.get_template('NearBeach/dashboard_widgets/opportunities.html')

    # context
    c = {
        'active_opportunities': active_opportunities,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def deactivate_campus(request, campus_id):
    if request.method == "POST":
        #Setting the campus as deleted
        campus_update = campus.objects.get(campus_id=campus_id)
        campus_update.is_deleted="TRUE"
        campus_update.save()

        #Deleting all customers connected with the campus
        #ModelClass.objects.filter(name='bar').update(name="foo")
        customer_campus.objects.filter(
            is_deleted="FALSE",
            campus_id=campus_id,
        ).update(is_deleted="TRUE")

        #Return blank page :)
        t = loader.get_template('NearBeach/blank.html')
        c = {}
        return HttpResponse(t.render(c,request))
    else:
        return HttpResponseBadRequest("Sorry, this request is only for POST")


@login_required(login_url='login')
def delete_campus_contact(request, customer_campus_id, cust_or_camp):
    """
    So... I will need to add in security to define IF a user can do this action
    """
    save_customer_campus = customer_campus.objects.get(pk=customer_campus_id)
    save_customer_campus.is_deleted = "TRUE"
    save_customer_campus.change_user = request.user
    save_customer_campus.save()

    if cust_or_camp=="CAMP":
        return HttpResponseRedirect(reverse('campus_information', args={save_customer_campus.campus_id.organisations_campus_id}))
    else:
        return HttpResponseRedirect(reverse('customer_information', args={save_customer_campus.customer_id.customer_id}))


@login_required(login_url='login')
def delete_cost(request, cost_id, location_id, project_or_task):
    # Delete the cost
    cost_save = cost.objects.get(pk=cost_id)
    cost_save.is_deleted = "TRUE"
    cost_save.change_user=request.user
    cost_save.save()

    # Once we assign them together, we go back to the original
    if project_or_task == "P":
        return HttpResponseRedirect(reverse('project_information', args={location_id}))
    else:
        return HttpResponseRedirect(reverse('task_information', args={location_id}))


@login_required(login_url='login')
def delete_group(request, group_id):
    """
    This will remove the group, and anyone connected to the group. Becareful - this is a sad function.
    :param request:
    :param group_id: The group we wish to delete
    :return: blank page

    Method
    ~~~~~~
    1. Check to see if the request is in POST - if not send user an error
    2. Check to see if the user has permission - if not, send them to the naughty corner
    3. Get the group using the group_id - set is_deleted to TRUE
    4. Filter user_group by the group_id
    5. Set the filtered user_group data field is_deleted to TRUE
    6. Return blank page
    """
    if request.method == "POST":
        #Check those user permissions
        permission_results = return_user_permission_level(request, None, 'administration_create_group')
        if permission_results['administration_create_group'] < 4:
            return HttpResponseBadRequest("You do not have permission to delete")

        #If group_id is 1, it means it is the admin. Fake delete by setting group_id = 0
        if group_id == 1 or group_id == '1':
            group_id = 0 #Shh, it will then do nothing :)group

        #Filter for the group - and then update is_deleted to TRUE
        group.objects.filter(
            group_id=group_id,
        ).update(
            is_deleted="TRUE",
        )

        #Filter for any user_group rows - then update is_deleted to TRUE
        user_group.objects.filter(
            is_deleted="FALSE",
            group_id=group_id,
        ).update(
            is_deleted="TRUE",
        )

        #Return a blank page
        t = loader.get_template('NearBeach/blank.html')
        c = {}
        return HttpResponse(t.render(c,request))
    else:
        return HttpResponseBadRequest("Sorry - can only be done in POST")



@login_required(login_url='login')
def delete_permission_set(request, permission_set_id):
    """
    This will remove a permission set along with any user_group's connected to this permission_set. Becareful
    :param request:
    :param permission_set_id: the permission set we are removing
    :return: blank page

    Method
    ~~~~~~
    1. Check to make sure it is in POST - otherwise throw error
    2. Check to make sure user has permission - otherwise throw error
    3. Get the permission_set using permission_set id - update is_deleted to TRUE
    4. Find all user_group rows connected with this permission_set - update is_deleted to True
    5. Return blank page
    """
    if request.method == "POST":
        #Check those user permissions
        permission_results = return_user_permission_level(request, None, 'administration_create_permission_set')
        if permission_results['administration_create_permission_set'] < 4:
            return HttpResponseBadRequest("You do not have permission to delete")

        #Get permission set and update
        permission_set.objects.filter(
            permission_set_id=permission_set_id
        ).update(
            is_deleted="TRUE",
        )

        #Update all user_groups connected to this permission set
        user_group.objects.filter(
            is_deleted="FALSE",
            permission_set_id=permission_set_id,
        ).update(
            is_deleted="TRUE",
        )

        #Send back blank page :)
        t = loader.get_template('NearBeach/blank.html')
        c = {}
        return HttpResponse(t.render(c,request))

    else:
        return HttpResponseBadRequest("Sorry - can only do this in POST")


@login_required(login_url='login')
def delete_tag(request,tag_id):
    """
    Delete tag will actually remove the tag and all it's assignments from the system.

    Only a user with a tag permission of 4 can do this task.

    :param request:
    :param tag_id: the tag to delete
    :return: blank page if successful

    Method
    ~~~~~~
    1. Check permissions - if use does not pass send them to the naughty corner
    2. Check to make sure is in POST - if not, return an error
    3. Delete the tag
    4. Delete the tag assignments
    5. Return a blank page
    """
    permission_results = return_user_permission_level(request,None,'tag')
    if permission_results['tag'] < 4:
        return HttpResponseForbidden

    if request.method == "POST":
        #Delete the tag
        update_tag = tag.objects.get(tag_id=tag_id)
        update_tag.is_deleted = "TRUE"
        update_tag.save()

        #Delete the tag assignments
        update_tag_assignment = tag_assignment.objects.filter(
            is_deleted="FALSE",
            tag_id=tag_id,
        ).update(
            is_deleted="TRUE",
        )

        #Return blank page
        t = loader.get_template('NearBeach/blank.html')
        c = {}
        return HttpResponse(t.render(c,request))
    else:
        return HttpResponseBadRequest("Sorry, this can only be done through POST")


@login_required(login_url='login')
def delete_tag_from_object(request, tag_id, location_id, destination):
    """
    If the user has permission, we will delete the tag from the current object location.

    Please note - a user might accidently type in the same tag multiple times. Hence we are just getting tag
    id, location_id and destination and removing ALL tags with the same id from this object location
    :param request:
    :param tag_id: the tag_id that we are removing
    :param location_id: location id for the object
    :param destination: the destination of the object
    :return:

    Method
    ~~~~~~
    1. Make sure is post
    2. Make sure user has permission to delete
    3. Filter for all tags in current destination and location
    4. Delete :)
    5. Send back blank page
    """

    if request.method == "POST":
        permission_results = return_user_permission_level(request, None, 'tag')
        if permission_results['tag'] < 4:
            return HttpResponseBadRequest("You do not have permission to delete")

        # Filter for all tags in current destination and location
        if destination == "project":
            tag_assignment_update=tag_assignment.objects.filter(
                is_deleted="FALSE",
                tag_id=tag_id,
                project_id=location_id,
            ).update(is_deleted="TRUE")
        elif destination == "task":
            tag_assignment_update = tag_assignment.objects.filter(
                is_deleted="FALSE",
                tag_id=tag_id,
                task_id=location_id,
            ).update(is_deleted="TRUE")
        elif destination == "opportunity":
            tag_assignment_update = tag_assignment.objects.filter(
                is_deleted="FALSE",
                tag_id=tag_id,
                opportunity_id=location_id,
            ).update(is_deleted="TRUE")
        elif destination == "requirement":
            tag_assignment_update = tag_assignment.objects.filter(
                is_deleted="FALSE",
                tag_id=tag_id,
                requirement_id=location_id,
            ).update(is_deleted="TRUE")

        #Return blank page
        t = loader.get_template('NearBeach/blank.html')

        c = {}

        return HttpResponse(t.render(c, request))
    else:
        return HttpResponseBadRequest("Sorry, this has to be done in POST")


@login_required(login_url='login')
def delete_user_permission(request, user_id, permission_set_id, group_id):
    """
    This function will remove all permission sets for a particular group and user.

    Users can be added to the same collections of { group, permission_set } multiple times. We will need to delete all of
    these.
    :param request:
    :param user_id: Which user we are focusing on
    :param permission_set_id: Which permission set
    :param group_id:  Which group
    :return:

    Method
    ~~~~~~
    1. Check to make sure command is in POST - if not error out
    2. Check to make sure user has permission to do this - if not error out
    3. Filter the user_group for the; user_id, permission_set_id, and group_id
    4. Apply "is_deleted='TRUE'" to the filtered object
    5. Return blank page :)
    """
    if request.method == "POST":
        #Check user permission
        permission_results = return_user_permission_level(request, [None], ['administration_create_group'])
        if not permission_results['administration_create_group'] == 4:
            return HttpResponseForbidden

        #Apply the filter and update is_deleted to TRUE
        user_group_update=user_group.objects.filter(
            is_deleted="FALSE",
            group_id=group_id,
            permission_set_id=permission_set_id,
            username_id=user_id,
        ).update(is_deleted="TRUE")

        # Return blank page
        t = loader.get_template('NearBeach/blank.html')
        c = {}
        return HttpResponse(t.render(c,request))

    else:
        return HttpResponseBadRequest("Sorry - can only do this in POST")


@login_required(login_url='login')
def diagnostic_information(request):
    permission_results = return_user_permission_level(request, None, "")

    # reCAPTCHA
    RECAPTCHA_PUBLIC_KEY = ''
    if hasattr(settings, 'RECAPTCHA_PUBLIC_KEY'):
        RECAPTCHA_PUBLIC_KEY = settings.RECAPTCHA_PUBLIC_KEY

    # Diagnostic Template
    t = loader.get_template('NearBeach/diagnostic_information.html')

    c = {
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'RECAPTCHA_PUBLIC_KEY': RECAPTCHA_PUBLIC_KEY,
        'diagnostic_test_document_upload_form': diagnostic_test_document_upload_form(),
    }

    return HttpResponse(t.render(c,request))



@login_required(login_url='login')
def diagnostic_test_database(request):
    """
    Ping the user's database. If there is an issue then report it
    """
    User.objects.filter(username=request.user)

    t = loader.get_template('NearBeach/blank.html')

    c = {}

    return HttpResponse(t.render(c,request))




@login_required(login_url='login')
def diagnostic_test_document_upload(request):
    """
    Upload user's document and send back a link to the document. Please note the document will be fetched using
    ajax so test for any issues
    """
    print("Sending in test")
    if request.method == "POST":
        print("Request is in post")
        if request.FILES == None:
            print("There was an error with the file")
            return HttpResponseBadRequest('File needs to be uploaded. Refresh the page and try again')

        # Get the file data
        print("Checking the file")
        file = request.FILES['document']

        # Data objects required
        print("Getting the filename string")
        filename = str(file)

        """
        File Uploads
        """
        print("Saving the document")
        document_save = document(
            document_description=filename,
            document=file,
            change_user=request.user,
        )
        document_save.save()

        print("Saving document permissions")
        document_permissions_save = document_permission(
            document_key=document_save,
            change_user=request.user,
        )
        document_permissions_save.save()

        #Time to send back the link to the user
        t = loader.get_template('NearBeach/diagnostic/test_document_download.html')

        c = {
            'document_key': document_save.document_key,
        }

        return HttpResponse(t.render(c,request))

    return HttpResponseBadRequest("Something went wrong")


@login_required(login_url='login')
def diagnostic_test_email(request):
    """
    Method
    ~~~~~~
    1.) Gather the required variables
    2.) Send an email to noreply@nearbeach.org
    3.) If the email fails at ANY point, send back an error
    4.) If the email works, send back a blank page
    """
    try:
        #Check variables
        EMAIL_HOST_USER = settings.EMAIL_HOST_USER
        EMAIL_BACKEND = settings.EMAIL_BACKEND
        EMAIL_USE_TLS = settings.EMAIL_USE_TLS
        EMAIL_HOST = settings.EMAIL_HOST
        EMAIL_PORT = settings.EMAIL_PORT
        EMAIL_HOST_USER = settings.EMAIL_HOST_USER
        EMAIL_HOST_PASSWORD = settings.EMAIL_HOST_PASSWORD

    except:
        #It failed. Send back an error
        return HttpResponseBadRequest("Variables have not been fully setup in settings.py")

    try:
        email = EmailMultiAlternatives(
            'NearBeach Diagnostic Test',
            'Ignore email - diagnostic test',
            settings.EMAIL_HOST_USER,
            ['donotreply@nearbeach.org'],
        )
        if not email.send():
            return HttpResponseBadRequest("Email did not send correctly.")
    except:
        return HttpResponseBadRequest("Email failed")

    # Diagnostic Template
    t = loader.get_template('NearBeach/blank.html')

    c = {
    }

    return HttpResponse(t.render(c,request))


@login_required(login_url='login')
def diagnostic_test_location_services(request):
    """
    Method
    ~~~~~~
    1.) Check to make sure MAPBOX keys are inplace
    2.) If exists, test keys
    3.) If pass, returns pass. If fails, return fail

    4.) Check to make sure GOOGLE keys are inplace
    5.) If exists, test keys
    6.) If pass, returns pass. If fails, return fail

    7.) No keys, return error
    """

    try:
        MAPBOX_API_TOKEN = settings.MAPBOX_API_TOKEN

        try:
            address_coded = urllib.parse.quote_plus("Flinders Street Melbourne")
            print(address_coded)

            url = "https://api.mapbox.com/geocoding/v5/mapbox.places/" + address_coded + ".json?access_token=" + settings.MAPBOX_API_TOKEN
            # response = urllib.urlopen(url)
            response = urllib.request.urlopen(url)
            data = json.loads(response.read())

            longatude = data["features"][0]["center"][0]
            latitude = data["features"][0]["center"][1]
            #It worked - now it will just leave
        except:
            return HttpResponseBadRequest("Sorry, could not contact Mapbox")
    except:
        try:
            google_maps = GoogleMaps(api_key=settings.GOOGLE_MAP_API_TOKEN)
            location = google_maps.search(location="Flinders Street Melbourne")
            first_location = location.first()

            #Save the data
            ongitude = first_location.lng
            latitude = first_location.lat
        except:
            return HttpResponseBadRequest("Could not contact Google Server")

    t = loader.get_template('NearBeach/blank.html')

    c = {}

    return HttpResponse(t.render(c,request))


@login_required(login_url='login')
def diagnostic_test_recaptcha(request):
    if request.method == "POST":
        """
        Method
        ~~~~~~
        1.) Check to make sure reCAPTCHA keys are inplace
        2.) If exists, test keys
        3.) If pass, returns pass. If fails, return fail
    
        4.) No keys, return error
        """
        # reCAPTCHA
        RECAPTCHA_PUBLIC_KEY = ''
        RECAPTCHA_PRIVATE_KEY = ''
        if hasattr(settings, 'RECAPTCHA_PUBLIC_KEY') and hasattr(settings, 'RECAPTCHA_PRIVATE_KEY'):
            RECAPTCHA_PUBLIC_KEY = settings.RECAPTCHA_PUBLIC_KEY
            RECAPTCHA_PRIVATE_KEY = settings.RECAPTCHA_PRIVATE_KEY
        else:
            #Getting data from settings file has failed.
            return HttpResponseBadRequest("Either RECAPTCHA_PUBLIC_KEY or RECAPTCHA_PRIVATE_KEY has not been correctly setup in your settings file.")

        """
        As the Google documentation states. I have to send the request back to
        the given URL. It gives back a JSON object, which will contain the
        success results.
    
        Method
        ~~~~~~
        1.) Collect the variables
        2.) With the data - encode the variables into URL format
        3.) Send the request to the given URL
        4.) The response will open and store the response from GOOGLE
        5.) The results will contain the JSON Object
        """
        recaptcha_response = request.POST.get('g-recaptcha-response')
        print("RECAPTCHA RESPONSE:" + str(recaptcha_response))
        url = 'https://www.google.com/recaptcha/api/siteverify'
        values = {
            'secret': RECAPTCHA_PRIVATE_KEY,
            'response': recaptcha_response
        }
        response = urlopen(url, urllib.parse.urlencode(values).encode('utf8'))
        result = json.load(response)

        print(result)

        # Check to see if the user is a robot. Success = human
        if not result['success']:
            return HttpResponseBadRequest("Failed recaptcha!\n" + str(result))

    t = loader.get_template('NearBeach/blank.html')

    c = {}

    return HttpResponse(t.render(c,request))


@login_required(login_url='login')
def email(request,location_id,destination):
    permission_results = return_user_permission_level(request, None, 'email')

    if permission_results['email'] < 2:
        return HttpResponseRedirect(reverse('permission_denied'))

    """
    organisation
    customer
    project
    task
    opportunity
    quote
    """
    if request.method == "POST":
        form = email_form(
            request.POST,
            location_id=location_id,
            destination=destination,
        )
        if form.is_valid():
            #Extract form data
            organisation_email = form.cleaned_data['organisation_email']
            email_quote = form.cleaned_data['email_quote']

            to_email = []
            cc_email = []
            bcc_email = []
            from_email = ''

            #Get the current user's email
            current_user = User.objects.get(id=request.user.id)

            if current_user.email == '':
                from_email = settings.EMAIL_HOST_USER
            else:
                from_email = current_user.email

            if organisation_email:
                to_email.append(organisation_email)

            for row in form.cleaned_data['to_email']:
                to_email.append(row.customer_email)

            for row in form.cleaned_data['cc_email']:
                cc_email.append(row.customer_email)

            for row in form.cleaned_data['bcc_email']:
                bcc_email.append(row.customer_email)

            email = EmailMultiAlternatives(
                form.cleaned_data['email_subject'],
                form.cleaned_data['email_content'],
                from_email,
                to_email,
                bcc_email,
                cc=cc_email,
                reply_to=['nearbeach@tpg.com.au'],
            )
            email.attach_alternative(form.cleaned_data['email_content'],"text/html")

            """
            If this is a quote and the email_quote is ticked, then we send the quote information
            """
            if email_quote == True:
                """
                Method
                ~~~~~~
                1.) Get quote instance to extract UUID
                2.) Get the template ID from form
                3.) Use the above information to get the PDF
                4.) Attach PDF
                """
                quote_results = quote.objects.get(quote_id=location_id)
                quote_template_id = request.POST.get('quote_template_description')
                print("Quote Template ID: " + str(quote_template_id))

                #Generating PDF
                url_path = "http://" + request.get_host() + "/preview_quote/" + str(quote_results.quote_uuid) + "/" + str(quote_template_id) + "/"
                print("URL LOCATION:")
                print(url_path)
                html = HTML(url_path)
                pdf_results = html.write_pdf()

                #Attach the PDF
                email.attach("Quote - " + str(quote_results.quote_id), pdf_results, 'application/pdf')


            email.send(fail_silently=False)



            """
            Once the email has been sent with no errors. Then we save the content. :)
            First create the content email
            Then apply who got sent the email.
            """
            print(email_content)
            email_content_submit=email_content(
                email_subject= form.cleaned_data['email_subject'],
                email_content=form.cleaned_data['email_content'],
                change_user=request.user,
                is_private=form.cleaned_data['is_private'],
            )
            email_content_submit.save()

            for row in form.cleaned_data['to_email']:
                email_contact_submit=email_contact(
                    email_content=email_content_submit,
                    to_customer=customer.objects.get(customer_id=row.customer_id),
                    change_user=request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()

            for row in form.cleaned_data['cc_email']:
                email_contact_submit = email_contact(
                    email_content=email_content_submit,
                    cc_customer=customer.objects.get(customer_id=row.customer_id),
                    change_user = request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()

            for row in form.cleaned_data['bcc_email']:
                email_contact_submit = email_contact(
                    email_content=email_content_submit,
                    bcc_customer=customer.objects.get(customer_id=row.customer_id),
                    change_user=request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()

            if destination == "organisation":
                email_contact_submit = email_contact(
                    email_content=email_content_submit,
                    organisation=organisation.objects.get(organisation_id=location_id),
                    change_user=request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()
            elif destination == "project":
                email_contact_submit = email_contact(
                    email_content=email_content_submit,
                    project=project.objects.get(project_id=location_id),
                    change_user=request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()
            elif destination == "task":
                email_contact_submit = email_contact(
                    email_content=email_content_submit,
                    task=task.objects.get(task_id=location_id),
                    change_user=request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()
            elif destination == "opportunity":
                email_contact_submit = email_contact(
                    email_content=email_content_submit,
                    opportunity=opportunity.objects.get(opportunity_id=location_id),
                    change_user=request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()
            elif destination == "quote":
                email_contact_submit = email_contact(
                    email_content=email_content_submit,
                    quotes=quote.objects.get(quote_id=location_id),
                    change_user=request.user,
                    is_private=form.cleaned_data['is_private'],
                )
                email_contact_submit.save()







            #Now go back where you came from
            if destination == "organisation":
                return HttpResponseRedirect(reverse('organisation_information', args={location_id}))
            elif destination == "customer":
                return HttpResponseRedirect(reverse('customer_information', args={location_id}))
            elif destination == "project":
                return HttpResponseRedirect(reverse('project_information', args={location_id}))
            elif destination == "task":
                return HttpResponseRedirect(reverse('task_information', args={location_id}))
            elif destination == "opportunity":
                return HttpResponseRedirect(reverse('opportunity_information', args={location_id}))
            elif destination == "quote":
                return HttpResponseRedirect(reverse('quote_information', args={location_id}))
            else:
                return HttpResponseRedirect(reverse('dashboard'))



        else:
            print("ERROR with email form.")
            print(form.errors)

    #Template
    t = loader.get_template('NearBeach/email.html')

    quote_template_results = ''

    #Initiate form
    if destination == "organisation":
        organisation_results = organisation.objects.get(organisation_id=location_id)
        initial = {
            'organisation_email': organisation_results.organisation_email,
        }
    elif destination == "customer":
        customer_results = customer.objects.get(
            is_deleted="FALSE",
            customer_id=location_id
        )
        initial = {
            'to_email': customer_results.customer_id,
        }
    elif destination == "project":
        customer_results = customer.objects.filter(
            customer_id__in=project_customer.objects.filter(
                is_deleted="FALSE",
                project_id=location_id,
            ).values('customer_id')
        )
        print(customer_results)
        initial = {
            'to_email': customer_results,
        }
    elif destination == "task":
        print("Selected TASK")
        task_results = task.objects.get(task_id=location_id)
        if task_results.organisation_id:
            customer_results = customer.objects.filter(
                is_deleted="FALSE",
                customer_id__in = task_customer.objects.filter(
                    is_deleted="FALSE",
                    task_id=location_id,
                ).values('customer_id')
            )
        else:
            customer_results = customer.objects.filter(
                customer_id__in=task_customer.objects.filter(
                    is_deleted="FALSE",
                    task_id=location_id,
                ).values('customer_id')
            )
        initial = {
            'to_email': customer_results,
        }
        print(customer_results)
    elif destination == "opportunity":
        customer_results = customer.objects.filter(
            Q(is_deleted="FALSE") &
            Q(
                Q(customer_id__in=opportunity.objects.filter(
                    is_deleted="FALSE",
                    opportunity_id=location_id,
                ).values('customer_id')) |
                Q(customer_id__in=customer.objects.filter(
                    is_deleted="FALSE",
                    organisation_id__in=opportunity.objects.filter(
                        opportunity_id=location_id
                    ).values('organisation_id')
                ).values('customer_id')
                )
            )
        )
        initial = {
            'to_email': customer_results,
        }

    elif destination == "quote":
        quote_template_results = quote_template.objects.filter(
            is_deleted="FALSE",
        )
        customer_results = customer.objects.filter(
            is_deleted="FALSE",
            customer_id__in=quote_responsible_customer.objects.filter(
                is_deleted="FALSE",
                quote_id=location_id,
            ).values('customer_id')
        )
        initial = {
            'to_email': customer_results,
        }
    else:
        print("Something went wrong")


    # context
    c = {
        'email_form': email_form(
            initial=initial,
            location_id=location_id,
            destination=destination,
        ),
        'destination': destination,
        'location_id': location_id,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'quote_template_results': quote_template_results,

    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def email_history(request,location_id,destination):
    permission_results = return_user_permission_level(request, None, 'email')

    #Get data
    if destination == "organisation":
        email_results = email_content.objects.filter(
            is_deleted="FALSE",
            email_content_id__in=email_contact.objects.filter(
                Q(is_deleted="FALSE") &
                Q(organisation_id=location_id) &
                Q(
                    Q(is_private=False) |
                    Q(change_user=request.user)
                )
            ).values('email_content_id')
        )
    elif destination == "customer":
        email_results = email_content.objects.filter(
            is_deleted="FALSE",
            email_content_id__in=email_contact.objects.filter(
                (
                        Q(to_customer=location_id) |
                        Q(cc_customer=location_id)
                ) &
                Q(is_deleted="FALSE") &
                Q(
                    Q(is_private=False) |
                    Q(change_user=request.user)
                )
            ).values('email_content_id')
        )
    elif destination == "project":
        email_results = email_content.objects.filter(
            is_deleted="FALSE",
            email_content_id__in=email_contact.objects.filter(
                Q(project=location_id) &
                Q(is_deleted="FALSE") &
                Q(
                    Q(is_private=False) |
                    Q(change_user=request.user)
                )
            ).values('email_content_id')
        )
    elif destination == "task":
        email_results = email_content.objects.filter(
            is_deleted="FALSE",
            email_content_id__in=email_contact.objects.filter(
                Q(task_id=location_id) &
                Q(is_deleted="FALSE") &
                Q(
                    Q(is_private=False) |
                    Q(change_user=request.user)
                )
            ).values('email_content_id')
        )
    elif destination == "opportunity":
        email_results = email_content.objects.filter(
            is_deleted="FALSE",
            email_content_id__in=email_contact.objects.filter(
                Q(opportunity_id=location_id) &
                Q(is_deleted="FALSE") &
                Q(
                    Q(is_private=False) |
                    Q(change_user=request.user)
                )
            ).values('email_content_id')
        )
    elif destination == "quote":
        email_results = email_content.objects.filter(
            is_deleted="FALSE",
            email_content_id__in=email_contact.objects.filter(
                Q(quotes=location_id) &
                Q(is_deleted="FALSE") &
                Q(
                    Q(is_private=False) |
                    Q(change_user=request.user)
                )
            ).values('email_content_id')
        )
    else:
        email_results = ''

    # Template
    t = loader.get_template('NearBeach/email_history.html')

    print(email_results)

    # context
    c = {
        'destination': destination,
        'location_id': location_id,
        'email_results': email_results,
        'email_permission': permission_results['email'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def email_information(request,email_content_id):
    permission_results = return_user_permission_level(request, None, 'email')

    if permission_results['email'] < 1:
        return HttpResponseRedirect(reverse('permission_denied'))

    email_content_results = email_content.objects.get(
        is_deleted="FALSE",
        email_content_id=email_content_id,
    )

    to_email_results = email_contact.objects.filter(
        is_deleted="FALSE",
        email_content_id=email_content_id,
        to_customer__isnull=False,
    )
    cc_email_results = email_contact.objects.filter(
        is_deleted="FALSE",
        email_content_id=email_content_id,
        cc_customer__isnull=False,
    )
    bcc_email_results = email_contact.objects.filter(
        is_deleted="FALSE",
        email_content_id=email_content_id,
        bcc_customer__isnull=False,
    )

    #Check to make sure it isn't private
    if email_content_results.is_private == True and not email_content_results.change_user == request.user:
        #The email is private and the user is not the original creator
        return HttpResponseRedirect(reverse('permission_denied'))

    initial = {
        'email_subject': email_content_results.email_subject,
        'email_content': email_content_results.email_content,
    }

    # Template
    t = loader.get_template('NearBeach/email_information.html')

    # context
    c = {
        'email_content_results': email_content_results,
        'email_information_form': email_information_form(initial=initial),
        'to_email_results': to_email_results,
        'cc_email_results': cc_email_results,
        'bcc_email_results': bcc_email_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],

    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def extract_quote(request, quote_uuid,quote_template_id):
    #Create the PDF
    url_path = "http://" + request.get_host() + "/preview_quote/" + quote_uuid + "/" + quote_template_id + "/"
    html = HTML(url_path)
    pdf_results = html.write_pdf()

    #Setup the response
    response = HttpResponse(pdf_results,content_type='application/pdf')
    response['Content-Disposition']='attachment; filename="NearBeach Quote.pdf"'

    return response


@login_required(login_url='login')
def group_information(request,group_id):
    """
    This def will bring up the group information page. If the user makes a change then it will apply those changes.
    This is assuming that the group_id is not the ADMINISTRATION page - because we do not want to change there AT ALL!!
    :param request:
    :param group_id:
    :return:
    """
    permission_results = return_user_permission_level(request, None,['administration'])

    if permission_results['administration'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))


    """
    If the group is the administration group, we do NOT want to load the form. Instead it will be blank. MWAHAHAHAH
    """
    group_results = group.objects.get(group_id=group_id)
    if group_id == 1 or group_id == '1': #1 is the administration account
        group_form_results = None
    else:
        group_form_results = group_form(
            group_id=group_id,
            initial={
                'group_name': group_results.group_name,
                'parent_group': group_results.parent_group,
        })

    # Get template
    t = loader.get_template('NearBeach/administration/group_information.html')

    # Context
    c = {
        'group_form': group_form_results,
        'group_id': group_id,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c,request))


@login_required(login_url='login')
def index(request):
    """
	The index page determines if a particular user has logged in. It will
	follow the following steps
	
	Method
	~~~~~~
	1.) If there is a user logged in, if not, send them to login
	2.) Find out if this user should be in the system, if not send them to
		invalid view
	3.) If survived this far the user will be sent to "Active Projects"
	"""
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse('login'))
    else:
        return HttpResponseRedirect(reverse('dashboard'))

    # Default
    return HttpResponseRedirect(reverse('login'))



@login_required(login_url='login')
def kanban_edit_card(request,kanban_card_id):
    kanban_card_results = kanban_card.objects.get(kanban_card_id=kanban_card_id)
    if (
        kanban_card_results.project
        or kanban_card_results.task
        or kanban_card_results.requirement
    ):
        linked_card = True
    else:
        linked_card = False


    permission_results = return_user_permission_level(request, None,['kanban','kanban_card','kanban_comment'])

    if permission_results['kanban'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))


    if request.method == "POST" and permission_results['kanban'] > 1:
        form = kanban_card_form(
            request.POST,
            kanban_board_id=kanban_card_results.kanban_board_id,
        )
        if form.is_valid():
            #Get required data
            kanban_card_instance = kanban_card.objects.get(kanban_card_id=kanban_card_id)
            current_user = request.user

            kanban_column_extract=form.cleaned_data['kanban_column']
            kanban_level_extract=form.cleaned_data['kanban_level']

            if linked_card == False:
                kanban_card_instance.kanban_card_text=form.cleaned_data['kanban_card_text']
            kanban_card_instance.kanban_column_id=kanban_column_extract.kanban_column_id
            kanban_card_instance.kanban_level_id =kanban_level_extract.kanban_level_id
            kanban_card_instance.save()

            #Comments section
            kanban_comment_extract = form.cleaned_data['kanban_card_comment']

            if not kanban_comment_extract == '':


                kanban_comment_submit = kanban_comment(
                    kanban_card_id=kanban_card_instance.kanban_card_id ,
                    kanban_comment=kanban_comment_extract,
                    user_id=current_user,
                    user_infomation=current_user.id,
                    change_user=request.user,
                )
                kanban_comment_submit.save()


            #Let's return the CARD back so that the user does not have to refresh
            t = loader.get_template('NearBeach/kanban/kanban_card_information.html')

            c = {
                'kanban_card_submit': kanban_comment_extract,
            }

        else:
            print(form.errors)
            HttpResponseBadRequest(form.errors)

    #Get data

    kanban_comment_results = kanban_comment.objects.filter(kanban_card_id=kanban_card_id)


    # Get template
    t = loader.get_template('NearBeach/kanban/kanban_edit_card.html')

    # context
    c = {
        'kanban_card_form': kanban_card_form(
            kanban_board_id=kanban_card_results.kanban_board_id,
            instance=kanban_card_results,
        ),
        'kanban_permission': permission_results['kanban'],
        'kanban_card_permission': permission_results['kanban_card'],
        'kanban_comment_permission': permission_results['kanban_comment'],
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'kanban_comment_results': kanban_comment_results,
        'kanban_card_id': kanban_card_id,
        'linked_card': linked_card,
        'kanban_card_results': kanban_card_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def kanban_edit_xy_name(request,location_id, destination):
    """
    This function is for editing both kanban column and level names.
    PERMISSIONS WILL NEED TO BE ADDED!
    """

    if destination == "column":
        kanban_xy_name = kanban_column.objects.get(kanban_column_id=location_id).kanban_column_name.encode('utf8')
    elif destination == "level":
        kanban_xy_name = kanban_level.objects.get(kanban_level_id=location_id).kanban_level_name.decode('utf8')
    else:
        kanban_xy_name = ''

    # load template
    t = loader.get_template('NearBeach/kanban/kanban_edit_xy_name.html')

    # context
    c = {
        'kanban_edit_xy_name_form': kanban_edit_xy_name_form(initial={
            'kanban_xy_name': kanban_xy_name,
        })
    }

    return HttpResponse(t.render(c, request))



def kanban_information(request,kanban_board_id):
    permission_results = return_user_permission_level(request, None,['kanban'])

    if permission_results['kanban'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    """
    Test User Access
    ~~~~~~~~~~~~~~~~
    A user who wants to access this Kanban Board will need to meet one of these two conditions
    1. They have an access to  a group whom has been granted access to this kanban board
    2. They are a super user (they should be getting access to all objects)
    """
    object_access = object_assignment.objects.filter(
        is_deleted="FALSE",
        kanban_board_id=kanban_board_id,
        group_id__in=user_group.objects.filter(
            is_deleted="FALSE",
            username=request.user,
        ).values('group_id')
    )
    if object_access.count() == 0 and not permission_results['administration'] == 4:
        return HttpResponseRedirect(reverse('permission_denied'))


    #Get the required information
    kanban_board_results = kanban_board.objects.get(kanban_board_id=kanban_board_id)

    """
    If this kanban is connected to a requirement then we need to send it to the 'kanban_requirement_information". This
    is due to the large difference between this kanban and the requirement's kanban board.
    """
    if kanban_board_results.requirement_id:
        return HttpResponseRedirect(reverse('kanban_requirement_information',args={kanban_board_id}))

    kanban_level_results = kanban_level.objects.filter(
        is_deleted="FALSE",
        kanban_board=kanban_board_id,
    ).order_by('kanban_level_sort_number')
    kanban_column_results = kanban_column.objects.filter(
        is_deleted="FALSE",
        kanban_board=kanban_board_id,
    ).order_by('kanban_column_sort_number')
    kanban_card_results = kanban_card.objects.filter(
        is_deleted="FALSE",
        kanban_board=kanban_board_id,
    ).order_by('kanban_card_sort_number')

    t = loader.get_template('NearBeach/kanban_information.html')

    # context
    c = {
        'kanban_board_id': kanban_board_id,
        'kanban_board_results': kanban_board_results,
        'kanban_level_results': kanban_level_results,
        'kanban_column_results': kanban_column_results,
        'kanban_card_results': kanban_card_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


def kanban_move_card(request,kanban_card_id,kanban_column_id,kanban_level_id):
    if request.method == "POST":
        kanban_card_result = kanban_card.objects.get(kanban_card_id=kanban_card_id)
        kanban_card_result.kanban_column_id = kanban_column.objects.get(kanban_column_id=kanban_column_id)
        kanban_card_result.kanban_level_id = kanban_level.objects.get(kanban_level_id=kanban_level_id)
        kanban_card_result.save()

        #Send back blank like a crazy person.
        t = loader.get_template('NearBeach/blank.html')

        # context
        c = {}

        return HttpResponse(t.render(c, request))
    else:
        return HttpResponseBadRequest("This request can only be through POST")


@login_required(login_url='login')
def kanban_list(request):
    permission_results = return_user_permission_level(request, None,['kanban'])

    if permission_results['kanban'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    kanban_board_results = kanban_board.objects.filter(
        is_deleted="FALSE",
    )

    t = loader.get_template('NearBeach/kanban_list.html')

    # context
    c = {
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'kanban_permission': permission_results['kanban'],
        'kanban_board_results': kanban_board_results,
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def kanban_new_card(request,kanban_board_id):
    permission_results = return_user_permission_level(request, None,['kanban'])

    if permission_results['kanban'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    if request.method == "POST":
        form = kanban_card_form(request.POST,kanban_board_id=kanban_board_id)
        if form.is_valid():
            kanban_column_results=form.cleaned_data['kanban_column']
            kanban_level_results=form.cleaned_data['kanban_level']

            #To add the card at the bottom of the pack, we first need to get the max value
            max_value_results = kanban_card.objects.filter(
                kanban_column=kanban_column_results.kanban_column_id,
                kanban_level=kanban_level_results.kanban_level_id,
            ).aggregate(Max('kanban_card_sort_number'))

            #In case it returns a none
            try:
                max_value = max_value_results['kanban_card_sort_number__max'] + 1
            except:
                max_value = 0

            kanban_card_submit = kanban_card(
                kanban_card_text=form.cleaned_data['kanban_card_text'],
                kanban_column=kanban_column_results,
                kanban_level=kanban_level_results,
                change_user=request.user,
                kanban_card_sort_number=max_value,
                kanban_board_id=kanban_board_id,
            )
            kanban_card_submit.save()

            #Let's return the CARD back so that the user does not have to refresh
            t = loader.get_template('NearBeach/kanban/kanban_card_information.html')

            c = {
                'kanban_card_submit': kanban_card_submit,
            }

            return HttpResponse(t.render(c, request))

        else:
            print(form.errors)


    kanban_column_results = kanban_column.objects.filter(kanban_board=kanban_board_id)
    kanban_level_results = kanban_level.objects.filter(kanban_board=kanban_board_id)

    t = loader.get_template('NearBeach/kanban/kanban_new_card.html')

    # context
    c = {
        'kanban_column_results': kanban_column_results,
        'kanban_level_results': kanban_level_results,
        'kanban_card_form': kanban_card_form(
            kanban_board_id=kanban_board_id,
        ),
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'kanban_board_id': kanban_board_id,
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def kanban_new_link(request,kanban_board_id,location_id='',destination=''):
    permission_results = return_user_permission_level(request, None,['kanban'])

    if permission_results['kanban'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    if request.method == "POST":
        form=kanban_new_link_form(
            request.POST,
            kanban_board_id=kanban_board_id,
        )
        if form.is_valid():
            #Check to make sure we have not connected the item before. If so, send them a band response
            if (
                    (kanban_card.objects.filter(project_id=location_id,is_deleted="FALSE") and destination == "project")
                    or (kanban_card.objects.filter(task_id=location_id,is_deleted="FALSE") and destination == "task")
                    or (kanban_card.objects.filter(requirement_id=location_id,is_deleted="FALSE") and destination == "requirement")
                ):
                #Sorry, this already exists
                return HttpResponseBadRequest("Card already exists") #How do we fix these for AJAX - send back an error message

            #Get form data
            kanban_column = form.cleaned_data['kanban_column']
            kanban_level = form.cleaned_data['kanban_level']

            # To add the card at the bottom of the pack, we first need to get the max value
            max_value_results = kanban_card.objects.filter(
                kanban_column=kanban_column.kanban_column_id,
                kanban_level=kanban_level.kanban_level_id,
            ).aggregate(Max('kanban_card_sort_number'))

            # In case it returns a none
            try:
                max_value = max_value_results['kanban_card_sort_number__max'] + 1
            except:
                max_value = 0

            #Start by creating the card
            kanban_card_submit = kanban_card(
                change_user=request.user,
                kanban_column = kanban_column,
                kanban_level = kanban_level,
                kanban_card_sort_number=max_value,
                kanban_board = kanban_board.objects.get(kanban_board_id=kanban_board_id)
            )

            #Get the instance, and the name
            if destination == "project":
                kanban_card_submit.project = project.objects.get(project_id=location_id)
                kanban_card_submit.kanban_card_text = "PRO" + location_id + " - " + kanban_card_submit.project.project_name
            elif destination == "task":
                kanban_card_submit.task = task.objects.get(task_id=location_id)
                kanban_card_submit.kanban_card_text = "TASK" + location_id + " - " + kanban_card_submit.task.task_short_description
            elif destination == "requirement":
                kanban_card_submit.requirement = requirement.objects.get(requirement_id=location_id)
                kanban_card_submit.kanban_card_text = "REQ" + location_id + " - " + kanban_card_submit.requirement.requirement_title
            else:
                #Oh no, something went wrong.
                return HttpResponseBadRequest("Sorry, that type of destination does not exist")

            kanban_card_submit.save()

            # Let's return the CARD back so that the user does not have to refresh
            t = loader.get_template('NearBeach/kanban/kanban_card_information.html')

            c = {
                'kanban_card_submit': kanban_card_submit,
            }

            return HttpResponse(t.render(c, request))
        else:
            print(form.errors)
            return HttpResponseBadRequest("BAD FORM")


    #Get data
    kanban_card_results = kanban_card.objects.filter(
        is_deleted="FALSE",
        kanban_board_id=kanban_board_id,
    )

    project_results = project.objects.filter(
        is_deleted="FALSE",
        project_status__in=('New','Open'),
    ).exclude(
        is_deleted="FALSE",
        project_id__in=kanban_card_results.filter(project_id__isnull=False).values('project_id')
    )
    task_results = task.objects.filter(
        is_deleted="FALSE",
        task_status__in=('New','Open'),
        task_id__in=kanban_card_results.filter(task_id__isnull=False).values('task_id')
    )
    requirement_results = requirement.objects.filter(
        is_deleted="FALSE",
        requirement_status_id__in=list_of_requirement_status.objects.filter(
            requirement_status_is_closed="FALSE",
        ).values('requirement_status_id')
    ).exclude(
        is_deleted="FALSE",
        requirement_id__in=kanban_card_results.filter(requirement_id__isnull=False).values('requirement_id')
    )

    t = loader.get_template('NearBeach/kanban/kanban_new_link.html')

    # context
    c = {
        'project_results': project_results,
        'task_results': task_results,
        'requirement_results': requirement_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'kanban_new_link_form': kanban_new_link_form(
            kanban_board_id=kanban_board_id
        )
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def kanban_properties(request,kanban_board_id):
    print("Kanban Properties")
    permission_results = return_user_permission_level(request, None,['kanban'])

    if permission_results['kanban'] < 4:
        return HttpResponseRedirect(reverse('permission_denied'))

    """
    If this requirement is connected to a requirement, then the user should NOT edit the properties, as it is a
    SET Designed module.
    """
    kanban_board_results = kanban_board.objects.get(kanban_board_id=kanban_board_id)
    if kanban_board_results.requirement:
        print("Sorry, can not edit these")
        return HttpResponseBadRequest("Sorry, but users are not permitted to edit a Requirement Kanban Board.")

    if request.method == "POST":
        received_json_data = json.loads(request.body)

        #Update title
        kanban_board_results.kanban_board_name = str(received_json_data["kanban_board_name"])
        kanban_board_results.save()

        #Update the sort order for the columns
        for row in range(0, received_json_data["columns"]["length"]):
            kanban_column_update = kanban_column.objects.get(kanban_column_id=received_json_data["columns"][str(row)]["id"])
            kanban_column_update.kanban_column_sort_number = row
            kanban_column_update.save()

        # Update the sort order for the columns
        for row in range(0, received_json_data["levels"]["length"]):
            kanban_level_update = kanban_level.objects.get(kanban_level_id=received_json_data["levels"][str(row)]["id"])
            kanban_level_update.kanban_level_sort_number = row
            kanban_level_update.save()

        #Return blank page
        t = loader.get_template('NearBeach/blank.html')
        c={}
        return HttpResponse(t.render(c, request))



    #Get SQL
    kanban_column_results = kanban_column.objects.filter(
        is_deleted="FALSE",
        kanban_board_id=kanban_board_id,
    ).order_by('kanban_column_sort_number')
    kanban_level_results = kanban_level.objects.filter(
        is_deleted="FALSE",
        kanban_board_id=kanban_board_id,
    ).order_by('kanban_level_sort_number')

    t = loader.get_template('NearBeach/kanban/kanban_properties.html')

    # context
    c = {
        'kanban_board_id': kanban_board_id,
        'kanban_column_results': kanban_column_results,
        'kanban_level_results': kanban_level_results,
        'kanban_board_results': kanban_board_results,
        'kanban_properties_form': kanban_properties_form(initial={
            'kanban_board_name': kanban_board_results.kanban_board_name,
        }),
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'permission': permission_results['kanban'],
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def kanban_requirement_information(request, kanban_board_id):
    permission_results = return_user_permission_level(request, None, ['kanban'])

    if permission_results['kanban'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    kanban_board_results = kanban_board.objects.get(kanban_board_id=kanban_board_id)

    """
    We have to make sure that this particular kanban_board IS actually connected to a requirement.
    """
    if not kanban_board_results.requirement_id:
        return HttpResponseRedirect(reverse('kanban_information', args={kanban_board_id}))


    """
    Test User Access
    ~~~~~~~~~~~~~~~~
    A user who wants to access this requirement board will need to meet one of these two conditions
    1. They have an access to  a group whom has been granted access to this requirement
    2. They are a super user (they should be getting access to all objects)
    """
    object_access = object_assignment.objects.filter(
        is_deleted="FALSE",
        requirement_id=kanban_board_results.requirement_id,
        group_id__in=user_group.objects.filter(
            is_deleted="FALSE",
            username=request.user,
        ).values('group_id')
    )
    if object_access.count() == 0 and not permission_results['administration'] == 4:
        return HttpResponseRedirect(reverse('permission_denied'))


    #Get requirement information and requirement_item information
    requirement_id = kanban_board_results.requirement_id
    requirement_results = requirement.objects.get(requirement_id=requirement_id)
    requirement_item_results = requirement_item.objects.filter(
        is_deleted="FALSE",
        requirement_id=requirement_id
    )
    item_status_results = list_of_requirement_item_status.objects.filter(
        is_deleted="FALSE",
    )

    t = loader.get_template('NearBeach/kanban_requirement_information.html')

    # context
    c = {
        'requirement_id': requirement_id,
        'requirement_results': requirement_results,
        'requirement_item_results': requirement_item_results,
        'item_status_results': item_status_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'permission': permission_results['kanban'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def kanban_requirement_item_update(request,requirement_item_id,status_id):
    if request.method == "POST":
        #Get instance of requirement item
        requirement_item_update = requirement_item.objects.get(requirement_item_id=requirement_item_id)

        #Update the requirement item's status
        requirement_item_update.requirement_item_status=list_of_requirement_item_status.objects.get(
            requirement_item_status_id=status_id,
        )

        #Save
        requirement_item_update.save()

        t = loader.get_template('NearBeach/blank.html')

        c = {}

        return HttpResponse(t.render(c,request))
    else:
        return HttpResponseBadRequest("Sorry, but this is a POST request only")



#No login needed - as it is aimed at external customers
def kudos_rating(request,kudos_key):
    if request.method == "POST":
        form = kudos_form(request.POST)
        if form.is_valid():
            #Save the kudos information
            kudos_update=kudos.objects.get(kudos_key=kudos_key)

            #Different fields to get data
            kudos_update.kudos_rating=form.cleaned_data['kudos_rating']
            kudos_update.improvement_note=form.cleaned_data['improvement_note']
            kudos_update.liked_note=form.cleaned_data['liked_note']
            kudos_update.change_user=request.user
            kudos_update.submitted_kudos="TRUE"

            #Save
            kudos_update.save()

            #Now go to thank you page
            t = loader.get_template('NearBeach/kudos_thank_you.html')

            c = {}

            return HttpResponse(t.render(c, request))
        else:
            print(form.errors)
            return HttpResponseBadRequest("Form had errors within it. It failed")

    #Get required data
    kudos_results = kudos.objects.get(kudos_key=kudos_key)
    project_results = project.objects.get(project_id=kudos_results.project_id)


    #If form has already been submitted, we take them to the thank you page. Other wise use the edited version
    if kudos_results.submitted_kudos == "TRUE":
        t = loader.get_template('NearBeach/kudos_read_only.html')
    else:
        t = loader.get_template('NearBeach/kudos_rating.html')

    c = {
        'kudos_form': kudos_form(
            initial={
                'project_description': project_results.project_description,
            }
        ),
        'kudos_key': kudos_key,
        'project_results': project_results,
    }

    return HttpResponse(t.render(c,request))


#No login needed - as it is aimed at external customers
def kudos_read_only(request,kudos_key):
    # Get required data
    kudos_results = kudos.objects.get(kudos_key=kudos_key)
    project_results = project.objects.get(project_id=kudos_results.project_id)

    t = loader.get_template('NearBeach/kudos_read_only.html')

    c = {
        'kudos_read_only_form': kudos_read_only_form(
            initial={
                'project_description': project_results.project_description,
                'improvement_note': kudos_results.improvement_note,
                'liked_note': kudos_results.liked_note,
            }
        ),
        'kudos_key': kudos_key,
        'kudos_results': kudos_results,
        'star_range': range(kudos_results.kudos_rating),
        'project_results': project_results,
    }

    return HttpResponse(t.render(c,request))


@login_required(login_url='login')
def list_of_tags(request):
    """
    List of tags will allow a user to configure all the tags currently in NearBeach. The user will be able to
    - Merge tags together
    - Delete tags
    - Rename tags
    - Create new tags
    :param request:
    :return: Page of tags

    Method
    ~~~~~~
    1. Check user permissions - if they are not allowed here send them to the naughty corner
    """

    # Get data
    tag_results = tag.objects.filter(
        is_deleted="FALSE",
    )

    # Template
    t = loader.get_template('NearBeach/tags/list_of_tags.html')

    # Context
    c = {
        'tag_results': tag_results,
    }

    return HttpResponse(t.render(c,request))


def login(request):
    """
	For some reason I can not use the varable "login_form" here as it is already being used.
	Instead I will use the work form.
	
	The form is declared at the start and filled with either the POST data OR nothing. If this
	process is called in POST, then the form will be checked and if it passes the checks, the
	user will be logged in.
	
	If the form is not in POST (aka GET) OR fails the checks, then it will create the form with
	the relevant errors.
	"""
    form = login_form(request.POST or None)
    print("LOGIN REQUEST")

    # reCAPTCHA
    RECAPTCHA_PUBLIC_KEY = ''
    RECAPTCHA_PRIVATE_KEY = ''
    if hasattr(settings, 'RECAPTCHA_PUBLIC_KEY') and hasattr(settings, 'RECAPTCHA_PRIVATE_KEY'):
        RECAPTCHA_PUBLIC_KEY = settings.RECAPTCHA_PUBLIC_KEY
        RECAPTCHA_PRIVATE_KEY = settings.RECAPTCHA_PRIVATE_KEY

    # POST
    if request.method == 'POST':
        print("POST")
        if form.is_valid():
            """
			Method
			~~~~~~
			1.) Collect the variables
			2.) IF reCAPTCHA is enabled, then process login through that
				statement
				IF it is not, proceed to verify login
			3.) If it all fails, it will just go back to the login screen.
			"""
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            print("DATA EXTRACTED")

            if hasattr(settings, 'RECAPTCHA_PUBLIC_KEY') and hasattr(settings, 'RECAPTCHA_PRIVATE_KEY'):
                """
				As the Google documentation states. I have to send the request back to
				the given URL. It gives back a JSON object, which will contain the
				success results.
				
				Method
				~~~~~~
				1.) Collect the variables
				2.) With the data - encode the variables into URL format
				3.) Send the request to the given URL
				4.) The response will open and store the response from GOOGLE
				5.) The results will contain the JSON Object
				"""
                recaptcha_response = request.POST.get('g-recaptcha-response')
                url = 'https://www.google.com/recaptcha/api/siteverify'
                values = {
                    'secret': RECAPTCHA_PRIVATE_KEY,
                    'response': recaptcha_response
                }
                response = urlopen(url, urllib.parse.urlencode(values).encode('utf8'))
                result = json.load(response)

                print(result)

                # Check to see if the user is a robot. Success = human
                if result['success']:
                    user = auth.authenticate(username=username, password=password)
                    auth.login(request, user)

            else:
                user = auth.authenticate(username=username, password=password)
                auth.login(request, user)

                #is_admin(request)

            # Just double checking. :)
            if request.user.is_authenticated:
                print("User Authenticated")
                """
                The user has been authenticated. Now the system will store the user's permissions and group 
                into cookies. :)
                
                First Setup
                ~~~~~~~~~~~
                If permission_set with id of 1 does not exist, go through first stage setup.
                """
                if not permission_set.objects.all():
                    #Create administration permission_set
                    submit_permission_set = permission_set(
                        permission_set_name="Administration Permission Set",
                        administration_assign_user_to_group=4,
                        administration_create_group=4,
                        administration_create_permission_set=4,
                        administration_create_user=4,
                        assign_campus_to_customer=4,
                        associate_project_and_task=4,
                        bug=4,
                        bug_client=4,
                        customer=4,
                        email=4,
                        invoice=4,
                        invoice_product=4,
                        kanban=4,
                        kanban_card=4,
                        opportunity=4,
                        organisation=4,
                        organisation_campus=4,
                        project=4,
                        quote=4,
                        requirement=4,
                        requirement_link=4,
                        task=4,
                        tax=4,
                        template=4,
                        document=1,
                        contact_history=1,
                        kanban_comment=1,
                        project_history=1,
                        task_history=1,
                        change_user=request.user,
                    )
                    submit_permission_set.save()

                    #Create admin group
                    submit_group = group(
                        group_name="Administration",
                        change_user=request.user,
                    )
                    submit_group.save()

                    #Add user to admin group
                    submit_user_group = user_group(
                        username=request.user,
                        group=group.objects.get(group_id=1),
                        permission_set=permission_set.objects.get(permission_set_id=1),
                        change_user=request.user,
                    )
                    submit_user_group.save()

                request.session['is_superuser'] = request.user.is_superuser

                return HttpResponseRedirect(reverse('alerts'))
            else:
                print("User not authenticated")
        else:
            print(form.errors)

    # load template
    t = loader.get_template('NearBeach/login.html')

    # context
    c = {
        'login_form': form,
        'RECAPTCHA_PUBLIC_KEY': RECAPTCHA_PUBLIC_KEY,
    }

    return HttpResponse(t.render(c, request))


def logout(request):
    # log the user out and go to login page
    auth.logout(request)
    return HttpResponseRedirect(reverse('login'))


@login_required(login_url='login')
def merge_tags(request, old_tag_id, new_tag_id=""):
    """
    Merge tags will get the old tag_id, and update all the tag assoications with the new tag_id before deleting the old
    tag id.
    :param request:
    :param old_tag_id: The old tag that we want to merge
    :param new_tag_id: The new tag that we want to merge into
    :return: back to the tag list

    Method
    ~~~~~~
    1. Check permissions - only a user with a permission of 4 is permitted. Anyone else is sent to the naughty space
    2. Check to see if method is POST - if it check instructions there
    3. Get a list of ALL tags excluding the current old_tag_id
    4. Render out the page and wait for the user
    """

    permission_results = return_user_permission_level(request, None, 'tag')

    if permission_results['tag'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    if request.method == "POST":
        """
        The user has submitted both an old_tag_id and a new_tag_id. The old tag id will be merged into the new tag id.
        1. In tag association, we update all the tag associations to the new tag from the old tag
        2. We state that the old tag is deleted.
        3. Return blank page back as a success
        """
        new_tag_instance = tag.objects.get(tag_id=new_tag_id)

        #Update all tags associated with the old tag id with the new tag id
        update_tag_association = tag_assignment.objects.filter(
            is_deleted="FALSE",
            tag_id=old_tag_id,
        ).update(
            tag_id=new_tag_instance,
        )

        #Delete the old tag
        old_tag_instance = tag.objects.get(tag_id=old_tag_id)
        old_tag_instance.is_deleted = "TRUE"
        old_tag_instance.save()

        #Return a blank page :)
        t = loader.get_template('NearBeach/blank.html')
        c = {}
        return HttpResponse(t.render(c,request))

    tag_results = tag.objects.filter(
        is_deleted="FALSE",
    ).exclude(
        tag_id=old_tag_id,
    )

    # Get template
    t = loader.get_template('NearBeach/tags/merge_tags.html')

    c = {
        'tag_results': tag_results,
        'old_tag_id': old_tag_id,
    }

    return HttpResponse(t.render(c, request))

@login_required(login_url='login')
def my_profile(request):
    permission_results = return_user_permission_level(request, None, "")

    #Data required in both POST and GET
    about_user_results=about_user.objects.filter(
        is_deleted="FALSE",
        user=request.user,
    ).order_by('-date_created')
    if about_user_results:
        about_user_text = about_user_results[0].about_user_text
    else:
        about_user_text = ""

    user_instance = User.objects.get(id=request.user.id)

    if request.method == "POST":
        """
        User Information
        ~~~~~~~~~~~~~~~~
        We want to always update the user information. Give the User the option to also update
        their password.
        """
        form = my_profile_form(request.POST)
        if form.is_valid():
            user_instance.first_name=form.cleaned_data['first_name']
            user_instance.last_name=form.cleaned_data['last_name']
            user_instance.email=form.cleaned_data['email']
            user_instance.save()

            password1 = form.cleaned_data['password1']
            password2 = form.cleaned_data['password2']

            if password1 == password2:
                # Change passwords
                if not password1 == "":
                    user_instance = User.objects.get(id=request.user.id)
                    user_instance.set_password(password1)
                    user_instance.save()

        else:
            print(form.errors)

        """
        About User Text
        ~~~~~~~~~~~~~~~
        If there is a difference between the current about user and what the user has submitted,
        we want to update the database.
        If there is no change - we will ignore. No need to flood the database with the exact same data over
        and over again.
        """
        form = about_user_form(request.POST)
        if form.is_valid():
            if not about_user_text == form.cleaned_data['about_user_text'] and not about_user_text == None:
                about_user_text = form.cleaned_data['about_user_text']

                about_user_submit = about_user(
                    change_user=request.user,
                    about_user_text=about_user_text,
                    user_id=request.user.id
                )
                about_user_submit.save()
        else:
            print(form.errors)

    #Get data
    project_results = project.objects.filter(
        is_deleted="FALSE",
        project_id__in=object_assignment.objects.filter(
            is_deleted="FALSE",
            assigned_user=request.user.id,
        ).values('project_id').distinct()
    )

    #Initialise about user form, if there is no about_user use a blank ""


    # load template
    t = loader.get_template('NearBeach/my_profile.html')

    # context
    c = {
        'project_results': project_results,
        'my_profile_form': my_profile_form(
            instance=user_instance,
        ),
        'about_user_form': about_user_form(initial={
            'about_user_text': about_user_text,
        }),
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def new_bug_client(request):
    permission_results = return_user_permission_level(request, None, 'bug_client')

    if permission_results['bug_client'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))
    form_errors = ''
    if request.method == "POST":
        form = bug_client_form(request.POST)
        if form.is_valid():
            #Get required data
            bug_client_name = form.cleaned_data['bug_client_name']
            list_of_bug_client = form.cleaned_data['list_of_bug_client']
            bug_client_url = form.cleaned_data['bug_client_url']

            #Test the link first before doing ANYTHING!
            try:
                url = bug_client_url + list_of_bug_client.bug_client_api_url + 'version'
                print(url)
                response = urlopen(url)
                data = json.load(response)
                print("Got the JSON")

                bug_client_submit = bug_client(
                    bug_client_name = bug_client_name,
                    list_of_bug_client = list_of_bug_client,
                    bug_client_url = bug_client_url,
                    change_user=request.user,
                )
                bug_client_submit.save()
                return HttpResponseRedirect(reverse('bug_client_list'))
            except:
                form_errors = "Could not connect to the API"


        else:
            print(form.errors)
            form_errors(form.errors)

    # load template
    t = loader.get_template('NearBeach/new_bug_client.html')

    # context
    c = {
        'bug_client_form': bug_client_form(),
        'form_errors': form_errors,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))

@login_required(login_url='login')
def new_campus(request, location_id, destination):
    permission_results = return_user_permission_level(request, None, 'organisation_campus')

    if permission_results['organisation_campus'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    """
	If the user is not logged in, we want to send them to the login page.
	This function should be in ALL webpage requests except for login and
	the index page
	"""
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse('login'))

    if request.method == 'POST':
        form = new_campus_form(request.POST)
        if form.is_valid():
            # Get instances
            region_instance = list_of_country_region.objects.get(
                region_id=request.POST.get('country_and_regions')
            )

            campus_nickname = form.cleaned_data['campus_nickname']
            campus_phone = form.cleaned_data['campus_phone']
            campus_fax = form.cleaned_data['campus_fax']
            campus_address1 = form.cleaned_data['campus_address1']
            campus_address2 = form.cleaned_data['campus_address2']
            campus_address3 = form.cleaned_data['campus_address3']
            campus_suburb = form.cleaned_data['campus_suburb']

            #organisation = organisation.objects.get(organisation_id)

            # BUG - some simple validation should go here?

            # Submitting the data
            submit_form = campus(
                #organisation_id=organisation,
                campus_nickname=campus_nickname,
                campus_phone=campus_phone,
                campus_fax=campus_fax,
                campus_address1=campus_address1,
                campus_address2=campus_address2,
                campus_address3=campus_address3,
                campus_suburb=campus_suburb,
                campus_region_id=region_instance,
                campus_country_id=region_instance.country_id,
                change_user = request.user,
            )
            if destination == "organisation":
                submit_form.organisation_id = organisation.objects.get(organisation_id=location_id)
            else:
                submit_form.customer = customer.objects.get(customer_id=location_id)
            submit_form.save()

            #Get the coordinates and update them into the system
            update_coordinates(submit_form.campus_id)

            if destination == "organisation":
                return HttpResponseRedirect(reverse(organisation_information, args={location_id}))
            else:
                return HttpResponseRedirect(reverse(customer_information, args={location_id}))
        else:
            print(form.errors)
            return HttpResponseRedirect(reverse(new_campus, args={location_id,destination}))

    # SQL
    countries_results = list_of_country.objects.all().order_by('country_name')
    countries_regions_results = list_of_country_region.objects.all().order_by('region_name')

    # load template
    t = loader.get_template('NearBeach/new_campus.html')

    # context
    c = {
        'location_id': location_id,
        'destination': destination,
        'new_campus_form': new_campus_form(),
        'countries_results': countries_results,
        'countries_regions_results': countries_regions_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def new_customer(request, organisation_id):
    permission_results = return_user_permission_level(request, None, 'customer')

    if permission_results['customer'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    form_errors = ''
    if request.method == 'POST':
        form = new_customer_form(request.POST)
        if form.is_valid():
            customer_title = form.cleaned_data['customer_title']
            customer_first_name = form.cleaned_data['customer_first_name']
            customer_last_name = form.cleaned_data['customer_last_name']
            customer_email = form.cleaned_data['customer_email']


            organisation_id = form.cleaned_data['organisation_id']

            submit_form = customer(
                customer_title=customer_title,
                customer_first_name=customer_first_name,
                customer_last_name=customer_last_name,
                customer_email=customer_email,
                organisation_id=organisation_id,
                change_user=request.user,
            )

            # BUG - no validation process to see if there exists a customer already :(
            submit_form.save()

            return HttpResponseRedirect(reverse(customer_information, args={submit_form.customer_id}))
        else:
            form_errors = form.errors
    else:
        initial = {
            'organisation_id': organisation_id,
        }

        form = new_customer_form(initial=initial)


    # load template
    t = loader.get_template('NearBeach/new_customer.html')



    # context
    c = {
        #'new_customer_form': new_customer_form(initial=initial),
        'new_customer_form': form,
        'organisation_id': organisation_id,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'form_errors': form_errors,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def new_group(request):
    """
    You need to create a new group. You must be over 3 on your administration create group :)
    :param request:
    :return: group_infomration page if in POST or new_group page in GET
    """
    # Check user permission
    permission_results = return_user_permission_level(request, [None], ['administration_create_group'])

    if permission_results['administration_create_group'] <= 1:
        # Send them to permission denied!!
        return HttpResponseRedirect(reverse(permission_denied))

    if request.method == "POST":
        form = new_group_form(request.POST)
        if form.is_valid():
            group_name = form.cleaned_data['group_name']

            """
            We want to check to see if the group name is unique. If there is another group name (excluding the deleted)
            is available - we will just go to it without any errors. Hidden to the user.
            """
            group_results = group.objects.filter(
                is_deleted="FALSE",
                group_name=group_name,
            )
            if group_results:
                return HttpResponseRedirect(reverse('group_information', args={ group_results[0].group_id }))

            #Group does not exist - lets make it
            group_submit = group(
                group_name=group_name,
                parent_group=form.cleaned_data['parent_group'],
                change_user=request.user,
            )
            group_submit.save()

            #Done making it - lets go to it
            return HttpResponseRedirect(reverse('group_information', args={ group_submit.group_id }))
        else:
            print(form.errors)

    # Get template
    t = loader.get_template('NearBeach/administration/new_group.html')

    c = {
        'new_group_form': new_group_form(),
        'administration_permission': permission_results['administration'],
        'new_item_permission': permission_results['new_item'],
    }

    return HttpResponse(t.render(c,request))

@login_required(login_url='login')
def new_kanban_board(request):
    permission_results = return_user_permission_level(request, None, 'kanban')

    if permission_results['kanban'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    if request.method == "POST":
        form = kanban_board_form(request.POST)
        if form.is_valid():
            #Create the new board
            kanban_board_submit = kanban_board(
                kanban_board_name=form.cleaned_data['kanban_board_name'],
                change_user=request.user,
            )
            kanban_board_submit.save()

            #Create the levels for the board
            column_count = 1
            for line in form.cleaned_data['kanban_board_column'].split('\n'):
                kanban_column_submit = kanban_column(
                    kanban_column_name=line,
                    kanban_column_sort_number=column_count,
                    kanban_board=kanban_board_submit,
                    change_user=request.user,
                )
                kanban_column_submit.save()
                column_count = column_count + 1


            level_count = 1
            for line in form.cleaned_data['kanban_board_level'].split('\n'):
                kanban_level_submit = kanban_level(
                    kanban_level_name=line,
                    kanban_level_sort_number=level_count,
                    kanban_board=kanban_board_submit,
                    change_user=request.user,
                )
                kanban_level_submit.save()
                level_count = level_count + 1

            """
            Permissions granting
            """
            select_groups = form.cleaned_data['select_groups']
            for row in select_groups:
                group_instance = group.objects.get(group_name=row)
                permission_save = object_assignment(
                    kanban_board_id=kanban_board_submit,
                    group_id=group_instance,
                    change_user=request.user,
                )
                permission_save.save()


            #Send you to the kanban information center
            return HttpResponseRedirect(reverse('kanban_information', args={kanban_board_submit.kanban_board_id}))

        else:
            print(form.errors)
            return HttpResponseBadRequest(form.errors)

    t = loader.get_template('NearBeach/new_kanban_board.html')

    c = {
        'kanban_board_form': kanban_board_form(initial={
            'kanban_board_column': 'Backlog\nIn Progress\nCompleted',
            'kanban_board_level': 'Sprint 1\nSprint 2',
        }),
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],

    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def new_kanban_requirement_board(request,requirement_id):
    permission_results = return_user_permission_level(request,None,'kanban_board')

    if permission_results['kanban_board'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    #Create the kanban board and link to requirement
    requirement_instance = requirement.objects.get(requirement_id=requirement_id)

    kanban_board_submit = kanban_board(
        kanban_board_name=requirement_instance.requirement_title,
        requirement=requirement_instance,
        change_user=request.user,
    )
    kanban_board_submit.save()

    #Go to the kanban board
    return HttpResponseRedirect(
        reverse(
            'kanban_requirement_information',
            args={kanban_board_submit.kanban_board_id}
        )
    )


@login_required(login_url='login')
def new_kudos(request,project_id):
    """
    Method
    ~~~~~~
    1. Do checks to see if user is allowed to do this
    2. Find ALL customers associated with this project
    3. Create a new kudos for each customer
    4. Go back to read only
    :param request: -- basic
    :param project_id: the project that we will be creating kudos for
    :return: back to the read only
    """
    permission_results = return_user_permission_level(request, None, 'project')



    print("REQUEST PATH: " + request.path)
    print("REQUEST PATH INFO: " + request.path_info)
    print("REQUEST FULL PATH: " + request.get_full_path())
    print("RAW URI: " + request.get_raw_uri())
    print("RAW get_host" + request.get_host())


    if permission_results['project'] < 4:
        return HttpResponseRedirect(reverse('permission_denied'))

    if request.method == "POST":
        #Get customers
        #project_results = project.objects.get(project_id=project_id)
        project_customer_results = project_customer.objects.filter(
            is_deleted="FALSE",
            project_id=project_id,
        )

        for customer_line in project_customer_results:
            kudos_submit = kudos(
                customer=customer_line.customer_id,
                project_id=project_id,
                change_user=request.user,
            )
            kudos_submit.save()

            #Try and send an email to the customer
            try:
                # Check variables
                EMAIL_HOST_USER = settings.EMAIL_HOST_USER
                EMAIL_BACKEND = settings.EMAIL_BACKEND
                EMAIL_USE_TLS = settings.EMAIL_USE_TLS
                EMAIL_HOST = settings.EMAIL_HOST
                EMAIL_PORT = settings.EMAIL_PORT
                EMAIL_HOST_USER = settings.EMAIL_HOST_USER
                EMAIL_HOST_PASSWORD = settings.EMAIL_HOST_PASSWORD

                email_content = "Hello " \
                                + str(customer_line.customer_id.customer_first_name) \
                                + """<br/>We have recently finished working on your project. Can you please evaluate our work at: <a href=\"""" \
                                + request.get_host() + """/kudos_rating/""" + str(kudos_submit.kudos_key) + """\">""" \
                                + request.get_host() + """/kudos_rating/""" + str(kudos_submit.kudos_key) + """/</a><br/>Regards<br/>Project Team"""

                email = EmailMultiAlternatives(
                    'Kudos Evaluation form',
                    email_content,
                    'donotreply@nearbeach.org',
                    [customer_line.customer_id.customer_email],
                )
                email.attach_alternative(email_content, "text/html")
                if not email.send():
                    return HttpResponseBadRequest("Email did not send correctly.")
            except:
                print("Email not sent")


        #Redirect back to read only template
        return HttpResponseRedirect(
            reverse(
                'project_readonly',
                args={project_id}
            )
        )
    else:
        return HttpResponseBadRequest("Sorry, can only do this request through post")

@login_required(login_url='login')
def new_opportunity(request, location_id,destination):
    permission_results = return_user_permission_level(request, None, 'opportunity')

    if permission_results['opportunity'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    # POST or None
    if request.method == 'POST':
        form = new_opportunity_form(request.POST)
        if form.is_valid():
            current_user = request.user
            # Start saving the data in the form
            opportunity_name = form.cleaned_data['opportunity_name']
            opportunity_description = form.cleaned_data['opportunity_description']
            currency_id = form.cleaned_data['currency_id']
            opportunity_amount = form.cleaned_data['opportunity_amount']
            amount_type_id = form.cleaned_data['amount_type_id']
            opportunity_success_probability = form.cleaned_data['opportunity_success_probability']
            lead_source_id = form.cleaned_data['lead_source_id']
            select_groups = form.cleaned_data['select_groups']
            opportunity_expected_close_date = form.cleaned_data['opportunity_expected_close_date']



            """
			Some dropdown boxes will need to have instances made from the values.
			"""
            stage_of_opportunity_instance = list_of_opportunity_stage.objects.get(
                opportunity_stage_id=request.POST.get('opportunity_stage')
            )

            """
			SAVE THE DATA
			"""
            submit_opportunity = opportunity(
                opportunity_name=opportunity_name,
                opportunity_description=opportunity_description,
                currency_id=currency_id,
                opportunity_amount=opportunity_amount,
                amount_type_id=amount_type_id,
                opportunity_success_probability=opportunity_success_probability,
                lead_source_id=lead_source_id,
                opportunity_expected_close_date=opportunity_expected_close_date,
                opportunity_stage_id=stage_of_opportunity_instance,
                user_id=current_user,
                change_user=request.user,
            )
            """
            We ignore the destination at this part. A user might have tried to create the opportunity from the organisation
            however have the change of mind when filling out the form. This short method checks to see if there is a
            customer id. If there is one, then it will assign the opportunity to the customer.
            """
            customer_id = request.POST.get('customer_id')
            if customer_id.isdigit():
                customer_instance = customer.objects.get(customer_id=request.POST.get('customer_id'))
                submit_opportunity.customer_id = customer_instance
                #If a customer has a null for an organisation it will pass through as null
                submit_opportunity.organisation_id = customer_instance.organisation_id
            else:
                organisations_instance = form.cleaned_data['organisation_id']
                if organisations_instance:
                    submit_opportunity.organisation_id = organisations_instance
            submit_opportunity.save()
            opportunity_instance = opportunity.objects.get(opportunity_id=submit_opportunity.opportunity_id)

            """
            Permissions granting
            """
            for row in select_groups:
                group_instance = group.objects.get(group_name=row)
                permission_save = object_assignment(
                    opportunity_id=opportunity_instance,
                    group_id=group_instance,
                    change_user=request.user,
                )
                permission_save.save()

            return HttpResponseRedirect(reverse(opportunity_information, args={submit_opportunity.opportunity_id}))
        else:
            print(form.errors)


    # load template
    t = loader.get_template('NearBeach/new_opportunity.html')

    # DATA
    customer_results = customer.objects.all()
    opportunity_stage_results = list_of_opportunity_stage.objects.filter(is_deleted="FALSE")

    # context
    c = {
        'new_opportunity_form': new_opportunity_form(),
        'customer_results': customer_results,
        'location_id': location_id,
        'destination': destination,
        'opportunity_stage_results': opportunity_stage_results,
        'timezone': settings.TIME_ZONE,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def new_organisation(request):
    permission_results = return_user_permission_level(request, None, 'organisation')

    if permission_results['organisation'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))
    """
	To stop duplicates in the system, the code will quickly check to see if
	there is already a company that has either one of the following;
	-- same name
	-- same website
	-- same contact email.
	
	If one of these conditions are met then the user will be returned to the
	form and shown the possible duplicates. If the user accepts this, then
	the organisation is created.	
	"""
    form_errors = ""
    form = new_organisation_form(request.POST or None)
    duplicate_results = None
    if request.method == 'POST':
        if form.is_valid():
            organisation_name = form.cleaned_data['organisation_name']
            organisation_email = form.cleaned_data['organisation_email']
            organisation_website = form.cleaned_data['organisation_website']

            duplicate_results = organisation.objects.filter(
                Q(organisation_name=organisation_name) | Q(organisation_email=organisation_email) | Q(
                    organisation_website=organisation_website))

            """
			If the user has clicked that they accept the duplicate OR if there
			are NO duplicates, just make the organisation :)
			"""
            if ((duplicate_results.count() == 0) or (request.POST.get("save_duplicate"))):
                # Save the form data
                submit_form = organisation(
                    organisation_name=organisation_name,
                    organisation_email=organisation_email,
                    organisation_website=organisation_website,
                    change_user=request.user,
                )
                submit_form.save()

                return HttpResponseRedirect(reverse(organisation_information, args={submit_form.organisation_id}))
        else:
            form_errors = form.errors

    """
	Now that we have determined if the organisation should be saved or not
	we are left with the only options;
	1.) There was no organisation to save
	2.) there was a duplicate organisation and we are asking the user about it
	"""
    # load template
    t = loader.get_template('NearBeach/new_organisation.html')

    # Define the duplication count
    duplication_count = 0;
    if not duplicate_results == None:
        duplication_count = duplicate_results.count()

    # context
    c = {
        'new_organisation_form': form,
        'duplicate_results': duplicate_results,
        'duplication_count': duplication_count,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'form_errors': form_errors,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def new_permission_set(request):
    permission_results = return_user_permission_level(request, None, 'administration_create_permission_set')

    if permission_results['administration_create_permission_set'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    save_errors = None
    if request.method == "POST" and permission_results['administration_create_permission_set'] >= 3:
        form = permission_set_form(request.POST)
        if form.is_valid():
            """
            If the permission_set name already exists, we won't create it, instead we will load the correct page. This
            is assuming it has not been deleted. :O
            """
            permission_set_name=form.cleaned_data['permission_set_name']
            permission_set_results=permission_set.objects.filter(
                is_deleted="FALSE",
                permission_set_name=permission_set_name,
            )
            if permission_set_results:
                return HttpResponseRedirect(reverse('permission_set_information',args={ permission_set_results[0].permission_set_id }))

            # Try and save the form.
            submit_permission_set = permission_set(
                permission_set_name=permission_set_name,
                administration_assign_user_to_group=form.cleaned_data['administration_assign_user_to_group'],
                administration_create_group=form.cleaned_data['administration_create_group'],
                administration_create_permission_set=form.cleaned_data['administration_create_permission_set'],
                administration_create_user=form.cleaned_data['administration_create_user'],
                assign_campus_to_customer=form.cleaned_data['assign_campus_to_customer'],
                associate_project_and_task=form.cleaned_data['associate_project_and_task'],
                customer=form.cleaned_data['customer'],
                invoice=form.cleaned_data['invoice'],
                invoice_product=form.cleaned_data['invoice_product'],
                opportunity=form.cleaned_data['opportunity'],
                organisation=form.cleaned_data['organisation'],
                organisation_campus=form.cleaned_data['organisation_campus'],
                project=form.cleaned_data['project'],
                requirement=form.cleaned_data['requirement'],
                requirement_link=form.cleaned_data['requirement_link'],
                task=form.cleaned_data['task'],
                document=form.cleaned_data['document'],
                contact_history=form.cleaned_data['contact_history'],
                project_history=form.cleaned_data['project_history'],
                task_history=form.cleaned_data['task_history'],
                change_user=request.user,
            )
            submit_permission_set.save()

            #Go to the new permission set :)
            return HttpResponseRedirect(reverse('permission_set_information', args={ submit_permission_set.permission_set_id }))


        else:
            print(form.errors)
            save_errors = form.errors

    # Load template
    t = loader.get_template('NearBeach/new_permission_set.html')

    # context
    c = {
        'permission_set_form': permission_set_form(request.POST or None),
        'save_errors': save_errors,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def new_project(request, location_id='', destination=''):
    permission_results = return_user_permission_level(request, None, 'project')

    if permission_results['project'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    if request.method == "POST":
        form = new_project_form(request.POST)
        if form.is_valid():
            project_name = form.cleaned_data['project_name']
            project_description = form.cleaned_data['project_description']
            organisation_id_form = form.cleaned_data['organisation_id']

            submit_project = project(
                project_name=project_name,
                project_description=project_description,
                project_start_date=form.cleaned_data['project_start_date'],
                project_end_date=form.cleaned_data['project_end_date'],
                project_status='New',
                change_user=request.user,
            )
            if organisation_id_form:
                submit_project.organisation_id=organisation_id_form

            # Submit the data
            submit_project.save()

            """
			Once the new project has been created, we will obtain a 
			primary key. Using this new primary key we will allocate
			permissions to the new project.
			"""
            project_permission = form.cleaned_data['project_permission']

            for row in project_permission:
                submit_group = object_assignment(
                    project_id=submit_project,
                    group_id=group.objects.get(group_id=row.group_id),
                    change_user=request.user,
                )
                submit_group.save()
            """
            If the destination is CUSTOMER, then we assign the project_customer to that customer.
            If the destination is connected to OPPORTUNITY, then we assign it to the opportunity.
            """
            print("CURRENT DESTINATION IS: " + str(destination))
            if destination == "customer":
                customer_instance = customer.objects.get(customer_id=location_id)
                save_project_customer = project_customer(
                    project_id=submit_project,
                    customer_id=customer_instance,
                    change_user=request.user,
                )
                save_project_customer.save()
            elif destination == "opportunity":
                opportunity_instance = opportunity.objects.get(opportunity_id=location_id)
                save_project_opportunity = project_opportunity(
                    project_id=submit_project,
                    opportunity_id=opportunity_instance,
                    change_user=request.user,
                )
                save_project_opportunity.save()

            """
            We want to return the user to the original location. This is dependent on the destination
            """
            print("New project now compeleted - going to location.")
            if destination == "organisation":
                return HttpResponseRedirect(reverse(organisation_information, args={location_id}))
            elif destination == "customer":
                return HttpResponseRedirect(reverse(customer_information, args={location_id}))
            elif destination == "opportunity":
                return HttpResponseRedirect(reverse(opportunity_information, args={location_id}))
            else:
                return HttpResponseRedirect(reverse(project_information, args={submit_project.pk}))
        else:
            print("Form is not valid")
            print(form.errors)

    # Obtain the group the user is associated with
    current_user = request.user

    groups_results = group.objects.filter(
        is_deleted="FALSE",
        group_id__in=user_group.objects.filter(
            is_deleted="FALSE",
            username_id=current_user.id
        ).values('group_id')
    )

    organisations_results = organisation.objects.filter(is_deleted='FALSE')


    #FIGURE OUT HOW TO GET ORGANISATION HERE!
    if destination == "" or destination == None:
        organisation_id = None
        customer_id = None
        opportunity_id = None
    elif destination == "organisation":
        organisation_id = location_id
        customer_id = None
        opportunity_id = None
    elif destination == "customer":
        customer_instance = customer.objects.get(customer_id=location_id)

        organisation_id = customer.organisation_id
        customer_id = customer.customer_id
        opportunity_id = None
    elif destination == "opportunity":
        opportunity_instance = opportunity.objects.get(opportunity_id=location_id)

        organisation_id = opportunity_instance.organisation_id
        customer_id = opportunity_instance.customer_id
        opportunity_id = opportunity_instance.opportunity_id


    # Load the template
    t = loader.get_template('NearBeach/new_project.html')

    print(request.user.id)

    # context
    c = {
        'new_project_form': new_project_form(initial={
            'organisation_id': organisation_id,
        }),
        'groups_results': groups_results,
        'groups_count': groups_results.__len__(),
        'opportunity_id': opportunity_id,
        'organisations_count': organisations_results.count(),
        'organisation_id': organisation_id,
        'customer_id': customer_id,
        'timezone': settings.TIME_ZONE,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'destination': destination,
        'location_id': location_id,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def new_quote(request,destination,primary_key):
    permission_results = return_user_permission_level(request, None,'quote')

    if permission_results['quote'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    if request.method == "POST":
        form = new_quote_form(request.POST)
        if form.is_valid():
            quote_title=form.cleaned_data['quote_title']
            quote_terms=form.cleaned_data['quote_terms']
            quote_stage_id=form.cleaned_data['quote_stage_id']
            customer_notes=form.cleaned_data['customer_notes']
            select_groups = form.cleaned_data['select_groups']


            # Create the final start/end date fields
            quote_valid_till = form.cleaned_data['quote_valid_till']

            quote_stage_instance = list_of_quote_stage.objects.get(quote_stage_id=quote_stage_id.quote_stage_id)

            submit_quotes = quote(
                quote_title=quote_title,
                quote_terms=quote_terms,
                quote_stage_id=quote_stage_instance,
                customer_notes=customer_notes,
                quote_valid_till=quote_valid_till,
                change_user=request.user
            )
            """
            ADD CODE HERE
            If the user does not have the access to approve quote, then the quote approval
            sticks to draft and they will not be able to turn it into an INVOICE.
            If however the user DOES have access to approve quote, then the quote approval
            sticks to approved and they can instantly turn the quote into an INVOICE.
            This is an automatic process - no user input needed
            
            
            EXCEPT I HAVE TO WRITE THE CODE. So by default I am just turning it to the default value.
            """
            submit_quotes.quote_approval_status_id='APPROVED'


            """
            Link the quote to the correct project/task/opportunity
            """
            if destination=='project':
                submit_quotes.project_id = project.objects.get(project_id=primary_key)
            elif destination=='task':
                submit_quotes.task_id = task.objects.get(task_id=primary_key)
            elif destination=='customer':
                submit_quotes.customer_id = customer.objects.get(customer_id=primary_key)
            elif destination=='organisation':
                submit_quotes.organisation_id = organisation.objects.get(organisation_id=primary_key)
            else:
                submit_quotes.opportunity_id = opportunity.objects.get(opportunity_id=primary_key)

            submit_quotes.save()

            if (select_groups):
                for row in select_groups:
                    group_instance = group.objects.get(group_name=row)
                    permission_save = object_assignment(
                        quote_id=submit_quotes,
                        group_id=group_instance,
                        change_user=request.user,
                    )
                    permission_save.save()


            #Now to go to the quote information page
            return HttpResponseRedirect(reverse(quote_information, args={submit_quotes.quote_id}))

        else:
            print(form.errors)

    end_date = datetime.datetime.now()+timedelta(14)


    # Load the template
    t = loader.get_template('NearBeach/new_quote.html')

    # context
    c = {
        'new_quote_form': new_quote_form,
        'primary_key': primary_key,
        'destination': destination,
        'end_year': end_date.year,
        'end_month': end_date.month,
        'end_day': end_date.day,
        'timezone': settings.TIME_ZONE,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))

@login_required(login_url='login')
def new_quote_template(request):
    permission_results = return_user_permission_level(request, None, 'templates')

    if permission_results['templates'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    # Define if the page is loading in POST
    if request.method == "POST":
        #User has requested new quote template
        quote_template_submit=quote_template(
            change_user_id=request.user.id,
            quote_template_description = "Quote Template",
            template_css="""
            .table_header {
                font-family: "Trebuchet MS", Arial, Helvetica, sans-serif;
                border-collapse: collapse;
                width: 100%;
            }
            
            .table_header {
                border: 1px solid #ddd;
                padding: 8px;
            }
            
            .table_header {
                padding-top: 12px;
                padding-bottom: 12px;
                text-align: left;
                background-color: #4CAF50;
                color: white;
            }
            
            table td, table td * {
                vertical-align: top;
            }
            """,
            header="NearBeach Quote Number {{ quote_id }}",
            company_letter_head="<p>NearBeach Incorporated<br />Melbourne 3000<br />Australia</p>",
            payment_terms="Please pay within 30 days",
            notes="{{ quote_terms }}",
            organisation_details="""
                <p>{{ organisation_name }}<br />
                {{ billing_address1 }}<br />
                {{ billing_address2 }}<br />
                {{ billing_address3 }}<br />
                {{ billing_suburb }} {{ billing_postcode }}<br />
                {{ billing_region }}<br />
                {{ billing_country }}</p>
            """,
            product_line = "Temp product line",
            service_line = "Temp service line",
            payment_method="""
            <table>
            <tbody>
            <tr style="height: 18px;">
            <td style="width: 50%; height: 18px;">Account</td>
            <td style="width: 50%; height: 18px;">0000 0000</td>
            </tr>
            <tr style="height: 18px;">
            <td style="width: 50%; height: 18px;">BSB</td>
            <td style="width: 50%; height: 18px;">000 000</td>
            </tr>
            <tr style="height: 18px;">
            <td style="width: 50%; height: 18px;">Acount Name</td>
            <td style="width: 50%; height: 18px;">NearBeach Holdings</td>
            </tr>
            </tbody>
            </table>
            """,
            footer="{{ page_number }}",
        )
        quote_template_submit.save()

        #Send back the quote number
        json_data = {}
        json_data['quote_template_id'] = quote_template_submit.pk
        #json_data['quote_template_id'] = '1'

        return JsonResponse(json_data)
    else:
        return HttpResponseBadRequest("Sorry, but new template can only be requested by a post command")



@login_required(login_url='login')
def new_task(request, location_id='', destination=''):
    permission_results = return_user_permission_level(request, None, 'task')

    if permission_results['task'] < 3:
        return HttpResponseRedirect(reverse('permission_denied'))

    # Define if the page is loading in POST
    if request.method == "POST":
        form = new_task_form(request.POST)
        if form.is_valid():
            task_short_description = form.cleaned_data['task_short_description']
            task_long_description = form.cleaned_data['task_long_description']
            organisation_id_form = form.cleaned_data['organisation_id']


            submit_task = task(
                task_short_description=task_short_description,
                task_long_description=task_long_description,
                #organisation_id=organisation_id_form,
                task_start_date=form.cleaned_data['task_start_date'],
                task_end_date=form.cleaned_data['task_end_date'],
                task_status='New',
                change_user = request.user,
            )

            if organisation_id_form:
                submit_task.organisation_id = organisation_id_form

            # Submit the data
            submit_task.save()

            """
			Once the new project has been created, we will obtain a 
			primary key. Using this new primary key we will allocate
			group to the new project.
			"""
            task_permission = form.cleaned_data['task_permission']

            for row in task_permission:
                submit_group = object_assignment(
                    task_id_id=submit_task.pk,
                    group_id_id=row.group_id,
                    change_user=request.user,
                )
                submit_group.save()

            """
            If the destination is CUSTOMER, then we assign the project_customer to that customer.
            If the destination is connected to OPPORTUNITY, then we assign it to the opportunity.
            """
            if destination == "customer":
                customer_instance = customer.objects.get(customer_id=location_id)
                save_project_customer = task_customer(
                    task_id=submit_task,
                    customer_id=customer_instance,
                    change_user=request.user,
                )
                save_project_customer.save()
            elif destination == "opportunity":
                opportunity_instance = opportunity.objects.get(opportunity_id=location_id)
                save_project_opportunity = task_opportunity(
                    task_id=submit_task,
                    opportunity_id=opportunity_instance,
                    change_user=request.user,
                )
                save_project_opportunity.save()

            """
            We want to return the user to the original location. This is dependent on the destination
            """
            if destination == "organisation":
                return HttpResponseRedirect(reverse(organisation_information, args={location_id}))
            elif destination == "customer":
                return HttpResponseRedirect(reverse(customer_information, args={location_id}))
            elif destination == "opportunity":
                return HttpResponseRedirect(reverse(opportunity_information, args={location_id}))
            else:
                return HttpResponseRedirect(reverse(task_information, args={submit_task.pk}))
                # Lets go back to the customer
    else:
        # Obtain the group the user is associated with
        groups_results = group.objects.filter(
            is_deleted="FALSE",
            group_id__in=user_group.objects.filter(
                is_deleted="FALSE",
                username_id=request.user.id
            ).values('group_id')
        )

        organisations_results = organisation.objects.filter(is_deleted='FALSE')

        # Setup dates for initalising
        today = datetime.datetime.now()
        next_week = today + datetime.timedelta(days=31)

        """
		We need to do some basic formulations with the hour and and minutes.
		For the hour we need to find all those who are in the PM and
		change both the hour and meridiem accordingly.
		For the minute, we have to create it in 5 minute blocks.
		"""
        hour = today.hour
        minute = int(5 * round(today.minute / 5.0))
        meridiems = 'AM'

        if hour > 12:
            hour = hour - 12
            meridiems = 'PM'
        elif hour == 0:
            hour = 12

        #FIGURE OUT HOW TO GET ORGANISATION HERE!
        if destination == "" or destination == None:
            organisation_id = None
            customer_id = None
            opportunity_id = None
        elif destination == "organisation":
            organisation_id = location_id
            customer_id = None
            opportunity_id = None
        elif destination == "customer":
            customer_instance = customer.objects.get(customer_id=location_id)

            organisation_id = customer.organisation_id
            customer_id = customer.customer_id
            opportunity_id = None
        elif destination == "opportunity":
            opportunity_instance = opportunity.objects.get(opportunity_id=location_id)

            organisation_id = opportunity_instance.organisation_id
            customer_id = opportunity_instance.customer_id
            opportunity_id = opportunity_instance.opportunity_id


        # Loaed the template
        t = loader.get_template('NearBeach/new_task.html')

        c = {
            'new_task_form': new_task_form(
                initial={
                    'organisation_id': organisation_id,
                }),
            'groups_results': groups_results,
            'groups_count': groups_results.__len__(),
            'organisation_id': organisation_id,
            'organisations_count': organisation.objects.filter(is_deleted='FALSE').count(),
            'customer_id': customer_id,
            'opportunity_id': opportunity_id,
            'timezone': settings.TIME_ZONE,
            'location_id': location_id,
            'destination': destination,
            'new_item_permission': permission_results['new_item'],
            'administration_permission': permission_results['administration'],
        }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def opportunity_delete_permission(request, opportunity_permissions_id):
    if request.method == "POST":
        opportunity_permission_update = opportunity_permission.objects.get(opportunity_permissions_id=opportunity_permissions_id)
        opportunity_permission_update.is_deleted = "TRUE"
        opportunity_permission_update.change_user = request.user
        opportunity_permission_update.save()

        # RETURN BLANK PAGE
        t = loader.get_template('NearBeach/blank.html')

        c = {}

        return HttpResponse(t.render(c, request))

    else:
        return HttpResponseBadRequest("Sorry, this has to be through post")




@login_required(login_url='login')
def opportunity_information(request, opportunity_id):
    permission_results = return_user_permission_level(request, None,'opportunity')

    if permission_results['opportunity']  == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    """
    Test User Access
    ~~~~~~~~~~~~~~~~
    A user who wants to access this Opportunity will need to meet one of these two conditions
    1. They have an access to  a group whom has been granted access to this Opportunity
    2. They are a super user (they should be getting access to all objects)
    """
    object_access = object_assignment.objects.filter(
        is_deleted="FALSE",
        opportunity_id=opportunity_id,
        group_id__in=user_group.objects.filter(
            is_deleted="FALSE",
            username=request.user,
        ).values('group_id')
    )
    if object_access.count() == 0 and not permission_results['administration'] == 4:
        return HttpResponseRedirect(reverse('permission_denied'))


    if request.method == "POST":
        form = opportunity_information_form(request.POST, request.FILES)
        if form.is_valid():
            current_user = request.user

            save_opportunity = opportunity.objects.get(opportunity_id=opportunity_id)

            # Save opportunity information
            save_opportunity.opportunity_name = form.cleaned_data['opportunity_name']
            save_opportunity.opportunity_description = form.cleaned_data['opportunity_description']
            save_opportunity.opportunity_amount = form.cleaned_data['opportunity_amount']
            save_opportunity.opportunity_success_probability = form.cleaned_data['opportunity_success_probability']
            save_opportunity.opportunity_expected_close_date=form.cleaned_data['opportunity_expected_close_date']
            save_opportunity.change_user=request.user

            # Instance needed
            save_opportunity.currency_id = list_of_currency.objects.get(currency_id=int(request.POST['currency_id']))
            save_opportunity.amount_type_id = list_of_amount_type.objects.get(
                amount_type_id=int(request.POST['amount_type_id']))
            save_opportunity.opportunity_stage_id = list_of_opportunity_stage.objects.get(
                opportunity_stage_id=int(request.POST['opportunity_stage_id']))


            #Save the opportunity
            save_opportunity.save()
            opportunity_instance = opportunity.objects.get(opportunity_id=opportunity_id)

            # Save the to-do if required
            next_step = form.cleaned_data['next_step']
            if not next_step == '':
                save_next_step = opportunity_next_step(
                    opportunity_id=opportunity_instance,
                    next_step_description=next_step,
                    change_user_id=request.user.id, #WHY???
                    user_id=current_user,
                )
                save_next_step.save()

            # If we need to add more users :D
            select_groups = form.cleaned_data['select_groups']
            if select_groups:
                for row in select_groups:
                    group_instance = group.objects.get(group_id=row.group_id)
                    permission_save = opportunity_permission(
                        opportunity_id=opportunity_instance,
                        group_id=group_instance,
                        user_id=current_user,
                        change_user=request.user,
                    )
                    permission_save.save()
                #Will remove the ALL USERS permissions now that we have limited the permissions
                opportunity_permission.objects.filter(
                    opportunity_id=opportunity_id,
                    all_user='TRUE',
                    is_deleted='FALSE'
                ).update(is_deleted='TRUE')

            select_users = form.cleaned_data['select_users']
            print(select_users)
            if select_users:
                for row in select_users:
                    assigned_user_instance = auth.models.User.objects.get(username=row)
                    permission_save = opportunity_permission(
                        opportunity_id=opportunity_instance,
                        assigned_user=assigned_user_instance,
                        user_id=current_user,
                        change_user=request.user,
                    )
                    permission_save.save()
                #Will remove the ALL USERS permissions now that we have limited the permissions
                opportunity_permission.objects.filter(
                    opportunity_id=opportunity_id,
                    all_user='TRUE',
                    is_deleted='FALSE'
                ).update(is_deleted='TRUE')
        else:
            print(form.errors)

    else:
        """
        We want to limit who can see what opportunity. The exception to this is for the user
        who just created the opportunity. (I should program in a warning stating that they
        might not be able to see the opportunity again unless they add themselfs to the 
        permissions list.

        The user has to meet at least one of these conditions;
        1.) User has permission
        2.) User's group has permission
        3.) All users have permission
        """
        user_groups_results = user_group.objects.filter(username=request.user)

        opportunity_permission_results = object_assignment.objects.filter(
            Q(
                Q(assigned_user=request.user)  # User has permission
                | Q(group_id__in=user_groups_results.values('group_id'))  # User's group have permission
            )
            & Q(opportunity_id=opportunity_id)
        )


        if (not opportunity_permission_results):
            return HttpResponseRedirect(
                reverse(
                    permission_denied,
                )
            )


    # Data
    project_results = project_opportunity.objects.filter(
        opportunity_id=opportunity_id,
        is_deleted='FALSE',
    )
    task_results = task_opportunity.objects.filter(
        opportunity_id=opportunity_id,
        is_deleted='FALSE',
    )
    opportunity_results = opportunity.objects.get(opportunity_id=opportunity_id)
    customer_results = customer.objects.filter(organisation_id=opportunity_results.organisation_id)
    group_permissions = object_assignment.objects.filter(
        group_id__isnull=False,
        opportunity_id=opportunity_id,
        is_deleted='FALSE',
    ).distinct()
    user_permissions = auth.models.User.objects.filter(
        id__in=object_assignment.objects.filter(
            assigned_user__isnull=False,
            opportunity_id=opportunity_id,
            is_deleted='FALSE',
        ).values('assigned_user').distinct()
    )

    quote_results = quote.objects.filter(
        is_deleted='FALSE',
        opportunity_id=opportunity_id,
    )
    print(user_permissions)

    end_hour = opportunity_results.opportunity_expected_close_date.hour
    end_meridiem = u'AM'

    print(str(end_hour))

    if end_hour > 12:
        end_hour = end_hour - 12
        end_meridiem = 'PM'
    elif end_hour == 0:
        end_hour = 12

    # initial data
    initial = {
        'finish_date_year': opportunity_results.opportunity_expected_close_date.year,
        'finish_date_month': opportunity_results.opportunity_expected_close_date.month,
        'finish_date_day': opportunity_results.opportunity_expected_close_date.day,
        'finish_date_hour': end_hour,
        'finish_date_minute': opportunity_results.opportunity_expected_close_date.minute,
        'finish_date_meridiems': end_meridiem,
    }

    # Loaed the template
    t = loader.get_template('NearBeach/opportunity_information.html')

    c = {
        'opportunity_id': str(opportunity_id),
        'opportunity_information_form': opportunity_information_form(
            instance=opportunity_results,
            initial=initial,
        ),
        'opportunity_results': opportunity_results,
        'customer_results': customer_results,
        'group_permission': group_permissions,
        'user_permissions': user_permissions,
        'project_results': project_results,
        'task_results': task_results,
        'quote_results': quote_results,
        'opportunity_perm': permission_results['opportunity'],
        'timezone': settings.TIME_ZONE,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'permission': permission_results['opportunity'],
    }

    return HttpResponse(t.render(c, request))




@login_required(login_url='login')
def organisation_information(request, organisation_id):
    permission_results = return_user_permission_level(request, None,['organisation','organisation_campus','customer'])

    if permission_results['organisation'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    if permission_results['organisation'] == 1:
        return HttpResponseRedirect(reverse('organisation_readonly',args={ organisation_id }))


    # Get the data from the form if the information has been submitted
    if request.method == "POST" and permission_results['organisation'] > 1:
        form = organisation_information_form(request.POST, request.FILES)
        if form.is_valid():
            save_data = organisation.objects.get(organisation_id=organisation_id)


            # Extract it from website
            save_data.organisation_name = form.cleaned_data['organisation_name']
            save_data.organisation_website = form.cleaned_data['organisation_website']
            save_data.change_user=request.user

            # Check to see if the picture has been updated
            update_profile_picture = request.FILES.get('update_profile_picture')
            if not update_profile_picture == None:
                save_data.organisation_profile_picture = update_profile_picture

            # Save
            save_data.save()

    # Query the database for organisation information
    organisation_results = organisation.objects.get(pk=organisation_id)
    campus_results = campus.objects.filter(
        organisation_id=organisation_id,
        is_deleted="FALSE",
    )
    customer_results = customer.objects.filter(
        organisation_id=organisation_results,
        is_deleted="FALSE",
    )
    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        organisation_id=organisation_id,
    )


    project_results = project.objects.filter(
        organisation_id=organisation_id,
        is_deleted="FALSE",
    )
    task_results = task.objects.filter(
        organisation_id=organisation_id,
        is_deleted="FALSE",
    )
    """
    We need to limit the amount of opportunities to those that the user has access to.
    """
    #user_groups_results = user_group.objects.filter(username=request.user)


    opportunity_results = opportunity.objects.filter(
        is_deleted="FALSE",
        organisation_id=organisation_id,
    )


    # Date required to initiate date
    today = datetime.datetime.now()

    # Loaed the template
    t = loader.get_template('NearBeach/organisation_information.html')

    # profile picture


    try:
        profile_picture = organisation_results.organisation_profile_picture.url
    except:
        profile_picture = ''


    c = {
        'organisation_results': organisation_results,
        'campus_results': campus_results,
        'customer_results': customer_results,
        'organisation_information_form': organisation_information_form(
            instance=organisation_results,
            initial={
                'start_date_year': today.year,
                'start_date_month': today.month,
                'start_date_day': today.day,
            }),
        'profile_picture': profile_picture,
        'project_results': project_results,
        'task_results': task_results,
        'opportunity_results': opportunity_results,
        'PRIVATE_MEDIA_URL': settings.PRIVATE_MEDIA_URL,
        'organisation_id': organisation_id,
        'organisation_permissions': permission_results['organisation'],
        'organisation_campus_permissions': permission_results['organisation_campus'],
        'customer_permissions': permission_results['customer'],
        'quote_results':quote_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))

@login_required(login_url='login')
def organisation_readonly(request, organisation_id):
    permission_results = return_user_permission_level(request, None,
                                                      ['organisation', 'organisation_campus', 'customer'])

    if permission_results['organisation'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))


    # Query the database for organisation information
    organisation_results = organisation.objects.get(pk=organisation_id)
    campus_results = campus.objects.filter(
        organisation_id=organisation_id,
        is_deleted="FALSE",
    )
    customer_results = customer.objects.filter(
        organisation_id=organisation_results,
        is_deleted="FALSE",
    )
    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        organisation_id=organisation_id,
    )

    project_results = project.objects.filter(
        organisation_id=organisation_id,
        is_deleted="FALSE",
    )
    task_results = task.objects.filter(
        organisation_id=organisation_id,
        is_deleted="FALSE",
    )
    """
    We need to limit the amount of opportunities to those that the user has access to.
    """
    opportunity_results = opportunity.objects.filter(
        is_deleted="FALSE",
        organisation_id=organisation_id,
    )

    contact_history_results = contact_history.objects.filter(
        is_deleted="FALSE",
        organisation_id=organisation_id,
    )

    """
    We want to bring through the project history's tinyMCE widget as a read only. However there are 
    most likely multiple results so we will create a collective.
    """
    contact_history_collective = []
    for row in contact_history_results:
        # First deal with the datetime
        contact_history_collective.append(
            contact_history_readonly_form(
                initial={
                    'contact_history': row.contact_history,
                    'submit_history': row.user_id.username + " - " + row.date_created.strftime("%d %B %Y %H:%M.%S"),
                },
                contact_history_id=row.contact_history_id,
            ),
        )

    email_results = email_content.objects.filter(
        is_deleted="FALSE",
        email_content_id__in=email_contact.objects.filter(
            Q(is_deleted="FALSE") &
            Q(organisation_id=organisation_id) &
            Q(
                Q(is_private=False) |
                Q(change_user=request.user)
            )
        ).values('email_content_id')
    )

    # Date required to initiate date
    today = datetime.datetime.now()

    # Loaed the template
    t = loader.get_template('NearBeach/organisation_information/organisation_readonly.html')

    # profile picture

    try:
        profile_picture = organisation_results.organisation_profile_picture.url
    except:
        profile_picture = ''

    c = {
        'organisation_results': organisation_results,
        'campus_results': campus_results,
        'customer_results': customer_results,
        'organisation_readonly_form': organisation_readonly_form(
            instance=organisation_results,
            ),
        'profile_picture': profile_picture,
        'project_results': project_results,
        'task_results': task_results,
        'opportunity_results': opportunity_results,
        'PRIVATE_MEDIA_URL': settings.PRIVATE_MEDIA_URL,
        'organisation_id': organisation_id,
        'organisation_permissions': permission_results['organisation'],
        'organisation_campus_permissions': permission_results['organisation_campus'],
        'customer_permissions': permission_results['customer'],
        'quote_results': quote_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'contact_history_collective': contact_history_collective,
        'email_results': email_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def permission_denied(request):
    #The user has no access to this page
    # Load the template
    t = loader.get_template('NearBeach/permission_denied.html')

    # context
    c = {
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def permission_set_information(request,permission_set_id):
    permission_results = return_user_permission_level(request, None, 'administration_create_permission_set')

    if permission_results['administration_create_permission_set'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    #DO POST STUFF HERE

    # Get data
    permission_set_results = permission_set.objects.get(permission_set_id=permission_set_id)

    # Load the template
    t = loader.get_template('NearBeach/permission_set_information.html')

    c = {
        'permission_set_form': permission_set_form(
            initial={
                'permission_set_name': permission_set_results.permission_set_name,
                'administration_assign_user_to_group': permission_set_results.administration_assign_user_to_group,
                'administration_create_group': permission_set_results.administration_create_group,
                'administration_create_permission_set': permission_set_results.administration_create_permission_set,
                'administration_create_user': permission_set_results.administration_create_user,
                'assign_campus_to_customer': permission_set_results.assign_campus_to_customer,
                'associate_project_and_task': permission_set_results.associate_project_and_task,
                'customer': permission_set_results.customer,
                'invoice': permission_set_results.invoice,
                'invoice_product': permission_set_results.invoice_product,
                'opportunity': permission_set_results.opportunity,
                'organisation': permission_set_results.organisation,
                'organisation_campus': permission_set_results.organisation_campus,
                'project': permission_set_results.project,
                'requirement': permission_set_results.requirement,
                'requirement_link': permission_set_results.requirement_link,
                'task': permission_set_results.task,
                'document': permission_set_results.document,
                'contact_history': permission_set_results.contact_history,
                'project_history': permission_set_results.project_history,
                'task_history': permission_set_results.task_history,
            }
        ),
        'permission_set_id': permission_set_id,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c,request))


"""
Issue - preview_quote will ask extract_quote to login. To remove this issue we have added the ability for UUID,
so the chances of a random user guessing the URL will be very small.
"""
def preview_quote(request,quote_uuid,quote_template_id):
    #Get data
    quote_results = quote.objects.get(quote_uuid=quote_uuid)
    quote_id = quote_results.quote_id

    product_results = quote_product_and_service.objects.filter(
        is_deleted="FALSE",
        #product_and_service.product_or_service = "product",
        product_and_service__in=product_and_service.objects.filter(
            product_or_service="Product",
        ).values('pk'),
        quote_id=quote_id,
    )
    service_results = quote_product_and_service.objects.filter(
        is_deleted="FALSE",
        # product_and_service.product_or_service = "product",
        product_and_service__in=product_and_service.objects.filter(
            product_or_service="Service",
        ).values('pk'),
        quote_id=quote_id,
    )

    quote_template_results = quote_template.objects.get(quote_template_id=quote_template_id)

    """
    The following section will extract the template fields and then do a simple mail merge until all the required
    template fields are JUST strings. This is the function update_template_strings
    """

    template_css = update_template_strings(quote_template_results.template_css,quote_results)
    header = update_template_strings(quote_template_results.header,quote_results)
    company_letter_head = update_template_strings(quote_template_results.company_letter_head,quote_results)
    payment_terms = update_template_strings(quote_template_results.payment_terms,quote_results)
    notes = update_template_strings(quote_template_results.notes,quote_results)
    organisation_details = update_template_strings(quote_template_results.organisation_details,quote_results)
    product_line = update_template_strings(quote_template_results.product_line,quote_results)
    service_line = update_template_strings(quote_template_results.service_line,quote_results)
    payment_method = update_template_strings(quote_template_results.payment_method,quote_results)
    footer = update_template_strings(quote_template_results.footer,quote_results)

    #Collect all the SUM information
    product_unadjusted_price=product_results.aggregate(Sum('product_price'))
    product_discount=product_results.aggregate(Sum('discount_amount'))
    product_sales_price=product_results.aggregate(Sum('sales_price'))
    product_tax=product_results.aggregate(Sum('tax'))
    product_total=product_results.aggregate(Sum('total'))

    service_unadjusted_price=service_results.aggregate(Sum('product_price'))
    service_discount=service_results.aggregate(Sum('discount_amount'))
    service_sales_price=service_results.aggregate(Sum('sales_price'))
    service_tax=service_results.aggregate(Sum('tax'))
    service_total=service_results.aggregate(Sum('total'))


    #Get Date
    current_date = datetime.datetime.now()

    # Load the template
    t = loader.get_template('NearBeach/render_templates/quote_template.html')

    # context
    c = {
        'template_css': template_css,
        'header': header,
        'company_letter_head': company_letter_head,
        'payment_terms': payment_terms,
        'notes': notes,
        'organisation_details': organisation_details,
        'product_line': product_line,
        'service_line': service_line,
        'payment_method': payment_method,
        'footer': footer,
        'product_unadjusted_price': product_unadjusted_price,
        'product_discount': product_discount,
        'product_sales_price': product_sales_price,
        'product_tax': product_tax,
        'product_total': product_total,
        'service_unadjusted_price': service_unadjusted_price,
        'service_discount': service_discount,
        'service_sales_price': service_sales_price,
        'service_tax': service_tax,
        'service_total': service_total,
        'current_user': request.user,
        'quote_id': quote_id,
        'current_date': current_date,
        'quote_results': quote_results,
        'product_results': product_results,
        'service_results': service_results,
    }

    return HttpResponse(t.render(c,request))



"""
TEMP CODE
"""
@login_required(login_url='login')
def private_document(request, document_key):
    """
    This is temp code. Hopefully I will make this function
    a lot better
    """
    PRIVATE_MEDIA_ROOT = settings.PRIVATE_MEDIA_ROOT
    #Now get the document location and return that to the user.
    document_results=document.objects.get(pk=document_key)

    if document_results.document_url_location:
        return HttpResponseRedirect(document_results.document_url_location)

    path = PRIVATE_MEDIA_ROOT + '/' + document_results.document.name
    #path = '/home/luke/Downloads/gog_gods_will_be_watching_2.1.0.9.sh'

    """
    Serve private files to users with read permission.
    """
    #logger.debug('Serving {0} to {1}'.format(path, request.user))
    #if not permissions.has_read_permission(request, path):
    #    if settings.DEBUG:
    #        raise PermissionDenied
    #    else:
    #        raise Http404('File not found')
    return server.serve(request, path=path)


"""
END TEMP DOCUMENT
"""


@login_required(login_url='login')
def project_information(request, project_id):
    #First look at the user's permissions for the project's group.
    project_groups_results = object_assignment.objects.filter(
        is_deleted="FALSE",
        project_id=project_id,
    ).values('group_id_id')

    permission_results = return_user_permission_level(request, project_groups_results,['project','project_history'])

    if permission_results['project'] == 0:
        # Send them to permission denied!!
        return HttpResponseRedirect(reverse(permission_denied))

    """
    Test User Access
    ~~~~~~~~~~~~~~~~
    A user who wants to access this project will need to meet one of these two conditions
    1. They have an access to  a group whom has been granted access to this project
    2. They are a super user (they should be getting access to all objects)
    """
    object_access = object_assignment.objects.filter(
        is_deleted="FALSE",
        project_id=project_id,
        group_id__in=user_group.objects.filter(
            is_deleted="FALSE",
            username=request.user,
        ).values('group_id')
    )
    if object_access.count() == 0 and not permission_results['administration'] == 4:
        return HttpResponseRedirect(reverse('permission_denied'))



    """
	There are two buttons on the project information page. Both will come
	here. Both will save the data, however only one of them will resolve
	this project.
	"""
    # Get the data from the form if the information has been submitted
    if request.method == "POST" and permission_results['project'] >= 2: #Greater than edit :)
        form = project_information_form(request.POST, request.FILES)
        if form.is_valid():
            # Define the data we will edit
            project_results = project.objects.get(project_id=project_id)

            project_results.project_name = form.cleaned_data['project_name']
            project_results.project_description = form.cleaned_data['project_description']
            project_results.project_start_date = form.cleaned_data['project_start_date']
            project_results.project_end_date = form.cleaned_data['project_end_date']

            # Check to make sure the resolve button was hit
            if 'Resolve' in request.POST:
                # Well, we have to now resolve the data
                project_results.project_status = 'Resolved'

            project_results.change_user=request.user
            project_results.save()

            """
            Now we need to update any kanban board cards connected to this project.
            """
            kanban_card_results = kanban_card.objects.filter(
                is_deleted="FALSE",
                project_id=project_id
            )
            for row in kanban_card_results:
                row.kanban_card_text = "PRO" + str(project_id) + " - " + form.cleaned_data['project_name']
                row.save()
        else:
            print(form.errors)

    project_results = get_object_or_404(project, project_id=project_id)
    opportunity_results = project_opportunity.objects.filter(
        is_deleted="FALSE",
        project_id=project_id,
    )

    #If project is completed - send user to read only module
    if project_results.project_status == "Closed" or project_results.project_status == "Resolved":
        return HttpResponseRedirect(reverse('project_readonly', args={project_id}))

    # Obtain the required data
    project_history_results = project_history.objects.filter(project_id=project_id, is_deleted='FALSE')
    cursor = connection.cursor()


    folders_results = folder.objects.filter(
        project_id=project_id,
        is_deleted='FALSE'
    ).order_by(
        'folder_description'
    )


    # Setup the initial data for the form
    initial = {
        'project_name': project_results.project_name,
        'project_description': project_results.project_description,
        'project_start_date': project_results.project_start_date,
        'project_end_date': project_results.project_end_date,
    }

    associated_task_results = task.objects.filter(
        is_deleted="FALSE",
        task_id__in=project_task.objects.filter(
            is_deleted="FALSE",
            project_id=project_id,
        ).values('task_id')
    )


    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        project_id = project_results,
    )


    # Load the template
    t = loader.get_template('NearBeach/project_information.html')

    # context
    c = {
        'project_information_form': project_information_form(initial=initial),
        'information_project_history_form': information_project_history_form(),
        'project_results': project_results,
        'associated_task_results': associated_task_results,
        'project_history_results': project_history_results,
        'folders_results': serializers.serialize('json', folders_results),
        'media_url': settings.MEDIA_URL,
        'quote_results': quote_results,
        'project_id': project_id,
        'permission': permission_results['project'],
        'project_history_permissions': permission_results['project_history'],
        'timezone': settings.TIME_ZONE,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'opportunity_results': opportunity_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def project_readonly(request, project_id):
    project_groups_results = object_assignment.objects.filter(
        is_deleted="FALSE",
        project_id=project.objects.get(project_id=project_id),
    ).values('group_id_id')

    permission_results = return_user_permission_level(request, project_groups_results, ['project', 'project_history'])

    #Get data
    project_results = project.objects.get(project_id=project_id)
    to_do_results = to_do.objects.filter(
        is_deleted="FALSE",
        project_id=project_id,
    )
    project_history_results = project_history.objects.filter(
        is_deleted="FALSE",
        project_id=project_id,
    )
    email_results = email_content.objects.filter(
        is_deleted="FALSE",
        email_content_id__in=email_contact.objects.filter(
            Q(project=project_id) &
            Q(is_deleted="FALSE") &
            Q(
                Q(is_private=False) |
                Q(change_user=request.user)
            )
        ).values('email_content_id')
    )

    associated_tasks_results = project_task.objects.filter(
        is_deleted="FALSE",
        project_id=project_id,
    )

    project_customers_results = project_customer.objects.filter(
        is_deleted="FALSE",
        project_id=project_id,

    )

    costs_results = cost.objects.filter(
        project_id=project_id,
        is_deleted='FALSE'
    )

    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        project_id=project_id,
    )

    bug_results = bug.objects.filter(
        is_deleted="FALSE",
        project_id=project_id,
    )

    assigned_results = object_assignment.objects.filter(
        project_id=project_id,
        is_deleted="FALSE",
    ).exclude(
        assigned_user=None,
    ).values(
        'assigned_user__id',
        'assigned_user',
        'assigned_user__username',
        'assigned_user__first_name',
        'assigned_user__last_name',
    ).distinct()


    group_list_results = object_assignment.objects.filter(
        is_deleted="FALSE",
        project_id=project_id,
    )

    kudos_results = kudos.objects.filter(
        project_id=project_id,
        is_deleted="FALSE",
    )

    """
    We want to bring through the project history's tinyMCE widget as a read only. However there are 
    most likely multiple results so we will create a collective.
    """
    project_history_collective =[]
    for row in project_history_results:
        #First deal with the datetime
        project_history_collective.append(
            project_history_readonly_form(
                initial={
                    'project_history': row.project_history,
                    'submit_history': row.user_infomation + " - " + str(row.user_id) + " - "\
                                      + row.date_created.strftime("%d %B %Y %H:%M.%S"),
                },
                project_history_id=row.project_history_id,
            )
        )


    #Get Template
    t = loader.get_template('NearBeach/project_information/project_readonly.html')

    # context
    c = {
        'project_id': project_id,
        'project_results': project_results,
        'project_readonly_form': project_readonly_form(
            initial={'project_description': project_results.project_description}
        ),
        'kudos_results': kudos_results,
        'to_do_results': to_do_results,
        'project_history_collective': project_history_collective,
        'email_results': email_results,
        'associated_tasks_results': associated_tasks_results,
        'project_customers_results': project_customers_results,
        'costs_results': costs_results,
        'quote_results': quote_results,
        'bug_results': bug_results,
        'assigned_results': assigned_results,
        'group_list_results': group_list_results,
        'project_permissions': permission_results['project'],
        'project_history_permissions': permission_results['project_history'],
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],

    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def project_remove_customer(request,project_customer_id):
    if request.method == "POST":
        project_customer_update = project_customer.objects.get(
            project_customer_id=project_customer_id
        )
        project_customer_update.is_deleted="TRUE"
        project_customer_update.change_user=request.user
        project_customer_update.save()


        #Return blank page
        t = loader.get_template('NearBeach/blank.html')
        c = {}
        return HttpResponse(t.render(c, request))
    else:
        return HttpResponseBadRequest("Can only do this through POST")


@login_required(login_url='login')
def quote_information(request, quote_id):
    permission_results = return_user_permission_level(request, None, 'quote')

    if permission_results['quote'] == 0:
        return HttpResponseRedirect(reverse(permission_denied))

    """
    Test User Access
    ~~~~~~~~~~~~~~~~
    A user who wants to access this quote will need to meet one of these two conditions
    1. They have an access to  a group whom has been granted access to this quote
    2. They are a super user (they should be getting access to all objects)
    """
    object_access = object_assignment.objects.filter(
        is_deleted="FALSE",
        quote_id=quote_id,
        group_id__in=user_group.objects.filter(
            is_deleted="FALSE",
            username=request.user,
        ).values('group_id')
    )
    if object_access.count() == 0 and not permission_results['administration'] == 4:
        return HttpResponseRedirect(reverse('permission_denied'))

    #Get the quote information
    quotes_results = quote.objects.get(quote_id=quote_id)

    """
    If any of the following conditions are met, we want to send the user to the read only module.
    - Quote's status is 'Quote Close Accepted'
    - Quote's status is 'Quote Close Rejected'
    - Quote's status is 'Quote Close Lost'
    - Quote's status is 'Quote Close Dead'
    - Invoice's status is 'Invoice Close Accepted'
    - Invoice's status is 'Invoice Close Rejected'
    - Invoice's status is 'Invoice Close Lost'
    - Invoice's status is 'Invoice Close Dead'
    - User only have read only permissions
    
    The above quote/invoice status have the "Closed" statement as true in the table 'list_of_quote_stages'. We just 
    need to check this status in that table.
    """
    print("QUOTE STAGE: " + str(quotes_results.quote_stage_id))
    if quotes_results.quote_stage_id.quote_closed == "TRUE" or permission_results['quote'] == 1:
        return HttpResponseRedirect(reverse('quote_readonly', args = { quote_id }))

    quote_template_results = quote_template.objects.filter(
        is_deleted="FALSE",
    )

    if request.method == "POST":
        form = quote_information_form(request.POST,quote_instance=quotes_results)
        if form.is_valid():
            #Extract the information from the forms
            quotes_results.quote_title = form.cleaned_data['quote_title']
            quotes_results.quote_terms = form.cleaned_data['quote_terms']
            quotes_results.quote_stage_id = form.cleaned_data['quote_stage_id']
            quotes_results.customer_notes = form.cleaned_data['customer_notes']
            quotes_results.quote_billing_address = form.cleaned_data['quote_billing_address']
            quotes_results.quote_valid_till = form.cleaned_data['quote_valid_till']

            #Check to see if we have to move quote to invoice
            if 'create_invoice' in request.POST:
                quotes_results.is_invoice = 'TRUE'
                quotes_results.quote_stage_id = list_of_quote_stage.objects.filter(is_invoice='TRUE').order_by('sort_order')[0]

            #Check to see if we have to revert the invoice to a quote
            if 'revert_quote' in request.POST:
                quotes_results.is_invoice = 'FALSE'
                quotes_results.quote_stage_id = list_of_quote_stage.objects.filter(is_invoice='FALSE').order_by('sort_order')[0]


            quotes_results.change_user=request.user
            quotes_results.save()

        else:
            print(form.errors)
    else:
        """
        We want to limit who can see what quote. The exception to this is for the user
        who just created the quote. (I should program in a warning stating that they
        might not be able to see the quote again unless they add themselves to the 
        permissions list.

        The user has to meet at least one of these conditions;
        1.) User has permission
        2.) User's group has permission
        3.) All users have permission
        """
        user_groups_results = user_group.objects.filter(username=request.user)

        quote_permission_results = object_assignment.objects.filter(
            Q(
                Q(assigned_user=request.user) # User has permission
                | Q(group_id__in=user_groups_results.values('group_id')) # User's group have permission
            )
            & Q(quote_id=quote_id)
            & Q(is_deleted="FALSE")
        )

        if (not quote_permission_results):
            return HttpResponseRedirect(
                reverse(
                    permission_denied,
                )
            )




    #Determine if quote or invoice
    quote_or_invoice = 'Quote'
    if quotes_results.is_invoice == 'TRUE':
        quote_or_invoice = 'Invoice'

    """
    	The 24 hours to 12 hours formula.
    	00:00 means that it is 12:00 AM - change required for hour
    	01:00 means that it is 01:00 AM - no change required
    	12:00 means that it is 12:00 PM - change required for meridiem
    	13:00 means that it is 01:00 PM - change required for hour and meridiem
    	"""
    quote_valid_till_hour = quotes_results.quote_valid_till.hour
    quote_valid_till_meridiem = u'AM'
    if quote_valid_till_hour == 0:
        quote_valid_till_hour = 12
    elif quote_valid_till_hour == 12:
        quote_valid_till_meridiem = u'PM'
    elif quote_valid_till_hour > 12:
        start_hour = quote_valid_till_hour - 12
        quote_valid_till_meridiem = u'PM'

    # Setup the initial data for the form
    initial = {
        'quote_title': quotes_results.quote_title,
        'quote_terms': quotes_results.quote_terms,
        'quote_stage_id': quotes_results.quote_stage_id.quote_stage_id,
        'quote_valid_till_year': quotes_results.quote_valid_till.year,
        'quote_valid_till_month': quotes_results.quote_valid_till.month,
        'quote_valid_till_day': quotes_results.quote_valid_till.day,
        'quote_valid_till_hour': quote_valid_till_hour,
        'quote_valid_till_minute': quotes_results.quote_valid_till.minute,
        'quote_valid_till_meridiem': quote_valid_till_meridiem,
        'customer_notes': quotes_results.customer_notes,
        'quote_billing_address': quotes_results.quote_billing_address,
    }

    # Load the template
    t = loader.get_template('NearBeach/quote_information.html')


    # context
    c = {
        'quotes_results': quotes_results,
        'quote_information_form': quote_information_form(
            initial=initial,
            quote_instance=quotes_results,
        ),
        'quote_id': quote_id,
        'quote_or_invoice': quote_or_invoice,
        'timezone': settings.TIME_ZONE,
        'quote_template_results': quote_template_results,
        'permission': permission_results['quote'],
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))




@login_required(login_url='login')
def quote_template_information(request,quote_template_id):
    permission_results = return_user_permission_level(request, None, 'template')

    if permission_results['template'] == 0:
        return HttpResponseRedirect(reverse(permission_denied))

    if request.method == "POST":
        form=quote_template_form(request.POST)
        if form.is_valid():
            quote_template_save=quote_template.objects.get(
                quote_template_id=quote_template_id,
            )
            quote_template_save.change_user=request.user
            quote_template_save.quote_template_description=form.cleaned_data['quote_template_description']
            quote_template_save.template_css=form.cleaned_data['template_css']
            quote_template_save.header= form.cleaned_data['header']
            quote_template_save.company_letter_head= form.cleaned_data['company_letter_head']
            quote_template_save.payment_terms= form.cleaned_data['payment_terms']
            quote_template_save.notes= form.cleaned_data['notes']
            quote_template_save.organisation_details= form.cleaned_data['organisation_details']
            #quote_template_save.product_line= form.cleaned_data['product_line']
            #quote_template_save.service_line= form.cleaned_data['service_line']
            quote_template_save.payment_method= form.cleaned_data['payment_method']
            quote_template_save.footer= form.cleaned_data['footer']
            quote_template_save.page_layout= form.cleaned_data['page_layout']
            quote_template_save.margin_left= form.cleaned_data['margin_left']
            quote_template_save.margin_right= form.cleaned_data['margin_right']
            quote_template_save.margin_top= form.cleaned_data['margin_top']
            quote_template_save.margin_bottom= form.cleaned_data['margin_bottom']
            quote_template_save.margin_header= form.cleaned_data['margin_header']
            quote_template_save.margin_footer= form.cleaned_data['margin_footer']

            if request.POST.get("delete_quote_template"):
                quote_template_save.is_deleted="TRUE"
                quote_template_save.save()
                return HttpResponseRedirect(reverse(search_templates))

            quote_template_save.save()

        else:
            print(form.errors)

    #Get data
    quote_template_results = quote_template.objects.get(quote_template_id=quote_template_id)

    # Load the template
    t = loader.get_template('NearBeach/quote_template_information.html')


    # context
    c = {
        'quote_template_form': quote_template_form(initial={
            'quote_template_description': quote_template_results.quote_template_description,
            'template_css': quote_template_results.template_css,
            'header': quote_template_results.header,
            'company_letter_head': quote_template_results.company_letter_head,
            'payment_terms': quote_template_results.payment_terms,
            'notes': quote_template_results.notes,
            'organisation_details': quote_template_results.organisation_details,
            'product_line': quote_template_results.product_line,
            'service_line': quote_template_results.service_line,
            'payment_method': quote_template_results.payment_method,
            'footer': quote_template_results.footer,
            'page_layout': quote_template_results.page_layout,
            'margin_left': quote_template_results.margin_left,
            'margin_right': quote_template_results.margin_right,
            'margin_top': quote_template_results.margin_top,
            'margin_bottom': quote_template_results.margin_bottom,
            'margin_header': quote_template_results.margin_header,
            'margin_footer': quote_template_results.margin_footer,
        }),
        'quote_template_id': quote_template_id,
        'quote_permission': permission_results['template'],
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def quote_readonly(request, quote_id):
    permission_results = return_user_permission_level(request, None, 'quote')

    if permission_results['quote'] == 0:
        return HttpResponseRedirect(reverse(permission_denied))


    #Get required data
    quote_results = quote.objects.get(quote_id=quote_id)

    line_item_results = quote_product_and_service.objects.filter(
        is_deleted='FALSE',
        quote_id=quote_id,
    )

    product_line_items = quote_product_and_service.objects.filter(
        quote_id=quote_id,
        product_and_service__product_or_service='Product',
        is_deleted="FALSE",
    )

    service_line_items = quote_product_and_service.objects.filter(
        quote_id=quote_id,
        product_and_service__product_or_service='Service',
        is_deleted="FALSE",
    )

    responsible_customer_results = customer.objects.filter(
        customer_id__in=quote_responsible_customer.objects.filter(
            quote_id=quote_id,
            is_deleted="FALSE"
        ).values('customer_id').distinct()
    )

    email_results = email_content.objects.filter(
        is_deleted="FALSE",
        email_content_id__in=email_contact.objects.filter(
            Q(quotes=quote_id) &
            Q(is_deleted="FALSE") &
            Q(
                Q(is_private=False) |
                Q(change_user=request.user)
            )
        ).values('email_content_id')
    )

    quote_template_results = quote_template.objects.filter(
        is_deleted="FALSE",
    )

    group_list_results = object_assignment.objects.filter(
        is_deleted="FALSE",
        quote_id=quote_id,
    ).exclude(
        group_id=None,
    )

    assigned_user_results = object_assignment.objects.filter(
        is_deleted="FALSE",
        quote_id=quote_id,
    ).exclude(
        assigned_user=None,
    )

    # Get template
    t = loader.get_template('NearBeach/quote_information/quote_readonly.html')

    # Context
    c = {
        'quote_results': quote_results,
        'quote_readonly_form': quote_readonly_form(
            initial={
                'quote_terms': quote_results.quote_terms,
                'customer_notes': quote_results.customer_notes,
            }
        ),
        'timezone': settings.TIME_ZONE,
        'line_item_results': line_item_results,
        'product_line_items': product_line_items,
        'service_line_items': service_line_items,
        'responsible_customer_results': responsible_customer_results,
        'email_results': email_results,
        'quote_template_results': quote_template_results,
        'group_list_results': group_list_results,
        'assigned_user_results': assigned_user_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c,request))


@login_required(login_url='login')
def rename_document(request, document_key):
    if request.method == "POST":
        print(request)
    else:
        return HttpResponseBadRequest("This is a POST function. POST OFF!")


@login_required(login_url='login')
def resolve_project(request, project_id):
    project_update = project.objects.get(project_id=project_id)
    project_update.project_status = 'Resolved'
    project_update.change_user=request.user
    project_update.save()
    return HttpResponseRedirect(reverse('dashboard'))


@login_required(login_url='login')
def resolve_task(request, task_id):
    task_update = task.objects.get(task_id=task_id)
    task_update.task_status = 'Resolved'
    task_update.change_user=request.user
    task_update.save()
    return HttpResponseRedirect(reverse('dashboard'))


@login_required(login_url='login')
def search(request):
    permission_results = return_user_permission_level(request, None, 'project')

    # Load the template
    t = loader.get_template('NearBeach/search.html')

    """
	We will use the POST varable to help filter the results from the 
	database. The results will then appear below
	"""
    search_results = ''


    # Define if the page is loading in POST
    if request.method == "POST":
        form = search_form(request.POST)
        if form.is_valid():
            search_results = form.cleaned_data['search_for']

    """
	This is where the magic happens. I will remove all spaces and replace
	them with a wild card. This will be used to search the concatenated
	first and last name fields
	"""
    search_like = '%'

    for split_row in search_results.split(' '):
        search_like += split_row
        search_like += '%'


    """
    Due to POSTGRESQL being a bit fussy when it comes to LIKE statements,
    we have had to make a work around. If the post results come back as an
    INT, we will feed them into the results as an INT. Otherwise 0 will be fed
    in.
    """
    int_results = 0
    if not search_results == '':
        if isinstance(search_results,int):
            int_results = int(search_results)


    # Query the database for organisation
    project_results = project.objects.extra(
        where=[
            """
            project_id = %s
            OR project_name LIKE %s
            OR project_description LIKE %s
            """,
            """
            is_deleted="FALSE"
            """
        ],
        params=[
            int(int_results),
            search_like,
            search_like,
        ]
    )

    # Get list of task
    task_results = task.objects.extra(
        where=[
            """
            task_id = %s
            OR task_short_description LIKE %s
            OR task_long_description LIKE %s
            """,
            """
            is_deleted="FALSE"
            """
        ],
        params=[
            int(int_results),
            search_like,
            search_like,
        ]
    )

    opportunity_results = opportunity.objects.all()
    requirement_results = requirement.objects.all()

    # context
    c = {
        'search_form': search_form(initial={'search_for': search_results}),
        'project_results': project_results,
        'task_results': task_results,
        'opportunity_results': opportunity_results,
        'requirement_results': requirement_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def search_customer(request):
    permission_results = return_user_permission_level(request, None, 'project')

    # Load the template
    t = loader.get_template('NearBeach/search_customer.html')

    """
	We will use the POST varable to help filter the results from the 
	database. The results will then appear below
	"""
    search_customer_results = ''

    # Define if the page is loading in POST
    if request.method == "POST":
        form = search_customer_form(request.POST)
        if form.is_valid():
            search_customer_results = form.cleaned_data['search_customer']

    """
	This is where the magic happens. I will remove all spaces and replace
	them with a wild card. This will be used to search the concatenated
	first and last name fields
	"""
    search_customer_like = '%'

    for split_row in search_customer_results.split(' '):
        search_customer_like += split_row
        search_customer_like += '%'

    """
    The annotate function gives the ability to concat the first and last name.
    This gives us the ability to;
    1.) Filter on the joined field
    2.) Display it as is to the customer
    """
    customer_results = customer.objects.filter(
        is_deleted="FALSE"
    ).annotate(
        customer_full_name=Concat(
            'customer_first_name',
            Value(' '),
            'customer_last_name',
        )
    ).extra(
        where=[
            """
            customer_first_name || customer_last_name LIKE %s
            """
        ],
        params=[
            search_customer_like,
        ]
    )

    # context
    c = {
        'search_customer_form': search_customer_form(initial={'search_customer': search_customer_results}),
        'customer_results': customer_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def search_group(request):
    """
    Brings up a list of all groups.
    :param request:
    :return:
    """
    permission_results = return_user_permission_level(request, None, 'administration_create_group')

    if permission_results['administration_create_group'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    #Data for group search
    group_results = group.objects.filter(
        is_deleted="FALSE"
    )

    #Load template
    t = loader.get_template('NearBeach/search_group.html')

    # context
    c = {
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
        'group_results': group_results,
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def search_organisation(request):
    permission_results = return_user_permission_level(request, None, 'project')

    # Load the template
    t = loader.get_template('NearBeach/search_organisations.html')

    """
	We will use the following varable to help filterer our database
	results. ***WrTIE BETTER TOO TIRED TO DESCRIBE THIS!!!***
	"""
    search_organisation_results = ''

    # Define if the page is loading in POST
    if request.method == "POST":
        form = search_organisation_form(request.POST)
        if form.is_valid():
            search_organisation_results = form.cleaned_data['search_organisation']

    """
	This is where the magic happens. I will remove all spaces and replace
	them with a wild card. This will be used to search the concatenated
	first and last name fields
	"""
    search_organisation_like = '%'

    for split_row in search_organisation_results.split(' '):
        search_organisation_like += split_row
        search_organisation_like += '%'

    # Now search the organisation
    # organisations_results = organisation.objects.filter(organisation_name__contains = search_organisation_like)

    # Query the database for organisation
    cursor = connection.cursor()
    cursor.execute("""
		SELECT DISTINCT
		  organisation.organisation_id
		, organisation.organisation_name
		, organisation.organisation_website
		, organisation.organisation_email
		FROM organisation
		WHERE 1=1
		AND organisation.organisation_name LIKE %s
		""", [search_organisation_like])
    organisations_results = namedtuplefetchall(cursor)

    # context
    c = {
        'search_organisation_form': search_organisation_form(
            initial={'search_organisation': search_organisation_results}),
        'organisations_results': organisations_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def search_permission_set(request):
    permission_results = return_user_permission_level(request, None, 'administration_create_permission_set')

    if permission_results['administration_create_permission_set'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    #Get data
    permission_set_results = permission_set.objects.filter(is_deleted="FALSE")

    # Load the template
    t = loader.get_template('NearBeach/search_permission_set.html')

    c = {
        'permission_set_results': permission_set_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c,request))


@login_required(login_url='login')
def search_projects_task(request):
    # Load the template
    t = loader.get_template('NearBeach/search_projects_and_task.html')

    print("Search project and task")

    # context
    c = {


    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def search_tags(request):
    """
    This search functionality allows the user to search NearBeach for tags. Tags are connected to the objects;
    - Projects
    - Tasks
    - Requirements
    - Opportunities

    This will bring back a result of ALL objects that contain that tag
    :param request:
    :return:

    Method
    ~~~~~~
    1. Check permissions - if you do not have permissions then you will be carted away
    2. Declare all variables
    3. Check to see if this is in POST
    """
    permission_results = return_user_permission_level(request, None, 'tag')
    if permission_results['tag'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))

    #Declaring variables
    search_for = ""
    search_form_form = search_form(request.POST or None)

    if request.method == "POST":
        if search_form_form.is_valid():
            #Lets get the form data
            search_for=search_form_form.cleaned_data['search_for']

    # Get data
    """
    These are the potential tags that match the search results. When blank - it will pull out all tags (as this can be
    used as a general search).
    """
    tag_assignment_results = tag_assignment.objects.filter(
        is_deleted="FALSE",
        tag_id__in=tag.objects.filter(
            is_deleted="FALSE",
            tag_name__contains=search_for,
        ).values('tag_id'),
    )

    """
    We want to limit the objects down to only those that the user has access to. We do not want to accidently show 
    projects/tasks/requirements/opportunities that are currently in other groups.
    
    The following object will check
    - Is the object still not deleted
    - Is the object in a list of objects that the user has access to (either via group or being assigned)
    - Is the object in the list of tag assignment results.
    """
    project_results = project.objects.filter(
        Q(is_deleted="FALSE") and
        Q(project_id__in=object_assignment.objects.filter(
            Q(is_deleted="FALSE",) and
            Q(
                Q(assigned_user_id=request.user.id) or
                Q(group_id__in=user_group.objects.filter(
                    is_deleted="FALSE",
                    username=request.user,
                ).values('group_id'))
            )
        ).values('project_id')) and
        Q(project_id__in=tag_assignment_results.filter(project_id__isnull=False).values('project_id'))
    )

    task_results = task.objects.filter(
        Q(is_deleted="FALSE") and
        Q(task_id__in=object_assignment.objects.filter(
            Q(is_deleted="FALSE", ) and
            Q(
                Q(assigned_user_id=request.user.id) or
                Q(group_id__in=user_group.objects.filter(
                    is_deleted="FALSE",
                    username=request.user,
                ).values('group_id'))
            )
        ).values('task_id')) and
        Q(task_id__in=tag_assignment_results.filter(task_id__isnull=False).values('task_id'))
    )

    requirement_results = requirement.objects.filter(
        Q(is_deleted="FALSE") and
        Q(requirement_id__in=object_assignment.objects.filter(
            Q(is_deleted="FALSE", ) and
            Q(
                Q(assigned_user_id=request.user.id) or
                Q(group_id__in=user_group.objects.filter(
                    is_deleted="FALSE",
                    username=request.user,
                ).values('group_id'))
            )
        ).values('requirement_id')) and
        Q(requirement_id__in=tag_assignment_results.filter(requirement_id__isnull=False).values('requirement_id'))
    )

    opportunity_results = opportunity.objects.filter(
        Q(is_deleted="FALSE") and
        Q(opportunity_id__in=object_assignment.objects.filter(
            Q(is_deleted="FALSE", ) and
            Q(
                Q(assigned_user_id=request.user.id) or
                Q(group_id__in=user_group.objects.filter(
                    is_deleted="FALSE",
                    username=request.user,
                ).values('group_id'))
            )
        ).values('opportunity_id')) and
        Q(opportunity_id__in=tag_assignment_results.filter(opportunity_id__isnull=False).values('opportunity_id'))
    )


    # Get template
    t = loader.get_template('NearBeach/search_tags.html')

    # Context
    c = {
        'search_form': search_form_form,
        'project_results': project_results,
        'task_results': task_results,
        'requirement_results': requirement_results,
        'opportunity_results': opportunity_results,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c,request))


@login_required(login_url='login')
def search_templates(request):
    permission_results = return_user_permission_level(request, None, 'templates')
    if permission_results['templates'] == 0:
        return HttpResponseRedirect(reverse('permission_denied'))


    quote_template_results=quote_template.objects.filter(
        is_deleted="FALSE",
    )

    # Load the template
    t = loader.get_template('NearBeach/search_templates.html')

    print("Search templates")

    # context
    c = {
        'quote_template_results': quote_template_results,
        'search_template_form': search_template_form(),
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def tag_information(request, location_id, destination):
    """
    Tag information is where the user requests tags for certain objects.

    :param request:
    :param location_id: the object id
    :param destination: the type of object, i.e. project, task, requirement, or opportunity
    :return: HTML for tag information

    Method
    ~~~~~~
    1. Check user permissions
    2. If POST, check comments in section - because it will save the tag
    3. Check which object type we are requesting for
    4. Gather the required data
    5. Send data to template and render
    6. Give the HTML to user. YAY :D
    """
    permission_results = return_user_permission_level(request, None, 'tag')
    #It does not matter if they have 0 for permission level. As we always want to show tags associated with the object.

    # Check to see if post
    if request.method == "POST":
        form = new_tag_form(request.POST)
        if form.is_valid():
            """
            Method
            ~~~~~~
            1. Extract the tag_name from the form
            2. Find out if the tag_name already exists
            3. If tag_name does not exist - create the new tag
            4. If tag_name does exist and is deleted, undelete it.
            4. Connect the current object to the tag :)
            5. Complete other method :) WOO
            """
            tag_name = form.cleaned_data['tag_name']

            #Find out if the tag already exists
            tag_instance = tag.objects.filter(tag_name=tag_name)


            #If tag_name does not exist - create it
            if not tag_instance:
                tag_submit = tag(
                    tag_name=tag_name,
                    change_user=request.user,
                )
                tag_submit.save()
                tag_instance = tag_submit
            else:
                tag_instance = tag_instance[0]  # Removes the filter :D

                if tag_instance.is_deleted == "TRUE":
                    #If tag_name does exist and is deleted, undelete it.
                    tag_instance.is_deleted = "FALSE"
                    tag_instance.save()

            #Connect the current object to the tag
            tag_assignment_submit = tag_assignment(
                tag_id=tag_instance,
                change_user=request.user,
            )

            # Which object?
            if destination == "project":
                tag_assignment_submit.project_id=project.objects.get(project_id=location_id)
            elif destination == "task":
                tag_assignment_submit.task_id = task.objects.get(task_id=location_id)
            elif destination == "opportunity":
                tag_assignment_submit.opportunity_id = opportunity.objects.get(opportunity_id=location_id)
            elif destination == "requirement":
                tag_assignment_submit.requirement_id = requirement.objects.get(requirement_id=location_id)

            tag_assignment_submit.save()

        else:
            print(form.errors)

    # Check object and get require data
    if destination == 'project':
        tag_results = tag.objects.filter(
            is_deleted="FALSE",
            tag_id__in=tag_assignment.objects.filter(
                is_deleted="FALSE",
                project_id=location_id,
            ).values('tag_id')
        )
    elif destination == "task":
        tag_results = tag.objects.filter(
            is_deleted="FALSE",
            tag_id__in=tag_assignment.objects.filter(
                is_deleted="FALSE",
                task_id=location_id,
            ).values('tag_id')
        )
    elif destination == "opportunity":
        tag_results = tag.objects.filter(
            is_deleted="FALSE",
            tag_id__in=tag_assignment.objects.filter(
                is_deleted="FALSE",
                opportunity_id=location_id,
            ).values('tag_id')
        )
    elif destination == "requirement":
        tag_results = tag.objects.filter(
            is_deleted="FALSE",
            tag_id__in=tag_assignment.objects.filter(
                is_deleted="FALSE",
                requirement_id=location_id,
            ).values('tag_id')
        )
    else:
        tag_results = None


    # Get all potential tags - for helping write tags
    tag_list_results = tag.objects.filter(
        is_deleted="FALSE",
    ).exclude(
        tag_id__in=tag_results.values('tag_id')
    )

    # Get template
    t = loader.get_template('NearBeach/tag_information.html')

    # Context
    c = {
        'tag_results': tag_results,
        'new_tag_form': new_tag_form(),
        'tag_permission': permission_results['tag'],
    }

    return HttpResponse(t.render(c,request))


@login_required(login_url='login')
def task_information(request, task_id):
    #First look at the user's permissions for the project's group.
    task_groups_results = object_assignment.objects.filter(
        is_deleted="FALSE",
        task_id=task.objects.get(task_id=task_id),
    ).values('group_id_id')

    permission_results = return_user_permission_level(request, task_groups_results,['task','task_history'])

    if permission_results['task'] == 0:
        # Send them to permission denied!!
        return HttpResponseRedirect(reverse(permission_denied))


    """
    Test User Access
    ~~~~~~~~~~~~~~~~
    A user who wants to access this task will need to meet one of these two conditions
    1. They have an access to  a group whom has been granted access to this task
    2. They are a super user (they should be getting access to all objects)
    """
    object_access = object_assignment.objects.filter(
        is_deleted="FALSE",
        task_id=task_id,
        group_id__in=user_group.objects.filter(
            is_deleted="FALSE",
            username=request.user,
        ).values('group_id')
    )
    if object_access.count() == 0 and not permission_results['administration'] == 4:
        return HttpResponseRedirect(reverse('permission_denied'))


    # Define the data we will edit
    task_results = get_object_or_404(task, task_id=task_id)

    """
    We want to take the user to the read only module if either of the conditions are met;
    - Task status has been set to 'Resolved'
    - Task status has been set to 'Completed'
    - User only have read only status
    """
    if task_results.task_status in ('Resolved','Closed') or permission_results['task'] == 1:
        #Take them to the read only
        return HttpResponseRedirect(reverse('task_readonly',args={ task_id }))

    # Get the data from the form
    if request.method == "POST":
        form = task_information_form(request.POST, request.FILES)
        if form.is_valid():
            # Extract all the information from the form and save
            task_results.task_short_description = form.cleaned_data['task_short_description']
            task_results.task_long_description = form.cleaned_data['task_long_description']
            task_results.task_start_date = form.cleaned_data['task_start_date']
            task_results.task_end_date = form.cleaned_data['task_end_date']

            """
            There are two buttons on the task information page. Both will come
            here. Both will save the data, however only one of them will resolve
            the task.
            
            We check here to see if the resolve button has been pressed.
            """
            if 'Resolve' in request.POST:
                # Well, we have to now resolve the data
                task_results.task_status = 'Resolved'
            task_results.save()

            """
            Now we need to update any kanban board cards connected to this project.
            """
            kanban_card_results = kanban_card.objects.filter(
                is_deleted="FALSE",
                task_id=task_id
            )
            for row in kanban_card_results:
                row.kanban_card_text = "TASK" + str(task_id) + " - " + form.cleaned_data['task_short_description']
                row.save()

    # Setup the initial
    initial = {
        'task_short_description': task_results.task_short_description,
        'task_long_description': task_results.task_long_description,
        'task_start_date': task_results.task_start_date,
        'task_end_date': task_results.task_end_date,
    }

    # Query the database for associated project information
    cursor = connection.cursor()
    cursor.execute("""
		SELECT 
		  project.project_id
		, project.project_name
		, project.project_end_date
		FROM project
			JOIN project_task
			ON project.project_id = project_task.project_id
			AND project_task.is_deleted = 'FALSE'
			AND project_task.task_id = %s
		""", [task_id])
    associated_project_results = namedtuplefetchall(cursor)


    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        task_id=task_results,
    )

    running_total = 0
    # Load the template
    t = loader.get_template('NearBeach/task_information.html')

    # context
    c = {
        'task_results': task_results,
        'task_information_form': task_information_form(initial=initial),
        'information_task_history_form': information_task_history_form(),
        'associated_project_results': associated_project_results,
        'media_url': settings.MEDIA_URL,
        'task_id': task_id,
        'permission': permission_results['task'],
        'task_history_permissions': permission_results['task_history'],
        'quote_results': quote_results,
        'timezone': settings.TIME_ZONE,
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def task_readonly(request,task_id):
    task_groups_results = object_assignment.objects.filter(
        is_deleted="FALSE",
        task_id=task.objects.get(task_id=task_id),
    ).values('group_id_id')

    permission_results = return_user_permission_level(request, task_groups_results, ['task', 'task_history'])

    # Get data
    task_results = task.objects.get(task_id=task_id)
    to_do_results = to_do.objects.filter(
        is_deleted="FALSE",
        task_id=task_id,
    )
    task_history_results = task_history.objects.filter(
        is_deleted="FALSE",
        task_id=task_id,
    )
    email_results = email_content.objects.filter(
        is_deleted="FALSE",
        email_content_id__in=email_contact.objects.filter(
            Q(task_id=task_id) &
            Q(is_deleted="FALSE") &
            Q(
                Q(is_private=False) |
                Q(change_user=request.user)
            )
        ).values('email_content_id')
    )

    associated_project_results = project_task.objects.filter(
        is_deleted="FALSE",
        task_id=task_id,
    )

    task_customers_results = task_customer.objects.filter(
        is_deleted="FALSE",
        task_id=task_id,

    )

    costs_results = cost.objects.filter(
        task_id=task_id,
        is_deleted='FALSE'
    )

    quote_results = quote.objects.filter(
        is_deleted="FALSE",
        task_id=task_id,
    )

    bug_results = bug.objects.filter(
        is_deleted="FALSE",
        task_id=task_id,
    )

    assigned_results = object_assignment.objects.filter(
        task_id=task_id,
        is_deleted="FALSE",
    ).exclude(
        assigned_user=None,
    ).values(
        'assigned_user__id',
        'assigned_user',
        'assigned_user__username',
        'assigned_user__first_name',
        'assigned_user__last_name',
    ).distinct()

    group_list_results = object_assignment.objects.filter(
        is_deleted="FALSE",
        task_id=task_id,
    )

    """
    We want to bring through the project history's tinyMCE widget as a read only. However there are 
    most likely multiple results so we will create a collective.
    """
    task_history_collective = []
    for row in task_history_results:
        # First deal with the datetime
        task_history_collective.append(
            task_history_readonly_form(
                initial={
                    'task_history': row.task_history,
                    'submit_history': row.user_infomation + " - " + str(row.user_id) + " - " \
                                      + row.date_created.strftime("%d %B %Y %H:%M.%S"),
                },
                task_history_id=row.task_history_id,
            )
        )

    print(task_history_collective)


    # Load template
    t = loader.get_template('NearBeach/task_information/task_readonly.html')

    # Context
    c = {
        'task_id': task_id,
        'task_results': task_results,
        'task_readonly_form': task_readonly_form(
            initial={'task_long_description': task_results.task_long_description}
        ),
        'to_do_results': to_do_results,
        'task_history_collective': task_history_collective,
        'email_results': email_results,
        'associated_project_results': associated_project_results,
        'task_customers_results': task_customers_results,
        'costs_results': costs_results,
        'quote_results': quote_results,
        'bug_results': bug_results,
        'assigned_results': assigned_results,
        'group_list_results': group_list_results,
        'project_permissions': permission_results['task'],
        'project_history_permissions': permission_results['task_history'],
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c,request))

@login_required(login_url='login')
def task_remove_customer(request,task_customer_id):
    if request.method == "POST":
        task_customer_update =task_customer.objects.get(
            task_customer_id=task_customer_id,
        )
        task_customer_update.change_user=request.user
        task_customer_update.is_deleted="TRUE"
        task_customer_update.save()

        #Return blank page
        t = loader.get_template('NearBeach/blank.html')
        c = {}
        return HttpResponse(t.render(c,request))
    else:
        return HttpResponseBadRequest("Sorry, can only do this in POST")


@login_required(login_url='login')
def timeline(request):
    permission_results = return_user_permission_level(request, [],[])

    t = loader.get_template('NearBeach/timeline.html')

    # context
    c = {
        'timeline_form': timeline_form(),
        'start_date': datetime.datetime.now(),
        'end_date': datetime.datetime.now() + datetime.timedelta(days=31),
        'new_item_permission': permission_results['new_item'],
        'administration_permission': permission_results['administration'],
    }

    return HttpResponse(t.render(c, request))



@login_required(login_url='login')
def timeline_data(request):
    if request.method == "POST":
        form = timeline_form(request.POST)
        if form.is_valid():
            """
            FUTURE NOTE - WE WILL NEED TO WRITE THIS SO THAT IT WILL AUTOMATICALLY DEPLOY EITHER PROJECT/TASKS OR 
            ANY OTHER OBJECT DEPENDING ON THE CHOICES MADE ON THE FORM!!!
            """
            #Get Variables
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            object_type = form.cleaned_data['object_type']

            if object_type == "Project":

                #Get json_data
                json_results = serializers.serialize(
                    'json',
                    project.objects.filter(
                        Q(is_deleted="FALSE") &
                        Q(
                            # Start and end date out of bounds
                            Q(
                                project_start_date__lte=start_date,
                                project_end_date__gte=end_date,
                            ) |

                            # Start date between start and end date
                            Q(
                                project_start_date__gte=start_date,
                                project_start_date__lte=end_date,
                            ) |

                            # End date betweeen start and end date
                            Q(
                                project_end_date__gte=start_date,
                                project_end_date__lte=end_date,
                            )
                        )
                    ).order_by(
                        'project_start_date',
                        'project_end_date',
                        'project_id',
                    ),
                    fields={
                        'project_id',
                        'project_name',
                        'project_start_date',
                        'project_end_date',
                        'project_status',
                    }
                )
            elif object_type == "Task":
                json_results = serializers.serialize(
                    'json',
                    task.objects.filter(
                        Q(is_deleted="FALSE") &
                        Q(
                            # Start and end date out of bounds
                            Q(
                                task_start_date__lte=start_date,
                                task_end_date__gte=end_date,
                            ) |

                            # Start date between start and end date
                            Q(
                                task_start_date__gte=start_date,
                                task_start_date__lte=end_date,
                            ) |

                            # End date betweeen start and end date
                            Q(
                                task_end_date__gte=start_date,
                                task_end_date__lte=end_date,
                            )
                        )
                    ).order_by(
                        'task_start_date',
                        'task_end_date',
                        'task_id',
                    ),
                    fields={
                        'task_id',
                        'task_name',
                        'task_start_date',
                        'task_end_date',
                        'task_status',
                    }
                )
            elif object_type == "Quote":
                """
                Quote will only have a "quote_valid_till" date. Thus the start date will automatically be the date 
                it was created.
                """
                json_results = serializers.serialize(
                    'json',
                    quote.objects.filter(
                        is_deleted="FALSE",
                        quote_valid_till__gte=start_date,
                        quote_valid_till__lte=end_date,
                    ).order_by(
                        'date_created',
                        'quote_valid_till',
                        'quote_id',
                    ),
                    fields={
                        'quote_id',
                        'quote_title',
                        'date_created',
                        'quote_valid_till',
                        'quote_stage',
                    }
                )
                print(json_results)
            elif object_type == "Opportunity":
                """
                Opportunity will only have a "Opportunity Only Valid Till" date. Thus the start date will automatically
                be the date it was created
                """
                json_results = serializers.serialize(
                    'json',
                    opportunity.objects.filter(
                        is_deleted="FALSE",
                        opportunity_expected_close_date__gte=start_date,
                        opportunity_expected_close_date__lte=end_date,
                    ).order_by(
                        'date_created',
                        'opportunity_expected_close_date',
                        'opportunity_id',
                    ),
                    fields={
                        'opportunity_id',
                        'opportunity_name',
                        'date_created',
                        'opportunity_expected_close_date',
                        'opportunity_stage_id',
                    }
                )
                print(json_results)
            else:
                #Something went wrong
                return HttpResponseBadRequest("Sorry, there is no object that fits that situation")

            return HttpResponse(json_results, content_type='application/json')

        else:
            print(form.errors)

    else:
        return HttpResponseBadRequest("timeline date has to be done in post!")




@login_required(login_url='login')
def to_do_list(request, location_id, destination):
    if request.method == "POST":
        form = to_do_form(request.POST)
        if form.is_valid():
            to_do_submit = to_do(
                to_do=form.cleaned_data['to_do'],
                change_user=request.user,
            )
            if destination == "project":
                to_do_submit.project = project.objects.get(project_id=location_id)
            elif destination == "task":
                to_do_submit.task = task.objects.get(task_id=location_id)
            else:
                to_do_submit.opportunity = opportunity.objects.get(opportunity_id=location_id)
            to_do_submit.save()
        else:
            print(form.errors)

    # Get data
    if destination == 'project':
        to_do_results = to_do.objects.filter(
            is_deleted='FALSE',
            project_id=location_id,
        )
    elif destination == 'task':
        to_do_results = to_do.objects.filter(
            is_deleted='FALSE',
            task_id=location_id,
        )
    else: #Opportunity
        to_do_results = to_do.objects.filter(
            is_deleted='FALSE',
            opportunity_id=location_id,
        )


    # Load the template
    t = loader.get_template('NearBeach/to_do/to_do.html')

    # context
    c = {
        'to_do_results': to_do_results,
        'to_do_form': to_do_form(),
    }

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def to_do_complete(request, to_do_id):
    to_do_update = to_do.objects.get(to_do_id=to_do_id)
    to_do_update.to_do_completed = True
    to_do_update.save()


    t = loader.get_template('NearBeach/blank.html')

    # context
    c = {}

    return HttpResponse(t.render(c, request))


@login_required(login_url='login')
def user_want_remove(request,user_want_id):
    if request.method=="POST":
        user_want_save = user_want.objects.get(pk=user_want_id)
        user_want_save.is_deleted="TRUE"
        user_want_save.save()

        #Send back blank page
        t = loader.get_template('NearBeach/blank.html')

        c = {}

        return HttpResponse(t.render(c, request))
    else:
        return HttpResponseBadRequest("Sorry, this function can only be done in POST")



@login_required(login_url='login')
def user_want_view(request):
    if request.method=="POST":
        form = user_want_form(request.POST)
        if form.is_valid():
            user_want_submit=user_want()
            user_want_submit.change_user = request.user
            user_want_submit.want_choice = form.cleaned_data['want_choice']
            user_want_submit.want_choice_text = form.cleaned_data['want_choice_text']
            user_want_submit.want_skill = form.cleaned_data['want_skill']
            user_want_submit.save()
        else:
            print(form.errors)

    want_results = user_want.objects.filter(
        is_deleted="FALSE",
        want_choice="1" #User wants
    )

    not_want_results = user_want.objects.filter(
        is_deleted="FALSE",
        want_choice="0" #Does not want
    )

    t = loader.get_template('NearBeach/my_profile/user_want.html')

    c = {
        'user_want_form': user_want_form(),
        'want_results': want_results,
        'not_want_results': not_want_results,
    }

    return HttpResponse(t.render(c, request))




@login_required(login_url='login')
def user_weblink_remove(request,user_weblink_id):
    if request.method == "POST":
        weblink_save = user_weblink.objects.get(pk=user_weblink_id)
        weblink_save.is_deleted="TRUE"
        weblink_save.save()

        #Return blank page
        t = loader.get_template('NearBeach/blank.html')

        c = {}

        return HttpResponse(t.render(c,request))
    else:
        #Can only do this through post
        return HttpResponseBadRequest("Can only do this through post")


@login_required(login_url='login')
def user_weblink_view(request):
    if request.method == "POST":
        form = user_weblink_form(request.POST)
        if form.is_valid():
            user_weblink_submit = user_weblink(
                change_user=request.user,
                user_weblink_url=form.cleaned_data['user_weblink_url'],
                user_weblink_source=form.cleaned_data['user_weblink_source'],
            )
            user_weblink_submit.save()
        else:
            print(form.errors)

    #Data
    user_weblink_results=user_weblink.objects.filter(
        is_deleted="FALSE",
        change_user=request.user,
    )

    #Template
    t = loader.get_template('NearBeach/my_profile/user_weblink.html')

    c = {
        'user_weblink_form': user_weblink_form(),
        'user_weblink_results': user_weblink_results,
    }

    return HttpResponse(t.render(c, request))







"""
The following def are designed to help display a customer 404 and 500 pages
"""
def handler404(request):
    response = render_to_response(
        '404.html',
        {},
        context_instance=RequestContext(request)
    )
    response.status_code = 404
    return response


def handler500(request):
    response = render_to_response(
        '500.html',
        {},
        context_instance=RequestContext(request)
    )
    response.status_code = 500
    return response


def update_coordinates(campus_id):
    campus_results = campus.objects.get(pk=campus_id)

    #Set the address up
    address = campus_results.campus_address1 + " " + \
              campus_results.campus_address2 + " " + \
              campus_results.campus_address3 + " " + \
              campus_results.campus_suburb + " " + \
              campus_results.campus_region_id.region_name + " " + \
              campus_results.campus_country_id.country_name + " "
    print(address)
    address = address.replace("/", " ")  # Remove those pesky /



    #If there are no co-ordinates for this campus, get them and save them
    if hasattr(settings, 'GOOGLE_MAP_API_TOKEN'):
        print("Google Maps token exists")
        google_maps = GoogleMaps(api_key=settings.GOOGLE_MAP_API_TOKEN)
        try:
            location = google_maps.search(location=address)
            first_location = location.first()

            #Save the data
            campus_results.campus_longitude = first_location.lng
            campus_results.campus_latitude = first_location.lat
            campus_results.save()
        except:
            print("Sorry, there was an error getting the location details for this address.")

    elif hasattr(settings, 'MAPBOX_API_TOKEN'):
        #Get address ready for HTML

        address_coded = urllib.parse.quote_plus(address)

        url = "https://api.mapbox.com/geocoding/v5/mapbox.places/" + address_coded + ".json?access_token=" + settings.MAPBOX_API_TOKEN

        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
        print(data)
        try:
            campus_results.campus_longitude = data["features"][0]["center"][0]
            campus_results.campus_latitude = data["features"][0]["center"][1]
            campus_results.save()

            print(data["features"][0]["center"])
        except:
            print("No data for the address: " + address)

def update_template_strings(variable,quote_results):
    """
    The following function will replace all {{ tag }} variables in the template with the results from the quote
    results. The current variables are;

    Groups
    ~~~~~~
    1.) Quotes
    2.) Organisatiions
    3.) Quote Billing Address
    """
    variable = variable.replace('{{ customer_id }}', str(quote_results.customer_id))
    variable = variable.replace('{{ customer_notes }}', quote_results.customer_notes)
    variable = variable.replace('{{ is_invoice }}', quote_results.is_invoice)
    variable = variable.replace('{{ opportunity_id }}', str(quote_results.opportunity_id))
    variable = variable.replace('{{ organisation_id }}', str(quote_results.organisation_id))
    variable = variable.replace('{{ project_id }}', str(quote_results.project_id))
#    variable = variable.replace('{{ quote_approval_status_id }}', str(quote_results.quote_approval_status_id))
    variable = variable.replace('{{ quote_billing_address }}', str(quote_results.quote_billing_address))
    variable = variable.replace('{{ quote_id }}', str(quote_results.quote_id))
    variable = variable.replace('{{ quote_stage_id }}', str(quote_results.quote_stage_id))
    variable = variable.replace('{{ quote_terms }}', quote_results.quote_terms)
    variable = variable.replace('{{ quote_title }}', quote_results.quote_title)
    variable = variable.replace('{{ quote_valid_till }}', str(quote_results.quote_valid_till))
    variable = variable.replace('{{ task_id }}', str(quote_results.task_id))

    #Group 2
    if quote_results.organisation_id:
        variable = variable.replace('{{ organisation_name }}', quote_results.organisation_id.organisation_name)
        variable = variable.replace('{{ organisation_website }}', quote_results.organisation_id.organisation_website)
        variable = variable.replace('{{ organisation_email }}', quote_results.organisation_id.organisation_email)
    else:
        variable = variable.replace('{{ organisation_name }}', '')
        variable = variable.replace('{{ organisation_website }}', '')
        variable = variable.replace('{{ organisation_email }}', '')

    #Group 3
    if quote_results.quote_billing_address:
        variable = variable.replace('{{ billing_address1 }}', quote_results.quote_billing_address.campus_address1)
        variable = variable.replace('{{ billing_address2 }}', quote_results.quote_billing_address.campus_address2)
        variable = variable.replace('{{ billing_address3 }}', quote_results.quote_billing_address.campus_address3)
        variable = variable.replace('{{ campus_id }}', str(quote_results.quote_billing_address.campus_id))
        variable = variable.replace('{{ campus_nickname }}', quote_results.quote_billing_address.campus_nickname)
        variable = variable.replace('{{ campus_phone }}', quote_results.quote_billing_address.campus_phone)
        variable = variable.replace('{{ campus_region_id }}', str(quote_results.quote_billing_address.campus_region_id))
        variable = variable.replace('{{ billing_suburb }}', quote_results.quote_billing_address.campus_suburb)
        if quote_results.quote_billing_address.campus_postcode == None:
            variable = variable.replace('{{ billing_postcode }}', '')
        else:
            variable = variable.replace('{{ billing_postcode }}', str(quote_results.quote_billing_address.campus_postcode))
        variable = variable.replace('{{ billing_region }}', str(quote_results.quote_billing_address.campus_region_id))
        variable = variable.replace('{{ billing_country }}', str(quote_results.quote_billing_address.campus_country_id))
    else:
        variable = variable.replace('{{ billing_address1 }}', '')
        variable = variable.replace('{{ billing_address2 }}', '')
        variable = variable.replace('{{ billing_address3 }}', '')
        variable = variable.replace('{{ billing_postcode }}', '')
        variable = variable.replace('{{ campus_id }}', '')
        variable = variable.replace('{{ campus_nickname }}', '')
        variable = variable.replace('{{ campus_phone }}', '')
        variable = variable.replace('{{ campus_region_id }}', '')
        variable = variable.replace('{{ billing_suburb }}', '')
        variable = variable.replace('{{ billing_region }}', '')
        variable = variable.replace('{{ billing_country }}', '')

    return variable
