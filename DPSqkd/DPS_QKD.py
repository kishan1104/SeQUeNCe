
from sequence.kernel.timeline import Timeline
from DPSqkd.DPSprotocol import DPSMessage,DPSMsgType
from sequence.topology.node import Node,QuantumRouter
import numpy as np
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from DPSqkd.DPSprotocol import DPS,pair_dps_protocols,DPSMessage
from sequence.qkd.cascade import pair_cascade_protocols
from sequence.constants import SPEED_OF_LIGHT
from DPSqkd.Utility import calculate_qber, estimate_qber, CreateNetwork
from DPSqkd.CustomComponents import DPSNode, ExtRouterNetTopo, EveDPSNode
from sequence.components.optical_channel import QuantumChannel, ClassicalChannel

# tl = Timeline()
# tl2 = Timeline()
pi  = np.pi



    
class Node3Net:
    def __init__(self,nodes:list,timeline,keysize=128):
        
        self.nodes = nodes
        self.key_size = keysize
        self.timeline = timeline
    
    def GetKey(self,node1:QuantumRouter,node2:QuantumRouter):
        self.alice_dps = DPS(node1,'dps1',node1.name+'.light_source') 
        self.bob_dps = DPS(node2,'dps',node2.name+'.light_source') 
        
        pair_dps_protocols(self.alice_dps,self.bob_dps)
        if len(node1.protocols) >= 1:
            node1.protocols[0] = self.alice_dps
        if len(node2.protocols) >= 1:
            node2.protocols[0] = self.bob_dps
        else:
            node1.protocols.append(self.alice_dps)
            node2.protocols.append(self.bob_dps)
        
        self.alice_dps.push(self.key_size)
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
                end_time = start_time + (int((self.key_size / node1.source.frequency) * 1e12)) + delay  # Run for a duration that allows key generation
                process = Process(self,"GetKey",[node1,node2])
                event = Event(start_time, process)
                self.timeline.schedule(event)
            else:
                start_time = end_time   # Schedule next round after the previous one finishes
                end_time = start_time + (int((self.key_size / node1.source.frequency) * 1e12)) + delay
                process = Process(self,"GetKey",[node1,node2])
                event = Event(start_time, process)
                self.timeline.schedule(event)
        print(end_time, "scheduled all key generation processes")
        start_time = end_time
        end_time = start_time +(int((self.key_size / node1.source.frequency) * 1e12))
        process = Process(self,"make_keys",[self.nodes])
        event = Event(end_time, process)
        self.timeline.schedule(event)
        # process2 = Process(self,"propogate_Keys",[self.nodes])
        # event2 = Event(end_time+ 20000, process2)
        # self.timeline.schedule(event2)
    
    def make_keys(self,nodes:list[Node]):
        for i,node in enumerate(nodes):
            if i == 0:
                node.dpskeys[f'K{i+1}'] = node.aliceKey
            elif i == len(nodes)-1:
                node.dpskeys[f'K{i}'] = node.bobKey
            
            else:
                node.dpskeys[f'K{i}'] = node.bobKey
                node.dpskeys[f'K{i+1}'] = node.aliceKey
        print(self.timeline.now(), "finished key generation, propogating keys")
        
    def propogate_Keys(self,nodes:list[Node]):
        minimum = 128
        for i, node in enumerate(nodes):
            for key,value in node.dpskeys.items():
                if len(value) < minimum:
                    minimum = len(value)
        print("minimum key length:", minimum)
        for i,node in enumerate(nodes):
            for key in node.dpskeys.keys():
                node.dpskeys[key] = node.dpskeys[key][:minimum]
        delay_time = 0
        process = Process(self,"propagation1",[nodes])
        event = Event(self.timeline.now()+delay_time, process)
        self.timeline.schedule(event)
        delay_time += 20000000
        process2 = Process(self,"propagation2",[nodes])
        event2 = Event(self.timeline.now()+delay_time, process2)
        self.timeline.schedule(event2)
        delay_time += 20000000
        process3 = Process(self,"propagation3",[nodes])
        event3 = Event(self.timeline.now()+delay_time, process3)
        self.timeline.schedule(event3)
       
    def propagation1(self,nodes:list[Node]):
        # first Propogation from Node1 to Node0 and Node2
        msg1 = nodes[1].dpskeys['K1']
        msg2 = nodes[1].dpskeys['K2']
        send_msg = ''.join(str(int(a) ^ int(b)) for a, b in zip(msg1, msg2))
        key_name = f'K{2}'
        nodes[1].send_message(nodes[0].name, DPSMessage(DPSMsgType.KEY_PROPAGATION,nodes[0].name,key = send_msg,keyname=key_name,xorKey='K1'))
        key_name = f'K{1}'
        nodes[1].send_message(nodes[2].name, DPSMessage(DPSMsgType.KEY_PROPAGATION,nodes[2].name,key = send_msg,keyname=key_name,xorKey='K2'))
    
    def propagation2(self,nodes:list[Node]):
        msg1 = nodes[2].dpskeys['K2']
        msg2 = nodes[2].dpskeys['K3']
        send_msg = ''.join(str(int(a) ^ int(b)) for a, b in zip(msg1, msg2))
        key_name = f'K{3}'
        nodes[2].send_message(nodes[1].name, DPSMessage(DPSMsgType.KEY_PROPAGATION,nodes[3].name,key = send_msg,keyname=key_name,xorKey='K2'))
        key_name = f'K{2}'
        nodes[2].send_message(nodes[3].name, DPSMessage(DPSMsgType.KEY_PROPAGATION,nodes[1].name,key = send_msg,keyname=key_name,xorKey='K3'))
    
    def propagation3(self,nodes:list[Node]):
        # print(nodes[0].dpskeys)
        msg1 = nodes[1].dpskeys['K1']
        msg2 = nodes[1].dpskeys['K3']
        send_msg = ''.join(str(int(a) ^ int(b)) for a, b in zip(msg1, msg2))
        key_name = f'K{3}'
        nodes[1].send_message(nodes[0].name, DPSMessage(DPSMsgType.KEY_PROPAGATION,nodes[0].name,key = send_msg,keyname=key_name,xorKey='K1'))
        msg1 = nodes[2].dpskeys['K1']
        msg2 = nodes[2].dpskeys['K3']
        send_msg = ''.join(str(int(a) ^ int(b)) for a, b in zip(msg1, msg2))
        key_name = f'K{1}'
        nodes[2].send_message(nodes[3].name, DPSMessage(DPSMsgType.KEY_PROPAGATION,nodes[3].name,key = send_msg,keyname=key_name,xorKey='K3'))




