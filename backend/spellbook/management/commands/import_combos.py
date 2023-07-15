import json
import gzip
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from dataclasses import dataclass
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.db.models import Max, Count
from djangorestframework_camel_case.util import camelize
from spellbook.variants.variants_generator import id_from_cards_and_templates_ids, generate_variants
from spellbook.models import Feature, Card, Job, Combo, CardInCombo, Variant, IngredientInCombination, CardInVariant
from spellbook.models.validators import MANA_SYMBOL
from spellbook.management.s3_upload import upload_json_to_aws
from ..scryfall import scryfall, update_cards


@dataclass(frozen=True)
class ImportedVariantBulkSaveItem:
    combo: Combo
    uses: list[CardInCombo]
    produces: list[Feature]


def sorted_prereq_search_terms(prereq: str, card_set: set[str]) -> list[str]:
    pre_lower = prereq.lower()
    terms = card_set | {'all permanents', 'all other permanents', 'all other cards', 'all cards', 'both cards', 'both permanents'}
    found_terms = list[tuple[str, int]]()
    for term in terms:
        lower_term = term.lower()
        regex = rf'(?:^|[^\w])({re.escape(lower_term)})(?:[^\w]|$)'
        search_result = re.search(regex, pre_lower)
        first_occurrence = None
        if search_result:
            first_occurrence = search_result.start(1)
        if '//' in term:
            complete_lower_term = lower_term
            split_over_slashes = complete_lower_term.partition('//')
            lower_term = split_over_slashes[0].strip()
            regex = rf'(?:^|[^\w])({re.escape(lower_term)})(?:[^\w]|$)'
            search_result = re.search(regex, pre_lower)
            if search_result:
                if first_occurrence is None or search_result.start(1) < first_occurrence:
                    first_occurrence = search_result.start(1)
            if ',' in lower_term:
                lower_term = lower_term.partition(',')[0]
                regex = rf'(?:^|[^\w])({re.escape(lower_term)})(?:[^\w]|$)'
                search_result = re.search(regex, pre_lower)
                if search_result:
                    if first_occurrence is None or search_result.start(1) < first_occurrence:
                        first_occurrence = search_result.start(1)
            lower_term = split_over_slashes[2].strip()
            regex = rf'(?:^|[^\w])({re.escape(lower_term)})(?:[^\w]|$)'
            search_result = re.search(regex, pre_lower)
            if search_result:
                if first_occurrence is None or search_result.start(1) < first_occurrence:
                    first_occurrence = search_result.start(1)
            if ',' in lower_term:
                lower_term = lower_term.partition(',')[0]
                regex = rf'(?:^|[^\w])({re.escape(lower_term)})(?:[^\w]|$)'
                search_result = re.search(regex, pre_lower)
                if search_result:
                    if first_occurrence is None or search_result.start(1) < first_occurrence:
                        first_occurrence = search_result.start(1)
            if first_occurrence is not None:
                found_terms.append((term, first_occurrence))
                continue
        elif ',' in term:
            lower_term = lower_term.partition(',')[0]
            regex = rf'(?:^|[^\w])({re.escape(lower_term)})(?:[^\w]|$)'
            search_result = re.search(regex, pre_lower)
            if search_result:
                if first_occurrence is None or search_result.start(1) < first_occurrence:
                    first_occurrence = search_result.start(1)
        if first_occurrence is not None:
            found_terms.append((term, first_occurrence))
    return [item[0] for item in sorted(found_terms, key=lambda item: item[1])]


def find_card_in_prereq(card_name: str, prerequisites: str) -> list[tuple[str, str, str]]:  # sentence, punctuation, following
    regex = r'(.*?)' + re.escape(card_name) + r'(.*?)(\.|[^\w](?:with(?! the other)(?=(.+?)(?:\.|$))|if|when|who|named by|does|has|naming|power|attached|as|from|increase)[^\w]|$)'
    negated_regex = r'(?:[^\w](?:with|if|when|who|named by|does|has|naming|power|attached|on|from|opponent|increase)[^\w])'
    matches = []
    for sentence in prerequisites.split('.'):
        for item in re.findall(regex, sentence + '.', re.IGNORECASE):
            if not re.search(negated_regex, item[0], re.IGNORECASE) and item[2].strip(' .,;').lower() not in {'who', 'named by', 'does', 'has', 'naming', 'power', 'attached', 'from'}:
                matches.append((item[1].strip(), item[2].strip(), item[3].strip()))
    return matches


