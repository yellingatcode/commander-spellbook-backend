import re
from django.db.models import Q, QuerySet, Count, Case, When, Value
from django.db.models.functions import Length
from collections import namedtuple, defaultdict
from typing import Callable
from .color_parser import parse_identity


QueryValue = namedtuple('QueryValue', ['prefix', 'operator', 'value'])


def card_search(q: QuerySet, cards: list[QueryValue]) -> QuerySet:
    q = q.annotate(uses_count=Count('uses', distinct=True))
    for card in cards:
        card_query = Q()
        value_is_digit = card.value.isdigit()
        match card.operator:
            case ':' if not value_is_digit:
                card_query &= Q(uses__name__icontains=card.value)
            case '=' if not value_is_digit:
                card_query &= Q(uses__name__iexact=card.value)
            case '<' if value_is_digit:
                card_query &= Q(uses_count__lt=card.value)
            case '>' if value_is_digit:
                card_query &= Q(uses_count__gt=card.value)
            case '<=' if value_is_digit:
                card_query &= Q(uses_count__lte=card.value)
            case '>=' if value_is_digit:
                card_query &= Q(uses_count__gte=card.value)
            case '=' if value_is_digit:
                card_query &= Q(uses_count=card.value)
            case _:
                raise NotSupportedError(f'Operator {card.operator} is not supported for card search with {"numbers" if value_is_digit else "strings"}.')
        if card.prefix == '-':
            card_query = ~card_query
        elif card.prefix != '':
            raise NotSupportedError(f'Prefix {card.prefix} is not supported for card search.')
        q = q.filter(card_query)
    return q


def identity_search(q: QuerySet, values: list[QueryValue]) -> QuerySet:
    q = q.annotate(identity_count=Case(When(identity='C', then=Value(0)), default=Length('identity')))
    for value in values:
        value_query = Q()
        value_is_digit = value.value.isdigit()
        identity = ''
        not_in_identity = ''
        if not value_is_digit:
            upper_value = parse_identity(value.value)
            if upper_value is None:
                raise NotSupportedError(f'Invalid color identity: {value.value}')
            for color in 'WURBG':
                if color in upper_value:
                    identity += color
                else:
                    not_in_identity += color
        match value.operator:
            case ':' if not value_is_digit:
                value_query &= Q(identity=identity)
            case '=' if not value_is_digit:
                value_query &= Q(identity=identity)
            case '<' if not value_is_digit:
                value_query &= Q(identity_count__lt=len(identity))
                for color in not_in_identity:
                    value_query &= ~Q(identity__contains=color)
            case '<=' if not value_is_digit:
                value_query &= Q(identity_count__lte=len(identity))
                for color in not_in_identity:
                    value_query &= ~Q(identity__contains=color)
            case '>' if not value_is_digit:
                value_query &= Q(identity_count__gt=len(identity))
                for color in identity:
                    value_query &= Q(identity__contains=color)
            case '>=' if not value_is_digit:
                value_query &= Q(identity_count__gte=len(identity))
                for color in identity:
                    value_query &= Q(identity__contains=color)
            case '=' if value_is_digit:
                value_query &= Q(identity_count=value.value)
            case '<' if value_is_digit:
                value_query &= Q(identity_count__lt=value.value)
            case '<=' if value_is_digit:
                value_query &= Q(identity_count__lte=value.value)
            case '>' if value_is_digit:
                value_query &= Q(identity_count__gt=value.value)
            case '>=' if value_is_digit:
                value_query &= Q(identity_count__gte=value.value)
            case _:
                raise NotSupportedError(f'Operator {value.operator} is not supported for identity search with {"numbers" if value_is_digit else "strings"}.')
        if value.prefix == '-':
            value_query = ~value_query
        elif value.prefix != '':
            raise NotSupportedError(f'Prefix {value.prefix} is not supported for identity search.')
        q = q.filter(value_query)
    return q


