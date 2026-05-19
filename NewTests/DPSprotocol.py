# from NewTests.DPS_QKD import DPSKeyMessage
# from jupyter_server_terminals import msg
import numpy as np
from enum import Enum, auto
from numpy import sqrt

from sequence.protocol import StackProtocol
from sequence.message import Message
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from sequence.constants import SPEED_OF_LIGHT

# =========================================================
# Pair function
# =========================================================
def pair_dps_protocols(alice, bob):
    alice.another = bob
    bob.another = alice
    alice.role = 0
    bob.role = 1
    print(f"Paired {alice.owner.name}'s {alice.name} with {bob.owner.name}'s {bob.name}")

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
        self.another = None

        self.key_length = 0


# =========================================================
# push() start key generation
# =========================================================
    def push(self, length):

        if self.role != 0:
            raise Exception("Only Alice starts DPS")

        self.key_length = length
        self.send_times = []
        self.phase_list = []
        self.key_bits = []
        self.bob_results= []
        self.times = []
        self.working = True
        self.another.working = True
        # print("called push")
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
        pulse_interval = int(1e12 / self.ls_freq)
        for i in range(num):

            time += pulse_interval

            process = Process(self, "emit_single", [])
            event = Event(time, process)

            self.owner.timeline.schedule(event)
            # print(f"Scheduled pulse {i+1} at time {time} ps")

    def setList(self, time):
        self.send_times.append(time)


    def emit_single(self):

        ls = self.owner.components[self.ls_name]
        # print(self.owner.components)

        send_time = self.owner.timeline.now()

        # print(f"{self.owner.name} emitting pulse at time {send_time} ps")
        self.send_times.append(send_time)

        state = [complex(sqrt(1/3))]
        sentstate = []
        phases = [1]
        for ph in range(2):
            phase = np.random.choice([-1, 1])   
            state.append(phase * complex(sqrt(1/3)))
            sentstate.append(int(phase))
            phases.append(phase)
        self.phase_list.append(phases)

        ls.emit([tuple(state)])
        self.total_emmited += 1
        # print(f"Emitted pulse {self.total_emmited} at time {send_time} ps")
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
        print(len(self.bob_results), "Bob recorded results so far,time:", time)
    def sendQubit(self,photon):
        if self.role == 1:
            return

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
        for t, det in self.bob_results:
            delay = self.another.owner.qchannels[self.owner.name].distance / SPEED_OF_LIGHT
            t = t - delay
            bin_seperation = 1400
            slot = (t%10000)//bin_seperation
            if slot == 1 or slot == 2:
                count += 1
                if det == f'{self.owner.name}.detector0':
                    self.bobkey.append(0)
                elif det == f'{self.owner.name}.detector1':
                    self.bobkey.append(1)
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
            delay = self.owner.qchannels[f'{self.another.owner.name}'].distance / SPEED_OF_LIGHT

            # self.times = []
            end = self.start_time + int(self.light_time * 1e12) + delay + 5000  # wait for 5000 ps after last pulse

            process = Process(self, "end_detection", [])
            event = Event(end, process)
            
            self.owner.timeline.schedule(event)

        elif msg.msg_type is DPSMsgType.KEY_PROPAGATION:
            print(f"{self.owner.name} received key propogation message with key: {msg.key}")

        # Alice receives detection times
        elif msg.msg_type is DPSMsgType.DETECTION_TIME:

            bin_sep = self.owner.components[self.ls_name].encoding_type["bin_separation"]
            # print(self.total_emmited, "pulses emmited")

            # print("Alice received times:", msg.times)
            # print("Alice send times    :", self.send_times)
            # print(len(msg.times), "detection times received",self.owner.timeline.now())
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
                while idx < len(self.send_times):
                    if t - self.send_times[idx]  <= 4200 and t - self.send_times[idx] >= 0:
                        # print(4200, t - self.send_times[idx], idx)
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
                bits = ''
                for bit in self.key_bits:
                    # print(bit, end=' ')
                    bits+=str(bit)
                # print(bits)
                self.key += bits
                # print(self.key,"key now")
                self.key_bits = []
                print(len(self.key),self.key_length)
                if self.owner.aliceKey == '':
                    self.owner.aliceKey = self.key
                # print("ALICE KEY:", self.owner.aliceKey) 
            # self._pop(info=self.key)

            self.key_bits.clear()


# =========================================================
# Convert key bits
# =========================================================
    def set_key(self):

        bits = self.key_bits[:self.key_length]
        self.key_bits = self.key_bits[self.key_length:]

        self.key = int("".join(str(b) for b in bits), 2)