def find_combos() -> list[tuple[str, tuple[str, ...], frozenset[str], str, str, str, dict[str, tuple[str, int, int, str]]]]:
    """Fetches the combos from the google sheet.
    Result format: id, cards, produced, prerequisite, description, mana, dictionary of prerequistes positions (card name -> (position_code, order, half_number, status))"""
    combo_to_produces = dict[frozenset[str], frozenset[str]]()
    combos_to_prerequisites = dict[frozenset[str], str]()
    combos_to_description = dict[frozenset[str], str]()
    combos_reverse_id = dict[frozenset[str], str]()
    combos_to_card_ordered = dict[frozenset[str], tuple[str, ...]]()
    # Commander Spellbook database fetching
    req = Request(
        'https://sheets.googleapis.com/v4/spreadsheets/1KqyDRZRCgy8YgMFnY0tHSw_3jC99Z0zFvJrPbfm66vA/values:batchGet?ranges=combos!A2:Q&key=AIzaSyBD_rcme5Ff37Evxa4eW5BFQZkmTbgpHew')
    with urlopen(req) as response:
        data = json.loads(response.read().decode())
        for row in data['valueRanges'][0]['values']:
            card_list = [name.lower().strip(' \t\n\r') for name in row[1:11] if name is not None and len(name) > 0]
            cards = tuple(dict.fromkeys(c for c in card_list if len(c) > 0))
            cards_set = frozenset(cards)
            if len(cards) <= 1:
                continue
            combos_reverse_id[cards_set] = row[0]
            pros = [token.replace('.', '') for token in row[14].strip(' \t\n\r').split('. ')]
            combo_to_produces[cards_set] = frozenset(pros)
            combos_to_prerequisites[cards_set] = row[12]
            combos_to_description[cards_set] = row[13]
            combos_to_card_ordered[cards_set] = cards
    result = []
    for card_set in combo_to_produces:
        id = combos_reverse_id[card_set]
        features = frozenset(combo_to_produces[card_set])
        prerequisites = combos_to_prerequisites[card_set]
        mana_regex = r'^(.*?)\s*((?:\{' + MANA_SYMBOL + r'\})+) available([^\.]*)\.(.*)$'
        mana_match = re.match(mana_regex, prerequisites, re.IGNORECASE)
        mana = ''
        if mana_match:
            prerequisites = mana_match.group(1) + mana_match.group(4)
            mana = mana_match.group(2).upper() + mana_match.group(3)
        new_prerequisites = prerequisites
        positions_dict = dict[str, tuple[str, int, int, str]]()
        position_order = 0
        for c in sorted_prereq_search_terms(prerequisites, card_set):
            half = 0
            status = ''
            positions = find_card_in_prereq(c, prerequisites)
            c_short_name = None
            if len(positions) == 0 and '//' in c:
                c_short_name = c.partition('//')[0].strip()
                half = 1
                positions = find_card_in_prereq(c_short_name, prerequisites)
                if len(positions) == 0 and ',' in c_short_name:
                    c_short_name = c_short_name.partition(',')[0]
                    positions = find_card_in_prereq(c_short_name, prerequisites)
                if len(positions) == 0:
                    c_short_name = c.partition('//')[2].strip()
                    half = 2
                    positions = find_card_in_prereq(c_short_name, prerequisites)
                    if len(positions) == 0 and ',' in c_short_name:
                        c_short_name = c_short_name.partition(',')[0]
                        positions = find_card_in_prereq(c_short_name, prerequisites)
            elif len(positions) == 0 and ',' in c:
                c_short_name = c.partition(',')[0]
                positions = find_card_in_prereq(c_short_name, prerequisites)
            for position in positions:
                p_list = list[IngredientInCombination.ZoneLocation]()
                if re.search(r'(?:[^\w]|^)hand(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list.append(IngredientInCombination.ZoneLocation.HAND)
                if re.search(r'(?:[^\w]|^)battlefield(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list.append(IngredientInCombination.ZoneLocation.BATTLEFIELD)
                    if re.search(r'(?:[^\w]|^)tapped(?:[^\w]|$)', position[0], re.IGNORECASE):
                        if status != '':
                            raise Exception('Status already set')
                        status = 'tapped'
                    if re.search(r'(?:[^\w]|^)untapped(?:[^\w]|$)', position[0], re.IGNORECASE):
                        if status != '':
                            raise Exception('Status already set')
                        status = 'untapped'
                    if re.search(r'(?:[^\w]|^)face down(?:[^\w]|$)', position[0], re.IGNORECASE):
                        if status != '':
                            raise Exception('Status already set')
                        status = 'face down'
                if re.search(r'(?:[^\w]|^)command zone(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list.append(IngredientInCombination.ZoneLocation.COMMAND_ZONE)
                if re.search(r'(?:[^\w]|^)graveyard(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list.append(IngredientInCombination.ZoneLocation.GRAVEYARD)
                if re.search(r'(?:[^\w]|^)exiled?(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list.append(IngredientInCombination.ZoneLocation.EXILE)
                    if re.search(r'(?:[^\w]|^)by(?:[^\w]|$)', position[0], re.IGNORECASE):
                        if status != '':
                            raise Exception('Status already set')
                        after_by = re.split(r'(?:[^\w]|^)by(?:[^\w]|$)', position[0], maxsplit=2, flags=re.IGNORECASE)[1]
                        status = f'exiled by {after_by}'
                    if position[1] == 'with':
                        modification = position[2]
                        modification = re.sub(r'([^\w]|^)them([^\w]|$)', r'\1it\2', modification, flags=re.IGNORECASE)
                        modification = re.sub(r'([^\w]|^)(cage|kick) counters([^\w]|$)', r'\1a \2 counter\3', modification, flags=re.IGNORECASE)
                        status += f'with {modification}'
                if re.search(r'(?:[^\w]|^)foretold(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list.append(IngredientInCombination.ZoneLocation.EXILE)
                if re.search(r'(?:[^\w]|^)library(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list.append(IngredientInCombination.ZoneLocation.LIBRARY)
                if re.search(r'(?:[^\w]|^)any zone(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list = [''.join(choice[0] for choice in IngredientInCombination.ZoneLocation.choices)]
                if re.search(r'(?:[^\w]|^)or(?:[^\w]|$)', position[0], re.IGNORECASE) or re.search(r'(?:[^\w]|^)with the other(?:[^\w]|$)', position[0], re.IGNORECASE):
                    if re.search(r'(?:[\w]|^)and/or(?:[^\w]|$)', position[0], re.IGNORECASE):
                        continue
                    elif len(p_list) > 1:
                        p_list = [''.join(p_list)]
                    elif not re.search(r'(?:[^\w]|^)instant or sorcery(?:[^\w]|$)', position[0], re.IGNORECASE):
                        raise Exception(f'Found invalid "or" in "{prerequisites}"')
                if len(p_list) == 1:
                    if c in positions_dict:
                        raise Exception(f'Found duplicate positioning for {c} in {prerequisites}')
                    positions_dict[c] = (p_list[0], position_order, half, status)
                    position_order += 1
                    if position[1] == '.':
                        if re.search(r'(?:\w|^),(?:[^\w]|$)', position[0], re.IGNORECASE):
                            new_prerequisites = re.subn(r'\s?' + re.escape(c_short_name if c_short_name else c) + r'[^,\.]*,[^\w](and[^\w])?', '', new_prerequisites, 1, re.IGNORECASE)[0].strip()
                        elif re.search(r'(?:[^\w]|^)and(?:[^\w]|$)', position[0], re.IGNORECASE):
                            new_prerequisites = re.subn(r'\s?' + re.escape(c_short_name if c_short_name else c) + r'[^,\.]*,?[^\w]and[^\w]', '', new_prerequisites, 1, re.IGNORECASE)[0].strip()
                        else:
                            new_prerequisites = re.subn(r'\s?' + re.escape(c_short_name if c_short_name else c) + r' ([^,\.]+)\.', '', new_prerequisites, 1, re.IGNORECASE)[0].strip()
                elif len(p_list) > 1:
                    raise Exception(f'Found {len(p_list)} positions for {c} in {prerequisites}')
        description = combos_to_description[card_set]
        result.append((id, combos_to_card_ordered[card_set], features, new_prerequisites, description, mana, positions_dict))
    return result


def format_feature_name(feature: str) -> str:
    feature = feature.strip()
    return feature[0].upper() + feature[1:]


class Command(BaseCommand):
    help = 'Tries to import combos from the google sheet'

    def add_arguments(self, parser):
        parser.add_argument(
            '--s3',
            action='store_true',
            dest='s3',
        )

    def log_job(self, job, message, style=lambda x: x):
        self.stdout.write(style(message))
        job.message += message + '\n'
        job.save(update_fields=['message'])

    def update_and_load_cards(self, job, x) -> tuple[dict[str, Card], dict[str, object]]:
        self.log_job(job, 'Fetching combos...done')
        self.log_job(job, 'Fetching scryfall dataset...')
        scryfall_db = scryfall()
        self.log_job(job, 'Fetching scryfall dataset...done')
        cards_from_combos: set[str] = {c.lower() for t in x for c in t[1]}
        self.log_job(job, f'Found {len(cards_from_combos)} cards, updating cards in database...')
        spellbook_cards = list(Card.objects.all())
        oracle_cards_in_database = {str(c.oracle_id): c for c in spellbook_cards}
        name_cards_in_database = {c.name: c for c in spellbook_cards}
        combo_card_name_to_card = dict[str, Card]()
        for i, card in enumerate(cards_from_combos):
            self.stdout.write(f'{i+1}/{len(cards_from_combos)} {card}')
            if card in scryfall_db:
                data = scryfall_db[card]
            else:
                self.log_job(job, f'Card {card} not found in Scryfall JSON, fetching...')
                scryreq = Request(
                    'https://api.scryfall.com/cards/named?' + urlencode({'fuzzy': card}))
                with urlopen(scryreq) as response:
                    data = json.loads(response.read().decode())
                    scryfall_db[card] = data
                self.log_job(job, f'Card {card} fetched')
            save_card = False
            if data['oracle_id'] in oracle_cards_in_database:
                c = oracle_cards_in_database[data['oracle_id']]
            elif data['name'] in name_cards_in_database:
                c = name_cards_in_database[data['name']]
                c.oracle_id = data['oracle_id']
                save_card = True
            else:
                c = Card.objects.create(name=data['name'], oracle_id=data['oracle_id'])
                oracle_cards_in_database[str(c.oracle_id)] = c
                name_cards_in_database[c.name] = c
                save_card = True
            updated_cards = update_cards(
                [c],
                scryfall_db,
                lambda x: self.log_job(job, x),
                lambda x: self.log_job(job, x, self.style.WARNING),
                lambda x: self.log_job(job, x, self.style.ERROR),
            )
            if len(updated_cards) > 0:
                c = updated_cards[0]
                save_card = True
            if save_card:
                self.stdout.write(f'Updating card {c.name}...')
                c.save()
                oracle_cards_in_database[str(c.oracle_id)] = c
                name_cards_in_database[c.name] = c
                self.stdout.write(f'Updating card {c.name}...done')
            combo_card_name_to_card[card] = c
        self.log_job(job, 'Done fetching cards')
        return combo_card_name_to_card, scryfall_db

    def handle(self, *args, **options):
        job = Job.start('import_combos')
        if job is None:
            self.stdout.write(self.style.ERROR('Job already running'))
            return
        job.save()
        try:
            self.log_job(job, 'Fetching combos...')
            x = find_combos()
            self.log_job(job, 'Found {} combos'.format(len(x)))
            combo_card_name_to_card, combo_card_name_to_scryfall = self.update_and_load_cards(job, x)
            self.log_job(job, 'Importing combos...')
            variant_id_map = dict[int, str]()
            bulk_combo_dict = dict[str, ImportedVariantBulkSaveItem]()
            existing_unique_ids = {id_from_cards_and_templates_ids([c.id for c in combo.uses.all()], []) for combo in Combo.objects.prefetch_related('uses')}
            with transaction.atomic(durable=True):
                existing_feature_names = {f.name.lower(): f for f in Feature.objects.all()}
                next_id = (Combo.objects.aggregate(Max('id'))['id__max'] or 0) + 1
                for i, (old_id, _cards, produced, prerequisite, description, mana_needed, positions) in enumerate(x):
                    self.stdout.write(f'{i+1}/{len(x)}\n' if (i + 1) % 100 == 0 else '.', ending='')
                    cards_from_combo = [combo_card_name_to_card[c] for c in _cards]
                    used_cards_types = dict[Card, str]()
                    for c, (p, _, half, status) in positions.items():
                        if c in _cards:
                            actual_card = combo_card_name_to_card[c]
                            actual_card_name = actual_card.name.lower()
                            used_cards_types[actual_card] = combo_card_name_to_scryfall[actual_card_name]['type_line']
                            if half > 0:
                                used_cards_types[actual_card] = used_cards_types[actual_card].partition('//')[0 if half == 1 else 2].strip()
                    permanents_from_combo = [c for c in cards_from_combo if any(t in used_cards_types.get(c, combo_card_name_to_scryfall[c.name.lower()]['type_line']) for t in ('Creature', 'Planeswalker', 'Artifact', 'Enchantment', 'Battle', 'Land'))]
                    cardincombo_list = list[CardInCombo]()
                    for c, (p, _, half, status) in sorted(positions.items(), key=lambda x: x[1][1]):
                        if c in _cards:
                            actual_card = combo_card_name_to_card[c]
                            cardincombo_list.append(CardInCombo(card=actual_card, zone_locations=p, card_state=status))
                        elif c == 'all permanents':
                            for card in permanents_from_combo:
                                if card in [c.card for c in cardincombo_list]:
                                    raise ValueError(f'Card {card} already used')
                                cardincombo_list.append(CardInCombo(card=card, zone_locations=p, card_state=status))
                        elif c == 'both permanents':
                            if len(permanents_from_combo) != 2:
                                raise ValueError(f'Expected 2 permanents, got {len(permanents_from_combo)}')
                            for card in permanents_from_combo:
                                if card in [c.card for c in cardincombo_list]:
                                    raise ValueError(f'Card {card} already used')
                                cardincombo_list.append(CardInCombo(card=card, zone_locations=p, card_state=status))
                        elif c == 'all other permanents':
                            for card in permanents_from_combo:
                                if card not in [c.card for c in cardincombo_list]:
                                    cardincombo_list.append(CardInCombo(card=card, zone_locations=p, card_state=status))
                        elif c == 'all other cards':
                            for card in cards_from_combo:
                                if card not in [c.card for c in cardincombo_list]:
                                    cardincombo_list.append(CardInCombo(card=card, zone_locations=p, card_state=status))
                        elif c == 'all cards':
                            for card in cards_from_combo:
                                if card in [c.card for c in cardincombo_list]:
                                    raise ValueError(f'Card {card} already used')
                                cardincombo_list.append(CardInCombo(card=card, zone_locations=p, card_state=status))
                        elif c == 'both cards':
                            if len(cards_from_combo) != 2:
                                raise ValueError(f'Expected 2 cards, got {len(cards_from_combo)}')
                            for card in cards_from_combo:
                                if card in [c.card for c in cardincombo_list]:
                                    raise ValueError(f'Card {card} already used')
                                cardincombo_list.append(CardInCombo(card=card, zone_locations=p, card_state=status))
                        else:
                            raise ValueError(f'Unknown card {c}')
                    for card in cards_from_combo:
                        card_in_combos = [c for c in cardincombo_list if c.card == card]
                        locations = [c.zone_locations for c in card_in_combos]
                        if len(locations) == 0:
                            self.log_job(job, f'Card {card} doesn\'t appear in prerequisites of combo {old_id}.', self.style.WARNING)
                            cardincombo_list.append(CardInCombo(card=card, zone_locations=IngredientInCombination.ZoneLocation.HAND, card_state=status))
                        elif len(locations) == 1:
                            pass
                        else:
                            first = locations[0]
                            if all(item == first for item in locations):
                                index = cardincombo_list.index(card_in_combos[0])
                                cardincombo_list = list[CardInCombo](c for c in cardincombo_list if c.card != card)
                                cardincombo_list.insert(index, card_in_combos[0])
                            else:
                                raise ValueError(f'Card {card} used multiple times')
                    for i, card_in_combo in enumerate(sorted(cardincombo_list, key=lambda c: cards_from_combo.index(c.card))):
                        card_in_combo.order = i
                    id = id_from_cards_and_templates_ids([c.id for c in cards_from_combo], [])
                    old_id = int(old_id)
                    variant_id_map[old_id] = id
                    if id in existing_unique_ids:
                        self.stdout.write(f'\nSkipping combo [{id}] {cards_from_combo}: already present in variants')
                        continue
                    if id in bulk_combo_dict:
                        self.stdout.write(f'\nSkipping combo [{id}] {cards_from_combo}: already present in imported variants')
                        continue
                    combo = Combo(
                        id=next_id,
                        other_prerequisites=prerequisite.replace('. ', '.\n'),
                        description=description.replace('. ', '.\n'),
                        kind=Combo.Kind.GENERATOR if len(cardincombo_list) < 6 else Combo.Kind.GENERATOR_WITH_MANY_CARDS,
                        mana_needed=mana_needed,
                    )
                    for cic in cardincombo_list:
                        cic.combo = combo
                    next_id += 1
                    produces_dict = {}
                    for name in (format_feature_name(p) for p in produced):
                        if name in produces_dict:
                            continue
                        name_lower = name.lower()
                        if name_lower in existing_feature_names:
                            produces_dict[name] = existing_feature_names[name_lower]
                        else:
                            feature = Feature(name=name)
                            feature.save()
                            produces_dict[name] = feature
                            existing_feature_names[name_lower] = feature
                    produces = list(produces_dict.values())
                    bulk_item = ImportedVariantBulkSaveItem(
                        combo=combo,
                        uses=cardincombo_list,
                        produces=produces,
                    )
                    bulk_combo_dict[id] = bulk_item
                self.log_job(job, 'Saving combos...')
                Combo.objects.bulk_create(b.combo for b in bulk_combo_dict.values())
                CardInCombo.objects.bulk_create(b for item in bulk_combo_dict.values() for b in item.uses)
                ProducesTable = Combo.produces.through
                ProducesTable.objects.bulk_create(ProducesTable(combo=item.combo, feature=f) for item in bulk_combo_dict.values() for f in item.produces)
                self.log_job(job, 'Saving combos...done')

            camelized_json = camelize(variant_id_map)
            if options['s3']:
                self.log_job(job, 'Uploading variant id map...')
                upload_json_to_aws(camelized_json, 'variant_id_map.json')
                self.log_job(job, 'Uploading variant id map...done')
            else:
                self.log_job(job, 'Saving variant id map...')
                variant_id_map_file: Path = settings.STATIC_BULK_FOLDER / 'variant_id_map.json'
                output = variant_id_map_file.resolve()
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open('w', encoding='utf8') as f, gzip.open(str(output) + '.gz', mode='wt', encoding='utf8') as fz:
                    json.dump(camelized_json, f)
                    json.dump(camelized_json, fz)
                self.log_job(job, 'Saving variant id map...done')

            self.log_job(job, 'Generating variants...')
            added, restored, deleted = generate_variants(job)
            self.log_job(job, f'Generating variants...done. Added {added} variants, restored {restored} variants, deleted {deleted} variants.')
            annotated_variants = Variant.objects.annotate(includes_count=Count('includes'))
            annotated_variants.filter(id__in=bulk_combo_dict.keys(), includes_count=1).update(status=Variant.Status.OK)
            bulk_civ_to_update = list[CardInVariant]()
            bulk_variants_to_update = list[Variant]()
            suspicious_variants = annotated_variants.filter(id__in=bulk_combo_dict.keys(), includes_count__gt=1)
            self.log_job(job, f'There are {suspicious_variants.count()} variants with multiple includes. They are probably redundant.')
            for suspicious_variant in suspicious_variants:
                source_combo = bulk_combo_dict[suspicious_variant.id]
                suspicious_variant.description = source_combo.combo.description
                suspicious_variant.mana_needed = source_combo.combo.mana_needed
                suspicious_variant.other_prerequisites = source_combo.combo.other_prerequisites
                used_cards = {c.card: c for c in source_combo.uses}
                for used_card in suspicious_variant.cardinvariant_set.all():
                    if used_card.card in used_cards:
                        cic = used_cards[used_card.card]
                        used_card.zone_locations = cic.zone_locations
                        used_card.batlefield_card_state = cic.battlefield_card_state
                        used_card.exile_card_state = cic.exile_card_state
                        used_card.graveyard_card_state = cic.graveyard_card_state
                        used_card.library_card_state = cic.library_card_state
                        bulk_civ_to_update.append(used_card)
                suspicious_variant.status = Variant.Status.OK
                bulk_variants_to_update.append(suspicious_variant)
            CardInVariant.objects.bulk_update(bulk_civ_to_update, ['zone_locations', 'batlefield_card_state', 'exile_card_state', 'graveyard_card_state', 'library_card_state'])
            Variant.objects.bulk_update(bulk_variants_to_update, ['description', 'mana_needed', 'other_prerequisites', 'status'])
            self.log_job(job, f'Successfully imported {len(bulk_combo_dict)}/{len(x)} combos. The rest was already present.', self.style.SUCCESS)
            job.termination = timezone.now()
            job.status = Job.Status.SUCCESS
            job.save()
        except Exception as e:
            job.termination = timezone.now()
            job.status = Job.Status.FAILURE
            job.message = f'Failed to import combos: {e}'
            job.save()
            print(e)
            raise e
