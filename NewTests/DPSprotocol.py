import numpy as np
from enum import Enum, auto
from numpy import sqrt

from sequence.protocol import StackProtocol
from sequence.message import Message
from sequence.kernel.process import Process
from sequence.kernel.event import Event


# =========================================================
# Pair function
# =========================================================
def pair_dps_protocols(alice, bob):
    alice.another = bob
    bob.another = alice
    alice.role = 0
    bob.role = 1


# =========================================================
# Message Types
# =========================================================
class DPSMsgType(Enum):
    BEGIN_PHOTON_PULSE = auto()
    DETECTION_TIME = auto()


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


# =========================================================
# DPS Protocol
# =========================================================
class DPS(StackProtocol):

    def __init__(self, owner, name, lightsource, role=-1):
        super().__init__(owner, name)

        self.ls_name = lightsource
        self.role = role

        self.working = False
        self.ready = True

        self.light_time = 0
        self.ls_freq = 0
        self.start_time = 0
        self.send_times = []
        self.phase_list = []
        self.key_bits = []

        self.bob_results = []
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

        self.working = True
        self.another.working = True

        self.start_protocol()


# =========================================================
# start protocol
# =========================================================
    def start_protocol(self):

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

        if self.role != 0:
            return

        lightsource = self.owner.components[self.ls_name]

        num = int(self.light_time * self.ls_freq)

        state_list = []
        self.phase_list = []

        for i in range(num):

            time = self.start_time + int(i * 1e12 / self.ls_freq)

            process = Process(self, "emit_single", [i])
            event = Event(time, process)

            self.owner.timeline.schedule(event)

    def emit_single(self, i):

        ls = self.owner.components[self.ls_name]

        send_time = self.owner.timeline.now()
        self.send_times.append(send_time)

        p1, p2 = np.random.choice([-1,1],2)

        state = (
            complex(sqrt(1/3)),
            complex(p1*sqrt(1/3)),
            complex(p2*sqrt(1/3))
        )

        self.phase_list.append((p1,p2))

        ls.emit([state])
# =========================================================
# Bob detector input (only time)
# =========================================================
    def pop(self, detector, time):

        if self.role != 1:
            return

        self.times.append(time)
        self.bob_results.append((time, detector))


# =========================================================
# Bob send detection times
# =========================================================
    def end_detection(self):
        bin_sep = self.another.owner.components[self.ls_name].encoding_type["bin_separation"]

        bob_key = []

        for t, det in self.bob_results:

            rel = t - self.start_time

            slot = int(rel / bin_sep) % 4

            if slot in [1,2]:

                bit = 0 if "detector0" in det else 1
                bob_key.append(bit)

        print("Bob KEY  :", "".join(map(str,bob_key)))
        # print("Bob sending times:", self.times)
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

            self.times = []
            end = self.start_time + int(self.light_time * 1e12)

            process = Process(self, "end_detection", [])
            event = Event(end, process)

            self.owner.timeline.schedule(event)

        # Alice receives detection times
        elif msg.msg_type is DPSMsgType.DETECTION_TIME:

            bin_sep = self.owner.components[self.ls_name].encoding_type["bin_separation"]

            for t in msg.times:

    # find closest Alice send time
                idx = None

                for i, ts in enumerate(self.send_times):

                    dt = t - ts

                    if 0 <= dt < 4 * bin_sep:
                        idx = i
                        break

                if idx is None:
                    continue

                dt = t - self.send_times[idx]
                slot = int(dt / bin_sep)

                p1, p2 = self.phase_list[idx]

                # print("pulse_index:", idx, "slot:", slot, "p1:", p1, "p2:", p2)

                if slot == 1:
                    bit = 0 if p1 == 1 else 1
                    self.key_bits.append(bit)

                elif slot == 2:
                    bit = 0 if p2 == 1 else 1
                    self.key_bits.append(bit)
            # print(self.key_bits)
            # print("Alice KEY:", "".join(map(str,self.key_bits)))            
            if self.key_bits:
                self.key = int("".join(str(b) for b in self.key_bits))
                print("DPS KEY:", self.key)
                self._pop(info=self.key)

                self.key_bits.clear()


# =========================================================
# Convert key bits
# =========================================================
    def set_key(self):

        bits = self.key_bits[:self.key_length]
        self.key_bits = self.key_bits[self.key_length:]

        self.key = int("".join(str(b) for b in bits), 2)