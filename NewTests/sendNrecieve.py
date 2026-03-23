from sequence.kernel.timeline import Timeline

from sequence.topology.node import Node
from sequence.components.photon import Photon
from sequence.components.light_source import LightSource
from sequence.components.optical_channel import QuantumChannel
from sequence.components.detector import Detector
import numpy as np
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from math import sqrt
# --------------------------------------------------
# 1️⃣ Create Timeline (Discrete Event Engine)
# --------------------------------------------------
timeline = Timeline()


class Emitter(Node):
    def __init__(self, name, timeline, seed=None, gate_fid = 1, meas_fid = 1):
        super().__init__(name, timeline, seed, gate_fid, meas_fid)
        self.source = LightSource(
                name="photon_source",
                timeline=timeline,
                frequency=1e6,  # 1 MHz emission rate
                mean_photon_num=0.2
            )
        self.counter = 0
        self.add_component(self.source)
        self.source.add_receiver(self)
        self.source.emit([(complex(1),complex(0)),(complex(sqrt(1/2)),complex(sqrt(1/2)))])

    def Counter(self):
        self.counter +=1
    def get(self, photon, **kwargs):
        self.Counter()
        self.qchannels[node2.name].transmit(photon,self)

class DetectorNode(Node):
    def __init__(self, name, timeline, seed=None, gate_fid = 1, meas_fid = 1):
        super().__init__(name, timeline, seed, gate_fid, meas_fid)
        self.detector = Detector(
                name="detector",
                timeline=timeline,
                efficiency=0.5
            )
        self.add_component(self.detector)
        self.set_first_component(self.detector.name)
        self.detector.owner = self
        self.counter = 0

    def Counter(self):
        self.counter +=1

    def receive_qubit(self, src, qubit):
        self.counter +=1
        # print('qubit recieved')
        return super().receive_qubit(src, qubit)
    # def get(self, photon, **kwargs):
    #     # return super().get(photon, **kwargs)
        
    #     print('detector get is called')
node1 = Emitter("EmitterNode", timeline)
node2 = DetectorNode("DetectorNode", timeline)


channel = QuantumChannel(
    name="qchannel",
    timeline=timeline,
    attenuation=0,      # dB/km
    distance=1000         # 1 km
)

channel.set_ends(node1, node2.name)



timeline.init()
timeline.run()


print(node1.counter)
# print(node2.counter)
print("Simulation finished")



