from django.conf import settings
from django.db.models import signals
from django.dispatch import receiver

from apps.commons import models


@receiver(signals.post_save, sender=models.Email)
def post_save_email_default(sender, instance, created, raw, using, *args, **kwargs):
    if created:
        """
        Open email base templates
        """
        instance.user_welcome = open(
            "%s/../apps/commons/templates/emails/user_confirmation.html" % settings.BASE_DIR, encoding="utf-8").read()
        instance.user_reset_password = open(
            "%s/../apps/commons/templates/emails/user_reset_password.html" % settings.BASE_DIR, encoding="utf-8").read()
        instance.save()
