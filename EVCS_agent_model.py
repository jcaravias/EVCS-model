import mesa 
from mesa.space import NetworkGrid
from mesa.datacollection import DataCollector
import numpy as np
import matplotlib.pyplot as plt

from Model_World import *


class EVAgent(mesa.Agent): 
    """ EVAgent objects represent electric vehicles which move with the model graph and may be in either a charging or driving state """ 
    
    def __init__(self, unique_id, model, inital_loc, trips, trip_lengths): 
        super().__init__(unique_id, model) 
        self.soc = 100 #state of charge
        self.amount_charged = 0
        self.loc = inital_loc #inital node location
        self.trips = trips #list of nodes to travel to
        self.trip_lengths = trip_lengths #list of how long to stay at each node 
        self.current_trip_length = trip_lengths[0] #how many ticks to stay at current node
        
        self.on_trip = True #indicator for being in driving state
        self.trip_start = 0 #tick when trip begins
        
        self.current_charger_objs = []  #list of all the chargers at the current node
        self.in_queue = False
        self.plugged_in = False #indicator for having been assigend a charger and charging
        self.charging = False #indicator for being in parked state
        self.charging_start = None #tick when charging begins 
        self.charger_used = None #the assigned charger object when charging
        
        self.trips_completed = 0
        self.no_charge_count = 0
        
    
    def take_trip(self): 
        """ This function executes the trip (driving) state. When a EV agent has been in the trip state for the length of the trip, complete the trip."""
            
        if self.model._current_tick - self.trip_start >= self.model.G.get_edge_data(self.loc,self.trips[0])["weight"]: 
            #if enough ticks have passed to complete trip (given by edge weight) 
            if flag:
                print("*****") 
                print("trip complete")
                print("drive distance", self.model.G.get_edge_data(self.loc,self.trips[0])["weight"])
                print("trip_list" , self.trips)
                print("trip_length", self.trip_lengths)
                print("current trip length", self.current_trip_length)
                print("*****") 
            
            self.on_trip = False
            
            #update attributes for completed trip    
            self.soc -= self.model.G.get_edge_data(self.loc,self.trips[0])["weight"] * discharge_factor #reduce soc by edge weight * discharge factor 
            self.trips_completed += 1
            self.loc = self.trips[0] #update location for new node
            self.current_trip_length = self.trip_lengths[0]
            self.trips = self.trips[1:]
            self.trip_lengths = self.trip_lengths[1:]
            self.model.grid.move_agent(self, self.loc)  #update position on grid 
   
            #switch to charging state
            self.charging = True
            self.charging_start = self.model._current_tick
            
            
            
    def charge(self): 
        """ This function executes the charging state. EV agents in this state may either charge and occupy a charger, or if all chargers are in use then it will 
        wait in the queue at that node"""
        
        try:
            self.current_charger_objs = self.model.charger_loc[self.loc]
        except: 
            self.current_charger_objs = []  
        
        if self.current_charger_objs != []: #if there are one or more chargers at this location
            for charger in self.current_charger_objs: #iterate through chargers at this node
                if self.model.charger_queue[self.loc] == [] or self.plugged_in: #if there are no cars in the queue
                    if charger.car_charging == None or charger.car_charging == self.unique_id: #if no other cars at this charger
                        #begin charging
                        self.charger_used = charger
                        charger.car_charging = self.unique_id #state that this car is at the given charger
                        self.plugged_in = True 
                        
                        #increase soc by charge_per_tick unless fully charged
                        temp = self.soc
                        self.soc += charge_per_tick
                        if self.soc > 100: #dont allow to charge over 100% 
                            self.soc = 100 
                        self.amount_charged += self.soc - temp

                        break
                
                #if there is a queue at the charger, check if you are first in line. if first, then remove from queue and start charging. if not dont charge
                else: #there is a queue
                    if self.model.charger_queue[self.loc][0] == self.unique_id: #if you are first in line
                        if charger.car_charging == None: #no other cars occupying this charger
                            #begin charging
                            self.model.charger_queue[self.loc] = self.model.charger_queue[self.loc][1:] #remove yourself from queue 
                            charger.car_charging = self.unique_id #start charging
                            self.plugged_in = True
                            self.charger_used = charger
                            break
                
            
            #if after interating through all the chargers you have not been assigned a charger, add yourself to queue
            if not self.plugged_in: 
                if self.unique_id not in self.model.charger_queue[self.loc]: #if not already in queue
                    self.model.charger_queue[self.loc].append(self.unique_id) 
                    self.in_queue = True

        #LEAVING THE CHARGING STATION
        if self.model._current_tick - self.charging_start >= self.current_trip_length: # if have been at charging station for trip length
            #begin trip if you have sufficient charge for the next edge 
            if self.soc > self.model.G.get_edge_data(self.loc,self.trips[0])["weight"] * discharge_factor: 
                self.charging = False
                self.plugged_in = False
                self.on_trip = True #switch to trip
                if self.charger_used != None: #if EV agent was occupying a charger, leave
                    self.charger_used.car_charging = None 
                    
                if self.in_queue: #if EV agent was in the queue, leave
                    self.model.charger_queue[self.loc] = [i for i in self.model.charger_queue[self.loc] if i != self.unique_id]  
                    self.in_queue = False
                
                self.trip_start = self.model._current_tick #update tick in which trip begins
                
            else: #do not have enough charge to begin the next trip, stay in charging state 
                self.charging = True
                self.no_charge_count += 1
                
        
    def step(self):     
        if self.charging: 
            self.charge()
        if self.on_trip: 
            self.take_trip()
        
        if flag: 
            print("\n")
            print("EV number",self.unique_id)
            print("Location", self.loc)
            print("car soc", self.soc)
            print("trip list", self.trips) 
            print("trip lenghts", self.trip_lengths)
            print("charger queue", self.model.charger_queue) 
            print("plugged in", self.plugged_in) 
            print("charging", self.charging)
            print("on trip", self.on_trip)
                

                