def prerequisites_search(q: QuerySet, values: list[QueryValue]) -> QuerySet:
    for value in values:
        prerequisites_query = Q()
        match value.operator:
            case ':':
                prerequisites_query &= Q(other_prerequisites__icontains=value.value)
            case _:
                raise NotSupportedError(f'Operator {value.operator} is not supported for prerequisites search.')
        if value.prefix == '-':
            prerequisites_query = ~prerequisites_query
        elif value.prefix != '':
            raise NotSupportedError(f'Prefix {value.prefix} is not supported for prerequisites search.')
        q = q.filter(prerequisites_query)
    return q


def steps_search(q: QuerySet, values: list[QueryValue]) -> QuerySet:
    for value in values:
        steps_query = Q()
        match value.operator:
            case ':':
                steps_query &= Q(description__icontains=value.value)
            case _:
                raise NotSupportedError(f'Operator {value.operator} is not supported for prerequisites search.')
        if value.prefix == '-':
            steps_query = ~steps_query
        elif value.prefix != '':
            raise NotSupportedError(f'Prefix {value.prefix} is not supported for prerequisites search.')
        q = q.filter(steps_query)
    return q


def spellbook_id_search(q: QuerySet, values: list[QueryValue]) -> QuerySet:
    for value in values:
        spellbook_id_query = Q()
        match value.operator:
            case ':' | '=':
                spellbook_id_query &= Q(id__istartswith=value.value)
            case _:
                raise NotSupportedError(f'Operator {value.operator} is not supported for spellbook id search.')
        if value.prefix == '-':
            spellbook_id_query = ~spellbook_id_query
        elif value.prefix != '':
            raise NotSupportedError(f'Prefix {value.prefix} is not supported for spellbook id search.')
        q = q.filter(spellbook_id_query)
    return q


keyword_map: dict[str, Callable[[QuerySet, list[QueryValue]], QuerySet]] = {
    'card': card_search,
    'coloridentity': identity_search,
    'prerequisites': prerequisites_search,
    'steps': steps_search,
    'spellbookid': spellbook_id_search,
}


alias_map: dict[str, str] = {
    'cards': 'card',
    'color_identity': 'coloridentity',
    'color': 'coloridentity',
    'colors': 'coloridentity',
    'commander': 'coloridentity',
    'id': 'coloridentity',
    'ids': 'coloridentity',
    'c': 'coloridentity',
    'ci': 'coloridentity',
    'prerequisite': 'prerequisites',
    'prereq': 'prerequisites',
    'pre': 'prerequisites',
    'step': 'steps',
    'description': 'steps',
}


QUERY_REGEX = r'(?:\s|^)(?:(?P<card_short>[a-zA-Z]+)|"(?P<card_long>[^"]+)"|(?P<prefix>-?)(?P<key>[a-zA-Z]+)(?P<operator>:|=|<|>|<=|>=)(?:(?P<value_short>[a-zA-Z0-9]+)|"(?P<value_long>[^"]+)"))(?=\s|$)'


class NotSupportedError(Exception):
    pass


def variants_query_parser(base: QuerySet, query_string: str) -> QuerySet:
    """
    Parse a query string into a Django Q object.
    """
    query_string = query_string.strip()
    regex_matches = re.finditer(QUERY_REGEX, query_string)
    parsed_queries = defaultdict[str, list[QueryValue]](list)
    queryset = base
    for regex_match in regex_matches:
        group_dict = regex_match.groupdict()
        if group_dict['card_short'] or group_dict['card_long']:
            card_term = group_dict['card_short'] or group_dict['card_long']
            parsed_queries['card'].append(QueryValue('', ':', card_term))
        elif group_dict['key']:
            key = group_dict['key']
            if key in alias_map:
                key = alias_map[key]
            if key not in keyword_map:
                raise NotSupportedError(f'Key {key} is not supported for query.')
            parsed_queries[key].append(QueryValue(group_dict['prefix'], group_dict['operator'], group_dict['value_short'] or group_dict['value_long']))
    for key, values in parsed_queries.items():
        queryset = keyword_map[key](queryset, values)
    return queryset