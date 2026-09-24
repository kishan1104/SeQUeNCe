from cmath import inf
import math
from sequence.qkd.cascade import Cascade
from ipywidgets import interact
from matplotlib import pyplot as plt
import time
from sequence.constants import SPEED_OF_LIGHT
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from sequence.kernel.timeline import Timeline
from sequence.topology.node import QKDNode
from sequence.components.optical_channel import QuantumChannel, ClassicalChannel
from sequence.constants import MILLISECOND
from DPSqkd.DPSprotocol import DPS,pair_dps_protocols
from DPSqkd.CustomComponents import DPSNode, ExtRouterNetTopo
from DPSqkd.PrivacyAmplification import PrivacyAmplification, pair_privacy_amp_protocols

from sequence.qkd.cascade import pair_cascade_protocols
import networkx as nx

import json







# source = "N00"
# destination = "N41"

# # Find one shortest path
# path = nx.shortest_path(G, source, destination)

# print("Shortest path:", path)




class KeyManager():
    def __init__(self, timeline, keysize, num_keys):
        # self.owner = owner
        self.timeline = timeline
        self.lower_protocols = []
        self.keysize = keysize
        self.num_keys = num_keys
        self.keys = []
        self.times = []
        
    def send_request(self):
        for p in self.lower_protocols:
            print(p)
            p.push(self.keysize, self.num_keys) # interface for cascade to generate keys
            
    def pop(self, key): # interface for cascade to return generated keys
        self.keys.append(key)
        self.times.append(self.timeline.now() * 1e-9)

def create_dps(node,stack_size=3):
    if stack_size > 0:
        # print('this is run')
        node.protocols = []
        node.protocol_stack[0] = DPS(node, node.name + ".DPS", node.name+'.light_source', node.name+'.interferometer')
        node.protocols.append(node.protocol_stack[0])
    if stack_size > 1:
        # Create cascade protocol
        node.protocol_stack[1] = Cascade(node, node.name + ".cascade")
        node.protocols.append(node.protocol_stack[1])
        node.protocol_stack[0].upper_protocols.append(node.protocol_stack[1])
        node.protocol_stack[1].lower_protocols.append(node.protocol_stack[0])
    if stack_size > 2:
        node.protocol_stack[2] = PrivacyAmplification(node,node.name+".privacy_amplification")
        node.protocols.append(node.protocol_stack[2])
        node.protocol_stack[1].upper_protocols.append(node.protocol_stack[2])
        node.protocol_stack[2].lower_protocols.append(node.protocol_stack[1])


def test(sim_time, keysize, net_file, source, destination, stack_size=3, frequency=1e6, mean_photon_num=0.2, phase_error=0.01):
    """
    sim_time: duration of simulation time (ms)
    keysize: size of generated secure key (bits)
    net_file: path to the network configuration file
    """
    # begin by defining the simulation timeline with the correct simulation time
    tl = Timeline()
    
    # Here, we create nodes for the network (QKD nodes for key distribution)
    n1 = DPSNode("n1", tl, frequency=frequency, mean_photon_num=mean_photon_num, phase_error=phase_error)
    n2 = DPSNode("n2", tl, frequency=frequency, mean_photon_num=mean_photon_num, phase_error=phase_error)
    n3 = DPSNode("n3", tl, frequency=frequency, mean_photon_num=mean_photon_num, phase_error=phase_error)
    n4 = DPSNode("n4", tl, frequency=frequency, mean_photon_num=mean_photon_num, phase_error=phase_error)
    # n1.set_seed(0)
    # n2.set_seed(1)
    # n3.set_seed(2)
    create_dps(n1,stack_size=3)
    create_dps(n2,stack_size=3)
    create_dps(n3,stack_size=3)
    create_dps(n4,stack_size=3)
    n1.protocol_stack[1].lower_protocols[0] = n1.protocol_stack[0]
    n2.protocol_stack[1].lower_protocols[0] = n2.protocol_stack[0]
    n3.protocol_stack[1].lower_protocols[0] = n3.protocol_stack[0]
    n4.protocol_stack[1].lower_protocols[0] = n4.protocol_stack[0]
    pair_dps_protocols(n1.protocol_stack[0], n2.protocol_stack[0])
    pair_cascade_protocols(n1.protocol_stack[1], n2.protocol_stack[1])
    pair_privacy_amp_protocols(n1.protocol_stack[2], n2.protocol_stack[2])


    
    # connect the nodes and set parameters for the fibers
    cc0 = ClassicalChannel("cc_n1_n2", tl, distance=1e3)
    cc1 = ClassicalChannel("cc_n2_n1", tl, distance=1e3)
    cc23 = ClassicalChannel("cc_n2_n3", tl, distance=1e3)
    cc32 = ClassicalChannel("cc_n3_n2", tl, distance=1e3)
    cc34 = ClassicalChannel("cc_n3_n4", tl, distance=1e3)
    cc43 = ClassicalChannel("cc_n4_n3", tl, distance=1e3)
    cc0.set_ends(n1, n2.name)
    cc1.set_ends(n2, n1.name)
    cc23.set_ends(n2, n3.name)
    cc32.set_ends(n3, n2.name)
    cc34.set_ends(n3, n4.name)
    cc43.set_ends(n4, n3.name)
    qc0 = QuantumChannel("qc_n1_n2", tl, attenuation=2e-4, distance=8e3, polarization_fidelity=0.97)
    qc1 = QuantumChannel("qc_n2_n1", tl, attenuation=2e-4, distance=8e3, polarization_fidelity=0.97)
    qc23 = QuantumChannel("qc_n2_n3", tl, attenuation=2.5e-5, distance=1e3, polarization_fidelity=0.97)
    qc32 = QuantumChannel("qc_n3_n2", tl, attenuation=2.5e-5, distance=1e3, polarization_fidelity=0.97)
    qc34 = QuantumChannel("qc_n3_n4", tl, attenuation=2.5e-5, distance=1e3, polarization_fidelity=0.97)
    qc43 = QuantumChannel("qc_n4_n3", tl, attenuation=2.5e-5, distance=1e3, polarization_fidelity=0.97)

    qc0.set_ends(n1, n2.name)
    qc1.set_ends(n2, n1.name)
    qc23.set_ends(n2, n3.name)
    qc32.set_ends(n3, n2.name)
    qc34.set_ends(n3, n4.name)
    qc43.set_ends(n4, n3.name)

    # instantiate our written keysize protocol
    km1 = KeyManager(tl, keysize, 1)
    km1.lower_protocols.append(n1.protocol_stack[2])
    n1.protocol_stack[2].upper_protocols.append(km1)
    km2 = KeyManager(tl, keysize, 1)
    km2.lower_protocols.append(n2.protocol_stack[2])
    n2.protocol_stack[2].upper_protocols.append(km2)
    km3 = KeyManager(tl, keysize, 1)
    km3.lower_protocols.append(n3.protocol_stack[2])
    n3.protocol_stack[2].upper_protocols.append(km3)

    network_config_file = net_file
    network_topo = ExtRouterNetTopo(network_config_file)
    timeline = network_topo.get_timeline()
    routers = network_topo.get_nodes_by_type(ExtRouterNetTopo.DPS_NODE)
    with open("clustered_network.json", "r") as f:
        data = json.load(f)

