import GObject from 'gi://GObject';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {QuickSlider, SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const BUS_NAME = 'dev.monitorcontrol.MonitorControl';
const OBJECT_PATH = '/dev/monitorcontrol/MonitorControl';
const IFACE = 'dev.monitorcontrol.MonitorControl';

const IFACE_XML = `<node>
  <interface name="${IFACE}">
    <method name="ListDisplays">
      <arg type="s" name="json" direction="out"/>
    </method>
    <method name="SetPercent">
      <arg type="s" name="identity" direction="in"/>
      <arg type="s" name="feature" direction="in"/>
      <arg type="i" name="percent" direction="in"/>
      <arg type="s" name="json" direction="out"/>
    </method>
    <signal name="Changed">
      <arg type="s" name="json"/>
    </signal>
  </interface>
</node>`;

const MonitorProxy = Gio.DBusProxy.makeProxyWrapper(IFACE_XML);

const BrightnessSlider = GObject.registerClass(
class BrightnessSlider extends QuickSlider {
    _init(display, proxy) {
        super._init({iconName: 'display-brightness-symbolic'});
        this._id = display.id;
        this._proxy = proxy;
        this._updating = false;
        const percent = (display.features && display.features.brightness) || 0;
        this.slider.value = percent / 100.0;
        this.accessible_name = display.name;
        this.slider.connect('notify::value', () => {
            if (this._updating)
                return;
            const value = Math.round(this.slider.value * 100);
            this._proxy.SetPercentRemote(this._id, 'brightness', value);
        });
    }

    setPercent(percent) {
        this._updating = true;
        this.slider.value = percent / 100.0;
        this._updating = false;
    }
});

const Indicator = GObject.registerClass(
class Indicator extends SystemIndicator {
    _init() {
        super._init();
        this._sliders = new Map();
        this._proxy = null;
    }

    setProxy(proxy) {
        this._proxy = proxy;
    }

    rebuild(displays) {
        for (const item of this.quickSettingsItems)
            item.destroy();
        this.quickSettingsItems.length = 0;
        this._sliders.clear();
        const rows = (displays || []).filter(d => d.features && d.features.brightness !== undefined);
        for (const display of rows) {
            const slider = new BrightnessSlider(display, this._proxy);
            this.quickSettingsItems.push(slider);
            this._sliders.set(display.id, slider);
        }
    }

    applyChanged(payload) {
        const changes = Array.isArray(payload) ? payload : [payload];
        for (const change of changes) {
            if (change.feature !== 'brightness')
                continue;
            const slider = this._sliders.get(change.id);
            if (slider)
                slider.setPercent(change.percent);
        }
    }
});

export default class MonitorControlExtension extends Extension {
    enable() {
        this._indicator = new Indicator();
        Main.panel.statusArea.quickSettings.addExternalIndicator(this._indicator);
        this._watch = Gio.bus_watch_name(
            Gio.BusType.SESSION,
            BUS_NAME,
            Gio.BusNameWatcherFlags.NONE,
            this._onAppeared.bind(this),
            this._onVanished.bind(this)
        );
    }

    disable() {
        if (this._watch) {
            Gio.bus_unwatch_name(this._watch);
            this._watch = 0;
        }
        this._disconnectProxy();
        if (this._indicator) {
            this._indicator.quickSettingsItems.forEach(i => i.destroy());
            this._indicator.destroy();
            this._indicator = null;
        }
    }

    _onAppeared() {
        this._proxy = new MonitorProxy(Gio.DBus.session, BUS_NAME, OBJECT_PATH,
            (proxy, error) => {
                if (error) {
                    console.error(`MonitorControl proxy: ${error.message}`);
                    return;
                }
                this._indicator.setProxy(proxy);
                this._changedId = proxy.connectSignal('Changed', (_p, _sender, params) => {
                    try {
                        this._indicator.applyChanged(JSON.parse(params[0]));
                    } catch (e) {
                        console.error(e);
                    }
                });
                this._reload();
            });
    }

    _onVanished() {
        this._disconnectProxy();
        if (this._indicator)
            this._indicator.rebuild([]);
    }

    _reload() {
        if (!this._proxy)
            return;
        this._proxy.ListDisplaysRemote((result, error) => {
            if (error) {
                console.error(error.message);
                return;
            }
            try {
                this._indicator.rebuild(JSON.parse(result[0]));
            } catch (e) {
                console.error(e);
            }
        });
    }

    _disconnectProxy() {
        if (this._proxy && this._changedId)
            this._proxy.disconnectSignal(this._changedId);
        this._changedId = 0;
        this._proxy = null;
    }
}
