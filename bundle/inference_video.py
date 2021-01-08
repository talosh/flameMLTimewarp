import os
import cv2
import torch
import argparse
import numpy as np
from tqdm import tqdm
from torch.nn import functional as F
import warnings
import _thread
import skvideo.io
from queue import Queue, Empty
warnings.filterwarnings("ignore")

from pprint import pprint

def transferAudio(sourceVideo, targetVideo):    
    import shutil
    import moviepy.editor
    tempAudioFileName = "./temp/audio.mkv"

    # split audio from original video file and store in "temp" directory
    if True:
        
        # clear old "temp" directory if it exits
        if os.path.isdir("temp"):
            # remove temp directory
            shutil.rmtree("temp")
        # create new "temp" directory
        os.makedirs("temp")
        # extract audio from video
        os.system("ffmpeg -y -i " + sourceVideo + " -c:a copy -vn " + tempAudioFileName)
        
    os.rename(targetVideo, "noAudio_"+targetVideo)
    # combine audio file and new video file
    os.system("ffmpeg -y -i " + "noAudio_"+targetVideo + " -i " + tempAudioFileName + " -c copy " + targetVideo)
    
    if os.path.getsize(targetVideo) == 0: # if ffmpeg failed to merge the video and audio together try converting the audio to mp3
        tempAudioFileName = "./temp/audio.mp3"
        os.system("ffmpeg -y -i " + sourceVideo + " -c:a mp3 -vn " + tempAudioFileName)
        os.system("ffmpeg -y -i " + "noAudio_"+targetVideo + " -i " + tempAudioFileName + " -c copy " + targetVideo)
        if (os.path.getsize(targetVideo) == 0): # if mp3 not supported by selected format
            os.rename("noAudio_"+targetVideo, targetVideo)
            print("Audio transfer failed. Interpolated video will have no audio")
        else:
            print("Lossless audio transfer failed. Audio was transcoded to mp3 instead.")
    
            # remove audio-less video
            os.remove("noAudio_"+targetVideo)
    else:
        os.remove("noAudio_"+targetVideo)

    # remove temp directory
    shutil.rmtree("temp")

    
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    torch.set_grad_enabled(False)
    torch.backends.cudnn.enabled = True
    torch.backends.cudnn.benchmark = True

parser = argparse.ArgumentParser(description='Interpolation for a pair of images')
parser.add_argument('--video', dest='video', type=str, default=None)
parser.add_argument('--img', dest='img', type=str, default=None)
parser.add_argument('--montage', dest='montage', action='store_true', help='montage origin video')
parser.add_argument('--UHD', dest='UHD', action='store_true', help='support 4k video')
parser.add_argument('--skip', dest='skip', action='store_true', help='whether to remove static frames before processing')
parser.add_argument('--fps', dest='fps', type=int, default=None)
parser.add_argument('--png', dest='png', action='store_true', help='whether to vid_out png format vid_outs')
parser.add_argument('--ext', dest='ext', type=str, default='mp4', help='vid_out video extension')
parser.add_argument('--exp', dest='exp', type=int, default=1)
args = parser.parse_args()
assert (not args.video is None or not args.img is None)
if not args.img is None:
    args.png = True

from model.RIFE_HD import Model
model = Model()
model.load_model('./train_log', -1)
model.eval()
model.device()

if not args.video is None:
    videoCapture = cv2.VideoCapture(args.video)
    fps = videoCapture.get(cv2.CAP_PROP_FPS)
    tot_frame = videoCapture.get(cv2.CAP_PROP_FRAME_COUNT)
    videoCapture.release()
    if args.fps is None:
        fpsNotAssigned = True
        args.fps = fps * (2 ** args.exp)
    else:
        fpsNotAssigned = False
    videogen = skvideo.io.vreader(args.video)
    lastframe = next(videogen)
    fourcc = cv2.VideoWriter_fourcc('H', 'F', 'Y', 'U')
    video_path_wo_ext, ext = os.path.splitext(args.video)
    print('{}.{}, {} frames in total, {}FPS to {}FPS'.format(video_path_wo_ext, args.ext, tot_frame, fps, args.fps))
    if args.png == False and fpsNotAssigned == True and not args.skip:
        print("The audio will be merged after interpolation process")
    else:
        print("Will not merge audio because using png, fps or skip flag!")
else:
    videogen = []
    exrs = []
    for f in os.listdir(args.img):
        if f.endswith('.png'):
            videogen.append(f)
        if f.endswith('.exr'):
            exrs.append(f)
    
    # prefer exr sequences if detected
    if exrs:
        videogen = exrs
    tot_frame = len(videogen)
    videogen.sort(key= lambda x:int(x[:-4]))
    if videogen[0].endswith('.exr'):
        lastframe = cv2.imread(os.path.join(args.img, videogen[0]), cv2.IMREAD_COLOR | cv2.IMREAD_ANYDEPTH)[:, :, ::-1].copy()
    else:
        lastframe = cv2.imread(os.path.join(args.img, videogen[0]))[:, :, ::-1].copy()
    videogen = videogen[1:]
h, w, _ = lastframe.shape
vid_out = None
if args.png:
    if not os.path.exists('vid_out'):
        os.mkdir('vid_out')
