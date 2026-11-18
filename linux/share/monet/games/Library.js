/* A failed or incomplete helper reply must never replace the working library. */
function read(out, code, fields) {
    if (code !== 0) return null
    try {
        const items = JSON.parse(out)
        const ids = new Set()
        if (!Array.isArray(items) || !items.every(item => {
            if (!item || !fields.every(field => typeof item[field] === "string")
                    || item.id === "" || item.name === "" || ids.has(item.id)) return false
            ids.add(item.id)
            return true
        })) return null
        return items
    } catch (e) {
        return null
    }
}
