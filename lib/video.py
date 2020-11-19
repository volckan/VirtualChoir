import cv2
import json
import math
import numpy as np
import os
from pydub import AudioSegment
import skvideo.io               # pip install sk-video
from subprocess import call
from tqdm import tqdm

from .logger import log

def gen_dicts(fps, quality="sane"):
    inputdict = {
        '-r': str(fps)
    }
    if quality == "sane":
        outputdict = {
            # See all options: https://trac.ffmpeg.org/wiki/Encode/H.264
            '-vcodec': 'libx264',  # use the h.264 codec
            '-pix_fmt': 'yuv420p', # support 'dumb' players
            '-crf': '17',          # visually lossless (or nearly so)
            '-preset': 'medium',   # default compression
            '-r': str(fps)         # fps
        }
    elif quality == "lossless":
        outputdict = {
            # See all options: https://trac.ffmpeg.org/wiki/Encode/H.264
            '-vcodec': 'libx264',  # use the h.264 codec
            '-pix_fmt': 'yuv420p', # support 'dumb' players
            '-crf': '0',           # set the constant rate factor to 0, (lossless)
            '-preset': 'veryslow', # maximum compression
            '-r': str(fps)         # fps
        }
    return inputdict, outputdict

class VideoTrack:
    def __init__(self):
        self.reader = None

    def open(self, file):
        print("video:", file)
        metadata = skvideo.io.ffprobe(file)
        #print(metadata.keys())
        if not "video" in metadata:
            return False
        #print(json.dumps(metadata["video"], indent=4))
        fps_string = metadata['video']['@r_frame_rate']
        (num, den) = fps_string.split('/')
        self.fps = float(num) / float(den)
        if self.fps < 1 or self.fps > 120:
            # something crazy happened let's try something else
            fps_string = metadata['video']['@avg_frame_rate']
            (num, den) = fps_string.split('/')
            self.fps = float(num) / float(den)

        self.fps = float(num) / float(den)
        codec = metadata['video']['@codec_long_name']
        self.w = int(metadata['video']['@width'])
        self.h = int(metadata['video']['@height'])
        if '@duration' in metadata['video']:
            self.duration = float(metadata['video']['@duration'])
        else:
            self.duration = 1
        self.total_frames = int(round(self.duration * self.fps))
        self.frame_counter = -1
        self.frame = []

        print('fps:', self.fps)
        print('codec:', codec)
        print('output size:', self.w, 'x', self.h)
        print('total frames:', self.total_frames)

        print("Opening ", file)
        self.reader = skvideo.io.FFmpegReader(file, inputdict={}, outputdict={})
        self.get_frame(0.0)     # read first frame
        if self.frame is None:
            log("warning: no first frame in:", file)
        return True

    def get_frame(self, time):
        # return the frame closest to the requested time
        frame_num = int(round(time * self.fps))
        # print("request frame num:", frame_num)
        if frame_num < 0:
            if self.frame is None:
                return np.zeros(shape=[self.h, self.w, 3], dtype=np.uint8)
            else:
                (h, w) = self.frame.shape[:2]
                return np.zeros(shape=[h, w, 3],
                                dtype=np.uint8)
        while self.frame_counter < frame_num and not self.frame is None:
            try:
                self.frame = self.reader._readFrame()
                self.frame = self.frame[:,:,::-1]
                self.frame_counter += 1
                if not len(self.frame):
                    self.frame = None
            except:
                self.frame = None
        return self.frame
        
    def skip_secs(self, seconds):
        if not self.reader:
            return
        skip_frames = int(round( seconds * self.fps ))
        print("skipping first %.2f seconds (%d frames.)" % (seconds, skip_frames))
        for i in range(skip_frames):
            self.reader._readFrame()

    def next_frame(self):
        try:
            frame = self.reader._readFrame()
        except:
            return None
        if not len(frame):
            return None
        frame = frame[:,:,::-1]     # convert from RGB to BGR (to make opencv happy)
        return frame

