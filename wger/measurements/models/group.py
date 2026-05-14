import uuid

# Django
from django.contrib.auth.models import User
from django.db import models


class MeasurementGroup(models.Model):
    """
    A named group that can contain multiple measurement categories.

    Use case: Blood Pressure has two components (systolic, diastolic).
    Both Category rows get a FK to the same MeasurementGroup.
    """

    class Meta:
        ordering = ['name']

    user = models.ForeignKey(
        User,
        verbose_name='User',
        on_delete=models.CASCADE,
        related_name='measurement_groups',
    )

    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name='UUID',
        help_text='Unique identifier used for syncing with clients.',
    )

    name = models.CharField(
        verbose_name='Name',
        max_length=100,
        help_text='Display name for this group, e.g. "Blood Pressure".',
    )

    description = models.CharField(
        verbose_name='Description',
        max_length=500,
        blank=True,
        default='',
    )

    def __str__(self):
        return f'MeasurementGroup {self.name} (user={self.user_id})'

    def get_owner_object(self):
        """Returns the object that has owner information"""
        return self
