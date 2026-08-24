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

def createState(phases=None):
    if phases is not None:
        state = [complex(sqrt(1/3))]
        for ph in phases[1:]:
            state.append(ph * complex(sqrt(1/3)))
        return tuple(state), phases
    
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
    return tuple(state), phases
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

    def __init__(self, owner, name, lightsource, role=-1):
        super().__init__(owner, name)

        self.ls_name = lightsource
        self.role = role
        self.total_emmited = 0
        self.working = False
        self.ready = True
        self.key = ''
        self.light_time = 0
        self.ls_freq = 0
        self.start_time = 0
        self.send_times = []
        self.phase_list = []
        self.key_bits = []
        self.bobkey = []
        self.bob_results = []
        self.corrected_key_indeces = []
        self.times = []
        self.slots = []
        self.pulse_interval = 10000
        # self.another = None
        self.error_rates = []
        self.key_length = 0


# =========================================================
# push() start key generation
# =========================================================
    def push(self, length,key_num = 1,run_time = math.inf):

        if self.role != 0:
            raise Exception("Only Alice starts DPS")

        self.key_length = length
        self.another.key_length = length
        self.send_times = []
        self.phase_list = []
        self.key_bits = []
        self.bob_results= []
        self.times = []
        self.working = True
        self.another.working = True
        print("called push",self)
        self.start_protocol()


# =========================================================
# start protocol
# =========================================================
    def start_protocol(self):
        # print(self.owner.components)
        # print(f"{self.owner.name} starting DPS protocol at time {self.owner.timeline.now()} ps")
        ls = self.owner.components[self.ls_name]
        self.ls_freq = ls.frequency

        self.light_time = self.key_length / self.ls_freq

        self.start_time = self.owner.timeline.now()

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


# =========================================================
# Alice send 3-pulse DPS states
# =========================================================
    def begin_photon_pulse(self):
        # print(f"{self.owner.name} begin photon pulse at time {self.owner.timeline.now()} ps")
        if self.role != 0:
            return

        num = int(self.light_time * self.ls_freq)

        state_list = []
        # self.phase_list = []
        time = self.start_time
        self.pulse_interval = int(1e12 / self.ls_freq)
        for i in range(num):

            time += self.pulse_interval

            process = Process(self, "emit_single", [])
            event = Event(time, process)

            self.owner.timeline.schedule(event)
            # print(f"Scheduled pulse {i+1} at time {time} ps")

    def setList(self, time):
        self.send_times.append(time)


    def emit_single(self):

        ls = self.owner.components[self.ls_name]
        # print(self.owner.components)
        # print(ls.encoding_type)
        send_time = self.owner.timeline.now()
        self.send_times.append(send_time)
        # print(f"{self.owner.name} emitting pulse at time {send_time} ps")
        
        
        state, phases = createState()
        self.phase_list.append(phases)
        ls.emit([state])
        self.total_emmited += 1
# =========================================================
# Bob detector input (only time)
# =========================================================
    def pop(self, detector, time):
        # print("Bob pop method called with detector:", detector, "time:", time)
        if self.role != 1:
            return

        self.times.append(time)
        # print(self.times, "Bob recorded times")
        self.bob_results.append((time, detector))
        # print(self.bob_results, "Bob recorded times and detectors")
        # print(len(self.bob_results), "Bob recorded results so far,time:", time)
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
        # print(self.times, "detection times")+
        # bin_sep = self.another.owner.components[self.ls_name].encoding_type["bin_separation"]

        bob_key = []
        # print("length of bob results",len(self.times))
        count = 0
        # print(f"bob results: {self.bob_results}")
        for t, det in self.bob_results:
            if self.eve:
                delay = self.eve.owner.qchannels[self.owner.name].distance / SPEED_OF_LIGHT
            else:
                delay = self.another.owner.qchannels[self.owner.name].distance / SPEED_OF_LIGHT
            t = t - delay
            bin_seperation = 1400
            slot = (t%self.pulse_interval)//bin_seperation
            if slot == 1 or slot == 2:
                count += 1
                if det == f'{self.owner.name}.detector0':
                    self.key_bits.append(0)
                elif det == f'{self.owner.name}.detector1':
                    self.key_bits.append(1)
        # print("self is ", self.owner.name)
        # print("keybits:", self.bobkey)
        # print("Number of key bits:", count)
        if self.owner.bobKey == '':
            self.owner.bobKey = "".join(map(str,self.bobkey))
        # print("Bob KEY  :", "".join(map(str,self.bobkey)))
        # print(self.owner.bobKey)
        # print("Bob sending times:", self.times)


        # self.bob_results = []
        msg = DPSMessage(
            DPSMsgType.DETECTION_TIME,
            self.another.name,
            times=self.times
        )
        # print(f"slots: {self.slots}")
        self.owner.send_message(self.another.owner.name, msg)


