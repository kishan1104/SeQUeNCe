

from sequence.protocol import StackProtocol
from sequence.topology.node import QKDNode


class PrivacyAmplification(StackProtocol):
    def __init__(self,owner:'QKDNode', name:str):
        super().__init__(owner, name)
        self.protocol_type = 'privacy_amplification'


    def push(self, keysize:int, num_keys:int):
        # This method is called by the upper protocol to request key generation
        # It will push the request down to the lower protocol (DPS)
        self._push(keylen=keysize, frame_num = num_keys)  # interface for DPS to generate key
    
    def pop(self, key):
        # This method is called by the lower protocol (DPS) to return generated keys
        # It will pop the generated keys up to the upper protocol

        print(self.name + f' got valid key')
        # for p in self.upper_protocols:
        #     p.pop(key)  # interface for DPS to return generated keys