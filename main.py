from random import randint, choice, shuffle, randrange
import json
import sys

STARTING_LOCATION = "Brockley"
EVENTS_IMPLEMENTED = True
TESTING = False

global roles



with open("cities.json") as f:
    CITIES = json.load(f)

CITY_LIST = [city["city"].lower() for city in CITIES]


COLOURS = ["black", "blue", "yellow", "red"]

EVENTS = [["Forecast","Draw, look at, and rearrange the top 6 cards of the infection deck. Put them back on top."],
          ["One Quiet Night","Skip the next INFECT CITIES step (do not flip over any infection cards)"],
          ["Government Grant", "Build a research station in a city of your choice (no city card needed)"],
          ["Airlift", "Move any one pawn to any city (Get permission before moving another player's pawn)"],
          ["Resilient Population","Remove any 1 card in the infection discard pile from the game. You may play this between the infect and intensify steps of an epidemic."]]



ROLES = {"Researcher":"brown", #need to implement ability
         "Scientist":"white",
         "Dispatcher":"purple",
         "Operations Expert":"light green",
         "Medic":"orange",
         "Quarantine Specialist":"dark green",
         "Contingency Planner":"cyan"}


CUBE_STARTING_STOCK = 24

class PyndemicException(Exception):
    pass


class Board:

    def __init__(self):
        self.roles = dict(ROLES)
        self.roles_used = []
        self.players = []
        self.infection_deck = []
        self.infection_discard = []
        self.player_deck = []
        self.player_discard = []
        self.outbreaks = 0
        self.epidemic_counter = 0
        self.infection_rate = 2
        self.cities = {city["city"]:City(self, city["city"], city["colour"], city["connections"]) for city in CITIES}
        self.event_cards = []
        self.cured = []
        self.eradicated = []
        self.cube_stock = {"black":CUBE_STARTING_STOCK, "red":CUBE_STARTING_STOCK, "yellow":CUBE_STARTING_STOCK, "blue":CUBE_STARTING_STOCK}
        self.outbreaks_this_turn = []
        self.one_quiet_night = False
        
        # fix missing connections
        for city in self.cities.values():
            for connection in city.connections:
                if city.name not in self.cities[connection].connections:
                    self.cities[connection].connections.append(city.name)                             

    def __getitem__(self, key):
        try:
            return self.cities[key]
        except KeyError as e:
            
            return self.cities[key.name]


    def __iter__(self):
        for city in self.cities.values():
            yield city

    def check_player_presence(self, city, role):
        if role in self.roles_used:
            return self.select_player(role).location == city
        else:
            return False

    def get_occupied_cities(self, occupants=False):
        if not occupants:
            return [p.location for p in self.players]
        else:
            return ["{} (w/ the {}".format(p.location, p.role) for p in self.players]

    def get_quarantine_locations(self):
        if "Quarantine Specialist" in self.roles_used:
            p = self.select_player("Quarantine Specialist")
            quarantine = self.cities[p.location].connections + [p.location]
            return quarantine
        else:
            return []
       
    def allow_event(self):
        """If any player has an event card in their hand, give the option to play it"""
        if len(self.infection_deck) > 0 and len(self.event_cards) > 0:
            c = input("Enter any key to play an event card, leave blank to continue.")
            if c:
                self.play_event_card()

    def play_event_card(self):
        events = ["{}: {}".format(e.name.upper(), e.info) for e in self.event_cards]
        c = pick_option(events+["CANCEL"], "AN EVENT CARD TO PLAY")

        try:
            event = self.event_cards[c]
        except IndexError: # player has chosen to cancel
            return

        if "Forecast" in event.name:
            forecasting = [self.infection_deck.pop(i) for i in range(6)]
            new_order = []
            
            for i in range(6):
                word = "NEXT"
                if i == 0:
                    word = "FIRST"
                elif i == 5:
                    word = "LAST"
                c = pick_option(["{} ({}).format"(c.name, c.info) for c in forecasting], "WHICH CARD {}".format(word))

                new_order.append(forecasting.pop(c))

            self.infection_deck = new_order + self.infection_deck

            print("\nThe next phase of infections has been forecast\n")
            
        elif "Government" in event.name:
            stations = self.get_research_stations()
            city = choose_city("to build a research station in", exceptions=stations)
            

            if len(stations) == 6:
                c = pick_option(stations, "RESEARCH STATION TO MOVE (maximum of 6 reached)")
                self.cities[stations[c]].research_station = False

            self.cities[city].research_station = True
                
            
            
            print("\nA government-funded research station was constructed in {}".format(city))

        elif "One Quiet Night" in event.name:
            self.one_quiet_night = True
            print("\nThe next infect cities step will be skipped.")

        elif "Airlift" in event.name:            
            pawns = ["The {} ({})".format(p.role, p.colour) for p in self.players]
            c = pick_option(pawns, "PAWN TO AIRLIFT TO ANOTHER CITY")
            role = self.players[c].role
            current_loc = self.players[c].location
            city = choose_city("to airlift the {} to".format(role), exceptions=[current_loc])
            self.players[c].location = city

            print("\The {} was airlifted to {}".format(role, city))

        elif "Resilient" in event.name:

            if len(self.infection_discard) > 0:
                cards = [c[1] for c in self.infection_discard]
                c = pick_option(cards, "INFECTION CARD TO REMOVE FROM THE GAME")
                removed = self.infection_discard[c][1]
                self.infection_discard.pop(0)

                print("\nThe {} infection card was removed from the game\n".format(removed))

        
        ## remove card from hand
        self.event_cards.remove(event)
                
        for player in self.players:
            if player.contingency:
                if player.contingency == event:
                    player.contingency = None
                    print("The {} event card has been removed from the game\n".format(event.name))
            if event in player.hand:
                i = player.hand.index(event)
                self.player_discard.append(player.hand.pop(i))
                    

    def check_game_over(self):
        m = ""
        exhausted_cubes = [colour for colour, amount in self.cube_stock.items() if amount < 1]
        if self.outbreaks > 7:
            m = "You exceeded the maximum number of outbreaks. GAME OVER!"
        elif len(self.cured) == 4:
            m = "You cured all 4 diseases. YOU WIN!"
        elif len(self.player_deck) < 1:
            m = "You exhausted the player deck. GAME OVER!"
        elif len(exhausted_cubes):
            m = "You exhausted the {} disease cubes. GAME OVER!".format(exhausted_cubes[0])
        if m:
            sys.exit(m)

    def player_move(self, player):
        c = 0
        game_over = self.check_game_over()
        if game_over:
            return game_over

        while c in [0, 1]:
            moves = player.get_valid_moves()
            redisplays = ["REDISPLAY THE BOARD", "REDISPLAY THE PLAYER HANDS"]
            self.allow_event()
            moves = redisplays + moves
            c = pick_option(moves, "AN ACTION")
            if c == 0:
                display_board(self, self.players)
            elif c == 1:
                display_hands(self, self.players)
        self.execute_move(player, moves[c])
        self.check_game_over()

    def select_player(self, role):
        """Return a player object that matches the given role"""
        for p in self.players:
            if p.role == role:
                return p
        raise PyndemicException("Trying to select a player that doesn't exist in this game...")

    def select_city(self, city):
        """Return a city object that matches the given city name"""
        for name, city_obj in self.cities.items():
            if name == city:
                return city_obj

    def get_research_stations(self):
        return [name for name, city in self.cities.items() if city.research_station]

    def check_eradication(self):

        for disease, amount in [cube_count for cube_count in self.cube_stock.items() if cube_count[0] not in self.eradicated]:
            if amount == CUBE_STARTING_STOCK:
                fancy_print("THE {} DISEASE HAS BEEN ERADICATED!!!".format(disease))
                self.eradicated.append(disease)

    def execute_move(self, player, move):

        city = player.location

        if "[Operations Expert]" in move:
            city_cards = player.select_cards(type_="CITY")
            c = pick_option([c.name for c in city_cards], "A CARD TO DISCARD TO USE THIS ABILITY")
            player.discard(city_cards[c].name) 

        if "[Contingency Planner]" in move:
            event_cards = [c for c in self.player_discard if c.type == "EVENT"]
            c = pick_option([c.name for c in event_cards], "AN EVENT CARD TO PICK UP AND RE-USE ONCE")
            chosen_event = event_cards[c]
            self.player_discard.remove(chosen_event)
            player.contingency = chosen_event
            self.event_cards.append(chosen_event)
            msg = "The Contingency Planner recovered the {} EVENT card".format(chosen_event.name)

        elif "[Dispatcher]" in move:
            c = pick_option([p.role for p in self.players], "A PLAYER TO MOVE TO A CITY WITH ANOTHER PAWN")
            chosen_player = self.players[c]
            c = pick_option(self.get_occupied_cities(occupants=True), "A CITY TO MOVE THE PLAYER TO") 
            new_city = self.get_occupied_cities[c]
            chosen_player.location = new_city
            msg = "The Dispatcher moved the {} to {}".format(chosen_player.role, new_city)            

        elif "TREAT" in move:
            move = move.replace(city, "")
            for colour in COLOURS:
                if colour in move:
                    if player.medic:
                        remove_cubes = self[city].cubes[colour]
                    else:
                        remove_cubes = 1
                    self[city].cubes[colour] -= remove_cubes
                    self.cube_stock[colour] += remove_cubes
                    if len(self.cured) > 0:
                        self.check_eradication()
                    
                    pluralise = ""
                    was_were = "was"
                    medic = ""
                    if remove_cubes > 1:
                        pluralise = "s"
                        was_were = "were"
                        medic = " [Medic]"

                    msg = "{} {} cube{} {} removed from {}{}.".format(remove_cubes, colour, pluralise, was_were, city, medic)

        elif "BUILD" in move:
            self[city].research_station = True
            if player.ops_expert:
                suffix = " by the Operations Expert"
            else:
                suffix = ""
                player.discard(city)
            msg = "Research station was built in {}{}".format(city, suffix)

        elif "SHARE" in move:
            neighbours = [p for p in self.players if p.location == city and p.role != player.role]
            if len(neighbours) == 0:
                raise PyndemicException("No player in same city to share knowledge with.")
            else:
                if "Researcher" in move:
                    researcher_involved = True
                else:
                    researcher_involved = False

                if "Take " in move:
                    for role in ROLES.keys():
                        if role in move:
                            sender = self.select_player(role)                            
                            recipient = player
                            break                                                        
                else:
                    if len(neighbours) > 1:
                        players = ["The {}".format(p.role) for p in neighbours]
                        c = pick_option(players, "PLAYER TO GIVE THE {} CARD TO".format(city))
                    else:
                        c = 0

                    sender = player
                    recipient = neighbours[c]
                
                if researcher_involved:
                    if "Take " in move:
                        wording = "TAKE FROM THE RESEARCHER"
                    else:
                        wording = "GIVE TO THE {}".format(recipient.role)
                    cards = sender.select_cards(type_="CITY")
                    c = pick_option([c.name for c in cards], "A CARD TO {}".format(wording.upper()))
                    card = cards[c]
                    city = card.name
                else:
                    card = sender.select_cards(card=city)
                sender.hand.remove(card)                
                recipient.receive_card(card)

                msg = "The {} gave the {} CITY CARD to the {}".format(sender.role, city, recipient.role)


        elif "DIRECT" in move:
            destination = move.replace("DIRECT FLIGHT TO ", "").replace(" by discarding that city card", "")
            player.discard(destination)
            player.location = destination
            msg = "The {} flew direct to {}".format(player.role, destination)


        elif "CHARTER" in move:
            destination = choose_city("to arrange CHARTER FLIGHT to: ", exceptions=[city])
            player.discard(city)
            player.location = destination

            msg = "The {} flew charter to {}".format(player.role, destination)

        elif "SHUTTLE" in move:
            if "[Operations Expert]" in move:
                destination = choose_city("Enter city to take shuttle flight to:", exceptions=[player.location])
            else:
                destination = move.replace("SHUTTLE FLIGHT TO ", "").replace(" from this research station.", "")
            
            player.location = destination

            msg = "The {} flew shuttle to {} {}".format(player.role, "the research station in" if not "Operations Expert]" else "",  destination)

        elif "DRIVE" in move:
            destination = move.replace("DRIVE/FERRY TO ", "")
            player.location = destination
        

            msg = "The {} drove to {}".format(player.role, destination)

            if player.medic:
                for disease in self.cured:
                    cure_cubes = self[destination].cubes[disease]
                    if cure_cubes > 0:
                        self[destination].cubes[disease] -= cure_cubes
                        print("The Medic automatically removed {} cubes of the cured {} disease in {}".format(cure_cubes, disease, destination))
                        self.cube_stock[disease] += cure_cubes

        elif "CURE" in move:
            start = len("DISCOVER THE CURE FOR THE ")
            stop = move.index(" DISEASE")
            disease = move[start:stop]
            
            num_cards = player.count_cards(disease)
            ## get only cards of a certain colour
            same_colour_cards = player.select_cards(colour=disease)                        
            if num_cards  < player.cure_set_num:
                raise PyndemicException("Not enough cards to cure disease")
            elif num_cards > player.cure_set_num:
                ## allow user to choose which cards to retain
                while len(same_colour_cards) > player.cure_set_num:
                    print("You have more than {} {} cards.".format(player.cure_set_num, disease))
                    c = pick_option([c.name for c in same_colour_cards], "A CARD TO RETAIN")
                    same_colour_cards.pop(c)

            for card in same_colour_cards:                
                player.discard(card.name)

            self.cured.append(disease)

            msg = "The {} discovered the cure for the {} disease!!!\n\n{}/4 DISEASES CURED\n".format(player.role, disease, len(self.cured))
            
            self.check_game_over()
            self.check_eradication()
            

        else:
            msg = "The {} skipped this action.".format(player.role)
                

        print(msg)
        
         

