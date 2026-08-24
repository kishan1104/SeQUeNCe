from ipywidgets import interact
from matplotlib import pyplot as plt
import time
from sequence.kernel.timeline import Timeline
from sequence.topology.node import QKDNode
from sequence.components.optical_channel import QuantumChannel, ClassicalChannel
from sequence.constants import MILLISECOND
from DPSqkd.DPSprotocol import DPS,pair_dps_protocols
from DPSqkd.CustomComponents import DPSNode

# class KeyManager():
#     def __init__(self, timeline, keysize, num_keys):
#         self.timeline = timeline
#         self.lower_protocols = []
#         self.keysize = keysize
#         self.num_keys = num_keys
#         self.keys = []
#         self.times = []
        
#     def send_request(self):
#         for p in self.lower_protocols:
#             p.push(self.keysize, self.num_keys) # interface for BB84 to generate key
            
#     def pop(self, info): # interface for BB84 to return generated keys
#         self.keys.append(info)
#         self.times.append(self.timeline.now() / MILLISECOND)

# def test(sim_time, keysize):
#     """
#     sim_time: duration of simulation time (ms)
#     keysize: size of generated secure key (bits)
#     """
#     # begin by defining the simulation timeline with the correct simulation time
#     tl = Timeline(sim_time * 1e9)
    
#     # Here, we create nodes for the network (QKD nodes for key distribution)
#     # stack_size=1 indicates that only the BB84 protocol should be included
#     n1 = QKDNode("n1", tl, stack_size=1)
#     n2 = QKDNode("n2", tl, stack_size=1)
#     n1.set_seed(0)
#     n2.set_seed(1)
#     pair_bb84_protocols(n1.protocol_stack[0], n2.protocol_stack[0])
    
#     # connect the nodes and set parameters for the fibers
#     # note that channels are one-way
#     # construct a classical communication channel
#     # (with arguments for the channel name, timeline, and length (in m))
#     cc0 = ClassicalChannel("cc_n1_n2", tl, distance=1e3)
#     cc1 = ClassicalChannel("cc_n2_n1", tl, distance=1e3)
#     cc0.set_ends(n1, n2.name)
#     cc1.set_ends(n2, n1.name)
#     # construct a quantum communication channel
#     # (with arguments for the channel name, timeline, attenuation (in db/m), and distance (in m))
#     qc0 = QuantumChannel("qc_n1_n2", tl, attenuation=1e-5, distance=1e3, polarization_fidelity=0.97)
#     qc1 = QuantumChannel("qc_n2_n1", tl, attenuation=1e-5, distance=1e3, polarization_fidelity=0.97)
#     qc0.set_ends(n1, n2.name)
#     qc1.set_ends(n2, n1.name)
    
#     # instantiate our written keysize protocol
#     km1 = KeyManager(tl, keysize, 25)
#     km1.lower_protocols.append(n1.protocol_stack[0])
#     n1.protocol_stack[0].upper_protocols.append(km1)
#     km2 = KeyManager(tl, keysize, 25)
#     km2.lower_protocols.append(n2.protocol_stack[0])
#     n2.protocol_stack[0].upper_protocols.append(km2)
    
#     # start simulation and record timing
#     tl.init()
#     km1.send_request()
#     tick = time.time()
#     tl.run()
#     print("execution time %.2f sec" % (time.time() - tick))
    
#     # display our collected metrics
#     plt.plot(km1.times, range(1, len(km1.keys) + 1), marker="o")
#     plt.xlabel("Simulation time (ms)")
#     plt.ylabel("Number of Completed Keys")
#     plt.show()
    
#     print("key error rates:")
#     for i, e in enumerate(n1.protocol_stack[0].error_rates):
#         print("\tkey {}:\t{}%".format(i + 1, e * 100))

from sequence.qkd.cascade import pair_cascade_protocols

class KeyManager():
    def __init__(self, timeline, keysize, num_keys):
        self.timeline = timeline
        self.lower_protocols = []
        self.keysize = keysize
        self.num_keys = num_keys
        self.keys = []
        self.times = []
        
    def send_request(self):
        for p in self.lower_protocols:
            print(p)
            p.push(self.keysize, self.num_keys) # interface for cascade to generate keys
            
    def pop(self, key): # interface for cascade to return generated keys
        self.keys.append(key)
        self.times.append(self.timeline.now() * 1e-9)
        
def test(sim_time, keysize):
    """
    sim_time: duration of simulation time (ms)
    keysize: size of generated secure key (bits)
    """
    # begin by defining the simulation timeline with the correct simulation time
    tl = Timeline(sim_time * 1e9)
    
    # Here, we create nodes for the network (QKD nodes for key distribution)
    n1 = DPSNode("n1", tl)
    n2 = DPSNode("n2", tl)
    # n1.set_seed(0)
    # n2.set_seed(1)
    
    n1.protocol_stack[1].lower_protocols[0] = n1.protocol_stack[0]
    n2.protocol_stack[1].lower_protocols[0] = n2.protocol_stack[0]
    pair_dps_protocols(n1.protocol_stack[0], n2.protocol_stack[0])
    pair_cascade_protocols(n1.protocol_stack[1], n2.protocol_stack[1])
    
    # connect the nodes and set parameters for the fibers
    cc0 = ClassicalChannel("cc_n1_n2", tl, distance=1e3)
    cc1 = ClassicalChannel("cc_n2_n1", tl, distance=1e3)
    cc0.set_ends(n1, n2.name)
    cc1.set_ends(n2, n1.name)
    qc0 = QuantumChannel("qc_n1_n2", tl, attenuation=1e-5, distance=1e3, polarization_fidelity=0.97)
    qc1 = QuantumChannel("qc_n2_n1", tl, attenuation=1e-5, distance=1e3, polarization_fidelity=0.97)
    qc0.set_ends(n1, n2.name)
    qc1.set_ends(n2, n1.name)
    
    # instantiate our written keysize protocol
    km1 = KeyManager(tl, keysize, 1)
    km1.lower_protocols.append(n1.protocol_stack[1])
    n1.protocol_stack[1].upper_protocols.append(km1)
    # n1.protocol_stack[0].upper_protocols.append(n1.protocol_stack[1])
    km2 = KeyManager(tl, keysize, 1)
    km2.lower_protocols.append(n2.protocol_stack[1])
    # n2.protocol_stack[0].upper_protocols.append(n2.protocol_stack[1])
    n2.protocol_stack[1].upper_protocols.append(km2)
    
    # start simulation and record timing
    tl.init()
    km1.send_request()
    tick = time.time()
    tl.run()
    print("execution time %.2f sec" % (time.time() - tick))


    # print(km2.keys)
    # print(n1.aliceKey)

    # print()
    # print()
    # print(n2.bobKey)
    # display our collected metrics
    # plt.plot(km1.times, range(1, len(km1.keys) + 1), marker="o")
    # plt.xlabel("Simulation time (ms)")
    # plt.ylabel("Number of Completed Keys")
    # plt.show()
    
    error_rates = []
    print(len(n1.aliceKey), len(n2.bobKey))

    print(km1.keys)
    print(km2.keys)
    for i, key in enumerate(km1.keys):
        counter = 0
        diff = key ^ km2.keys[i]
        for j in range(km1.keysize):
            counter += (diff >> j) & 1
        error_rates.append(counter)

    print("key error rates:")
    for i, e in enumerate(error_rates):
        print("\tkey {}:\t{}%".format(i + 1, e))

# Create and run the simulation
# interactive_plot = interact(test, sim_time=(10, 100, 10), keysize=[128, 256, 512])
# interactive_plot

test(100000000,128)