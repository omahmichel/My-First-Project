from django.core.management.commands.check import Command as DjangoCheck
from platform_events.capture import record_event

class Command(DjangoCheck):
    def handle(self,*args,**options):
        try:
            result=super().handle(*args,**options)
        except Exception as exc:
            record_event(category='system',action='check.failed',summary='Django system check failed',severity='error',details={'exception_type':type(exc).__name__})
            raise
        record_event(category='system',action='check.completed',summary='Django system check completed at the selected fail level')
        return result
