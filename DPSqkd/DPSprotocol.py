# from NewTests.DPS_QKD import DPSKeyMessage
# from jupyter_server_terminals import msg
import math

import numpy as np
from enum import Enum, auto
from numpy import sqrt

from sequence.protocol import StackProtocol
from sequence.message import Message
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from sequence.constants import SPEED_OF_LIGHT
# from math import 
from sympy import sqrt,pi, cos, sin

# =========================================================
# Pair function
# =========================================================
def pair_dps_protocols(alice, bob,eve=None):
    alice.another = bob
    bob.another = alice
    alice.role = 0
    bob.role = 1
    alice.eve = None
    bob.eve = None
    if eve:
        alice.eve = eve
        bob.eve = eve
        eve.another = bob
    # print(f"Paired {alice.owner.name}'s {alice.name} with {bob.owner.name}'s {bob.name}")


# =========================================================
# Message Types
# =========================================================
class DPSMsgType(Enum):
    BEGIN_PHOTON_PULSE = auto()
    DETECTION_TIME = auto()
    KEY_PROPAGATION = auto()

# =========================================================
# Message
# =========================================================
class DPSMessage(Message):

    def __init__(self, msg_type, receiver, **kwargs):
        super().__init__(msg_type, receiver)
        self.protocol_type = DPS

        if msg_type is DPSMsgType.BEGIN_PHOTON_PULSE:
            self.frequency = kwargs["frequency"]
            self.light_time = kwargs["light_time"]
            self.start_time = kwargs["start_time"]

        elif msg_type is DPSMsgType.DETECTION_TIME:
            self.times = kwargs["times"]
        
        elif msg_type is DPSMsgType.KEY_PROPAGATION:
            self.key = kwargs["key"]
            self.keyname = kwargs["keyname"]
            self.xorKey = kwargs["xorKey"]
        
# =========================================================
# DPS Protocol
# =========================================================
class DPS(StackProtocol):

    def __init__(self, owner, name, lightsource, interferometer, role=-1):
        super().__init__(owner, name)

        self.ls_name = lightsource
        self.interferometer = interferometer
        self.role = role
        self.total_emmited = 0

        self.working = False
        self.ready = True
        self.key = 0
        self.light_time = 0
        self.ls_freq = 0
        self.start_time = 0
        self.photon_delay = 0 #time delay of photon (including dispersion) ps
        self.send_times = []
        self.phase_list = []
        self.key_bits = None
        self.another = None
        self.bobkey = []
        self.bob_results = []
        # self.corrected_key_indeces = []
        self.times = []
        # self.slots = []
        self.pulse_interval = 10000
        # self.another = None
        self.key_lengths = []
        self.keys_left_list = []
        self.end_run_times = []


        self.latency = 0  # measured in seconds
        self.last_key_time = 0
        self.throughputs = []  # measured in bits/sec
        self.error_rates = []

# =========================================================
# push() start key generation
# =========================================================
    def createState(self,phases=None):
        if phases is not None:
            state = [complex(sqrt(1/3))]
            for ph in phases[1:]:
                state.append(ph * complex(sqrt(1/3)))
            return tuple(state), phases
        
        state = [complex(sqrt(1/3))]
        sentstate = []
        phases = [1]
        for ph in range(2):
            phvalue = self.owner.generator.choice([1,-1])   
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
        return tuple(state), phases
    def push(self, length,key_num = 1,run_time = math.inf):

        if self.role != 0:
            raise Exception("Only Alice starts DPS")

        self.key_lengths.append(length)
        self.another.key_lengths.append(length)
        self.keys_left_list.append(key_num)
        end_run_time = run_time + self.owner.timeline.now()
        self.end_run_times.append(end_run_time)
        self.another.end_run_times.append(end_run_time)

        if self.ready:
            self.ready = False
            self.working = True
            self.another.working = True
            self.start_protocol()
        # self.send_times = []
        # self.phase_list = []
        # self.key_bits = []
        # self.bob_results= []
        # self.times = []


        # self.working = True
        # self.another.working = True
        # print("called push generating keys",self)
        # self.start_protocol()