class City:

    def __init__(self, board, name, colour, connections):
        self.board = board
        self.name = name
        self.colour = colour
        self.connections = connections
        self.cubes = {"red":0,
                      "blue":0,
                      "yellow":0,
                      "black":0}
        self.research_station = False
        

    def connected_to(self, destination):
        return destination in self.connections

    def infect(self, colour, num):
        if self.board.check_player_presence(self.name, "Medic") and colour in self.board.cured:
            print("The Medic prevented the spread of the cured {} disease in {}. NO EFFECT".format(colour, self.name))
        elif self.name in self.board.get_quarantine_locations():
            print("The Quarantine Specialist prevented the spread of the {} disease in {}. NO EFFECT".format(colour, self.name))
        else:
            
            self.cubes[colour] += num
            self.board.cube_stock[colour] -= num
            self.board.check_game_over()
            if self.cubes[colour] > 3:
                self.outbreak(colour)
            else:
                print("{} now contains {} disease cube{}.".format(self.name, self.cubes[colour], "s" if self.cubes[colour] > 1 else ""))
            
    def outbreak(self, colour):
        self.board.check_game_over()
        excess = self.cubes[colour] - 3         # calculate extra unneeded cubes
        self.board.cube_stock[colour] += excess # add back to the stock pile
        self.cubes[colour] = 3                  # reset outbreak city to 3 cubes
        if self.name in self.board.outbreaks_this_turn:
            print("An outbreak has already occurred in {} this turn.".format(self.name))
        else:
            self.board.outbreaks_this_turn.append(self.name)                        
            print("AN OUTBREAK OF THE {} DISEASE OCCURRED IN {}".format(colour, self.name))
            self.board.outbreaks += 1
            for city in self.connections:
                input("continue? ")
                print("\n...the disease spread to neighbouring city {}".format(city))
                city = self.board.select_city(city)
                city.infect(colour, 1)

    def get_disease_stats(self):
        info = "("
        for colour, amount in self.cubes.items():
            if amount > 0:
                info += "{} {},".format(amount, colour)

        if info.count(",") == 1:
            info = ""
        else:
            info = info[:-2] + ")"               
                
        
        return sum(self.cubes.values()), info
    
