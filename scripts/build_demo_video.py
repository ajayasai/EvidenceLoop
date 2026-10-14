"""Build an explicitly labelled screenshot walkthrough with local Windows TTS.

Consumes inspected deck renders and the submission narration. No network calls,
browser automation, or live-inference claims are introduced by this builder.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / '.runtime' / 'submission-video-build'
OUT = ROOT / 'artifacts' / 'submission-20261014'


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        raise SystemExit('The already-installed ffmpeg and ffprobe are required.')
    rows = []
    script = (ROOT / 'docs/submission/DEMO_6MIN.md').read_text(encoding='utf-8')
    for line in script.splitlines():
        match = re.match(r'^\| (\d):(\d{2})[\u2013-](\d):(\d{2}) \| (.*?) \| (.*?) \|$', line)
        if not match:
            continue
        a, b, c, d, shot, narration = match.groups()
        if len(rows) == 10:
            break
        narration = narration.strip('\u201c\u201d"')
        rows.append({'index': len(rows) + 1, 'planned_seconds': int(c) * 60 + int(d) - int(a) * 60 - int(b),
                     'shot': shot, 'narration': narration})
    if len(rows) != 10:
        raise SystemExit('Expected ten timed narration rows; verify the source script.')
    rows[0]['narration'] = ('This is a recorded screenshot walkthrough with synthetic narration. ' + rows[0]['narration'])
    for row in rows:
        row['wave_path'] = str(BUILD / f"voice-{row['index']:02}.wav")
    (BUILD / 'narration.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    speech_script = BUILD / 'synthesize.ps1'
    speech_script.write_text('''$ErrorActionPreference = 'Stop'
$taskNarration = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'narration.json') -Raw | ConvertFrom-Json
$taskVoice = New-Object -ComObject SAPI.SpVoice
$taskVoice.Rate = -1
foreach ($taskInstalledVoice in $taskVoice.GetVoices()) {
    if ($taskInstalledVoice.GetDescription() -eq 'Microsoft Zira Desktop - English (United States)') { $taskVoice.Voice = $taskInstalledVoice }
}
foreach ($taskPart in $taskNarration) {
    $taskStream = New-Object -ComObject SAPI.SpFileStream
    $taskStream.Open($taskPart.wave_path, 3, $false)
    $taskVoice.AudioOutputStream = $taskStream
    [void]$taskVoice.Speak($taskPart.narration)
    $taskStream.Close()
}
Write-Output ('Generated local narration with ' + $taskVoice.Voice.GetDescription())
''', encoding='utf-8')
    subprocess.run(['powershell.exe', '-NoProfile', '-File', str(speech_script)], check=True)
    clips, elapsed, subtitles = [], 0.0, []
    def stamp(seconds: float) -> str:
        ms = round(seconds * 1000)
        return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}'
    for row in rows:
        index = row['index']
        frame = OUT / 'deck' / 'slides' / f'slide-{index:02}.png'
        if not frame.is_file():
            raise SystemExit(f'Missing inspected slide render: {frame}')
        wave = row['wave_path']
        seconds = float(subprocess.check_output([ffprobe, '-v', 'error', '-show_entries', 'format=duration',
                                                '-of', 'default=noprint_wrappers=1:nokey=1', wave], text=True))
        duration = max(row['planned_seconds'], seconds + 1.5)
        row.update({'audio_seconds': seconds, 'video_seconds': duration, 'starts_at_seconds': elapsed})
        clip = BUILD / f'chapter-{index:02}.mp4'
        subprocess.run([ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-loop', '1', '-framerate', '15', '-i', str(frame),
                        '-i', wave, '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0xf8f7ef,setsar=1',
                        '-af', 'apad', '-t', str(duration), '-c:v', 'libx264', '-preset', 'fast', '-tune', 'stillimage',
                        '-crf', '23', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '96k', '-ar', '44100', '-ac', '1', str(clip)], check=True)
        clips.append(clip)
        # Short caption units remain readable; timing is estimated within the spoken segment.
        words = row['narration'].split()
        for start in range(0, len(words), 13):
            end = min(start + 13, len(words))
            subtitles.append(f"{len(subtitles)+1}\n{stamp(elapsed+seconds*start/len(words))} --> {stamp(elapsed+seconds*end/len(words))}\n{' '.join(words[start:end])}\n")
        elapsed += duration
    if not 300 <= elapsed <= 480:
        raise SystemExit(f'Video duration {elapsed:.2f}s is outside the five-to-eight-minute target.')
    concat = BUILD / 'concat.txt'
    concat.write_text(''.join(f"file '{clip.as_posix()}'\n" for clip in clips), encoding='utf-8')
    final = OUT / 'EvidenceLoop-recorded-walkthrough.mp4'
    subprocess.run([ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat),
                    '-c', 'copy', '-movflags', '+faststart', str(final)], check=True)
    (OUT / 'EvidenceLoop-recorded-walkthrough.srt').write_text('\n'.join(subtitles), encoding='utf-8')
    (OUT / 'video-manifest.json').write_text(json.dumps({'format': 'Recorded screenshot walkthrough, synthetic offline narration',
        'voice': 'Microsoft Zira Desktop - English (United States)', 'additional_cost': 0,
        'live_screen_recording': False, 'live_model_response_shown': False,
        'caption_timing': 'Estimated per spoken segment; supplied as a separate editable SRT.',
        'duration_seconds': elapsed,
        'chapters': [{key: value for key, value in row.items() if key != 'wave_path'} for row in rows]},
        indent=2), encoding='utf-8')
    print(json.dumps({'output': str(final), 'duration_seconds': round(elapsed, 3), 'chapters': len(rows)}))


if __name__ == '__main__':
    main()