# network_config_file = 'clustered_network.json'
# network_topo = ExtRouterNetTopo(network_config_file)
# timeline = network_topo.get_timeline()
# routers = network_topo.get_nodes_by_type(ExtRouterNetTopo.DPS_NODE)


# router_names = [node.name for node in routers]

# main_routers = [router for router in routers if router.name in ['N0', 'N1', 'N2', 'N3', 'N4']]

# bsm_routers = [router for router in routers if router.name not in ['N0', 'N1', 'N2', 'N3', 'N4']]

# print("routers in the network:", main_routers)



# nwt = Node3Net(nodes, tl,256)

# nwt.run()

# nwt.GetKey(main_routers[0],main_routers[1])
# nwt.GetKey(nodes[0],nodes[1])

def test(n):
    nodenwt = []
    nodes = []
    timelines = []
    for i in range(n):
        tim = Timeline()
        node = CreateNetwork(2, tim, DPSNode)
        nwt = Node3Net(node, tim,2990)
        nodenwt.append(nwt)
        nodes.append(node)
        timelines.append(tim)
    return nodenwt,nodes,timelines


def qber_with_eve(n,attack=''):
    nodes = []
    timelines = []
    nwtnodes = []
    for i in range(n):
        tim = Timeline()
        alice = DPSNode('Alice', tim)
        bob = DPSNode('Bob', tim)
        eve = EveDPSNode('Eve', tim,attack=attack)

        qc1 = QuantumChannel('qc_Alice_Eve', tim, attenuation=0.0002, distance=40100)
        qc1.set_ends(alice, eve.name)
        qc2 = QuantumChannel('qc_Eve_Bob', tim, attenuation=0.0002, distance=0)
        qc2.set_ends(eve, bob.name)

        cc1 = ClassicalChannel('cc_Alice_Bob', tim, 1000)
        cc1.set_ends(alice, bob.name)
        cc2 = ClassicalChannel('cc_Bob_Alice', tim, 1000)
        cc2.set_ends(bob, alice.name)

        alice_dps = DPS(alice,'dps1',alice.name+'.light_source')
        bob_dps = DPS(bob,'dps',bob.name+'.light_source')
        eve_dps = DPS(eve,'dps2',eve.name+'.light_source')
        pair_dps_protocols(alice_dps,bob_dps,eve_dps)
        alice.protocols[0] = alice_dps
        bob.protocols[0] = bob_dps
        eve.protocols[0] = eve_dps

        nodes.append((alice,bob,eve))
        nwtnodes.append((alice_dps,bob_dps,eve_dps))
        timelines.append(tim)

    return nwtnodes, nodes, timelines

