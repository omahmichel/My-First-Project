from django.core.checks import run_checks
from django.core.management.base import BaseCommand, CommandError
from platform_events.capture import record_event

class Command(BaseCommand):
    requires_system_checks=[]
    help='Run and record Django system checks, without logging sensitive message content.'
    def handle(self,*args,**options):
        issues=run_checks()
        level=max((i.level for i in issues),default=0)
        severity='error' if level>=40 else 'warning' if level>=30 else 'info'
        record_event(category='system',action='check.result',summary='System validation check completed',severity=severity,
            details={'check_ids':[i.id for i in issues[:30]],'issue_count':len(issues)})
        self.stdout.write(f'System checks: {len(issues)} issue(s); severity={severity}.')
        if level>=40: raise CommandError('System validation failed. Run manage.py check for local diagnostics.')
