from django.db import migrations

def import_errors(apps,schema_editor):
    Event=apps.get_model('platform_events','PlatformEvent')
    Bug=apps.get_model('platform_events','BugReport')
    alias=schema_editor.connection.alias
    for e in Event.objects.using(alias).filter(category='system',severity__in=['error','critical']).iterator(chunk_size=200):
        Bug.objects.using(alias).get_or_create(event_id=e.pk,defaults=dict(title=e.summary,source='application',reporter_id=e.actor_id,business_id=e.business_id,created_at=e.occurred_at))

class Migration(migrations.Migration):
    dependencies=[('platform_events','0003_bugreport')]
    operations=[migrations.RunPython(import_errors,migrations.RunPython.noop)]
