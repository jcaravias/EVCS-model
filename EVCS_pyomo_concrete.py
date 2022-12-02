#Define EVCS optimization using a concrete model 
#Created: Nov 25, last update: Nov 30

##########################################################################
""" NOTES 
- need to change this such that the speed changes depending on the rate of the charger 
- implement correct charge/dischage rates, correct infrastructure prices 
- create Networkx figure?!
""" 
##########################################################################

import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import random
import pandas as pd

from call_EVCS import *

model = pyo.ConcreteModel()

no_chargers = 10
no_agents = 5
no_nodes = 3
no_ticks = 10
    
df, travel_list, move_indicator, edge_weight_list = call_model(no_chargers, no_agents, no_ticks)

def format_data1(data, no_ticks, no_agents): 
    #use only for edge weight dict
    result = {}
    for i in range(no_agents):#i = number agents
        
        for j in range(len(data[i])): #j = number ticks
            if (i + 1, j + 1) not in result.keys():
                result[(i + 1 , j + 1)] = data[i][j]
            else:
                result[(i + 1, j + 1)].append(data[i][j])
    return result

# def format_data2(data, no_ticks, no_agents, no_nodes): 
#     #NEED TO CHANGE THIS SO THAT LOC IS IJK
#     #use only for location dict
#     result = {}
#     # result (agent, tick):
#     for i in no_nodes: # iterate over all nodes
#         for k in data.keys(): #keys are ticks, 
#             for j in range(no_agents): #j is agent 
#                 if (i, j + 1, k + 1) not in result.keys():
#                     result[(i, j + 1 , k + 1)] = data[k][j]
#                 else: 
#                     result[(j + 1, k + 1)].append(data[k][j])
#     return result

def format_data2(data, no_nodes, no_ticks, no_agents):
    #CHECK INDEXING!
    result = {} 
    #i = node, j = agent, k = tick
    for i in range(no_nodes): 
        for j in range(no_agents): 
            for k in range(no_ticks):  
                if data[k][j] == i: 
                    result[(i + 1, j + 1, k + 1)] = 1
                else: 
                    result[(i + 1, j + 1, k + 1)] = 0
    return result


#Define parameters
model.no_chargers = pyo.Param(initialize = no_chargers)#number charging stations
model.no_agents = pyo.Param(initialize = no_agents)#number EV agents 
model.no_ticks = pyo.Param(initialize = no_ticks) #number of timesteps (1 tick = 30 minutes)
model.no_nodes = pyo.Param(initialize = no_nodes)#number of nodes


#define index sets 
model.I = pyo.RangeSet(model.no_nodes) #iterate over all nodes 
model.J = pyo.RangeSet(model.no_agents) #iterate over all EV agents 
model.K = pyo.RangeSet(model.no_ticks) #iteration over all time steps


#PARAMETERS
#define coefficients
model.charge_factor_fast = pyo.Param(initialize = 5) #increase in charge per tick for fast charger 
model.charge_factor_slow = pyo.Param(initialize = 2) #increase in charge per tick for slow charger

model.charge_factor = pyo.Param(initialize = 5) #increase in charge per tick 


model.lambda_s = pyo.Param(initialize = 5) #cost per slow charger
model.lambda_f = pyo.Param(initialize = 3) #cost per fast charger
model.alpha = pyo.Param(initialize = 0.4) #multi-objective cost weighting parameter

#get data
location_dict = df.to_dict()['Agent location'] 
# print("HEREE LOCATION DICT") #dict that maps ticks to list of agent locations 
# print(location_dict)

edge_weight_data = format_data1(edge_weight_list, no_ticks, no_agents)
loc_data = format_data2(location_dict, no_nodes, no_ticks, no_agents)

# print("****************************************************************************") 
# print(loc_data)

#model.w = pyo.Param(model.J, initialize = wait_times) #average wait time for EV agent j
model.soc = pyo.Param(model.J, model.K,initialize = 100, mutable = True) #charge level of ev agent j at time step k, itialized to 100%
model.loc = pyo.Param(model.I, model.J, model.K, initialize = loc_data) #indicator that agent j is located at node i at time step k
model.weight = pyo.Param(model.J, model.K, initialize = edge_weight_data) #edge weight if the agent completes a trip

# print("***********************")
# model.soc.display()

# print("***********************")
# model.loc.display()

# print("***********************")
# model.weight.display()

#DECISION VARIABLES
#***** EV agent decisions to charge variables ****** 
model.c = pyo.Var(model.I, model.J, model.K, within = pyo.Binary) #decision to charge for agent j at location i at time step k

#*****Charging station decision variables ****** 
#binary decision for placement of charging station at each node 
model.d = pyo.Var(model.I,within=pyo.Binary)