class Player():

    def __init__(self, count, board):
        self.board = board
        self.player_no = count
        self.cure_set_num = 5
        self.location = STARTING_LOCATION
        self.hand = []
        self.medic = False
        self.contingency = False
        self.ops_expert = False
        self.dispatcher = False
        self.researcher = False
        self.choose_role()

    def give_ability(self, role):
        if role == "Scientist":
            print("You only need 4 cards of the same colour to do the DISCOVER A CURE action")
            self.cure_set_num = 4
        elif role == "Medic":
            print("""Remove all cubes of one colour when doing TREAT DISEASE
Automatically remove cubes of cured diseases from the city you are in (and prevent them from being placed there)""")
            self.medic = True
        elif role == "Quarantine Specialist":
            print("Prevent disease cube placements (and outbreaks) in the city you are in and all cities connected to it")
        elif role == "Contingency Planner":
            print("""As an action, take any discarded event card and store it on this card. When you play the stored event card, remove it from the game.
(Limit - 1 event card at a time which is not part of your hand)""")
            self.contingency = True
        elif role == "Operations Expert":
            print("""As an action, build a research station in the city you are in (no City card needed)
Once per turn as an action, move from a research station to any city by discarding any City card.""")
            self.ops_expert = True
        elif role == "Dispatcher":
            print("""As an action, move any other pawn to a city containing another pawn""")
            self.dispatcher = True
        elif role == "Researcher":
            print("""When doing the SHARE KNOWLEDGE action, GIVE any city card to a player in the same city (it need not match the city you are in)""")
            self.researcher = True
        input("continue? ")         

    def select_cards(self, card=None, colour=None, type_=None):
        """Return a Card object that matches the requested city, or a list of cards matching a colour"""
        if card is not None:
            for c in self.hand:
                if c.name == card:
                    return c
            raise PyndemicException("You told me to select a card of a city I don't have...")
        else:
            if type_ is not None:
                return [c for c in self.hand if c.type == type_]
            else:
                return [c for c in self.hand if colour in c.info]

    def count_cards(self, colour):  
        n = len([c for c in self.hand if c.info.lower() == colour])
        print("I counted {} cards".format(n))
        return n
        
        
    def choose_role(self):
        roles = self.board.roles
        role = choice(list(roles.keys()))
        pawn = roles[role]
        roles.pop(role)        
        print("PLAYER {}'s role is the {}. They will use the {} pawn".format(self.player_no, role, pawn))
        self.give_ability(role)
        self.role = role
        self.board.roles_used.append(role)    
        self.colour = pawn

    def check_player_has_location_card(self, city=None):
        if city is None:
            city = self.location
        return city in [c.name for c in self.hand if c.type == "CITY"]

    def get_city_cards(self):
        return [c.name for c in self.hand if c.type == "CITY" and c.name != self.location]
                                 
    def get_adjacent_cities(self):
        return self.board[self.location].connections

    def get_players_in_same_city(self):
        return [p for p in self.board.players if p.role != self.role and p.location == self.location]

    def check_curable_diseases(self):
        card_colours = [c.info for c in self.hand if c.type == "CITY"]
        for colour in ["red", "blue", "black", "yellow"]:
            if card_colours.count(colour) >= 5:
                return colour
        return ""

    def discard(self, card):
        c = self.select_cards(card)
        print("The {} utilised their {} card.".format(self.role, c.name))
        self.hand.remove(c)

    def receive_card(self, card):
        proposed_hand = list(self.hand + [card])
        if len(proposed_hand) > 7:
            print("{}: HAND MAXIMUM REACHED".format(self.role))
            print("Select a card to discard: ")            
            cities = ["[{}]: {}".format(c.type, c.name) for c in proposed_hand]
            discarding = pick_option(cities, "A CARD TO DISCARD")
            ## if the list index of the card to discard is 7, player is choosing to discard a newly dealt card
            if discarding == 7:                
                self.board.player_discard.append(card)
            else:
                self.board.player_discard.append(self.hand.pop(discarding))
                self.hand.append(card)
            print("The {} discarded the {}:{} card.".format(self.role,  proposed_hand[discarding].type,  proposed_hand[discarding].name))
        else:
            self.hand.append(card)

    def get_valid_moves(self):
        
        ## assess hand and board for valid moves
        moves = ["SKIP THIS ACTION"]
        for city in self.get_adjacent_cities():
            moves.append("DRIVE/FERRY TO {}".format(city))

        for city in self.get_city_cards():
            moves.append("DIRECT FLIGHT TO {} by discarding that city card".format(city))

        neighbours = len(self.get_players_in_same_city()) > 0

        if self.researcher and neighbours and len(self.get_city_cards()) > 0:       
            moves.append("SHARE KNOWLEDGE: Give ANY city card to another player in the same location [Researcher]")
        
        for player in self.get_players_in_same_city():
            
            if self.check_player_has_location_card():
                moves.append("SHARE KNOWLEDGE: Give your {} city card to another player".format(self.location))
                break
            else:                
                if player.check_player_has_location_card(self.location):
                    p = player.role
                    moves.append("SHARE KNOWLEDGE: Take the {} city card from the {}".format(self.location, p))
            if player.researcher:
                if len(player.select_cards(type_="CITY")) > 0:
                    moves.append("SHARE KNOWLEDGE: Take ANY city card from the Researcher.")

        if self.check_player_has_location_card():            
            moves.append("CHARTER FLIGHT TO ANY OTHER CITY by discarding your {} city card".format(self.location))
            if not self.board[self.location].research_station and not self.ops_expert:
                moves.append("BUILD A RESEARCH STATION in {}".format(self.location))
                

        if self.ops_expert and not self.board[self.location].research_station:
            moves.append("BUILD A RESEARCH STATION in {} [Operations Expert]".format(self.location))
	

        diseases_here = [colour for colour in self.board[self.location].cubes.keys() if self.board[self.location].cubes[colour] > 0]
        for colour in diseases_here:
            moves.append("TREAT DISEASE: Remove {} {} cube{} from {}".format("all" if self.medic else 1, colour, "s" if self.medic else "", self.location))
        curable = self.check_curable_diseases()

        if self.board[self.location].research_station:
            other_research_stations = [name for name, city in self.board.cities.items() if city.research_station and name != self.location]
            for city in other_research_stations:
                moves.append("SHUTTLE FLIGHT TO {} from this research station.".format(city))
            if curable:
                moves.append("DISCOVER THE CURE FOR THE {} DISEASE by discarding {} {} cards.".format(curable, self.cure_set_num, curable))

        if self.ops_expert and self.board[self.location].research_station:
            moves.append("SHUTTLE FLIGHT TO ANY OTHER CITY from this research station [Operations Expert]")
        
        if self.contingency and len([c for c in self.board.player_discard if c.type == "EVENT"]) > 0:
            moves.append("PICK UP ONE DISCARDED EVENT CARD [Contingency Planner]") 
    
        if self.dispatcher:
            moves.append("SELECT A PAWN TO MOVE TO A CITY CONTAINING ANOTHER PAWN [Dispatcher]")
    
        return moves


        

