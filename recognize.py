import fingerprint
import decoder
import numpy
import pyaudio
import time


class BaseRecognizer(object):

    def __init__(self, fingermusic):
        self.fingermusic = fingermusic
        self.Fs = fingerprint.DEFAULT_FS

    def _recognize(self, *data):
        matches = []
        for d in data:
            matches.extend(self.fingermusic.find_matches(d, Fs=self.Fs))
        return self.fingermusic.align_matches(matches)

    def recognize(self):
        pass  # base class does nothing


class MicrophoneRecognizer(BaseRecognizer):
    default_chunksize   = 8192
    default_format      = pyaudio.paInt16
    default_channels    = 2
    default_samplerate  = 44100

    def __init__(self, dejavu):
        super(MicrophoneRecognizer, self).__init__(dejavu)
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.data = []
        self.channels = MicrophoneRecognizer.default_channels
        self.chunksize = MicrophoneRecognizer.default_chunksize
        self.samplerate = MicrophoneRecognizer.default_samplerate
        self.recorded = False

    def start_recording(self, channels=default_channels,
                        samplerate=default_samplerate,
                        chunksize=default_chunksize):
        self.chunksize = chunksize
        self.channels = channels
        self.recorded = False
        self.samplerate = samplerate

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        self.stream = self.audio.open(
            format=self.default_format,
            channels=channels,
            rate=samplerate,
            input=True,
            frames_per_buffer=chunksize,
        )

        self.data = [[] for i in range(channels)]

    def process_recording(self):
        data = self.stream.read(self.chunksize)
        nums = numpy.fromstring(data, numpy.int16)
        for c in range(self.channels):
            self.data[c].extend(nums[c::self.channels])

    def stop_recording(self):
        self.stream.stop_stream()
        self.stream.close()
        self.stream = None
        self.recorded = True

    def recognize_recording(self):
        if not self.recorded:
            raise NoRecordingError("Recording was not complete/begun")
        return self._recognize(*self.data)

    def get_recorded_time(self):
        return len(self.data[0]) / self.rate

    def recognize(self, seconds=10):
        self.start_recording()
        for i in range(0, int(self.samplerate / self.chunksize
                              * seconds)):
            self.process_recording()
        self.stop_recording()
        return self.recognize_recording()


class NoRecordingError(Exception):
    pass
