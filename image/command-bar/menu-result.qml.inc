    // D-Bus runners dispatch asynchronously. Keep keyboard focus until the app has
    // processed its menu command, including when Return was pressed before results arrived.
    property var menuRequest: null
    onVisibleChanged: if (!visible) menuRequest = null

    function runResult(row, queued) {
        const index = resultModel.index(row, 0)
        const id = String(resultModel.data(index, Milou.ResultsModel.IdRole))
        const prefix = "monet-utilities_menu/"
        if (!id.startsWith(prefix)) {
            const ran = resultModel.run(index)
            if (ran || queued) activated()
            return
        }
        if (menuRequest) return
        const request = {}
        menuRequest = request
        function finish(reply) {
            if (menuRequest !== request) return
            menuRequest = null
            if (reply.isValid && reply.value && listView.visible) listView.activated()
        }
        DBus.SessionBus.asyncCall({service: "org.monet.ToolSearch", path: "/runner",
            iface: "org.monet.ToolSearch", member: "WaitForMenu", signature: "(s)",
            arguments: [id.slice("monet-utilities_".length)]}, finish, finish)
        if (!resultModel.run(index)) menuRequest = null
    }