class Card:

    def __init__(self, type_, name, details):
        self.type = type_
        self.name = name
        self.info = details


def fancy_print(string):
    char = choice("-=*~")
    print()
    print(char*len(string))
    print(string)
    print(char*len(string))

def display_board(board, players):
    print()
    print("The board currently looks like this...")
    print()
    input("continue? ")
    fancy_print("OUTBREAK COUNTER: {} /// ".format(board.outbreaks) + "INFECTION RATE: {}".format(board.infection_rate))
    fancy_print("DISEASE SPREAD")


    print("{:30}{:30}{:30}{:30}".format("BLUE:", "YELLOW:", "BLACK:", "RED:"))
    blues = [city for city in board if city.colour == "blue" and city.get_disease_stats()[0] > 0]
    yellows = [city for city in board if city.colour == "yellow" and city.get_disease_stats()[0] > 0]
    blacks = [city for city in board if city.colour == "black" and city.get_disease_stats()[0] > 0]
    reds = [city for city in board if city.colour == "red" and city.get_disease_stats()[0] > 0]

    ## to avoid zip mashing up, fill all lists with empty entries so they are as big as the biggest list
    extend = len(max([blues, yellows, blacks, reds], key=len))
    
    blues += [None] * (extend-len(blues))
    yellows += [None] * (extend-len(yellows))
    blacks += [None] * (extend-len(blacks))
    reds += [None] * (extend-len(reds))    
    
    c = 0
    comment = ""

    for blue, yel, black, red in zip(blues, yellows, blacks, reds):
        #print("hello")
        #print(blue, yel, black, red)
        for city in [blue, yel, black, red]:
            if city is not None:
                num, info = board[city.name].get_disease_stats()
            
                stat = "[{}]: {} {}".format(num, city.name, info)
                print("{:30}".format(stat), end="")
                
            else:
                print("{:30}".format(comment), end="")

            c += 1
            if c % 4 == 0:
                print()

