import struct
import socket
import datetime

class Packet:
    '''
    RIP packet consistint of:
    header (4 bytes),
    body, made from RTEs (N*20 bytes)
    '''

    def __init__(self, data=None, header=None, rtes=None):

        if data:
            self._from_network(data)

        else:
            self._from_host(header, rtes)

    def __repr__(self):
        return f"RIPPacket: Command {self.header.cmd}, Ver. {self.header.ver}, number of RTEs {len(self.rtes)}."

    def _from_network(self, data):
        '''
        Raw data received from network
        '''

        datalen = len(data)

        # Parse packet into Header and RTEs
        rte_count = int((datalen - Header.SIZE) / RTE.SIZE)

        self.header = Header(data[0:Header.SIZE])

        rte_start = Header.SIZE
        rte_end = Header.SIZE + RTE.SIZE

        self.rtes = []

        # Loop over data packet to obtain each RTE
        for _ in range(rte_count):
            self.rtes.append(RTE(raw_data = data[rte_start:rte_end], src_id=self.header.src))

            rte_start += RTE.SIZE
            rte_end += RTE.SIZE

    def _from_host(self, header, rtes):
        '''
        Packet being constructed locally
        '''

        self.header = header
        self.rtes = rtes

    def serialize(self):
        '''
        Convert into byte string for transmission
        '''

        packet = self.header.serialize()

        for rte in self.rtes:
            packet += rte.serialize()

        return packet


class Header:

    '''
    RIP Packet header, consisting of: 
    command (1 byte),
    version (1 byte),
    must be zero (2 bytes)
    In this simulation MBZ field is used for source router ID
    '''

    FORMAT = "!BBH"
    SIZE = struct.calcsize(FORMAT)
    COMMAND_RESPONSE = 2
    VERSION = 2

    def __init__(self, raw_data=None, router_id=None):

        self.packed = None

        if raw_data:
            self._from_network(raw_data)
        elif router_id:
            self._from_host(router_id)

    def __repr__(self):
        return f"RIP Header (cmd = {self.cmd}, ver = {self.ver}, src = {self.src})"

    def _from_network(self, raw_data):
        '''
        Raw data received from network
        '''
        header = struct.unpack(self.FORMAT, raw_data)

        self.cmd = header[0]
        self.ver = header[1]
        self.src = header[2]

    def _from_host(self, router_id):
        '''
        Packet Header being constructed locally
        '''
        self.cmd = self.COMMAND_RESPONSE
        self.ver = self.VERSION
        self.src = router_id

    def serialize(self):
        '''
        Convert into byte string for transmission
        '''
        return struct.pack(self.FORMAT, self.cmd, self.ver, self.src)


class RTE:

    '''
    RTE, consisting of: 
    AFI (2 bytes),
    Route tag [UNUSED] (2 bytes) = 0,
    Address (4 bytes) = router id
    Mask [UNUSED] (4 bytes) = 0 
    Next Hop (4 bytes)
    Metric (4 bytes)
    '''

    AF_INET = 2 # ipv4
    FORMAT = "!HHIIII"
    SIZE = struct.calcsize(FORMAT)
    MIN_METRIC = 0
    MAX_METRIC = 16

    def __init__(self, raw_data=None, src_id=None, address=None,
                 next_hop=None, metric=None, imported=False):

        self.changed = False
        self.imported = imported
        self.init_timeout()

        if raw_data and src_id != None:
            self._from_network(raw_data, src_id)
        else:
            self._from_host(address, next_hop, metric)

    def __repr__(self):
        return '|{:^13}|{:^10}|{:^12}|{:^14}|{:^12}|\n'.format(
                    self.addr,
                    self.metric,
                    self.next_hop,
                    self.changed,
                    self.is_garbage
                )

    def _from_network(self, raw_data, src_id):
        '''
        Raw data received from network
        '''
        rte = struct.unpack(self.FORMAT, raw_data)

        self.afi = rte[0]
        self.tag = rte[1]
        self.addr = rte[2]
        self.mask = rte[3]
        self.next_hop = rte[4]
        self.metric = rte[5]

        if self.next_hop == 0:
            self.next_hop = src_id
    
    def _from_host(self, address, next_hop, metric):
        '''
        RTE being constructed locally
        '''
        self.afi = self.AF_INET
        self.tag = 0 # unused
        self.addr = address
        self.mask = 0 # unused
        self.next_hop = next_hop
        self.metric = metric

    def init_timeout(self):
        '''
        Set timeout
        '''

        if self.imported:
            self.timeout = None
        else:
            self.timeout = datetime.datetime.now()

        self.is_garbage = False

    def __eq__(self, other):

        return  (
                    self.afi == other.afi and
                    self.addr == other.addr and
                    self.mask == other.mask and
                    self.tag == other.tag and 
                    self.next_hop == other.next_hop and 
                    self.metric == other.metric
                )

    def serialize(self):
        '''
        Convert into byte string for transmission
        '''
        return struct.pack(self.FORMAT,
                           self.afi,
                           self.tag,
                           self.addr,
                           self.mask,
                           self.next_hop,
                           self.metric)
    
    def set_next_hop(self, next_hop):
        '''
        Self (non-static) variables must be set through functions
        '''
        self.next_hop = next_hop