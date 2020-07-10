import time
from threading import Thread
import sys
import os
from router import Router, RouterConfig, Output

HOST = '127.0.0.1'
ROUTER_LIFESPAN = 60
ROUTERS_MAX = 8
ROUTERS_FILE="routers.txt"

def main():
    # Read and parse /routers directory
    try:
        router_configs =  read_router_files()
    except Exception as e:
        print(e)
        sys.exit(1)

    # Create router_logs directory
    if not os.path.exists("router_logs"):
        os.mkdir("router_logs")

    # Start threads for every router and wait until they join
    threads = []
    for router in router_configs:
        threads.append(Thread(target = run_router, args = (router,)))

    for t in threads:
        t.start()

    time.sleep(0.0001)

    for t in threads:
        t.join()
  

def run_router(routercfg):
    router = Router(config = routercfg, host = HOST, lifespan = ROUTER_LIFESPAN)
    # Wait for ports to configure, prevents multithreading-socket specific annoyances
    time.sleep(2)
    router.run()

def read_router_files():

  # helper function - {id}:{port}:{metric} templated output to Output class
  def _to_output(output_string):
      output_list = output_string.strip().split(':')
      return Output(
          int(output_list[0]),
          int(output_list[1]),
          int(output_list[2])
      )
  
  router_configs = []
  f = open(ROUTERS_FILE, 'r')
  lines = f.readlines()

  if lines.pop(0).strip() != '[ROUTERS]':
      raise Exception(f"Improper formatting in {ROUTERS_FILE}, refer to readme.txt")

  while len(lines) != 0:

      # File formatting check
      if (
          lines[0][:3] != 'id:' or
          lines[1][:7] != 'inputs:' or
          lines[2][:8] != 'outputs:' or
          (len(lines) >= 4 and lines[3].strip() != '')
      ):
          raise Exception(f"Improper formatting in {ROUTERS_FILE}, refer to readme.txt")

      # Parsing
      try:
          id = int(lines[0][3:].strip())
          inputs = [int(i.strip()) for i in lines[1][7:].strip().split(',')]
          outputs = [_to_output(i) for i in lines[2][8:].strip().split(',')]

      except Exception as e:
          raise  Exception(f"Improper formatting in {ROUTERS_FILE}, refer to readme.txt")

      router_configs.append(
          RouterConfig(
            id = id,
            inputs = inputs,
            outputs = outputs
          )
      )

      lines = lines[4:] if len(lines) >= 4 else []
  
  if len(router_configs) > ROUTERS_MAX:
      raise Exception(f"Too many routers defined in routers.txt, maximum: {ROUTERS_MAX}")\

  return router_configs

if __name__ == "__main__":
    main()