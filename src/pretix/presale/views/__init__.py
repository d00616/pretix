import uuid
from itertools import groupby
from datetime import timedelta

from django.db.models import Q
from django.utils.timezone import now

from pretix.base.models import CartPosition


class CartMixin:
    def get_session_key(self):
        if 'cart_key' in self.request.session:
            return self.request.session.get('cart_key')
        key = str(uuid.uuid4())
        self.request.session['cart_key'] = key
        return key


class CartDisplayMixin(CartMixin):

    def get_cart(self):
        qw = Q(session=self.get_session_key())
        if self.request.user.is_authenticated():
            qw |= Q(user=self.request.user)

        cartpos = list(CartPosition.objects.current.filter(
            qw & Q(event=self.request.event)
        ).order_by(
            'item', 'variation'
        ).select_related(
            'item', 'variation'
        ).prefetch_related(
            'variation__values', 'variation__values__prop'
        ))

        # Group items of the same variation
        # We do this by list manipulations instead of a GROUP BY query, as
        # Django is unable to join related models in a .values() query
        def keyfunc(pos):
            return pos.item_id, pos.variation_id, pos.price

        positions = []
        for k, g in groupby(sorted(cartpos, key=keyfunc), key=keyfunc):
            g = list(g)
            group = g[0]
            group.count = len(g)
            group.total = group.count * group.price
            positions.append(group)

        return {
            'positions': positions,
            'total': sum(p.total for p in positions),
            'minutes_left': (
                max(min(p.expires for p in positions) - now(), timedelta()).seconds // 60
                if positions else 0
            ),
        }


class EventViewMixin:

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['event'] = self.request.event
        return context
