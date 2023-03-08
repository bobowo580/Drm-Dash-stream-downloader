mport os,requests,shutil,glob
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
        print("Total time: " + str(day) + " days " + str(hour) + " hours " + str(minute) + " minutes and " + str(second) + " seconds")
        total_time = float(str((day * 24 * 60 * 60) + (hour * 60 * 60) + (minute * 60) + (int(second.split('.')[0]))) + '.' + str(int(second.split('.')[-1])))
        return total_time

    else:
        print("Duration Format Error")
        return None

def download_media(filename,url,epoch = 0):
    if(os.path.isfile(filename)):
        media_head = requests.head(url, allow_redirects = True)
        if media_head.status_code == 200:
            media_length = int(media_head.headers.get("content-length"))
            if(os.path.getsize(filename) >= media_length):
                print("Video already downloaded.. skipping Downloading..")
            else:
                print("Redownloading faulty download..")
                os.remove(filename) #Improve removing logic
                download_media(filename,url)
        else:
            if (epoch > retry):
                exit("Server doesn't support HEAD.")
            download_media(filename,url,epoch + 1)
    else:
        media = requests.get(url, stream=True)
        media_length = int(media.headers.get("content-length"))
        if media.status_code == 200:
            if(os.path.isfile(filename) and os.path.getsize(filename) >= video_length):
                print("Video already downloaded.. skipping write to disk..")
            else:
                try:
                    with open(filename, 'wb') as video_file:
                        shutil.copyfileobj(media.raw, video_file)
                        return False #Successfully downloaded the file
                except:
                    print("Connection error: Reattempting download of video..")
                    download_media(filename,url, epoch + 1)

            if os.path.getsize(filename) >= video_length:
                pass
            else:
                print("Error downloaded video is faulty.. Retrying to download")
                download_media(filename,url, epoch + 1)
        elif(media.status_code == 404):
            print("Probably end hit!\n",url)
            return True #Probably hit the last of the file
        else:
            if (epoch > retry):
                exit("Error Video fetching exceeded retry times.")
            print("Error fetching video file.. Retrying to download")
            download_media(filename,url, epoch + 1)


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
    audio = []
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
            print("Processing " + adapt_set.mime_type)
            content_type = adapt_set.mime_type
            repr = adapt_set.representations[-1] # Max Quality
            for segment in repr.segment_templates:
                if(segment.duration):
                    print("Media segments are of equal timeframe")
                    segment_time = segment.duration / segment.timescale
                    total_segments = running_time / segment_time
                else:
                    print("Media segments are of inequal timeframe")
                    print(segment.media)
                    for timeline in segment.segment_timelines:
                        last_s = timeline.Ss[-1]
                        print("last_s:", last_s.t ,last_s.d , last_s.r)

                    media_file = segment.media
                    media_file.replace("$Number$", segment.start_number)#
                    media_file.replace("$RepresentationID$", repr.id)
                    media_file.replace("$Time$", last_s.t + last_s.d * last_s.r)
                    
                    media_segments.append(media_file)
                    print(media_file)
                    

    return media_segments



if __name__ == "__main__":
    mpd = "http://31.30.141.198:80/cdn.vodafone.cz/LIVE/5066/sfmt=shls/6.mpd?start=LIVE&end=END&device=DASH_STB_NGRSSP_LIVE_SD"
    base_url = mpd.split("6.mpd")[0]
    os.chdir(working_dir)
    media_info = manifest_parser(mpd)
    #handle_irregular_segments(media_info)