# Create an undirected graph
    G = nx.Graph()

    # Add only qconnections
    for connection in data["qconnections"]:
        G.add_edge(
            connection["node1"],
            connection["node2"],
            distance=connection["distance"]
        )
    # print(network_topo.nodes)
    nodes = nx.shortest_path(G, source, destination)

    # print("Shortest path:", nodes)

    # print("routers:", routers, 'length :', len(routers))
    # print(network_topo.nodes, network_topo.nodes[destination])
    for node in routers:
        if node.name in nodes:
            idx = nodes.index(node.name)
            nodes[idx] = node

    class Node3Net:
        def __init__(self,nodes:list,timeline,keysize=128, stack_size=3):
            self.keymanagers = {}
            self.nodes = nodes
            self.key_size = keysize
            self.timeline = timeline
            self.stack_size = stack_size
        
        def GetKey(self,node1,node2): 
            # self.alice_dps = DPS(node1,'dps1',node1.name+'.light_source') 
            # self.bob_dps = DPS(node2,'dps',node2.name+'.light_source') 
            create_dps(node1,stack_size=self.stack_size)
            create_dps(node2,stack_size=self.stack_size)
            pair_dps_protocols(node1.protocol_stack[0], node2.protocol_stack[0])
            pair_cascade_protocols(node1.protocol_stack[1], node2.protocol_stack[1])
            pair_privacy_amp_protocols(node1.protocol_stack[2], node2.protocol_stack[2])

            
        # if self.keymanagers.get(node1.name) is None:
            keymanager = KeyManager(self.timeline, self.key_size, 1)
            keymanager.lower_protocols.append(node1.protocol_stack[2])
            node1.protocol_stack[2].upper_protocols.append(keymanager)
            self.keymanagers[(node1.name, node2.name)] = keymanager

        # if self.keymanagers.get(node2.name) is None:
            km2 = KeyManager(self.timeline, self.key_size, 1)
            km2.lower_protocols.append(node2.protocol_stack[2])
            node2.protocol_stack[2].upper_protocols.append(km2)
            self.keymanagers[(node2.name, node1.name)] = km2

            

            self.keymanagers[(node1.name, node2.name)].send_request() # interface to get keys back


        def run(self):

            key_bet = []
            for i in range(len(self.nodes)):
                if i == len(self.nodes)-1:
                    break
                key_bet.append((self.nodes[i],self.nodes[i+1]))
            

            start_time = None
            end_time = None
            for i,(node1,node2) in enumerate(key_bet):
                delay = node1.qchannels[node2.name].distance / SPEED_OF_LIGHT
                if i == 0:
                    start_time = self.timeline.now()
                    end_time = start_time + (int((self.key_size +10000 / node1.source.frequency) * 1e12)) + delay  
                    process = Process(self,"GetKey",[node1,node2])
                    event = Event(start_time, process)
                    self.timeline.schedule(event)
                else:
                    start_time = end_time   # Schedule next round after the previous one finishes
                    end_time = start_time + (int((self.key_size +10000 / node1.source.frequency) * 1e12)) + delay
                    process = Process(self,"GetKey",[node1,node2])
                    event = Event(start_time, process)
                    self.timeline.schedule(event)
            print(end_time, "scheduled all key generation processes")




    # nodes = [n1,n2,n3,n4]

    # print(nodes)

    net = Node3Net(nodes, timeline, keysize=keysize)

    # start simulation and record timing
    timeline.init()
    # net.run()
    tick = time.time()
    timeline.run()


    tl.init()
    km1.send_request()
    tl.run()

    print(km1.keys,km2.keys)

    for km in net.keymanagers.keys():
        print(km, ':', net.keymanagers[km].keys)


    
    error_rates = []

    print("execution time %.2f sec" % (time.time() - tick))

test(1e12 , 128, "./clustered_network.json", "N0", "N00")