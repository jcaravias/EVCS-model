#Calls EVCS model to get data for use in the EVCS_pyomo_concrete model
#November 25

from EVCS_agent_model2 import *
import pandas as pd 
import numpy as np
import math

def get_move_edge_weight(G, move_indicator,travel_list): 
    result = {}
    for agent in move_indicator.keys(): 
        result_list = []
        for step in range(len(move_indicator[agent])): 
           
            if move_indicator[agent][step] == 1: 
                node1 = travel_list[agent][step] 
                node2 = travel_list[agent][step + 1] 
                result_list.append(G.get_edge_data(node1,node2)["weight"])
            else: 
                result_list.append(0)
        result[agent] = result_list 
    return result

def call_model(no_chargers, no_agents, no_ticks):
    """
    Inputs: pyomo params: #EVs, #charging stations, #nodes
    Output (as single pandas df): 
         - SOC for vehicle i at time step t
         - Average waiting time for vehicle i 
    Output to be read in as data for concrete pyomo model
     """ 
    flag = False
    no_homes = no_agents
    no_work = math.floor(no_chargers / 2)
    no_stores = math.floor(no_chargers / 2)
    no_fast = math.floor(no_chargers /2)
    scenario = 2
    charge_rates = (26.3, 3.47, 0.7) #(fast charger rate, slow charger rate, home charger rate) 

    if scenario == 1: 
        n = abs(no_homes - no_chargers)
    else: 
        n = no_chargers
        
    edge_weight_ranges = {"home_to_work": 3, "work_to_store": 0, "store_to_home": 2} #input factors to generate the edge weights 
    
    MW = Model_World(no_homes = no_homes, no_work = no_work, no_stores = no_stores, no_ticks = no_ticks, edge_weight_ranges = edge_weight_ranges)
    Model_Graph = MW.G
    
    trip_lists = MW.get_trip_lists()
    travel_list = MW.get_travel(trip_lists)
    move_indicator = MW.get_move_indicator(travel_list) 
    edge_weight_list = get_move_edge_weight(Model_Graph, move_indicator,travel_list)

    charger_placement = MW.get_charger_placement(scenario, int(n))
        
    model = EVCSModel(no_agents=no_agents, no_chargers=no_chargers, charger_placement =charger_placement, no_ticks = no_ticks,
                  G=Model_Graph, trip_lists = trip_lists, no_fast = no_fast, charge_rates  = charge_rates,scenario = scenario, day_ahead_df = day_ahead_df)
    
    for _ in range(no_ticks):
        model.step()

    data_collection = model.datacollector.get_model_vars_dataframe()    
    df = pd.DataFrame()
    df["Average overall charge level"] = data_collection['Average overall charge level']
    df["Average agent soc"] = data_collection["Average agent soc"]
    df["Agent location"] = data_collection["Agent location"]
    df["Length of Queue"] = data_collection['Length of Queue']

    return df, travel_list, move_indicator, edge_weight_list
    

no_chargers = 5 
no_agents = 3
no_ticks = 30


    
data, travel_list, move_list, edge_weight_list = call_model(no_chargers, no_agents, no_ticks)
