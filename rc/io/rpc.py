#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
from   tfm.rc.compatibility    import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
from   tfm.rc.io.timeoutclient import TimeoutServerProxy
from   tfm.rc.threading        import threaded

import TRACE

import contextlib
import select
import threading

class StoppableRPCServer(SimpleXMLRPCServer):
    """
    Adapted from http://bit.ly/nkXWKH, except that we actually wait
    for last request to complete since otherwise this fails sometimes,
    at least on Ubuntu
    """
    allow_reuse_address = True

    def __init__(self, address, timeout=0.1):
        # print("rpc.py:  address = ",address)
        # breakpoint()
        SimpleXMLRPCServer.__init__(self,
                                    address,
                                    requestHandler=SimpleXMLRPCRequestHandler,
                                    logRequests=False,
                                    allow_none=True)
        self.__is_shut_down = threading.Event()
        self.__is_shut_down.clear()
        self.timeout   = timeout
        self.__stopped = False

    def serve_forever(self):
        while not self.__stopped:
            try:
                self.handle_request()
            except select.error:  # no-coverage
                return
        self.__is_shut_down.set()

    def stop(self):
        self.__stopped = True
        self.__is_shut_down.wait()
        self.server_close()


@contextlib.contextmanager
def rpc_server(host='', port=6000, funcs={}, timeout=0.01):
    TRACE.TRACE(7,f"EMOE 000: host:{host} port:{port}","rpc.py")
    server = StoppableRPCServer((host, port), timeout=timeout)
    TRACE.TRACE(7,f"EMOE 001: host:{host} port:{port}","rpc.py")
    with threaded(target=server.serve_forever,name=f'rpc-server-{host}-{port}'):
        TRACE.TRACE(7,"EMOE 002 in the loop, I guess","rpc.py")
        for name, func in funcs.items():
            server.register_function(func, name)
        try:
            yield
        finally:
            # server.stop()
            TRACE.TRACE(7,"EMOE 003","rpc.py")

    TRACE.TRACE(7,"004 DONE","rpc.py")

@contextlib.contextmanager
def rpc_client(host="localhost", port=6000, timeout=30):
    client = TimeoutServerProxy("http://%s:%s" % (host, port), timeout)
    yield client
