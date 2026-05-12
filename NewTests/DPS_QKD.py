import time

from sequence.kernel.timeline import Timeline
from NewTests.DPSprotocol import DPSMessage,DPSMsgType
from sequence.message import Message
from sequence.topology.node import Node,QKDNode,QSDetectorTimeBin
from sequence.protocol import StackProtocol
from sequence.components.detector import Detector,QSDetector
from sequence.components.interferometer import Interferometer
from sequence.components.photon import Photon
from sequence.components.light_source import LightSource
from sequence.components.optical_channel import QuantumChannel,ClassicalChannel
from sequence.components.detector import QSDetectorTimeBin
import numpy as np
from numpy import sqrt
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from sequence.utils.encoding import time_bin
from NewTests.DPSprotocol import DPS,pair_dps_protocols,DPSMessage


print("started running test")


tl = Timeline()
tl2 = Timeline()
pi  = np.pi

class CDetector(Detector):
    def __init__(self, name, timeline, efficiency = 1, dark_count = 0, count_rate = 25000000, time_resolution = 150):
        super().__init__(name, timeline, efficiency, dark_count, count_rate, time_resolution)
    
    def get(self,photon=None, **kwargs):
        self.photon_counter +=1
        
        if self.get_generator().random() < self.efficiency:

            self.record_detection()
            process = Process( self._receivers[0], "photonDet",   [self.name, self.timeline.now()])
            event = Event(self.timeline.now(), process)
            self.timeline.schedule(event)
            # self._receivers[0].get(self.name, self.timeline.now())
            # print("recieved detector of arrival:",self.name, self.timeline.now())

            
        else:
            print(f'Photon loss in detector {self.name}')

class CInterferometer(Interferometer):
    def __init__(self, name, timeline, path_diff, phase_error=0):
        super().__init__(name, timeline, path_diff, phase_error)
        pass
    def get(self,photon:"Photon",**kwargs):
        assert photon.encoding_type["name"] == "time_bin", \
            "Invalid photon encoding {} received by interferometer".format(photon.encoding_type["name"])
        if photon.use_qm:
            raise NotImplementedError("Interferometer usage not configured for quantum manager.")
        state = photon.quantum_state.state

        # print("allival at interferometer,:", self.timeline.now(), "state:", state)
# -------- 3 time-bin interferometer --------
        # print(len(state))
        if len(state) == 3:

            a, b, c = state
            r = self.get_generator().random()

            # print(a,b,c)
            # outer slots probability
            p_early = 0.16666666666
            p_late  = 0.16666666666

            # choose time slot
            if r < p_early:
                # time t
                time = 0
                detector_num = self.get_generator().choice([0,1])

            elif r < 0.5:
                # -------- first interference (E,M) --------
                time = self.path_difference

                # constructive / destructive
                if abs(a + b) > abs(a - b):
                    # print('constructive',time)
                    # print('constructive E M', abs(a+b), 'a,b ',abs(a-b), "a and b",a,"   ",b)
                    detector_num = 0
                else:
                    # print('destructive',abs(a + b),' a,b ', abs(a - b),abs(a-b), "a and b",a,"   ",b)
                    # print('destructive',time)
                    detector_num = 1

            elif r < 1 - p_late:
                # -------- second interference (M,L) --------
                time = 2 * self.path_difference

                if abs(b + c) > abs(b - c):
                    # print('constructive',abs(b + c),' b,c ', abs(b - c), "b and c",b,"   ",c)
                    detector_num = 0
                    # print('constructive M,L',time)
                else:
                    # print('destructive',abs(b + c),' b,c ', abs(b - c), "b and c",b,"   ",c)
                    detector_num = 1
                    # print('destructive M,L',time)
            else:
                # time t+3T
                time = 3 * self.path_difference
                detector_num = self.get_generator().choice([0,1])
        # print(detector_num)
        process = Process( self._receivers[detector_num], "get",   [photon])
        event = Event(self.timeline.now() + time, process)
        self.timeline.schedule(event)





class DPSNode(Node):
    def __init__(self, name, timeline, seed=None, gate_fid = 1, meas_fid = 1):
        super().__init__(name, timeline, seed, gate_fid, meas_fid)
        self.source = LightSource(name = name+'light_source',
                                  timeline=tl,
                                  frequency=1e6,
                                  mean_photon_num=0.2,
                                  encoding_type=time_bin)
        self.aliceKey = ''
        self.bobKey = ''
        self.dpskeys = {}
        self.add_component(self.source)
        self.source.add_receiver(self)
        self.detectors = [CDetector(name + ".detector" + str(i), timeline) for i in range(2)]
        self.interferometer = CInterferometer(name + ".interferometer", timeline, time_bin["bin_separation"])
        self.interferometer.add_receiver(self.detectors[0])
        self.interferometer.add_receiver(self.detectors[1])
        self.timestamps = []
        self.comps = [self.interferometer] + self.detectors
        self.detectors[0].add_receiver(self)
        self.detectors[1].add_receiver(self)
        

    def get(self, photon,**kwargs):
        self.issent = True
        # print(self.qchannels[bob.name])
        # self.qchannels[bob.name].transmit(photon,self)
        self.protocols[0].sendQubit(photon)

    def send_qubit(self, dst, qubit):
        return super().send_qubit(dst, qubit)

    def photonDet(self,detector,time, **kwargs):
        for p in self.protocols:
            
            if hasattr(p, "pop"):
                p.pop(detector, time)

    def receive_qubit(self, src, qubit):
        self.interferometer.get(qubit)


    def propogate_key(self,msg):
        print(self.dpskeys)
        print(f"{self.name} is propogating key {msg.keyname} with xorKey {msg.xorKey}")
        self.dpskeys[msg.keyname] =''.join(str(int(a) ^ int(b)) for a, b in zip(msg.key, self.dpskeys[msg.xorKey]))

    def receive_message(self, src, msg):

        if msg.msg_type is DPSMsgType.KEY_PROPAGATION:
            self.propogate_key(msg)
            # print(f"{self.name} received key propogation message with key: {msg.key}, keyname: {msg.keyname}, xorKey: {msg.xorKey}")
        else:
            self.protocols[0].received_message(src, msg)
            print(f"{self.name} received message of type {msg.msg_type} with content: {msg.payload}") 


