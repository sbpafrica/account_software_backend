import uuid
from django.db import models

class BaseModel(models.Model):
    """
    [DEVELOPER NOTE]: Abstract base model inherited by all database entities in SBP-FMS.
    Provides standard UUID primary keys and immutable creation/update audit timestamps.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
