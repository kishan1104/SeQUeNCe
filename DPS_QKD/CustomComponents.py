
import json


from DPS_QKD.DPSprotocol import DPS, DPSMsgType
from sequence.message import Message
from sequence.topology.node import QKDNode
from sequence.qkd.cascade import Cascade
from sequence.components.detector import Detector
from sequence.components.interferometer import Interferometer
from sequence.components.photon import Photon
from sequence.components.light_source import LightSource
import numpy as np
from numpy import log,multiply, sqrt
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from sequence.topology.router_net_topo import RouterNetTopo
from sequence.topology.topology import Topology as Topo
from sequence.utils.encoding import time_bin
from sequence.utils.encoding import polarization
from sequence.utils import log
from sequence.constants import SPEED_OF_LIGHT
from sympy import sqrt,pi, cos, sin


def createState(phases=None):
    if phases is not None:
        state = [complex(sqrt(1/3))]
        for ph in phases[1:]:
            state.append(ph * complex(sqrt(1/3)))
        return tuple(state), phases
    


class CLightSource(LightSource):
    def __init__(self, name, timeline, frequency=8e7, wavelength=1550, bandwidth=0, mean_photon_num=0.1,
                 encoding_type=polarization, phase_error=0.2):
        super().__init__(name, timeline, frequency, wavelength, bandwidth, mean_photon_num, encoding_type, phase_error)
    

    def emit(self, state_list):
        """Method to emit photons.

    Will emit photons for a length of time determined by the `state_list` parameter.
    The number of photons emitted per period is calculated as a poisson random variable.

    Arguments:
        state_list (list[list[complex]]): list of complex coefficient arrays to send as photon-encoded qubits.
    """

        log.logger.info(f"{self.name} emitting {len(state_list)} photons")

        time = self.timeline.now()
        period = int(round(1e12 / self.frequency))
        # print("period:", period)
        for i, state in enumerate(state_list):
            num_photons = self.get_generator().poisson(self.mean_photon_num)
            # print("state before error:", state)

            
            if self.get_generator().random() < self.phase_error:
                state = multiply([1, -1, 1], state)


            for _ in range(num_photons):
                wavelength = self.linewidth * self.get_generator().standard_normal() + self.wavelength
                new_photon = Photon(str(i), self.timeline,
                                    wavelength=wavelength,
                                    location=self.owner,
                                    encoding_type=self.encoding_type,
                                    quantum_state=tuple(state))
                process = Process(self._receivers[0], "get", [new_photon])
                event = Event(time, process)
                self.timeline.schedule(event)
                self.photon_counter += 1

        time += period

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

class DPSNode(QKDNode):
    def __init__(self, name, timeline, seed=None, stack_size = 5):
        super().__init__(name, timeline, seed=seed,stack_size=stack_size)
        source = CLightSource(name = name+'.light_source',
                                timeline=timeline,
                                frequency=1e6,
                                mean_photon_num=0.2,
                                encoding_type=time_bin)
        self.aliceKey = ''
        self.bobKey = ''
        self.eveKey = ''
        self.dpskeys = {}
        self.add_component(source)
        source.add_receiver(self)
        self.detectors = [CDetector(name + ".detector" + str(i), timeline) for i in range(2)]
        self.interferometer = CInterferometer(name + ".interferometer", timeline, time_bin["bin_separation"])
        self.interferometer.add_receiver(self.detectors[0])
        self.interferometer.add_receiver(self.detectors[1])
        self.add_component(self.interferometer)
        self.timestamps = []
        self.comps = [self.interferometer] + self.detectors
        self.detectors[0].add_receiver(self)
        self.detectors[1].add_receiver(self)
        self.counter = 0
        ls_name = name + ".light_source"
        if stack_size > 0:
            # print('this is run')
            self.protocols = []
            self.protocol_stack[0] = DPS(self, name + ".DPS", ls_name)
            self.protocols.append(self.protocol_stack[0])
        if stack_size > 1:
            # Create cascade protocol
            self.protocol_stack[1] = Cascade(self, name + ".cascade")
            self.protocols.append(self.protocol_stack[1])
            self.protocol_stack[0].upper_protocols.append(self.protocol_stack[1])
            self.protocol_stack[1].lower_protocols.append(self.protocol_stack[0])

    def init(self):
        pass
        

    def get(self, photon,**kwargs):
        self.issent = True
        # print(self.protocols)
        # print(self.qchannels[bob.name])
        # self.qchannels[bob.name].transmit(photon,self)
        # print(f"{self.name} is sending a qubit at time {self.timeline.now()} with state {photon.quantum_state.state}")
        self.protocols[0].sendQubit(photon)

    def send_qubit(self, dst, qubit):
        return super().send_qubit(dst, qubit)

    def photonDet(self,detector,time, **kwargs):
        # print(self.counter)
        self.counter += 1
        for p in self.protocols:
            if p == "BB84":
                print("BB84 protocol not yet implemented for QKDNode; skipping photon detection handling.")
            elif p.name == self.name+".DPS":
                if hasattr(p, "pop"):
                    p.pop(detector, time)
            # if hasattr(p, "pop"):
            #     p.pop(detector, time)
            else:
                # print(f"Unknown protocol {p.name} at node {self.name}; cannot handle photon detection.")
                pass

    def receive_qubit(self, src, qubit):
        self.interferometer.get(qubit)


    def propogate_key(self,msg):
        # print(self.dpskeys)
        # print(f"{self.name} is propogating key {msg.keyname} with xorKey {msg.xorKey}")
        self.dpskeys[msg.keyname] =''.join(str(int(a) ^ int(b)) for a, b in zip(msg.key, self.dpskeys[msg.xorKey]))

    def receive_message(self, src: str, msg: "Message") -> None:
        # signal to protocol that we've received a message
        for protocol in self.protocols:
            print('message i')
            if getattr(protocol, "protocol_type", None) or type(protocol) == msg.protocol_type:
                protocol.received_message(src, msg)
                return

        # if we reach here, we didn't successfully receive the message in any protocol
        print(self.protocols)
        raise Exception(f"Message received for unknown protocol '{msg.protocol_type}' on node {self.name}")




