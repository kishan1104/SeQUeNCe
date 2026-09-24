

from sequence.protocol import StackProtocol
from sequence.topology.node import QKDNode


def pair_privacy_amp_protocols(sender: 'PrivacyAmplification', receiver: 'PrivacyAmplification'):


    sender.another = receiver
    receiver.another = sender
    sender.role = 0
    receiver.role = 1


import secrets


def toeplitz_hash(key, keylen, output_length):
    """
    Perform Toeplitz hashing for privacy amplification.

    Args:
        key_bits: list/array of 0/1 bits
        output_length: number of bits required in final key

    Returns:
        final_key: list of 0/1 bits
        seed: Toeplitz seed used to construct the hash
    """
    key_bits = [
        (key >> i) & 1
        for i in range(keylen - 1, -1, -1)
    ]
    n = len(key_bits)
    m = output_length

    # A Toeplitz matrix is specified by n + m - 1 random bits
    seed = [
        secrets.randbits(1)
        for _ in range(n + m - 1)
    ]

    final_key = []

    for i in range(m):

        bit = 0

        for j in range(n):

            # Toeplitz matrix element
            t_ij = seed[i + j]

            # Binary multiplication and addition
            bit ^= t_ij & key_bits[j]

        final_key.append(bit)
    final_bits = 0

    for bit in final_key:
        final_bits = (final_bits << 1) | bit
    return final_bits, seed


def toeplitz_hash_with_seed(key, keylen, output_length, seed):
    """
    Apply a previously generated Toeplitz hash.
    """
    
    key_bits = [
            (key >> i) & 1
            for i in range(keylen - 1, -1, -1)
        ]
    n = len(key_bits)
    m = output_length

    if len(seed) != n + m - 1:
        raise ValueError(
            "Invalid Toeplitz seed length"
        )

    final_key = []

    for i in range(m):

        bit = 0

        for j in range(n):

            t_ij = seed[i + j]

            bit ^= t_ij & key_bits[j]

        final_key.append(bit)
    final_bits = 0
    print(f'final key length in bits: {len(final_key)}')
    for bit in final_key:
        final_bits = (final_bits << 1) | bit
    return final_bits

class PrivacyAmplification(StackProtocol):
    def __init__(self,owner:'QKDNode', name:str):
        super().__init__(owner, name)
        self.protocol_type = 'privacy_amplification'
        self.toeplitsz_seed = None
        self.keysize = None
        self.final_key = None
        
    def push(self, keysize:int, num_keys:int):
        # This method is called by the upper protocol to request key generation
        # It will push the request down to the lower protocol (DPS)
        self.keysize = keysize
        self.another.keysize = keysize
        self._push(keylen=keysize, frame_num = num_keys)  # interface for DPS to generate key
    
    def pop(self, key):
        # This method is called by the lower protocol (DPS) to return generated keys
        # It will pop the generated keys up to the upper protocol
        if self.another.toeplitsz_seed is None:
            final_key, seed = toeplitz_hash(
                key,
                keylen=self.keysize,
                output_length=self.keysize
            )   
            self.another.toeplitsz_seed = seed
            self.toeplitsz_seed = seed
            self.final_key = final_key
        else:
            final_key = toeplitz_hash_with_seed(
                key,
                keylen=self.keysize,
                output_length=self.keysize,
                seed=self.another.toeplitsz_seed
            )
            self.final_key = final_key
        print(self.name + f' got valid key')
        for p in self.upper_protocols:
            # print(f'Popping key to {p}')
            p.pop(self.final_key)  # interface for DPS to return generated keys