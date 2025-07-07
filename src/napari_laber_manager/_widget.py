"""
Napari Label Manager Plugin
A plugin for batch management of label colors and opacity in napari.
"""

import re

import napari
from napari.utils import colormaps as cmap
from qtpy.QtCore import Qt, Signal
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
        self.viewer.layers.events.removed.connect(self.update_layer_combo)
        self.update_layer_combo()

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
