try:
    import RPi.GPIO as GPIO

    HAVE_GPIO = True
except ImportError:

    class GPIO:
        LOW = None
        HIGH = None
        IN = None
        BCM = None
        OUT = None

        @staticmethod
        def setmode(mode):
            pass

        @staticmethod
        def setup(pin, direction):
            pass

        @staticmethod
        def output(pin, value):
            pass

        @staticmethod
        def cleanup(pin=None):
            pass

        @staticmethod
        def getmode():
            return None

        @staticmethod
        def gpio_function(pin):
            return None

    HAVE_GPIO = False


def is_rpi() -> bool:
    return HAVE_GPIO
