from sequence.kernel.timeline import Timeline

from sequence.topology.node import Node
from sequence.components.switch import Switch
from sequence.components.detector import Detector,QSDetector
from sequence.components.interferometer import Interferometer
from sequence.components.photon import Photon
from sequence.components.light_source import LightSource
from sequence.components.optical_channel import QuantumChannel
from sequence.components.detector import QSDetectorTimeBin
import numpy as np
from numpy import sqrt
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from sequence.utils.encoding import time_bin


tl = Timeline()

pi  = np.pi

class CDetector(Detector):
    def __init__(self, name, timeline, efficiency = 0.9, dark_count = 0, count_rate = 25000000, time_resolution = 150):
        super().__init__(name, timeline, efficiency, dark_count, count_rate, time_resolution)
    
    def get(self,photon=None, **kwargs):
        self.photon_counter +=1
        
        if self.get_generator().random() < self.efficiency:

            self.record_detection()
            print(self.timeline.now(),self.name)
            return self.timeline.now()
            # measurement = photon.measure(((complex(sqrt(1 / 2)), complex(sqrt(1 / 2))), (complex(sqrt(1 / 2)), complex(-sqrt(1 / 2)))),photon,np.random)
            # return measurement
        else:
            print(f'Photon loss in detector {self.name}')

class CInterferometer(Interferometer):
    def __init__(self, name, timeline, path_diff, phase_error=0):
        super().__init__(name, timeline, path_diff, phase_error)
    
    def get(self,photon:"Photon",**kwargs):
        assert photon.encoding_type["name"] == "time_bin", \
            "Invalid photon encoding {} received by interferometer".format(photon.encoding_type["name"])
        if photon.use_qm:
            raise NotImplementedError("Interferometer usage not configured for quantum manager.")



class CQSDetector(QSDetectorTimeBin):
    def __init__(self, name, timeline):
        # super().__init__(name,timeline)
        QSDetector.__init__(self, name, timeline)
        self.detectors = [CDetector(name + ".detector" + str(i), timeline) for i in range(3)]
        self.interferometer = Interferometer(name + ".interferometer", timeline, time_bin["bin_separation"])
        self.interferometer.add_receiver(self.detectors[0])
        self.interferometer.add_receiver(self.detectors[1])
        self.add_receiver(self.detectors[2])
        self.timestamps = []
        self.components = [self.interferometer] + self.detectors
        self.trigger_times = [[], [], []]
    def get(self,photon,**kwargs):
        # print("sending to interferometer")
        self.timestamps.append(self.timeline.now())
        # self.interferometer.get(photon)
        return self.timeline.now()




class Alice(Node):
    def __init__(self, name, timeline, seed=None, gate_fid = 1, meas_fid = 1):
        super().__init__(name, timeline, seed, gate_fid, meas_fid)

        # self.source = LightSource(name = 'photon_Source',
        #                           timeline=tl,
        #                           frequency=1e6,
        #                           mean_photon_num=0.8,
        #                           encoding_type=time_bin)
        
        # self.add_component(self.source)
        # self.source.add_receiver(self)
        # self.source.emit([(complex(1),complex(0))])
        # print(self.qchannels)
        # self.source.emit([(complex(0),complex(1))])
        self.timesent = []
        self.emitPluse()
        
    
    def emitPluse(self,phase=[1,1,0,0,1,0,1,0,0,0]):

        phase_0 = (complex(sqrt(1/2)),complex(sqrt(1/2)))
        phase_pi = (complex(sqrt(1/2)),-complex(sqrt(1/2)))
        time = self.timeline.now()
        for i in range(len(phase)):
            if phase[i] == 0:
                new_photon = Photon(str(i),self.timeline,encoding_type=time_bin,quantum_state=phase_0)
            else:
                new_photon = Photon(str(i),self.timeline,encoding_type=time_bin,quantum_state=phase_pi)
            
            process = Process(self,'get',[new_photon])
            # print(time)
            event = Event(time,process)
            self.timeline.schedule(event)
            self.timesent.append((time,phase[i]))
            time = time + 1400
            
        # new_photon = Photon('photon', self.timeline,encoding_type=time_bin,quantum_state=stateEarly)
        # newp2 = Photon('photon2', self.timeline,encoding_type=time_bin,quantum_state=stateLate)
          
        # process2 = Process(self,'get',[newp2])  
        # self.get(new_photon)
        
        # event2 = Event(tl.now(),process2)
        
        # self.timeline.schedule(event2)

    def get(self, photon, **kwargs):
        self.issent = True
        # print("get method called")
        # print(self.qchannels)
        self.qchannels[bob.name].transmit(photon,self)

    




class Bob(Node):
    def __init__(self, name, timeline, seed=None, gate_fid = 1, meas_fid = 1):
        super().__init__(name, timeline, seed, gate_fid, meas_fid)
    
        self.detector0 = CQSDetector(name='detector',timeline=tl)
        self.add_component(self.detector0)
        self.set_first_component(self.detector0.name)
        self.detector0.owner = self
        self.timestamps = []
    def receive_qubit(self, src, qubit):
        # print("Qubit Recieved")
        measure = self.components[self.first_component_name].get(qubit)
        self.timestamps.append(measure)



alice = Alice("Alice",tl)
bob = Bob("Bob",tl)

channel = QuantumChannel(
    name='qc',
    timeline=tl,
    attenuation=0,
    distance=1000
)

channel.set_ends(alice,bob.name)

phase = 0
# emitprocess = Process(Alice,'emitPluse',[alice,phase])



tl.init()
# emit_event = Event(88,emitprocess)
# tl.schedule(emit_event)
# alice.emitPluse(0)
tl.run()

print(alice.timesent)
print(bob.timestamps)

# state = (complex(1/np.sqrt(2)),complex(1/np.sqrt(2)))

# photon = Photon('name',tl,0,None,time_bin,state,False)

# detector = QSDetectorTimeBin('detector',tl)

# detector.get(photon)


# measurement = photon.measure(((complex(sqrt(1 / 2)), complex(sqrt(1 / 2))), (complex(sqrt(1 / 2)), complex(-sqrt(1 / 2)))),photon,np.random)

# print(measurement)