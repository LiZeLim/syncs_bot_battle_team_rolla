from collections import defaultdict, deque
import random
from typing import Optional, Tuple, Union, cast
from risk_helper.game import Game
from risk_shared.models.card_model import CardModel
from risk_shared.queries.query_attack import QueryAttack
from risk_shared.queries.query_claim_territory import QueryClaimTerritory
from risk_shared.queries.query_defend import QueryDefend
from risk_shared.queries.query_distribute_troops import QueryDistributeTroops
from risk_shared.queries.query_fortify import QueryFortify
from risk_shared.queries.query_place_initial_troop import QueryPlaceInitialTroop
from risk_shared.queries.query_redeem_cards import QueryRedeemCards
from risk_shared.queries.query_troops_after_attack import QueryTroopsAfterAttack
from risk_shared.queries.query_type import QueryType
from risk_shared.records.moves.move_attack import MoveAttack
from risk_shared.records.moves.move_attack_pass import MoveAttackPass
from risk_shared.records.moves.move_claim_territory import MoveClaimTerritory
from risk_shared.records.moves.move_defend import MoveDefend
from risk_shared.records.moves.move_distribute_troops import MoveDistributeTroops
from risk_shared.records.moves.move_fortify import MoveFortify
from risk_shared.records.moves.move_fortify_pass import MoveFortifyPass
from risk_shared.records.moves.move_place_initial_troop import MovePlaceInitialTroop
from risk_shared.records.moves.move_redeem_cards import MoveRedeemCards
from risk_shared.records.moves.move_troops_after_attack import MoveTroopsAfterAttack
from risk_shared.records.record_attack import RecordAttack
from risk_shared.records.types.move_type import MoveType


class BotState:
    def __init__(self):
        self.enemy: Optional[int] = None


def main():
    game = Game()
    bot_state = BotState()

    while True:
        query = game.get_next_query()

        def choose_move(query: QueryType) -> MoveType:
            match query:
                case QueryClaimTerritory() as q:
                    return handle_claim_territory(game, bot_state, q)

                case QueryPlaceInitialTroop() as q:
                    return handle_place_initial_troop(game, bot_state, q)

                case QueryRedeemCards() as q:
                    return handle_redeem_cards(game, bot_state, q)

                case QueryDistributeTroops() as q:
                    return handle_distribute_troops(game, bot_state, q)

                case QueryAttack() as q:
                    return handle_attack(game, bot_state, q)

                case QueryTroopsAfterAttack() as q:
                    return handle_troops_after_attack(game, bot_state, q)

                case QueryDefend() as q:
                    return handle_defend(game, bot_state, q)

                case QueryFortify() as q:
                    return handle_fortify(game, bot_state, q)

        game.send_move(choose_move(query))


def handle_claim_territory(
    game: Game, bot_state: BotState, query: QueryClaimTerritory
) -> MoveClaimTerritory:
    unclaimed_territories = game.state.get_territories_owned_by(None)
    my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
    adjacent_territories = game.state.get_all_adjacent_territories(my_territories)
    available = list(set(unclaimed_territories) & set(adjacent_territories))

    if len(available) != 0:

        def count_adjacent_friendly(x: int) -> int:
            return len(set(my_territories) & set(game.state.map.get_adjacent_to(x)))

        selected_territory = sorted(
            available, key=lambda x: count_adjacent_friendly(x), reverse=True
        )[0]
    else:
        selected_territory = sorted(
            unclaimed_territories,
            key=lambda x: len(game.state.map.get_adjacent_to(x)),
            reverse=True,
        )[0]

    return game.move_claim_territory(query, selected_territory)


def handle_place_initial_troop(
    game: Game, bot_state: BotState, query: QueryPlaceInitialTroop
) -> MovePlaceInitialTroop:
    border_territories = game.state.get_all_border_territories(
        game.state.get_territories_owned_by(game.state.me.player_id)
    )
    border_territory_models = [game.state.territories[x] for x in border_territories]
    min_troops_territory = min(border_territory_models, key=lambda x: x.troops)

    return game.move_place_initial_troop(query, min_troops_territory.territory_id)


def handle_redeem_cards(
    game: Game, bot_state: BotState, query: QueryRedeemCards
) -> MoveRedeemCards:
    card_sets: list[Tuple[CardModel, CardModel, CardModel]] = []
    cards_remaining = game.state.me.cards.copy()

    while len(cards_remaining) >= 5:
        card_set = game.state.get_card_set(cards_remaining)
        assert card_set != None
        card_sets.append(card_set)
        cards_remaining = [card for card in cards_remaining if card not in card_set]

    if game.state.card_sets_redeemed > 12 and query.cause == "turn_started":
        card_set = game.state.get_card_set(cards_remaining)
        while card_set != None:
            card_sets.append(card_set)
            cards_remaining = [card for card in cards_remaining if card not in card_set]
            card_set = game.state.get_card_set(cards_remaining)

    return game.move_redeem_cards(
        query, [(x[0].card_id, x[1].card_id, x[2].card_id) for x in card_sets]
    )


