from collections import defaultdict, deque
import random
import math
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


# We will store our enemy in the bot state.
class BotState():
    def __init__(self):
        self.enemy: Optional[int] = None


def main():

    # Get the game object, which will connect you to the engine and
    # track the state of the game.
    game = Game()
    bot_state = BotState()

    # Respond to the engine's queries with your moves.
    while True:

        # Get the engine's query (this will block until you receive a query).
        query = game.get_next_query()

        # Based on the type of query, respond with the correct move.
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

        # Send the move to the engine.
        game.send_move(choose_move(query))

def handle_claim_territory(
    game: Game, bot_state: BotState, query: QueryClaimTerritory
) -> MoveClaimTerritory:
    """At the start of the game, you can claim a single unclaimed territory every turn
    until all the territories have been claimed by players."""

    unclaimed_territories = game.state.get_territories_owned_by(None)
    my_territories = game.state.get_territories_owned_by(game.state.me.player_id)

    # Define the territories for Australia and South America
    australia_territories = {38, 39, 40, 41}
    south_america_territories = {28, 29, 30, 31}

    # Find the unclaimed territories in Australia and South America
    unclaimed_australia = list(australia_territories & set(unclaimed_territories))
    unclaimed_south_america = list(
        south_america_territories & set(unclaimed_territories)
    )

    # Check if we already own any territories in Australia or South America
    own_australia = list(australia_territories & set(my_territories))
    own_south_america = list(south_america_territories & set(my_territories))

    # Prioritize claiming in Australia first, then South America
    if unclaimed_australia and not own_south_america:
        selected_territory = unclaimed_australia[0]
    elif unclaimed_south_america and not own_australia:
        selected_territory = unclaimed_south_america[0]
    else:
        # We will try to always pick new territories that are next to ones that we own,
        # or a random one if that isn't possible.
        adjacent_territories = game.state.get_all_adjacent_territories(my_territories)

        # We can only pick from territories that are unclaimed and adjacent to us.
        available = list(set(unclaimed_territories) & set(adjacent_territories))
        if available:
            # We will pick the one with the most connections to our territories
            # this should make our territories clustered together a little bit.
            def count_adjacent_friendly(x: int) -> int:
                return len(set(my_territories) & set(game.state.map.get_adjacent_to(x)))

            selected_territory = sorted(
                available, key=lambda x: count_adjacent_friendly(x), reverse=True
            )[0]
        else:
            # Or if there are no such territories, we will pick just an unclaimed one with the greatest degree.
            selected_territory = sorted(
                unclaimed_territories,
                key=lambda x: len(game.state.map.get_adjacent_to(x)),
                reverse=True,
            )[0]

    return game.move_claim_territory(query, selected_territory)

def handle_place_initial_troop(
    game: Game, bot_state: BotState, query: QueryPlaceInitialTroop
) -> MovePlaceInitialTroop:
    """After all the territories have been claimed, you can place a single troop on one
    of your territories each turn until each player runs out of troops."""

    australia_region = [40, 41, 38, 39]
    south_america_region = [30, 31, 29, 28]

    my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
    unclaimed_territories = game.state.get_territories_owned_by(None)

    # Function to check if a region is fully claimed
    def is_region_claimed(region):
        return all(territory in my_territories for territory in region)

    # Prioritize placing troops to secure Australia, then South America
    def place_troops_for_region(region):
        for territory in region:
            if territory in my_territories:
                # Place troop on territory with the fewest troops
                if game.state.territories[territory].troops < 5:
                    return game.move_place_initial_troop(query, territory)
        # If all territories have more troops than the threshold, place it on the first territory owned by the bot
        for territory in region:
            if territory in my_territories:
                return game.move_place_initial_troop(query, territory)

    # Check if we need to focus on Australia
    if not is_region_claimed(australia_region):
        move = place_troops_for_region(australia_region)
        if move:
            return move

    # Check if we need to focus on South America
    if not is_region_claimed(south_america_region):
        move = place_troops_for_region(south_america_region)
        if move:
            return move

    # Get the list of border territories
    border_territories = game.state.get_all_border_territories(my_territories)

    # Function to count the number of enemy territories adjacent to a given territory
    def count_adjacent_enemies(territory: int) -> int:
        return sum(
            1
            for neighbor in game.state.map.get_adjacent_to(territory)
            if game.state.territories[neighbor].occupier != game.state.me.player_id
        )

    # Sort border territories by the number of adjacent enemies in descending order
    sorted_border_territories = sorted(
        border_territories, key=count_adjacent_enemies, reverse=True
    )

    # Find the most contested border territory to place the troop
    for territory in sorted_border_territories:
        if game.state.territories[territory].troops < 5:
            return game.move_place_initial_troop(query, territory)

    # If all territories have more troops than the threshold, place it at the most contested one
    return game.move_place_initial_troop(query, sorted_border_territories[0])


