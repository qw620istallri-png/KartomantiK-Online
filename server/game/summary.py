"""End-of-game summary: score over the turns and each player's highlights."""
from collections import Counter


class SummaryMixin:
    def rules_live_points(self, player_id):
        """Points a player holds right now: Vessel cards plus effect points."""
        player = self.players[player_id]
        card_points = self.card_points or {}
        vessel = sum(card_points.get(card_id, 0) for card_id in player["zones"]["receptacle"])
        return vessel + int(player.get("score") or 0)

    def record_score_history(self, turn):
        """Called when a turn ends: the points of each player at that moment."""
        if any(entry["turn"] == turn for entry in self.score_history):
            return
        self.score_history.append({
            "turn": turn,
            "scores": {player_id: self.rules_live_points(player_id) for player_id in self.players},
        })

    def freeze_end_summary(self):
        """Before a player leaves an ended game: keep the summary as it is."""
        if self.ended and self.final_summary is None:
            self.final_summary = self.game_summary()

    def ended_summary(self):
        """The summary shown on the end screen: frozen once a player leaves the
        ended game, so their column, points and highlights stay."""
        return self.final_summary or self.game_summary()

    def game_summary(self):
        players = {
            player_id: {"confrontationsWon": 0, "actions": 0, "keyCardId": None}
            for player_id in self.players
        }
        won_cards = {player_id: Counter() for player_id in self.players}
        played_cards = {player_id: Counter() for player_id in self.players}
        stalemates = 0
        for entry in self.log:
            details = entry.get("details") or {}
            if entry["type"] == "rules_confrontation_compared":
                winner_id = details.get("winnerId")
                if details.get("stalemate"):
                    stalemates += 1
                elif winner_id in players:
                    players[winner_id]["confrontationsWon"] += 1
                    won_cards[winner_id].update(details.get("winnerCardIds") or [])
            elif entry["type"] == "rules_action_declared" and entry.get("actorId") in players:
                players[entry["actorId"]]["actions"] += 1
                card_id = (details.get("source") or {}).get("cardId")
                if card_id:
                    played_cards[entry["actorId"]][card_id] += 1
        for player_id, summary in players.items():
            # the card that won the most confrontations, else the one played the most
            ranked = won_cards[player_id].most_common(1) or played_cards[player_id].most_common(1)
            summary["keyCardId"] = ranked[0][0] if ranked else None
            summary["keyCardWins"] = won_cards[player_id][summary["keyCardId"]] if ranked else 0
        final_turn = self.phase_tracker["turn"]
        history = [entry for entry in self.score_history if entry["turn"] < final_turn]
        history.append({
            "turn": final_turn,
            "scores": {player_id: self.rules_live_points(player_id) for player_id in self.players},
        })
        return {
            "turns": final_turn,
            # kept with the summary: a player who leaves the ended game still
            # shows under their name
            "names": {player_id: player.get("name") for player_id, player in self.players.items()},
            "stalemates": stalemates,
            "players": players,
            "scoreHistory": history,
            "durationSeconds": int(max(0, (self.log[-1]["timestamp"] if self.log else self.created_at) - self.created_at)),
        }
