import re
from dataclasses import dataclass
from django.core.exceptions import ValidationError
from django.db.models import Q


@dataclass(frozen=True)
class QueryValue:
    prefix: str
    key: str
    operator: str
    value: str

    def is_negated(self) -> bool:
        match self.prefix:
            case '':
                return False
            case '-':
                return True
            case _:
                raise ValidationError(f'Prefix {self.prefix} is not supported for {self.key} search.')

    @classmethod
    def from_string(cls, string: str) -> 'QueryValue':
        match re.fullmatch(r'(?P<prefix>-?)(?P<key>[a-zA-Z_]+)(?P<operator><=|>=|:|=|<|>)(?:"(?P<long_value>(?:[^"\\]|\\")+)"|(?P<short_value>.+))', string):
            case None:
                raise ValidationError(f'Invalid query value: {string}')
            case match:
                return cls(match['prefix'], match['key'], match['operator'], match['long_value'] or match['short_value'])

    @classmethod
    def from_short_string(cls, string: str, key: str, operator: str) -> 'QueryValue':
        match re.fullmatch(r'(?P<prefix>-?)(?:"(?P<long_value>(?:[^"\\]|\\")+)"|(?P<short_value>.+))', string):
            case None:
                raise ValidationError(f'Invalid query value: {string}')
            case match:
                return cls(match['prefix'], key, operator, match['long_value'] or match['short_value'])


@dataclass(frozen=True)
class VariantFilter:
    q: Q
    negated: bool = False


@dataclass(frozen=True)
class VariantFilterCollection:
    cards_filters: tuple[VariantFilter, ...] = ()
    results_filters: tuple[VariantFilter, ...] = ()
    variants_filters: tuple[VariantFilter, ...] = ()

    def __and__(self, other: 'VariantFilterCollection') -> 'VariantFilterCollection':
        return VariantFilterCollection(
            cards_filters=self.cards_filters + other.cards_filters,
            results_filters=self.results_filters + other.results_filters,
            variants_filters=self.variants_filters + other.variants_filters
        )
