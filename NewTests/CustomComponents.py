import time
import json

from sequence.kernel.timeline import Timeline
from NewTests.DPSprotocol import DPSMessage,DPSMsgType
from sequence.message import Message
from sequence.topology.node import Node,QKDNode,QSDetectorTimeBin,QuantumRouter
from sequence.protocol import StackProtocol
from sequence.components.detector import Detector,QSDetector
from sequence.components.interferometer import Interferometer
from sequence.components.photon import Photon
from sequence.components.light_source import LightSource
from sequence.components.optical_channel import QuantumChannel,ClassicalChannel
from sequence.components.detector import QSDetectorTimeBin
import numpy as np
from numpy import log, sqrt,multiply
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from sequence.topology.router_net_topo import RouterNetTopo
from sequence.topology.topology import Topology as Topo
from sequence.utils.encoding import time_bin
from sequence.utils.encoding import polarization, fock
from sequence.utils import log

class CLightSource(LightSource):
    def __init__(self, name, timeline, frequency=8e7, wavelength=1550, bandwidth=0, mean_photon_num=0.1,
                 encoding_type=polarization, phase_error=1):
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

                error = self.get_generator().choice([0, 1, 2])

                if error == 0:
                    state = multiply([1, -1, 1], state)

                elif error == 1:
                    state = multiply([1, 1, -1], state)

                else:
                    state = multiply([1, -1, -1], state)
            # print("state after error:", state)
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
    def __init__(self, name, timeline, seed=None, ):
        super().__init__(name, timeline, seed=seed,)
        self.source = CLightSource(name = name+'light_source',
                                timeline=timeline,
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
        self.counter = 0

    def init(self):
        pass
        

    def get(self, photon,**kwargs):
        self.issent = True
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
            elif p.name == "dps":
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

    def receive_message(self, src, msg):

        if msg.msg_type is DPSMsgType.KEY_PROPAGATION:
            self.propogate_key(msg)
            # print(f"{self.name} received key propogation message with key: {msg.key}, keyname: {msg.keyname}, xorKey: {msg.xorKey}")
        else:
            self.protocols[0].received_message(src, msg)
            # print(f"{self.name} received message of type {msg.msg_type} with content: {msg.payload}")