#Define EVCS optimization using a concrete model 
#Created: Nov 25, last update: Nov 30

##########################################################################
""" NOTES 
- account for if number of chargers is greater than number of nodes --> need to add capacity greater than 1  **
""" 
##########################################################################

import pyomo.environ as pyo
from pyomo.opt import SolverFactory
from pyomo.util.infeasible import log_infeasible_constraints

import random
import pandas as pd
import numpy as np

from sklearn import preprocessing

from call_EVCS import *

#initalize model inputs
no_chargers = 10 #no_charges <= no_nodes, cannot have multiple chargers at single node 



no_work = 5
no_stores = 10
no_homes = 30

no_nodes = no_work + no_stores + no_homes
no_agents = no_homes

no_ticks = 144 #3 days
    
#get EV agent travel data from EVCS model world
def format_edge_weights(data, no_ticks, no_agents): 
    #returns dictionary with key (agent j, tick k) and value is edge weight of completed trip for agent j at tick k
    result = {}
    for j in range(no_agents):#j = agents
        for k in range(len(data[j])): #k = ticks
            if (j + 1, k + 1) not in result.keys():
                result[(j + 1 , k + 1)] = data[j][k]
            else:
                result[(j + 1, k + 1)].append(data[j][k])
    return result

def format_locations(data, no_nodes, no_ticks, no_agents):
    #returns dictionary with key (node i, agent j, tick k) and value binary indicator if agent j is at node i on time step k
    result = {} 
    for i in range(no_nodes): 
        for j in range(no_agents): 
            for k in range(no_ticks):  
                if data[k][j] == i: 
                    result[(i + 1, j + 1, k + 1)] = 1
                else: 
                    result[(i + 1, j + 1, k + 1)] = 0
    return result

#get data and format
MW, SG, df, travel_list, move_indicator, edge_weight_list = call_model(no_nodes, no_work, no_stores, no_homes,no_chargers, no_agents, no_ticks)

location_dict = df.to_dict()['Agent location'] #dictionary that maps tick to list of agent locations
edge_weight_data = format_edge_weights(edge_weight_list, no_ticks, no_agents)
loc_data = format_locations(location_dict, no_nodes, no_ticks, no_agents)



##########################################################################
#OPTIMIZATION FRAMEWORK 
##########################################################################

model = pyo.ConcreteModel() #define pyomo concrete model

#PARAMETERS
model.no_chargers = pyo.Param(initialize = no_chargers)#number charging stations
model.no_agents = pyo.Param(initialize = no_agents)#number EV agents 
model.no_ticks = pyo.Param(initialize = no_ticks) #number of timesteps (1 tick = 30 minutes)
model.no_nodes = pyo.Param(initialize = no_nodes)#number of nodes


#INDEX SETS
model.I = pyo.RangeSet(model.no_nodes) #iterate over all nodes 
model.J = pyo.RangeSet(model.no_agents) #iterate over all EV agents 
model.K = pyo.RangeSet(model.no_ticks) #iteration over all time steps

#COEFFICIENTS
model.charge_factor_f = pyo.Param(initialize = 26.3) #increase in charge per tick for fast charger 
model.charge_factor_s = pyo.Param(initialize = 3.47) #increase in charge per tick for slow charger

model.discharge_factor = pyo.Param(initialize = 4.7) #decrease in soc per unit edge weight = (20 / 420) * 100 = 4.7


model.lambda_s = pyo.Param(initialize = 1182) #cost per slow charger 
model.lambda_f = pyo.Param(initialize = 28401) #cost per fast charger
model.alpha = pyo.Param(initialize = 0.5) #multi-objective cost weighting parameter

#Define EV agent travel and location values 
#model.w = pyo.Param(model.J, initialize = wait_times) #average wait time for EV agent j
model.loc = pyo.Param(model.I, model.J, model.K, initialize = loc_data) #indicator that agent j is located at node i at time step k
model.weight = pyo.Param(model.J, model.K, initialize = edge_weight_data) #edge weight if the agent completes a trip, edge weight is given in tick to complete trip

# print("***********************")
# model.soc.display()

# print("***********************")
# model.loc.display()

# print("***********************")
# model.weight.display()

def soc_bounds(m, j, k): 
    return (20, 100)

#DECISION VARIABLES
model.soc = pyo.Var(model.J, model.K,initialize = 100, bounds = (20,100)) #charge level of ev agent j at time step k, itialized to 100%
model.c = pyo.Var(model.I, model.J, model.K, within = pyo.Binary) #binary decision to charge for agent j at location i at time step k
model.d = pyo.Var(model.I,within=pyo.Binary) #binary decision for placement of charging station at each node i

