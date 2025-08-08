#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class FT897CAT:
    def __init__(self):
        self.is_connected = True
        self.split_active = False
        self.current_vfo = 'A'

    def set_ctcss_tone(self, tx_hz, rx_hz):
        pass

    def set_ctcss_dcs_mode(self, mode):
        pass

    def toggle_vfo(self):
        self.current_vfo = 'B' if self.current_vfo == 'A' else 'A'
        return True

    def split_off(self):
        self.split_active = False
        return True

    def split_on(self):
        self.split_active = True
        return True

    def setup_split_operation(self, rx_freq_hz, tx_freq_hz, mode=None):
        ctcss_tone = getattr(self, '_temp_ctcss_for_split', None)
        if ctcss_tone and ctcss_tone > 0:
            if not self.toggle_vfo():
                return False
            if not self.set_ctcss_tone(ctcss_tone, ctcss_tone):
                return False
            self.set_ctcss_dcs_mode('off')
            if not self.toggle_vfo():
                return False
        self.split_on()
        return True


class RadioControlApp:
    def __init__(self):
        self.cat = FT897CAT()
        self.current_ctcss = None

    def handle_ptt_on(self):
        if self.current_ctcss and self.cat.split_active:
            if self.cat.toggle_vfo():
                self.cat.set_ctcss_tone(self.current_ctcss, self.current_ctcss)
                self.cat.set_ctcss_dcs_mode('ctcss_enc')
                self.cat.toggle_vfo()

    def handle_ptt_off(self):
        if self.current_ctcss and self.cat.split_active:
            self.cat.set_ctcss_dcs_mode('ctcss_dec')
