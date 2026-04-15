import time

from sequence.kernel.timeline import Timeline

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

pi  = np.pi

class CDetector(Detector):
    def __init__(self, name, timeline, efficiency = 1, dark_count = 0, count_rate = 25000000, time_resolution = 150):
        super().__init__(name, timeline, efficiency, dark_count, count_rate, time_resolution)
    
    def get(self,photon=None, **kwargs):
        self.photon_counter +=1
        
        if self.get_generator().random() < self.efficiency:

            self.record_detection()
            self._receivers[0].get(self.name, self.timeline.now())
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



class Alice(Node):
    def __init__(self, name, timeline, seed=None, gate_fid = 1, meas_fid = 1):
        super().__init__(name, timeline, seed, gate_fid, meas_fid)

        self.source = LightSource(name = 'light_source',
                                  timeline=tl,
                                  frequency=1e6,
                                  mean_photon_num=0.2,
                                  encoding_type=time_bin)
        self.aliceKey = ''
        self.add_component(self.source)
        self.source.add_receiver(self)

    def get(self, photon, **kwargs):
        self.issent = True
        self.qchannels[bob.name].transmit(photon,self)
        

    




class Bob(Node):
    def __init__(self, name, timeline, seed=None, gate_fid = 1, meas_fid = 1):
        super().__init__(name, timeline, seed, gate_fid, meas_fid)
        self.detectors = [CDetector(name + ".detector" + str(i), timeline) for i in range(2)]
        self.interferometer = CInterferometer(name + ".interferometer", timeline, time_bin["bin_separation"])
        self.interferometer.add_receiver(self.detectors[0])
        self.interferometer.add_receiver(self.detectors[1])
        self.timestamps = []
        self.components = [self.interferometer] + self.detectors
        self.detectors[0].add_receiver(self)
        self.detectors[1].add_receiver(self)


    

    def get(self,detector,time, **kwargs):
        for p in self.protocols:
            
            if hasattr(p, "pop"):
                p.pop(detector, time)

    def receive_qubit(self, src, qubit):
        self.interferometer.get(qubit)
        
alice = Alice("Alice",tl)
bob = Bob("Bob",tl)

channel = QuantumChannel(
    name='qc',
    timeline=tl,
    attenuation=0,
    distance=0
)

channel.set_ends(alice,bob.name)

cca_b = ClassicalChannel('cc',tl,1000)
ccb_a = ClassicalChannel('cc2',tl,1000)
cca_b.set_ends(bob,alice.name)
ccb_a.set_ends(alice,bob.name)


alice_dps = DPS(alice,"dps","light_source")
bob_dps   = DPS(bob,"dps","light_source")

pair_dps_protocols(alice_dps,bob_dps)

alice.protocols.append(alice_dps)
bob.protocols.append(bob_dps)


alice_dps.push(128)

     
tl.init()

tl.run()

