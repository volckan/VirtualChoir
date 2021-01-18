#!/usr/bin/env python3

import argparse
import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import os
from scipy import signal
from pydub import AudioSegment, scipy_effects # pip install pydub
from pydub.playback import play

parser = argparse.ArgumentParser(description='virtual choir')
parser.add_argument('file', help='audio file')
args = parser.parse_args()

def custom_eq(sample, demud_gain=1.2, intel_gain=1.2):
    sample = sample.set_channels(1) # tmp
    sample = sample.set_sample_width(2)
    raw = sample.get_array_of_samples()
    
    print("eq-ing ...")
    bands = []

    sos = signal.butter(10, 100, 'lp', fs=sample.frame_rate, output='sos')
    filtered = signal.sosfilt(sos, raw).astype(float)
    bands.append(filtered)
    
    sos = signal.butter(10, [100, 250], 'bp', fs=sample.frame_rate, output='sos')
    filtered = signal.sosfilt(sos, raw).astype(float)
    bands.append(filtered)
    
    sos = signal.butter(10, [250, 300], 'bp', fs=sample.frame_rate, output='sos')
    filtered = signal.sosfilt(sos, raw).astype(float)
    bands.append(filtered * demud_gain)
    
    sos = signal.butter(10, [300, 2500], 'bp', fs=sample.frame_rate, output='sos')
    filtered = signal.sosfilt(sos, raw).astype(float)
    bands.append(filtered)
    
    sos = signal.butter(2, [2500, 3000], 'bp', fs=sample.frame_rate, output='sos')
    filtered = signal.sosfilt(sos, raw).astype(float)
    bands.append(filtered * intel_gain)
    
    sos = signal.butter(10, [3000, 5000], 'bp', fs=sample.frame_rate, output='sos')
    filtered = signal.sosfilt(sos, raw).astype(float)
    bands.append(filtered)
    
    sos = signal.butter(10, 5000, 'hp', fs=sample.frame_rate, output='sos')
    filtered = signal.sosfilt(sos, raw).astype(float)
    bands.append(filtered)
    
    result = bands[0]
    for b in bands[1:]:
        result += b

    plt.figure()

    fft = np.fft.rfft(raw)
    freq = np.fft.rfftfreq(len(raw), d=1/sample.frame_rate)
    plt.plot(freq, np.abs(fft), label="sample")

    fft = np.fft.rfft(result)
    freq = np.fft.rfftfreq(len(result), d=1/sample.frame_rate)
    plt.plot(freq, np.abs(fft), label="eq result")
    
    if True:
        for i, b in enumerate(bands[4:5]):
            fft = np.fft.rfft(b)
            freq = np.fft.rfftfreq(len(b), d=1/sample.frame_rate)
            plt.plot(freq, np.abs(fft), label="band %d" % i)
    
    plt.legend()

    plt.figure()
    plt.plot(raw, label="orig")
    plt.plot(result, label="eq")
    plt.legend()
    
    plt.show()

    return result

