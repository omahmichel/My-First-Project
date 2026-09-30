import json
from hashlib import sha256
from django.db import migrations

def import_history(apps,schema_editor):
    Event=apps.get_model('platform_events','PlatformEvent')
    Entry=apps.get_model('admin','LogEntry')
    alias=schema_editor.connection.alias
    entries=Entry.objects.using(alias).filter(change_message__startswith='{"platformAdmin": true,').iterator(chunk_size=200)
    for row in entries:
        try: data=json.loads(row.change_message)
        except (ValueError,TypeError): continue
        Event.objects.using(alias).get_or_create(dedupe_key=sha256(f'legacy-admin-{row.pk}'.encode()).hexdigest(),defaults=dict(
            occurred_at=row.action_time,last_seen_at=row.action_time,category='administration',severity='info',
            action='admin.status_changed',summary='Administrator changed account status',actor_id=str(row.user_id),
            object_type=data.get('targetKind','') if data.get('targetKind') in ('users','businesses') else '',
            object_id=str(row.object_id)[:64],source='legacy-admin',details={'legacy_id':row.pk,'state':'active' if data.get('afterActive') else 'inactive'}))

class Migration(migrations.Migration):
    dependencies=[('platform_events','0001_initial'),('admin','0003_logentry_add_action_flag_choices')]
    operations=[migrations.RunPython(import_history,migrations.RunPython.noop)]
