import numpy as np
import networkx as nx

from pandas import DataFrame
from sequencer import NetworkPlan, Sequencer
from nose.tools import eq_ 

import sys
# Turn off progress bar and print statements
class catch_prints(object):
    def write(self, arg):
        pass
    def flush(self):
        pass

sys.stdout = catch_prints()    

def gen_data():
    """
    generates test metrics and network, where the network is a 
    balanced graph of height 2 and branch factor 2
    """
    network = nx.balanced_tree(2, 2)

    metrics = DataFrame(network.node).T

    metrics['Demand'] =     [np.nan, 100, 50, 25, 12, 6, 3]
    metrics['Population'] = [np.nan, 100, 50, 25, 12, 6, 3]
    #level 0 
    metrics['coords'] = [np.array([125,10]) for x in  metrics.index]
    #level 2
    metrics['coords'].ix[1] = metrics['coords'].ix[0] + [-.5, -.25]
    metrics['coords'].ix[2] = metrics['coords'].ix[0] + [+.5, -.25]
    #level 3
    metrics['coords'].ix[3] = metrics['coords'].ix[1] + [-.25, -.25]
    metrics['coords'].ix[4] = metrics['coords'].ix[1] + [+.25, -.25]
    metrics['coords'].ix[5] = metrics['coords'].ix[2] + [-.25, -.25]
    metrics['coords'].ix[6] = metrics['coords'].ix[2] + [+.25, -.25]
    metrics['coords'] = metrics['coords'].apply(tuple)

    nx.set_node_attributes(network, 'coords', metrics.coords.to_dict())
    #nx.draw(network, nx.get_node_attributes(network, 'coords'))
    
    return metrics, network.to_directed()

class TestNetworkPlan(NetworkPlan):
    
    def __init__(self):
        self._metrics, self._network = gen_data()
        self.proj = 'wgs4'
        self.priority_metric = 'Population'
        self.distance_matrix = self._distance_matrix()
        
        # Set the edge weight to the distance between those nodes                                                                                                             
        self._weight_edges()

        # Transform edges to a rooted graph                                                                                                                                   
        self.direct_network()
        self._metrics = self.metrics.fillna(0)

class TestSequencer(Sequencer):
    
    def nodal_demand(self, df):
        return df['Demand']
    def sequence(self):
        return DataFrame(list(self._sequence())).set_index('Sequence..Far.sighted.sequence')

def test_is_tree():
    """Ensures all roots have in_degree of 0 and leaves have in_degree of 1"""
    nwp = TestNetworkPlan()
    in_degree = nwp.network.in_degree()
    # Test that all roots have in_degree == 0
    ensure_roots = [in_degree[root] == 0 for root in nwp.roots]
    # Test that all leaves have in_degree == 1
    ensure_leaves = [in_degree[leaf] == 1 for leaf in (set(nwp.network.node.keys()) - set(nwp.roots))]

    eq_(all(ensure_roots + ensure_leaves), True)

def test_accumulate_demand():
    """Tests that the accumulated demand is correct"""
    
    nwp = TestNetworkPlan()
    # Build dictionary of accumulated values for each node
    acc_dicts =  {node : TestSequencer(nwp).accumulate(node) for node in nwp.network.node.keys()}
    # Dictionary of known accumulated demand computed manually
    demands = {0: (100 + 50 + 25 + 12 + 6 + 3), 
               1: (100 + 25 + 12), 
               2: ( 50 +  6 +  3), 
               3:25, 4:12, 5:6, 6:3}
    
    # Assert that accumulate method and manual computation are equal
    eq_(np.all([acc_dicts[node]['demand'] == demands[node] for node in nwp.network.node.keys()]), True)

def test_accumulate_cost():
    """Tests that the accumulates costs are correct"""

    nwp = TestNetworkPlan()
    # Build dictionary of accumulated values for each node
    acc_dicts = {node : TestSequencer(nwp).accumulate(node) for node in nwp.network.node.keys()}
    def get_distance(f, t):
        return nwp.distance_matrix[f][t]

    # Manually compute downstream distances
    costs = {0 : sum([get_distance(0, 1), get_distance(0, 2), 
                      get_distance(1, 3), get_distance(1, 4), 
                      get_distance(2, 5), get_distance(2, 6)]),
             1 : sum([get_distance(0, 1), get_distance(1, 3), get_distance(1, 4)]),
             2 : sum([get_distance(0, 2), get_distance(2, 5), get_distance(2, 6)]),
             3 : get_distance(1, 3),
             4 : get_distance(1, 4),
             5 : get_distance(2, 5),
             6 : get_distance(2, 6)}

    eq_(np.all([np.allclose(acc_dicts[node]['cost'], costs[node]) for node in nwp.network.node.keys()]), True)

def test_sequencer_follows_topology():
    """Tests that the sequencer doesn't skip nodes in the network"""
    nwp = TestNetworkPlan()
    model = TestSequencer(nwp)
    results = model.sequence()
    fnodes = results['Sequence..Upstream.id']
    tnodes = results['Sequence..Root.vertex.id']

    #For each from_node, assert that the sequencer has already pointed to it or its a root
    eq_(np.all([fnode in nwp.roots or fnode in tnodes.ix[:i-1] for i, fnode in fnodes.iterkv()]), True)

