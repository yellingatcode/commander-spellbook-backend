from enum import Enum
import json
import hashlib
import logging
from typing import Iterable, Optional
from dataclasses import dataclass, field
from django.db import transaction
from .models import Card, Feature, Combo, Job, Template, Variant
import pyomo.environ as pyo
from pyomo.opt import TerminationCondition
from pyomo.opt.base.solvers import OptSolver
from pyomo.core.expr.numeric_expr import LinearExpression

MAX_CARDS_IN_COMBO = 5


class NodeState(Enum):
    NOT_VISITED = 0
    VISITING = 1
    VISITED = 2


class Node:
    state: NodeState = NodeState.NOT_VISITED
    depth: int = 0
    down: bool = False


@dataclass
class CardNode(Node):
    card: Card

    def __hash__(self):
        return hash(self.card) + 7 * hash('card')


@dataclass
class TemplateNode(Node):
    template: Template

    def __hash__(self):
        return hash(self.template) + 7 * hash('template')


@dataclass
class FeatureNode(Node):
    feature: Feature
    cards: list[CardNode]
    produced_by_combos: list['ComboNode']
    needed_by_combos: list['ComboNode']

    def __hash__(self):
        return hash(self.feature) + 7 * hash('feature')


@dataclass
class ComboNode(Node):
    combo: Combo
    cards: list[CardNode]
    templates: list[TemplateNode]
    features_needed: list[FeatureNode]
    features_produced: list[FeatureNode]

    def __hash__(self):
        return hash(self.combo) + 7 * hash('combo')


@dataclass(frozen=True)
class VariantIngredients:
    cards: list[CardNode]
    templates: list[TemplateNode]
    combos: list[ComboNode]
    features: list[FeatureNode]


@dataclass
class VariantDefinition:
    card_ids: list[int]
    template_ids: list[int]
    of_ids: set[int]
    feature_ids: set[int]
    included_ids: set[int]


def base_model(nodes: Iterable[Node]) -> Optional[pyo.ConcreteModel]:
    model = pyo.ConcreteModel(name='Spellbook')
    combos: set[ComboNode] = set()
    features: set[FeatureNode] = set()
    templates: set[TemplateNode] = set()
    cards: set[CardNode] = set()
    for node in nodes:
        match node:
            case CardNode(_):
                cards.add(node)
            case TemplateNode(_):
                templates.add(node)
            case FeatureNode(_, _, _):
                features.add(node)
            case ComboNode(_, _, _, _):
                combos.add(node)
            case _:
                raise ValueError(f'Unknown node type: {node}')
    model.B = pyo.Set(initialize=[c.combo.id for c in combos])
    model.F = pyo.Set(initialize=[f.feature.id for f in features])
    model.C = pyo.Set(initialize=[c.card.id for c in cards])
    model.T = pyo.Set(initialize=[t.template.id for t in templates])
    if len(model.C) == 0:
        return None
    model.b = pyo.Var(model.B, domain=pyo.Boolean)
    model.f = pyo.Var(model.F, domain=pyo.Boolean)
    model.c = pyo.Var(model.C, domain=pyo.Boolean)
    model.t = pyo.Var(model.T, domain=pyo.Boolean)
    # Variants constraints
    model.vexpr = LinearExpression(
        constant=0,
        linear_coefs=[1] * (len(model.c) + len(model.t)),
        linear_vars=[model.c[i] for i in model.c] + [model.t[i] for i in model.t])
    model.V = pyo.Constraint(expr=model.vexpr <= MAX_CARDS_IN_COMBO)
    # Combo constraints
    model.BC = pyo.ConstraintList()
    model.BF = pyo.ConstraintList()
    model.BT = pyo.ConstraintList()
    model.BCFT = pyo.ConstraintList()
    for combo_node in combos:
        b = model.b[combo_node.combo.id]
        card_vars = []
        for card_node in combo_node.cards:
            if card_node.down or card_node.card.id in model.C:
                c = model.c[card_node.card.id]
                card_vars.append(c)
                model.BC.add(b <= c)
        template_vars = []
        for template_node in combo_node.templates:
            if template_node.down or template_node.template.id in model.T:
                t = model.t[template_node.template.id]
                template_vars.append(t)
                model.BT.add(b <= t)
        feature_vars = []
        for feature_node in combo_node.features_needed:
            if feature_node.down or feature_node.feature.id in model.F:
                f = model.f[feature_node.feature.id]
                feature_vars.append(f)
                model.BF.add(b <= f)
        model.BCFT.add(b >= sum(card_vars + feature_vars + template_vars) - len(card_vars) - len(feature_vars) - len(template_vars) + 1)
    # Feature constraints
    model.FC = pyo.ConstraintList()
    model.FB = pyo.ConstraintList()
    model.FCB = pyo.ConstraintList()
    for feature_node in features:
        f = model.f[feature_node.feature.id]
        card_vars = []
        for card_node in feature_node.cards:
            if card_node.card.id in model.c:
                c = model.c[card_node.card.id]
                card_vars.append(c)
                model.FC.add(f >= c)
        combo_vars = []
        for combo_node in feature_node.produced_by_combos:
            if combo_node.combo.id in model.b:
                b = model.b[combo_node.combo.id]
                combo_vars.append(b)
                model.FB.add(f >= b)
        model.FCB.add(f <= sum(card_vars + combo_vars))
    # Minimize cards, maximize features and combos
    count_templates = len(model.t)
    model.objexpr1 = LinearExpression(
        constant=0,
        linear_coefs=[count_templates + 1] * len(model.c) + [1] * count_templates,
        linear_vars=model.vexpr.linear_vars
    )
    model.MinimizeCardsObj = pyo.Objective(
        expr=model.objexpr1,
        sense=pyo.minimize)
    count_features = len(model.f)
    model.objexpr2 = LinearExpression(
        constant=0,
        linear_coefs=[count_features + 1] * len(model.b) + [1] * count_features,
        linear_vars=[model.b[i] for i in model.b] + [model.f[i] for i in model.f]
    )
    model.MaximizeCombosObj = pyo.Objective(
        expr=model.objexpr2,
        sense=pyo.maximize)
    model.MinimizeCardsObj.deactivate()
    model.MaximizeCombosObj.deactivate()
    model.Variants = pyo.ConstraintList()
    model.Sequential = pyo.ConstraintList()
    return model