def handle_redeem_cards(game: Game, bot_state: BotState, query: QueryRedeemCards) -> MoveRedeemCards:
    """After the claiming and placing initial troops phases are over, you can redeem any
    cards you have at the start of each turn, or after killing another player."""

    # We will always redeem the minimum number of card sets we can until the 12th card set has been redeemed.
    # This is just an arbitrary choice to try and save our cards for the late game.

    # We always have to redeem enough cards to reduce our card count below five.
    card_sets: list[Tuple[CardModel, CardModel, CardModel]] = []
    cards_remaining = game.state.me.cards.copy()

    total_troops_per_player = {}
    for player in game.state.players.values():
        total_troops_per_player[player.player_id] = sum(
            [
                game.state.territories[x].troops
                for x in game.state.get_territories_owned_by(player.player_id)
            ]
        )
    least_powerful_player = min(total_troops_per_player.items(), key=lambda x: x[1])[0]

    if least_powerful_player == game.state.me.player_id:
        while len(cards_remaining) > 0:
            card_set = game.state.get_card_set(cards_remaining)
            if card_set is None:
                break
            card_sets.append(card_set)
            cards_remaining = [card for card in cards_remaining if card not in card_set]
    else:
        while len(cards_remaining) >= 5:
            card_set = game.state.get_card_set(cards_remaining)
            # According to the pigeonhole principle, we should always be able to make a set
            # of cards if we have at least 5 cards.
            assert card_set != None
            card_sets.append(card_set)
            cards_remaining = [card for card in cards_remaining if card not in card_set]

        # Remember we can't redeem any more than the required number of card sets if
        # we have just eliminated a player.
        if game.state.card_sets_redeemed > 12 and query.cause == "turn_started":
            card_set = game.state.get_card_set(cards_remaining)
            while card_set != None:
                card_sets.append(card_set)
                cards_remaining = [card for card in cards_remaining if card not in card_set]
                card_set = game.state.get_card_set(cards_remaining)

    return game.move_redeem_cards(query, [(x[0].card_id, x[1].card_id, x[2].card_id) for x in card_sets])


