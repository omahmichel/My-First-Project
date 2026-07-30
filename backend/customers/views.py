from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.models import Business, BusinessMembership
from .models import Customer
from .serializers import CustomerSerializer


class BusinessCustomerAccessMixin:
    # Resolves one active business visible to the authenticated user.

    def get_business_and_role(self):
        if hasattr(self, "_business_and_role"):
            return self._business_and_role

        user = self.request.user

        business = get_object_or_404(
            Business.objects.filter(
                Q(owner=user)
                | Q(
                    memberships__user=user,
                    memberships__is_active=True,
                )
            )
            .select_related("owner")
            .distinct(),
            pk=self.kwargs["business_id"],
            status=Business.Status.ACTIVE,
        )

        if business.owner_id == user.id:
            role = BusinessMembership.Role.OWNER
        else:
            membership = get_object_or_404(
                BusinessMembership,
                business=business,
                user=user,
                is_active=True,
            )
            role = membership.role

        self._business_and_role = (business, role)
        return self._business_and_role

    def require_customer_write_access(self):
        # Owners, managers and cashiers can create or update customers.
        business, role = self.get_business_and_role()

        if role not in (
            BusinessMembership.Role.OWNER,
            BusinessMembership.Role.MANAGER,
            BusinessMembership.Role.CASHIER,
        ):
            return None, Response(
                {
                    "detail": (
                        "Your role does not allow customer changes."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return business, None

    def require_customer_remove_access(self):
        # Only owners and managers can remove customer records.
        business, role = self.get_business_and_role()

        if role not in (
            BusinessMembership.Role.OWNER,
            BusinessMembership.Role.MANAGER,
        ):
            return None, Response(
                {
                    "detail": (
                        "Only an owner or manager can remove a customer."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return business, None

    def get_serializer_context(self):
        business, role = self.get_business_and_role()

        return {
            "request": self.request,
            "business": business,
            "current_role": role,
        }

    def get_active_customer(self):
        business, _ = self.get_business_and_role()

        return get_object_or_404(
            Customer.objects.select_related(
                "business",
                "created_by",
            ),
            pk=self.kwargs["customer_id"],
            business=business,
            is_active=True,
        )


class BusinessCustomerListCreateAPIView(
    BusinessCustomerAccessMixin,
    APIView,
):
    # Lists active customers and creates customers inside one business.

    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business, _ = self.get_business_and_role()

        customers = (
            Customer.objects.filter(
                business=business,
                is_active=True,
            )
            .select_related("business", "created_by")
            .order_by("name", "phone")
        )

        serializer = CustomerSerializer(
            customers,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    def post(self, request, business_id):
        _, denied_response = self.require_customer_write_access()

        if denied_response:
            return denied_response

        serializer = CustomerSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        customer = serializer.save()

        return Response(
            CustomerSerializer(
                customer,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )


class BusinessCustomerDetailAPIView(
    BusinessCustomerAccessMixin,
    APIView,
):
    # Retrieves, updates or softly deactivates one isolated customer.

    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id, customer_id):
        customer = self.get_active_customer()

        return Response(
            CustomerSerializer(
                customer,
                context=self.get_serializer_context(),
            ).data
        )

    def patch(self, request, business_id, customer_id):
        _, denied_response = self.require_customer_write_access()

        if denied_response:
            return denied_response

        customer = self.get_active_customer()
        serializer = CustomerSerializer(
            customer,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def put(self, request, business_id, customer_id):
        _, denied_response = self.require_customer_write_access()

        if denied_response:
            return denied_response

        customer = self.get_active_customer()
        serializer = CustomerSerializer(
            customer,
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def delete(self, request, business_id, customer_id):
        _, denied_response = self.require_customer_remove_access()

        if denied_response:
            return denied_response

        customer = self.get_active_customer()
        customer.is_active = False
        customer.save(update_fields=("is_active", "updated_at"))

        return Response(status=status.HTTP_204_NO_CONTENT)