def combo_model(model: pyo.ConcreteModel, combo_id: int) -> pyo.ConcreteModel:
    model.XB = pyo.Constraint(expr=model.b[combo_id] >= 1)
    return model


def solve_combo_model(model: pyo.ConcreteModel, opt: OptSolver) -> bool:
    model.MinimizeCardsObj.activate()
    results = opt.solve(model, tee=False)
    model.MinimizeCardsObj.deactivate()
    if results.solver.termination_condition == TerminationCondition.optimal:
        model.Sequential.add(model.MinimizeCardsObj <= pyo.value(model.MinimizeCardsObj))
        model.MaximizeCombosObj.activate()
        results = opt.solve(model, tee=False)
        model.MaximizeCombosObj.deactivate()
        model.Sequential.clear()
        if results.solver.termination_condition == TerminationCondition.optimal:
            return True
    return False


def create_solver() -> OptSolver:
    return pyo.SolverFactory('glpk')


class Data:
    def __init__(self):
        self.combos = Combo.objects.prefetch_related('uses', 'requires', 'needs', 'removes', 'produces')
        self.features = Feature.objects.prefetch_related('cards', 'produced_by_combos', 'needed_by_combos', 'removed_by_combos')
        self.cards = Card.objects.prefetch_related('features', 'used_in_combos')
        self.variants = Variant.objects.prefetch_related('uses', 'requires')
        self.utility_features_ids = frozenset[int](Feature.objects.filter(utility=True).values_list('id', flat=True))
        self.templates = Template.objects.prefetch_related('required_by_combos')
        self.not_working_variants = [frozenset[int](v.uses.values_list('id', flat=True)) for v in self.variants.filter(status=Variant.Status.NOT_WORKING)]


