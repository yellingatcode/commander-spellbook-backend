import re
from itertools import combinations
from datetime import datetime
from django.db.models import TextField, Count, Q
from django.contrib import admin
from django.utils.html import format_html
from django.utils.formats import localize
from django.utils.text import normalize_newlines
from django.forms import Textarea
from django.contrib.admin import ModelAdmin
from spellbook.models.validators import ORACLE_SYMBOL
from spellbook.variants.variants_generator import DEFAULT_CARD_LIMIT


def datetime_to_html(datetime: datetime) -> str | None:
    if datetime is None:
        return None
    return format_html('<span class="local-datetime" data-iso="{}">{}</span>', datetime.isoformat(), localize(datetime))


def upper_oracle_symbols(text: str):
    return re.sub(r'\{' + ORACLE_SYMBOL + r'\}', lambda m: m.group(0).upper(), text, flags=re.IGNORECASE)


class NormalizedTextareaWidget(Textarea):
    def value_from_datadict(self, data, files, name: str):
        return normalize_newlines(super().value_from_datadict(data, files, name))


class SpellbookModelAdmin(ModelAdmin):
    formfield_overrides = {
        TextField: {'widget': NormalizedTextareaWidget},
    }

    def get_form(self, request, obj, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)

        def clean_mana_needed(self):
            if self.cleaned_data['mana_needed']:
                result = upper_oracle_symbols(self.cleaned_data['mana_needed'])
                return result
            return self.cleaned_data['mana_needed']
        form.clean_mana_needed = clean_mana_needed
        return form


class SearchMultipleRelatedMixin:
    def get_search_results(self, request, queryset, search_term: str):
        result = queryset
        may_have_duplicates = False
        for sub_term in search_term.split(' + '):
            sub_term = sub_term.strip()
            if sub_term:
                result, d = super().get_search_results(request, result, sub_term)
                may_have_duplicates |= d
        return result, may_have_duplicates


class IdentityFilter(admin.SimpleListFilter):
    title = 'identity'
    parameter_name = 'identity'

    def lookups(self, request, model_admin):
        return [(i, i) for i in (''.join(t) or 'C' for length in range(6) for t in combinations('WUBRG', length))]

    def queryset(self, request, queryset):
        if self.value() is not None:
            return queryset.filter(identity=self.value())
        return queryset

    def get_facet_counts(self, pk_attname, filtered_qs):
        counts = {}
        for i, choice in enumerate(self.lookup_choices):
            counts[f"{i}__c"] = Count(
                pk_attname,
                filter=Q(identity=choice[0])
            )
        return counts


class CardsCountListFilter(admin.SimpleListFilter):
    title = 'cards count'
    parameter_name = 'cards_count'
    one_more_than_max = DEFAULT_CARD_LIMIT + 1
    one_more_than_max_display = f'{one_more_than_max}+'

    def lookups(self, request, model_admin):
        return [(i, str(i)) for i in range(2, CardsCountListFilter.one_more_than_max)] + [(CardsCountListFilter.one_more_than_max_display, CardsCountListFilter.one_more_than_max_display)]

    def queryset(self, request, queryset):
        value = self.value()
        if value is None:
            return queryset
        if value == CardsCountListFilter.one_more_than_max_display:
            return queryset.filter(cards_count__gte=CardsCountListFilter.one_more_than_max)
        value = int(value)
        return queryset.filter(cards_count=value)

    def get_facet_counts(self, pk_attname, filtered_qs):
        counts = {}
        for i, choice in enumerate(self.lookup_choices):
            value = choice[0]
            counts[f"{i}__c"] = Count(
                pk_attname,
                filter=Q(cards_count=value) if value != CardsCountListFilter.one_more_than_max_display else Q(cards_count__gte=CardsCountListFilter.one_more_than_max)
            )
        return counts
