# This file is part of wger Workout Manager.
#
# wger Workout Manager is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# wger Workout Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Workout Manager.  If not, see <http://www.gnu.org/licenses/>.
# Standard Library

# Django
from django.contrib.auth.models import User
from django.db import models


class FormulaChoices(models.TextChoices):
    """
    Supported built-in dynamic formula names.
    Add new formulas here.
    """

    BMI = "bmi", "Body Mass Index (BMI)"
    LEAN_BODY_MASS = "lbm", "Lean Body Mass"
    ONE_RM_EPLEY = "1rm_epley", "1RM — Epley formula"
    ONE_RM_BRZYCKI = "1rm_brzycki", "1RM — Brzycki formula"


class Category(models.Model):
    class Meta:
        ordering = [
            "-name",
        ]

    user = models.ForeignKey(
        User,
        verbose_name="User",
        on_delete=models.CASCADE,
    )

    name = models.CharField(
        verbose_name="Name",
        max_length=100,
    )

    unit = models.CharField(
        verbose_name="Unit",
        max_length=30,
    )

    group = models.ForeignKey(
        'measurements.MeasurementGroup',
        verbose_name='Group',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='categories',
        help_text=(
            'Optional group this category belongs to. '
            'Use for multi-value measurements like Blood Pressure.'
        ),
    )

    formula = models.CharField(
        verbose_name="Formula",
        max_length=20,
        choices=FormulaChoices.choices,
        null=True,
        blank=True,
        help_text=(
            "If set, this is a dynamic (calculated) category. "
            "Values are computed from other data, not entered manually."
        ),
    )

    @property
    def is_dynamic(self) -> bool:
        """True if this category has a formula (i.e. is computed, not stored)."""
        return self.formula is not None

    def get_owner_object(self):
        """
        Returns the object that has owner information
        """
        return self

    def __str__(self):
        return f"{self.name} ({self.unit})"
