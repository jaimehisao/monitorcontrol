# MonitorControl for Linux

Control external display brightness, contrast, and volume from the keyboard
and a compact GTK window, the way [MonitorControl](https://github.com/MonitorControl/MonitorControl)
does on macOS.

This is the start of a Linux port. Hardware control talks DDC/CI over I2C;
laptop panels use the sysfs backlight. See the rest of the tree as it lands.
