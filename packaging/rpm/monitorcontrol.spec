# COPR / Fedora: python app using distro GTK 4 + PyGObject (not PyInstaller).
# Build from a GitHub tag: Source0 is the GitHub archive.
Name:           monitorcontrol
Version:        1.0.0
Release:        1%{?dist}
Summary:        Brightness, contrast, and volume for any plugged-in display
License:        MIT
URL:            https://github.com/jaimehisao/monitorcontrol
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-gobject
BuildRequires:  gtk4
BuildRequires:  libadwaita
BuildRequires:  systemd-rpm-macros

Requires:       python3-gobject
Requires:       python3-cairo
Requires:       gtk4
Requires:       libadwaita
Requires:       python3-gobject-base
Requires(pre):  shadow-utils

%description
MonitorControl talks DDC/CI (VESA MCCS) to external monitors and uses
/sys/class/backlight for laptop panels. Brightness keys, an on-screen
HUD, and a GNOME Quick Settings slider.

GTK 4 and libadwaita come from the distribution. This package is not
the PyInstaller one-file binary.

%prep
%autosetup -p1 -n %{name}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files monitorcontrol

install -D -m 644 src/monitorcontrol/data/dev.monitorcontrol.MonitorControl.desktop \
    %{buildroot}%{_datadir}/applications/dev.monitorcontrol.MonitorControl.desktop
install -D -m 644 src/monitorcontrol/data/dev.monitorcontrol.MonitorControl.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/dev.monitorcontrol.MonitorControl.svg
install -D -m 644 packaging/shared/90-monitorcontrol-i2c.rules \
    %{buildroot}%{_udevrulesdir}/90-monitorcontrol-i2c.rules
install -D -m 644 packaging/shared/i2c-dev.conf \
    %{buildroot}%{_prefix}/lib/modules-load.d/i2c-dev.conf
install -d %{buildroot}%{_datadir}/gnome-shell/extensions/monitorcontrol@monitorcontrol.dev
install -m 644 src/monitorcontrol/data/gnome-extension/extension.js \
    src/monitorcontrol/data/gnome-extension/metadata.json \
    %{buildroot}%{_datadir}/gnome-shell/extensions/monitorcontrol@monitorcontrol.dev/

%pre
getent group i2c >/dev/null || groupadd -r i2c

%post
%udev_rules_update

%postun
%udev_rules_update

%check
%pyproject_check_import

%files -f %{pyproject_files}
%license LICENSE
%doc README.md
%{_bindir}/monitorcontrol
%{_datadir}/applications/dev.monitorcontrol.MonitorControl.desktop
%{_datadir}/icons/hicolor/scalable/apps/dev.monitorcontrol.MonitorControl.svg
%{_udevrulesdir}/90-monitorcontrol-i2c.rules
%{_prefix}/lib/modules-load.d/i2c-dev.conf
%{_datadir}/gnome-shell/extensions/monitorcontrol@monitorcontrol.dev/

%changelog
* Thu Sep 11 2026 MonitorControl contributors <jaimehisao@users.noreply.github.com> - 1.0.0-1
- Initial COPR package.
