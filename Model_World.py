import networkx as nx
import itertools
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import random
import math

random.seed(10)

class Model_World(): 
    def __init__(self, no_homes, no_work, no_stores, no_ticks): 
        self.no_homes = no_homes
        self.no_work = no_work
        self.no_stores = no_stores
        self.total_nodes = no_homes + no_work + no_stores
        self.no_ticks = no_ticks
        
        node_types = {}
        node_types["homes"] = [i for i in range(no_homes)]
        node_types["work"] = [i for i in range(no_homes, no_homes + no_work)]
        node_types["stores"] = [i for i in range(no_homes + no_work, no_homes + no_work + no_stores)]
        self.node_types = node_types
        
        self.G = self.build_graph()
        self.color_map = self.get_color_map()
        
    def get_node_type(self,node): 
        if node < self.no_homes: 
            return "home"
        elif self.no_homes <= node and node < self.no_work + self.no_homes: 
            return "work"
        elif node >= self.no_work + self.no_homes and node < self.total_nodes: 
            return "store" 
        else: 
            return None
        
    def get_edge_weight(self, node1, node2): 
        """ edge weights are given as # of ticks, where one tick = 30 minutes""" 

        type1 = self.get_node_type(node1)
        type2 = self.get_node_type(node2)
        if (type1 == "home" and type2 == "work") or (type2 == "home" and type1 == "work"): 
            return round(random.random() * 3,2) #between 0 and 1.5 hours home to work

        elif (type1 == "work" and type2 == "store") or (type2 == "work" and type1 == "store"): 
            return round(random.random(),2) #between 0 and half an hour work to store 

        elif (type1 == "home" and type2 == "store") or (type2 == "home" and type1 == "store"): 
            return round(random.random() * 2 ,2) #between 0 and 1 hours home to store

        else:
            return None
        
    def get_trip_lists(self):
        result_dict = {}

        for i in range(self.no_homes): 
            trip_list = []
            trip_length = []

            work_id = random.choice(self.node_types["work"])

            while sum(trip_length[1:]) < self.no_ticks: 
                trip_list.append(i)
                trip_length.append(random.randint(16,28))

                trip_list.append(work_id) 
                trip_length.append(random.randint(16,20))

                trip_list.append(random.choice(self.node_types["stores"]))
                trip_length.append(random.randint(4,8))

            result_dict[i] = (trip_list, trip_length)

        return result_dict
    
    def get_charger_placement(self, scenario, n):
        """ returns a list of integers representing the nodes where chargers are placed """ 
        
        charger_placement = []
        if scenario == 1: # scenario 1 is that there are chargers at all homes plus n additional chargers to be ranomly placed at stores/work
            charger_placement += self.node_types["homes"]
            work_store_nodes = self.node_types["work"] + self.node_types["stores"] 
            charger_placement += [random.choice(work_store_nodes) for i in range(n)]
            return charger_placement
        
        if scenario == 2: #scenario 2 is to place all n chargers randomly (note this causes the issue that some vehicles may never visit a node with a charger)
            nodes = [i for i in range(self.total_nodes)] 
            return [random.choice(nodes) for i in range(n)] 
        
    
    def build_graph(self):
        G = nx.Graph()

        nodes = [i for i in range(self.total_nodes)]
        
        #Add edges for fully connected graph
        G.add_nodes_from(nodes)
        G.add_edges_from(itertools.combinations(nodes, 2))
        G.add_edges_from([(i, i) for i in range(self.total_nodes)]) #add self loops 

       #Add randomly generated edge weights
        for i in range(self.no_homes): #loop over homes
            for j in range(self.no_homes, self.no_homes + self.no_work): #loop over work
                G[i][j]['weight'] = self.get_edge_weight(i, j) 
                G[j][i]['weight'] = G[i][j]['weight']

            for w in range(self.no_homes + self.no_work, self.total_nodes): #loop over stores
                G[i][w]["weight"] = self.get_edge_weight(i, w) 
                G[w][i]["weight"] = G[i][w]["weight"]

        for k in range(self.no_homes, self.no_homes + self.no_work): #loop over work
            for h in range(self.no_homes + self.no_work, self.total_nodes): #loop over stores 
                G[k][h]['weight'] = self.get_edge_weight(k,h) 
                G[h][k]['weight'] = G[k][h]['weight']

        #add edge weight 0 for self loops and edges between nodes of same type
        for pair in itertools.product([i for i in range(self.no_homes)], repeat=2):
            G[pair[0]][pair[1]]["weight"] = 0

        for pair in itertools.product([i for i in range(self.no_homes, self.no_homes + self.no_work)], repeat=2):
            G[pair[0]][pair[1]]["weight"] = 0

        for pair in itertools.product([i for i in range(self.no_homes + self.no_work, self.total_nodes)], repeat=2):
            G[pair[0]][pair[1]]["weight"] = 0

        return G
    
    def get_color_map(self): 
        #define color map 
        #G = self.build_graph()

        color_map = []
        for node in self.G: 
            node_type = self.get_node_type(node)

            if node_type == "home":
                color_map.append("red")
            elif node_type == "work": 
                color_map.append("green")
            elif node_type == "store": 
                color_map.append("blue")

        return color_map

    def print_graph(self):
        #Print Graph G

        pos=nx.spring_layout(self.G)
        edge_weight = nx.get_edge_attributes(self.G, 'weight')

        nx.draw(self.G, with_labels=True, node_size=500, node_color = self.color_map)
        nx.draw_networkx_edge_labels(self.G, pos, edge_labels = edge_weight)
        plt.show() 
        