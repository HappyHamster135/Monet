import QtQuick

// Distances are measured in pages. A new target brakes the current movement
// before reversing, including when a second scroll arrives mid-slide.
SmoothedAnimation {
    velocity: 560 / Math.max(1, duration)
    maximumEasingTime: Math.round(duration * 0.4)
    reversingMode: SmoothedAnimation.Eased
}