def handle_distribute_troops(game: Game, bot_state: BotState, query: QueryDistributeTroops) -> MoveDistributeTroops:
    """After you redeem cards (you may have chosen to not redeem any), you need to distribute
    all the troops you have available across your territories. This can happen at the start of
    your turn or after killing another player.
    """

    total_troops = game.state.me.troops_remaining
    distributions = defaultdict(lambda: 0)
    border_territories = game.state.get_all_border_territories(
        game.state.get_territories_owned_by(game.state.me.player_id)
    )

    my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
    total_troops_per_player = {}
    for player in game.state.players.values():
        total_troops_per_player[player.player_id] = sum(
            [
                game.state.territories[x].troops
                for x in game.state.get_territories_owned_by(player.player_id)
            ]
        )

    most_powerful_player = max(total_troops_per_player.items(), key=lambda x: x[1])[0]
    least_powerful_player = min(total_troops_per_player.items(), key=lambda x: x[1])[0]

    # Ensure we place the matching territory bonus
    if len(game.state.me.must_place_territory_bonus) != 0:
        assert total_troops >= 2
        distributions[game.state.me.must_place_territory_bonus[0]] += 2
        total_troops -= 2

    def distribute_evenly():
        troops_per_territory = total_troops // len(border_territories)
        leftover_troops = total_troops % len(border_territories)

        for territory in border_territories:
            distributions[territory] += troops_per_territory

            # Get the territory with the lowest number of troops
            my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
            # Get the territory with the lowest number of troops
            my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
            weakest_territory = max(
                my_territories, key=lambda x: game.state.territories[x].troops
            )

        # Add leftover troops to the strongest territory
        distributions[weakest_territory] += leftover_troops

    def doom_stack():
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

    def survival_stack():
        my_territories = game.state.get_territories_owned_by(game.state.me.player_id)

        def count_adjacent_friendly(x: int) -> int:
            return len(set(border_territories) & set(game.state.map.get_adjacent_to(x)))

        selected_territory = sorted(
            border_territories, key=lambda x: count_adjacent_friendly(x), reverse=True
        )[0]

        distributions[selected_territory] += total_troops

    # If we are the not strongest player
    if most_powerful_player == game.state.me.player_id:
        distribute_evenly()
    elif least_powerful_player != game.state.me.player_id: #doom stack if we are not the strongest
        doom_stack()
    else: #if we are the weakest player, then we need to stack on our strongest territory so that we dont die
        survival_stack()

    return game.move_distribute_troops(query, distributions)


def handle_attack(
    game: Game, bot_state: BotState, query: QueryAttack
) -> Union[MoveAttack, MoveAttackPass]:
    """After the troop phase of your turn, you may attack any number of times until you decide to
    stop attacking (by passing). After a successful attack, you may move troops into the conquered
    territory. If you eliminated a player you will get a move to redeem cards and then distribute troops.
    """

    # Get a list of your territories and the territories adjacent to them
    my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
    bordering_territories = game.state.get_all_adjacent_territories(my_territories)

    def find_disconnected_clusters(territories: list[int]) -> list[list[int]]:
        """Finds clusters of connected territories from the given list."""
        clusters = []
        visited = set()

        def dfs(territory, cluster):
            stack = [territory]
            while stack:
                current = stack.pop()
                if current not in visited:
                    visited.add(current)
                    cluster.append(current)
                    for neighbor in game.state.map.get_adjacent_to(current):
                        if neighbor in territories and neighbor not in visited:
                            stack.append(neighbor)

        for territory in territories:
            if territory not in visited:
                cluster = []
                dfs(territory, cluster)
                clusters.append(cluster)

        return clusters

    def find_intermediate_enemy_territories(clusters: list[list[int]]) -> list[int]:
        """Finds enemy territories that lie between our clusters."""
        intermediate_territories = set()
        for cluster in clusters:
            for territory in cluster:
                for neighbor in game.state.map.get_adjacent_to(territory):
                    if (
                        neighbor not in my_territories
                        and game.state.territories[neighbor].occupier
                        != game.state.me.player_id
                    ):
                        intermediate_territories.add(neighbor)
        return list(intermediate_territories)

    def attack_weakest(territories: list[int]) -> Optional[MoveAttack]:
        """Attack the weakest territory from the list."""
        territories = sorted(
            territories, key=lambda x: game.state.territories[x].troops
        )
        for candidate_target in territories:
            candidate_attackers = sorted(
                list(
                    set(game.state.map.get_adjacent_to(candidate_target))
                    & set(my_territories)
                ),
                key=lambda x: game.state.territories[x].troops,
                reverse=True,
            )
            for candidate_attacker in candidate_attackers:
                if game.state.territories[candidate_attacker].troops > 2:
                    return game.move_attack(
                        query,
                        candidate_attacker,
                        candidate_target,
                        min(3, game.state.territories[candidate_attacker].troops - 1),
                    )

    # Find disconnected clusters of our territories
    clusters = find_disconnected_clusters(my_territories)

    # Find enemy territories that are between our clusters
    intermediate_enemy_territories = find_intermediate_enemy_territories(clusters)

    # Try to attack the weakest intermediate enemy territory
    if intermediate_enemy_territories:
        move = attack_weakest(intermediate_enemy_territories)
        if move:
            return move

    # If no such territory exists, attack the weakest enemy territory adjacent to any of our territories
    enemy_territories = list(set(bordering_territories) - set(my_territories))
    move = attack_weakest(enemy_territories)
    if move:
        return move

    return game.move_attack_pass(query)


