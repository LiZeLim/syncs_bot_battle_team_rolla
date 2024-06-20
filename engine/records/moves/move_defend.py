from typing import Literal, cast, final
from pydantic import ValidationInfo, model_validator

from engine.game.state import State
from engine.records.base_move import BaseMove
from engine.records.moves.move_attack import MoveAttack

@final
class MoveDefend(BaseMove):
    record_type: Literal["move_defend"] = "move_defend"
    defending_troops: int

    @model_validator(mode="after")
    def _check_territory_occupied(self: 'MoveDefend', info: ValidationInfo) -> 'MoveDefend':
        state: State = info.context["state"] # type: ignore
        move_attack: int = info.context["context"] # type: ignore

        move_attack_obj = cast(MoveAttack, state.match_history[move_attack])
        if move_attack_obj.move == "pass":
            raise RuntimeError("Trying to defend attack move that was a pass.")
        
        defending_territory = move_attack_obj.move.defending_territory
        if state.territories[defending_territory].occupier != self.move_by_player:
            raise RuntimeError("Wrong player is defending.")

        if not 1 <= self.defending_troops <= 2:
            raise ValueError(f"You must commit 1 or 2 troops for the defence.")
        if state.territories[defending_territory].troops < self.defending_troops:
            raise ValueError(f"You tried to defend with more troops then you had occupying the defending territory.")
        
        return self

    def get_public_record(self):
        return self

    def commit(self, state: State) -> None:
        state.match_history.append(self)
