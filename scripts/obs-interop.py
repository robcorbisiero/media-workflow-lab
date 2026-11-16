"""Optional Windows OBS integration check; uses an explicitly supplied portable copy."""
import argparse
import array
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import uuid


def run(obs_directory, ffmpeg, ffprobe, seconds=12, recovery=False):
    if recovery:
        seconds = 30
    obs_directory = Path(obs_directory).resolve()
    executable = obs_directory / 'bin/64bit/obs64.exe'
    if not executable.is_file():
        raise ValueError('Supply the extracted official Windows x64 OBS ZIP directory')
    ident = 'MediaLab_' + uuid.uuid4().hex
    output = Path(__file__).resolve().parents[1] / 'artifacts' / ident
    output.mkdir(parents=True)
    # Portable OBS stores all configuration beneath this dedicated extracted copy.
    config = obs_directory / 'config/obs-studio'
    profile = config / 'basic/profiles' / ident
    profile.mkdir(parents=True, exist_ok=False)
    scenes = config / 'basic/scenes'
    scenes.mkdir(parents=True, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    url = f'srt://127.0.0.1:{port}?mode=caller&latency=120000&timeout=5000000'
    source = dict(name='Synthetic SRT', id='ffmpeg_source', versioned_id='ffmpeg_source',
                  uuid=str(uuid.uuid4()), settings=dict(is_local_file=False, input=url,
                  input_format='mpegts', buffering_mb=2, reconnect_delay_sec=1,
                  clear_on_media_end=True, restart_on_activate=True), mixers=1,
                  volume=1.0, enabled=True, muted=False)
    scene = dict(name='SRT Lab', id='scene', versioned_id='scene', uuid=str(uuid.uuid4()),
                 settings=dict(id_counter=1, items=[dict(name='Synthetic SRT',
                 source_uuid=source['uuid'], id=1, visible=True, locked=False,
                 pos=dict(x=0.0,y=0.0), scale=dict(x=1.0,y=1.0), rot=0.0)]))
    collection = dict(name=ident, sources=[source,scene], groups=[],
                      current_scene='SRT Lab', current_program_scene='SRT Lab',
                      scene_order=[dict(name='SRT Lab')], transitions=[], version=2,
                      modules={'output-timer':dict(recordTimerHours=0,
                      recordTimerMinutes=0,recordTimerSeconds=seconds,
                      autoStartRecordTimer=True,pauseRecordTimer=False)})
    (scenes / (ident+'.json')).write_text(json.dumps(collection,indent=2),encoding='utf-8')
    (profile / 'basic.ini').write_text(f'''[General]
Name={ident}
[Output]
Mode=Simple
FilenameFormatting=obs-recording
[SimpleOutput]
FilePath={output.as_posix()}
RecFormat2=mkv
StreamEncoder=x264
RecEncoder=x264
RecQuality=Small
VBitrate=1000
ABitrate=96
Preset=ultrafast
RecTracks=1
[Video]
BaseCX=640
BaseCY=360
OutputCX=640
OutputCY=360
FPSType=1
FPSInt=25
[Audio]
SampleRate=48000
ChannelSetup=Stereo
''',encoding='utf-8')
    common=[ffmpeg,'-hide_banner','-nostdin','-loglevel','warning']
    command=common+['-re','-f','lavfi','-i','testsrc2=size=640x360:rate=25',
        '-re','-f','lavfi','-i','sine=frequency=880:sample_rate=48000',
        '-t',str(seconds+15),'-c:v','libx264','-preset','ultrafast','-tune','zerolatency',
        '-pix_fmt','yuv420p','-g','25','-b:v','800k','-c:a','aac','-b:a','96k',
        '-f','mpegts',f'srt://127.0.0.1:{port}?mode=listener&latency=120000&pkt_size=1316&timeout=20000000']
    sender=obs=None
    events=[]
    recording_started=None
    interrupted=restored=False
    try:
        with (output/'sender.log').open('wb') as log:
            sender=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=log)
            time.sleep(.5)
            obs=subprocess.Popen([str(executable),'--portable','--multi','--disable-updater',
                '--disable-missing-files-check','--profile',ident,'--collection',ident,
                '--scene','SRT Lab','--startrecording'],cwd=executable.parent)
            # OBS's own output timer finalizes the file; never terminate an active recording.
            deadline=time.monotonic()+seconds+35
            recording=output/'obs-recording.mkv'
            while time.monotonic()<deadline:
                logs=sorted((config/'logs').glob('*.txt'),key=lambda p:p.stat().st_mtime,reverse=True)
                if logs:
                    text=logs[0].read_text(encoding='utf-8',errors='replace')
                    if ident in text:
                        if recording_started is None and '==== Recording Start' in text:
                            recording_started=time.monotonic()
                        if recovery and recording_started is not None:
                            elapsed=time.monotonic()-recording_started
                            if elapsed >= 8 and not interrupted:
                                sender.terminate()
                                sender.wait(timeout=5)
                                interrupted=True
                                events.append(dict(action='sender_stopped',recording_offset=elapsed))
                                print('Feed interrupted; OBS keeps recording.',flush=True)
                            if elapsed >= 16 and not restored:
                                sender=subprocess.Popen(command,stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL,stderr=log)
                                restored=True
                                events.append(dict(action='sender_restarted',recording_offset=elapsed))
                                print('Feed restarted on the same endpoint; checking OBS recovery.',flush=True)
                        if 'Recording Stop' in text and recording.is_file():
                            break
                time.sleep(.5)
            else:
                raise TimeoutError('OBS did not finalize its timed recording; inspect portable OBS logs')
            probe=json.loads(subprocess.check_output([ffprobe,'-v','error','-show_streams',
                '-show_format','-of','json',str(recording)],text=True,timeout=10))
            codecs={s['codec_type']:s['codec_name'] for s in probe['streams']}
            if codecs.get('video')!='h264' or codecs.get('audio')!='aac':
                raise RuntimeError('Expected OBS-recorded H.264 and AAC')
            if float(probe['format']['duration']) < seconds-1:
                raise RuntimeError('OBS recording too short')
            frame=output/'obs-frame.png'
            subprocess.run(common+['-y','-ss','5','-i',str(recording),'-frames:v','1','-update','1',str(frame)],check=True,timeout=10)
            rgb=subprocess.check_output(common+['-ss','5','-i',str(recording),'-frames:v','1',
                '-f','rawvideo','-pix_fmt','rgb24','pipe:1'],timeout=10)
            next_rgb=subprocess.check_output(common+['-ss','6','-i',str(recording),'-frames:v','1',
                '-f','rawvideo','-pix_fmt','rgb24','pipe:1'],timeout=10)
            pcm=subprocess.check_output(common+['-ss','5','-i',str(recording),'-t','1',
                '-vn','-ac','1','-ar','48000','-f','s16le','pipe:1'],timeout=10)
            samples=array.array('h',pcm)
            if not samples:
                raise RuntimeError('No decoded audio samples')
            rms=math.sqrt(sum(x*x for x in samples)/len(samples))/32768
            if not rgb or not samples or max(rgb)-min(rgb)<100 or rms<.005 or rgb==next_rgb:
                raise RuntimeError('Decoded OBS output was blank, frozen, or silent')
            result=dict(status='passed', recording=str(recording), probe=probe,
                        decoded_audio_rms=rms, rgb_range=max(rgb)-min(rgb), distinct_frames=True,
                        scope='Synthetic FFmpeg sender -> loopback SRT -> OBS Media Source -> OBS recording')
            if recovery:
                if not interrupted or not restored:
                    raise RuntimeError('Recovery fault sequence did not execute')
                checks={}
                frames={}
                for label,offset in [('before',5),('outage',14),('recovered',24),('recovered_next',25)]:
                    pixels=subprocess.check_output(common+['-ss',str(offset),'-i',str(recording),
                        '-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],timeout=10)
                    audio=subprocess.check_output(common+['-ss',str(offset),'-i',str(recording),
                        '-t','0.5','-vn','-ac','1','-ar','48000','-f','s16le','pipe:1'],timeout=10)
                    values=array.array('h',audio)
                    if not pixels or not values:
                        raise RuntimeError(f'Missing decoded recovery samples: {label}')
                    frames[label]=pixels
                    checks[label]=dict(offset=offset,rgb_range=max(pixels)-min(pixels),
                        audio_rms=math.sqrt(sum(x*x for x in values)/len(values))/32768)
                    subprocess.run(common+['-y','-ss',str(offset),'-i',str(recording),
                        '-frames:v','1','-update','1',str(output/f'{label}.png')],check=True,timeout=10)
                for label in ('before','recovered','recovered_next'):
                    if checks[label]['rgb_range']<100 or checks[label]['audio_rms']<.005:
                        raise RuntimeError(f'Feed not present at recovery checkpoint: {label}')
                if checks['outage']['audio_rms']>.001 or checks['outage']['rgb_range']>20:
                    raise RuntimeError('Expected black/silent outage checkpoint not observed')
                if frames['recovered']==frames['recovered_next']:
                    raise RuntimeError('Recovered video was frozen')
                result['recovery']=dict(events=events,checkpoints=checks,
                    scope='Local sender process interruption and restart; not packet-loss simulation')
            (output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(dict(status='passed',artifacts=str(output),audio_rms=rms),indent=2))
            return output
    finally:
        if sender and sender.poll() is None:
            sender.terminate()
            sender.wait(timeout=5)
        # Leave OBS open for inspection. The timer stops recording automatically.


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--obs-directory',required=True)
    parser.add_argument('--seconds',type=int,choices=range(8,31),default=12)
    parser.add_argument('--recovery',action='store_true',help='30-second stop/restart fault exercise')
    args=parser.parse_args()
    ffmpeg=os.environ.get('FFMPEG_PATH') or shutil.which('ffmpeg')
    ffprobe=os.environ.get('FFPROBE_PATH') or shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        parser.error('Set FFMPEG_PATH and FFPROBE_PATH, or add both tools to PATH')
    run(args.obs_directory,ffmpeg,ffprobe,args.seconds,args.recovery)
