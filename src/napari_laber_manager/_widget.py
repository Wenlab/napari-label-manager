"""
Napari Label Manager Plugin
A plugin for batch management of label colors and opacity in napari.

Performance Optimizations for Large Label Layers:

Memory-Efficient Strategies:
1. **Time-Series Optimization**: For 4D+ arrays, only process current time slice
2. **Block Sampling**: Use systematic sampling instead of random indices to avoid memory allocation
3. **Tiered Sampling**:
   - Normal arrays: Exact computation
   - Large arrays (>10M pixels): Block sampling with 500k sample size
   - Extremely large arrays: Minimal sampling with 50k sample size
4. **Caching System**: Results cached per layer ID to avoid recomputation
5. **Delayed Updates**: Layer info updates delayed to prevent UI blocking
6. **Background Computation**: Heavy computations run in separate threads
7. **Graceful Degradation**: Multiple fallback strategies for memory errors

Memory Usage Improvements:
- Avoids creating large index arrays (which caused the 140GB allocation error)
- Processes only current time slice for time-series data
- Uses step-based sampling instead of random.choice()
- Automatic fallback to smaller samples when memory is insufficient

These optimizations handle datasets with billions of pixels while maintaining responsiveness.
"""

import re
import threading

import napari
import numpy as np
from napari.utils import colormaps as cmap
from qtpy.QtCore import Qt, QTimer, Signal
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LabelManager(QWidget):
    """Main widget for label management."""

    # Signal emitted when colormap changes
    colormap_changed = Signal(object)

    def __init__(self, napari_viewer: napari.Viewer, parent=None):
        super().__init__(parent)
        self.viewer = napari_viewer
        self.current_layer = None
        self.full_color_dict = {}
        self.background_value = 0
        self.max_labels = 100

        # Performance optimization: cache for layer stats
        self._layer_stats_cache = {}
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._delayed_update_layer_info)

        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout()

        # set width
        self.setMinimumWidth(400)
        # Header
        header = QLabel("Label Manager")
        header.setFont(QFont("Arial", 12, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Layer selection
        layer_group = QGroupBox("Layer Selection")
        layer_layout = QVBoxLayout()

        self.layer_combo = QComboBox()
        self.layer_combo.currentTextChanged.connect(self.on_layer_changed)
        layer_layout.addWidget(QLabel("Select Label Layer:"))
        layer_layout.addWidget(self.layer_combo)

        layer_group.setLayout(layer_layout)
        layout.addWidget(layer_group)

        # Colormap generation
        colormap_group = QGroupBox("Colormap Generation")
        colormap_layout = QVBoxLayout()

        # Number of colors and seed
        gen_layout = QHBoxLayout()
        gen_layout.addWidget(QLabel("Max Labels:"))
        self.max_labels_spin = QSpinBox()
        self.max_labels_spin.setRange(1, 1000)
        self.max_labels_spin.setValue(self.max_labels)
        gen_layout.addWidget(self.max_labels_spin)

        gen_layout.addWidget(QLabel("Random Seed:"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 100)
        self.seed_spin.setValue(50)
        gen_layout.addWidget(self.seed_spin)

        self.generate_btn = QPushButton("Generate New Colormap")
        self.generate_btn.clicked.connect(self.generate_colormap)
        gen_layout.addWidget(self.generate_btn)

        colormap_layout.addLayout(gen_layout)
        colormap_group.setLayout(colormap_layout)
        layout.addWidget(colormap_group)

        # Batch management
        batch_group = QGroupBox("Batch Label Management")
        batch_layout = QVBoxLayout()

        # Label IDs input
        batch_layout.addWidget(
            QLabel("Label IDs (comma-separated, ranges with '-'):")
        )
        self.label_ids_input = QLineEdit()
        self.label_ids_input.setPlaceholderText("e.g., 1,3,5-10,20,25-30")
        batch_layout.addWidget(self.label_ids_input)

        # Quick presets
        presets_layout = QHBoxLayout()
        presets_layout.addWidget(QLabel("Quick presets:"))
        self.preset_first10_btn = QPushButton("First 10")
        self.preset_first10_btn.clicked.connect(
            lambda: self.set_preset_ids("1-10")
        )
        presets_layout.addWidget(self.preset_first10_btn)

        self.preset_even_btn = QPushButton("Even IDs")
        self.preset_even_btn.clicked.connect(
            lambda: self.set_preset_ids("even")
        )
        presets_layout.addWidget(self.preset_even_btn)

        self.preset_odd_btn = QPushButton("Odd IDs")
        self.preset_odd_btn.clicked.connect(lambda: self.set_preset_ids("odd"))
        presets_layout.addWidget(self.preset_odd_btn)

        self.preset_all_btn = QPushButton("All Current")
        self.preset_all_btn.clicked.connect(self.set_all_current_ids)
        presets_layout.addWidget(self.preset_all_btn)

        batch_layout.addLayout(presets_layout)

        # Opacity controls
        opacity_frame = QFrame()
        opacity_layout = QVBoxLayout()

        # Selected labels opacity
        selected_layout = QHBoxLayout()
        selected_layout.addWidget(QLabel("Selected Labels Opacity:"))
        self.selected_opacity_slider = QSlider(Qt.Horizontal)
        self.selected_opacity_slider.setRange(0, 100)
        self.selected_opacity_slider.setValue(100)
        self.selected_opacity_label = QLabel("1.00")
        self.selected_opacity_slider.valueChanged.connect(
            lambda v: self.selected_opacity_label.setText(f"{v/100:.2f}")
        )
        selected_layout.addWidget(self.selected_opacity_slider)
        selected_layout.addWidget(self.selected_opacity_label)
        opacity_layout.addLayout(selected_layout)

        # Other labels opacity
        other_layout = QHBoxLayout()
        other_layout.addWidget(QLabel("Other Labels Opacity:"))
        self.other_opacity_slider = QSlider(Qt.Horizontal)
        self.other_opacity_slider.setRange(0, 100)
        self.other_opacity_slider.setValue(50)
        self.other_opacity_label = QLabel("0.50")
        self.other_opacity_slider.valueChanged.connect(
            lambda v: self.other_opacity_label.setText(f"{v/100:.2f}")
        )
        other_layout.addWidget(self.other_opacity_slider)
        other_layout.addWidget(self.other_opacity_label)
        opacity_layout.addLayout(other_layout)

        # Hide other labels option
        self.hide_others_checkbox = QCheckBox(
            "Hide Other Labels (opacity = 0)"
        )
        self.hide_others_checkbox.toggled.connect(self.on_hide_others_toggled)
        opacity_layout.addWidget(self.hide_others_checkbox)

        opacity_frame.setLayout(opacity_layout)
        batch_layout.addWidget(opacity_frame)

        # Apply button
        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.clicked.connect(self.apply_changes)
        batch_layout.addWidget(self.apply_btn)

        batch_group.setLayout(batch_layout)
        layout.addWidget(batch_group)

        # Status and info
        info_group = QGroupBox("Status & Info")
        info_layout = QVBoxLayout()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: green;")
        info_layout.addWidget(self.status_label)

        self.info_text = QTextEdit()
        self.info_text.setMaximumHeight(100)
        self.info_text.setReadOnly(True)
        info_layout.addWidget(self.info_text)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        self.setLayout(layout)

    def connect_signals(self):
        """Connect viewer signals."""
        self.viewer.layers.events.inserted.connect(self.update_layer_combo)
        self.viewer.layers.events.removed.connect(self.on_layer_removed)
        self.viewer.layers.events.removed.connect(self.update_layer_combo)

        # Connect to layer events for cache invalidation
        self.viewer.layers.events.changed.connect(
            self.on_layer_properties_changed
        )

        self.update_layer_combo()

    def on_layer_removed(self, event):
        """Handle layer removal to clean up cache."""
        # Clean up cache for removed layers
        removed_layer = event.value
        layer_id = id(removed_layer)
        if layer_id in self._layer_stats_cache:
            del self._layer_stats_cache[layer_id]

    def on_layer_properties_changed(self, event):
        """Handle layer property changes that might affect cache validity."""
        # Clear cache when layer properties change (e.g., time step)
        if hasattr(event, "source") and hasattr(event.source, "current_step"):
            layer_id = id(event.source)
            if layer_id in self._layer_stats_cache:
                # Only clear if this is a time-series change
                del self._layer_stats_cache[layer_id]

    def update_layer_combo(self):
        """Update layer combo box with available label layers."""
        self.layer_combo.clear()
        label_layers = [
            layer.name
            for layer in self.viewer.layers
            if hasattr(layer, "colormap")
        ]
        self.layer_combo.addItems(label_layers)

    def on_layer_changed(self, layer_name: str):
        """Handle layer selection change."""
        if layer_name:
            try:
                self.current_layer = self.viewer.layers[layer_name]
                self.update_status(f"Selected layer: {layer_name}", "blue")

                # Initialize colormap if needed
                if hasattr(self.current_layer, "colormap"):
                    self.extract_current_colormap()

                # Clear cache for this layer
                layer_id = id(self.current_layer)
                if layer_id in self._layer_stats_cache:
                    del self._layer_stats_cache[layer_id]

                # Delay layer info update to avoid blocking UI
                self._update_timer.start(100)  # 100ms delay

            except KeyError:
                self.update_status(f"Layer '{layer_name}' not found", "red")

    def extract_current_colormap(self):
        """Extract current colormap from the selected layer."""
        if self.current_layer and hasattr(self.current_layer, "colormap"):
            colormap = self.current_layer.colormap
            if hasattr(colormap, "colors"):
                self.full_color_dict = {
                    i + 1: tuple(color)
                    for i, color in enumerate(colormap.colors)
                }
                self.full_color_dict[None] = (0.0, 0.0, 0.0, 0.0)
                if hasattr(colormap, "background_value"):
                    self.background_value = colormap.background_value

    def set_preset_ids(self, preset_type: str):
        """Set preset label IDs."""
        if preset_type == "1-10":
            self.label_ids_input.setText("1-10")
        elif preset_type == "even":
            even_ids = [str(i) for i in range(2, min(21, self.max_labels), 2)]
            self.label_ids_input.setText(",".join(even_ids))
        elif preset_type == "odd":
            odd_ids = [str(i) for i in range(1, min(21, self.max_labels), 2)]
            self.label_ids_input.setText(",".join(odd_ids))

    def parse_label_ids(self, ids_string: str) -> list:
        """Parse label IDs from string input using regex."""
        ids = set()
        pattern = (
            r"(\d+)(?:-(\d+))?"  # Matches single IDs or ranges like "1-5"
        )
        matches = re.findall(pattern, ids_string)
        if not ids_string.strip():
            return ids

        for start, end in matches:
            if end:
                # match a range
                ids.update(range(int(start), int(end) + 1))
            else:
                # match a single ID
                ids.add(int(start))

        return sorted(ids)  # Remove duplicates and sort

    def on_hide_others_toggled(self, checked: bool):
        """Handle hide others checkbox toggle."""
        self.other_opacity_slider.setEnabled(not checked)
        if checked:
            self.other_opacity_label.setText("0.00")
        else:
            self.other_opacity_label.setText(
                f"{self.other_opacity_slider.value()/100:.2f}"
            )

    def generate_colormap(self):
        """Generate a new random colormap."""
        self.max_labels = self.max_labels_spin.value()
        seed = self.seed_spin.value() / 100.0

        # Generate colormap
        colormap = self.generate_random_label_colormap(
            self.max_labels,
            background_value=self.background_value,
            random_seed=seed,
        )

        # Convert to color dict
        self.full_color_dict, self.background_value = (
            self.colormap_to_color_dict(colormap)
        )

        self.update_status(
            f"Generated colormap with {self.max_labels} colors", "green"
        )

    def apply_changes(self):
        """Apply opacity changes to selected labels."""
        if not self.current_layer:
            self.update_status("No layer selected", "red")
            return

        # Parse label IDs
        ids_string = self.label_ids_input.text()
        valid_ids = self.parse_label_ids(ids_string)

        if not valid_ids:
            self.update_status("No valid label IDs provided", "red")
            return

        # Get opacity values
        selected_opacity = self.selected_opacity_slider.value() / 100.0
        other_opacity = (
            0.0
            if self.hide_others_checkbox.isChecked()
            else self.other_opacity_slider.value() / 100.0
        )

        # Apply changes
        filtered_color_dict = self.get_filtered_color_dict(
            self.full_color_dict,
            valid_ids,
            selected_opacity=selected_opacity,
            other_opacity=other_opacity,
        )

        # Create and apply new colormap
        new_colormap = self.color_dict_to_color_map(
            filtered_color_dict,
            name=f"batch_managed_{len(valid_ids)}",
            background_value=self.background_value,
        )

        self.current_layer.colormap = new_colormap

        # Update info
        info_text = f"Applied to {len(valid_ids)} labels: {valid_ids[:10]}"
        if len(valid_ids) > 10:
            info_text += f"... (and {len(valid_ids) - 10} more)"
        info_text += f"\nSelected opacity: {selected_opacity:.2f}"
        info_text += f"\nOther opacity: {other_opacity:.2f}"

        self.info_text.setText(info_text)
        self.update_status("Changes applied successfully", "green")

        # Emit signal
        self.colormap_changed.emit(new_colormap)

    def update_status(self, message: str, color: str = "black"):
        """Update status label."""
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color};")

    # Core colormap functions
    def generate_random_label_colormap(
        self,
        num_colors: int,
        background_value: int = 0,
        random_seed: float = 0.5,
    ):
        """Generate random label colormap."""
        return cmap.label_colormap(num_colors, random_seed, background_value)

    def colormap_to_color_dict(self, colormap):
        """Convert colormap to color dictionary."""
        color_dict = {
            item_id + 1: tuple(color)
            for item_id, color in enumerate(colormap.colors)
        }
        color_dict[None] = (0.0, 0.0, 0.0, 0.0)
        background_value = (
            colormap.background_value
            if hasattr(colormap, "background_value")
            else 0
        )
        return color_dict, background_value

    def get_filtered_color_dict(
        self,
        full_color_dict,
        valid_ids,
        selected_opacity=1.0,
        other_opacity=0.5,
    ):
        """Get filtered color dictionary with batch opacity management."""
        filtered_color_dict = {}

        for key, color in full_color_dict.items():
            if key is None:
                # Keep background unchanged
                filtered_color_dict[key] = color
            elif key in valid_ids:
                # Apply selected opacity to valid IDs
                filtered_color_dict[key] = (
                    color[0],
                    color[1],
                    color[2],
                    selected_opacity,
                )
            else:
                # Apply other opacity to invalid IDs
                filtered_color_dict[key] = (
                    color[0],
                    color[1],
                    color[2],
                    other_opacity,
                )

        return filtered_color_dict

    def color_dict_to_color_map(
        self, color_dict, name="custom", background_value=0
    ):
        """Convert color dictionary to colormap."""
        direct_colormap = cmap.direct_colormap(color_dict)
        direct_colormap.background_value = background_value
        direct_colormap.name = name
        return direct_colormap

    def get_current_label_count(self) -> int:
        """Get the count of unique non-zero labels in the current layer."""
        if not self.current_layer or not hasattr(self.current_layer, "data"):
            return 0

        # Use cache to avoid expensive computation
        layer_id = id(self.current_layer)
        if layer_id in self._layer_stats_cache:
            return self._layer_stats_cache[layer_id]["count"]

        # For large arrays, use sampling for estimation
        data = self.current_layer.data
        if data.size > 10_000_000:  # 10M pixels
            return self._estimate_label_count_sampling(data, layer_id)

        # For smaller arrays, compute exactly
        unique_labels = np.unique(data)
        non_zero_labels = unique_labels[unique_labels != 0]
        count = len(non_zero_labels)

        # Cache the result
        self._layer_stats_cache[layer_id] = {
            "count": count,
            "ids": non_zero_labels.tolist(),
        }
        return count

    def get_current_label_ids(self) -> list:
        """Get list of unique non-zero label IDs in the current layer."""
        if not self.current_layer or not hasattr(self.current_layer, "data"):
            return []

        # Use cache to avoid expensive computation
        layer_id = id(self.current_layer)
        if layer_id in self._layer_stats_cache:
            return self._layer_stats_cache[layer_id]["ids"]

        # For large arrays, use sampling for estimation
        data = self.current_layer.data
        if data.size > 10_000_000:  # 10M pixels
            return self._estimate_label_ids_sampling(data, layer_id)

        # For smaller arrays, compute exactly
        unique_labels = np.unique(data)
        non_zero_labels = unique_labels[unique_labels != 0]
        ids = sorted(non_zero_labels.tolist())

        # Cache the result
        self._layer_stats_cache[layer_id] = {"count": len(ids), "ids": ids}
        return ids

    def update_layer_info(self):
        """Update layer information display (now optimized for large datasets)."""
        # This method is now handled by _delayed_update_layer_info
        # to prevent blocking the UI thread
        self._delayed_update_layer_info()

    def set_all_current_ids(self):
        """Set all current label IDs in the input field."""
        if label_ids := self.get_current_label_ids():
            ids_string = ",".join(map(str, label_ids))
            self.label_ids_input.setText(ids_string)

            layer_id = id(self.current_layer)
            cache_info = self._layer_stats_cache.get(layer_id, {})
            is_estimate = cache_info.get("is_estimate", False)
            is_minimal = cache_info.get("minimal_sample", False)

            if is_estimate:
                if is_minimal:
                    self.update_status(
                        f"Set ~{len(label_ids)} label IDs (minimal sample - very large dataset)",
                        "orange",
                    )
                else:
                    original_shape = cache_info.get("data_shape", "unknown")
                    self.update_status(
                        f"Set ~{len(label_ids)} estimated label IDs (shape: {original_shape})",
                        "orange",
                    )
            else:
                self.update_status(
                    f"Set {len(label_ids)} current label IDs", "green"
                )
        else:
            self.update_status("No labels found in current layer", "orange")

    def _get_current_time_slice(self, data: np.ndarray) -> np.ndarray:
        """Get the current time slice if this is a time-series dataset."""
        if hasattr(self.current_layer, "current_step") and data.ndim >= 3:
            # This is likely a time-series dataset
            current_step = getattr(
                self.current_layer, "current_step", [0] * (data.ndim - 2)
            )
            if (
                isinstance(current_step, (list, tuple))
                and len(current_step) > 0
            ):
                # Get the first dimension's current step (usually time)
                time_idx = (
                    current_step[0] if current_step[0] < data.shape[0] else 0
                )
                return data[time_idx]
        return data

    def _estimate_label_count_sampling(
        self, data: np.ndarray, layer_id: int
    ) -> int:
        """Estimate label count using memory-efficient sampling for large arrays."""
        # For time-series data, only process current time slice
        data = self._get_current_time_slice(data)

        # Use smaller sample size for extremely large arrays
        max_sample_size = 500_000  # Reduced from 1M
        sample_size = min(
            max_sample_size, max(10_000, data.size // 100)
        )  # At least 10k, at most 1% of data

        try:
            # Use memory-efficient block sampling instead of random indices
            sample = self._block_sample_array(data, sample_size)

            # Get unique labels in sample
            unique_sample = np.unique(sample)
            non_zero_sample = unique_sample[unique_sample != 0]
            estimated_count = len(non_zero_sample)

            # Cache the estimated result (mark as estimate)
            self._layer_stats_cache[layer_id] = {
                "count": estimated_count,
                "ids": non_zero_sample.tolist(),
                "is_estimate": True,
                "data_shape": self.current_layer.data.shape,  # Store original shape
            }
            return estimated_count

        except MemoryError:
            # Fallback to even smaller sample
            return self._minimal_sample_estimation(data, layer_id)

    def _estimate_label_ids_sampling(
        self, data: np.ndarray, layer_id: int
    ) -> list:
        """Estimate label IDs using memory-efficient sampling for large arrays."""
        # For time-series data, only process current time slice
        data = self._get_current_time_slice(data)

        # Use smaller sample size for extremely large arrays
        max_sample_size = 500_000  # Reduced from 1M
        sample_size = min(
            max_sample_size, max(10_000, data.size // 100)
        )  # At least 10k, at most 1% of data

        try:
            # Use memory-efficient block sampling instead of random indices
            sample = self._block_sample_array(data, sample_size)

            # Get unique labels in sample
            unique_sample = np.unique(sample)
            non_zero_sample = unique_sample[unique_sample != 0]
            ids = sorted(non_zero_sample.tolist())

            # Cache the estimated result (mark as estimate)
            self._layer_stats_cache[layer_id] = {
                "count": len(ids),
                "ids": ids,
                "is_estimate": True,
                "data_shape": self.current_layer.data.shape,  # Store original shape
            }
            return ids

        except MemoryError:
            # Fallback to even smaller sample
            return self._minimal_sample_estimation(
                data, layer_id, return_ids=True
            )

    def _block_sample_array(
        self, data: np.ndarray, sample_size: int
    ) -> np.ndarray:
        """Memory-efficient block sampling without creating large index arrays."""
        # Calculate step size for uniform sampling
        total_size = data.size
        step = max(1, total_size // sample_size)

        # Use numpy's advanced indexing with calculated steps
        if data.ndim == 1:
            return data[::step][:sample_size]
        elif data.ndim == 2:
            h, w = data.shape
            h_step = max(1, h // int(np.sqrt(sample_size)))
            w_step = max(1, w // int(np.sqrt(sample_size)))
            return data[::h_step, ::w_step].ravel()[:sample_size]
        else:
            # For higher dimensions, flatten and sample with step
            flat_data = data.ravel()
            return flat_data[::step][:sample_size]

    def _minimal_sample_estimation(
        self, data: np.ndarray, layer_id: int, return_ids: bool = False
    ):
        """Fallback method for extremely large arrays that cause memory errors."""
        try:
            # Use a very small sample size
            sample_size = min(
                50_000, data.size // 1000
            )  # 0.1% of data or 50k max
            sample = self._block_sample_array(data, sample_size)

            unique_sample = np.unique(sample)
            non_zero_sample = unique_sample[unique_sample != 0]

            if return_ids:
                ids = sorted(non_zero_sample.tolist())
                self._layer_stats_cache[layer_id] = {
                    "count": len(ids),
                    "ids": ids,
                    "is_estimate": True,
                    "minimal_sample": True,
                    "data_shape": self.current_layer.data.shape,
                }
                return ids
            else:
                count = len(non_zero_sample)
                self._layer_stats_cache[layer_id] = {
                    "count": count,
                    "ids": non_zero_sample.tolist(),
                    "is_estimate": True,
                    "minimal_sample": True,
                    "data_shape": self.current_layer.data.shape,
                }
                return count

        except (MemoryError, ValueError, RuntimeError) as e:
            # Ultimate fallback - return minimal info
            self._layer_stats_cache[layer_id] = {
                "count": 0,
                "ids": [],
                "is_estimate": True,
                "error": str(e),
                "data_shape": self.current_layer.data.shape,
            }
            return [] if return_ids else 0

    def _delayed_update_layer_info(self):
        """Update layer information in a delayed manner to avoid blocking UI."""
        if not self.current_layer:
            self.info_text.setText("No layer selected")
            return

        # Start background computation
        self._compute_layer_info_async()

    def _compute_layer_info_async(self):
        """Compute layer information asynchronously."""

        def compute_in_background():
            try:
                label_count = self.get_current_label_count()
                layer_id = id(self.current_layer)
                cache_info = self._layer_stats_cache.get(layer_id, {})
                is_estimate = cache_info.get("is_estimate", False)
                is_minimal = cache_info.get("minimal_sample", False)
                data_shape = cache_info.get("data_shape", "unknown")

                # Prepare info text
                info_text = f"Current layer: {self.current_layer.name}\n"
                info_text += f"Data shape: {data_shape}\n"

                if is_estimate:
                    if is_minimal:
                        info_text += f"Estimated labels: ~{label_count} (minimal sample - extremely large dataset)\n"
                    else:
                        info_text += f"Estimated labels: ~{label_count} (sampled from current time slice)\n"
                else:
                    info_text += f"Total labels: {label_count}\n"

                # Add performance tip for time-series data
                if (
                    isinstance(data_shape, (tuple, list))
                    and len(data_shape) >= 4
                ):
                    info_text += "Tip: Processing current time slice only for performance\n"

                # Update UI in main thread
                QTimer.singleShot(0, lambda: self.info_text.setText(info_text))

            except (
                MemoryError,
                ValueError,
                RuntimeError,
                AttributeError,
            ) as e:
                error_msg = f"Error computing layer info: {str(e)}"
                QTimer.singleShot(
                    0, lambda: self.update_status(error_msg, "red")
                )

        # Run computation in background thread
        thread = threading.Thread(target=compute_in_background, daemon=True)
        thread.start()
