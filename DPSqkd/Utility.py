import random

from sequence.components.optical_channel import QuantumChannel, ClassicalChannel
from sequence.topology.node import Node

def calculate_qber(alice_key, bob_key):
    """
    Calculate Quantum Bit Error Rate (QBER).

    Args:
        alice_key (list[int]): Alice's sifted key bits.
        bob_key (list[int]): Bob's sifted key bits.

    Returns:
        float: QBER
    """

    assert len(alice_key) == len(bob_key), \
        "Keys must have the same length"

    if len(alice_key) == 0:
        print(len(alice_key), "Alice key length")
        return 0.0

    errors = sum(
        1
        for a, b in zip(alice_key, bob_key)
        if a != b
    )

    return errors / len(alice_key)




def estimate_qber(alice_key, bob_key, sample_size):
    assert len(alice_key) == len(bob_key)

    indices = random.sample(
        range(len(alice_key)),
        min(sample_size, len(alice_key))
    )

    errors = sum(
        1
        for i in indices
        if alice_key[i] != bob_key[i]
    )

    qber = errors / len(indices)
    return qber

def CreateNetwork(numberofnodes,tl, nodeType:Node):
    nodes = []
    for i in range(numberofnodes):
        node = nodeType(f'Node{i}', tl)
        nodes.append(node)
    for i,node in enumerate(nodes):
        if i < numberofnodes - 1:
            qc = QuantumChannel(f'qc_{node.name}_{nodes[i+1].name}', tl, attenuation=0.0002, distance=24000)
            # qc2 = QuantumChannel(f'qc_{nodes[i+1].name}_{node.name}', tl, attenuation=0, distance=1000)
            # qc2.set_ends(nodes[i+1], node.name)
            qc.set_ends(node, nodes[i+1].name)
            cc1 = ClassicalChannel(f'cc_{node.name}_{nodes[i+1].name}', tl, 1000)
            cc2 = ClassicalChannel(f'cc_{nodes[i+1].name}_{node.name}', tl, 1000)
            cc1.set_ends(node, nodes[i+1].name)
            cc2.set_ends(nodes[i+1], node.name)

    return nodes



if __name__ == "__main__":
    pass