def display_hands(board, players):
    fancy_print("PLAYER HANDS:")


    for player in players:
        print("The {} is in {}".format(player.role.upper(), player.location))
        
        for card in player.hand:
            stat = "[{}]: {} ({})".format(card.type, card.name, card.info)
            print(stat)
        print()
        input("continue? ")

    fancy_print("RESEARCH STATIONS: " + "".join("{}/".format(place) for place in board.get_research_stations())[:-1])

def choose_city(prompt, exceptions=[]):
    destination = ""
    cities = list(CITY_LIST)
    for city in exceptions:        
        cities.remove(city.lower())        
        
    while destination not in cities:
        destination = input("Enter city {}\n".format(prompt)).lower()
        if destination not in cities:
            print("Unnecessary or otherwise illegal choice.")

    return destination.title()

def pick_option(options, category="AN OPTION"):
    """Allow the user to choose from a list of options, and make sure
    the option they have selected is valid. Return the option as a list index"""
    columns = False
    if len(options) > 5:
        columns = True   
 
    c = ""
    while c not in [str(i) for i in range(1, len(options)+1)]:
        print("\nSELECT {}\n".format(category.upper()))
        if not columns:
            for i, option in enumerate(options):
                print("{}. {}".format(i+1, option))
        else:
            i = 1
            column1 = options[0::2]
            column2 = options[1::2] + [""]
            for col1, col2 in zip(column1, column2):
                print("{}. {:65}   | {}. {:65}".format(i, col1[:65], i+1, col2[:65]))
                i += 2

        c = input("continue? ")

    return int(c)-1

