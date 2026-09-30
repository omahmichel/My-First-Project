from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from .capture import record_event

class ReportThrottle(UserRateThrottle):
    rate='5/min'
    scope='platform_client_error'

class ClientReport(serializers.Serializer):
    kind=serializers.ChoiceField(choices=['javascript_error','unhandled_rejection'])
    area=serializers.ChoiceField(choices=['platform-admin','app','businesses','onboarding','public','authentication'])
    def to_internal_value(self,data):
        if not isinstance(data,dict) or set(data)-set(self.fields):
            raise serializers.ValidationError({'detail':'Only error kind and page area are accepted.'})
        return super().to_internal_value(data)

class ClientError(APIView):
    permission_classes=[IsAuthenticated]
    throttle_classes=[ReportThrottle]
    def post(self,request):
        report=ClientReport(data=request.data);report.is_valid(raise_exception=True)
        record_event(category='system',action='browser.'+report.validated_data['kind'],
            summary='Browser reported an application error',severity='error',aggregate=True,
            actor_id=str(request.user.pk),source='browser-report',route=report.validated_data['area'])
        response=Response(status=204);response['Cache-Control']='no-store';return response