class EveDPSNode(QKDNode):
    def __init__(self, name, timeline, attack='', seed=None, ):
        super().__init__(name, timeline, seed=seed,)
        source = CLightSource(name = name+'light_source',
                                timeline=timeline,
                                frequency=1e6,
                                mean_photon_num=0.2,
                                encoding_type=time_bin)
        self.aliceKey = ''
        self.bobKey = ''
        self.eveKey = []
        self.dpskeys = {}
        self.add_component(source)
        source.add_receiver(self)
        self.detectors = [CDetector(name + ".detector" + str(i), timeline) for i in range(2)]
        self.interferometer = CInterferometer(name + ".interferometer", timeline, time_bin["bin_separation"])
        self.interferometer.add_receiver(self.detectors[0])
        self.interferometer.add_receiver(self.detectors[1])
        self.timestamps = []
        self.comps = [self.interferometer] + self.detectors
        self.detectors[0].add_receiver(self)
        self.detectors[1].add_receiver(self)
        self.counter = 0
        self.path_difference = time_bin["bin_separation"]
        self.attack = attack

    def init(self):
        pass
        

    def get(self, photon,**kwargs):
        self.issent = True
        # print(self.qchannels[bob.name])
        # self.qchannels[bob.name].transmit(photon,self)
        # print(f"{self.name} is sending a qubit at time {self.timeline.now()} with state {photon.quantum_state.state}")
        self.protocols[0].sendQubit(photon)

    def receive_qubit(self, src, qubit):
        if self.attack == '':
            self.send_to_Protocol(qubit)
            return
        elif self.attack == 'IR':


            state = qubit.quantum_state.state
            bit, time, slot = self.measure_state(state)
            self.eveKey.append((bit, time,))
            resend_state = self.make_resend_state(bit,slot)
            # print(detector,time, "Eve detected a photon!")
            photon = Photon(str(self.counter), self.timeline, encoding_type=time_bin, quantum_state=resend_state)
            self.send_to_Protocol(photon)
            return
        elif self.attack == 'PNS':
            r = self.get_generator().random()
            if r < 1:
                state = qubit.quantum_state.state
                bit,time,slot = self.measure_state(state)
                self.eveKey.append((bit,time))
            
            self.send_to_Protocol(qubit)

    def send_to_Protocol(self,photon):
        for p in self.protocols:
            # print("protocol:", p.name)
            if p == "BB84":
                print("BB84 protocol not yet implemented for QKDNode; skipping photon detection handling.")
            elif p.name == self.name+".DPS":
                if hasattr(p, "sendEveQubit"):
                    p.sendEveQubit(photon)
            # if hasattr(p, "pop"):
            #     p.pop(detector, time)
            else:
                # print("unknown protocol")
                # print(f"Unknown protocol {p.name} at node {self.name}; cannot handle photon detection.")
                pass

    def measure_state(self, state):

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
                slot = 0

            elif r < 0.5:
                # -------- first interference (E,M) --------
                time = self.path_difference
                slot = 1
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
                slot = 2
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
                slot = 3
                time = 3 * self.path_difference
                detector_num = self.get_generator().choice([0,1])

            return int(detector_num), time+self.timeline.now(),slot
        
    def createState(self,phases=None):
        if phases is not None:
            state = [complex(sqrt(1/3))]
            for ph in phases[1:]:
                state.append(ph * complex(sqrt(1/3)))
            return tuple(state)
        
        state = [complex(sqrt(1/3))]
        sentstate = []
        phases = [1]
        for ph in range(2):
            phvalue = np.random.choice([1,-1])   
            state.append(phvalue * complex(sqrt(1/3)))
            sentstate.append((phvalue))
            phases.append(phvalue)
        # self.phase_list.append(phases)
        if np.random.random() <= 0:
                chosen = np.random.choice([1,2])
                r = np.random.random()
                if r < 0.5:
                    delta = np.random.uniform(0, pi/4)
                elif r < 0.75:
                    delta = np.random.uniform(0, pi/2)
                else:
                    delta = np.random.uniform(0,pi)
                state[chosen] = state[chosen] * (cos(delta) + 1j*sin(delta))
        return tuple(state)
    

    def make_resend_state(self, bit,slot):

        amp = np.sqrt(1/3)
        choice = self.get_generator().choice([0,1])
        if slot == 1:

            if bit == 0:
                
                if choice == 0:
                    return (
                        amp,
                        amp,
                        amp
                    )
                else:
                    return (
                        amp,
                        amp,
                        -amp
                    )
            else:
                if choice == 0:
                    return (
                        amp,
                        -amp,
                        amp
                    )
                else:
                    return (
                        amp,
                        -amp,
                        -amp
                    )


        elif slot == 2:

            if bit == 0:
                if choice == 0:
                    return (
                        amp,
                        amp,
                        amp
                    )
                else:
                    return (
                        amp,
                        -amp,
                        -amp
                    )
            else:
                if choice == 0:
                    return (
                        amp,
                        -amp,
                        amp
                    )
                else:
                    return (
                        amp,
                        amp,
                        -amp
                    )
        else:
            return self.createState()

    def send_qubit(self, dst, qubit):
        # print(f"{self.name} is sending a qubit at time {self.timeline.now()} with state {qubit.quantum_state.state}")
        return super().send_qubit(dst, qubit)

    def photonDet(self,detector,time, **kwargs):
        # print(self.counter)
        self.counter += 1
        # for p in self.protocols:
        #     if p == "BB84":
        #         print("BB84 protocol not yet implemented for QKDNode; skipping photon detection handling.")
        #     elif p.name == "dps":
        #         if hasattr(p, "pop"):
        #             p.pop(detector, time)
        #     # if hasattr(p, "pop"):
        #     #     p.pop(detector, time)
        #     else:
        #         # print(f"Unknown protocol {p.name} at node {self.name}; cannot handle photon detection.")
        #         pass
        self.eveKey.append((detector, time))
        resend_state = self.make_resend_state(detector)
        # print(detector,time, "Eve detected a photon!")
        photon = Photon(str(self.counter), self.timeline, encoding_type=time_bin, quantum_state=resend_state)
        # 

        for p in self.protocols:
            # print("protocol:", p.name)
            if p == "BB84":
                print("BB84 protocol not yet implemented for QKDNode; skipping photon detection handling.")
            elif p.name == self.name + ".DPS":
                if hasattr(p, "sendEveQubit"):
                    p.sendEveQubit(photon)
            # if hasattr(p, "pop"):
            #     p.pop(detector, time)
            else:
                # print("unknown protocol")
                # print(f"Unknown protocol {p.name} at node {self.name}; cannot handle photon detection.")
                pass


    # def propogate_key(self,msg):
    #     # print(self.dpskeys)
    #     # print(f"{self.name} is propogating key {msg.keyname} with xorKey {msg.xorKey}")
    #     self.dpskeys[msg.keyname] =''.join(str(int(a) ^ int(b)) for a, b in zip(msg.key, self.dpskeys[msg.xorKey]))

    # def receive_message(self, src, msg):

    #     if msg.msg_type is DPSMsgType.KEY_PROPAGATION:
    #         self.propogate_key(msg)
    #         # print(f"{self.name} received key propogation message with key: {msg.key}, keyname: {msg.keyname}, xorKey: {msg.xorKey}")
    #     else:
    #         self.protocols[0].received_message(src, msg)
    #         # print(f"{self.name} received message of type {msg.msg_type} with content: {msg.payload}")



