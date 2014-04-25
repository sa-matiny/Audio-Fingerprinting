from database import get_database
import decoder
import fingerprint
import multiprocessing
import os
from recognize import MicrophoneRecognizer
import MySQLdb

class FingerMusics(object):
    def __init__(self, config):
        super(FingerMusics, self).__init__()

        self.config = config

        # initialize db
        db_cls = get_database(config.get("database_type", None))

        self.db = db_cls(**config.get("database", {}))
        self.db.setup()

    # if we should limit seconds fingerprinted,
        # None|-1 means use entire track
        self.limit = self.config.get("fingerprint_limit", None)
        if self.limit == -1: # for JSON compatibility
            self.limit = None


    # get songs previously indexed
        self.songs = self.db.get_songs()
        self.songnames_set = set()  # to know which ones we've computed before
        for song in self.songs:
            song_name = song[self.db.FIELD_SONGNAME]
            self.songnames_set.add(song_name)
            print "Added: %s to the set of fingerprinted songs..." % song_name

    def fingerprint_directory(self, path, extensions, nprocesses=None):

        filenames_to_fingerprint = []
        for filename, _ in decoder.find_files(path, extensions):

            # don't refingerprint already fingerprinted files
            if decoder.path_to_songname(filename) in self.songnames_set:
                print "%s already fingerprinted, continuing..." % filename
                continue

            filenames_to_fingerprint.append(filename)
        print filenames_to_fingerprint

        for files in filenames_to_fingerprint:
            song_name, hashes = _fingerprint_worker(files,self.limit)
            print song_name
            #print hashes
            sid = self.db.insert_song(song_name)
            self.db.insert_hashes(sid, hashes)

    def fingerprint_file(self, filepath, song_name=None):
        song_name, hashes = _fingerprint_worker(filepath, self.limit, song_name=song_name)
        sid = self.db.insert_song(song_name)
        self.db.insert_hashes(sid, hashes)

    def find_matches(self, samples, Fs=fingerprint.DEFAULT_FS):
        hashes = fingerprint.fingerprint(samples, Fs=Fs)
        return self.db.return_matches(hashes)

    def align_matches(self, matches):
        """
            Finds hash matches that align in time with other matches and finds
            consensus about which hashes are "true" signal from the audio.

            Returns a dictionary with match information.
        """
        # align by diffs
        diff_counter = {}
        largest = 0
        largest_count = 0
        song_id = -1
        for tup in matches:
            sid, diff = tup
            if not diff in diff_counter:
                diff_counter[diff] = {}
            if not sid in diff_counter[diff]:
                diff_counter[diff][sid] = 0
            diff_counter[diff][sid] += 1

            if diff_counter[diff][sid] > largest_count:
                largest = diff
                largest_count = diff_counter[diff][sid]
                song_id = sid

        print("Diff is %d with %d offset-aligned matches" % (largest,
                                                             largest_count))

        # extract idenfication
        song = self.db.get_song_by_id(song_id)
        if song:
            songname = song.get("song_name", None)
        else:
            return None

        # return match info
        song = {
            "song_id": song_id,
            "song_name": songname,
            "confidence": largest_count,
            "offset": largest
        }

        return song

    def recognize(self, recognizer, *options, **kwoptions):
        r = recognizer(self)
        return r.recognize(*options, **kwoptions)
            
def _fingerprint_worker(filename, limit=None, song_name=None):
    songname, extension = os.path.splitext(os.path.basename(filename))
    song_name = song_name or songname

    channels, Fs = decoder.read(filename, limit)

    result = set()

    channel_amount = len(channels)
    for i in range(channel_amount):
        print("Fingerprinting channel %d/%d for %s" % (i + 1,channel_amount,filename))
        hashes = fingerprint.fingerprint(channels[i], Fs=Fs)
        print("Finished channel %d/%d for %s" % (i + 1, channel_amount,filename))
        result |= set(hashes)

    return song_name, result

pas = raw_input('Input your MYSQLdb password\n')

db = MySQLdb.connect(user="root",passwd=pas)
cursor = db.cursor()
cursor.execute('CREATE DATABASE IF NOT EXISTS mymusic')

config = {
	"database": {
		"host": "127.0.0.1",
		"user": "root",
		"passwd": pas, 
		"db": "mymusic",
	}
}
musics = FingerMusics(config)

musics.fingerprint_directory("music", [".mp3"])

print musics.db.get_num_fingerprints()