# =========================================================
# start protocol
# =========================================================
    def start_protocol(self):
        # print(f"{self.owner.name} starting DPS protocol at time {self.owner.timeline.now()} ps")


        print(self.name + ' starting protocol')
        if len(self.key_lengths)> 0:
            self.phase_list = []
            self.another.phase_list = []
            self.send_times = []
            self.another.send_times = []

            self.key_bits = []
            self.another.key_bits = []
            self.latency = 0
            self.another.latency = 0

            self.working = True
            self.another.working = True

            ls = self.owner.components[self.ls_name]

            self.ls_freq = ls.frequency

            self.light_time = self.key_lengths[0] / (self.ls_freq * ls.mean_photon_num)

            self.start_time = int(self.owner.timeline.now()) + round(self.owner.cchannels[self.another.owner.name].delay)
            self.batch_start_time = int(self.owner.timeline.now())
            msg = DPSMessage(
                DPSMsgType.BEGIN_PHOTON_PULSE,
                self.another.name,
                frequency=self.ls_freq,
                light_time=self.light_time,
                start_time=self.start_time
            )

            self.owner.send_message(self.another.owner.name, msg)

            process = Process(self, "begin_photon_pulse", [])
            event = Event(self.start_time, process)
            self.owner.timeline.schedule(event)

            self.last_key_time = self.owner.timeline.now()

        else:
            self.ready = True




# =========================================================
# Alice send 3-pulse DPS states
# =========================================================
    def begin_photon_pulse(self):
        # print(f"{self.name} begin photon pulse at time {self.owner.timeline.now()} ps")

        if self.working and self.owner.timeline.now() < self.end_run_times[0]:
            self.owner.destination = self.another.owner.name

            num_pulses = round(self.light_time * self.ls_freq)
            phase_list = []
            send_times = []
            state_list = []
            now_time = self.owner.timeline.now()
            period = int(round(1e12/self.ls_freq))
            lightsource = self.owner.components[self.ls_name]
            encoding_type = lightsource.encoding_type
            for i in range(num_pulses):
                send_times.append(now_time+(i*period))
                state, phases = self.createState()
                phase_list.append(phases)
                state_list.append(state)
            lightsource.emit(state_list)

            self.phase_list.append(phase_list)
            self.send_times.append(send_times)

            self.start_time = self.owner.timeline.now()
            process = Process(self,'begin_photon_pulse',[])
            event = Event(self.start_time + int(round(self.light_time * 1e12)),process)
            self.owner.timeline.schedule(event)
        else:
            self.working = False
            self.another.working = False

            self.key_lengths.pop(0)
            self.keys_left_list.pop(0)
            self.end_run_times.pop(0)
            self.another.key_lengths.pop(0)
            self.another.end_run_times.pop(0)
            time = self.owner.timeline.now() + self.owner.qchannels[self.another.owner.name].delay + 1
            process = Process(self, "start_protocol", [])
            event = Event(time, process)
            self.owner.timeline.schedule(event)

        
    def setList(self, time):
        self.send_times.append(time)



# =========================================================
# Bob detector input (only time)
# =========================================================
    def pop(self, detector, time):
        # print("Bob pop method called with detector:", detector, "time:", time, ' length:', len(self.times))
        if self.role != 1:
            return

        if self.times and time - self.times[-1] <= 4200:
            # print(f'multiple photons')
            return
        
        self.times.append(time)
        
        # print(self.times, "Bob recorded times")
    #     print(
    #     "BOB DETECTION:",
    #     "time =", time,
    #     "detector =", detector
    # )
        self.bob_results.append((time, detector))
    def sendQubit(self,photon):
        if self.role == 1:
            return
        # print('Alice send qubit to ', self.another.owner.name)
        if self.eve:
            # print('Alice send qubit to Eve', self.eve.owner.name)
            self.owner.send_qubit(self.eve.owner.name, photon)
        else:
            # print('Alice send qubit to ', self.another.owner.name)

            self.owner.send_qubit(self.another.owner.name, photon)
    
    def sendEveQubit(self,photon):
        # print('recived photon to send to bob')
        self.owner.send_qubit(self.another.owner.name, photon)
        