class DPSKeyMessage(Message):
    def __init__(self,msg_type,dst,key):
        super().__init__(msg_type,dst)
        self.key = key

class ExtRouterNetTopo(RouterNetTopo):


    DPS_NODE = "DPSNode"

    def __init__(self, conf_file_name: str):
        super().__init__(conf_file_name)
    
    def _load(self,filename: str):
        with open(filename)as fh:
            config = json.load(fh)
        self._get_templates(config)
        # self.tl = Timeline()
        self._add_timeline(config=config)
        self._add_nodes(config)
        self._add_qconnections(config)
        self._add_qchannels(config)
        self._add_cchannels(config)
        self._add_cconnections(config)
        self._generate_forwarding_table(config)

    def _add_nodes(self, config: dict):
        for node in config[Topo.ALL_NODE]:
            seed = node[Topo.SEED]
            node_type = node[Topo.TYPE]
            name = node[Topo.NAME]
            template_name = node.get(Topo.TEMPLATE, None)
            template = self.templates.get(template_name, {})
            if node_type == self.DPS_NODE:
                node_obj = DPSNode(name, self.tl, seed=seed, **template)
            # elif node_type == self.BSM_NODE:
            #     node_obj = DPSNode(name, self.tl, seed=seed, **template)
            else:
                raise ValueError(f"Unknown type of node '{node_type}'")

            node_obj.set_seed(seed)
            self.nodes[node_type].append(node_obj)
    def _add_qconnections(self, config):
        for q_connect in config.get(Topo.ALL_Q_CONNECT,[]):
            node1 = q_connect[Topo.CONNECT_NODE_1]
            node2 = q_connect[Topo.CONNECT_NODE_2]
            attenuation = q_connect[Topo.ATTENUATION]
            distance = q_connect[Topo.DISTANCE]
            channel_type = q_connect[Topo.TYPE]
            cc_delay = []
            for cc in config.get(self.ALL_C_CHANNEL, []):   # classical channel
                if cc[self.SRC] == node1 and cc[self.DST] == node2:
                    delay = cc.get(self.DELAY, cc.get(self.DISTANCE, 1000) / SPEED_OF_LIGHT)
                    cc_delay.append(delay)
                elif cc[self.SRC] == node2 and cc[self.DST] == node1:
                    delay = cc.get(self.DELAY, cc.get(self.DISTANCE, 1000) / SPEED_OF_LIGHT)
                    cc_delay.append(delay)

            for cc in config.get(self.ALL_C_CONNECT, []):  # classical connection
                if (cc[self.CONNECT_NODE_1] == node1 and cc[self.CONNECT_NODE_2] == node2) \
                        or (cc[self.CONNECT_NODE_1] == node2 and cc[self.CONNECT_NODE_2] == node1):
                    delay = cc.get(self.DELAY, cc.get(self.DISTANCE, 1000) / SPEED_OF_LIGHT)
                    cc_delay.append(delay)
            if len(cc_delay) == 0:
                assert 0, q_connect
            cc_delay = int(np.mean(cc_delay) // 2)

            if channel_type == "quantum":
                for src in [node1, node2]:
                    # print("node1:", node1, "node2:", node2, "attenuation:", attenuation, "distance:", distance, "cc_delay:", cc_delay,src)
                    if src ==node1:
                        dst = node2
                    else:
                        dst = node1
                    
                    qc_name = f"QC-{src}-{dst}"  # the quantum channel
                    qc_info = {self.NAME: qc_name,
                               self.SRC: src,
                               self.DST: dst,
                               self.DISTANCE: distance,
                               self.ATTENUATION: attenuation}
                    if self.ALL_Q_CHANNEL not in config:
                        config[self.ALL_Q_CHANNEL] = []
                    config[self.ALL_Q_CHANNEL].append(qc_info)

                    cc_name = f"CC-{src}-{dst}"  # the classical channel
                    cc_info = {self.NAME: cc_name,
                               self.SRC: src,
                               self.DST: dst,
                               self.DISTANCE: distance,
                               self.DELAY: cc_delay}
                    if self.ALL_C_CHANNEL not in config:
                        config[self.ALL_C_CHANNEL] = []
                    config[self.ALL_C_CHANNEL].append(cc_info)
