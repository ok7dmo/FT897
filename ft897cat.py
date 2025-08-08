#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class FT897CAT:
    def __init__(self):
        self.is_connected = True
        self.split_active = False
        self.current_vfo = 'A'
        self.ptt_active = False

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

    def disable_split_operation(self):
        """Ensure split is off."""
        return self.split_off()

    def ptt_on(self):
        self.ptt_active = True
        return True

    def ptt_off(self):
        self.ptt_active = False
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
        self.ptt_button_state = False  # False=off, True=on

    def toggle_ptt(self):
        """Act like a two-state switch for PTT."""
        if self.cat.ptt_active:
            self.handle_ptt_off()
        else:
            self.handle_ptt_on()
        self.ptt_button_state = self.cat.ptt_active

    def tune_memory(self, freq_hz, mode, is_repeater=False):
        """Tune memory channels, disabling split outside repeaters."""
        if not is_repeater:
            self.cat.disable_split_operation()

    def handle_ptt_on(self):
        if self.current_ctcss and self.cat.split_active:
            if self.cat.toggle_vfo():
                self.cat.set_ctcss_tone(self.current_ctcss, self.current_ctcss)
                self.cat.set_ctcss_dcs_mode('ctcss_enc')
                self.cat.toggle_vfo()
        self.cat.ptt_on()

    def handle_ptt_off(self):
        if self.current_ctcss and self.cat.split_active:
            self.cat.set_ctcss_dcs_mode('ctcss_dec')
        self.cat.ptt_off()