# model.charge = pyo.Var(model.J, model.K, within= pyo.Binary) #indicator variable that agent j charged at step k

model.charge_f = pyo.Var(model.J, model.K, within= pyo.Binary) #indicator variable that agent j charged at step k at a FAST charger
model.charge_s = pyo.Var(model.J, model.K, within= pyo.Binary) #indicator variable that agent j charged at step k at a SLOW charger

model.f = pyo.Var(model.I,within=pyo.Binary) #binary decision for FAST charger at node i 
model.s = pyo.Var(model.I,within=pyo.Binary) #binary decision for SLOW charger at node i 

max_infra_cost = pyo.value(model.lambda_f) * no_nodes #if only built fast chargers at every node
print(max_infra_cost)


#OBJECTIVE FUNCTION
def obj_expression(m):
    #minimize the infrastcture cost of each placed charging station
    infra_cost = sum([m.d[i] * (m.lambda_s*m.s[i] + m.lambda_f*m.f[i]) for i in m.I]) 
   
    
    infra_cost_normalized = infra_cost / max_infra_cost
    
    #maximize the sum of soc 
    soc_average_agent = 0
    for k in range(1,no_ticks): 
        soc_average_agent += np.mean([m.soc[j,k] for j in range(1,no_agents)]) # average soc for all agents per time step 
        
    soc_overall_average = soc_average_agent / no_ticks / 100
    # soc_total_normalized = preprocessing.normalize(no_agents)
    # print(soc_total_normalized)
    return (m.alpha * infra_cost_normalized) - (1 - m.alpha) * soc_overall_average

model.OBJ = pyo.Objective(expr=obj_expression) #assign objective function to model

# print("OBJECTIVE FUNCTION")
# model.OBJ.display()


#CONSTRAINTS 
def soc_constraint(m, j, k):
    #SOC is initalied to 100 at first time step. 
    #Then SOC for time step k is equal to SOC at step k - 1 plus additional charge from charging minus charge from completing a trip
    if k == 1: 
        return m.soc[j, k] == 100
        #return pyo.Constraint.Skip
    else: 
        # return  m.soc[j, k] == m.soc[j, k-1] + (m.charge_factor * m.charge[j,k]) - (pyo.value(m.weight[j,k]) *m.discharge_factor)
        return  m.soc[j, k] == m.soc[j, k-1] + (m.charge_factor_f * m.charge_f[j,k]) + (m.charge_factor_s * m.charge_s[j,k]) - (pyo.value(m.weight[j,k]) *m.discharge_factor)

# print("WEIGHT")
# model.weight.display()
    
model.soc_constraint = pyo.Constraint(model.J, model.K, rule=soc_constraint)
# print("DISPLAY SOC CONSTRAINT")
# model.soc_constraint.pprint()


def charge_indicator_f(m, j, k):
    #Defines the fast charge indicator
    return m.charge_f[j, k] == sum(m.c[i, j, k] * m.f[i] for i in m.I)

model.charge_indicator_f = pyo.Constraint(model.J, model.K, rule=charge_indicator_f)

def charge_indicator_s(m, j, k):
    #Defines the slow charge indicator
    return m.charge_s[j, k] == sum(m.c[i, j, k] * m.s[i] for i in m.I)

model.charge_indicator_s = pyo.Constraint(model.J, model.K, rule=charge_indicator_s)

def single_agent_use(m, i, k): 
    #for each time step, only one agent can be plugged into a given charger
    return sum(m.c[i,j,k] for j in m.J) <= 1 

model.single_agent_use = pyo.Constraint(model.I, model.K, rule=single_agent_use)

def charger_agent_loc(m, i, j, k): 
    #agent j can only use charger at node i at time step k if it is also at that location
    return m.loc[i,j,k] >= m.c[i,j,k]

model.charger_agent_loc = pyo.Constraint(model.I, model.J, model.K, rule=charger_agent_loc)

def existing_charger_constraint(m, i, j, k): 
    #there must be a charger placed at node i in order for an agent to charge here
    return m.d[i] >= m.c[i,j,k] 

model.existing_charger_constraint = pyo.Constraint(model.I, model.J, model.K, rule=existing_charger_constraint)

def fast_slow_constraint(m, i):
    #charger can only be assigned as fast OR slow
    #if fast then not slow, if slow then not fast
    return m.f[i] + m.s[i] == m.d[i]