else:
    vid_out = cv2.VideoWriter('{}_{}X_{}fps.{}'.format(video_path_wo_ext, (2 ** args.exp), int(np.round(args.fps)), args.ext), fourcc, args.fps, (w, h))
    
def clear_write_buffer(user_args, write_buffer):
    cnt = 0
    while True:
        item = write_buffer.get()
        if item is None:
            break
        if user_args.png:
            cv2.imwrite('vid_out/{:0>7d}.png'.format(cnt), item[:, :, ::-1])
            cnt += 1
        else:
            vid_out.write(item[:, :, ::-1])

def build_read_buffer(user_args, read_buffer, videogen):
    for frame in videogen:
        if not user_args.img is None:

            if frame.endswith('.exr'):
                frame = cv2.imread(os.path.join(user_args.img, frame), cv2.IMREAD_COLOR | cv2.IMREAD_ANYDEPTH)[:, :, ::-1].copy()
            else:
                frame = cv2.imread(os.path.join(user_args.img, frame))[:, :, ::-1].copy()

        if user_args.montage:
            frame = frame[:, left: left + w]
        read_buffer.put(frame)
    read_buffer.put(None)

def make_inference(I0, I1, exp):
    global model
    middle = model.inference(I0, I1, args.UHD)
    if exp == 1:
        return [middle]
    first_half = make_inference(I0, middle, exp=exp - 1)
    second_half = make_inference(middle, I1, exp=exp - 1)
    return [*first_half, middle, *second_half]
            
if args.montage:
    left = w // 4
    w = w // 2
if args.UHD:
    ph = ((h - 1) // 64 + 1) * 64
    pw = ((w - 1) // 64 + 1) * 64
else:
    ph = ((h - 1) // 32 + 1) * 32
    pw = ((w - 1) // 32 + 1) * 32
padding = (0, pw - w, 0, ph - h)
pbar = tqdm(total=tot_frame)
skip_frame = 1
if args.montage:
    lastframe = lastframe[:, left: left + w]
write_buffer = Queue(maxsize=500)
read_buffer = Queue(maxsize=500)
_thread.start_new_thread(build_read_buffer, (args, read_buffer, videogen))
_thread.start_new_thread(clear_write_buffer, (args, write_buffer))

if lastframe.dtype == 'float32':
    I1 = torch.from_numpy(np.transpose(lastframe, (2,0,1))).to(device, non_blocking=True).unsqueeze(0)
else:
    I1 = torch.from_numpy(np.transpose(lastframe, (2,0,1))).to(device, non_blocking=True).unsqueeze(0).float() / 255.

I1 = F.pad(I1, padding)

while True:
    frame = read_buffer.get()
    if frame is None:
        break
    I0 = I1
    if lastframe.dtype == 'float32':
        I1 = torch.from_numpy(np.transpose(frame, (2,0,1))).to(device, non_blocking=True).unsqueeze(0)
    else:
        I1 = torch.from_numpy(np.transpose(frame, (2,0,1))).to(device, non_blocking=True).unsqueeze(0).float() / 255.
    I1 = F.pad(I1, padding)

    diff = (F.interpolate(I0, (16, 16), mode='bilinear', align_corners=False)
         - F.interpolate(I1, (16, 16), mode='bilinear', align_corners=False)).abs()
    
    if diff.max() < 2e-3 and args.skip:
        if skip_frame % 100 == 0:
            print("Warning: Your video has {} static frames, skipping them may change the duration of the generated video.".format(skip_frame))
        skip_frame += 1
        pbar.update(1)
        continue

    if diff.mean() > 0.2:
        output = []
        for i in range((2 ** args.exp) - 1):
            output.append(I0)
    else:
        output = make_inference(I0, I1, args.exp)
        
    if args.montage:
        write_buffer.put(np.concatenate((lastframe, lastframe), 1))
        for mid in output:
            mid = (((mid[0] * 255.).byte().cpu().numpy().transpose(1, 2, 0)))
            write_buffer.put(np.concatenate((lastframe, mid[:h, :w]), 1))
    else:
        write_buffer.put(lastframe)
        for mid in output:
            mid = (((mid[0] * 255.).byte().cpu().numpy().transpose(1, 2, 0)))
            write_buffer.put(mid[:h, :w])
    pbar.update(1)
    lastframe = frame
if args.montage:
    write_buffer.put(np.concatenate((lastframe, lastframe), 1))
else:
    write_buffer.put(lastframe)
import time
while(not write_buffer.empty()):
    time.sleep(0.1)
pbar.close()
if not vid_out is None:
    vid_out.release()

# move audio to new video file if appropriate
if args.png == False and fpsNotAssigned == True and not args.skip and not args.video is None:
    outputVideoFileName = '{}_{}X_{}fps.{}'.format(video_path_wo_ext, 2 ** args.exp, int(np.round(args.fps)), args.ext)
    try:
        transferAudio(args.video, outputVideoFileName)
    except:
        print("Audio transfer failed. Interpolated video will have no audio")
        os.rename("noAudio_"+outputVideoFileName, outputVideoFileName)
