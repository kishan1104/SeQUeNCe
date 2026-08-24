from sequence.kernel.timeline import Timeline
from sequence.topology.node import Node
from sequence.components.memory import Memory
from sequence.components.detector import Detector
from sequence.components.optical_channel import QuantumChannel

class SenderNode(Node):
    def __init__(self, name, timeline):
        super().__init__(name, timeline)
        
        memory_name = name + ".memory"
        memory = Memory(memory_name, timeline, fidelity=1, frequency=0,
                        efficiency=1, coherence_time=0, wavelength=500)
        self.add_component(memory)
        memory.add_receiver(self)

    def get(self, photon, **kwargs):
        print('sending qubit')
        self.send_qubit(kwargs['dst'], photon)

class ReceiverNode(Node):
    def __init__(self, name, timeline):
        super().__init__(name, timeline)

        detector_name = name + ".detector"
        detector = Detector(detector_name, timeline, efficiency=1)
        self.add_component(detector)
        self.set_first_component(detector_name)
        detector.owner = self

    def receive_qubit(self, src, qubit):
        self.components[self.first_component_name].get(qubit)


tl = Timeline(10e12)
node1 = SenderNode("node1", tl)
node2 = ReceiverNode("node2", tl)
node1.set_seed(0)
node2.set_seed(1)
qc = QuantumChannel("qc", tl, attenuation=0, distance=1e3)
qc.set_ends(node1, node2.name)
memories = node1.get_components_by_type(Memory)
memory = memories[0]
memory.update_state([complex(0), complex(1)])

from sequence.kernel.process import Process
from sequence.kernel.event import Event

process = Process(memory, "excite", ["node2"])
event = Event(0, process)
tl.schedule(event)
tl.init()
tl.run()