# =========================================================
# Receive classical messages
# =========================================================
    def received_message(self, src, msg):

        # Bob receives start message
        if msg.msg_type is DPSMsgType.BEGIN_PHOTON_PULSE:

            self.ls_freq = msg.frequency
            self.light_time = msg.light_time
            self.start_time = msg.start_time
            if self.eve:
                delay = self.eve.owner.qchannels[f'{self.owner.name}'].distance / SPEED_OF_LIGHT
            else:
                delay = self.another.owner.qchannels[f'{self.owner.name}'].distance / SPEED_OF_LIGHT 
            # self.owner.qchannels[f'{self.another.owner.name}'].distance / SPEED_OF_LIGHT

            # self.times = []
            end = self.start_time + int(self.light_time * 1e12) + delay + 5000  # wait for 5000 ps after last pulse

            process = Process(self, "end_detection", [])
            event = Event(end, process)
            
            self.owner.timeline.schedule(event)

        elif msg.msg_type is DPSMsgType.KEY_PROPAGATION:
            # print(f"{self.owner.name} received key propogation message with key: {msg.key}")
            pass

        # Alice receives detection times
        elif msg.msg_type is DPSMsgType.DETECTION_TIME:

            bin_sep = self.owner.components[self.ls_name].encoding_type["bin_separation"]
            # print(self.total_emmited, "pulses emmited")

            # print("Alice received times:", msg.times)
            # print("Alice send times    :", self.send_times)
            # print("Alice send times    :", self.send_times)
            # print(len(msg.times), "detection times received",self.owner.timeline.now())
            if self.eve:
                self.distance = self.owner.qchannels[f'{self.eve.owner.name}'].distance
            else:
                self.distance = self.owner.qchannels[f'{self.another.owner.name}'].distance
            delay = self.distance / SPEED_OF_LIGHT
            # print("Distance:", self.distance, "m, Delay:", delay, "ps")
            msg.times = [int(t - delay) for t in msg.times]
            # print("Alice times after delay correction:", msg.times)
            # print("Alice phaselist :",self.phase_list)
            idx = 0
            # print(len(self.phase_list), "Alice phase list")
            # print(len(self.key_bits), "Alice key bits before processing detection times")
            for t in msg.times:
                # print("Processing detection time:", t, "ps")
                while idx < len(self.send_times):
                    # print("Match found:", t - self.send_times[idx], idx)
                    if t - self.send_times[idx]  <= 4200 and t - self.send_times[idx] >= 0:
                        
                        break
                        # print(self.send_times[idx]-t, t, self.send_times[idx],t)
                    idx += 1
                if idx >= len(self.send_times):
                    print("No more send times to match with")
                    break
                dt = t - self.send_times[idx]
                slot = int(dt / bin_sep)
                # print("slot:", slot, "dt:", dt, "index:",idx)
                p0,p1, p2 = self.phase_list[idx]
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
            # print(self.key_bits,"self key")                 
            if self.key_bits:
                # print("Alice key bits:", self.key_bits)
                # bits = ''
                # for bit in self.key_bits:
                #     # print(bit, end=' ')
                #     bits+=str(bit)
                # # print(bits)
                # self.key += bits
                # # print(self.key,"key now")
                # self.key_bits = []
                # print(len(self.key),self.key_length)
                print(type(self.key_bits[0]))
                self.set_key()
                self.another.set_key()
                if self.owner.aliceKey == '':
                    self.owner.aliceKey = self.key
                    # print('upper protocols', self.lower_protocols)
                    # print(self)
                    self._pop(info=self.key)
                    self.another._pop(info = self.another.key)
                    self.another.owner.bobKey = self.another.key
                # print("ALICE KEY:", self.owner.aliceKey) 
            # self._pop(info=self.key)
                key_diff = self.key ^ self.another.key
                num_errors = 0
                while key_diff:
                    key_diff &= key_diff - 1
                    num_errors += 1
                self.error_rates.append(num_errors / self.key_lengths[0])

                self.keys_left_list[0] -= 1

            self.last_key_time = self.owner.timeline.now()
            # self.key_bits.clear()


# =========================================================
# Convert key bits
# =========================================================
    def set_key(self):
        bits = self.key_bits[:self.key_length]
        self.key_bits = self.key_bits[self.key_length:]
        self.key = int("".join(str(b) for b in bits), 2)

    # def set_bob_key(self):
    #     bits = self.bobkey[:self.key_length]
    #     self.bobkey = self.bobkey[self.key_length:]

    #     self.key = int("".join(str(b) for b in bits), 2)