# nwtnodes, node_list, timeline_list = test(1)

# for i,tm in enumerate(timeline_list):
#         tm.init()
#         nwtnodes[i].run()
#         tm.run()

nwtnodes, nodes, timelines = test(1)

for i,tm in enumerate(timelines):
        tm.init()
        nwtnodes[i].run()
        tm.run()

# nwtnodes, nodes, timelines = qber_with_eve(100,'IR')
# for i,tm in enumerate(timelines):
#         tm.init()
#         nwtnodes[i][0].push(128)
#         tm.run()


tl = Timeline()
alice = DPSNode('Alice', tl)
bob = DPSNode('Bob', tl)
eve = EveDPSNode('Eve', tl)


qc1 = QuantumChannel('qc_Alice_Eve', tl, attenuation=0.0002, distance=1000)
qc1.set_ends(alice, eve.name)
qc2 = QuantumChannel('qc_Eve_Bob', tl, attenuation=0.0002, distance=0)
qc2.set_ends(eve, bob.name)

cc1 = ClassicalChannel('cc_Alice_Bob', tl, 1000)
cc1.set_ends(alice, bob.name)
cc2 = ClassicalChannel('cc_Bob_Alice', tl, 1000)
cc2.set_ends(bob, alice.name)


alice_dps = DPS(alice,'dps1',alice.name+'.light_source')
bob_dps = DPS(bob,'dps',bob.name+'.light_source')
eve_dps = DPS(eve,'dps2',eve.name+'.light_source')
pair_dps_protocols(alice_dps,bob_dps,eve_dps)
alice.protocols[0] = alice_dps
bob.protocols[0] = bob_dps
eve.protocols[0] = eve_dps



class KeyManager():
    def __init__(self, timeline, keysize, num_keys):
        self.timeline = timeline
        self.lower_protocols = []
        self.keysize = keysize
        self.num_keys = num_keys
        self.keys = []
        self.times = []
        
    def send_request(self):
        for p in self.lower_protocols:
            p.push(self.keysize, self.num_keys) # interface for cascade to generate keys
            
    def pop(self, key): # interface for cascade to return generated keys
        self.keys.append(key)
        self.times.append(self.timeline.now() * 1e-9)
        print(f"KeyManager received key: {key} at time {self.timeline.now() * 1e-9} seconds")


tl.init()
# alice_dps.push(64)
tl.run()

tl2 = Timeline((1000*10000)*1e9)
alice2 = DPSNode('Alice2', tl2)
bob2 = DPSNode('Bob2', tl2)

acqc2 = QuantumChannel('qc_Alice2_Bob2', tl2, attenuation=0.0002, distance=1000)
acqc2.set_ends(alice2, bob2.name)

accc1 = ClassicalChannel('cc_Alice2_Bob2', tl2, 1000)
accc1.set_ends(alice2, bob2.name)
accc2 = ClassicalChannel('cc_Bob2_Alice2', tl2, 1000)
accc2.set_ends(bob2, alice2.name)

