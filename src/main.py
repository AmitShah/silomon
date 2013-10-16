'''
Created on Aug 8, 2013

@author: amitshah
'''
from mailgun import *
from bluerover import Api
import ssl,socket,sys
import os,tornado
from tornado.httpserver import HTTPServer
from tornado.websocket import WebSocketHandler
import sys,functools,json
from threading import Lock
import datetime,logging, threading

logger = logging.getLogger('sensor_main')
logger.setLevel(logging.INFO)

fh = logging.FileHandler('sensor.log')
fh.setLevel(logging.INFO)
logger.addHandler(fh)


'''helper method to handle casting of improper chars'''
def ignore_exception(IgnoreException=Exception,DefaultVal=None):
    """ Decorator for ignoring exception from a function
    e.g.   @ignore_exception(DivideByZero)
    e.g.2. ignore_exception(DivideByZero)(Divide)(2/0)
    """
    def dec(function):
        def _dec(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except IgnoreException:
                return DefaultVal
        return _dec
    return dec

sint = ignore_exception(IgnoreException=ValueError)(int)

class Observer(object):
    
    def __init__(self):
        self._observers = []
        
    def attach(self, observer):
        if not observer in self._observers:
            self._observers.append(observer)

    def detach(self, observer):
        try:
            self._observers.remove(observer)
        except ValueError:
            pass

    def notify(self, msg):    
        for observer in self._observers:
            observer(message=msg)

from threading import RLock

class EventObserver(Observer):
    state = dict()    
    def __init__(self):
        Observer.__init__(self)
        pass
    
    def notify(self, message):
        try:
            event = json.loads(message)        
            if not isinstance(event,(int,long)) and 'rfidTagNum' in event:
                EventObserver.state[event['rfidTagNum']] = event
                Observer.notify(self, json.dumps(EventObserver.state))
        except:            
            pass
    
        
'''Look for new line characters and notify all observer per line '''
class LineObserver(EventObserver):
    def __init__(self):
        EventObserver.__init__(self)
        self.buffer = ''
        self.rlock = RLock()
    '''we need to protect buffer from async calls :('''        
    def notify(self,message):
        try:              
            #prevent multiple async calls from overriding the buffer while in processing  
            with self.rlock:                
                self.buffer= self.buffer+message                
                while "\n" in self.buffer:
                    (line, self.buffer) = self.buffer.split("\n", 1)
                    data = line.strip() #remove blank lines (when keep alive is sent from server)
                    if data:
                        logger.info(('sending buffered data:%s' % self.buffer))
                        EventObserver.notify(self, data)                            
        except:
            pass
        finally:
            pass
        

    
    
class BaseHandler(tornado.web.RequestHandler):        
    def initialize(self,api,event_state):
        self.api = api
        self.event_state = event_state
        pass
    
    def get_current_user(self):
        '''used for web api administration access'''
        #self.account_service.getUserWithPassword()
        user = self.get_secure_cookie('user')
        if user is not None:            
            user = json.loads(self.get_secure_cookie("user"))
        return user


        
class UpdateHandler(WebSocketHandler):
    
    observer = LineObserver()
    
    def open(self):
        UpdateHandler.observer.attach(self)
        self(json.dumps(UpdateHandler.observer.state))
        
    def on_message(self, message):
        cmd = json.loads(message)
        pass
    
    def on_close(self):
        UpdateHandler.observer.detach(self)
        
    def broadcast_as_json(self,message):
        self.write_message(json.encoder.encode_basestring(message))
        
    def __call__(self,message=None):
        self.broadcast_as_json(message)

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('silo.html')
  
class RfidsHandler(BaseHandler):    
    def post(self):
        json_rfid= self.api.call_api("/rfid", {})
        self.write(json_rfid)          

class DevicesHandler(BaseHandler):
    def post(self):
        devices = self.api.call_api("/device",{})
        self.write(devices)
  
if __name__ == '__main__':
    
    '''let setup tcp connection to the upstream service to get sensor data 
    and handle this data with a async socket read for distribution :) '''
    
    api = Api(token='9DquKlyhPKpZ35mxcjG/JUqWAd//U12O13ja6Wqp',
              key='yXIJ1omZUNtbo6wNjMOkKYBLNJakn0nr/OzgVtDKh2i5lDktVT2xv5xfbYlCkW+Z',
              base_url='https://developers.polairus.com')
    
    sock = socket.socket()    
    s = ssl.wrap_socket(sock)
    
    def connect_to_service():        
        s.connect(('developers.polairus.com',443))    
        s.sendall(api.create_eventstream_request())
        pass
    
    def data_handler(sock,fd,events):
        try:                    
            data = sock.recv(4096)
            logger.info(('received data:%s' % data))
            UpdateHandler.observer.notify(data)        
        except:
            sock.close()
            tornado.ioloop.IOLoop.instance().add_timeout(datetime.timedelta(seconds=30), connect_to_service)            
        pass

    callback = functools.partial(data_handler, s)
    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.add_handler(s.fileno(), callback, ioloop.READ)    
    ioloop.add_callback(connect_to_service)
    
    #define all the services
    services = dict(
        api = api,
        event_state = None
        )
    
    settings = dict(
        template_path=os.path.join(os.path.dirname(__file__), "template"),
        static_path=os.path.join(os.path.dirname(__file__), "static"),
        cookie_secret= 'secret_key',
        login_url='/login'
        )
      
    application = tornado.web.Application([
    (r"/update", UpdateHandler),
    (r"/rfids", RfidsHandler, services),
    (r"/devices", DevicesHandler, services),
    (r"/*", MainHandler),
          
    ], **settings)
    
    sockets = tornado.netutil.bind_sockets(9999)
    server = HTTPServer(application)
    server.add_sockets(sockets)
    
    #pc.start()
    ioloop.start()
    