class Graph:
    def __init__(self, data: Data):
        if data is not None:
            self.data = data
            self.cnodes = dict[int, CardNode]((card.id, CardNode(card)) for card in data.cards)
            self.tnodes = dict[int, TemplateNode]((template.id, TemplateNode(template)) for template in data.templates)
            self.fnodes = dict[int, FeatureNode]((feature.id, FeatureNode(feature, [self.cnodes[i.id] for i in feature.cards.all()], [], [])) for feature in data.features)
            self.bnodes = dict[int, ComboNode]()
            for combo in data.combos:
                node = ComboNode(combo,
                    cards=[self.cnodes[i.id] for i in combo.uses.all()],
                    templates=[self.tnodes[i.id] for i in combo.requires.all()],
                    features_needed=[self.fnodes[i.id] for i in combo.needs.all()],
                    features_produced=[self.fnodes[i.id] for i in combo.produces.all()])
                self.bnodes[combo.id] = node
                for feature in combo.produces.all():
                    featureNode = self.fnodes[feature.id]
                    featureNode.produced_by_combos.append(node)
                for feature in combo.needs.all():
                    featureNode = self.fnodes[feature.id]
                    featureNode.needed_by_combos.append(node)
        else:
            raise Exception('Invalid arguments')

    def reset(self) -> bool:
        for node in self.cnodes.values():
            node.state = NodeState.NOT_VISITED
            node.depth = 0
            node.down = False
        for node in self.tnodes.values():
            node.state = NodeState.NOT_VISITED
            node.depth = 0
            node.down = False
        for node in self.fnodes.values():
            node.state = NodeState.NOT_VISITED
            node.depth = 0
            node.down = False
        for node in self.bnodes.values():
            node.state = NodeState.NOT_VISITED
            node.depth = 0
            node.down = False
        return True

    def variants(self, combo_id: int) -> Iterable[VariantIngredients]:
        combo = self.bnodes[combo_id]
        # Down step
        nodes = self._combo_nodes_down(combo)
        for n in nodes:
            n.down = True
        # Up step
        for node in nodes.copy():
            ups = set()
            match node:
                case FeatureNode(_, _, _):
                    ups = self._feature_nodes_up(node)
                case ComboNode(_, _, _, _):
                    ups = self._combo_nodes_up(node)
            nodes.update(ups)
        base = base_model(nodes)
        if base is None:
            return []
        model = combo_model(base, combo_id)
        opt = create_solver()
        while solve_combo_model(model, opt):
            card_id_list = sorted([v for v in model.c if model.c[v].value == 1], key=lambda c: self.cnodes[c].depth)
            template_id_list = {v for v in model.t if model.t[v].value == 1}
            feature_id_list = {v for v in model.f if model.f[v].value == 1}
            combo_id_list = {v for v in model.b if model.b[v].value == 1}
            yield VariantIngredients(
                cards=[self.cnodes[i] for i in card_id_list],
                features=[self.fnodes[i] for i in feature_id_list],
                combos=[self.bnodes[i] for i in combo_id_list],
                templates=[self.tnodes[i] for i in template_id_list]
            )
            # Eclude any solution containing the current variant of the combo, from now on
            model.Variants.add(sum(model.c[i] for i in card_id_list) <= len(card_id_list) - 1)

    def _combo_nodes_down(self, combo: ComboNode, base_cards_amount: int = 0, depth: int = 0) -> set[Node]:
        combo.state = NodeState.VISITING
        cards: set[ComboNode] = set()
        for c in combo.cards:
            if c.state == NodeState.NOT_VISITED:
                cards.add(c)
        templates: set[TemplateNode] = set()
        for t in combo.templates:
            if t.state == NodeState.NOT_VISITED:
                templates.add(t)
        cards_amount = len(cards) + len(templates) + base_cards_amount
        if cards_amount > MAX_CARDS_IN_COMBO:
            return set()
        this_combo_set = {combo}
        if len(combo.features_needed) == 0:
            for node in cards | templates:
                node.state = NodeState.VISITED
                node.depth = depth
            return cards | templates | this_combo_set
        needed_features: set[FeatureNode] = set()
        nodes_from_features: set[Node] = set()
        for f in combo.features_needed:
            if f.state == NodeState.VISITING:
                return set()
            nodesf = self._feature_nodes_down(f, cards_amount, depth + 1)
            if len(nodesf) == 0:
                return set()
            needed_features.add(f)
            nodes_from_features.update(nodesf)
        for node in cards | templates | needed_features:
            node.state = NodeState.VISITED
            node.depth = depth
        return cards | templates | needed_features | nodes_from_features | this_combo_set

    def _feature_nodes_down(self, feature: FeatureNode, base_cards_amount: int = 0, depth: int = 0) -> set[Node]:
        feature.state = NodeState.VISITING
        cards: set[ComboNode] = set()
        for c in feature.cards:
            if c.state == NodeState.NOT_VISITED:
                cards.add(c)
        combos: set[ComboNode] = set()
        other: set[Node] = set()
        for c in feature.produced_by_combos:
            if c.state == NodeState.NOT_VISITED:
                new_other = self._combo_nodes_down(c, base_cards_amount, depth + 1)
                if len(new_other) > 0:
                    combos.add(c)
                    other.update(new_other)
        for node in cards | combos:
            node.depth = depth
        return cards | combos | other

    def _combo_nodes_up(self, combo: ComboNode) -> set[Node]:
        combo.state = NodeState.VISITING
        features: set[FeatureNode] = set()
        other: set[Node] = set()
        for f in combo.features_produced:
            if f.state == NodeState.NOT_VISITED:
                features.add(f)
                other.update(self._feature_nodes_up(f))
                f.state = NodeState.VISITED
        return features | other

    def _feature_nodes_up(self, feature: FeatureNode) -> set[Node]:
        feature.state = NodeState.VISITING
        combos: set[ComboNode] = set()
        other: set[Node] = set()
        for c in feature.needed_by_combos:
            if c.state == NodeState.NOT_VISITED:
                combos.add(c)
                other.update(self._combo_nodes_up(c))
                c.state = NodeState.VISITED
        return combos | other


