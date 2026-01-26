# Signal Alert Sound

## Required File

- **Filename**: `signal-alert.mp3`
- **Format**: MP3, 44.1kHz
- **Duration**: 0.5-1.0 seconds
- **Style**: Professional, non-intrusive chime
- **File Size**: < 50KB

## Description

This directory should contain the audio file that plays when a new trading signal is generated.

The sound should be:

- Professional and pleasant
- Not jarring or alarming
- Suitable for office/trading environment
- Clear enough to notice but not disruptive

## Suggested Sources

1. **Free Sound Libraries**:

   - freesound.org (search: "notification chime")
   - mixkit.co/free-sound-effects/notification/
   - zapsplat.com

2. **Create Your Own**:
   - Use tools like Audacity or GarageBand
   - Export as MP3 at 44.1kHz

## Implementation

The audio file is loaded by `SignalToastService.ts` and played when:

- Sound alerts are enabled in settings
- A new signal notification arrives
- Signal meets confidence threshold (if filter enabled)

Volume is controlled by user settings (0-100%).
