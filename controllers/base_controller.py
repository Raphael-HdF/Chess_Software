#! /usr/bin/env python3
# coding: utf-8

from models.constants import *
from views import View
from models import Tournament, Player, Match, DbConnect
from datetime import datetime


class Controller:
    """Main controller."""

    def __init__(self):
        self.view = View()
        self.db = DbConnect()

    def run(self):
        """
        First fonction launch by the controller to show the menu and get the input.
        :return: function
        """
        self.view.prompt_menu()
        menu_choice = self.view.ask_input("Veuillez saisir le numéro correspondant à votre choix", '[1-8]', True)
        self.db = DbConnect()

        switcher = {
            '1': self.start_tournament,
            '2': self.start_match,
            '3': self.show_tournaments,
            '4': self.edit_tournament,
            '5': self.show_results,
            '6': self.create_player,
            '7': self.show_players,
            '8': self.edit_player,
        }

        # Get the function from switcher dictionary
        func = switcher.get(menu_choice, lambda: print("Good Bye !"))
        # Execute the function
        func()
        self.run()

    def set_tournament_name(self):
        return self.view.ask_input("Nom du tournoi ?", required=True)

    def set_tournament_place(self):
        return self.view.ask_input("Emplacement du tournoi ?", required=True)

    def set_tournament_start_date(self):
        return self.view.ask_input("Date de début du tournoi ? (au format jj/mm/aaaa)", "date") or TODAY

    def set_tournament_end_date(self, start_date):
        end_date = self.view.ask_input("Date de fin du tournoi ? (au format jj/mm/aaaa)", "date")
        if end_date >= start_date:
            return end_date
        else:
            return start_date

    def set_tournament_turns(self):
        return self.view.ask_input("Nombre de tours ?", "integer") or DEFAULT_TURNS

    def set_tournament_time_control(self):
        list_regex = f"^[1-{len(TIME_CONTROL)}]*$"
        tournament_time_control = int(self.view.ask_input(
            self.view.get_list_to_print(TIME_CONTROL, "Méthode de gestion de controle de temps ?"),
            list_regex)) - 1
        return TIME_CONTROL[tournament_time_control] or TIME_CONTROL[0]

    def set_tournament_description(self):
        return self.view.ask_input("Veuillez saisir la description du tournoi") or None

    def start_tournament(self):
        """
        Ask all the inputs to init the tournament
        :return:
        """
        args = {}
        args["name"] = self.set_tournament_name()
        args["place"] = self.set_tournament_place()
        args["start_date"] = self.set_tournament_start_date()
        args["end_date"] = self.set_tournament_end_date(args["start_date"])
        args["turns"] = self.set_tournament_turns()
        args["players"] = self.assign_players()
        args["time_control"] = self.set_tournament_time_control()
        args["description"] = self.set_tournament_description()

        tournament = Tournament(**args)
        self.view.show_tournament(tournament)

        input()

    def get_pairs(self, tournament, players):
        nb_pairs = int(len(tournament["players"]) / 2)

        pairs = []
        # Creation des paires si 1er match
        if tournament["status"] == 'Doit commencer':
            for nb_pair in range(nb_pairs):
                player_1 = players[nb_pair].doc_id
                player_2 = players[nb_pair + nb_pairs].doc_id
                pairs.append({'player_1': player_1,
                              'player_2': player_2,
                              'tournament': tournament.doc_id,
                              'turn': tournament['active_turn'] + 1,
                              })

        # Creation des paires si ce n'est pas le 1er match
        else:
            self.db = DbConnect()
            players_scores = self.db.get_players_scores(tournament.doc_id)
            players_paired = []
            for player in players_scores:
                if player in players_paired:
                    continue
                # players_to_check = list(players_scores.keys())
                players_to_check = set(list(players_scores.keys())).difference(players_paired)
                players_to_check.remove(player)

                if players_to_check:
                    # Vérifie si le joueur a déjà joué avec tous les autres joueurs
                    no_match = self.db.get_match_played(tournament.doc_id, player, list(players_to_check))
                    if 0 < len(no_match) < (len(players_scores) - 1):
                        player_2 = no_match[0]
                    else:
                        temp = list(players_scores)
                        try:
                            player_2 = temp[temp.index(player) + 1]
                        except (ValueError, IndexError):
                            player_2 = None

                    pairs.append({'player_1': player,
                                  'player_2': player_2,
                                  'tournament': tournament.doc_id,
                                  'turn': tournament['active_turn'] + 1,
                                  })
                    players_paired.extend([player, player_2])
        return pairs

    def start_match(self):
        """
        Ask all the inputs to init the match
        :return:
        """
        tournaments = self.db.get_tournament_in_progress(['name'])
        tournament = self.select_tournament(tournaments, "Selectionnez le tournoi à lancer")

        if len(tournament["players"]) % 2 == 1:
            print("le nombre de joueur doit être pair pour lancer la compétition")
            return

        while tournament["status"] != 'Fini':

            players = self.db.get_list_of_players(tournament["players"], [('ranking', 1)])

            pairs = self.get_pairs(tournament, players)

            players_list = dict((item.doc_id, item) for item in players)
            self.view.show_pairs(players_list, pairs)
            input('Appuyez sur entrée pour lancer le tour\n')
            start_time = datetime.now()
            input('Appuyez sur entrée pour terminer le tour\n')
            end_time = datetime.now()

            for pair in pairs:
                self.view.show_pairs(players_list, [pair])
                result = int(self.view.ask_input(
                    "Merci de choisir la vainqueur du tour\n"
                    "\t[1] Joueur 1\n"
                    "\t[2] Joueur 2\n"
                    "\t[3] Match nul\n", "[1-3]", True))
                if result == 1:
                    pair['score_p1'] = 1
                    pair['score_p2'] = 0
                elif result == 2:
                    pair['score_p1'] = 0
                    pair['score_p2'] = 1
                elif result == 3:
                    pair['score_p1'] = 0.5
                    pair['score_p2'] = 0.5

                pair['start_time'] = start_time
                pair['end_time'] = end_time
                match = Match(**pair)

            tournament['active_turn'] += 1
            self.db.edit_tournament(tournament.doc_id, 'active_turn', tournament['active_turn'])

            if tournament['active_turn'] == tournament['turns']:
                tournament['status'] = 'Fini'
                self.db.edit_tournament(tournament.doc_id, 'status', tournament['status'])
                break
            else:
                tournament['status'] = 'En cours'
                self.db.edit_tournament(tournament.doc_id, 'status', tournament['status'])
                ask_continue = self.view.ask_input('Voulez vous lancer le prochain round ? oui [o] ou non [n] ?',
                                                   input_constraint="[n|N|o|O]")
                if ask_continue.lower() == 'n':
                    return

        self.show_results(tournament)

    def show_results(self, tournament=None):

        if not tournament:
            tournaments = self.db.get_all_tournaments()
            tournament = self.select_tournament(tournaments,
                                                "Choisissez le tournoi dont vous voulez afficher les résultats")
        tournament_id = tournament.doc_id
        players_scores = self.db.get_players_scores(tournament_id)
        self.view.display_results(players_scores)
        input()

    def select_tournament(self, tournaments, message=""):
        input_tournament = None
        while not input_tournament:
            self.view.show_tournaments(tournaments)

            input_tournament = self.view.ask_input(
                message,
                "integer"
            )
            if input_tournament:
                for tournament in tournaments:
                    if tournament.doc_id == input_tournament:
                        return tournament

    def show_tournaments(self):
        """
        Fonction to display all the tournaments
        :return: None
        """
        tournaments = self.db.get_all_tournaments()
        self.view.show_tournaments(tournaments)
        input()

    def edit_tournament(self):
        """
        Fonction to edit the tournament after asking which field to change
        :return: None
        """
        tournaments = self.db.get_all_tournaments()
        input_tournament = None
        while not input_tournament:
            self.view.show_tournaments(tournaments)

            input_tournament = self.view.ask_input(
                "Tournoi à modifier ?",
                "integer"
            )
            if input_tournament:
                for tournament in tournaments:
                    if tournament.doc_id == input_tournament:
                        tournament_keys = list(tournament.keys())
                        tournament_keys.remove('active_turn')
                        tournament_keys.remove('status')
                        tournament_key = self.view.ask_input_on_list("Caractérisitque à modifier ?",
                                                                     tournament_keys, required=True)

                        func = self.set_tournament(tournament_key)
                        if tournament_key == "end_date":
                            tournament_value = func(tournament["start_date"])
                        elif tournament_key == "players":
                            tournament_value = func(tournament)
                        else:
                            tournament_value = func()
                        self.db.edit_tournament(tournament.doc_id, tournament_key, tournament_value)
                        break
        self.show_tournaments()

    def set_tournament(self, key):
        """
        Get the function to edit a tournamet field, called by the function tournament_edit()
        :param key:
        :return: function
        """
        switcher = {
            "name": self.set_tournament_name,
            "place": self.set_tournament_place,
            "start_date": self.set_tournament_start_date,
            "end_date": self.set_tournament_end_date,
            "turns": self.set_tournament_turns,
            "players": self.assign_players,
            "time_control": self.set_tournament_time_control,
            "description": self.set_tournament_description
        }
        return switcher.get(key, lambda: print("Not working"))

    def assign_players(self, tournament=None):
        """
        Function to assign or delete players from tournament
        :param tournament: Tournament()
        :return: List
        """
        if tournament:
            tournament_players = tournament['players']
        else:
            tournament_players = []
        input_player = True
        while input_player and len(tournament_players) != 8:
            players = self.db.get_all_players()
            if tournament_players:
                print("\nJoueurs actuellement selectionnés : (il faut 8 joueurs)")
                self.view.show_players(players, include=tournament_players)

            print("\nJoueurs selectionnables :")
            self.view.show_players(players, exception=tournament_players)
            input_player = self.view.ask_input(
                "Tapez le numéro d'un joueur pour l'ajouter\n"
                "Tappez le numéro d'un joueur avec un - devant pour l'enlever\n"
                "Laisser vide pour passer à la section suivante\n"
                "ou tappez 0 pour créer un nouveau joueur",
                "integer"
            )
            if input_player == 0:
                self.create_player()
                input_player = True
            elif input_player:
                for player in players:
                    if player.doc_id == input_player:
                        if player.doc_id not in tournament_players:
                            tournament_players.append(player.doc_id)
                            break
                        else:
                            print('Joueur déja sélectionné')
                    elif player.doc_id == (input_player * -1):
                        if player.doc_id in tournament_players:
                            tournament_players.remove(player.doc_id)
                            break
                        else:
                            print("Joueur n'est pas encore sélectionné")

        return tournament_players

    def set_player_first_name(self):
        return self.view.ask_input("Prénom du joueur ?", required=True)

    def set_player_last_name(self):
        return self.view.ask_input("Nom du joueur ?", required=True)

    def set_player_date_of_birth(self):
        return self.view.ask_input("Date de naissance du joueur ? (au format jj/mm/aaaa)",
                                   "date", required=True)

    def set_player_gender(self):
        return self.view.ask_input_on_list("Genre du joueur ?", GENDER, required=True)

    def set_player_ranking(self):
        player_ranking = self.view.ask_input("Rang du joueur ?", "[0-9]*")
        return int(player_ranking) or 0

    def create_player(self):
        """
        Ask all the inputs to create a new player
        :return: None
        """
        args = {
            "first_name": self.set_player_first_name(),
            "last_name": self.set_player_last_name(),
            "date_of_birth": self.set_player_date_of_birth(),
            "gender": self.set_player_gender(),
            "ranking": self.set_player_ranking()
        }

        player = Player(**args)
        self.view.show_player(player)

        input()

    def show_players(self):
        """
        Function to display all the players
        :return: None
        """
        players = self.db.get_all_players()
        sort_type = self.view.ask_input_on_list("Voulez vous les trier par nom ou par classement ?",
                                                ['name', 'ranking'], True)
        self.view.show_players(players, sort_type)

        input()

    def edit_player(self):
        """
        Fonction to edit the player after asking which field to change
        :return: None
        """
        players = self.db.get_all_players()
        input_player = None
        while not input_player:
            self.view.show_players(players)

            input_player = self.view.ask_input(
                "Joueur à modifier ?",
                "integer"
            )
            if input_player:
                for player in players:
                    if player.doc_id == input_player:
                        player_key = self.view.ask_input_on_list("Caractérisitque à modifier ?",
                                                                 list(player.keys()), required=True)

                        func = self.set_player(player_key)
                        player_value = func()
                        self.db.edit_player(player.doc_id, player_key, player_value)
                        break
        self.show_players()

    def set_player(self, key):
        """
        Get the function to edit a player field, called by the function player_edit()
        :param key:
        :return: function
        """
        switcher = {
            'first_name': self.set_player_first_name,
            'last_name': self.set_player_last_name,
            'date_of_birth': self.set_player_date_of_birth,
            'gender': self.set_player_gender,
            'ranking': self.set_player_ranking
        }
        return switcher.get(key, lambda: print("Not working"))