def unique_id_from_cards_and_templates_ids(cards: list[int], templates: list[int]) -> str:
    hash_algorithm = hashlib.sha256()
    hash_algorithm.update(json.dumps({'c': sorted(cards), 't': sorted(templates)}).encode('utf-8'))
    return hash_algorithm.hexdigest()


def subtract_removed_features(variant: Variant, features: set[int]) -> set[int]:
    return features - set(variant.includes.values_list('removes__id', flat=True))


def merge_identities(identities: Iterable[str]):
    i = set(''.join(identities).upper())
    return ''.join([color for color in 'WUBRG' if color in i])


def includes_any(v: set[int], others: Iterable[set[int]]) -> bool:
    for o in others:
        if v.issuperset(o):
            return True
    return False


def update_variant(
        data: Data,
        unique_id: str,
        variant_def: VariantDefinition,
        status: Variant.Status,
        restore=False):
    variant = data.variants.get(unique_id=unique_id)
    variant.of.set(variant_def.of_ids)
    variant.includes.set(variant_def.included_ids)
    variant.produces.set(subtract_removed_features(variant, variant_def.feature_ids) - data.utility_features_ids)
    variant.identity = merge_identities(variant.uses.values_list('identity', flat=True))
    ok = status == Variant.Status.OK or \
        status != Variant.Status.NOT_WORKING and not includes_any(v=frozenset(variant_def.card_ids), others=data.not_working_variants)
    if restore:
        combos = data.combos.filter(id__in=variant_def.included_ids)
        variant.zone_locations = '\n'.join(c.zone_locations for c in combos if len(c.zone_locations) > 0)
        variant.cards_state = '\n'.join(c.cards_state for c in combos if len(c.cards_state) > 0)
        variant.other_prerequisites = '\n'.join(c.other_prerequisites for c in combos if len(c.other_prerequisites) > 0)
        variant.mana_needed = ' '.join(c.mana_needed for c in combos if len(c.mana_needed) > 0)
        variant.description = '\n'.join(c.description for c in combos if len(c.description) > 0)
        variant.status = Variant.Status.NEW if ok else Variant.Status.NOT_WORKING
    if not ok:
        variant.status = Variant.Status.NOT_WORKING
    if not ok or restore:
        variant.save()
    return variant.id