def blah_custom_eq(sample,
              low_db=0, demud_db=0, intel_db=0, air_db=0):
    sample.set_channels(1) # tmp
    
    print("eq-ing ...")
    bands = []
    bands.append( scipy_effects.low_pass_filter(sample, 100) + low_db )
    bands.append( scipy_effects.band_pass_filter(sample, 100, 250) )
    bands.append( scipy_effects.band_pass_filter(sample, 250, 300) + demud_db )
    bands.append( scipy_effects.band_pass_filter(sample, 300, 2500) )
    bands.append( scipy_effects.band_pass_filter(sample, 2500, 3000) + intel_db )
    bands.append( scipy_effects.band_pass_filter(sample, 3000, 10000) )
    bands.append( scipy_effects.band_pass_filter(sample, 10000, 16000) + air_db )
    bands.append( scipy_effects.high_pass_filter(sample, 16000) )
    result = bands[0]
    for b in bands[1:]:
        result = result.overlay(b)

    plt.figure()

    sample.set_channels(1)
    raw = sample.get_array_of_samples()
    fft = np.fft.rfft(raw)
    freq = np.fft.rfftfreq(len(raw), d=1/sample_rate)
    plt.plot(freq, np.abs(fft), label="sample")

    if True:
        for i, b in enumerate(bands[1:2]):
            b.set_channels(1)
            raw = b.get_array_of_samples()
            fft = np.fft.rfft(raw)
            freq = np.fft.rfftfreq(len(raw), d=1/sample_rate)
            plt.plot(freq, np.abs(fft), label="band %d" % i)
    
    result.set_channels(1)
    raw = result.get_array_of_samples()
    fft = np.fft.rfft(raw)
    freq = np.fft.rfftfreq(len(raw), d=1/sample_rate)
    plt.plot(freq, np.abs(fft), label="eq result")
    
    #fig, ax = plt.subplots(nrows=8, sharex=True, sharey=True)
    #oenv = librosa.onset.onset_strength(y=np.array(raw).astype('float'),
    #                                    sr=sample_rate,
    #                                    hop_length=hop_length)
    #t = librosa.times_like(oenv, sr=sample_rate, hop_length=hop_length)
    #chroma = librosa.feature.chroma_cqt(y=np.array(raw).astype('float'),
    #                                    sr=sample_rate,
    #                                    hop_length=hop_length)
    #img = librosa.display.specshow(chroma,
    #                               x_axis='time',
    #                               y_axis='chroma',
    #                               hop_length=int(hop_length*0.5), ax=ax[0])
    #fig.colorbar(img, ax=ax)a

    plt.legend()
    plt.show()

    return result

print("Loading sample:", args.file)
basename, ext = os.path.splitext(args.file)
sample = AudioSegment.from_file(args.file, ext[1:])
#result = blah_custom_eq(sample, 6, 6, 6, 6)
result = custom_eq(sample, 3, 3)
print(np.min(result), np.max(result))
result = np.int16(result)
eqd = AudioSegment(result.tobytes(), frame_rate=sample.frame_rate, sample_width=2, channels=1)
play(eqd)

sample.set_channels(1)

# direct
raw = sample.get_array_of_samples()
#b, a = signal.butter(4, 100, 'lp', analog=True)
b, a = signal.butter(10, [2500, 3000], 'bp', analog=True)
w, h = signal.freqs(b, a)
plt.semilogx(w, 20 * np.log10(abs(h)))
plt.title('Butterworth filter frequency response')
plt.xlabel('Frequency [radians / second]')
plt.ylabel('Amplitude [dB]')
plt.margins(0, 0.1)
plt.grid(which='both', axis='both')
plt.axvline(100, color='green') # cutoff frequency

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
ax1.plot(raw)
ax1.set_title('raw signal')
#ax1.axis([0, 1, -2, 2])

#sos = signal.butter(10, 15, 'hp', fs=sample.frame_rate, output='sos')
sos = signal.butter(2, 20000, 'lp', fs=sample.frame_rate, output='sos')
filtered = signal.sosfilt(sos, raw)
ax2.plot(filtered)
ax2.set_title('After 15 Hz high-pass filter')
#ax2.axis([0, 1, -2, 2])
ax2.set_xlabel('Time [seconds]')
plt.tight_layout()

plt.figure()
fft = np.fft.rfft(raw)
freq = np.fft.rfftfreq(len(raw), d=1/sample.frame_rate)
plt.plot(freq, np.abs(fft), label="sample")

fft = np.fft.rfft(filtered)
freq = np.fft.rfftfreq(len(filtered), d=1/sample.frame_rate)
plt.plot(freq, np.abs(fft), label="filtered")
plt.show()

result.set_channels(1)

print("plotting...")
plt.figure()
plt.plot(sample.get_array_of_samples(), label="orig")
plt.plot(result.get_array_of_samples(), label="eq")
plt.legend()
plt.show()

play(result)