def get_num(prompt, min_, max_):
    """Get the user to enter a valid number within a range"""
    
    valid = False
    while not valid:
        n = input(prompt)
        if n.isdigit():
            n = int(n)
            if n in range(min_, max_+1):
                valid = True
                return n
            else:
                print("Enter a number between {} and {}".format(min_, max_))
        else:
            print("Enter digits only.")

def get_difficulty():
    """Add three onto the number of the difficulty rating selected.
    Returns the number of epidemic cards to be placed into the deck"""
    return pick_option(["normal", "moderate", "hard"], "difficulty") + 3    

def create_players(board):
    """Initialise each player, selecting a role at random
    Returns a list of player objects"""
    
    num = get_num("How many players? ", 1, 6)
    return [Player(i+1, board) for i in range(num)]    

def create_player_deck(difficulty, players, board):
    """Create a deck of player cards and randomly insert
    X epidemic cards according to the selected difficulty.
    Returns the constructed deck"""    
    deck = [Card("CITY", c["city"], c["colour"]) for c in list(CITIES)]
    deck += [Card("EVENT", title, info) for title, info in EVENTS]
    
    shuffle(deck)
    
    starting = 2
    if len(players) == 2:
        starting += 2
    elif len(players) == 3:
        starting += 1
        
    print("Each player will begin with a starting hand of {} cards.".format(starting))

    fancy_print("DEALING PLAYER CARDS")

    board.player_deck = deck

    for i in range(starting):
        for p in players:
            deal_player_cards(p, 1, board)    
                       
    division = len(deck) // difficulty
    input(division)
    # for each epidemic card
    for i in range(difficulty):
        # pick a random position in that division of the deck
        position = randrange(i * division, (i+1) * division)
        deck.insert(position, Card("EPIDEMIC!", "!!!", "1. Draw the bottom card from the infection deck and then add it do the discard pile 2. Infect this city with 3 disease cubes. 3. Shuffle the entire discard pile and add this back to the top of the infection deck"))
        
    return deck

