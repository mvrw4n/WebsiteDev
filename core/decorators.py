from functools import wraps
from rest_framework.response import Response
from rest_framework import status

def check_quota(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        profile = request.user.profile
        if not profile.can_access_leads:
            return Response(
                {"error": "Subscription required or trial expired."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        if profile.leads_quota <= 0:
            return Response(
                {"error": "Monthly leads quota exhausted."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Execute the view and capture response
        response = view_func(request, *args, **kwargs)
        
        # Only decrement quota if the request was successful
        if response.status_code in [200, 201]:
            profile.leads_quota -= 1
            profile.save()
        
        return response
    return wrapper
