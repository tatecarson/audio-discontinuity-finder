# Audio Forensics - Edit Detection Tool

A web-based application for detecting difficult-to-find edits, splices, and discontinuities in audio recordings. Useful for audio forensics, quality assurance, and identifying potential tampering in recordings.

## Features

- **Multiple Detection Algorithms**: Uses 6 different analysis methods to detect edit points:
  - Waveform discontinuity detection (sudden amplitude jumps)
  - Zero-crossing rate anomaly detection
  - Spectral flux analysis (frequency content changes)
  - Short-time energy discontinuities (volume jumps)
  - Phase coherence analysis
  - Background noise floor change detection

- **Interactive Visualization**:
  - Waveform display with edit markers
  - Mel spectrogram visualization
  - Timeline with clickable edit point markers
  - Audio playback with navigation to edit points

- **Confidence Scoring**: Each detected edit point includes:
  - Confidence score (0-100%)
  - Detection method(s) used
  - Description of the anomaly

- **Adjustable Sensitivity**: Control detection sensitivity to balance between finding subtle edits and reducing false positives

## Supported Audio Formats

WAV, MP3, FLAC, OGG, M4A, AAC, WMA, AIFF

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd audio-discontinuity-finder
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Start the application:
   ```bash
   python app.py
   ```

2. Open your browser to `http://localhost:5001`

3. Upload an audio file by:
   - Clicking "Choose File" button
   - Dragging and dropping onto the upload area

4. Adjust the sensitivity slider (higher = more sensitive, may produce more false positives)

5. Click "Analyze Audio" to process the file

6. Review results:
   - View waveform or spectrogram visualizations
   - Click on timeline markers to jump to edit points
   - Use "Previous Edit" / "Next Edit" buttons to navigate
   - Filter edit points by confidence level

## Detection Methods Explained

### Waveform Discontinuity
Detects sudden jumps in amplitude that exceed the local statistical threshold. Hard cuts often produce visible discontinuities in the waveform.

### Zero-Crossing Rate
Analyzes the rate at which the audio signal crosses zero amplitude. Edits can cause unnatural transitions in this rate.

### Spectral Flux
Measures frame-to-frame changes in the frequency spectrum. Spliced audio segments often have different spectral characteristics.

### Energy Discontinuity
Detects sudden changes in audio volume (RMS energy). Even carefully edited audio may have subtle level mismatches.

### Phase Coherence
Analyzes phase relationships across frequency bands. Edits can introduce phase discontinuities that are imperceptible to hearing but detectable through analysis.

### Noise Floor
Tracks changes in background noise level. Different recording environments or equipment produce different ambient noise signatures.

## API

### POST /api/analyze

Analyze an audio file for edit points.

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Body:
  - `file`: Audio file
  - `sensitivity`: Float 0.1-1.0 (optional, default 0.5)

**Response:**
```json
{
  "duration": 120.5,
  "sampleRate": 44100,
  "editPoints": [
    {
      "timestamp": 45.234,
      "confidence": 0.85,
      "method": "combined(spectral_flux,energy_discontinuity)",
      "description": "[2 methods] Sudden spectral content change; Sudden energy change (8.5 dB)"
    }
  ],
  "waveform": [...],
  "spectrogram": {...},
  "metadata": {...}
}
```

## Deployment

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `5001` | Server port |
| `HOST` | `0.0.0.0` | Server host |
| `FLASK_DEBUG` | `false` | Enable debug mode |
| `MAX_CONTENT_MB` | `100` | Max upload size in MB |

### Docker

```bash
docker compose up --build
```

The app will be available at `http://localhost:8080`

### Fly.io

```bash
fly launch --copy-config
fly deploy
```

### Heroku / Railway / Render

These platforms auto-detect the `Procfile`. Just connect your repo and deploy.

### Manual Production

```bash
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:8080 --workers 2 --threads 4 --timeout 120 app:app
```

## Technical Details

- Built with Flask (Python) backend
- Uses librosa for audio analysis
- NumPy and SciPy for signal processing
- Pure JavaScript frontend (no frameworks)
- Canvas-based visualizations
- Gunicorn for production serving

## Limitations

- Analysis accuracy depends on audio quality and edit techniques
- Heavily processed or compressed audio may reduce detection accuracy
- Not all detected points are actual edits (false positives possible)
- Very subtle edits may not be detected (false negatives possible)
- Processing time increases with file length

## License

MIT License
