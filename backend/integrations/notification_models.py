from django.conf import settings
from django.db import models


class NotificationRead(models.Model):
    """Per-user acknowledgement of a scoped notification version."""
    business = models.ForeignKey("businesses.Business", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notification_key = models.CharField(max_length=180)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=("business", "user", "notification_key"),
            name="unique_notification_read_per_user",
        )]