# =========================================================
# Bob send detection times
# =========================================================
    def end_detection(self):
        '''method to process sent qubits '''
        print(f'{self.name} ending detection')

        if self.working and self.owner.timeline.now() < self.end_run_times[0]:
            count = 0
            self.start_time = self.owner.timeline.now()
            for t, det in self.bob_results:
                # print(t, det)
                if self.eve:
                    delay = self.eve.owner.qchannels[self.owner.name].distance / SPEED_OF_LIGHT
                else:
                    delay = self.another.owner.qchannels[self.owner.name].distance / SPEED_OF_LIGHT
                t = t
                bin_seperation = 1400
                slot = int((t%self.ls_freq)//bin_seperation)
                # print(f'slot at end detection : {slot}, dt = {t}')
                if slot == 1 or slot == 2:
                    count += 1
                    if det == f'{self.owner.name}.detector0':
                        # print(f'appended 0')
                        self.key_bits.append(0)
                    elif det == f'{self.owner.name}.detector1':
                        self.key_bits.append(1)
                        # print(f'appended 1')
            # print(f"key bits length {len(self.key_bits)}")
            if self.owner.bobKey == '':
                self.owner.bobKey = "".join(map(str,self.key_bits))
            # print(self.owner.timeline.now(), "end runtime :", self.end_run_times[0])
            if self.owner.timeline.now() + self.light_time * 1e12 -1 < self.end_run_times[0]:
                # print(f'end detection scheduled again at ', self.start_time + int(round(self.light_time*1e12)-1))
                process = Process(self, 'end_detection', [])
                event = Event(self.start_time + int(round(self.light_time*1e12)-1), process)
                self.owner.timeline.schedule(event)

            # print(len(self.times), ': self.times')
        # self.bob_results = []
            msg = DPSMessage(
                DPSMsgType.DETECTION_TIME,
                self.another.name,
                times=self.times
            )
            # print(f"slots: {self.slots}")
            self.owner.send_message(self.another.owner.name, msg)
            self.times = []
            self.bob_results = []
            self.phase_list = []
            


# =========================================================
# Receive classical messages
# =========================================================
    def received_message(self, src, msg):

        '''Method to recieve messages.
        
        Will perform different processing actions based on the message received. 

        '''

        if self.working and self.owner.timeline.now() < self.end_run_times[0]:
    

            # Bob receives start message
            if msg.msg_type is DPSMsgType.BEGIN_PHOTON_PULSE:

                self.ls_freq = msg.frequency
                self.light_time = msg.light_time
                
                if self.eve:
                    delay = self.owner.qchannels[src].delay
                else:
                    delay = self.owner.qchannels[src].delay 
                self.start_time = msg.start_time + delay
                end = self.start_time + int(self.light_time * 1e12) -1 # wait for 5000 ps after last pulse

                process = Process(self, "end_detection", [])
                event = Event(end, process)
                
                self.owner.timeline.schedule(event)

            elif msg.msg_type is DPSMsgType.KEY_PROPAGATION:
            
                pass

            # Alice receives detection times
            elif msg.msg_type is DPSMsgType.DETECTION_TIME:

                bin_sep = self.owner.components[self.ls_name].encoding_type["bin_separation"]

                if self.eve:
                    self.distance = self.owner.qchannels[f'{self.eve.owner.name}'].distance
                else:
                    self.distance = self.owner.qchannels[f'{self.another.owner.name}'].distance
                delay = self.distance / SPEED_OF_LIGHT
                # print("Distance:", self.distance, "m, Delay:", delay, "ps")
                msg_times_nodelay = [int(t - delay) for t in msg.times]
                # print(f'delay times {len(msg_times_nodelay)}')
                
                send_times = self.send_times.pop(0)
                phase_list = self.phase_list.pop(0)
                # print(f'len send times:{len(send_times)}')
                # print(f'phase list : {len(phase_list)}')
                idx = 0
                count = 0
                for t in msg_times_nodelay:
                    
                    while idx < len(send_times):

                        difference = t - send_times[idx]

                        if 0 <= difference <= 4200:
                            # print(f'{t} send time and diff:{difference}')
                            count+=1
                            break

                        idx += 1

                    if idx >= len(send_times):
                        print("No more send times to match with")
                        break

                    # We matched this send time.
                    # Move to the next one so it cannot be reused.
                    # matched_time = send_times[idx]
                    # print(f'this is total count {count}, send_times at index {idx} is {send_times[idx]}')
                    # idx += 1

                    # print(
                    #     "MATCH:",
                    #     "detection =", t,
                    #     "send_time =", matched_time,
                    #     "difference =", t - matched_time
                    # )
                    dt = t - send_times[idx]
                    # print(f'time = {t} and send_times index {idx} is {send_times[idx]} this is difference {dt}')
                    slot = int(dt / bin_sep)
                    # print("slot:", slot, "dt:", send_times[idx], "index:",idx, 'phase ', ([int(i) for i in phase_list[idx]]))
                    p0,p1, p2 = phase_list[idx]
                    # print(self.phase_list[idx], "Alice phase for this pulse")
                    if slot == 1:
                        bit = 0 if p1 == 1 else 1
                        self.key_bits.append(bit)

                    elif slot == 2:
                        if p1 == 1 and p2 == -1:
                            bit = 1
                            self.key_bits.append(bit)
                        elif p1 == -1 and p2 == 1:
                            bit = 1
                            self.key_bits.append(bit)
                        elif p1 == 1 and p2 == 1:
                            bit = 0
                            self.key_bits.append(bit)
                        elif p1 == -1 and p2 == -1:
                            bit = 0
                            self.key_bits.append(bit)
                        # bit = 0 if p2 == 1 else 1
                # print((self.key_bits),"self key")   
                # print("key length ",self.key_lengths[0])
                if len(self.key_bits) >= self.key_lengths[0]:
                    throughput = self.key_lengths[0]*1e12 / (self.owner.timeline.now()-self.last_key_time)
                    while len(self.key_bits)>= self.key_lengths[0] and self.keys_left_list[0]>0:
                        print(f'{self.name} generated a valid key')
                        self.set_key()
                        self.another.set_key()
                        # key = "".join(str(b) for b in self.key_bits)
                        # key2 = "".join(str(b) for b in self.another.key_bits)
                        self._pop(info = self.key)
                        
                        self.another._pop(info = self.another.key)

                        if self.latency == 0:
                            self.latency = (self.owner.timeline.now() - self.last_key_time) * 1e-12
                        self.throughputs.append(throughput)

                        key_diff = self.key ^ self.another.key
                        num_errors = 0
                        while key_diff:
                            key_diff &= key_diff - 1
                            num_errors += 1
                        self.error_rates.append(num_errors / self.key_lengths[0])
                        self.keys_left_list[0] -=1


                    self.last_key_time = self.owner.timeline.now()
                    # print(f"last key time:", self.last_key_time)

                if self.keys_left_list[0] <1:
                    self.working = False
                    self.another.working = False

                # print(self.owner.timeline.now())

    def set_key(self):
        # print(f'{self} called the set_key')
        bits = self.key_bits[0:self.key_lengths[0]]
        del self.key_bits[0:self.key_lengths[0]]
        self.key = int("".join(str(b) for b in bits), 2)
        # print(f'after set key is done key_bits length = {len(self.key_bits)}')
