import numpy as np
import matplotlib.mlab as mlab
#from scipy.ndimage.filters import maximum_filter
#from scipy.ndimage.morphology import (generate_binary_structure,iterate_structure, binary_erosion)
#from scipy.fftpack import dct
import hashlib
import scipy.ndimage as ndi


IDX_FREQ_I = 0
IDX_TIME_J = 1

DEFAULT_FS = 44100
DEFAULT_WINDOW_SIZE = 4096
DEFAULT_OVERLAP_RATIO = 0.5
DEFAULT_FAN_VALUE = 15

DEFAULT_AMP_MIN = 10
PEAK_NEIGHBORHOOD_SIZE = 40
MIN_HASH_TIME_DELTA = 0


def fingerprint(channel_samples, Fs=DEFAULT_FS, wsize=DEFAULT_WINDOW_SIZE, wratio=DEFAULT_OVERLAP_RATIO, fan_value=DEFAULT_FAN_VALUE, amp_min=DEFAULT_AMP_MIN):
    """
    FFT the channel, loklsg transform output, find local maxima, then return
    locally sensitive hashes.
    """


    # FFT the signal and extract frequency components
    arr2D = mlab.specgram(
        channel_samples,
        NFFT=wsize,
        Fs=Fs,
        window=mlab.window_hanning,
        noverlap=int(wsize * wratio))[0]

    # apply log transform since specgram() returns linear array
    np.seterr(all='ignore')
    arr2D = 10 * np.log10(arr2D)
    arr2D[arr2D == -np.inf] = 0  # replace infs with zeros

    # find local maxima
    local_maxima = peak_local_max(arr2D)

    # return hashes
    return generate_hashes(local_maxima, fan_value=fan_value)


def peak_local_max(image, min_distance=10, threshold_abs=0, threshold_rel=0.1,
                   exclude_border=True, indices=True, num_peaks=np.inf,
                   footprint=None, labels=None):

    out = np.zeros_like(image, dtype=np.bool)
    # In the case of labels, recursively build and return an output
    # operating on each label separately
    if labels is not None:
        label_values = np.unique(labels)
        # Reorder label values to have consecutive integers (no gaps)
        if np.any(np.diff(label_values) != 1):
            mask = labels >= 1
            labels[mask] = 1 + rank_order(labels[mask])[0].astype(labels.dtype)
        labels = labels.astype(np.int32)

        # New values for new ordering
        label_values = np.unique(labels)
        for label in label_values[label_values != 0]:
            maskim = (labels == label)
            out += peak_local_max(image * maskim, min_distance=min_distance,
                                  threshold_abs=threshold_abs,
                                  threshold_rel=threshold_rel,
                                  exclude_border=exclude_border,
                                  indices=False, num_peaks=np.inf,
                                  footprint=footprint, labels=None)

        if indices is True:
            return np.transpose(out.nonzero())
        else:
            return out.astype(np.bool)

    if np.all(image == image.flat[0]):
        if indices is True:
            return []
        else:
            return out

    image = image.copy()
    # Non maximum filter
    if footprint is not None:
        image_max = ndi.maximum_filter(image, footprint=footprint,
                                       mode='constant') == image
    else:
        size = 2 * min_distance + 1
        image_max = ndi.maximum_filter(image, size=size, mode='constant') == image
    '''mask = (image == image_max)
    image *= mask'''
    
    
    # extract peaks
    amps = image[image_max]
    j, i = np.where(image_max)

    # filter peaks
    amps = amps.flatten()
    peaks = zip(i, j, amps)
    peaks_filtered = [x for x in peaks if x[2] > DEFAULT_AMP_MIN]  # freq, time, amp

    # get indices for frequency and time
    frequency_idx = [x[1] for x in peaks_filtered]
    time_idx = [x[0] for x in peaks_filtered]

    
    '''if exclude_border:
        # zero out the image borders
        for i in range(image.ndim):
            image = image.swapaxes(0, i)
            image[:min_distance] = 0
            image[-min_distance:] = 0
            image = image.swapaxes(0, i)

    # find top peak candidates above a threshold
    peak_threshold = max(np.max(image.ravel()) * threshold_rel, threshold_abs)

    # get coordinates of peaks
    coordinates = np.transpose((image > peak_threshold).nonzero())

    if coordinates.shape[0] > num_peaks:
        intensities = image[coordinates[:, 0], coordinates[:, 1]]
        idx_maxsort = np.argsort(intensities)[::-1]
        coordinates = coordinates[idx_maxsort][:num_peaks]'''

    if indices is True:
        return zip(frequency_idx, time_idx)
    else:
        nd_indices = zip(frequency_idx, time_idx)
        out[nd_indices] = True
        return out

'''def get_2D_peaks(arr2D, plot=False, amp_min=DEFAULT_AMP_MIN):
    struct = generate_binary_structure(2, 1)
    neighborhood = iterate_structure(struct, PEAK_NEIGHBORHOOD_SIZE)

    print 1
    # find local maxima using our fliter shape
    local_max = maximum_filter(arr2D, footprint=neighborhood) == arr2D
    print 2
    background = (arr2D == 0)
    print 3
    eroded_background = binary_erosion(background, structure=neighborhood,
                                       border_value=1)

    # Boolean mask of arr2D with True at peaks
    detected_peaks = local_max - eroded_background

    # extract peaks
    amps = arr2D[detected_peaks]
    j, i = np.where(detected_peaks)

    # filter peaks
    amps = amps.flatten()
    peaks = zip(i, j, amps)
    peaks_filtered = [x for x in peaks if x[2] > amp_min]  # freq, time, amp

    # get indices for frequency and time
    frequency_idx = [x[1] for x in peaks_filtered]
    time_idx = [x[0] for x in peaks_filtered]

    return zip(frequency_idx, time_idx)'''


def generate_hashes(peaks, fan_value=DEFAULT_FAN_VALUE):
    """
    Hash list structure:
       sha1_hash[0:20]    time_offset
    [(e05b341a9b77a51fd26, 32), ... ]
    """
    fingerprinted = set()  # to avoid rehashing same pairs

    for i in range(len(peaks)):
        for j in range(fan_value):
            if (i + j) < len(peaks) and not (i, i + j) in fingerprinted:
                freq1 = peaks[i][IDX_FREQ_I]
                freq2 = peaks[i + j][IDX_FREQ_I]

                t1 = peaks[i][IDX_TIME_J]
                t2 = peaks[i + j][IDX_TIME_J]

                t_delta = t2 - t1

                if t_delta >= MIN_HASH_TIME_DELTA:
                    h = hashlib.sha1("%s|%s|%s" % (str(freq1), str(freq2), str(t_delta)))
                    yield (h.hexdigest()[0:20], t1)

                # ensure we don't repeat hashing
                fingerprinted.add((i, i + j))