# fixme: figure out why zooming on some landscape videos in some cases
#        doesn't always fill the grid cell (see Coeur, individual grades.) 
def render_combined_video(project, results_dir,
                          video_names, offsets, rotate_hints={},
                          title_page=None, credits_page=None):
    # 1080p
    output_w = 1920
    output_h = 1080
    output_fps = 30
    border = 10
    log("output video specs:", output_w, "x", output_h, "fps:", output_fps)
    
    # load static pages if specified
    if title_page:
        log("adding a title page:", title_page)
        title_rgb = cv2.imread(os.path.join(project, title_page),
                               flags=cv2.IMREAD_ANYCOLOR|cv2.IMREAD_ANYDEPTH)
        title_frame = np.zeros(shape=[output_h, output_w, 3], dtype=np.uint8)
        (h, w) = title_rgb.shape[:2]
        scale_w = output_w / w
        scale_h = output_h / h
        if scale_w < scale_h:
            title_scale = cv2.resize(title_rgb, (0,0), fx=scale_w,
                                     fy=scale_w,
                                     interpolation=cv2.INTER_AREA)
        else:
            title_scale = cv2.resize(title_rgb, (0,0), fx=scale_h,
                                     fy=scale_h,
                                     interpolation=cv2.INTER_AREA)
        x = int((output_w - title_scale.shape[1]) / 2)
        y = int((output_h - title_scale.shape[0]) / 2)
        title_frame[y:y+title_scale.shape[0],x:x+title_scale.shape[1]] = title_scale
        #cv2.imshow("title", title_frame)
        
    credits_frame = np.zeros(shape=[output_h, output_w, 3], dtype=np.uint8)
    if credits_page:
        log("adding a credits page:", credits_page)
        credits_rgb = cv2.imread(os.path.join(project, credits_page),
                                 flags=cv2.IMREAD_ANYCOLOR|cv2.IMREAD_ANYDEPTH)
        (h, w) = credits_rgb.shape[:2]
        scale_w = output_w / w
        scale_h = output_h / h
        if scale_w < scale_h:
            credits_scale = cv2.resize(credits_rgb, (0,0), fx=scale_w,
                                     fy=scale_w,
                                     interpolation=cv2.INTER_AREA)
        else:
            credits_scale = cv2.resize(credits_rgb, (0,0), fx=scale_h,
                                     fy=scale_h,
                                     interpolation=cv2.INTER_AREA)
        x = int((output_w - credits_scale.shape[1]) / 2)
        y = int((output_h - credits_scale.shape[0]) / 2)
        credits_frame[y:y+credits_scale.shape[0],x:x+credits_scale.shape[1]] = credits_scale
        #cv2.imshow("credits", credits_frame)

    # open all the video clips and grab some quick stats
    videos = []
    durations = []
    for i, file in enumerate(video_names):
        v = VideoTrack()
        path = os.path.join(project, file)
        if v.open(path):
            videos.append(v)
            durations.append(v.duration + offsets[i])
        else:
            # don't render but we still need a placeholder so videos
            # continue match offset time list by position
            videos.append(None)
    duration = np.median(durations)
    duration += 4 # for credits/fade out
    log("median video duration (with fade to credits):", duration)
    
    if len(videos) == 0:
        return

    # plan our grid
    num_portrait = 0
    num_landscape = 0
    for v in videos:
        if v is None or v.frame is None:
            continue
        (h, w) = v.frame.shape[:2]
        if w > h:
            num_landscape += 1
        else:
            num_portrait += 1
    cell_landscape = True
    if num_portrait > num_landscape:
        cell_landscape = False
        log("portrait dominant input videos")
    else:
        log("landscape dominant input videos")

    num_good_videos = sum(v is not None for v in videos)
    cols = 1
    rows = 1
    while cols * rows < num_good_videos:
        if cell_landscape:
            if cols <= rows:
                cols += 1
            else:
                rows += 1
        else:
            if cols < rows*4:
                cols += 1
            else:
                rows += 1
    log("video grid (rows x cols):", rows, "x", cols)
    grid_w = int(output_w / cols)
    grid_h = int(output_h / rows)
    cell_w = (output_w - border*(cols+1)) / cols
    cell_h = (output_h - border*(rows+1)) / rows
    cell_aspect = cell_w / cell_h
    print("  grid size:", grid_w, "x", grid_h)
    print("  cell size:", cell_w, "x", cell_h, "aspect:", cell_aspect)
    
    # open writer for output
    output_file = os.path.join(results_dir, "silent_video.mp4")
    inputdict, outputdict = gen_dicts(output_fps, "sane")
    writer = skvideo.io.FFmpegWriter(output_file, inputdict=inputdict, outputdict=outputdict)
    done = False
    frames = [None] * len(videos)
    output_time = 0
    pbar = tqdm(total=int(duration*output_fps), smoothing=0.05)
    while output_time <= duration:
        for i, v in enumerate(videos):
            if v is None:
                frames[i] = None
                continue
            frame = v.get_frame(output_time - offsets[i])
            if not frame is None:
                basevid = os.path.basename(video_names[i])
                #print("basevid:", basevid)
                if basevid in rotate_hints:
                    if rotate_hints[basevid] == 90:
                        frame = cv2.transpose(frame)
                        frame = cv2.flip(frame, 1)
                    elif rotate_hints[basevid] == 180:
                        frame = cv2.flip(frame, -1)
                    elif rotate_hints[basevid] == 270:
                        frame = cv2.transpose(frame)
                        frame = cv2.flip(frame, 0)
                    else:
                        print("unhandled rotation angle:", rotate_hints[video_names[i]])
                (h, w) = frame.shape[:2]
                vid_aspect = w/h
                vid_landscape = (vid_aspect >= 1)
                scale_w = cell_w / w
                scale_h = cell_h / h
                
                #option = "fit"
                option = "zoom"
                if option == "fit":
                    if scale_w < scale_h:
                        frame_scale = cv2.resize(frame, (0,0), fx=scale_w,
                                                 fy=scale_w,
                                                 interpolation=cv2.INTER_AREA)
                    else:
                        frame_scale = cv2.resize(frame, (0,0), fx=scale_h,
                                                 fy=scale_h,
                                                 interpolation=cv2.INTER_AREA)
                    frames[i] = frame_scale
                elif option == "zoom":
                    if cell_landscape != vid_landscape:
                        # compromise zoom/fit/arrangement
                        avg = (scale_w + scale_h) * 0.5
                        scale_w = avg
                        scale_h = avg
                        #print("scale:", scale_w, scale_h)
                    if scale_w < scale_h:
                        frame_scale = cv2.resize(frame, (0,0), fx=scale_h,
                                                 fy=scale_h,
                                                 interpolation=cv2.INTER_AREA)
                        #(tmp_h, tmp_w) = frame_scale.shape[:2]
                        #cut = int((tmp_w - cell_w) * 0.5)
                        #frame_scale = frame_scale[:,cut:cut+int(round(cell_w))]
                    else:
                        frame_scale = cv2.resize(frame, (0,0), fx=scale_w,
                                                 fy=scale_w,
                                                 interpolation=cv2.INTER_AREA)
                    (tmp_h, tmp_w) = frame_scale.shape[:2]
                    if tmp_h > cell_h:
                        cuth = int((tmp_h - cell_h) * 0.5)
                    else:
                        cuth = 0
                    if tmp_w > cell_w:
                        cutw = int((tmp_w - cell_w) * 0.5)
                    else:
                        cutw = 0
                    frame_scale = frame_scale[cuth:cuth+int(round(cell_h)),cutw:cutw+int(round(cell_w))]
                    #if cell_landscape != vid_landscape:
                    #    print("scaled size h x w:", tmp_h, tmp_w)
                    #    print("cropped size:", frame_scale.shape[:2])
                    frames[i] = frame_scale
                # cv2.imshow(video_names[i], frame_scale)
            elif not frames[i] is None:
                # fade
                frames[i] = (frames[i] * 0.9).astype('uint8')
            else:
                # bummer video with no frames?
                frames[i] = None
        main_frame = np.zeros(shape=[output_h, output_w, 3], dtype=np.uint8)

        row = 0
        col = 0
        for i, f in enumerate(frames):
            if f is None:
                continue
            x = int(round(border + col * (cell_w + border)))
            y = int(round(border + row * (cell_h + border)))
            if f.shape[1] < cell_w:
                gap = (cell_w - f.shape[1]) * 0.5
                x += int(gap)
            if f.shape[0] < cell_h:
                gap = (cell_h - f.shape[0]) * 0.5
                y += int(gap)
            main_frame[y:y+f.shape[0],x:x+f.shape[1]] = f
            col += 1
            if col >= cols:
                col = 0
                row += 1
        #cv2.imshow("main", main_frame)

        if title_page and output_time <= 5:
            if output_time < 4:
                alpha = 1
            elif output_time >= 4 and output_time <= 5:
                alpha = (5 - output_time) / (5 - 4)
            else:
                alpha = 0
            #print("time:", output_time, "alpha:", alpha)
            output_frame = cv2.addWeighted(title_frame, alpha, main_frame, 1 - alpha, 0)
        elif output_time >= duration - 5:
            if output_time >= duration - 4:
                alpha = 1
            elif output_time >= duration - 5 and output_time < duration - 4:
                alpha = 1 - ((duration - 4) - output_time) / (5 - 4)
            else:
                alpha = 0
            #print("time:", output_time, "alpha:", alpha)
            output_frame = cv2.addWeighted(credits_frame, alpha, main_frame, 1 - alpha, 0)
        else:
            output_frame = main_frame
        cv2.imshow("output", output_frame)
        cv2.waitKey(1)

        # write the frame as RGB not BGR
        writer.writeFrame(output_frame[:,:,::-1])
        
        output_time += 1 / output_fps
        pbar.update(1)
    pbar.close()
    writer.close()
    log("gridded video (only) file: silent_video.mp4")
    