class Charger(mesa.Model): 
    """  Charger objects track the cars at the given station""" 
    
    def __init__(self,unique_id, model,node_loc): 
        super().__init__(unique_id, model)
        self.unique_id = unique_id
        self.node_loc = node_loc
        self.car_charging = None
        
    def step(self): 
        pass
    
class EVCSModel(mesa.Model): 
    """ EV Charging Station Model uses an agent based approach. EV agent and chargers are placed throughout a graph defined by Model_World.py 
    
    EV agents move between nodes in the network according to a randomly generated "trip list". At each node, EV agents may charge if a charger is present 
    that is not in use by another agent. If the charger is in use, then the EV agent joins the charger queue at that node.
    
    Time steps is discretized in the model by defined "ticks", where 1 tick = 30 minutes. EV agents execute charging, waiting in the queue,
    or travel at each time step. 
    
    Key data about EV movements is collected. 

    """ 
    def __init__(self, no_agents,no_chargers,charger_placement, no_ticks, G, trip_lists):
        self.ticks = no_ticks
        self._current_tick = 0
        
        self.no_agents = no_agents
        self.no_chargers = no_chargers
        self.agents = []
        self.chargers = []
        self.charger_queue = {} #key = node, value = car id in queue at that node
        self.charger_loc = {} #key = node, value = charger id at that node 
        
        self.schedule = mesa.time.BaseScheduler(self)
        
        self.G = G
        self.grid = NetworkGrid(self.G)
    
        self.datacollector = DataCollector(model_reporters={"Average SOC": get_average_soc,
                                                           "EV trips complete": get_trips_completed, 
                                                            "Amount charged": get_amount_charged, 
                                                           "Instances of insufficient charge": get_insufficient_charge_count, 
                                                           "Length of queue": get_number_in_queue})
        #Generate EV agents 
        for i in range(self.no_agents): 
            a = EVAgent(unique_id = i, model =self, inital_loc = trip_lists[i][0][0], trips = trip_lists[i][0][1:], trip_lengths = trip_lists[i][1][1:])
            self.grid.place_agent(a, i)
            self.agents.append(a)
            self.schedule.add(a)
            
        #Generate charger agents and queue 
        for i in range(self.no_chargers): 
            c = Charger(unique_id = i, model = self ,node_loc =charger_placement[i])
            self.chargers.append(c)
            
            if charger_placement[i] not in self.charger_queue.keys(): 
                self.charger_queue[charger_placement[i]] = [] 
                
            if charger_placement[i] not in self.charger_loc.keys(): 
                self.charger_loc[charger_placement[i]] = [c]
            else: 
                self.charger_loc[charger_placement[i]].append(c)
        
    def step(self):
        self.schedule.step()
        self.datacollector.collect(self)
        self._current_tick += 1
        if flag: 
            print("CURRENT TICK" , self._current_tick)
            print("__________________________")
        
#Define functions for data collection
def get_average_soc(model):
    ev_soc = [agent.soc for agent in model.agents] 
    return np.mean(ev_soc) 

def get_trips_completed(model):  
    ev_trips_completed = [agent.trips_completed for agent in model.agents] 
    return np.sum(ev_trips_completed)

def get_amount_charged(model): 
    ev_amount_charged = [agent.amount_charged for agent in model.agents] 
    return np.sum(ev_amount_charged)

def get_insufficient_charge_count(model): 
    count = [agent.no_charge_count for agent in model.agents] 
    return np.sum(count)          

def get_number_in_queue(model): 
    count = [1 for agent in model.agents if agent.in_queue] 
    return np.sum(count)