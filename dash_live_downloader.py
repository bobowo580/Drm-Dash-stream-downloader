#!/usr/bin/env python3

from time import sleep
import os
import asyncio,aiohttp,requests
from mpegdash.parser import MPEGDASHParser
#from mpegdash.nodes import Descriptor
#from mpegdash.utils import (
#    parse_attr_value, parse_child_nodes, parse_node_value,
#    write_attr_value, write_child_node, write_node_value
#)

download_dir = os.getcwd() + "/download" # set the folder to download files

if not os.path.exists(download_dir):
    os.makedirs(download_dir)


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

async def download_file(url, file_name):
    async with aiohttp.ClientSession() as session:
        print("downloading " + url)
        async with session.get(url) as resp:
            with open(file_name, 'wb') as f:
                while True:
                    chunk = await resp.content.read(10240)
                    if not chunk:
                        break
                    f.write(chunk)
        print("download finished " + file_name)
        
async def download_files(base_url, media_segments):
    tasks = []
    for media_url in media_segments:
        file_name = media_url.split("?")[0]
        if(os.path.isfile(file_name)):
            print(file_name + " already downloaded.. skipping.")
        else:
            tasks.append(download_file(base_url + media_url, file_name)) 
    await asyncio.gather(*tasks)
            
async def download_media(base_url, media_url):
    file_name = media_url.split("?")[0]
    if(os.path.isfile(file_name)):
        print(file_name + " already downloaded.. skipping.")
    else:
        full_url = base_url + media_url
        print("Downloading " + full_url)
        #media = await requests.get(full_url, stream=True)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if media.status_code == 200:
                    try:
                        with open(file_name, 'wb') as f:
                            await f.write(resp.content())
                            #for chunk in media.iter_content(chunk_size = 102400):
                            #    await f.write(chunk)
                    except:
                        print("Failed to save file: " + file_name)

                else:
                    print("Error code: ", media.status_code, full_url)
    print("download finished " + file_name)



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
                    #print(media_file)

    return media_segments



if __name__ == "__main__":
    mpd = "http://127.0.0.1/dash.mpd"
    base_url = mpd.split("?")[0]
    base_url = base_url.split("/")[-1]
    base_url = mpd.split(base_url)[0]
    print(base_url)
    os.chdir(download_dir)
    media_segments = manifest_parser(mpd)
    
    while True:
        asyncio.run(download_files(base_url, media_segments))
        sleep(1)
        media_segments = manifest_parser(mpd)