class Node3Net:
    def __init__(self,nodes:list[Node],tl,keysize=128):
        
        # self.alice = DPSNode(name1,tl)
        # self.bob = DPSNode(name2,tl)
        # self.charlie = DPSNode(name2,tl)
        self.nodes = nodes
        self.key_size = keysize
        self.timeline = tl
    
    def GetKey(self,node1:Node,node2:Node):
        self.alice_dps = DPS(node1,'dps1',node1.name+'light_source') 
        self.bob_dps = DPS(node2,'dps',node2.name+'light_source') 
        
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
            if i == 0:
                start_time = self.timeline.now()
                end_time = start_time + (int((self.key_size / node1.source.frequency) * 1e12))  # Run for a duration that allows key generation
                process = Process(self,"GetKey",[node1,node2])
                event = Event(start_time, process)
                self.timeline.schedule(event)
            else:
                start_time = end_time   # Schedule next round after the previous one finishes
                end_time = start_time + (int((self.key_size / node1.source.frequency) * 1e12))
                process = Process(self,"GetKey",[node1,node2])
                event = Event(start_time, process)
                self.timeline.schedule(event)
        print(end_time, "scheduled all key generation processes")
        start_time = end_time
        end_time = start_time +(int((self.key_size / node1.source.frequency) * 1e12))
        process = Process(self,"make_keys",[nodes])
        event = Event(end_time, process)
        self.timeline.schedule(event)
        process2 = Process(self,"propogate_Keys",[nodes])
        event2 = Event(end_time+ 20000, process2)
        self.timeline.schedule(event2)
    
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
        process = Process(self,"propagation1",[])
        event = Event(self.timeline.now()+delay_time, process)
        self.timeline.schedule(event)
        delay_time += 20000000
        process2 = Process(self,"propagation2",[])
        event2 = Event(self.timeline.now()+delay_time, process2)
        self.timeline.schedule(event2)
        delay_time += 20000000
        process3 = Process(self,"propagation3",[])
        event3 = Event(self.timeline.now()+delay_time, process3)
        self.timeline.schedule(event3)
       
    def propagation1(self):
        # first Propogation from Node1 to Node0 and Node2
        msg1 = nodes[1].dpskeys['K1']
        msg2 = nodes[1].dpskeys['K2']
        send_msg = ''.join(str(int(a) ^ int(b)) for a, b in zip(msg1, msg2))
        key_name = f'K{2}'
        nodes[1].send_message(nodes[0].name, DPSMessage(DPSMsgType.KEY_PROPAGATION,nodes[0].name,key = send_msg,keyname=key_name,xorKey='K1'))
        key_name = f'K{1}'
        nodes[1].send_message(nodes[2].name, DPSMessage(DPSMsgType.KEY_PROPAGATION,nodes[2].name,key = send_msg,keyname=key_name,xorKey='K2'))
    
    def propagation2(self):
        msg1 = nodes[2].dpskeys['K2']
        msg2 = nodes[2].dpskeys['K3']
        send_msg = ''.join(str(int(a) ^ int(b)) for a, b in zip(msg1, msg2))
        key_name = f'K{3}'
        nodes[2].send_message(nodes[1].name, DPSMessage(DPSMsgType.KEY_PROPAGATION,nodes[3].name,key = send_msg,keyname=key_name,xorKey='K2'))
        key_name = f'K{2}'
        nodes[2].send_message(nodes[3].name, DPSMessage(DPSMsgType.KEY_PROPAGATION,nodes[1].name,key = send_msg,keyname=key_name,xorKey='K3'))
    
    def propagation3(self):
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







def CreateNetwork(numberofnodes,tl):
    nodes = []
    for i in range(numberofnodes):
        node = DPSNode(f'Node{i}', tl)
        nodes.append(node)
    for i,node in enumerate(nodes):
        if i < numberofnodes - 1:
            qc = QuantumChannel(f'qc_{node.name}_{nodes[i+1].name}', tl, attenuation=0, distance=1000)
            qc.set_ends(node, nodes[i+1].name)
            cc1 = ClassicalChannel(f'cc_{node.name}_{nodes[i+1].name}', tl, 1000)
            cc2 = ClassicalChannel(f'cc_{nodes[i+1].name}_{node.name}', tl, 1000)
            cc1.set_ends(node, nodes[i+1].name)
            cc2.set_ends(nodes[i+1], node.name)

    return nodes




class DPSKeyMessage(Message):
    def __init__(self,msg_type,dst,key):
        super().__init__(msg_type,dst)
        self.key = key



nodes = CreateNetwork(4,tl)

sim3 = Node3Net(nodes,tl)

sim3.run()



     
tl.init()



tl.run()




for i,node in enumerate(nodes):
    print(f"{node.name}'s dps keys: {node.dpskeys}")

# for node in nodes:
#     print(f"{node.name}'s alice key: {node.aliceKey}")
#     print(f"{node.name}'s bob key  : {node.bobKey}")