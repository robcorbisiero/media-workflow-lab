param([string]$FfmpegDirectory)
$ErrorActionPreference = 'Stop'
if ($FfmpegDirectory) {
    $env:FFMPEG_PATH = (Resolve-Path -LiteralPath (Join-Path $FfmpegDirectory 'ffmpeg.exe')).Path
    $env:FFPROBE_PATH = (Resolve-Path -LiteralPath (Join-Path $FfmpegDirectory 'ffprobe.exe')).Path
}
Push-Location (Split-Path $PSScriptRoot -Parent)
try { python lab.py } finally { Pop-Location }
