"""
Radio Station Player
A PyQt5-based application for playing internet radio stations using python-vlc
with Radio Browser API integration and full accessibility support
"""

import sys
import vlc
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QListWidget, QLabel,
                             QLineEdit, QMessageBox, QSlider, QComboBox,
                             QTabWidget, QProgressBar, QTextEdit, QShortcut)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QKeySequence
from radio_api import RadioBrowserAPI


class StationLoaderThread(QThread):
    """Background thread for loading stations from API"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, api, search_type, search_value):
        super().__init__()
        self.api = api
        self.search_type = search_type
        self.search_value = search_value

    def run(self):
        try:
            if self.search_type == 'country':
                stations = self.api.get_stations_by_country(self.search_value, limit=100)
            elif self.search_type == 'language':
                stations = self.api.get_stations_by_language(self.search_value, limit=100)
            elif self.search_type == 'search':
                stations = self.api.search_stations(name=self.search_value, limit=100)
            elif self.search_type == 'top':
                stations = self.api.get_top_stations(limit=100)
            else:
                stations = []
            self.finished.emit(stations)
        except Exception as e:
            self.error.emit(str(e))


class RadioPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.is_playing = False
        self.current_station = None
        self.current_station_data = None
        self.api = RadioBrowserAPI()
        self.api_stations = []

        # Default radio stations (fallback)
        self.local_stations = {
            "Český rozhlas Radiožurnál": "https://rozhlas.stream/radiozurnal_mp3_128.mp3",
            "Český rozhlas Dvojka": "https://rozhlas.stream/dvojka_mp3_128.mp3",
            "Český rozhlas Vltava": "https://rozhlas.stream/vltava_mp3_128.mp3",
            "Frekvence 1": "https://stream.bauermedia.cz/frekvence1-128.mp3",
            "Evropa 2": "https://stream.bauermedia.cz/evropa2-128.mp3",
        }

        self.init_ui()
        self.setup_accessibility()
        self.setup_shortcuts()

    def init_ui(self):
        self.setWindowTitle('Radio Station Player - Accessible')
        self.setGeometry(100, 100, 800, 700)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Title
        title = QLabel('Radio Station Player')
        title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 10px;")
        title.setAlignment(Qt.AlignCenter)
        title.setAccessibleName("Radio Station Player - Main Title")
        title.setAccessibleDescription("Main application title")
        main_layout.addWidget(title)

        # Current station label
        self.current_label = QLabel('No station playing')
        self.current_label.setStyleSheet("font-size: 14px; padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        self.current_label.setAlignment(Qt.AlignCenter)
        self.current_label.setAccessibleName("Current playback status")
        self.current_label.setAccessibleDescription("Shows which station is currently playing")
        main_layout.addWidget(self.current_label)

        # Volume control
        volume_layout = QHBoxLayout()
        volume_label = QLabel('Volume:')
        volume_label.setAccessibleName("Volume label")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(70)
        self.volume_slider.valueChanged.connect(self.change_volume)
        self.volume_slider.setAccessibleName("Volume slider")
        self.volume_slider.setAccessibleDescription("Adjust volume from 0 to 100 percent. Use arrow keys to change.")
        self.volume_slider.setToolTip("Volume control - use left/right arrow keys")
        self.volume_value = QLabel('70%')
        self.volume_value.setAccessibleName("Volume percentage")
        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_value)
        main_layout.addLayout(volume_layout)

        # Control buttons
        button_layout = QHBoxLayout()

        self.play_button = QPushButton('Play')
        self.play_button.setStyleSheet("padding: 10px; font-size: 12px;")
        self.play_button.clicked.connect(self.play_pause)
        self.play_button.setAccessibleName("Play button")
        self.play_button.setAccessibleDescription("Press to play or pause the selected station. Shortcut: Space")
        self.play_button.setToolTip("Play/Pause (Space)")
        button_layout.addWidget(self.play_button)

        self.stop_button = QPushButton('Stop')
        self.stop_button.setStyleSheet("padding: 10px; font-size: 12px;")
        self.stop_button.clicked.connect(self.stop)
        self.stop_button.setAccessibleName("Stop button")
        self.stop_button.setAccessibleDescription("Press to stop playback. Shortcut: Escape")
        self.stop_button.setToolTip("Stop playback (Escape)")
        button_layout.addWidget(self.stop_button)

        main_layout.addLayout(button_layout)

        # Tab widget for different station sources
        self.tab_widget = QTabWidget()
        self.tab_widget.setAccessibleName("Station source tabs")
        self.tab_widget.setAccessibleDescription("Switch between online database and local stations")
        main_layout.addWidget(self.tab_widget)

        # Tab 1: Online stations from Radio Browser
        online_tab = QWidget()
        online_layout = QVBoxLayout()
        online_tab.setLayout(online_layout)

        # Search controls
        search_label = QLabel('Search Online Stations (Radio Browser API):')
        search_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        search_label.setAccessibleName("Online stations search section")
        online_layout.addWidget(search_label)

        search_type_layout = QHBoxLayout()
        search_type_label = QLabel('Search by:')
        self.search_type_combo = QComboBox()
        self.search_type_combo.addItems(['Name', 'Country Code', 'Language', 'Top Voted'])
        self.search_type_combo.setAccessibleName("Search type selector")
        self.search_type_combo.setAccessibleDescription("Select how to search for stations")
        self.search_type_combo.setToolTip("Choose search method")
        search_type_layout.addWidget(search_type_label)
        search_type_layout.addWidget(self.search_type_combo)
        online_layout.addLayout(search_type_layout)

        search_input_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('e.g., "BBC", "CZ" for Czech, "czech" for language')
        self.search_input.returnPressed.connect(self.search_online_stations)
        self.search_input.setAccessibleName("Search input field")
        self.search_input.setAccessibleDescription("Enter search term and press Enter to search")
        self.search_input.setToolTip("Enter search term and press Enter")
        search_input_layout.addWidget(self.search_input)

        self.search_button = QPushButton('Search')
        self.search_button.clicked.connect(self.search_online_stations)
        self.search_button.setAccessibleName("Search button")
        self.search_button.setAccessibleDescription("Click to search for stations")
        self.search_button.setToolTip("Search online stations (or press Enter)")
        search_input_layout.addWidget(self.search_button)
        online_layout.addLayout(search_input_layout)

        # Progress bar for loading
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setAccessibleName("Loading progress")
        online_layout.addWidget(self.progress_bar)

        # Online stations list
        online_stations_label = QLabel('Online Stations:')
        online_stations_label.setAccessibleName("Online stations list label")
        online_layout.addWidget(online_stations_label)

        self.online_station_list = QListWidget()
        self.online_station_list.itemDoubleClicked.connect(self.play_online_station)
        self.online_station_list.setAccessibleName("Online stations list")
        self.online_station_list.setAccessibleDescription("List of stations from online database. Double-click or press Enter to play")
        self.online_station_list.setToolTip("Double-click or press Enter to play station")
        online_layout.addWidget(self.online_station_list)

        # Station info button
        self.info_button = QPushButton('Show Station Info')
        self.info_button.clicked.connect(self.show_station_info)
        self.info_button.setAccessibleName("Station information button")
        self.info_button.setAccessibleDescription("Show detailed information about selected station")
        self.info_button.setToolTip("Show detailed station information (I)")
        online_layout.addWidget(self.info_button)

        self.tab_widget.addTab(online_tab, "Online Stations")

        # Tab 2: Local/Custom stations
        local_tab = QWidget()
        local_layout = QVBoxLayout()
        local_tab.setLayout(local_layout)

        # Local station list
        list_label = QLabel('Local & Custom Stations:')
        list_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        list_label.setAccessibleName("Local stations section")
        local_layout.addWidget(list_label)

        self.local_station_list = QListWidget()
        self.local_station_list.addItems(self.local_stations.keys())
        self.local_station_list.itemDoubleClicked.connect(self.play_local_station)
        self.local_station_list.setAccessibleName("Local stations list")
        self.local_station_list.setAccessibleDescription("List of local and custom stations. Double-click or press Enter to play")
        self.local_station_list.setToolTip("Double-click or press Enter to play station")
        local_layout.addWidget(self.local_station_list)

        # Add custom station section
        custom_label = QLabel('Add Custom Station:')
        custom_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        custom_label.setAccessibleName("Add custom station section")
        local_layout.addWidget(custom_label)

        name_layout = QHBoxLayout()
        name_label = QLabel('Name:')
        name_layout.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('Station name')
        self.name_input.setAccessibleName("Station name input")
        self.name_input.setAccessibleDescription("Enter the name for your custom station")
        self.name_input.setToolTip("Enter station name")
        name_layout.addWidget(self.name_input)
        local_layout.addLayout(name_layout)

        url_layout = QHBoxLayout()
        url_label = QLabel('URL:')
        url_layout.addWidget(url_label)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText('https://stream.example.com/radio.mp3')
        self.url_input.setAccessibleName("Station URL input")
        self.url_input.setAccessibleDescription("Enter the streaming URL for your custom station")
        self.url_input.setToolTip("Enter stream URL")
        url_layout.addWidget(self.url_input)
        local_layout.addLayout(url_layout)

        add_button = QPushButton('Add Station')
        add_button.setStyleSheet("padding: 8px; font-size: 12px;")
        add_button.clicked.connect(self.add_custom_station)
        add_button.setAccessibleName("Add custom station button")
        add_button.setAccessibleDescription("Click to add the custom station to your list")
        add_button.setToolTip("Add custom station to list")
        local_layout.addWidget(add_button)

        self.tab_widget.addTab(local_tab, "Local Stations")

        # Help text
        help_text = QLabel('Keyboard shortcuts: Space=Play/Pause, Escape=Stop, I=Info, F1=Help')
        help_text.setStyleSheet("font-size: 10px; color: #666; padding: 5px;")
        help_text.setAccessibleName("Keyboard shortcuts help")
        main_layout.addWidget(help_text)

        # Set initial volume
        self.player.audio_set_volume(70)

        # Load top stations on startup
        QTimer.singleShot(1000, self.load_top_stations)

    def setup_accessibility(self):
        """Configure additional accessibility features"""
        # Set window accessible name and description
        self.setAccessibleName("Radio Station Player Application")
        self.setAccessibleDescription("Application for playing internet radio stations with full keyboard support")

    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Play/Pause with Space
        QShortcut(QKeySequence(Qt.Key_Space), self, self.play_pause)

        # Stop with Escape
        QShortcut(QKeySequence(Qt.Key_Escape), self, self.stop)

        # Volume up/down
        QShortcut(QKeySequence(Qt.Key_Plus), self, lambda: self.volume_slider.setValue(
            min(100, self.volume_slider.value() + 5)))
        QShortcut(QKeySequence(Qt.Key_Minus), self, lambda: self.volume_slider.setValue(
            max(0, self.volume_slider.value() - 5)))

        # Station info
        QShortcut(QKeySequence(Qt.Key_I), self, self.show_station_info)

        # Help
        QShortcut(QKeySequence(Qt.Key_F1), self, self.show_help)

        # Enter key on lists
        QShortcut(QKeySequence(Qt.Key_Return), self.online_station_list,
                 lambda: self.play_online_station(self.online_station_list.currentItem())
                 if self.online_station_list.currentItem() else None)
        QShortcut(QKeySequence(Qt.Key_Return), self.local_station_list,
                 lambda: self.play_local_station(self.local_station_list.currentItem())
                 if self.local_station_list.currentItem() else None)

    def load_top_stations(self):
        """Load top voted stations on startup"""
        self.search_type_combo.setCurrentText('Top Voted')
        self.search_online_stations()

    def search_online_stations(self):
        """Search for stations using Radio Browser API"""
        search_type = self.search_type_combo.currentText()
        search_value = self.search_input.text().strip()

        if search_type != 'Top Voted' and not search_value:
            self.announce_status("Please enter a search term")
            return

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.search_button.setEnabled(False)
        self.announce_status("Searching for stations, please wait")

        # Determine search type
        if search_type == 'Name':
            thread_type = 'search'
        elif search_type == 'Country Code':
            thread_type = 'country'
            search_value = search_value.upper()
        elif search_type == 'Language':
            thread_type = 'language'
        else:  # Top Voted
            thread_type = 'top'
            search_value = ''

        # Load stations in background thread
        self.loader_thread = StationLoaderThread(self.api, thread_type, search_value)
        self.loader_thread.finished.connect(self.on_stations_loaded)
        self.loader_thread.error.connect(self.on_load_error)
        self.loader_thread.start()

    def on_stations_loaded(self, stations):
        """Handle loaded stations"""
        self.progress_bar.setVisible(False)
        self.search_button.setEnabled(True)

        self.api_stations = stations
        self.online_station_list.clear()

        if not stations:
            self.announce_status("No stations found")
            return

        for station in stations:
            display_name = self.api.format_station_for_display(station)
            self.online_station_list.addItem(display_name)

        self.announce_status(f"Found {len(stations)} stations")

    def on_load_error(self, error_msg):
        """Handle loading error"""
        self.progress_bar.setVisible(False)
        self.search_button.setEnabled(True)
        self.announce_status(f"Error loading stations: {error_msg}")
        QMessageBox.warning(self, 'Error', f'Failed to load stations: {error_msg}')

    def play_online_station(self, item):
        """Play selected online station"""
        if not item:
            return

        index = self.online_station_list.row(item)
        if 0 <= index < len(self.api_stations):
            station = self.api_stations[index]
            self.current_station_data = station
            url = self.api.get_station_url(station)
            name = station.get('name', 'Unknown')
            self.current_station = name

            # Register click with API
            station_uuid = station.get('stationuuid', '')
            if station_uuid:
                self.api.click_station(station_uuid)

            self.play_stream(url, name)

    def play_local_station(self, item):
        """Play selected local station"""
        if not item:
            return

        station_name = item.text()
        self.current_station = station_name
        self.current_station_data = None
        url = self.local_stations[station_name]
        self.play_stream(url, station_name)

    def play_stream(self, url, name):
        """Play a radio stream"""
        try:
            media = self.instance.media_new(url)
            self.player.set_media(media)
            self.player.play()
            self.is_playing = True
            status_text = f'Now playing: {name}'
            self.current_label.setText(status_text)
            self.current_label.setStyleSheet("font-size: 14px; padding: 10px; background-color: #90EE90; border-radius: 5px;")
            self.play_button.setText('Pause')
            self.announce_status(status_text)
        except Exception as e:
            error_msg = f'Failed to play station: {str(e)}'
            self.announce_status(error_msg)
            QMessageBox.warning(self, 'Error', error_msg)

    def play_pause(self):
        """Toggle play/pause"""
        if not self.current_station:
            # Try to play selected station from current tab
            if self.tab_widget.currentIndex() == 0:  # Online tab
                selected_items = self.online_station_list.selectedItems()
                if selected_items:
                    self.play_online_station(selected_items[0])
                else:
                    self.announce_status("Please select a station first")
            else:  # Local tab
                selected_items = self.local_station_list.selectedItems()
                if selected_items:
                    self.play_local_station(selected_items[0])
                else:
                    self.announce_status("Please select a station first")
            return

        if self.is_playing:
            self.player.pause()
            self.is_playing = False
            self.play_button.setText('Play')
            self.current_label.setStyleSheet("font-size: 14px; padding: 10px; background-color: #FFD700; border-radius: 5px;")
            self.announce_status("Playback paused")
        else:
            self.player.play()
            self.is_playing = True
            self.play_button.setText('Pause')
            self.current_label.setStyleSheet("font-size: 14px; padding: 10px; background-color: #90EE90; border-radius: 5px;")
            self.announce_status("Playback resumed")

    def stop(self):
        """Stop playback"""
        self.player.stop()
        self.is_playing = False
        self.current_station = None
        self.current_station_data = None
        self.play_button.setText('Play')
        self.current_label.setText('No station playing')
        self.current_label.setStyleSheet("font-size: 14px; padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        self.announce_status("Playback stopped")

    def change_volume(self, value):
        """Change volume"""
        self.player.audio_set_volume(value)
        self.volume_value.setText(f'{value}%')
        # Don't announce every volume change, too verbose for screen readers

    def add_custom_station(self):
        """Add a custom station"""
        name = self.name_input.text().strip()
        url = self.url_input.text().strip()

        if not name or not url:
            self.announce_status("Please enter both name and URL")
            QMessageBox.warning(self, 'Warning', 'Please enter both name and URL')
            return

        if name in self.local_stations:
            self.announce_status("Station name already exists")
            QMessageBox.warning(self, 'Warning', 'Station name already exists')
            return

        self.local_stations[name] = url
        self.local_station_list.addItem(name)
        self.name_input.clear()
        self.url_input.clear()
        self.announce_status(f'Station {name} added successfully')
        QMessageBox.information(self, 'Success', f'Station "{name}" added successfully')

    def show_station_info(self):
        """Show detailed information about selected station"""
        if self.tab_widget.currentIndex() == 0 and self.current_station_data:
            # Online station
            info = self.api.get_station_info(self.current_station_data)
            QMessageBox.information(self, 'Station Information', info)
        elif self.current_station:
            # Local station
            url = self.local_stations.get(self.current_station, 'Unknown')
            info = f"Name: {self.current_station}\nURL: {url}"
            QMessageBox.information(self, 'Station Information', info)
        else:
            self.announce_status("No station selected")
            QMessageBox.information(self, 'Information', 'No station selected')

    def show_help(self):
        """Show help dialog"""
        help_text = """
Radio Station Player - Keyboard Shortcuts

Playback:
  Space       - Play/Pause
  Escape      - Stop
  Enter       - Play selected station

Volume:
  +           - Increase volume
  -           - Decrease volume
  Arrow Keys  - Adjust volume slider

Navigation:
  Tab         - Move to next control
  Shift+Tab   - Move to previous control
  Arrow Keys  - Navigate lists

Information:
  I           - Show station info
  F1          - Show this help

The application is fully accessible with screen readers.
        """
        QMessageBox.information(self, 'Keyboard Shortcuts', help_text.strip())

    def announce_status(self, message):
        """Announce status for screen readers by updating accessible description"""
        self.current_label.setAccessibleDescription(message)
        # Also update the label text if it's an error or info message
        # This helps both sighted users and screen reader users

    def closeEvent(self, event):
        """Clean up on close"""
        self.player.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)

    # Enable accessibility
    app.setApplicationName("Radio Station Player")
    app.setOrganizationName("Radio Player")

    player = RadioPlayer()
    player.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
