These instructions describe how to update the Yaesu FT-897 CAT control application without modifying the connect, disconnect, _send, or _read methods. The examples assume a PyQt5 GUI and serial connection already exist.

1. **Clean power menu**
   - Remove band switching from the "Výkon" (Power) menu.
   - Each power option should call only `set_power(desired_value)`.
   - Update the power_label text after sending the command.
   
Example:
```python
# inside the Power menu action slot
value = 100  # or 50, 10 etc.
self.cat.set_power(value)
self.power_label.setText(f"{value} W")
```

2. **Optimize serial communication**
   - Shorten the delay in `_send` to ~20 ms.
   - Read only the needed bytes for meter values.
   - Combine S-meter and TX-meter queries.

Example `_send`:
```python
def _send(self, data: bytes):
    self.serial_port.reset_input_buffer()
    self.serial_port.reset_output_buffer()
    self.serial_port.write(data)
    time.sleep(0.02)
    return True
```

Example `get_smeter`:
```python
def get_smeter(self):
    if not self._send(b'\x00\x00\x00\x00\xe7'):
        return None
    resp = self._read(2)  # opcode echo + value
    return resp[1] if resp and len(resp) >= 2 else None
```

Example `get_meters`:
```python
def get_meters(self):
    cmds = b'\x00\x00\x00\x00\xe7' + b'\x00\x00\x00\x00\xf7'
    self._send(cmds)
    resp = self._read(4)  # two 2-byte replies
    return resp[1], resp[3]
```

3. **Update GUI refresh logic**
   - Replace the old `StatusThread` with a QTimer that calls `update_status` every 300 ms.
   - Inside `update_status`, call `get_meters` and update labels accordingly.
   - Only call `adjust_all_fonts` when the window is resized.

Example timer setup in `__init__`:
```python
self.status_timer = QTimer(self)
self.status_timer.setInterval(300)
self.status_timer.timeout.connect(self.update_status)
self.status_timer.start()
```

4. **Modernize status updates**
   - Use the new meter methods in `update_status`:
```python
raw_s, raw_p = self.cat.get_meters()
if raw_s is not None:
    self.smeter_bar.setValue(raw_s)
if raw_p is not None:
    self.power_bar.setValue(raw_p)
```