model.fast_slow_constraint = pyo.Constraint(model.I, rule=fast_slow_constraint)

def fast_charger_constraint(m, i): 
    #fast charger constraint 
    #if there is no charger at node i (d_i = 0) then fast is not assigned (f_i= 0) 
    return - m.d[i] + m.f[i] <= 0

model.fast_charger_constraint = pyo.Constraint(model.I, rule=fast_charger_constraint)

def slow_charger_constraint(m, i): 
    #fast charger constraint 
    #if there is no charger at node i (d_i = 0) then slow is not assigned (s_i= 0) 
    return - m.d[i] + m.s[i] <= 0

model.slow_charger_constraint = pyo.Constraint(model.I, rule=slow_charger_constraint)

#set optimizer as Gurobi and solve
opt = SolverFactory('gurobi')
results = opt.solve(model,tee=True) 



#display optimization results 
results.write()
# model.pprint()
print("OBJECTIVE")
print(pyo.value(model.OBJ))

print("PLACEMENT") 
print(model.d.display()) 

print("FAST")
print(model.f.display())

print("SLOW")
print(model.s.display())

# # # print("LOCATION")
# # # model.loc.display() 

# print("CHARGE FAST") 
# model.charge_f.display()

print("CHARGE SLOW") 
model.charge_s.display()

# print("SOC") 
# model.soc.display() 

# print("CHARGE") 
# print(model.charge.display())

# print("CHARGE LOC C") 

# for i in range(1, no_nodes): 
#     for j in range(1, no_agents): 
#         for k in range(1, no_ticks): 
#             if int(pyo.value(model.c[i, j,k])) == 1: 
#                 print(i,j,k) 
           
                

# print(test)
# print("HEREERE")
# for i in 
# print(model.c.display())

# print("EDGE WEIGHTS") 
# model.weight.display() 





# EXPORT DATA FROM OPTIMIZATION
#charger data
charger_df = pd.DataFrame()
charger_placement = [pyo.value(model.d[i]) for i in model.I]
fast_chargers = [pyo.value(model.f[i]) for i in model.I]
slow_chargers = [pyo.value(model.s[i]) for i in model.I]

charger_df["charger placement"] = charger_placement
charger_df["fast chargers"] = fast_chargers
charger_df["slow chargers"] = slow_chargers

#agent data
soc_df = pd.DataFrame()
average_soc = [] #average soc over all agents at time step k
for k in model.K:
    average_soc.append(np.mean([pyo.value(model.soc[j,k]) for j in model.J]))
soc_df["average soc"] = average_soc



charging_list = []
for k in model.K: 
    agent_charging = []
    for j in model.J: 
        agent_charging.append(pyo.value(model.charge_f[j,k]) + pyo.value(model.charge_s[j,k]))
    charging_list.append(agent_charging)

agent_charge_df = pd.DataFrame(charging_list)
 

                               
def get_data():
    infra_cost = sum([pyo.value(model.d[i]) * (pyo.value(model.lambda_s)*pyo.value(model.s[i]) + pyo.value(model.lambda_f)*pyo.value(model.f[i])) for i in model.I]) 
    infra_cost_normalized = infra_cost / max_infra_cost
    soc_average_agent = 0
    for k in range(1,no_ticks): 
        soc_average_agent += np.mean([pyo.value(model.soc[j,k]) for j in range(1,no_agents)])
    print("infra_cost", infra_cost) 
    print("infra_cost_normalized", infra_cost_normalized)
    
    print("soc_total", soc_average_agent /no_ticks/100) 
    print("objective funtion", pyo.value(model.OBJ))
    
    return MW, SG, charger_df, soc_df, agent_charge_df, location_dict


get_data()

# print(df)

# df.to_csv("charger_placement.csv")

# #agent charging decision data frame, index is the tick value is a list where each entry is binary indiactor for if the agent is charging
# df2 = pd.DataFrame()
# charge_indicator = []
# # location_indicator = []

# for k in model.K:
#     agent_charging = [pyo.value(model.charge[j, k]) for j in model.J]
#     charge_indicator.append(agent_charging)
    
# #     for i in model.I: 
# #         location = [pyo.value(model.loc[i, j, k]) for j in model.J]
# #         location_indicator += location
                                        
# # df2["agent charging"] = charge_indicator
# # df2["agent location"] = location_indicator

                    
                  

# # print(df2)

# df2.to_csv("chage_indicator.csv")



############################################################################################