alice2_dps = DPS(alice2,f'{alice2.name}.DPS',alice2.name+'.light_source')
bob2_dps = DPS(bob2,'dps',bob2.name+'.light_source')
pair_dps_protocols(alice2_dps,bob2_dps)
alice2.protocols[0] = alice2_dps
bob2.protocols[0] = bob2_dps
alice2.protocol_stack[0] = alice2_dps
bob2.protocol_stack[0] = bob2_dps
alice2.protocol_stack[1].lower_protocols[0] = alice2.protocol_stack[0]
bob2.protocol_stack[1].lower_protocols[0] = bob2.protocol_stack[0]

print(alice2.protocol_stack)

pair_cascade_protocols(alice2.protocol_stack[1],bob2.protocol_stack[1])

km1 = KeyManager(tl2, 1000, 1)
km1.lower_protocols.append(alice2.protocol_stack[1])
alice2.protocol_stack[1].upper_protocols.append(km1)
alice2.protocol_stack[0].upper_protocols.append(bob2.protocol_stack[1])
km2 = KeyManager(tl2, 1000, 1)
km2.lower_protocols.append(bob2.protocol_stack[1])
bob2.protocol_stack[1].upper_protocols.append(alice2.protocol_stack[1])
bob2.protocol_stack[1].upper_protocols.append(km2)
# print('upper protocols',alice2.protocol_stack[0].upper_protocols)

tl2.init()
# alice2_dps.push(8000)
# alice2.protocols[1].push(100)
km1.send_request()
tl2.run()
# alice2.protocols[1].state = 1


# print("Alice2's keys:", km1.keys)
# error_rates = []
# for i, key in enumerate(km1.keys):
#     counter = 0
#     diff = key ^ km2.keys[i]
#     for j in range(km1.keysize):
#         counter += (diff >> j) & 1
#     error_rates.append(counter)

# print("key error rates:")
# for i, e in enumerate(error_rates):
#     print("\tkey {}:\t{}%".format(i + 1, e * 100))
# timeline.init()
# timeline.run()


# print(alice.aliceKey)
# print(bob.bobKey)
# print(eve.eve_key)

# print(alice2.aliceKey)
# print(bob2.bobKey)
# print(eve.eve_key)

# needed_keys = [('N0','N11'),('N2','N41')]


# for i,node in enumerate(nodes):
#     print(f" {node.name}'s dps keys: {node.dpskeys}")

def print_keys_and_qber(nodes:list[Node]):
    quber_list = []
    for i,node in enumerate(nodes):
        # print(node[0].aliceKey,node[1].bobKey)
        if  len(node[0].aliceKey) > len(node[1].bobKey):
            qber = calculate_qber(node[0].aliceKey[:len(node[1].bobKey)], node[1].bobKey)
            # print(f"quber of {i}", qber)
            quber_list.append(qber)
        else: 
            qber = calculate_qber(node[0].aliceKey, node[1].bobKey[:len(node[0].aliceKey)])
            # print(f"quber of {i}", qber)
            quber_list.append(qber)
        print("alice_Key=",node[0].aliceKey)
        print(f'bob_key={node[1].bobKey}')
        print(f'len of keys = {len(node[1].bobKey)}')
        # print(f'eve_key={''.join(str(key[0]) for key in node[2].eveKey)}')
    print("average qber:", sum(quber_list)/len(quber_list))


# for i, e in enumerate(alice2.protocol_stack[0].error_rates):
#         print("\tkey {}:\t{}%".format(i + 1, e * 100))
    
# print_keys_and_qber(nodes)

# print_keys_and_qber([(alice2,bob2)])


# for node in node_list[0]:
#     print(f"{node.name}'s alice key: {node.aliceKey}")
#     print(f"{node.name}'s bob key  : {node.bobKey}")

# if  len(nodes[0].aliceKey) > len(nodes[1].bobKey):
#     print(calculate_qber(nodes[0].aliceKey[:len(nodes[1].bobKey)], nodes[1].bobKey))
# else: 
#     print(calculate_qber(nodes[0].aliceKey, nodes[1].bobKey[:len(nodes[0].aliceKey)]))

# print(calculate_qber(nodes[0].aliceKey, nodes[1].bobKey))


