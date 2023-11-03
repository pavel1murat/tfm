# import contextlib
# import zmq
# from rc.compatibility import Queue
# from rc.threading import threadable
# from rc.util import stringify_times


# class Sender():
#     def __init__(self, ip='localhost', port=5000):
#         self.__context = zmq.Context()
#         self.__socket = self.__context.socket(zmq.PUSH)
#         self.__socket.setsockopt(zmq.LINGER, 10)
#         self.__socket.connect("tcp://%s:%s" % (ip, port))
#         self.addr = (ip, port)

#     def send(self, data):
#         self.__socket.send_json(stringify_times(data))

#     def sendraw(self, data):
#         self.__socket.send(data)

#     def close(self):
#         self.__socket.close()
#         self.__context.term()


# class PubSender():
#     def __init__(self, port=8000):
#         self.__context = zmq.Context()
#         self.__socket = self.__context.socket(zmq.PUB)
#         self.__socket.bind("tcp://*:%s" % port)

#     def send(self, data):
#         self.__socket.send_json(stringify_times(data))

#     def sendraw(self, data):
#         self.__socket.send(data)

#     def close(self):
#         self.__socket.close()
#         self.__context.term()


# @contextlib.contextmanager
# def sender(*args, **kwargs):
#     s = Sender(*args, **kwargs)
#     try:
#         yield s
#     finally:
#         s.close()


# @contextlib.contextmanager
# def pubsender(*args, **kwargs):
#     s = PubSender(*args, **kwargs)
#     try:
#         yield s
#     finally:
#         s.close()


# class Receiver():
#     def __init__(self, ip='localhost', port=5000):
#         if ip == 'localhost':
#             ip = '*'
#         self.__context = zmq.Context()
#         self.__socket = self.__context.socket(zmq.PULL)
#         self.__socket.bind("tcp://%s:%s" % (ip, port))
#         self.__socket.linger = 0

#     def recv_nonblock(self):
#         try:
#             ret = self.__socket.recv_json(flags=zmq.NOBLOCK)
#             return ret
#         except zmq.ZMQError as e:
#             if e.errno == zmq.EAGAIN:
#                 return None
#             raise  # no-coverage

#     def stop(self):
#         self.__socket.close()
#         self.__context.term()


# @contextlib.contextmanager
# def receiver(*args, **kwargs):
#     r = Receiver(*args, **kwargs)
#     try:
#         yield r
#     finally:
#         r.stop()


# @contextlib.contextmanager
# def threaded_receiver(rargs={}, targs={}, func=lambda m: None):
#     with receiver(**rargs) as r:

#         def get_messages():
#             while True:
#                 msg = r.recv_nonblock()
#                 if msg:
#                     func(msg)
#                 else:
#                     return

#         targs["func"] = get_messages
#         with threadable(**targs) as t:
#             yield r, t


# @contextlib.contextmanager
# def queueing_receiver(rargs={}, targs={}):
#     q = Queue.Queue()
#     with threaded_receiver(rargs=rargs, targs=targs, func=q.put) as (r, t):
#         yield q, t
