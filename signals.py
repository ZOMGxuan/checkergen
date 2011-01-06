"""Module for signalling upon stimuli appearance using the serial or 
parallel ports."""

SERPORT = None
PARPORT = None
STATE = None
GROUP_START = 42 # 0b00101010
GROUP_STOP = 17 # 0b00010001

available = {'serial': False, 'parallel': False}

try:
    import serial

    try:
        test_port = serial.Serial(0)
        test_port.close()
        del test_port
        available['serial'] = True
    except serial.serialutil.SerialException:
        pass
except ImportError:
    pass

try:
    import parallel
    try:
        test_port = parallel.Parallel()
        del test_port
        available['parallel'] = True
    except:
        pass
except ImportError:
    pass

if available['serial']:
    def ser_init():
        global SERPORT
        SERPORT = serial.Serial(0)

    def ser_send():
        global SERPORT
        global STATE
        if STATE != None:
            SERPORT.write(str(STATE))

    def ser_quit():
        global SERPORT
        SERPORT.close()
        SERPORT = None
else:
    msg = 'serial port functionality not available'
    def ser_init(msg=msg):
        raise NotImplementedError(msg)

    def ser_send(msg=msg):
        raise NotImplementedError(msg)

    def ser_quit(msg=msg):
        raise NotImplementedError(msg)

if available['parallel']:
    def par_init():
        global PARPORT
        PARPORT = parallel.Parallel()
        PARPORT.setData(0)

    def par_send():
        global PARPORT
        global STATE
        if STATE != None:
            PARPORT.setData(PARSTATE)
        else:
            PARPORT.setData(0)

    def par_quit():
        global PARPORT
        PARPORT.setData(0)
        PARPORT = None
else:
    msg = 'parallel port functionality not available'
    def par_init(msg=msg):
        raise NotImplementedError(msg)

    def par_send():
        raise NotImplementedError(msg)

    def par_quit(msg=msg):
        raise NotImplementedError(msg)

def init(sigser, sigpar):
    global STATE
    STATE = None
    if sigser:
        ser_init()
    if sigpar:
        par_init()

def set_start():
    global STATE
    STATE = GROUP_START

def set_stop():
    global STATE
    STATE = GROUP_STOP

def set_null():
    global STATE
    STATE = None

def send(sigser, sigpar):
    if sigser:
        ser_send()
    if sigpar:
        par_send()

def quit(sigser, sigpar):
    global STATE
    STATE = None
    if sigser:
        ser_quit()
    if sigpar:
        par_quit()
    
