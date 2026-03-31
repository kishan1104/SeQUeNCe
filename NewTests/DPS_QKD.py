from sequence.kernel.timeline import Timeline

from sequence.topology.node import Node
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


tl = Timeline()

pi  = np.pi

class CDetector(Detector):
    def __init__(self, name, timeline, efficiency = 0.9, dark_count = 0, count_rate = 25000000, time_resolution = 150):
        super().__init__(name, timeline, efficiency, dark_count, count_rate, time_resolution)
    
    def get(self,photon=None, **kwargs):
        self.photon_counter +=1
        
        if self.get_generator().random() < self.efficiency:

            self.record_detection()
            self._receivers[0].getkey(photon,self.timeline.now())
            
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
        state = photon.quantum_state.state

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
                    detector_num = 0
                else:
                    # print('destructive',time)
                    detector_num = 1

            elif r < 1 - p_late:
                # -------- second interference (M,L) --------
                time = 2 * self.path_difference

                if abs(b + c) > abs(b - c):
                    detector_num = 0
                    # print('constructive M,L',time)
                else:
                    detector_num = 1
                    # print('destructive M,L',time)
            else:
                # time t+3T
                time = 3 * self.path_difference
                detector_num = self.get_generator().choice([0,1])

        process = Process(self._receivers[detector_num], "get", [detector_num])
        event = Event(self.timeline.now() + time, process)
        self.timeline.schedule(event)



class DPSProtocol(StackProtocol):

    def __init__(self, owner:Node, name:str,lightsource:str,interferometer:str,role = -1):
        super().__init__(owner, name)
        self.ls_name = lightsource
        self.interferometer_name = interferometer
        self.role = role

        self.working = False
        self.ready = True
        self.light_time = 0
        self.ls_freq = 0
        self.start_time = 0
        self.photon_delay = 0
        self.phases_list = []
        self.timeAtdetector = []
        self.key = 0
        self.key_bits = None
        self.another = None
        self.key_length = 0

        self.latency = 0
        self.last_key_time = 0
        self.throughputs = []
        self.error_rates = []
    
    def push(self,length:int):
        if self.role != 0:
            assert "Generate key must be called by alice"
        
        if self.ready:
            self.ready = False
            self.working = True
            self.another.working = True
            self.start_protocol()
        
    
    def start_protocol(self):
        """Method to start protocol.

        When called, this method will begin the process of key generation.
        Parameters for hardware will be calculated, and a `begin_photon_pulse` method scheduled.

        Side Effects:
            Will schedule future `begin_photon_pulse` event.
            Will send a BEGIN_PHOTON_PULSE method to other protocol instance.
        """
        print("starting protocol")

        ls = self.owner.components[self.ls_name]
        self.ls_freq = ls.frequency

        # send message that photon pulse is beginning, then send bits
        self.start_time = int(self.owner.timeline.now()) + round(self.owner.cchannels[self.another.owner.name].delay)

        self.owner.send_message(self.another.owner.name,"starting photon pulses")


        process = Process(self,"begin_photon_pulse",[])
        event = Event(self.start_time,process)

        self.owner.timeline.schedule(event)
        self.last_key_time = self.owner.timeline.now()

    def begin_photon_pulse(self):
        """Method to begin sending photons

        """    
        print("starting photon pulse")
        if self.working:
            self.owner.destination = self.another.owner.name

            num_pulses = round(self.light_time*self.ls_freq)

            pulse_list = np.random.choice([0,1,2,3],num_pulses)


            #hardware
            lightsource = self.owner.components[self.ls_name]
            encoding_type = lightsource.encoding_type
            state_list = []
            for i in range(num_pulses):
                if pulse_list[i] == 0:
                    state = (complex(sqrt(1/3)),complex(sqrt(1/3)),complex(sqrt(1/3)))
                elif pulse_list[i] == 1:
                    state = (complex(sqrt(1/3)),complex(sqrt(1/3)),-complex(sqrt(1/3)))
                elif pulse_list[i] == 2:
                    state = (complex(sqrt(1/3)),-complex(sqrt(1/3)),complex(sqrt(1/3)))
                else:
                    state = (complex(sqrt(1/3)),-complex(sqrt(1/3)),-complex(sqrt(1/3)))
                state_list.append(state)
            
