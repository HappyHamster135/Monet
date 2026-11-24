# Monet desktop media shortcuts

Monet builds Plasma’s media controller from the Fedora source corresponding to the desktop image. The controller registers KDE’s original shortcut actions and uses its filtered MPRIS model. Preferences in Settings → Sound → Media keys apply only to those actions. The normal Plasma selection handles unconfigured desktops. A fallback player starts only when the user selects it and presses Play with no eligible player. Its installed desktop entry handles launch and activation.

The module checks playback capabilities before issuing commands, and waits up to ten seconds for a newly launched player to register. It uses the Flatpak application ID where available. For players without a desktop ID, exclusions use the player identity.

The image verifies the library, original module, linked packages, binary and source archive before installation. To rebuild the module, extract the archive and configure CMake with the extracted directory as `UPSTREAM_SOURCE` and `monet-session/mediakeys` as the source directory. Use the development packages and build options from the session image stage.