def handle_troops_after_attack(game: Game, bot_state: BotState, query: QueryTroopsAfterAttack) -> MoveTroopsAfterAttack:
    """After conquering a territory in an attack, you must move troops to the new territory."""

    # Get the record that describes the attack, and then the move that specifies which territory was the attacking territory.
    record_attack = cast(RecordAttack, game.state.recording[query.record_attack_id])
    move_attack = cast(MoveAttack, game.state.recording[record_attack.move_attack_id])

    # Determine the minimum number of troops to move
    min_troops_to_move = min(move_attack.attacking_troops, game.state.territories[move_attack.attacking_territory].troops - 1)

    if len(game.state.recording) < 2000:
        # Move half the number of troops from the attacking territory to the defending territory, rounded up
        move_troops = max(min_troops_to_move, 
                        min(game.state.territories[move_attack.attacking_territory].troops - 1, 
                            math.ceil(game.state.territories[move_attack.attacking_territory].troops / 2)))

        print(
            "Attacking Territory Troops",
            game.state.territories[move_attack.attacking_territory].troops,
            "Move Troops",
            move_troops,
        )
        if move_troops >= 2:
            return game.move_troops_after_attack(query, move_troops)
        else:
            return game.move_troops_after_attack(query, 1)
    else:
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


def handle_fortify(game: Game, bot_state: BotState, query: QueryFortify) -> Union[MoveFortify, MoveFortifyPass]:
    """At the end of your turn, you can fortify your positions by moving troops from one territory to another.
    This function will move troops from inner territories to border territories, or to other inner territories
    if they are closer to the border territories."""

    my_territories = game.state.get_territories_owned_by(game.state.me.player_id)
    border_territories = set(game.state.get_all_border_territories(my_territories))
    inner_territories = set(my_territories) - border_territories

    if not inner_territories:
        return game.move_fortify_pass(query)

    fortify_moves = []

    for inner_territory in inner_territories:
        troops_to_move = (
            game.state.territories[inner_territory].troops - 1
        )  # Always leave at least 1 troop
        if troops_to_move > 0:
            # Find the shortest path to a border territory
            path = find_shortest_path_from_vertex_to_set(
                game, inner_territory, border_territories
            )
            if path:
                next_step = path[0]
                fortify_moves.append((inner_territory, next_step, troops_to_move))

    # If we have moves to make, perform the first one (or choose a strategy to pick one)
    if fortify_moves:
        from_territory, to_territory, troops = fortify_moves[0]
        return game.move_fortify(query, from_territory, to_territory, troops)

    return game.move_fortify_pass(query)


def find_shortest_path_from_vertex_to_set(game: Game, source: int, target_set: set[int]) -> list[int]:
    """Used in move_fortify()."""

    queue = deque()
    queue.appendleft(source)

    parent = {}
    seen = {source: True}

    while queue:
        current = queue.pop()
        if current in target_set:
            break

        for neighbour in game.state.map.get_adjacent_to(current):
            if neighbour not in seen:
                seen[neighbour] = True
                parent[neighbour] = current
                queue.appendleft(neighbour)

    path = []
    while current in parent:
        path.append(current)
        current = parent[current]

    path.reverse()
    return path

if __name__ == "__main__":
    main()