class Alice(Node):
    def __init__(self, name, timeline, seed=None, gate_fid = 1, meas_fid = 1):
        super().__init__(name, timeline, seed, gate_fid, meas_fid)

        self.source = LightSource(name = 'photon_Source',
                                  timeline=tl,
                                  frequency=1e6,
                                  mean_photon_num=0.8,
                                  encoding_type=time_bin)
        
        self.add_component(self.source)
        self.source.add_receiver(self)
        self.source.emit([(complex(sqrt(1/3)),complex(sqrt(1/3)),complex(sqrt(1/3)))])
        self.timesent = []
    
    def emitPulse(self,photon:Photon):

        state = []

        for ph in range(3):
            phase = self.get_generator().choice([-1, 1])   
            state.append(phase * complex(sqrt(1/3)))         

        time = self.timeline.now()
        photon.set_state(tuple(state)) 
        self.qchannels[bob.name].transmit(photon,self)
        self.timesent.append((time))
        

    def get(self, photon, **kwargs):
        self.issent = True
        self.emitPulse(photon)
        # print("get method called")
        # print(self.qchannels)
    
    def receive_message(self, src, msg):
        print("message recieved from Bob:",msg)
        # return super().receive_message(src, msg)

    




class Bob(Node):
    def __init__(self, name, timeline, seed=None, gate_fid = 1, meas_fid = 1):
        super().__init__(name, timeline, seed, gate_fid, meas_fid)
    
        # self.detector0 = CQSDetector(name='detector',timeline=tl)
        self.detectors = [CDetector(name + ".detector" + str(i), timeline) for i in range(3)]
        self.interferometer = CInterferometer(name + ".interferometer", timeline, time_bin["bin_separation"])
        self.interferometer.add_receiver(self.detectors[0])
        self.interferometer.add_receiver(self.detectors[1])
        self.add_receiver(self.detectors[2])
        self.timestamps = []
        self.components = [self.interferometer] + self.detectors
        self.detectors[0].add_receiver(self)
        self.detectors[1].add_receiver(self)
        # self.owner = self
    def receive_qubit(self, src, qubit):
        # print("Qubit Recieved")
        print(type(qubit),"qubit type")
        self.interferometer.get(qubit)
        # self.timestamps.append(measure)

    def getkey(self,keybit,time):
        self.timestamps.append(time)
        print(self.cchannels)
        # self.send_message(self.cchannels['Alice'],time)
        self.cchannels[alice.name].transmit(time,self,1)
        print(keybit,time, "at Bob")

    # def send_message(self, dst, msg, priority=...):
    #     return super().send_message(dst, msg, priority)
alice = Alice("Alice",tl)
bob = Bob("Bob",tl)

channel = QuantumChannel(
    name='qc',
    timeline=tl,
    attenuation=0,
    distance=0
)

channel.set_ends(alice,bob.name)

cc = ClassicalChannel('cc',tl,1000)

cc.set_ends(bob,alice.name)
# cc.set_ends(alice,bob.name)

# channel.set_ends(bob, alice.name)

phase = 0
# emitprocess = Process(Alice,'emitPulse',[alice,phase])



tl.init()
# emit_event = Event(88,emitprocess)
# tl.schedule(emit_event)
# alice.emitPulse(0)
tl.run()

print("time sent (Alice):",alice.timesent)
# print(bob.timestamps)

# state = (complex(1/np.sqrt(2)),complex(1/np.sqrt(2)))

# photon = Photon('name',tl,0,None,time_bin,state,False)

# detector = QSDetectorTimeBin('detector',tl)

# detector.get(photon)


# measurement = photon.measure(((complex(sqrt(1 / 2)), complex(sqrt(1 / 2))), (complex(sqrt(1 / 2)), complex(-sqrt(1 / 2)))),photon,np.random)

# print(measurement)