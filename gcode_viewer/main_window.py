import os
from PySide6.QtWidgets import (
    QMainWindow, QMenuBar, QMenu, QFileDialog,
    QStatusBar, QMessageBox, QSplitter, QWidget, QVBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QToolBar, QPushButton,
    QGroupBox, QGridLayout, QProgressBar, QScrollArea, QHBoxLayout,
    QCheckBox, QSlider, QLineEdit
)
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtCore import Qt, QTimer, QSize, QThread, Signal
from .gl_widget import GLWidget
from .gcode_model import GCodeModel


class GCodeLoader(QThread):
    progress = Signal(int)
    finished = Signal(object, str)
    error = Signal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            self.progress.emit(10)

            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                gcode_content = f.read()

            self.progress.emit(50)

            from .gcode_model import GCodeModel
            model = GCodeModel()
            model.load_from_gcode(gcode_content)

            self.progress.emit(100)
            self.finished.emit(model, self.file_path)

        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('GVis3D')
        self.setGeometry(100, 100, 1400, 900)

        self.gcode_model = None
        self.current_file = None
        self.selected_layers = set()
        self.loader_thread = None

        self._create_menu()
        self._create_toolbar()
        self._create_ui()
        self._create_status_bar()
        self._apply_styles()

        self._load_default_model()

    def _create_menu(self):
        menu_bar = self.menuBar()

        file_menu = QMenu('&File', self)
        open_action = QAction('&Open GCode File...', self)
        open_action.setShortcut(QKeySequence('Ctrl+O'))
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction('E&xit', self)
        exit_action.setShortcut(QKeySequence('Ctrl+Q'))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        menu_bar.addMenu(file_menu)

        view_menu = QMenu('&View', self)
        reset_view_action = QAction('&Reset View', self)
        reset_view_action.setShortcut(QKeySequence('R'))
        reset_view_action.triggered.connect(self._reset_view)
        view_menu.addAction(reset_view_action)

        view_menu.addSeparator()

        top_view_action = QAction('&Top View', self)
        top_view_action.setShortcut(QKeySequence('1'))
        top_view_action.triggered.connect(lambda: self.gl_widget.set_view_preset('top'))
        view_menu.addAction(top_view_action)

        front_view_action = QAction('&Front View', self)
        front_view_action.setShortcut(QKeySequence('2'))
        front_view_action.triggered.connect(lambda: self.gl_widget.set_view_preset('front'))
        view_menu.addAction(front_view_action)

        side_view_action = QAction('&Side View', self)
        side_view_action.setShortcut(QKeySequence('3'))
        side_view_action.triggered.connect(lambda: self.gl_widget.set_view_preset('side'))
        view_menu.addAction(side_view_action)

        isometric_view_action = QAction('&Isometric View', self)
        isometric_view_action.setShortcut(QKeySequence('4'))
        isometric_view_action.triggered.connect(lambda: self.gl_widget.set_view_preset('isometric'))
        view_menu.addAction(isometric_view_action)

        view_menu.addSeparator()

        self.show_axis_action = QAction('&Show Axis', self, checkable=True, checked=True)
        self.show_axis_action.triggered.connect(self._toggle_axis)
        view_menu.addAction(self.show_axis_action)

        self.show_grid_action = QAction('&Show Grid', self, checkable=True, checked=True)
        self.show_grid_action.triggered.connect(self._toggle_grid)
        view_menu.addAction(self.show_grid_action)

        self.show_travel_action = QAction('&Show Travel Lines', self, checkable=True, checked=True)
        self.show_travel_action.triggered.connect(self._toggle_travel)
        view_menu.addAction(self.show_travel_action)

        menu_bar.addMenu(view_menu)

        help_menu = QMenu('&Help', self)
        about_action = QAction('&About', self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        menu_bar.addMenu(help_menu)

    def _create_toolbar(self):
        toolbar = QToolBar('Main Toolbar', self)
        toolbar.setIconSize(QSize(24, 24))

        open_icon = QIcon.fromTheme('document-open')
        open_btn = QPushButton(open_icon, ' Open')
        open_btn.clicked.connect(self._open_file)
        toolbar.addWidget(open_btn)

        toolbar.addSeparator()

        reset_icon = QIcon.fromTheme('view-refresh')
        reset_btn = QPushButton(reset_icon, ' Reset')
        reset_btn.clicked.connect(self._reset_view)
        toolbar.addWidget(reset_btn)

        toolbar.addSeparator()

        top_btn = QPushButton('Top')
        top_btn.setToolTip('Top View (1)')
        top_btn.clicked.connect(lambda: self.gl_widget.set_view_preset('top'))
        toolbar.addWidget(top_btn)

        front_btn = QPushButton('Front')
        front_btn.setToolTip('Front View (2)')
        front_btn.clicked.connect(lambda: self.gl_widget.set_view_preset('front'))
        toolbar.addWidget(front_btn)

        side_btn = QPushButton('Side')
        side_btn.setToolTip('Side View (3)')
        side_btn.clicked.connect(lambda: self.gl_widget.set_view_preset('side'))
        toolbar.addWidget(side_btn)

        iso_btn = QPushButton('ISO')
        iso_btn.setToolTip('Isometric View (4)')
        iso_btn.clicked.connect(lambda: self.gl_widget.set_view_preset('isometric'))
        toolbar.addWidget(iso_btn)

        self.addToolBar(toolbar)

    def _create_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        splitter = QSplitter(Qt.Horizontal)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(splitter)

        self.gl_widget = GLWidget()
        splitter.addWidget(self.gl_widget)
        splitter.setStretchFactor(0, 5)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(10)

        stats_group = QGroupBox('Model Statistics')
        stats_layout = QGridLayout(stats_group)
        stats_layout.setSpacing(6)
        stats_layout.setContentsMargins(12, 12, 12, 12)

        self.stats_labels = {}
        stats_items = [
            ('Layers:', 'layers'),
            ('Segments:', 'segments'),
            ('Extrusion:', 'extrusion_distance'),
            ('Travel:', 'travel_distance'),
            ('Total:', 'total_distance'),
        ]

        for i, (label, key) in enumerate(stats_items):
            stats_layout.addWidget(QLabel(label), i, 0)
            value_label = QLabel('-')
            value_label.setAlignment(Qt.AlignRight)
            value_label.setStyleSheet('font-weight: bold; color: #ffffff;')
            stats_layout.addWidget(value_label, i, 1)
            self.stats_labels[key] = value_label

        scroll_layout.addWidget(stats_group)

        bbox_group = QGroupBox('Bounding Box')
        bbox_layout = QGridLayout(bbox_group)
        bbox_layout.setSpacing(4)
        bbox_layout.setContentsMargins(12, 12, 12, 12)

        bbox_items = [
            ('Min X:', 'bbox_min_x'),
            ('Min Y:', 'bbox_min_y'),
            ('Min Z:', 'bbox_min_z'),
            ('Max X:', 'bbox_max_x'),
            ('Max Y:', 'bbox_max_y'),
            ('Max Z:', 'bbox_max_z'),
        ]

        for i, (label, key) in enumerate(bbox_items):
            bbox_layout.addWidget(QLabel(label), i, 0)
            value_label = QLabel('-')
            value_label.setAlignment(Qt.AlignRight)
            stats_layout.addWidget(value_label, i, 1)
            self.stats_labels[key] = value_label

        scroll_layout.addWidget(bbox_group)

        layer_group = QGroupBox('Layers')
        layer_layout = QVBoxLayout(layer_group)
        layer_layout.setContentsMargins(12, 12, 12, 12)
        layer_layout.setSpacing(8)

        layer_header_layout = QHBoxLayout()
        self.layer_count_label = QLabel('Layers: 0')
        self.layer_count_label.setStyleSheet('font-weight: bold;')
        layer_header_layout.addWidget(self.layer_count_label)
        layer_header_layout.addStretch()
        layer_layout.addLayout(layer_header_layout)

        self.layer_filter = QLineEdit()
        self.layer_filter.setPlaceholderText('Search layers by Z height...')
        self.layer_filter.textChanged.connect(self._filter_layers)
        layer_layout.addWidget(self.layer_filter)

        layer_control_layout = QHBoxLayout()
        layer_control_layout.setSpacing(6)
        self.select_all_btn = QPushButton('Select All')
        self.select_all_btn.clicked.connect(self._select_all_layers)
        self.deselect_all_btn = QPushButton('Deselect All')
        self.deselect_all_btn.clicked.connect(self._deselect_all_layers)
        layer_control_layout.addWidget(self.select_all_btn)
        layer_control_layout.addWidget(self.deselect_all_btn)
        layer_layout.addLayout(layer_control_layout)

        self.layer_list = QListWidget()
        self.layer_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.layer_list.itemClicked.connect(self._toggle_layer_selection)
        self.layer_list.setMaximumHeight(200)
        layer_layout.addWidget(self.layer_list)

        scroll_layout.addWidget(layer_group)

        display_group = QGroupBox('Display')
        display_layout = QVBoxLayout(display_group)
        display_layout.setContentsMargins(12, 12, 12, 12)
        display_layout.setSpacing(8)

        self.axis_checkbox = QCheckBox('Show Axis')
        self.axis_checkbox.setChecked(True)
        self.axis_checkbox.stateChanged.connect(self._toggle_axis)
        display_layout.addWidget(self.axis_checkbox)

        self.grid_checkbox = QCheckBox('Show Grid')
        self.grid_checkbox.setChecked(True)
        self.grid_checkbox.stateChanged.connect(self._toggle_grid)
        display_layout.addWidget(self.grid_checkbox)

        self.travel_checkbox = QCheckBox('Show Travel Lines')
        self.travel_checkbox.setChecked(True)
        self.travel_checkbox.stateChanged.connect(self._toggle_travel)
        display_layout.addWidget(self.travel_checkbox)

        scroll_layout.addWidget(display_group)

        lighting_group = QGroupBox('Lighting')
        lighting_layout = QVBoxLayout(lighting_group)
        lighting_layout.setContentsMargins(12, 12, 12, 12)
        lighting_layout.setSpacing(8)

        self.lighting_checkbox = QCheckBox('Enable Lighting')
        self.lighting_checkbox.setChecked(True)
        self.lighting_checkbox.stateChanged.connect(self._toggle_lighting)
        lighting_layout.addWidget(self.lighting_checkbox)

        ambient_row = QHBoxLayout()
        ambient_label = QLabel('Ambient:')
        ambient_label.setFixedWidth(60)
        ambient_row.addWidget(ambient_label)
        self.ambient_slider = QSlider(Qt.Horizontal)
        self.ambient_slider.setRange(0, 100)
        self.ambient_slider.setValue(30)
        self.ambient_slider.valueChanged.connect(self._update_ambient_intensity)
        ambient_row.addWidget(self.ambient_slider)
        self.ambient_value_label = QLabel('0.30')
        self.ambient_value_label.setFixedWidth(40)
        self.ambient_value_label.setAlignment(Qt.AlignRight)
        ambient_row.addWidget(self.ambient_value_label)
        lighting_layout.addLayout(ambient_row)

        spot_row = QHBoxLayout()
        spot_label = QLabel('Spotlight:')
        spot_label.setFixedWidth(60)
        spot_row.addWidget(spot_label)
        self.spot_slider = QSlider(Qt.Horizontal)
        self.spot_slider.setRange(0, 100)
        self.spot_slider.setValue(80)
        self.spot_slider.valueChanged.connect(self._update_spotlight_intensity)
        spot_row.addWidget(self.spot_slider)
        self.spot_value_label = QLabel('0.80')
        self.spot_value_label.setFixedWidth(40)
        self.spot_value_label.setAlignment(Qt.AlignRight)
        spot_row.addWidget(self.spot_value_label)
        lighting_layout.addLayout(spot_row)

        scroll_layout.addWidget(lighting_group)

        tube_group = QGroupBox('Tube Rendering')
        tube_layout = QVBoxLayout(tube_group)
        tube_layout.setContentsMargins(12, 12, 12, 12)
        tube_layout.setSpacing(8)

        self.tubes_checkbox = QCheckBox('Enable Tube Rendering')
        self.tubes_checkbox.setChecked(True)
        self.tubes_checkbox.stateChanged.connect(self._toggle_tubes)
        tube_layout.addWidget(self.tubes_checkbox)

        radius_row = QHBoxLayout()
        radius_label = QLabel('Radius:')
        radius_label.setFixedWidth(60)
        radius_row.addWidget(radius_label)
        self.radius_slider = QSlider(Qt.Horizontal)
        self.radius_slider.setRange(5, 50)
        self.radius_slider.setValue(15)
        self.radius_slider.valueChanged.connect(self._update_tube_radius)
        radius_row.addWidget(self.radius_slider)
        self.radius_value_label = QLabel('0.15')
        self.radius_value_label.setFixedWidth(40)
        self.radius_value_label.setAlignment(Qt.AlignRight)
        radius_row.addWidget(self.radius_value_label)
        tube_layout.addLayout(radius_row)

        scroll_layout.addWidget(tube_group)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        right_layout.addWidget(scroll_area)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 1)

    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage('Ready')

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _apply_styles(self):
        stylesheet = """
            QMainWindow {
                background-color: #1a1a2e;
            }
            QMenuBar {
                background-color: #16213e;
                color: #eaeaea;
                padding: 6px;
                font-size: 13px;
            }
            QMenuBar::item {
                padding: 6px 16px;
                border-radius: 4px;
                margin: 0 2px;
            }
            QMenuBar::item:selected {
                background-color: #0f3460;
            }
            QMenu {
                background-color: #16213e;
                color: #eaeaea;
                border: 1px solid #0f3460;
                border-radius: 8px;
                padding: 4px;
                font-size: 13px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0f3460;
            }
            QToolBar {
                background-color: #16213e;
                border-bottom: 2px solid #0f3460;
                padding: 6px;
                spacing: 8px;
            }
            QToolBar QPushButton {
                background-color: #0f3460;
                color: #eaeaea;
                border: 1px solid #1a1a2e;
                border-radius: 6px;
                padding: 6px 12px;
                margin: 2px;
                font-size: 13px;
            }
            QToolBar QPushButton:hover {
                background-color: #1a4d80;
                border-color: #4a90d9;
            }
            QToolBar QPushButton:pressed {
                background-color: #2a5d90;
            }
            QGroupBox {
                background-color: #16213e;
                color: #eaeaea;
                border: 1px solid #0f3460;
                border-radius: 10px;
                margin-top: 16px;
                padding-top: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 10px 0 10px;
                color: #4a90d9;
            }
            QLabel {
                color: #b8b8d0;
                font-size: 12px;
            }
            QListWidget {
                background-color: #0f3460;
                color: #eaeaea;
                border: 1px solid #1a4d80;
                border-radius: 6px;
                selection-background-color: #1a4d80;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #16213e;
            }
            QListWidget::item:hover {
                background-color: #16213e;
            }
            QListWidget::item:selected {
                background-color: #1a4d80;
            }
            QCheckBox {
                color: #b8b8d0;
                font-size: 12px;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #4a90d9;
                border-radius: 4px;
                background-color: #0f3460;
            }
            QCheckBox::indicator:checked {
                background-color: #4a90d9;
                border-color: #4a90d9;
            }
            QCheckBox::indicator:checked::after {
                image: url(:/qt-project.org/styles/commonstyle/images/check.png);
            }
            QLineEdit {
                background-color: #0f3460;
                color: #eaeaea;
                border: 1px solid #1a4d80;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #4a90d9;
                outline: none;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #0f3460;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 18px;
                height: 18px;
                background: #4a90d9;
                border-radius: 9px;
                margin: -6px 0;
            }
            QSlider::handle:horizontal:hover {
                background: #5a9fe9;
            }
            QScrollArea {
                border: none;
            }
            QScrollBar:vertical {
                width: 8px;
                background: #16213e;
            }
            QScrollBar::handle:vertical {
                background: #4a90d9;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #5a9fe9;
            }
            QProgressBar {
                background-color: #0f3460;
                border: 1px solid #1a4d80;
                border-radius: 6px;
                height: 16px;
                text-align: center;
                color: #eaeaea;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #4a90d9;
                border-radius: 4px;
            }
            QStatusBar {
                background-color: #16213e;
                color: #b8b8d0;
                font-size: 12px;
            }
            QSplitter::handle {
                background-color: #0f3460;
                width: 6px;
                border-radius: 3px;
                margin: 4px;
            }
            QSplitter::handle:hover {
                background-color: #4a90d9;
            }
            QPushButton {
                background-color: #0f3460;
                color: #eaeaea;
                border: 1px solid #1a4d80;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1a4d80;
                border-color: #4a90d9;
            }
            QPushButton:pressed {
                background-color: #2a5d90;
            }
        """
        self.setStyleSheet(stylesheet)

    def _open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            'Open GCode File',
            '',
            'GCode Files (*.gcode *.gco *.gc);;All Files (*)'
        )

        if file_path:
            self._load_gcode_file(file_path)

    def _load_gcode_file(self, file_path):
        if self.loader_thread:
            if self.loader_thread.isRunning():
                self.loader_thread.quit()
                self.loader_thread.wait()
            self.loader_thread.progress.disconnect()
            self.loader_thread.finished.disconnect()
            self.loader_thread.error.disconnect()

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage('Loading GCode file...')

        self.loader_thread = GCodeLoader(file_path)
        self.loader_thread.progress.connect(self._on_load_progress)
        self.loader_thread.finished.connect(self._on_load_finished)
        self.loader_thread.error.connect(self._on_load_error)
        self.loader_thread.start()

    def _on_load_progress(self, value):
        self.progress_bar.setValue(value)

    def _on_load_finished(self, model, file_path):
        self.gcode_model = model
        self.current_file = file_path
        self.setWindowTitle(f'GVis3D - {os.path.basename(file_path)}')
        self._update_layer_list()
        self._update_stats()
        self._update_status_bar()

        self.gl_widget.set_model(self.gcode_model)
        self.progress_bar.setValue(100)
        self.status_bar.showMessage(f'Loaded: {os.path.basename(file_path)}')

        QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

    def _on_load_error(self, error_msg):
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, 'Error', f'Failed to load GCode file:\n{error_msg}')

    def _load_default_model(self):
        default_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'examples', 'octocat.gcode'
        )
        if os.path.exists(default_path):
            self._load_gcode_file(default_path)

    def _update_layer_list(self):
        self.layer_list.clear()
        self.selected_layers.clear()

        if self.gcode_model:
            layer_count = self.gcode_model.get_layer_count()
            self.layer_count_label.setText(f'Layers: {layer_count}')

            for i, layer in enumerate(self.gcode_model.layers):
                item = QListWidgetItem(f'Layer {i} (Z: {layer.z:.2f})')
                item.setData(Qt.UserRole, i)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                self.selected_layers.add(i)
                self.layer_list.addItem(item)

        self._filter_layers(self.layer_filter.text())

    def _filter_layers(self, text):
        text = text.lower().strip()
        for i in range(self.layer_list.count()):
            item = self.layer_list.item(i)
            item.setHidden(bool(text) and text not in item.text().lower())

    def _toggle_layer_selection(self, item):
        layer_index = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked:
            self.selected_layers.add(layer_index)
        else:
            self.selected_layers.discard(layer_index)
        self.gl_widget.set_visible_layers(self.selected_layers)

    def _select_all_layers(self):
        for i in range(self.layer_list.count()):
            item = self.layer_list.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Checked)
                self.selected_layers.add(item.data(Qt.UserRole))
        self.gl_widget.set_visible_layers(self.selected_layers)

    def _deselect_all_layers(self):
        for i in range(self.layer_list.count()):
            item = self.layer_list.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Unchecked)
                self.selected_layers.discard(item.data(Qt.UserRole))
        self.gl_widget.set_visible_layers(self.selected_layers)

    def _update_stats(self):
        if not self.gcode_model:
            return

        stats = self.gcode_model.get_model_stats()

        self.stats_labels['layers'].setText(str(stats['layers']))
        self.stats_labels['segments'].setText(str(stats['segments']))
        self.stats_labels['extrusion_distance'].setText(f'{stats["extrusion_distance"]} mm')
        self.stats_labels['travel_distance'].setText(f'{stats["travel_distance"]} mm')
        self.stats_labels['total_distance'].setText(f'{stats["total_distance"]} mm')

        self.stats_labels['bbox_min_x'].setText(f'{stats["bbox_min"]["x"]}')
        self.stats_labels['bbox_min_y'].setText(f'{stats["bbox_min"]["y"]}')
        self.stats_labels['bbox_min_z'].setText(f'{stats["bbox_min"]["z"]}')
        self.stats_labels['bbox_max_x'].setText(f'{stats["bbox_max"]["x"]}')
        self.stats_labels['bbox_max_y'].setText(f'{stats["bbox_max"]["y"]}')
        self.stats_labels['bbox_max_z'].setText(f'{stats["bbox_max"]["z"]}')

    def _update_status_bar(self):
        if self.gcode_model:
            layer_count = self.gcode_model.get_layer_count()
            segment_count = len(self.gcode_model.get_all_segments())
            self.status_bar.showMessage(
                f'Layers: {layer_count} | Segments: {segment_count} | '
                f'Extrusion: {self.gcode_model.total_extrusion:.1f}mm | '
                f'Travel: {self.gcode_model.total_travel:.1f}mm'
            )

    def _reset_view(self):
        self.gl_widget.reset_view()

    def _toggle_axis(self, state):
        show = bool(state)
        self.gl_widget.show_axis = show
        self.show_axis_action.blockSignals(True)
        self.show_axis_action.setChecked(show)
        self.show_axis_action.blockSignals(False)
        self.axis_checkbox.blockSignals(True)
        self.axis_checkbox.setChecked(show)
        self.axis_checkbox.blockSignals(False)
        self.gl_widget.update()

    def _toggle_grid(self, state):
        show = bool(state)
        self.gl_widget.show_grid = show
        self.show_grid_action.blockSignals(True)
        self.show_grid_action.setChecked(show)
        self.show_grid_action.blockSignals(False)
        self.grid_checkbox.blockSignals(True)
        self.grid_checkbox.setChecked(show)
        self.grid_checkbox.blockSignals(False)
        self.gl_widget.update()

    def _toggle_travel(self, state):
        show = bool(state)
        self.gl_widget.show_travel = show
        self.show_travel_action.blockSignals(True)
        self.show_travel_action.setChecked(show)
        self.show_travel_action.blockSignals(False)
        self.travel_checkbox.blockSignals(True)
        self.travel_checkbox.setChecked(show)
        self.travel_checkbox.blockSignals(False)
        self.gl_widget.update()

    def _toggle_lighting(self, state):
        self.gl_widget.use_lighting = bool(state)
        self.lighting_checkbox.blockSignals(True)
        self.lighting_checkbox.setChecked(bool(state))
        self.lighting_checkbox.blockSignals(False)
        self.gl_widget.update_lighting()

    def _toggle_tubes(self, state):
        self.gl_widget.use_tubes = bool(state)
        self.tubes_checkbox.blockSignals(True)
        self.tubes_checkbox.setChecked(bool(state))
        self.tubes_checkbox.blockSignals(False)
        self.gl_widget.update()

    def _update_ambient_intensity(self, value):
        self.gl_widget.ambient_intensity = value / 100.0
        self.ambient_value_label.setText(f'{value / 100.0:.2f}')
        self.gl_widget.update_lighting()

    def _update_spotlight_intensity(self, value):
        self.gl_widget.spotlight_intensity = value / 100.0
        self.spot_value_label.setText(f'{value / 100.0:.2f}')
        self.gl_widget.update_lighting()

    def _update_tube_radius(self, value):
        self.gl_widget.tube_radius = value / 100.0
        self.radius_value_label.setText(f'{value / 100.0:.2f}')
        self.gl_widget.update()

    def _show_about(self):
        QMessageBox.about(
            self,
            'About GVis3D',
            'GVis3D\n\n'
            'A desktop 3D viewer for GCode files.\n\n'
            'Built using PySide6 and PyOpenGL.\n\n'
            'Controls:\n'
            '- Drag to rotate\n'
            '- Scroll to zoom\n'
            '- Right-click to pan\n'
            '- R to reset view\n'
            '- 1/2/3/4 for preset views\n\n'
            'Keyboard Shortcuts:\n'
            '- Ctrl+O: Open file\n'
            '- Ctrl+Q: Exit\n'
            '- R: Reset view\n'
            '- 1: Top view\n'
            '- 2: Front view\n'
            '- 3: Side view\n'
            '- 4: Isometric view'
        )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_R:
            self._reset_view()
        elif event.key() == Qt.Key_1:
            self.gl_widget.set_view_preset('top')
        elif event.key() == Qt.Key_2:
            self.gl_widget.set_view_preset('front')
        elif event.key() == Qt.Key_3:
            self.gl_widget.set_view_preset('side')
        elif event.key() == Qt.Key_4:
            self.gl_widget.set_view_preset('isometric')
        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(('.gcode', '.gco', '.gc')):
                self._load_gcode_file(file_path)
                break