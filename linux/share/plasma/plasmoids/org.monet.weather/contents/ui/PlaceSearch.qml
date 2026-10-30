import QtQuick

QtObject {
    id: search
    property var results: []
    property bool busy: false
    property string problem: ""
    property var request: null
    property int generation: 0
    property string endpoint: "https://geocoding-api.open-meteo.com/v1/search"
    property int timeout: 10000
    property string language: Qt.locale().name.split("_")[0].toLowerCase()
    function cancel() {
        ++generation
        deadline.stop()
        const old = request
        request = null
        if (old) old.abort()
        busy = false
        results = []
        problem = ""
    }
    function find(name) {
        cancel()
        name = name.trim()
        if (name.length < 2) return
        const mine = generation
        const xhr = new XMLHttpRequest()
        request = xhr // Retain the request while the widget's scene is collected.
        busy = true
        xhr.onreadystatechange = () => {
            if (mine !== generation || xhr.readyState !== XMLHttpRequest.DONE) return
            deadline.stop()
            busy = false
            request = null
            try {
                if (xhr.status !== 200) throw new Error("request failed")
                const data = JSON.parse(xhr.responseText)
                if (data.error || (data.results !== undefined && !Array.isArray(data.results))) throw new Error("invalid response")
                results = (data.results || []).filter(p => typeof p.name === "string"
                    && typeof p.latitude === "number" && typeof p.longitude === "number"
                    && isFinite(p.latitude) && isFinite(p.longitude)
                    && Math.abs(p.latitude) <= 90 && Math.abs(p.longitude) <= 180).slice(0, 8)
            } catch (e) {
                results = []
                problem = i18nd("monet", "Could not search for places. Check your connection and try again.")
            }
        }
        xhr.open("GET", endpoint + "?count=8&format=json&name=" + encodeURIComponent(name)
            + "&language=" + (/^[a-z]{2}$/.test(language) ? language : "en"))
        deadline.start()
        xhr.send()
    }
    property Timer deadline: Timer {
        interval: search.timeout
        onTriggered: {
            search.cancel()
            search.problem = i18nd("monet", "Place search timed out. Try again.")
        }
    }
    Component.onDestruction: cancel()
}
