from rest_framework import generics

from core.api import OrganizationAPIMixin
from .models import Budget
from .serializers import BudgetSerializer


class BudgetListCreate(OrganizationAPIMixin, generics.ListCreateAPIView):
    queryset = Budget.objects.select_related("category")
    serializer_class = BudgetSerializer


class BudgetDetail(OrganizationAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Budget.objects.select_related("category")
    serializer_class = BudgetSerializer
