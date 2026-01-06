"""
Audio Forensics Web Application
Flask backend for audio edit detection.
"""

import os
import uuid
import json
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import numpy as np

from audio_analyzer import AudioForensicsAnalyzer, AnalysisResult

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# Configuration
UPLOAD_FOLDER = tempfile.mkdtemp()
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'flac', 'ogg', 'm4a', 'aac', 'wma', 'aiff'}
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def analysis_result_to_dict(result: AnalysisResult) -> dict:
    """Convert AnalysisResult to JSON-serializable dict."""
    return {
        'duration': result.duration,
        'sampleRate': result.sample_rate,
        'editPoints': [
            {
                'timestamp': ep.timestamp,
                'confidence': ep.confidence,
                'method': ep.detection_method,
                'description': ep.description
            }
            for ep in result.edit_points
        ],
        'waveform': result.waveform_data.tolist(),
        'spectrogram': {
            'data': result.spectrogram_data.tolist() if result.spectrogram_data is not None else None,
            'times': result.spectrogram_times.tolist() if result.spectrogram_times is not None else None,
            'freqs': result.spectrogram_freqs.tolist() if result.spectrogram_freqs is not None else None
        },
        'metadata': result.analysis_metadata
    }


@app.route('/')
def index():
    """Serve the main application page."""
    return send_from_directory('static', 'index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze_audio():
    """
    Analyze an uploaded audio file for potential edit points.

    Request:
        - file: Audio file (multipart/form-data)
        - sensitivity: Optional float 0-1 (default 0.5)

    Response:
        - JSON with analysis results
    """
    # Check if file was uploaded
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({
            'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 400

    # Get sensitivity parameter
    try:
        sensitivity = float(request.form.get('sensitivity', 0.5))
        sensitivity = max(0.1, min(1.0, sensitivity))
    except (TypeError, ValueError):
        sensitivity = 0.5

    # Save file temporarily
    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4()}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

    try:
        file.save(filepath)

        # Analyze the audio
        analyzer = AudioForensicsAnalyzer(sensitivity=sensitivity)
        result = analyzer.analyze(filepath)

        # Convert to JSON-serializable format
        response_data = analysis_result_to_dict(result)
        response_data['filename'] = filename

        return jsonify(response_data)

    except Exception as e:
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

    finally:
        # Clean up uploaded file
        if os.path.exists(filepath):
            os.remove(filepath)


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'audio-forensics-analyzer'})


if __name__ == '__main__':
    # Ensure static folder exists
    os.makedirs('static', exist_ok=True)

    print("Starting Audio Forensics Analyzer...")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print("Server running at http://localhost:5000")

    app.run(host='0.0.0.0', port=5000, debug=True)
