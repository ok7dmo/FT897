"""
Radio Station Player
A PyQt5-based application for playing internet radio stations using python-vlc
"""

import sys
import vlc
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QListWidget, QLabel,
                             QLineEdit, QMessageBox, QSlider)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon


class RadioPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.is_playing = False
        self.current_station = None

        # Default radio stations
        self.stations = {
            "Český rozhlas Radiožurnál": "https://rozhlas.stream/radiozurnal_mp3_128.mp3",
            "Český rozhlas Dvojka": "https://rozhlas.stream/dvojka_mp3_128.mp3",
            "Český rozhlas Vltava": "https://rozhlas.stream/vltava_mp3_128.mp3",
            "Frekvence 1": "https://stream.bauermedia.cz/frekvence1-128.mp3",
            "Evropa 2": "https://stream.bauermedia.cz/evropa2-128.mp3",
            "BBC World Service": "http://stream.live.vc.bbcmedia.co.uk/bbc_world_service",
            "NPR News": "https://nprdmp-live01-mp3.akacast.akamaistream.net/7/998/364916/v1/npr.akacast.akamaistream.net/nprdmp_live01_mp3",
        }

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Radio Station Player')
        self.setGeometry(100, 100, 600, 500)

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
        main_layout.addWidget(title)

        # Current station label
        self.current_label = QLabel('No station playing')
        self.current_label.setStyleSheet("font-size: 14px; padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        self.current_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.current_label)

        # Volume control
        volume_layout = QHBoxLayout()
        volume_label = QLabel('Volume:')
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(70)
        self.volume_slider.valueChanged.connect(self.change_volume)
        self.volume_value = QLabel('70%')
        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_value)
        main_layout.addLayout(volume_layout)

        # Station list
        list_label = QLabel('Available Stations:')
        list_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        main_layout.addWidget(list_label)

        self.station_list = QListWidget()
        self.station_list.addItems(self.stations.keys())
        self.station_list.itemDoubleClicked.connect(self.play_selected_station)
        main_layout.addWidget(self.station_list)

        # Control buttons
        button_layout = QHBoxLayout()

        self.play_button = QPushButton('Play')
        self.play_button.setStyleSheet("padding: 10px; font-size: 12px;")
        self.play_button.clicked.connect(self.play_pause)
        button_layout.addWidget(self.play_button)

        self.stop_button = QPushButton('Stop')
        self.stop_button.setStyleSheet("padding: 10px; font-size: 12px;")
        self.stop_button.clicked.connect(self.stop)
        button_layout.addWidget(self.stop_button)

        main_layout.addLayout(button_layout)

        # Add custom station section
        custom_layout = QVBoxLayout()
        custom_label = QLabel('Add Custom Station:')
        custom_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        custom_layout.addWidget(custom_label)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel('Name:'))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('Station name')
        name_layout.addWidget(self.name_input)
        custom_layout.addLayout(name_layout)

        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel('URL:'))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText('https://stream.example.com/radio.mp3')
        url_layout.addWidget(self.url_input)
        custom_layout.addLayout(url_layout)

        add_button = QPushButton('Add Station')
        add_button.setStyleSheet("padding: 8px; font-size: 12px;")
        add_button.clicked.connect(self.add_custom_station)
        custom_layout.addWidget(add_button)

        main_layout.addLayout(custom_layout)

        # Set initial volume
        self.player.audio_set_volume(70)

    def play_selected_station(self, item):
        station_name = item.text()
        self.current_station = station_name
        url = self.stations[station_name]
        self.play_stream(url, station_name)

    def play_stream(self, url, name):
        try:
            media = self.instance.media_new(url)
            self.player.set_media(media)
            self.player.play()
            self.is_playing = True
            self.current_label.setText(f'Now playing: {name}')
            self.current_label.setStyleSheet("font-size: 14px; padding: 10px; background-color: #90EE90; border-radius: 5px;")
            self.play_button.setText('Pause')
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to play station: {str(e)}')

    def play_pause(self):
        if not self.current_station:
            selected_items = self.station_list.selectedItems()
            if selected_items:
                self.play_selected_station(selected_items[0])
            else:
                QMessageBox.information(self, 'Info', 'Please select a station first')
            return

        if self.is_playing:
            self.player.pause()
            self.is_playing = False
            self.play_button.setText('Play')
            self.current_label.setStyleSheet("font-size: 14px; padding: 10px; background-color: #FFD700; border-radius: 5px;")
        else:
            self.player.play()
            self.is_playing = True
            self.play_button.setText('Pause')
            self.current_label.setStyleSheet("font-size: 14px; padding: 10px; background-color: #90EE90; border-radius: 5px;")

    def stop(self):
        self.player.stop()
        self.is_playing = False
        self.current_station = None
        self.play_button.setText('Play')
        self.current_label.setText('No station playing')
        self.current_label.setStyleSheet("font-size: 14px; padding: 10px; background-color: #f0f0f0; border-radius: 5px;")

    def change_volume(self, value):
        self.player.audio_set_volume(value)
        self.volume_value.setText(f'{value}%')

    def add_custom_station(self):
        name = self.name_input.text().strip()
        url = self.url_input.text().strip()

        if not name or not url:
            QMessageBox.warning(self, 'Warning', 'Please enter both name and URL')
            return

        if name in self.stations:
            QMessageBox.warning(self, 'Warning', 'Station name already exists')
            return

        self.stations[name] = url
        self.station_list.addItem(name)
        self.name_input.clear()
        self.url_input.clear()
        QMessageBox.information(self, 'Success', f'Station "{name}" added successfully')

    def closeEvent(self, event):
        self.player.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    player = RadioPlayer()
    player.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
