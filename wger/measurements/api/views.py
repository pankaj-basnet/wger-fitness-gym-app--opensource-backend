# -*- coding: utf-8 -*-

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
import logging

# Django
from django.contrib.auth.models import User

# Third Party
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# wger
from wger.measurements.api.filtersets import MeasurementEntryFilterSet
from wger.measurements.api.serializers import (
    DynamicMeasurementPointSerializer,
    MeasurementGroupSerializer,
    MeasurementSerializer,
    UnitSerializer,
)
from wger.measurements.models import (
    Category,
    Measurement,
)
from wger.measurements.models.dynamic import FORMULA_REGISTRY
from wger.measurements.models.group import MeasurementGroup
from wger.utils.viewsets import WgerOwnerObjectModelViewSet


logger = logging.getLogger(__name__)


class MeasurementGroupViewSet(WgerOwnerObjectModelViewSet):
    """
    API endpoint for measurement groups.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = MeasurementGroupSerializer
    is_private = True
    ordering_fields = '__all__'
    filterset_fields = ('id', 'name', 'uuid')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return MeasurementGroup.objects.none()
        return MeasurementGroup.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """
        Set the owner
        """
        serializer.save(user=self.request.user)

    def get_owner_objects(self):
        """
        Return objects to check for ownership permission
        """
        return [(User, 'user')]


class CategoryViewSet(WgerOwnerObjectModelViewSet):
    """
    API endpoint for measurement units
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UnitSerializer
    is_private = True
    ordering_fields = '__all__'
    filterset_fields = ('id', 'name', 'unit', 'group', 'formula')

    def get_queryset(self):
        """
        Only allow access to appropriate objects
        """
        # REST API generation
        if getattr(self, 'swagger_fake_view', False):
            return Category.objects.none()

        return Category.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """
        Set the owner
        """
        serializer.save(user=self.request.user)

    def get_owner_objects(self):
        """
        Return objects to check for ownership permission
        """
        return [(User, 'user')]

    @action(detail=True, methods=['get'], url_path='dynamic-values')
    def dynamic_values(self, request, pk=None):
        """
        For dynamic (formula-based) categories, compute and return the
        historical values.

        GET /api/v2/measurement-category/{id}/dynamic-values/

        Returns 400 if the category is not dynamic.
        Returns computed values from cache (24hr TTL) or recalculates.
        """
        category = self.get_object()

        if not category.is_dynamic:
            return Response(
                {'detail': 'This category is not a dynamic (formula-based) category.'},
                status=400,
            )

        calculator = FORMULA_REGISTRY.get(category.formula)
        if calculator is None:
            return Response(
                {'detail': f'No calculator registered for formula: {category.formula}'},
                status=501,
            )

        results = calculator(request.user)
        serializer = DynamicMeasurementPointSerializer(results, many=True)
        return Response(serializer.data)


class MeasurementViewSet(WgerOwnerObjectModelViewSet):
    """
    API endpoint for measurements
    POST request returns 400
    """

    permission_classes = [IsAuthenticated]
    serializer_class = MeasurementSerializer
    is_private = True
    ordering_fields = '__all__'
    filterset_class = MeasurementEntryFilterSet

    def get_owner_objects(self):
        """
        Return objects to check for ownership permission
        """
        return [(Category, 'category')]

    def get_queryset(self):
        """
        Only allow access to appropriate objects
        """
        # REST API generation
        if getattr(self, 'swagger_fake_view', False):
            return Measurement.objects.none()

        return Measurement.objects.filter(category__user=self.request.user)

    def perform_create(self, serializer):
        """
        Block creating measurements for dynamic categories.
        Dynamic categories are computed, not stored.
        """
        category = serializer.validated_data.get('category')
        if category and category.is_dynamic:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                'Cannot add measurements to a dynamic category. '
                'Values are computed automatically from the formula.'
            )
        super().perform_create(serializer)