def handle_distribute_troops(
    game: Game, bot_state: BotState, query: QueryDistributeTroops
) -> MoveDistributeTroops:
    total_troops = game.state.me.troops_remaining
    distributions = defaultdict(lambda: 0)
    border_territories = game.state.get_all_border_territories(
        game.state.get_territories_owned_by(game.state.me.player_id)
    )

    if len(game.state.me.must_place_territory_bonus) != 0:
        assert total_troops >= 2
        distributions[game.state.me.must_place_territory_bonus[0]] += 2
        total_troops -= 2

    if len(game.state.recording) < 4000:
        troops_per_territory = total_troops // len(border_territories)
        leftover_troops = total_troops % len(border_territories)
        for territory in border_territories:
            distributions[territory] += troops_per_territory
        distributions[border_territories[0]] += leftover_troops
    else:
        my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
        weakest_players = sorted(
            game.state.players.values(),
            key=lambda x: sum(
                [
                    game.state.territories[y].troops
                    for y in game.state.get_territories_owned_by(x.player_id)
                ]
            ),
        )

        for player in weakest_players:
            bordering_enemy_territories = set(
                game.state.get_all_adjacent_territories(my_territories)
            ) & set(game.state.get_territories_owned_by(player.player_id))
            if len(bordering_enemy_territories) > 0:
                selected_territory = list(
                    set(
                        game.state.map.get_adjacent_to(
                            list(bordering_enemy_territories)[0]
                        )
                    )
                    & set(my_territories)
                )[0]
                distributions[selected_territory] += total_troops
                break

    return game.move_distribute_troops(query, distributions)


def handle_attack(
    game: Game, bot_state: BotState, query: QueryAttack
) -> Union[MoveAttack, MoveAttackPass]:
    my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
    bordering_territories = game.state.get_all_adjacent_territories(my_territories)

    def attack_weakest(territories: list[int]) -> Optional[MoveAttack]:
        territories = sorted(
            territories, key=lambda x: game.state.territories[x].troops
        )
        for candidate_target in territories:
            if (
                game.state.territories[candidate_target].occupier
                != game.state.me.player_id
            ):
                candidate_attackers = sorted(
                    list(
                        set(game.state.map.get_adjacent_to(candidate_target))
                        & set(my_territories)
                    ),
                    key=lambda x: game.state.territories[x].troops,
                    reverse=True,
                )
                for candidate_attacker in candidate_attackers:
                    if (
                        game.state.territories[candidate_attacker].troops
                        >= game.state.territories[candidate_target].troops + 1
                    ):
                        return game.move_attack(
                            query,
                            candidate_attacker,
                            candidate_target,
                            min(
                                3, game.state.territories[candidate_attacker].troops - 1
                            ),
                        )
        return None

    if (
        bot_state.enemy is None
        or len(game.state.get_territories_owned_by(bot_state.enemy)) == 0
    ):
        strongest_player = sorted(
            game.state.players.values(),
            key=lambda x: len(game.state.get_territories_owned_by(x.player_id)),
            reverse=True,
        )[0]
        bot_state.enemy = strongest_player.player_id

    enemy_territories = game.state.get_territories_owned_by(bot_state.enemy)
    valid_targets = list(set(bordering_territories) & set(enemy_territories))

    move = attack_weakest(valid_targets)
    if move:
        return move

    return game.move_attack_pass(query)


def handle_troops_after_attack(
    game: Game, bot_state: BotState, query: QueryTroopsAfterAttack
) -> MoveTroopsAfterAttack:
    """After conquering a territory in an attack, you must move troops to the new territory."""

    # First we need to get the record that describes the attack, and then the move that specifies
    # which territory was the attacking territory.
    record_attack = cast(RecordAttack, game.state.recording[query.record_attack_id])
    move_attack = cast(MoveAttack, game.state.recording[record_attack.move_attack_id])

    # We will always move the maximum number of troops we can.
    return game.move_troops_after_attack(
        query, game.state.territories[move_attack.attacking_territory].troops - 1
    )


def handle_defend(game: Game, bot_state: BotState, query: QueryDefend) -> MoveDefend:
    """If you are being attacked by another player, you must choose how many troops to defend with."""

    # We will always defend with the most troops that we can.

    # First we need to get the record that describes the attack we are defending against.
    move_attack = cast(MoveAttack, game.state.recording[query.move_attack_id])
    defending_territory = move_attack.defending_territory

    # We can only defend with up to 2 troops, and no more than we have stationed on the defending
    # territory.
    defending_troops = min(game.state.territories[defending_territory].troops, 2)
    return game.move_defend(query, defending_troops)


def handle_fortify(
    game: Game, bot_state: BotState, query: QueryFortify
) -> Union[MoveFortify, MoveFortifyPass]:
    fortifiable_territories = set()
    visited = set()

    def add_fortifiable(x: int) -> None:
        fortifiable_territories.add(x)
        visited.add(x)
        for territory in game.state.map.get_adjacent_to(x):
            if (
                territory not in visited
                and game.state.territories[territory].occupier == game.state.me.player_id
            ):
                add_fortifiable(territory)

    for territory in game.state.get_territories_owned_by(game.state.me.player_id):
        add_fortifiable(territory)

    candidates = []
    for territory in fortifiable_territories:
        for adjacent in game.state.map.get_adjacent_to(territory):
            if (
                game.state.territories[adjacent].occupier != game.state.me.player_id
                and game.state.territories[territory].troops > 1
            ):
                candidates.append(territory)
                break

    if len(candidates) == 0:
        return game.move_fortify_pass(query)

    from_territory = sorted(
        candidates, key=lambda x: game.state.territories[x].troops, reverse=True
    )[0]
    to_territory = sorted(
        list(
            set(game.state.map.get_adjacent_to(from_territory))
            & fortifiable_territories
        ),
        key=lambda x: game.state.territories[x].troops,
    )[0]

    return game.move_fortify(
        query,
        from_territory,
        to_territory,
        game.state.territories[from_territory].troops - 1,
    )


main()