def create_infection_deck():
    deck = [[c["colour"], c["city"]] for c in list(CITIES)]
    shuffle(deck)
    return deck

def infect_cities(board, rate=None, cubes=1):
    if rate is None:
        rate = board.infection_rate

    for i in range(rate):
        card =board.infection_deck.pop(0)
        colour, city = card
        print("{} INFECTION CARD {} was drawn.".format(colour, city))
        if colour in board.eradicated:
            print("{} disease eradicated. NO EFFECT".format(colour))
        else:

            board[city].infect(colour, cubes)
            board.allow_event()
        board.infection_discard.append(card)

def epidemic(board):
    print("EPIDEMIC!!!!")
    board.epidemic_counter += 1
    if board.epidemic_counter + 1 % 3 == 0:
        board.infection_rate += 1
        print("\nThe infection rate increased to {}\n.".format(board.infection_rate))
    infect_cities(board, rate=1, cubes=3)
    shuffle(board.infection_discard)                                      # shuffle discard pile
    board.infection_deck = board.infection_discard + board.infection_deck             # add discard pile to top of deck
    board.infection_discard = []


def deal_player_cards(player, n, board):
    """Deal a number of cards to a player
    Returns a list of cards being dealt"""
        
    dealt = []
    for i in range(n):
        try:
            card = board.player_deck.pop(0)       
        except IndexError:
            board.check_game_over()
        print("A {} card was drawn by the {}".format(card.type, player.role))
        if "EVENT" in card.type:
            board.event_cards.append(card)
            board.allow_event()
        
        if "EPIDEMIC" in card.type:            
            epidemic(board)
            board.player_discard.append(card)
            continue
            
        print("{}: {}".format(card.name.upper(), card.info))
        input("continue? ") 
        dealt = player.receive_card(card)
        


      
        


