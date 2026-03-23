from sequence.kernel.timeline import Timeline

from sequence.topology.node import Node
from sequence.components.photon import Photon
from sequence.components.light_source import LightSource
from sequence.components.optical_channel import QuantumChannel
from sequence.components.detector import Detector
import numpy as np
from sequence.kernel.process import Process
from sequence.kernel.event import Event



tl = Timeline()

class Alice(Node):
    def __init__(self, name, timeline, seed=None, gate_fid = 1, meas_fid = 1):
        super().__init__(name, timeline, seed, gate_fid, meas_fid)
    
    def get(self, photon, **kwargs):
        self.send_qubit(kwargs['dst'],photon)
    
    



class Bob(Node):
    def __init__(self, name, timeline, seed=None, gate_fid = 1, meas_fid = 1):
        super().__init__(name, timeline, seed, gate_fid, meas_fid)

        pass
        
        detector = Detector(
            name="detectorOne",
            timeline=tl,
            efficiency=1
        )

        self.add_component(detector)

    def receive_qubit(self, src, qubit):
        pass



# b = Bob("bob",tl)

numpulse = round(1 * 10)

from sequence.utils.encoding import polarization

basislist = np.random.choice([0,1],numpulse)
bitlist = np.random.choice([0,1],numpulse)
print(basislist)
print(bitlist)
print('----------------')

print((polarization['bases'][basislist[0]])[bitlist[0]])
