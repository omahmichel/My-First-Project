import time
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.utils import timezone
from owner_alerts.models import LoginFailure
from owner_alerts.services import process_pending


class Command(BaseCommand):
    help = 'Submit queued owner SMS through mNotify. Run every minute, or use --loop in a worker.'
    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument('--loop', action='store_true')
        parser.add_argument('--interval', type=int, default=5)
    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 1000 or options['interval'] < 1:
            raise CommandError('Use limit 1-1000 and a positive interval.')
        try:
            while True:
                close_old_connections()
                LoginFailure.objects.filter(created_at__lt=timezone.now()-timedelta(days=1)).delete()
                self.stdout.write(str(process_pending(options['limit'])))
                if not options['loop']:
                    break
                time.sleep(options['interval'])
        except KeyboardInterrupt:
            self.stdout.write('Owner SMS worker stopped.')
