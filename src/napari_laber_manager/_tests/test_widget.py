import numpy as np
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
)

from napari_laber_manager._widget import (
    LabelManager,
)


def test_label_manager_widget_creation(make_napari_viewer):
    """Test that LabelManager widget is created correctly with all components."""
    # Create viewer and add a label layer
    viewer = make_napari_viewer()
    np.random.seed(42)
    labels = np.random.randint(0, 20, size=(100, 100))
    viewer.add_labels(labels, name="test_labels")

    # Create widget
    widget = LabelManager(viewer)

    # Test widget creation and type
    assert isinstance(widget, LabelManager)
    assert widget.viewer is viewer

    # Test UI components exist and are correct types
    assert isinstance(widget.layer_combo, QComboBox)
    assert isinstance(widget.max_labels_spin, QSpinBox)
    assert isinstance(widget.seed_spin, QSpinBox)
    assert isinstance(widget.generate_btn, QPushButton)
    assert isinstance(widget.label_ids_input, QLineEdit)
    assert isinstance(widget.selected_opacity_slider, QSlider)
    assert isinstance(widget.other_opacity_slider, QSlider)
    assert isinstance(widget.hide_others_checkbox, QCheckBox)
    assert isinstance(widget.apply_btn, QPushButton)

    # Test initial values
    assert widget.max_labels == 100
    assert widget.background_value == 0
    assert widget.max_labels_spin.value() == 100
    assert widget.seed_spin.value() == 50
    assert widget.selected_opacity_slider.value() == 100
    assert widget.other_opacity_slider.value() == 50


def test_layer_selection_update(make_napari_viewer):
    """Test that layer combo updates when layers are added/removed."""
    viewer = make_napari_viewer()
    widget = LabelManager(viewer)

    # Initially no label layers
    assert widget.layer_combo.count() == 0

    # Add a label layer
    np.random.seed(42)
    labels = np.random.randint(0, 20, size=(100, 100))
    viewer.add_labels(labels, name="test_labels")

    # Layer combo should update
    assert widget.layer_combo.count() == 1
    assert widget.layer_combo.itemText(0) == "test_labels"

    # Add another label layer
    labels2 = np.random.randint(0, 15, size=(50, 50))
    viewer.add_labels(labels2, name="test_labels2")

    assert widget.layer_combo.count() == 2


def test_label_ids_parsing(make_napari_viewer):
    """Test parsing of label IDs from string input."""
    viewer = make_napari_viewer()
    widget = LabelManager(viewer)

    # Test single IDs
    ids = widget.parse_label_ids("1,3,5")
    assert ids == [1, 3, 5]

    # Test ranges
    ids = widget.parse_label_ids("1-5")
    assert ids == [1, 2, 3, 4, 5]

    # Test mixed single IDs and ranges
    ids = widget.parse_label_ids("1,3,5-8,10")
    assert ids == [1, 3, 5, 6, 7, 8, 10]

    # Test duplicates are removed
    ids = widget.parse_label_ids("1,2,1-3")
    assert ids == [1, 2, 3]


def test_preset_ids_setting(make_napari_viewer):
    """Test setting preset label IDs."""
    viewer = make_napari_viewer()
    widget = LabelManager(viewer)

    # Test first 10 preset
    widget.set_preset_ids("1-10")
    assert widget.label_ids_input.text() == "1-10"

    # Test even IDs preset
    widget.set_preset_ids("even")
    expected_even = "2,4,6,8,10,12,14,16,18,20"
    assert widget.label_ids_input.text() == expected_even

    # Test odd IDs preset
    widget.set_preset_ids("odd")
    expected_odd = "1,3,5,7,9,11,13,15,17,19"
    assert widget.label_ids_input.text() == expected_odd


def test_hide_others_checkbox_functionality(make_napari_viewer):
    """Test hide others checkbox functionality."""
    viewer = make_napari_viewer()
    widget = LabelManager(viewer)

    # Initially not checked
    assert not widget.hide_others_checkbox.isChecked()
    assert widget.other_opacity_slider.isEnabled()

    # Check the box
    widget.hide_others_checkbox.setChecked(True)
    widget.on_hide_others_toggled(True)

    assert not widget.other_opacity_slider.isEnabled()
    assert widget.other_opacity_label.text() == "0.00"

    # Uncheck the box
    widget.hide_others_checkbox.setChecked(False)
    widget.on_hide_others_toggled(False)

    assert widget.other_opacity_slider.isEnabled()
    assert widget.other_opacity_label.text() == "0.50"  # Default value


def test_colormap_generation(make_napari_viewer):
    """Test colormap generation functionality."""
    viewer = make_napari_viewer()
    widget = LabelManager(viewer)

    # Set parameters
    widget.max_labels_spin.setValue(50)
    widget.seed_spin.setValue(25)

    # Generate colormap
    widget.generate_colormap()

    # Check that colormap was generated
    assert widget.max_labels == 50
    assert len(widget.full_color_dict) > 0
    assert None in widget.full_color_dict  # Background should be present


def test_layer_changed_functionality(make_napari_viewer):
    """Test layer selection change functionality."""
    viewer = make_napari_viewer()
    widget = LabelManager(viewer)

    # Add a label layer
    np.random.seed(42)
    labels = np.random.randint(0, 20, size=(100, 100))
    layer = viewer.add_labels(labels, name="test_labels")

    # Select the layer
    widget.on_layer_changed("test_labels")

    # Check that current layer is set
    assert widget.current_layer is layer

    # Test with non-existent layer
    widget.on_layer_changed("non_existent")
    # Should handle gracefully without crashing