def create_variant(
        data: Data,
        unique_id: str,
        variant_def: VariantDefinition):
    combos = data.combos.filter(id__in=variant_def.included_ids)
    zone_locations = '\n'.join(c.zone_locations for c in combos if len(c.zone_locations) > 0)
    cards_state = '\n'.join(c.cards_state for c in combos if len(c.cards_state) > 0)
    other_prerequisites = '\n'.join(c.other_prerequisites for c in combos if len(c.other_prerequisites) > 0)
    mana_needed = ' '.join(c.mana_needed for c in combos if len(c.mana_needed) > 0)
    description = '\n'.join(c.description for c in combos if len(c.description) > 0)
    ok = not includes_any(v=frozenset(variant_def.card_ids), others=data.not_working_variants)
    variant = Variant(
        unique_id=unique_id,
        zone_locations=zone_locations,
        cards_state=cards_state,
        other_prerequisites=other_prerequisites,
        mana_needed=mana_needed,
        description=description,
        identity=merge_identities(data.cards.filter(id__in=variant_def.card_ids).values_list('identity', flat=True)))
    if not ok:
        variant.status = Variant.Status.NOT_WORKING
    variant.save()
    variant.uses.set(variant_def.card_ids)
    variant.requires.set(variant_def.template_ids)
    variant.of.set(variant_def.of_ids)
    variant.includes.set(variant_def.included_ids)
    variant.produces.set(subtract_removed_features(variant, variant_def.feature_ids) - data.utility_features_ids)
    return variant.id


def get_variants_from_graph(data: Data) -> dict[str, VariantDefinition]:
    logging.info('Computing all possible variants:')
    combos = data.combos.filter(generator=True)
    result = dict[str, VariantDefinition]()
    graph = Graph(data)
    total = combos.count()
    for i, combo in enumerate(combos):
        variants = graph.variants(combo.id)
        for variant in variants:
            cards_ids = [cn.card.id for cn in variant.cards]
            templates_ids = [tn.template.id for tn in variant.templates]
            unique_id = unique_id_from_cards_and_templates_ids(cards_ids, templates_ids)
            feature_ids = {fn.feature.id for fn in variant.features}
            combo_ids = {cn.combo.id for cn in variant.combos}
            if unique_id in result:
                x = result[unique_id]
                x.of_ids.add(combo.id)
                x.included_ids.update(combo_ids)
                x.feature_ids.update(feature_ids)
            else:
                logging.info(f'Found new variant for combo {combo.id} ({i + 1}/{total}): {unique_id}')
                result[unique_id] = VariantDefinition(
                    card_ids=cards_ids,
                    template_ids=templates_ids,
                    feature_ids=feature_ids,
                    included_ids=combo_ids,
                    of_ids={combo.id})
        graph.reset()
        logging.info(f'{i + 1}/{total} combos processed')
    return result


def generate_variants(job: Job = None) -> tuple[int, int, int]:
    logging.info('Fetching variants set to RESTORE...')
    data = Data()
    to_restore = set(data.variants.filter(status=Variant.Status.RESTORE).values_list('unique_id', flat=True))
    logging.info('Fetching all variant unique ids...')
    old_id_set = set(data.variants.values_list('unique_id', flat=True))
    logging.info('Computing combos MILP representation...')
    variants = get_variants_from_graph(data)
    logging.info(f'Saving {len(variants)} variants...')
    if job:
        with transaction.atomic(durable=True):
            job.message += f'Saving {len(variants)} variants...\n'
            job.save()
    variants_ids = set()
    with transaction.atomic():
        for unique_id, variant_def in variants.items():
            if unique_id in old_id_set:
                status = data.variants.get(unique_id=unique_id).status
                update_variant(
                    data=data,
                    unique_id=unique_id,
                    variant_def=variant_def,
                    status=status,
                    restore=unique_id in to_restore)
            else:
                variants_ids.add(
                    create_variant(
                        data=data,
                        unique_id=unique_id,
                        variant_def=variant_def))
        if job is not None:
            job.variants.set(variants_ids)
        new_id_set = set(variants.keys())
        to_delete = old_id_set - new_id_set
        added = new_id_set - old_id_set
        restored = new_id_set & to_restore
        logging.info(f'Added {len(added)} new variants.')
        logging.info(f'Updated {len(restored)} variants.')
        delete_query = data.variants.filter(unique_id__in=to_delete, frozen=False)
        deleted = delete_query.count()
        delete_query.delete()
        logging.info(f'Deleted {deleted} variants...')
        logging.info('Done.')
        return len(added), len(restored), deleted
