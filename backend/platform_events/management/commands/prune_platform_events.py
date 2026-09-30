from datetime import timedelta
from django.core.management.base import BaseCommand,CommandError
from django.utils import timezone
from platform_events.models import PlatformEvent

class Command(BaseCommand):
    help='Preview old activity rows; --apply explicitly deletes them. Default retention: 90 days.'
    def add_arguments(self,p):
        p.add_argument('--days',type=int,default=90)
        p.add_argument('--apply',action='store_true')
    def handle(self,*args,**options):
        if options['days']<7: raise CommandError('Minimum retention is 7 days.')
        rows=PlatformEvent.objects.filter(last_seen_at__lt=timezone.now()-timedelta(days=options['days']))
        count=rows.count()
        if options['apply']: rows.delete()
        self.stdout.write(f'{count} old event rows '+('deleted.' if options['apply'] else 'eligible; no records deleted.'))
