from sequence.kernel.timeline import Timeline

from sequence.topology.node import Node
from sequence.components.switch import Switch
from sequence.components.detector import Detector,QSDetector
from sequence.components.interferometer import Interferometer
from sequence.components.photon import Photon
from sequence.components.light_source import LightSource
from sequence.components.optical_channel import QuantumChannel
from sequence.components.detector import QSDetectorTimeBin
from sequence.components.beam_splitter import BeamSplitter
from sequence.components.mirror import Mirror
import numpy as np
from numpy import sqrt
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from sequence.utils.encoding import time_bin


rng = np.random.default_rng()
tl = Timeline()

class Alice(Node):
    def __init__(self, name, timeline, seed=None, gate_fid = 1, meas_fid = 1):
        super().__init__(name, timeline, seed, gate_fid, meas_fid)
    
        newPhoton = Photon('alice',self.timeline,quantum_state=(complex(sqrt(1/2)),complex(sqrt(1/2))))
        process = Process(self,'get',[newPhoton])
        event = Event(self.timeline.now(),process)
        self.timeline.schedule(event)
        # newPhoton2 = Photon('alice2',self.timeline,quantum_state=(complex(0),complex(1)))
        # process2 = Process(self,'get',[newPhoton2])
        # event2 = Event(self.timeline.now()+200,process2)
        # self.timeline.schedule(event2)
        newPhotonst = newPhoton.quantum_state.state[0] - newPhoton.quantum_state.state[1]
        print(newPhoton.quantum_state.measure(time_bin['bases'][0],rng))
        print(newPhoton.quantum_state.state[0] - newPhoton.quantum_state.state[1])
    def get(self, photon, **kwargs):
        self.issent = True
        # print("get method called")
        # print(self.qchannels)
        self.qchannels[bob.name].transmit(photon,self)


class Bob(Node):
    def __init__(self, name, timeline, seed=None, gate_fid = 1, meas_fid = 1):
        super().__init__(name, timeline, seed, gate_fid, meas_fid)

        self.bs1 = BeamSplitter('bs1',tl,1)
        self.bs2 = BeamSplitter('bs2',tl,1)
        self.mr1 = Mirror('mr1',tl,1,self.name)
        # self.mr2 = Mirror('mr2',tl,1,self.name)
        self.det0 = Detector('det0',tl,1)
        self.det1 = Detector('det1',tl,1)
        self.add_component(self.bs1)
        self.add_component(self.bs2)
        self.add_component(self.mr1)
        # self.add_component(self.mr2)

        self.bs1.add_receiver(self.mr1)
        self.bs1.add_receiver(self.bs2)
        self.bs2.add_receiver(self.det0)
        self.bs2.add_receiver(self.det1)
        self.bs1.set_basis_list([0],self.timeline.now(),0)
        self.bs2.set_basis_list([0],self.timeline.now(),0)
        self.set_first_component(self.bs1.name)


    def receive_qubit(self, src, qubit):
        # return super().receive_qubit(src, qubit)
        print('recieved from ',src)
        if src == 'bob':
            self.components[self.bs2.name].get(qubit)
        else:
            self.components[self.first_component_name].get(qubit)
    


alice = Alice("alice",tl)
bob = Bob("bob",tl)

channel = QuantumChannel(
    name='qc',
    timeline=tl,
    attenuation=0,
    distance=1000
)
channel2 = QuantumChannel(
    name='qc2',
    timeline=tl,
    attenuation=0,
    distance=1000
)

channel2.set_ends(bob,bob.name)

channel.set_ends(alice,bob.name)


tl.init()

tl.run()