DEBUG = False

def debug(board, players):
    if DEBUG:
        print("who's playing?", "".join([p.role for p in players]))
        print("who's opsexpert?","".join([str(p.ops_expert) for p in players]))
        print("who's the medic?","".join([str(p.medic) for p in players]))




def main_loop():

    board = Board()
    
    difficulty = get_difficulty()
    print()
    players = create_players(board)

    board[STARTING_LOCATION].research_station = True
    
    infection_deck = create_infection_deck()
    infection_discard = []
    print()
    player_deck = create_player_deck(difficulty, players, board)
    player_discard = []
    
    board.players = players
    board.infection_deck = infection_deck
    board.infection_discard = infection_discard
    board.player_deck = player_deck
    board.player_discard = player_discard

    for i in range(3, 0, -1):
        infect_cities(board, rate=3, cubes=i)
    
    turn = 1

    game_over = False

    if TESTING:
        for card in [Card("CITY", "Brockley", "black"),
                     Card("CITY", "Peckham", "black"),
                     Card("CITY", "Lewisham", "black")]:
            players[0].receive_card(card)
    
    while not game_over:

        display_board(board, players)
        display_hands(board, players)        

        print("TURN {}".format(1))
        current = players[(turn-1) % len(players)]
        print("It's the {} player's turn ({})".format(current.colour, current.role))
               
        action = 1
        while action <= 4:
            
            debug(board, players)
            board.outbreaks_this_turn = []
            print("\nYou are in {}".format(current.location))     
            board.allow_event()                
            print("\nACTION {}/4".format(action))
            board.player_move(current)
            action += 1

           
        print("The {} completed all of their actions".format(current.role))

        fancy_print("DRAWING PLAYER CARDS:")
        input("continue? ")
        deal_player_cards(current, 2, board)
        fancy_print("INFECTING CITIES:")        
        input("continue? ")
        if board.one_quiet_night:
            print("\nOne quiet night...\n")
            board.one_quiet_night = False
        else:
            infect_cities(board)

        turn += 1
            
            

if __name__ == "__main__":

    main_loop()
    
     
