# An Extremely simple demonstrative implementation of the ripv2 routing protocol

Outputs appear after execution in the /router_logs directory
These are routing tables after every update that added new information
Since routers need to transfer data bilaterally one connection between two router will take up 2 ports one in router A, and one in router B, communication is performed by sending data to the corresponding receiving UDP port. Each new connection creates another port in both routers.
Routers are defined in the routers.txt file following these rules:

1. Each router has a separate id where 0 <= id <=8

2. File has a header with the text "[ROUTERS]"

2. Each router has exactly 3 lines with the following formatting:

  id: {router id}
  inputs: {port1}
  outputs: {router id}:{router port}:{metric}

3. Formatting rules:

  id is a single integer
  outputs refer to DESTINATION router id, port and metric
  multiple inputs/outputs are separated by commas e.g.

    id: 5
    inputs: 3000, 4000
    outputs: 1:1000:1, 2:2000:2, 3:3000:3

4. After each router a blank line is left, no blank line is left at the end of file.

An example main topology is included, along with corresponding routers.txt and router_logs outputs

You main want to configure router lifespan and maximum number of router in main.py

To Run:

python main.py via cli  