#binary decision for FAST charger at node i 
model.f = pyo.Var(model.I,within=pyo.Binary)

#binary decision for SLOW charger at node i 
model.s = pyo.Var(model.I,within=pyo.Binary)

#indicator variable that agent j charged at step k
model.charge = pyo.Var(model.J, model.K, within= pyo.Binary) 


#OBJECTIVE FUNCTION
def obj_expression(m):
    infra_cost = sum([m.d[i] * (m.lambda_s*m.s[i] + m.lambda_f*m.f[i]) for i in model.I]) 
    return infra_cost 

#assign objective function to model
model.OBJ = pyo.Objective(expr=obj_expression)

# print("OBJECTIVE FUNCTION")
# model.OBJ.display()

def charge_indicator(m, j, k):
    return m.charge[j, k] == sum(m.c[i, j, k] for i in m.I)

model.charge_indicator = pyo.Constraint(model.J, model.K, rule=charge_indicator)
# model.charge_indicator.pprint()


# #CONSTRAINTS 
def soc_constraint(m, j, k):
    #soc_it = soc_i(t-1) + (c_itn * charge_factor)  + (move_indicator * edge weight) 
    if k == 1: 
        return model.soc[j, k] == 100
        #return pyo.Constraint.Skip
    else: 
        charge_increase = (m.charge_factor * m.charge[j, k]) 
        drive_decrease = (m.weight[j,k] * 200) / 420 * 100
        previous_soc = m.soc[j, k - 1]
        current_soc = previous_soc + charge_increase - drive_decrease
        
        # print("decrease", "j",j, "k", k,(pyo.value(m.weight[j,k]) * 200) / 420 * 100)
        
#         increase = pyo.value(m.charge_factor) * pyo.value(m.charge[j, k])
#         decrease = pyo.value(m.weight[j,k]* 200) / 420 * 100
#         prev = pyo.value(m.soc[j, k - 1])
#         current = prev + increase - decrease 
        
#         print("HELLO WORLD", current)
        # print("here")
        return model.soc[j, k] == model.soc[j, k-1] + (model.charge_factor * model.charge[j,k]) - (model.weight[j, k])# * 200 / 420 * 100)
        # return model.soc[j, k] == current_soc
    
model.soc_constraint = pyo.Constraint(model.J, model.K, rule=soc_constraint)
print("DISPLAY SOC CONSTRAINT")
model.soc_constraint.pprint()

#charger assignment logical constriants
def single_agent_use(m, i, k): 
    #for each time step, only one agent can be plugged into a given charger
    return sum(m.c[i,j,k] for j in m.J) <= 1 

model.single_agent_use = pyo.Constraint(model.I, model.K, rule=single_agent_use)

def charger_agent_loc(m, i, j, k): 
    #agent j can only use charger at node i at time step k if it is also at that location
    return m.loc[i,j,k] >= m.c[i,j,k]

model.charger_agent_loc = pyo.Constraint(model.I, model.J, model.K, rule=charger_agent_loc)

def fast_slow_constraint(m, i):
    #charger can only be assigned as fast OR slow
    #if fast then not slow, if slow then not fast
    return m.f[i] + m.s[i] == 1

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

# print("PLACEMENT") 
# print(model.d.display()) 

# print("FAST")
# print(model.f.display())

# print("SLOW")
# print(model.s.display())

# print("LOCATION")
# model.loc.display() 

# print("SOC") 
# model.soc.display() 

# print("EDGE WEIGHTS") 
# model.weight.display() 




#EXPORT DATA FROM OPTIMIZATION
#charger placement data frame
df = pd.DataFrame()
charger_placement = [pyo.value(model.d[i]) for i in model.I]
fast_chargers = [pyo.value(model.f[i]) for i in model.I]
slow_chargers = [pyo.value(model.s[i]) for i in model.I]

df["charger placement"] = charger_placement
df["fast chargers"] = fast_chargers
df["slow chargers"] = slow_chargers

print(df)

df.to_csv("charger_placement.csv")

#agent charging decision data frame, index is the tick value is a list where each entry is binary indiactor for if the agent is charging
df2 = pd.DataFrame()
charge_indicator = []
# location_indicator = []

for k in model.K:
    agent_charging = [pyo.value(model.charge[j, k]) for j in model.J]
    charge_indicator.append(agent_charging)
    
#     for i in model.I: 
#         location = [pyo.value(model.loc[i, j, k]) for j in model.J]
#         location_indicator += location
                      
                      
# df2["agent charging"] = charge_indicator
# df2["agent location"] = location_indicator

                    
                  

# print(df2)

df2.to_csv("chage_indicator.csv")




