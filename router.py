import socket
import sys
import time
import select
import os
import threading
import datetime
from packet import RTE, Packet, Header


class Output:

    def __init__(self, id, port, metric):
        self.id = id
        self.port = port
        self.metric = metric

class RouterConfig:

    def __init__(self, id, inputs, outputs):
        self.id = id
        self.inputs = inputs
        self.outputs = outputs

class Router:

    TIMER = 5 # calling updates every 5 seconds
    ROUTE_TIMEOUT = TIMER * 6 # route unupdated for 30 secs - mark as garbage
    DELETE_TIMEOUT = TIMER * 6 # route marked for garbage for 30 secs - delete
    

    def __init__(self, config, host = '127.0.0.1', lifespan = 60):
        self.id = None,
        self.inputs = {}
        self.outputs = {}
        self.routing_table = {}
        self.id = config.id
        self.host = host
        self.lifespan = lifespan

        # Indicates a change in the routing table
        self.changed = False

        # Ouput file
        self.f = None

        # How long the simulated router lives
        self.end_life = False
        
        self.config_inputs(config.inputs)
        self.config_outputs(config.outputs)
        self.config_io()
        
        # Add self to routing table
        self.routing_table[self.id] = RTE(
            address = self.id,
            next_hop = 0,
            metric = 0,
            imported = True
        )

        # Log initial table state
        self.log_routing_table()
    
    def run(self):
        self.config_timers()
        end = time.time() + self.lifespan
        while time.time() < end:
            # Wait until atleast one input is ready for reading
            readable_ports = select.select(self.inputs.values(), [], [])[0]
            if readable_ports:
                self.handle_inputs(readable_ports)
        time.sleep(5) # let any leftover processes die out
        self.f.close()
        self.end_life = True
        for port in self.inputs:
            self.inputs[port].close()

    def config_outputs(self, outputs):
        '''
        Load outputs into dictionary
        '''
        for output in outputs:
            if not (1 <= output.metric <= 16) or not (1024 <= output.port <= 49151):
                raise Exception("Invalid output parameters")
            self.outputs[output.id] = {
                'port': output.port,
                'metric': output.metric,
            }

    def config_inputs(self, inputs):
        '''
        Open a UDP socket for each input
        '''
        for port in inputs:
            try:
                self.inputs[port] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.inputs[port].setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.inputs[port].bind((self.host, port))

                print(f"#{self.id} Router - {port} port socket created")
            except socket.error as err:
                print(f"{self.id} Router - ERROR creating socket {port}:\n{err}")
                sys.exit()

    def handle_inputs(self, readable_ports):
        '''
        Receive packets an update routing table as necessary
        '''

        for port in readable_ports:
            packet = Packet(data = port.recvfrom(1024)[0])
            self.update_routing_table(packet)

        # If routing table changed force trigger an update call to all outputs
        if self.changed:
            self.log_routing_table() # log table on change
            print(f"#{self.id} Router - routing table change logged")

            changed_rtes = []
            for rte in self.routing_table.values():
                if rte.changed:
                    changed_rtes.append(rte)
                    rte.changed = False

            self.changed = False
            
            delay = 2 # send update with simulated 2 second delay
            threading.Timer(delay, self.update, [changed_rtes])


    def config_io(self):
        '''
        Create {router id}_log.txt file to which every routing table update will be logged
        '''

        filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), "router_logs", f"{self.id}_log.txt")

        try:
            self.f = open(filepath, 'w')
        except IOError:
            print(f"{self.id} Router - ERROR opening file: {filepath}\n")
    
    def log_routing_table(self):
        '''
        log the routing table
        '''
        header = (
            "+-------------+----------+------------+--------------+------------+\n"
            f"|                  Router #{self.id}  Routing Table                       |\n"
            "+-------------+----------+------------+--------------+------------+\n"
            "| destination |  metric  |  next hop  |  is changed  | is garbage |\n"
            "+-------------+----------+------------+--------------+------------+\n"
        )
       
        header += repr(self.routing_table[self.id])
        header += "|_____________|__________|____________|______________|____________|\n"
        header += "+-------------+----------+------------+--------------+------------+\n"

        rtes = ''
        for entry in self.routing_table:
            if entry != self.id:
                rtes += repr(self.routing_table[entry])
                rtes += "+-------------+----------+------------+--------------+------------+\n"

        self.f.write(header)
        self.f.write(rtes)
        self.f.write('\n')

    def update_routing_table(self, packet):
        '''
        Check if packet has better paths and update the tabel accordingly
        '''

        for rte in packet.rtes:
            # ignore own RTE
            if rte.addr != self.id:

                # Fetch existing RTE if route table contains one
                current_rte = self.routing_table.get(rte.addr)

                # Next hop - packet sender source router
                rte.set_next_hop(packet.header.src)
                # Either metric to src + received metric or 16 - unreachable
                rte.metric = min(rte.metric + self.outputs[packet.header.src]['metric'], RTE.MAX_METRIC)
                
                # New Route
                if not current_rte:
                    # Ignore if unreachable
                    if rte.metric == RTE.MAX_METRIC:
                        return

                    # Set change flags and add to routing table
                    rte.changed = True
                    self.changed = True
                    self.routing_table[rte.addr] = rte
                    return

                # Route exists
                else:
                    if rte.next_hop == current_rte.next_hop:

                        # Existing route became unreachable
                        if current_rte.metric != rte.metric and rte.metric >= RTE.MAX_METRIC:
                            current_rte.metric = RTE.MAX_METRIC
                            current_rte.is_garbage = True
                            current_rte.changed = True
                            self.changed = True

                        # Existing route changed metric
                        elif current_rte.metric != rte.metric:
                            self.update_route(current_rte, rte)

                        # Existing route didn't change
                        elif not current_rte.is_garbage:
                            current_rte.init_timeout() 
                
                    # Better route through another router
                    elif rte.metric < current_rte.metric:
                        self.update_route(current_rte, rte)
    
    def update_route(self, current_rte, rte):
        '''
        Update an existing RTE with new info
        '''

        current_rte.init_timeout()
        current_rte.is_garbage = False
        current_rte.changed = True
        current_rte.metric = rte.metric
        current_rte.next_hop = rte.next_hop
        self.changed = True     

    def update(self, rtes):
        '''
        Send update to all outputs
        '''
        if self.inputs != {}:

            sock = list(self.inputs.values())[0]
            local_header = Header(router_id=self.id)

            for output in self.outputs:

                validated_rtes = []
                for entry in rtes:
                    if entry.next_hop != output:
                        validated_rtes.append(entry)
                    else:
                        # Split horizon with poisoned reverse - if next_hop is destination output, set metric to unreachable
                        validated_rtes.append(
                            RTE(raw_data=None,
                                src_id=None, address=entry.addr,
                                next_hop=entry.next_hop, metric= RTE.MAX_METRIC,
                                imported=entry.imported)
                        )
            
                packet = Packet(header = local_header, rtes = validated_rtes)

                # Send
                sock.sendto(packet.serialize(),(self.host, self.outputs[output]["port"]))

    def timer(self, function, param=None):
        '''
        Call specified function every {TIMER} seconds
        '''
        # Stop timer if end flag set
        if self.end_life == True:
            return

        if param != None:
            function(list(param.values()))
            period = self.TIMER # * randrange(8, 12, 1) / 10
        else:
            period = self.TIMER
            function()

        threading.Timer(period, self.timer, [function, param]).start()

    def check_timeout(self):
        '''
        Check every RTE in routing table
        If timeout has passed, mark RTE as garbage and set metric to max
        '''

        if self.routing_table != {}:

            for rte in self.routing_table.values():
                if rte.timeout != None and (datetime.datetime.now() - rte.timeout).total_seconds() >= self.ROUTE_TIMEOUT:
                    rte.is_garbage = True
                    rte.changed = True
                    self.changed = True
                    rte.metric = RTE.MAX_METRIC
                    rte.timeout = datetime.datetime.now()
                    self.log_routing_table()

    def check_is_garbage(self):
        '''
        If RTE's are marked as garbage and their timeout tag exceeds DELETE_TIMEOUT, delete them
        '''

        if self.routing_table != {}:
            to_delete = []
            for rte in self.routing_table.values():
                if rte.is_garbage and (datetime.datetime.now() - rte.timeout).total_seconds() >= self.DELETE_TIMEOUT:
                    to_delete.append(rte.addr)

            for entry in to_delete:
                del self.routing_table[entry]
        
            if len(to_delete) > 0:
                self.log_routing_table()


    def config_timers(self):
        '''
        Start timers on: periodic update, RTE timeout and RTE deletion
        '''
        self.timer(self.update, param=self.routing_table)
        self.timer(self.check_timeout)
        self.timer(self.check_is_garbage)
