"""
Audio Forensics Analyzer
Detects potential edit points in audio files using multiple analysis techniques.
"""

import numpy as np
from scipy import signal
from scipy.ndimage import uniform_filter1d
import librosa
from dataclasses import dataclass
from typing import List, Tuple, Optional
import warnings

warnings.filterwarnings('ignore')


@dataclass
class EditPoint:
    """Represents a detected potential edit point in audio."""
    timestamp: float  # Time in seconds
    confidence: float  # 0-1 confidence score
    detection_method: str  # Which algorithm detected it
    description: str  # Human-readable description


@dataclass
class AnalysisResult:
    """Complete analysis result for an audio file."""
    duration: float
    sample_rate: int
    edit_points: List[EditPoint]
    waveform_data: np.ndarray
    spectrogram_data: Optional[np.ndarray]
    spectrogram_times: Optional[np.ndarray]
    spectrogram_freqs: Optional[np.ndarray]
    analysis_metadata: dict
    method_plots: dict


class AudioForensicsAnalyzer:
    """
    Multi-method audio forensics analyzer for detecting edits and splices.

    Detection methods:
    1. Waveform discontinuity - sudden amplitude changes
    2. Zero-crossing rate anomalies - unnatural transitions
    3. Spectral flux analysis - frequency content changes
    4. Short-time energy discontinuities - volume jumps
    5. Phase coherence analysis - phase discontinuities
    6. Background noise analysis - ambient noise changes
    """

    def __init__(self, sensitivity: float = 0.5):
        """
        Initialize analyzer with sensitivity setting.

        Args:
            sensitivity: 0-1, higher = more sensitive (more detections, more false positives)
        """
        self.sensitivity = np.clip(sensitivity, 0.1, 1.0)

    def analyze(self, audio_path: str) -> AnalysisResult:
        """
        Perform complete forensic analysis on an audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            AnalysisResult with all detection data
        """
        # Load audio
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        duration = len(y) / sr

        # Collect edit points from all detection methods
        all_edit_points = []
        method_plots = {}

        # Run all detection algorithms
        waveform_points, waveform_plot = self._detect_waveform_discontinuities(y, sr)
        all_edit_points.extend(waveform_points)
        method_plots['waveform_discontinuity'] = waveform_plot

        zcr_points, zcr_plot = self._detect_zcr_anomalies(y, sr)
        all_edit_points.extend(zcr_points)
        method_plots['zero_crossing_rate'] = zcr_plot

        flux_points, flux_plot = self._detect_spectral_flux_anomalies(y, sr)
        all_edit_points.extend(flux_points)
        method_plots['spectral_flux'] = flux_plot

        energy_points, energy_plot = self._detect_energy_discontinuities(y, sr)
        all_edit_points.extend(energy_points)
        method_plots['energy_discontinuity'] = energy_plot

        phase_points, phase_plot = self._detect_phase_discontinuities(y, sr)
        all_edit_points.extend(phase_points)
        method_plots['phase_discontinuity'] = phase_plot

        noise_points, noise_plot = self._detect_noise_floor_changes(y, sr)
        all_edit_points.extend(noise_points)
        method_plots['noise_floor'] = noise_plot

        # Merge nearby detections and boost confidence for multiple method agreements
        merged_points = self._merge_nearby_detections(all_edit_points)

        # Sort by timestamp
        merged_points.sort(key=lambda x: x.timestamp)

        # Generate spectrogram for visualization
        spec_data, spec_times, spec_freqs = self._compute_spectrogram(y, sr)

        # Downsample waveform for visualization (keep ~10000 points max)
        waveform_display = self._downsample_waveform(y, target_points=10000)

        return AnalysisResult(
            duration=duration,
            sample_rate=sr,
            edit_points=merged_points,
            waveform_data=waveform_display,
            spectrogram_data=spec_data,
            spectrogram_times=spec_times,
            spectrogram_freqs=spec_freqs,
            analysis_metadata={
                'sensitivity': self.sensitivity,
                'total_samples': len(y),
                'methods_used': [
                    'waveform_discontinuity',
                    'zero_crossing_rate',
                    'spectral_flux',
                    'energy_discontinuity',
                    'phase_coherence',
                    'noise_floor'
                ]
            },
            method_plots=method_plots
        )

    def _detect_waveform_discontinuities(self, y: np.ndarray, sr: int) -> Tuple[List[EditPoint], dict]:
        """
        Detect sudden jumps in the waveform that indicate hard cuts.
        """
        edit_points = []

        # Calculate sample-to-sample differences
        diff = np.abs(np.diff(y))

        # Use adaptive threshold based on local statistics
        window_size = int(sr * 0.1)  # 100ms window
        local_mean = uniform_filter1d(diff, size=window_size, mode='reflect')
        local_std = np.sqrt(uniform_filter1d((diff - local_mean)**2, size=window_size, mode='reflect'))

        # Threshold: mean + (sensitivity-adjusted) * std
        threshold_multiplier = 6.0 - (self.sensitivity * 4.0)  # 2-6 std
        threshold = local_mean + threshold_multiplier * local_std

        # Find peaks above threshold
        peaks, properties = signal.find_peaks(diff, height=threshold, distance=int(sr * 0.05))

        for peak in peaks:
            # Calculate confidence based on how much it exceeds threshold
            if peak < len(threshold):
                excess = diff[peak] / (threshold[peak] + 1e-10)
                confidence = min(1.0, (excess - 1.0) / 3.0)

                if confidence > 0.1:
                    edit_points.append(EditPoint(
                        timestamp=peak / sr,
                        confidence=confidence,
                        detection_method='waveform_discontinuity',
                        description='Sudden amplitude jump detected'
                    ))

        plot_values, plot_times = self._prepare_plot_series(diff, sr)
        plot_data = {
            'times': plot_times,
            'values': plot_values
        }

        return edit_points, plot_data

    def _detect_zcr_anomalies(self, y: np.ndarray, sr: int) -> Tuple[List[EditPoint], dict]:
        """
        Detect anomalies in zero-crossing rate which indicate unnatural transitions.
        """
        edit_points = []

        # Calculate frame-based zero-crossing rate
        frame_length = int(sr * 0.025)  # 25ms frames
        hop_length = int(sr * 0.010)    # 10ms hop

        zcr = librosa.feature.zero_crossing_rate(y, frame_length=frame_length, hop_length=hop_length)[0]

        # Calculate rate of change in ZCR
        zcr_diff = np.abs(np.diff(zcr))

        # Find anomalies
        mean_diff = np.mean(zcr_diff)
        std_diff = np.std(zcr_diff)
        threshold = mean_diff + (3.0 - self.sensitivity * 2.0) * std_diff

        anomaly_frames = np.where(zcr_diff > threshold)[0]

        for frame in anomaly_frames:
            timestamp = librosa.frames_to_time(frame, sr=sr, hop_length=hop_length)
            confidence = min(1.0, (zcr_diff[frame] - threshold) / (std_diff + 1e-10) * 0.3)

            if confidence > 0.1:
                edit_points.append(EditPoint(
                    timestamp=timestamp,
                    confidence=confidence,
                    detection_method='zero_crossing_rate',
                    description='Abnormal zero-crossing rate transition'
                ))

        plot_values, plot_times = self._prepare_plot_series(zcr_diff, sr, hop_length=hop_length)
        plot_data = {
            'times': plot_times,
            'values': plot_values
        }

        return edit_points, plot_data

    def _detect_spectral_flux_anomalies(self, y: np.ndarray, sr: int) -> Tuple[List[EditPoint], dict]:
        """
        Detect sudden changes in spectral content using spectral flux.
        """
        edit_points = []

        # Compute STFT
        n_fft = 2048
        hop_length = 512
        S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))

        # Calculate spectral flux (frame-to-frame spectral difference)
        flux = np.sqrt(np.sum(np.diff(S, axis=1)**2, axis=0))

        # Normalize
        flux = flux / (np.max(flux) + 1e-10)

        # Adaptive threshold
        mean_flux = np.mean(flux)
        std_flux = np.std(flux)
        threshold = mean_flux + (2.5 - self.sensitivity * 1.5) * std_flux

        # Find peaks
        peaks, _ = signal.find_peaks(flux, height=threshold, distance=int(sr / hop_length * 0.1))

        for peak in peaks:
            timestamp = librosa.frames_to_time(peak, sr=sr, hop_length=hop_length)
            confidence = min(1.0, (flux[peak] - threshold) / (std_flux + 1e-10) * 0.4)

            if confidence > 0.15:
                edit_points.append(EditPoint(
                    timestamp=timestamp,
                    confidence=confidence,
                    detection_method='spectral_flux',
                    description='Sudden spectral content change'
                ))

        plot_values, plot_times = self._prepare_plot_series(flux, sr, hop_length=hop_length)
        plot_data = {
            'times': plot_times,
            'values': plot_values
        }

        return edit_points, plot_data

    def _detect_energy_discontinuities(self, y: np.ndarray, sr: int) -> Tuple[List[EditPoint], dict]:
        """
        Detect sudden changes in short-time energy (volume jumps).
        """
        edit_points = []

        # Calculate RMS energy
        frame_length = int(sr * 0.025)
        hop_length = int(sr * 0.010)

        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

        # Convert to dB
        rms_db = librosa.amplitude_to_db(rms + 1e-10)

        # Calculate frame-to-frame difference
        energy_diff = np.abs(np.diff(rms_db))

        # Threshold for sudden energy change (in dB)
        threshold = 6.0 - self.sensitivity * 3.0  # 3-6 dB

        jumps = np.where(energy_diff > threshold)[0]

        for jump in jumps:
            timestamp = librosa.frames_to_time(jump, sr=sr, hop_length=hop_length)
            confidence = min(1.0, (energy_diff[jump] - threshold) / 10.0)

            if confidence > 0.1:
                edit_points.append(EditPoint(
                    timestamp=timestamp,
                    confidence=confidence,
                    detection_method='energy_discontinuity',
                    description=f'Sudden energy change ({energy_diff[jump]:.1f} dB)'
                ))

        plot_values, plot_times = self._prepare_plot_series(energy_diff, sr, hop_length=hop_length)
        plot_data = {
            'times': plot_times,
            'values': plot_values
        }

        return edit_points, plot_data

    def _detect_phase_discontinuities(self, y: np.ndarray, sr: int) -> Tuple[List[EditPoint], dict]:
        """
        Detect phase discontinuities that often occur at edit points.
        """
        edit_points = []

        # Compute STFT with phase
        n_fft = 2048
        hop_length = 512
        D = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)

        # Get phase
        phase = np.angle(D)

        # Calculate phase derivative (instantaneous frequency deviation)
        phase_diff = np.diff(phase, axis=1)

        # Unwrap phase differences
        phase_diff = np.angle(np.exp(1j * phase_diff))

        # Calculate phase coherence across frequency bands
        phase_variance = np.var(phase_diff, axis=0)

        # Normalize
        phase_variance = phase_variance / (np.max(phase_variance) + 1e-10)

        # Find anomalies
        mean_var = np.mean(phase_variance)
        std_var = np.std(phase_variance)
        threshold = mean_var + (2.0 - self.sensitivity) * std_var

        anomalies = np.where(phase_variance > threshold)[0]

        for frame in anomalies:
            timestamp = librosa.frames_to_time(frame, sr=sr, hop_length=hop_length)
            confidence = min(1.0, (phase_variance[frame] - threshold) / (std_var + 1e-10) * 0.3)

            if confidence > 0.15:
                edit_points.append(EditPoint(
                    timestamp=timestamp,
                    confidence=confidence,
                    detection_method='phase_discontinuity',
                    description='Phase coherence anomaly detected'
                ))

        plot_values, plot_times = self._prepare_plot_series(phase_variance, sr, hop_length=hop_length)
        plot_data = {
            'times': plot_times,
            'values': plot_values
        }

        return edit_points, plot_data

    def _detect_noise_floor_changes(self, y: np.ndarray, sr: int) -> Tuple[List[EditPoint], dict]:
        """
        Detect changes in background noise floor that indicate different recording segments.
        """
        edit_points = []

        # Analyze in longer segments to capture background noise characteristics
        segment_length = int(sr * 0.5)  # 500ms segments
        hop = int(sr * 0.1)  # 100ms hop

        noise_floors = []

        for i in range(0, len(y) - segment_length, hop):
            segment = y[i:i + segment_length]

            # Estimate noise floor as lower percentile of amplitude
            sorted_amp = np.sort(np.abs(segment))
            noise_floor = np.mean(sorted_amp[:int(len(sorted_amp) * 0.1)])
            noise_floors.append(noise_floor)

        noise_floors = np.array(noise_floors)

        if len(noise_floors) > 2:
            # Detect sudden changes in noise floor
            noise_diff = np.abs(np.diff(noise_floors))

            mean_diff = np.mean(noise_diff)
            std_diff = np.std(noise_diff)
            threshold = mean_diff + (2.5 - self.sensitivity * 1.5) * std_diff

            changes = np.where(noise_diff > threshold)[0]

            for change in changes:
                timestamp = change * hop / sr
                confidence = min(1.0, (noise_diff[change] - threshold) / (std_diff + 1e-10) * 0.4)

                if confidence > 0.15:
                    edit_points.append(EditPoint(
                        timestamp=timestamp,
                        confidence=confidence,
                        detection_method='noise_floor',
                        description='Background noise level change'
                    ))

        if len(noise_floors) > 1:
            noise_diff = np.abs(np.diff(noise_floors))
            times = (np.arange(len(noise_diff)) * hop) / sr
        else:
            noise_diff = np.array([])
            times = np.array([])

        plot_values, plot_times = self._prepare_plot_series(noise_diff, sr, times=times)
        plot_data = {
            'times': plot_times,
            'values': plot_values
        }

        return edit_points, plot_data

    def _prepare_plot_series(
        self,
        values: np.ndarray,
        sr: int,
        hop_length: Optional[int] = None,
        times: Optional[np.ndarray] = None,
        target_points: int = 1200
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Downsample a time series for plotting and return aligned times."""
        values = np.asarray(values)
        if times is None:
            if hop_length is None:
                times = np.arange(len(values)) / sr
            else:
                times = librosa.frames_to_time(
                    np.arange(len(values)),
                    sr=sr,
                    hop_length=hop_length
                )
        else:
            times = np.asarray(times)

        if len(values) == 0:
            return values, times

        if len(values) > target_points:
            idx = np.linspace(0, len(values) - 1, target_points).astype(int)
            values = values[idx]
            times = times[idx]

        return values, times

    def _merge_nearby_detections(self, edit_points: List[EditPoint],
                                   time_threshold: float = 0.1) -> List[EditPoint]:
        """
        Merge detections that are close in time and boost confidence for multi-method agreement.
        """
        if not edit_points:
            return []

        # Sort by timestamp
        sorted_points = sorted(edit_points, key=lambda x: x.timestamp)

        merged = []
        current_group = [sorted_points[0]]

        for point in sorted_points[1:]:
            if point.timestamp - current_group[-1].timestamp <= time_threshold:
                current_group.append(point)
            else:
                merged.append(self._merge_group(current_group))
                current_group = [point]

        merged.append(self._merge_group(current_group))

        return merged

    def _merge_group(self, group: List[EditPoint]) -> EditPoint:
        """Merge a group of nearby detections into one."""
        if len(group) == 1:
            return group[0]

        # Average timestamp
        avg_timestamp = np.mean([p.timestamp for p in group])

        # Boost confidence based on number of methods agreeing
        methods = set(p.detection_method for p in group)
        base_confidence = max(p.confidence for p in group)

        # Boost for multi-method agreement (up to 1.5x for 3+ methods)
        method_boost = 1.0 + 0.15 * (len(methods) - 1)
        boosted_confidence = min(1.0, base_confidence * method_boost)

        # Combine descriptions
        descriptions = list(set(p.description for p in group))
        combined_desc = '; '.join(descriptions[:3])
        if len(descriptions) > 3:
            combined_desc += f' (+{len(descriptions) - 3} more)'

        return EditPoint(
            timestamp=avg_timestamp,
            confidence=boosted_confidence,
            detection_method=f"combined({','.join(methods)})",
            description=f"[{len(methods)} methods] {combined_desc}"
        )

    def _compute_spectrogram(self, y: np.ndarray, sr: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute mel spectrogram for visualization."""
        # Use mel spectrogram for better visualization
        n_mels = 128
        hop_length = 512

        S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=n_mels, hop_length=hop_length)
        S_db = librosa.power_to_db(S, ref=np.max)

        # Get time and frequency axes
        times = librosa.frames_to_time(np.arange(S_db.shape[1]), sr=sr, hop_length=hop_length)
        freqs = librosa.mel_frequencies(n_mels=n_mels, fmax=sr/2)

        return S_db, times, freqs

    def _downsample_waveform(self, y: np.ndarray, target_points: int = 10000) -> np.ndarray:
        """Downsample waveform for efficient visualization."""
        if len(y) <= target_points:
            return y

        # Use peak-preserving downsampling
        factor = len(y) // target_points

        # Reshape to find min/max in each chunk
        truncated_len = (len(y) // factor) * factor
        reshaped = y[:truncated_len].reshape(-1, factor)

        # Interleave min and max for each chunk to preserve peaks
        mins = reshaped.min(axis=1)
        maxs = reshaped.max(axis=1)

        result = np.empty(len(mins) + len(maxs), dtype=y.dtype)
        result[0::2] = mins
        result[1::2] = maxs

        return result