def merge(results_dir):
    log("video: merging video and audio into final result: gridded_video.mp4")
    # use ffmpeg to combine the video and audio tracks into the final movie
    input_video = os.path.join(results_dir, "silent_video.mp4")
    input_audio = os.path.join(results_dir, "mixed_audio.mp3")
    output_video = os.path.join(results_dir, "gridded_video.mp4")
    result = call(["ffmpeg", "-i", input_video, "-i", input_audio, "-c:v", "copy", "-c:a", "aac", "-y", output_video])
    print("ffmpeg result code:", result)

# https://superuser.com/questions/258032/is-it-possible-to-use-ffmpeg-to-trim-off-x-seconds-from-the-beginning-of-a-video/269960
# ffmpeg -i input.flv -ss 2 -vcodec copy -acodec copy output.flv
#   -vcodec libx264 -crf 0

#ffmpeg -f lavfi -i color=c=black:s=1920x1080:r=25:d=1 -i testa444.mov -filter_complex "[0:v] trim=start_frame=1:end_frame=5 [blackstart]; [0:v] trim=start_frame=1:end_frame=3 [blackend]; [blackstart] [1:v] [blackend] concat=n=3:v=1:a=0[out]" -map "[out]" -c:v qtrle -c:a copy -timecode 01:00:00:00 test16.mov

