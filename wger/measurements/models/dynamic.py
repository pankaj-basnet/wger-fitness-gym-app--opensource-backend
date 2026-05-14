# Standard Library
import datetime
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Tuple

# Django
from django.contrib.auth.models import User
from django.core.cache import cache

logger = logging.getLogger(__name__)

DYNAMIC_MEASUREMENT_CACHE_TTL = 60 * 60 * 24  # 24 hours


@dataclass
class DynamicMeasurementPoint:
    """A single computed measurement data point."""

    date: datetime.date
    value: Decimal
    notes: str = 'auto-calculated'


def _get_category_values(user: User, category_name_hint: str) -> List[Tuple]:
    """
    Helper: fetch all (date, value) pairs for the first category
    belonging to the user that contains the given hint in its name.

    Returns list of (date, Decimal value) tuples ordered by date desc.
    """
    from wger.measurements.models.category import Category
    from wger.measurements.models.measurement import Measurement

    categories = Category.objects.filter(
        user=user,
        name__icontains=category_name_hint,
    )
    if not categories.exists():
        return []

    category = categories.first()
    return list(
        Measurement.objects.filter(category=category).order_by('date').values_list('date', 'value')
    )


def calculate_bmi(user: User) -> List[DynamicMeasurementPoint]:
    """
    Calculates BMI for each date where both weight and height are available.

    Formula: BMI = weight_kg / (height_m)^2
    Height is assumed static (takes latest entry).
    Weight is taken from each logged date.

    Args:
        user: The Django user whose data to use.

    Returns:
        List of DynamicMeasurementPoint ordered by date.
    """
    cache_key = f'dynamic_bmi_{user.pk}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    weight_entries = _get_category_values(user, 'weight')
    height_entries = _get_category_values(user, 'height')

    if not weight_entries or not height_entries:
        return []

    # Use latest height entry as the static height
    _, height_cm = height_entries[-1]
    if not height_cm or height_cm == 0:
        return []

    height_m = Decimal(str(height_cm)) / Decimal('100')

    result = []
    for date, weight_kg in weight_entries:
        if weight_kg is None:
            continue
        bmi = Decimal(str(weight_kg)) / (height_m**2)
        result.append(
            DynamicMeasurementPoint(
                date=date,
                value=round(bmi, 2),
                notes=f'BMI = {weight_kg}kg / ({height_cm}cm)²',
            )
        )

    cache.set(cache_key, result, DYNAMIC_MEASUREMENT_CACHE_TTL)
    return result


def calculate_lean_body_mass(user: User) -> List[DynamicMeasurementPoint]:
    """
    Calculates Lean Body Mass for each date where both weight and body fat % are available.

    Formula: LBM = weight * (1 - body_fat_pct / 100)

    Args:
        user: The Django user whose data to use.

    Returns:
        List of DynamicMeasurementPoint ordered by date.
    """
    cache_key = f'dynamic_lbm_{user.pk}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    weight_entries = dict(_get_category_values(user, 'weight'))
    fat_pct_entries = dict(_get_category_values(user, 'body fat'))

    if not weight_entries or not fat_pct_entries:
        return []

    result = []
    for date, weight in weight_entries.items():
        fat_pct = fat_pct_entries.get(date)
        if fat_pct is None or weight is None:
            continue
        lbm = Decimal(str(weight)) * (1 - Decimal(str(fat_pct)) / 100)
        result.append(
            DynamicMeasurementPoint(
                date=date,
                value=round(lbm, 2),
                notes=f'LBM = {weight}kg * (1 - {fat_pct}%)',
            )
        )

    cache.set(cache_key, result, DYNAMIC_MEASUREMENT_CACHE_TTL)
    return sorted(result, key=lambda x: x.date)


def calculate_one_rm_epley(user: User) -> List[DynamicMeasurementPoint]:
    """
    Calculates estimated 1RM using the Epley formula from WorkoutLog entries.

    Formula: 1RM = weight * reps * 0.0333 + weight
    Only considers sets with reps <= 10 (Epley is less accurate for high-rep sets).
    Takes the highest result per day.

    Args:
        user: The Django user whose data to use.

    Returns:
        List of DynamicMeasurementPoint ordered by date.
    """
    cache_key = f'dynamic_1rm_epley_{user.pk}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # Import here to avoid circular imports at module level
    from wger.manager.models import WorkoutLog

    logs = (
        WorkoutLog.objects.filter(user=user, weight__isnull=False, repetitions__isnull=False)
        .filter(repetitions__gt=0, repetitions__lte=10)
        .order_by('date')
        .values_list('date', 'weight', 'repetitions')
    )

    # Group by date, take max 1RM per day
    daily_max: dict = {}
    for log_datetime, weight, reps in logs:
        date = log_datetime.date() if hasattr(log_datetime, 'date') else log_datetime
        one_rm = Decimal(str(weight)) * Decimal(str(reps)) * Decimal('0.0333') + Decimal(
            str(weight)
        )
        if date not in daily_max or one_rm > daily_max[date]:
            daily_max[date] = one_rm

    result = [
        DynamicMeasurementPoint(date=d, value=round(v, 2), notes='1RM (Epley)')
        for d, v in sorted(daily_max.items())
    ]

    cache.set(cache_key, result, DYNAMIC_MEASUREMENT_CACHE_TTL)
    return result


def invalidate_dynamic_cache(user_id: int):
    """
    Invalidates all dynamic measurement caches for a user.
    Call this when new Measurement or WorkoutLog entries are saved.
    """
    for formula in ('bmi', 'lbm', '1rm_epley', '1rm_brzycki'):
        cache.delete(f'dynamic_{formula}_{user_id}')


# Formula Registry
# Maps FormulaChoices values to their calculator functions.

FORMULA_REGISTRY = {
    'bmi': calculate_bmi,
    'lbm': calculate_lean_body_mass,
    '1rm_epley': calculate_one_rm_epley,
}
