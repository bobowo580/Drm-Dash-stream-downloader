#!/usr/bin/env python3

from time import sleep
from threading import Thread
import os,requests,shutil
from mpegdash.parser import MPEGDASHParser
from mpegdash.nodes import Descriptor
from mpegdash.utils import (
    parse_attr_value, parse_child_nodes, parse_node_value,
    write_attr_value, write_child_node, write_node_value
)

#global ids
retry = 3
download_dir = os.getcwd() # set the folder to output
working_dir = os.getcwd() + "/working_dir" # set the folder to download ephemeral files

if not os.path.exists(working_dir):
    os.makedirs(working_dir)


def durationtoseconds(period):
    #Duration format in PTxDxHxMxS
    if(period[:2] == "PT"):
        period = period[2:]   
        day = int(period.split("D")[0] if 'D' in period else 0)
        hour = int(period.split("H")[0].split("D")[-1]  if 'H' in period else 0)
        minute = int(period.split("M")[0].split("H")[-1] if 'M' in period else 0)
        second = period.split("S")[0].split("M")[-1]
        total_time = float(str((day * 24 * 60 * 60) + (hour * 60 * 60) + (minute * 60) + (int(second.split('.')[0]))) + '.' + str(int(second.split('.')[-1])))
        print("Total time: ", total_time, " seconds")
        return total_time

    else:
        print("Duration Format Error")
        return None

def async(f):
    def wrapper(*args, **kwargs):
        thr = Thread(target = f, args = args, kwargs = kwargs)
        thr.start()
    return wrapper


@async
def download_media(base_url, media_url):
    file_name = media_url.split("?")[0]
    if(os.path.isfile(file_name)):
        print(file_name + " already downloaded.. skipping.")
    else:
        full_url = base_url + media_url
        print("Downloading " + full_url)
        media = requests.get(full_url, stream=True)
        if media.status_code == 200:
            try:
                with open(file_name, 'wb') as f:
                    #shutil.copyfileobj(media.raw, f)
                    for chunk in media.iter_content(chunk_size = 102400):
                        f.write(chunk)
            except:
                print("Failed to save file: " + file_name)

        else:
            print("Error code: ", media.status_code, full_url)
    print("download finished " + file_name)


def handle_irregular_segments(media_info):
    no_segment,video_url,video_kid,video_extension,no_segment,audio_url,audio_kid,audio_extension = media_info
    video_url = base_url + video_url
    audio_url = base_url + audio_url   
    #video_init = video_url.replace("$Number$","init")
   # audio_init = audio_url.replace("$Number$","init")
   # download_media("video_0.mp4",video_init)
   # download_media("audio_0.mp4",audio_init)
    for count in range(1,no_segment):
        video_segment_url = video_url.replace("$Number$",str(count))
        audio_segment_url = audio_url.replace("$Number$",str(count))
        video_status = download_media(f"video_{str(count)}.{video_extension}",video_segment_url)   
        audio_status = download_media(f"audio_{str(count)}.{audio_extension}",audio_segment_url)
        if(video_status):
            if os.name == "nt":
                video_concat_command = "copy /b " + "+".join([f"video_{i}.{video_extension}" for i in range(0,count)]) + " encrypted_video.mp4"
                audio_concat_command = "copy /b " + "+".join([f"audio_{i}.{audio_extension}" for i in range(0,count)]) + " encrypted_audio.mp4"
            else:
                video_concat_command = "cat " + " ".join([f"video_{i}.{video_extension}" for i in range(0,count)]) + " > encrypted_video.mp4"
                audio_concat_command = "cat " + " ".join([f"audio_{i}.{audio_extension}" for i in range(0,count)]) + " > encrypted_audio.mp4"
            os.system(video_concat_command)
            os.system(audio_concat_command)
            break

def manifest_parser(mpd_url):
    media_segments = []
    manifest = requests.get(mpd_url).text
    with open("manifest.mpd",'w') as manifest_handler:
        manifest_handler.write(manifest)
    mpd = MPEGDASHParser.parse("./manifest.mpd")
    if(mpd.type == "dynamic" ):
        running_time = durationtoseconds(mpd.time_shift_buffer_depth)
    else:
        running_time = durationtoseconds(mpd.media_presentation_duration)
    for period in mpd.periods:
        for adapt_set in period.adaptation_sets:
            #print("Processing AdaptationSet " + adapt_set.content_type)
            for repr in adapt_set.representations:
                for segment in repr.segment_templates:
                    last_t = 0
                    total_segments = 0
                    for S in segment.segment_timelines[0].Ss:
                        if(S.t):
                            last_t = S.t
                        if(S.r):
                            last_t = last_t + S.d * S.r
                            total_segments += (S.r + 1) 
                        else:
                            last_t = last_t + S.d
                            total_segments += 1
                    media_file = segment.media.replace("$RepresentationID$", repr.id)
                    media_file = media_file.replace("$Time$", str(last_t))
                    if(segment.duration):
                        print("Media segments are of equal timeframe")
                        segment_time = segment.duration / segment.timescale
                        total_segments = running_time / segment_time

                    media_file = media_file.replace("$Number$", str(segment.start_number + total_segments))
                    #print(total_segments) 
                    media_segments.append(media_file)
                    print(media_file)

    return media_segments



if __name__ == "__main__":
    mpd = "http://127.0.0.1/dash.mpd"
    base_url = mpd.split("?")[0]
    base_url = base_url.split("/")[-1]
    base_url = mpd.split(base_url)[0]
    print(base_url)
    os.chdir(working_dir)
    media_segments = manifest_parser(mpd)
    while True:
        for media_url in media_segments:
            download_media(base_url, media_url)
        sleep(1)
        media_segments = manifest_parser(mpd)