def save_aligned(project, results_dir, video_names, sync_offsets):
    # first clean out any previous aligned_audio tracks in case tracks
    # have been updated or added or removed since the previous run.
    for file in sorted(os.listdir(results_dir)):
        if file.startswith("aligned_video_"):
            fullname = os.path.join(results_dir, file)
            log("NOTICE: deleting file from previous run:", file)
            os.unlink(fullname)
            
    log("Writing aligned version of videos...", fancy=True)
    for i, video in enumerate(video_names):
        video_file = os.path.join(project, video)
        # decide trim/pad
        sync_ms = sync_offsets[i]
        if sync_ms >= 0:
            trim_sec = sync_ms / 1000
            pad_sec = 0
        else:
            trim_sec = 0
            pad_sec = -sync_ms / 1000
        
        # scan video meta data for resolution/fps
        metadata = skvideo.io.ffprobe(video_file)
        #print(metadata.keys())
        if not "video" in metadata:
            log("No video frames found in:", video_file)
            continue
        #print(json.dumps(metadata["video"], indent=4))
        fps_string = metadata['video']['@r_frame_rate']
        (num, den) = fps_string.split('/')
        fps = float(num) / float(den)
        codec = metadata['video']['@codec_long_name']
        w = int(metadata['video']['@width'])
        h = int(metadata['video']['@height'])
        if '@duration' in metadata['video']:
            duration = float(metadata['video']['@duration'])
        else:
            duration = 1
        total_frames = int(round(duration * fps))
        frame_counter = -1

        # pathfoo
        basename = os.path.basename(video)
        name, ext = os.path.splitext(basename)
        # FilemailCli can't handle "," in file names
        name = name.replace(',', '')
        tmp_video = os.path.join(results_dir, "tmp_video.mp4")
        tmp_audio = os.path.join(results_dir, "tmp_audio.mp3")
        output_file = os.path.join(results_dir, "aligned_video_" + name + ".mp4")
        log("aligned_video_" + name + ".mp4", "offset(sec):", sync_ms/1000)
        log("  fps:", fps, "codec:", codec, "size:", w, "x", h, "total frames:", total_frames)

        # open source
        reader = skvideo.io.FFmpegReader(video_file, inputdict={}, outputdict={})
        
        # open destination
        inputdict, outputdict = gen_dicts(fps, "sane")
        writer = skvideo.io.FFmpegWriter(tmp_video, inputdict=inputdict, outputdict=outputdict)

        # pad or trim
        pad_frames = 0
        if pad_sec > 0:
            pad_frames = int(round(fps*pad_sec))
            log("  pad (sec):", pad_sec, "frames:", pad_frames)
                
        trim_frames = 0
        if trim_sec > 0:
            trim_frames = int(round(fps*trim_sec))
            log("  trim (sec):", trim_sec, "frames:", trim_frames)
            for i in range(trim_frames):
                reader._readFrame() # discard

        # copy remainder of video
        pbar = tqdm(total=(total_frames+pad_frames-trim_frames), smoothing=0.05)
        while True:
            try:
                frame = reader._readFrame()
                if not len(frame):
                    frame = None
                else:
                    # small bit of down scaling while maintaining
                    # original aspect ratio
                    target_area = 1280*720
                    area = frame.shape[0] * frame.shape[1]
                    #print("area:", area, "target_area:", target_area)
                    if area > target_area:
                        scale = math.sqrt( target_area / area )
                        frame = cv2.resize(frame, (0,0), fx=scale, fy=scale,
                                           interpolation=cv2.INTER_AREA)
            except:
                frame = None
            if frame is None:
                break
            else:
                while pad_frames:
                    black = frame * 0
                    writer.writeFrame(black)
                    pad_frames -= 1
                    pbar.update(1)
                writer.writeFrame(frame)
                pbar.update(1)
        writer.close()
        pbar.close()

        # load the audio (ignoring we already have it loaded somewhere else)
        basename, ext = os.path.splitext(video_file)
        sample = AudioSegment.from_file(video_file, ext[1:])
        if sync_ms >= 0:
            synced_sample = sample[sync_ms:]
        else:
            pad = AudioSegment.silent(duration=-sync_ms)
            synced_sample = pad + sample
        synced_sample.export(tmp_audio, format="mp3")
        
        log("video: merging aligned video and audio into final result:", output_file)
        # use ffmpeg to combine the video and audio tracks into the final movie
        input_video = os.path.join(results_dir, "tmp_video.mp4")
        input_audio = os.path.join(results_dir, "tmp_audio.mp3")
        result = call(["ffmpeg", "-i", input_video, "-i", input_audio, "-c:v", "copy", "-c:a", "aac", "-y", output_file])
        print("ffmpeg result code:", result)

        # clean up
        os.unlink(input_audio)
        os.unlink(input_video)
